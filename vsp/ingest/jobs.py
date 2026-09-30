"""The runnable jobs behind `python3 -m vsp.ingest` (research doc §9, Job A
= niche feed, Job B = our reels). Every job takes an open read-write
connection (vsp.ingest.db.connect), a GraphClient (see make_client) where it
calls the API, the loaded config (vsp.ingest.settings.load) and `now`
(tests pin it), and returns a JSON-serialisable report; nothing prints.

    make_client(con, cfg, env=None, transport=None, ...) -> GraphClient
    run_hashtags(con, client, cfg, niche=None, recent=False, ...)   Job A.1-3
    run_watchlist(con, client, cfg, niche=None, force=False, ...)   Job A.4
    run_own(con, client, cfg, since=None, ...)                      Job B.1
    run_account_insights(con, client, cfg, days=3, day=None, ...)   Job B.3
    run_import(con, path, source, niche=None, cfg=None, ...)        importer
    run_classify(con, cfg, ...)                                     classify
    run_transcribe(con, cfg, candidates=None, ...)                  own renders
    purge(con, cfg=None, now=None, vendor=False, ...)               guardrails
    status(con, cfg=None, now=None) -> dict

report["stopped"] is set (and the job returns early, keeping what it
stored) when Meta rate-limits or usage headers pass the stop threshold
("rate_limited"), or when the token / a permission is the problem
("token" / "permission") — the CLI maps those to exit codes 3 and 2.
media_url values returned by the API live only in memory for the optional
transcription step; they are never written.
"""
import os
import re
from collections import Counter
from datetime import timedelta

from vsp.ingest import db as idb
from vsp.ingest import settings as S
from vsp.ingest.graph import (DEFAULT_VERSION, ENV_APP_ID, ENV_SECRET, ENV_TOKEN,
                              ENV_USER, ENV_VERSION, BudgetExceeded, GraphClient,
                              GraphError, NotConfigured, RateLimited, HashtagBudget)
from vsp.ingest.normalize import is_reel, normalize_item, upsert_reel
from vsp.ingest.util import hours_between, parse_ts, sql_ts, utcnow

TAG_RE = re.compile(r"#vsp-([0-9a-fA-F]{8})\b")


def script_tag(caption):
    """'vsp-<sha8>' from the pipeline's caption tag #vsp-<first 8 hex of
    script_sha256>, or None."""
    m = TAG_RE.search(caption or "")
    return f"vsp-{m.group(1).lower()}" if m else None


def graph_version(cfg=None, env=None):
    e = os.environ if env is None else env
    return ((e.get(ENV_VERSION) or "").strip() or (cfg or {}).get("graph_version")
            or DEFAULT_VERSION)


def make_client(con, cfg, env=None, transport=None, clock=None, sleep=None, log=None,
                require_user=True, rng=None):
    """GraphClient from VSP_IG_* (version: env > config > v26.0) with the
    research-DB hashtag budget attached. Raises NotConfigured."""
    e = os.environ if env is None else env
    missing = [n for n in ([ENV_TOKEN] + ([ENV_USER] if require_user else []))
               if not (e.get(n) or "").strip()]
    if missing:
        raise NotConfigured(missing)
    limit = S.get(cfg or {}, "budget.max_active_hashtags", S.MAX_TAGS_TOTAL)
    budget = HashtagBudget(con, limit=limit, clock=clock) if con is not None else None
    return GraphClient(e[ENV_TOKEN].strip(), (e.get(ENV_USER) or "").strip() or None,
                       version=graph_version(cfg, e),
                       app_secret=(e.get(ENV_SECRET) or "").strip() or None,
                       app_id=(e.get(ENV_APP_ID) or "").strip() or None,
                       transport=transport, budget=budget, sleep=sleep, log=log, rng=rng)


# ------------------------------------------------------------------ report
def _report(job, now_dt, client=None):
    r = {"job": job, "started_at": sql_ts(now_dt), "stopped": None, "errors": [],
         "warnings": [], "inserted": 0, "updated": 0, "adopted": 0,
         "skipped": Counter(), "queries": []}
    if client is not None:
        r["_c0"] = (client.calls, client.retries, len(client.slept))
    return r


def _finish(rep, client=None, con=None):
    if client is not None:
        c0 = rep.pop("_c0", (0, 0, 0))
        rep["api_calls"] = client.calls - c0[0]
        rep["retries"] = client.retries - c0[1]
        slept = client.slept[c0[2]:]
        rep["slept_s"] = round(sum(s for s, _ in slept), 3)
        rep["usage_pct"] = client.usage_pct
        if client.dropped_metrics:
            rep["dropped_metrics"] = sorted(client.dropped_metrics)
    rep.pop("_c0", None)
    rep["skipped"] = dict(rep["skipped"])
    rep["finished_at"] = sql_ts()
    if con is not None:
        con.commit()
    return rep


def _stop_for(rep, err, what):
    """-> True when `err` must stop the whole job (recorded in rep)."""
    if isinstance(err, RateLimited) or getattr(err, "rate_limited", False):
        rep["stopped"] = f"rate_limited: {err}"
        return True
    if getattr(err, "token_problem", False):
        rep["stopped"] = f"token: {err}"
        return True
    if getattr(err, "permission_problem", False):
        rep["stopped"] = f"permission: {err}"
        return True
    rep["errors"].append(f"{what}: {err}")
    return False


def _store(con, rep, items, q, now_dt, **kw):
    """Normalize + upsert API items -> {media_id: media_url} (memory only)."""
    urls = {}
    for it in items:
        row, why = normalize_item(it, now=now_dt, **kw)
        if row is None:
            rep["skipped"][why] += 1
            continue
        st = upsert_reel(con, row)
        rep[st] += 1
        q["kept"] += 1
        mu = it.get("media_url") if isinstance(it, dict) else None
        if mu:
            urls[row["media_id"]] = mu
    con.commit()
    return urls


def _post_fetch(con, cfg, rep, media_urls, classify_after, env, asr_transport,
                ffmpeg_runner, log, ffmpeg=None):
    if media_urls:
        rep["transcribe"] = run_transcribe(
            con, cfg, candidates=[(m, u, "media_url") for m, u in media_urls.items()],
            env=env, transport=asr_transport, runner=ffmpeg_runner, log=log,
            ffmpeg=ffmpeg)
        media_urls.clear()                 # signed CDN URLs: drop them now
    if classify_after:
        rep["classify"] = run_classify(con, cfg)


# ------------------------------------------------------------------ Job A
def run_hashtags(con, client, cfg, niche=None, recent=False, now=None,
                 classify_after=True, env=None, asr_transport=None, ffmpeg_runner=None,
                 log=None, ffmpeg=None):
    """Top (and with recent=True, recent) reels for every configured hashtag
    the rolling-7-day budget allows. Refused tags are never called."""
    log = log or (lambda m: None)
    now_dt = parse_ts(now) or utcnow()
    rep = _report("hashtags", now_dt, client)
    plan = S.hashtag_plan(cfg, niche)
    if not plan:
        rep["errors"].append("no hashtags configured" + (f" for niche {niche}" if niche
                                                         else "") + " in config/ingest.json")
        return _finish(rep, client, con)
    budget = client.budget
    tags = [t for _, t in plan]
    allowed, refused = budget.plan(tags)
    if any(not budget.is_active(t) for t in allowed):
        # §9 A.1: check what Instagram already counts before opening new slots
        try:
            rep["remote_placeholders"] = budget.sync_remote(
                client.recently_searched_hashtags())
            allowed, refused = budget.plan(tags)
        except GraphError as e:
            if _stop_for(rep, e, "recently_searched_hashtags"):
                return _finish(rep, client, con)
    rep["budget"] = {"limit": budget.limit, "used_before": budget.used(),
                     "refused": [{"tag": t, "next_free_at": budget.next_free_at()}
                                 for t in refused]}
    for t in refused:
        rep["warnings"].append(f"#{t} not queried: hashtag budget full "
                               f"(next slot frees at {budget.next_free_at()} UTC)")
    f = cfg.get("fetch") or {}
    media_urls = {}
    edges = [("top_media", "ig_hashtag_top", f.get("top_pages", 2))]
    if recent:
        edges.append(("recent_media", "ig_hashtag_recent", f.get("recent_pages", 1)))
    for n, tag in plan:
        if tag not in allowed:
            continue
        for edge, source, pages in edges:
            q = {"query": "#" + tag, "niche": n, "edge": edge, "items": 0, "kept": 0}
            try:
                items = getattr(client, edge)(tag, limit=f.get("page_limit", 50),
                                              max_pages=pages)
            except BudgetExceeded as e:
                rep["warnings"].append(str(e))
                break
            except GraphError as e:
                if _stop_for(rep, e, f"#{tag} {edge}"):
                    _post_fetch(con, cfg, rep, media_urls, classify_after, env,
                                asr_transport, ffmpeg_runner, log, ffmpeg)
                    return _finish(rep, client, con)
                continue
            q["items"], q["pages"] = len(items), client.last_paging.get("pages")
            media_urls.update(_store(
                con, rep, items, q, now_dt, source=source, source_query="#" + tag,
                niche=n, retention_days=f.get("retention_days", 30),
                max_age_days=S.get(f, "max_age_days.hashtag", 7)))
            rep["queries"].append(q)
            log(f"#{tag} {edge}: {q['items']} items, {q['kept']} reels kept")
    rep["budget"]["used_after"] = budget.used()
    rep["budget"]["remaining"] = budget.remaining()
    _post_fetch(con, cfg, rep, media_urls, classify_after, env, asr_transport,
                ffmpeg_runner, log, ffmpeg)
    idb.set_meta(con, "last_run:hashtags" + (":recent" if recent else ""), sql_ts(now_dt))
    return _finish(rep, client, con)


def run_watchlist(con, client, cfg, niche=None, force=False, now=None,
                  classify_after=True, env=None, asr_transport=None, ffmpeg_runner=None,
                  log=None, ffmpeg=None):
    """Business Discovery on the benchmark handles (once per handle per
    watchlist_min_hours unless force). Rows carry username + the views /
    followers outlier score in notes."""
    log = log or (lambda m: None)
    now_dt = parse_ts(now) or utcnow()
    rep = _report("watchlist", now_dt, client)
    plan = S.watchlist(cfg, niche)
    if not plan:
        rep["warnings"].append("no benchmark handles configured" +
                               (f" for niche {niche}" if niche else "") +
                               " (niches.<niche>.handles in config/ingest.json)")
        return _finish(rep, client, con)
    f = cfg.get("fetch") or {}
    min_h = float(f.get("watchlist_min_hours", 20))
    media_urls = {}
    for n, handle in plan:
        key = f"bd_last:{handle.lower()}"
        last = idb.get_meta(con, key)
        age = hours_between(now_dt, last) if last else None
        if not force and age is not None and 0 <= age < min_h:
            rep["skipped"][f"fetched < {min_h:g} h ago"] += 1
            continue
        q = {"query": "@" + handle, "niche": n, "edge": "business_discovery",
             "items": 0, "kept": 0}
        try:
            account, items = client.business_discovery(
                handle, limit=f.get("watchlist_media_limit", 25),
                max_pages=f.get("watchlist_pages", 1))
        except GraphError as e:
            if _stop_for(rep, e, f"@{handle}"):
                _post_fetch(con, cfg, rep, media_urls, classify_after, env,
                            asr_transport, ffmpeg_runner, log, ffmpeg)
                return _finish(rep, client, con)
            idb.set_meta(con, key, sql_ts(now_dt))   # a bad handle: once a day too
            continue
        q["items"], q["followers"] = len(items), account.get("followers_count")
        media_urls.update(_store(
            con, rep, items, q, now_dt, source="ig_bd", source_query="@" + handle,
            niche=n, username=account.get("username") or handle,
            followers=account.get("followers_count"),
            retention_days=f.get("retention_days", 30),
            max_age_days=S.get(f, "max_age_days.watchlist", 30)))
        idb.set_meta(con, key, sql_ts(now_dt))
        rep["queries"].append(q)
        log(f"@{handle}: {q['items']} items, {q['kept']} reels kept")
    _post_fetch(con, cfg, rep, media_urls, classify_after, env, asr_transport,
                ffmpeg_runner, log, ffmpeg)
    idb.set_meta(con, "last_run:watchlist", sql_ts(now_dt))
    return _finish(rep, client, con)


# ------------------------------------------------------------------ Job B
def run_own(con, client, cfg, since=None, now=None, log=None):
    """Register our own Reels (is_own=1) with the script tag from the caption
    (#vsp-<sha8> -> script_slug 'vsp-<sha8>'). Default since = the newest
    own post seen minus a 2-day overlap."""
    log = log or (lambda m: None)
    now_dt = parse_ts(now) or utcnow()
    rep = _report("own", now_dt, client)
    since_dt = parse_ts(since) if since else None
    if since_dt is None:
        last = parse_ts(idb.get_meta(con, "own:last_posted_at"))
        since_dt = last - timedelta(days=2) if last else None
    rep["since"] = sql_ts(since_dt) if since_dt else None
    username = idb.get_meta(con, "own:username")
    if not username:
        try:
            acct = client.ig_account()
            username = acct.get("username")
            if username:
                idb.set_meta(con, "own:username", username)
            if acct.get("followers_count") is not None:
                idb.set_meta(con, "own:followers_count", acct.get("followers_count"))
        except GraphError as e:
            if _stop_for(rep, e, "ig account"):
                return _finish(rep, client, con)
    f = cfg.get("fetch") or {}
    q = {"query": "own media", "edge": "media", "items": 0, "kept": 0, "tagged": 0}
    try:
        items = client.own_media(since=since_dt, max_pages=f.get("own_pages", 10))
    except GraphError as e:
        _stop_for(rep, e, "own media")
        return _finish(rep, client, con)
    q["items"] = len(items)
    newest = parse_ts(idb.get_meta(con, "own:last_posted_at"))
    for it in items:
        if not is_reel(it):
            rep["skipped"]["not a reel"] += 1
            continue
        row, why = normalize_item(it, source="ig_own",
                                  source_query="@" + username if username else None,
                                  username=username, now=now_dt, is_own=True)
        if row is None:
            rep["skipped"][why] += 1
            continue
        row["script_slug"] = script_tag(it.get("caption"))
        st = upsert_reel(con, row)
        rep[st] += 1
        q["kept"] += 1
        if row["script_slug"]:
            q["tagged"] += 1
            con.execute("UPDATE reels SET script_slug=? WHERE platform='instagram' AND "
                        "media_id=? AND script_slug IS NULL", (row["script_slug"],
                                                               row["media_id"]))
        ts = parse_ts(row.get("posted_at"))
        if ts and (newest is None or ts > newest):
            newest = ts
    if newest:
        idb.set_meta(con, "own:last_posted_at", sql_ts(newest))
    rep["queries"].append(q)
    idb.set_meta(con, "last_run:own", sql_ts(now_dt))
    log(f"own media: {q['items']} items, {q['kept']} reels, {q['tagged']} with #vsp- tags")
    return _finish(rep, client, con)


def run_account_insights(con, client, cfg, days=3, day=None, now=None, log=None):
    """Daily account insights (follows_and_unfollows by follow_type,
    profile_links_taps, views, reach) for the last `days` complete UTC days
    (data lags up to 48 h, so recent days are re-fetched) -> account_metrics."""
    now_dt = parse_ts(now) or utcnow()
    rep = _report("insights", now_dt, client)
    if day:
        targets = [str(day)[:10]]
    else:
        targets = [(now_dt - timedelta(days=k)).strftime("%Y-%m-%d")
                   for k in range(1, max(1, int(days)) + 1)]
    rep["days"], rep["values"] = targets, 0
    for d in targets:
        try:
            res = client.account_insights(d)
        except GraphError as e:
            if _stop_for(rep, e, f"account insights {d}"):
                return _finish(rep, client, con)
            continue
        for metric, breakdown, value in res["values"]:
            con.execute("INSERT OR REPLACE INTO account_metrics(date, metric, breakdown, "
                        "value, captured_at) VALUES (?, ?, ?, ?, ?)",
                        (res["date"], metric, breakdown or "", value, sql_ts(now_dt)))
            rep["values"] += 1
        rep["warnings"] += res["warnings"]
    idb.set_meta(con, "last_run:insights", sql_ts(now_dt))
    return _finish(rep, client, con)


# ------------------------------------------------------------ local jobs
def run_import(con, path, source, niche=None, cfg=None, own=False, now=None,
               dry_run=False, classify_after=True, warn=None):
    from vsp.ingest.importers import import_file
    rep = import_file(con, path, source, niche=niche, cfg=cfg, own=own, now=now,
                      dry_run=dry_run, warn=warn)
    if classify_after and not dry_run and not own:
        rep["classify"] = run_classify(con, cfg)
    return rep


def run_classify(con, cfg=None, reclassify=False, limit=None, llm="auto"):
    from vsp.ingest.classify import classify
    return classify(con, llm=llm, limit=limit, reclassify=reclassify, cfg=cfg)


def run_transcribe(con, cfg, candidates=None, own_renders=False, env=None,
                   transport=None, runner=None, log=None, ffmpeg=None):
    from vsp.ingest import transcribe as T
    cands = list(candidates or [])
    if own_renders:
        cands += T.own_render_candidates(con, limit=T.settings(cfg)["max_per_run"])
    return T.run(con, cands, cfg=cfg, env=env, transport=transport, runner=runner,
                 log=log, ffmpeg=ffmpeg)


def purge(con, cfg=None, now=None, vendor=False, media_ids=(), source=None,
          dry_run=False):
    """Guardrails (research doc §9): delete rows past purge_after (others'
    media not seen for retention_days, or media found deleted), plus on
    request every vendor:* row, one source, or given media ids (deletion
    requests). Own media also loses its reel_metrics + posts rows.
    Aggregates are rebuilt afterwards."""
    now_ts = sql_ts(parse_ts(now) or utcnow())
    conds, args = ["(purge_after IS NOT NULL AND purge_after <= ?)"], [now_ts]
    if vendor:
        conds.append("source LIKE 'vendor:%'")
    if source:
        conds.append("source = ?")
        args.append(source)
    ids = [str(m) for m in media_ids or () if str(m).strip()]
    if ids:
        conds.append("media_id IN (%s)" % ",".join("?" * len(ids)))
        args += ids
    rows = con.execute("SELECT id, media_id, is_own, source, purge_after FROM reels "
                       "WHERE " + " OR ".join(conds), args).fetchall()
    rep = {"job": "purge", "dry_run": bool(dry_run), "reels": len(rows),
           "own": sum(1 for r in rows if r["is_own"]),
           "by_source": dict(Counter(r["source"] or "legacy" for r in rows)),
           "metrics": 0, "posts": 0}
    own_ids = [r["media_id"] for r in rows if r["is_own"] and r["media_id"]]
    for mid in own_ids + ids:
        rep["metrics"] += con.execute("SELECT COUNT(*) FROM reel_metrics WHERE "
                                      "media_id=?", (mid,)).fetchone()[0]
        rep["posts"] += con.execute("SELECT COUNT(*) FROM posts WHERE media_id=?",
                                    (mid,)).fetchone()[0]
    if dry_run:
        return rep
    for r in rows:
        con.execute("DELETE FROM reels WHERE id=?", (r["id"],))
    for mid in set(own_ids + ids):
        con.execute("DELETE FROM reel_metrics WHERE media_id=?", (mid,))
        con.execute("DELETE FROM posts WHERE media_id=?", (mid,))
    from vsp.ingest.classify import rebuild_aggregates
    rep["aggregates"] = rebuild_aggregates(con, cfg)
    idb.set_meta(con, "last_run:purge", now_ts)
    con.commit()
    return rep


def status(con, cfg=None, now=None):
    now_dt = parse_ts(now) or utcnow()
    one = lambda q, a=(): con.execute(q, a).fetchone()[0]  # noqa: E731
    week = sql_ts(now_dt - timedelta(days=7))
    out = {"db": getattr(con, "db_path", None), "schema_version": idb.schema_version(con),
           "reels_total": one("SELECT COUNT(*) FROM reels"),
           "legacy_rows": one("SELECT COUNT(*) FROM reels WHERE source IS NULL"),
           "by_source": {r[0]: r[1] for r in con.execute(
               "SELECT source, COUNT(*) FROM reels WHERE source IS NOT NULL "
               "GROUP BY 1 ORDER BY 2 DESC")},
           "by_niche": {r[0]: r[1] for r in con.execute(
               "SELECT niche, COUNT(*) FROM reels WHERE source IS NOT NULL AND "
               "COALESCE(is_own, 0) = 0 GROUP BY 1 ORDER BY 2 DESC")},
           "fresh_7d": one("SELECT COUNT(*) FROM reels WHERE source IS NOT NULL AND "
                           "COALESCE(is_own, 0) = 0 AND analyzed_at >= ?", (week,)),
           "unclassified": one("SELECT COUNT(*) FROM reels WHERE source IS NOT NULL AND "
                               "COALESCE(is_own, 0) = 0 AND classified_by IS NULL AND "
                               "COALESCE(hook_source, '') != 'curated' AND "
                               "COALESCE(hook_text, '') != ''"),
           "vendor_rows": one("SELECT COUNT(*) FROM reels WHERE " +
                              "source LIKE 'vendor:%'"),
           "vendor_excluded": idb.exclude_vendor(cfg),
           "transcripts": one("SELECT COUNT(*) FROM reels WHERE "
                              "COALESCE(transcript, '') != ''"),
           "own_reels": one("SELECT COUNT(*) FROM reels WHERE is_own = 1"),
           "own_tagged": one("SELECT COUNT(*) FROM reels WHERE is_own = 1 AND "
                             "script_slug IS NOT NULL"),
           "posts_linked": one("SELECT COUNT(*) FROM posts"),
           "metric_snapshots": one("SELECT COUNT(*) FROM reel_metrics"),
           "account_metric_days": one("SELECT COUNT(DISTINCT date) FROM account_metrics"),
           "purge_due": one("SELECT COUNT(*) FROM reels WHERE purge_after IS NOT NULL "
                            "AND purge_after <= ?", (sql_ts(now_dt),)),
           "last_runs": {r[0].split(":", 1)[1]: r[1] for r in con.execute(
               "SELECT key, value FROM meta WHERE key LIKE 'last_run:%' ORDER BY key")}}
    budget = HashtagBudget(con, limit=S.get(cfg or {}, "budget.max_active_hashtags",
                                            S.MAX_TAGS_TOTAL),
                           clock=lambda: now_dt)
    out["hashtag_budget"] = {"limit": budget.limit, "used": budget.used(),
                             "remaining": budget.remaining(),
                             "next_free_at": budget.next_free_at() if budget.used() else None,
                             "active": [a["tag"] for a in budget.active()]}
    return out
