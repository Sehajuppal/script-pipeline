"""`python3 -m vsp.ingest doctor` — what is configured, what is missing, and
the exact steps to fix it (env vars, token /me check, permissions, token
expiry, Instagram account, Public Content Access, hashtag budget, schema
version, research-pack age, transcription, LLM, vendor rows).

    run(env=None, offline=False, transport=None, now=None) ->
        {"ok": bool, "checks": [{"level", "check", "detail"}], "steps": [str]}
    render(result) -> text

Levels: OK, INFO, WARN, FAIL; ok == no FAIL. Online checks only run when a
token is set and offline=False; every call goes through the injectable
transport. Secrets are never printed (only "set (N chars)").
"""
import os
import sys

from vsp import config
from vsp.ingest import db as idb
from vsp.ingest import settings as S
from vsp.ingest.graph import (DEFAULT_VERSION, ENV_APP_ID, ENV_SECRET, ENV_TOKEN,
                              ENV_USER, ENV_VERSION, GraphError, HashtagBudget,
                              NotConfigured)
from vsp.ingest.util import mask, parse_ts, sql_ts, utcnow

REQUIRED_PERMISSIONS = ("instagram_basic", "instagram_manage_insights",
                        "pages_show_list", "pages_read_engagement")
V = DEFAULT_VERSION

STEPS = {
    "config": ("Create the ingest config: `cp config/ingest.example.json "
               "config/ingest.json`, then edit niches -> hashtags (<= 3 per niche, "
               "<= 25 in total) and benchmark Business/Creator handles (or point "
               "VSP_INGEST_CONFIG at your file)."),
    "db": ("Create/migrate the research DB: `python3 -m vsp.ingest init-db` (point "
           "VSP_VIRAL_DB at the research agent's viral.db first to migrate it in "
           "place; the migration is additive)."),
    "account": ("Make the posting Instagram account a Business or Creator account "
                "and link it to a Facebook Page (Instagram app > Settings > Account "
                "type and tools; Page > Settings > Linked accounts)."),
    "app": ("Create a Meta app at https://developers.facebook.com/apps (type "
            "Business), add the products 'Facebook Login for Business' and "
            "'Instagram' (Instagram API with Facebook Login), and pin Graph API "
            f"{V}."),
    "token": ("Mint a token with instagram_basic, instagram_manage_insights, "
              "pages_show_list, pages_read_engagement (Graph API Explorer > your "
              "app > User Token > add the permissions > Generate), exchange it for "
              "a 60-day token: `curl \"https://graph.facebook.com/" + V +
              "/oauth/access_token?grant_type=fb_exchange_token&client_id=$APP_ID"
              "&client_secret=$APP_SECRET&fb_exchange_token=$SHORT_TOKEN\"`, then "
              f"`export {ENV_TOKEN}=<access_token>`."),
    "user_id": ("Find the Instagram Business account id: `curl \"https://graph."
                "facebook.com/" + V + "/me/accounts?fields=name,instagram_business_"
                "account{id,username}&access_token=$" + ENV_TOKEN + "\"`, then "
                f"`export {ENV_USER}=<instagram_business_account.id>` (not the Page "
                "id)."),
    "permissions": ("Re-generate the token with the missing permission(s) listed "
                    "above. Accounts without a role on the app also need Advanced "
                    "Access via App Review."),
    "pca": ("Hashtag Search needs the 'Instagram Public Content Access' feature: "
            "App Dashboard > App Review > Permissions and Features > request it. "
            "Meta requires Business Verification and a reviewable, testable UI "
            "(a login button, a screencast per permission, use-case text: "
            "'developing the business's content strategy'). Until approved, run "
            "`watchlist` (Business Discovery) and `import` only."),
    "refresh": ("Refresh the long-lived token before day 60 (re-run the exchange "
                "around day 50 and update " + ENV_TOKEN + "), or switch to a Page "
                "token minted from a long-lived user token (no fixed expiry)."),
    "secret": (f"Optional: `export {ENV_SECRET}=...` (every call then carries "
               "appsecret_proof; enable 'Require App Secret' in App settings > "
               f"Advanced) and `export {ENV_APP_ID}=...` (lets doctor read the "
               "token's expiry via /debug_token)."),
    "hermes": ("Under Hermes, list VSP_IG_ACCESS_TOKEN, VSP_IG_USER_ID, "
               "VSP_IG_APP_SECRET, VSP_IG_APP_ID, VSP_ASR_API_KEY and VSP_LLM_API_KEY "
               "in terminal.env_passthrough of the vsp profile (Hermes strips "
               "provider keys such as MODEL_API_KEY from commands)."),
    "pack": "Rebuild the research pack: `python3 -m vsp.ingest refresh-pack`.",
    "vendor": ("vendor:* rows may come from scrapers that conflict with Instagram's "
               "Terms (research doc §7): set \"vendor_rows\": \"exclude\" (or "
               "VSP_EXCLUDE_VENDOR=1) to keep them out of the pack, or delete them "
               "with `python3 -m vsp.ingest purge --vendor`."),
    "followers": ("follows_and_unfollows needs >= 100 followers; until then the "
                  "insights job records the other account metrics only."),
}


STEP_ORDER = ["config", "db", "account", "app", "token", "user_id", "permissions",
              "pca", "refresh", "secret", "followers", "vendor", "pack", "hermes"]


class _Doc:
    def __init__(self):
        self.checks, self.steps = [], []

    def add(self, level, check, detail, *step_keys):
        self.checks.append({"level": level, "check": check, "detail": detail})
        for k in step_keys:
            if k and k not in self.steps:
                self.steps.append(k)


def _version_ok(v):
    try:
        return int(str(v).lstrip("v").split(".")[0]) >= 22
    except ValueError:
        return False


def run(env=None, offline=False, transport=None, now=None, cfg_path=None):
    e = os.environ if env is None else env
    now_dt = parse_ts(now) or utcnow()
    d = _Doc()
    d.add("OK" if sys.version_info >= (3, 9) else "FAIL", "python",
          sys.version.split()[0])
    # ------------------------------------------------------------- config
    cfg = None
    try:
        cfg = S.load(cfg_path, required=True)
        n_tags = len(S.hashtag_plan(cfg))
        n_handles = len(S.watchlist(cfg))
        d.add("OK", "config", f"{cfg['_path']}: {n_tags} hashtags, {n_handles} handles")
        if not n_handles:
            d.add("INFO", "watchlist", "no benchmark handles configured (Business "
                  "Discovery idle) — add 10-30 per niche")
    except S.ConfigError as ce:
        d.add("FAIL", "config", "; ".join(ce.problems), "config")
        cfg = S.load(cfg_path, required=False) if not os.path.isfile(
            S.config_path(cfg_path)) else dict(S.DEFAULTS)
    # ----------------------------------------------------------------- DB
    dbp = idb.db_path()
    con = None
    if not idb.exists(dbp):
        d.add("FAIL", "research DB", f"not found at {dbp} (VSP_VIRAL_DB)", "db")
    else:
        ro = idb.connect_ro(dbp)
        try:
            ver = idb.schema_version(ro)
            ingest = idb.has_ingest_schema(ro)
            n = ro.execute("SELECT COUNT(*) FROM reels").fetchone()[0] if \
                "reels" in idb.tables(ro) else 0
        finally:
            ro.close()
        if ver is None or ver < idb.SCHEMA_VERSION or not ingest:
            d.add("WARN", "schema", f"{dbp}: schema version {ver} (need "
                  f"{idb.SCHEMA_VERSION}); {n} reels", "db")
        else:
            d.add("OK", "schema", f"{dbp}: schema version {ver}, {n} reels")
            con = idb.connect(dbp, migrate_schema=False)
    # ---------------------------------------------------------------- env
    tok = (e.get(ENV_TOKEN) or "").strip()
    uid = (e.get(ENV_USER) or "").strip()
    ver = (e.get(ENV_VERSION) or "").strip() or (cfg or {}).get("graph_version") or V
    d.add("OK" if tok else "FAIL", ENV_TOKEN, mask(tok),
          *(() if tok else ("account", "app", "token", "pca", "hermes")))
    d.add("OK" if uid else "FAIL", ENV_USER, uid or "(unset)",
          *(() if uid else ("user_id",)))
    d.add("OK" if _version_ok(ver) else "WARN", ENV_VERSION,
          f"{ver} (default {V}; pin it — v21.0 expires 21 Jan 2027)")
    d.add("OK" if e.get(ENV_SECRET) else "INFO", ENV_SECRET,
          mask(e.get(ENV_SECRET)) + ("" if e.get(ENV_SECRET) else
                                     " — optional (appsecret_proof)"),
          *(() if e.get(ENV_SECRET) else ("secret",)))
    # ------------------------------------------------------------- online
    if tok and not offline:
        _online(d, e, cfg or {}, con, transport, now_dt)
    elif tok:
        d.add("INFO", "online checks", "skipped (--offline)")
    # ------------------------------------------------------------- budget
    if con is not None:
        b = HashtagBudget(con, limit=S.get(cfg or {}, "budget.max_active_hashtags",
                                           S.MAX_TAGS_TOTAL), clock=lambda: now_dt)
        used = b.used()
        d.add("OK" if b.remaining() else "WARN", "hashtag budget",
              f"{used}/{b.limit} unique hashtags in the rolling 7 days, "
              f"{b.remaining()} left" + (f", next slot frees {b.next_free_at()} UTC"
                                         if used else ""))
        vend = con.execute("SELECT COUNT(*) FROM reels WHERE source LIKE "
                           "'vendor:%'").fetchone()[0]
        excl = idb.exclude_vendor(cfg, e)
        if vend:
            d.add("OK" if excl else "WARN", "vendor rows",
                  f"{vend} vendor:* rows ({'excluded' if excl else 'INCLUDED'} in "
                  f"the pack)", *(() if excl else ("vendor",)))
        con.close()
    # --------------------------------------------------------------- pack
    try:
        from vsp import research
        pack, meta = research.load_pack(config.research_pack_path())
        if meta["errors"]:
            d.add("FAIL" if os.path.isfile(meta["path"]) else "WARN", "research pack",
                  "; ".join(meta["errors"])[:200], "pack")
        else:
            age = meta.get("age_hours")
            d.add("WARN" if meta.get("stale") else "OK", "research pack",
                  f"{meta['path']}: age {age} h" + (" (stale > 48 h)" if meta.get(
                      "stale") else "") + f", {pack.get('reels_total', 0)} reels"
                  + (", top_reels present" if pack.get("top_reels") else ""),
                  *(("pack",) if meta.get("stale") else ()))
    except Exception as ex:  # noqa: BLE001
        d.add("WARN", "research pack", f"could not load: {type(ex).__name__}: {ex}")
    # -------------------------------------------------------- transcribe
    from vsp.ingest import transcribe as T
    st = T.status(cfg, e)
    if not st["enabled"]:
        d.add("INFO", "transcribe", "off (optional; config transcribe.enabled)")
    else:
        d.add("OK" if st["ready"] else "WARN", "transcribe",
              "ready (key from " + str(st["key_env"]) + ", ffmpeg " + str(st["ffmpeg"])
              + ")" if st["ready"] else st["reason"])
    # --------------------------------------------------------------- LLM
    from vsp.ingest.classify import resolve_llm
    fn = resolve_llm("auto")
    d.add("INFO", "LLM classify", "vsp.llm.complete_json available (used when a model "
          "is configured; rules otherwise)" if fn else "rules only (vsp.llm."
          "complete_json not present)")
    # ------------------------------------------------------------ learned
    pri = config.priors_path()
    if os.path.isfile(pri):
        age = (now_dt.timestamp() - os.path.getmtime(pri)) / 3600.0
        d.add("OK", "priors", f"{pri} (updated {age:.0f} h ago)")
    else:
        d.add("INFO", "priors", f"{pri} not written yet (python3 -m vsp.feedback learn)")
    ok = not any(c["level"] == "FAIL" for c in d.checks)
    keys = sorted(d.steps, key=lambda k: STEP_ORDER.index(k) if k in STEP_ORDER else 99)
    return {"ok": ok, "checks": d.checks, "steps": [STEPS[k] for k in keys],
            "step_keys": keys, "at": sql_ts(now_dt)}


def _online(d, e, cfg, con, transport, now_dt):
    from vsp.ingest.jobs import make_client
    try:
        client = make_client(con, cfg, env=e, transport=transport, require_user=False,
                             sleep=lambda s: None)
    except (NotConfigured, ValueError) as ex:
        d.add("FAIL", "graph client", str(ex), "token")
        return
    try:
        me = client.whoami()
        d.add("OK", "token /me", f"valid for {me.get('username') or me.get('name') or '?'}"
              f" (id {me.get('id')})")
    except GraphError as ex:
        d.add("FAIL", "token /me", str(ex), "token" if ex.token_problem else None)
        return
    try:
        perms = client.permissions()
        missing = [p for p in REQUIRED_PERMISSIONS if perms.get(p) != "granted"]
        d.add("FAIL" if missing else "OK", "permissions",
              ("missing: " + ", ".join(missing)) if missing else
              "granted: " + ", ".join(REQUIRED_PERMISSIONS),
              *(("permissions",) if missing else ()))
    except GraphError as ex:
        d.add("WARN", "permissions", str(ex))
    if client.app_id and client.app_secret:
        try:
            info = client.token_debug()
            exp = info.get("expires_at")
            if not info.get("is_valid", True):
                d.add("FAIL", "token expiry", "token reported invalid", "token")
            elif exp in (0, None):
                d.add("OK", "token expiry", "no fixed expiry (Page / system-user token)")
            else:
                days = (float(exp) - now_dt.timestamp()) / 86400.0
                d.add("OK" if days > 10 else "WARN", "token expiry",
                      f"expires in {days:.1f} days", *(() if days > 10 else ("refresh",)))
        except GraphError as ex:
            d.add("WARN", "token expiry", str(ex))
    else:
        d.add("INFO", "token expiry", f"unknown (set {ENV_APP_ID} + {ENV_SECRET}); "
              "long-lived user tokens last 60 days", "refresh")
    if not client.ig_user_id:
        return
    try:
        acct = client.ig_account()
        fol = acct.get("followers_count")
        d.add("OK", "instagram account", f"@{acct.get('username')} ({fol} followers, "
              f"{acct.get('media_count')} media)")
        if isinstance(fol, int) and fol < 100:
            d.add("INFO", "follows_and_unfollows", f"{fol} followers < 100",
                  "followers")
    except GraphError as ex:
        d.add("FAIL", "instagram account", str(ex), "user_id")
        return
    try:
        ids = client.recently_searched_hashtags()
        extra = ""
        if con is not None:
            extra = f"; {client.budget.sync_remote(ids)} unknown ids added to the budget"
        d.add("OK", "Public Content Access", f"hashtag search available "
              f"({len(ids)} hashtags active on Instagram's side{extra})")
    except GraphError as ex:
        d.add("FAIL" if ex.permission_problem else "WARN", "Public Content Access",
              str(ex), "pca" if ex.permission_problem else None)


def render(res):
    lines = [f"vsp.ingest doctor — {res['at']} UTC"]
    for c in res["checks"]:
        lines.append(f"  [{c['level']:<4}] {c['check']}: {c['detail']}")
    if res["steps"]:
        lines.append("")
        lines.append("Setup steps (in order):")
        for i, s in enumerate(res["steps"], 1):
            lines.append(f"  {i}. {s}")
    lines.append("")
    lines.append("doctor: " + ("OK" if res["ok"] else "problems found (FAIL above)"))
    return "\n".join(lines)
