"""vsp.feedback — the closed performance-feedback loop: YOUR posted reels ->
Instagram insight snapshots -> labels -> learned/priors.json (read by the
maker's hook-family choice) + learned/PERFORMANCE.md.

    python3 -m vsp.feedback link --media-id ID --manifest PATH [--trial]
    python3 -m vsp.feedback link --auto [--search DIR ...]
    python3 -m vsp.feedback pull [--no-link]
    python3 -m vsp.feedback learn
    python3 -m vsp.feedback report
    python3 -m vsp.feedback status | selfcheck

THE CAPTION TAG. Put `#vsp-<first 8 hex chars of script_sha256>` anywhere in
the posted reel's caption, e.g. `#vsp-0a1b2c3d`. script_sha256 is the
sha256 of the run's script.json bytes (manifest.json -> script_summary ->
script_sha256, also manifest outputs["script.json"]). `python3 -m vsp.ingest
own` stores the tag as reels.script_slug ('vsp-0a1b2c3d'); `link --auto`
finds the manifest.json whose script_sha256 starts with those 8 characters
(under outputs/, VSP_FEEDBACK_SEARCH or --search) and links the two.
Instagram only treats `#vsp` as the hashtag; the suffix is parsed from the
raw caption and stripped from research hooks. No tag (or a trial the
caption cannot carry)? `link --media-id ID --manifest PATH [--trial]`.
Trial Reels have no read-side flag (research doc §4), so --trial records it.

What a link stores (posts table): the manifest's script_summary (prompt,
niche, hook_family, hook_source, hook, presenter, format, duration_s, seed,
candidate_seed, script_sha256); without a script_summary the script.json
next to the manifest is read (its sha256 = script_sha256).

pull: for every own reel (vsp.ingest `own` registers them), one lifetime
insights snapshot per checkpoint of about 24 h, 48 h, 7 d and 28 d
(CHECKPOINTS; a snapshot taken at age a satisfies the largest checkpoint
<= a, so an hourly cron takes exactly one per checkpoint; missed ones are
not back-filled because Instagram only reports lifetime totals). Empty
insights (the up-to-48 h lag) store nothing; deleted media is marked for
`python3 -m vsp.ingest purge`.

learn — labels per own reel, from its latest snapshot at >= 24 h:
    hook_rate   = 1 - reels_skip_rate   (percent vs fraction normalised per
                                         account: any value > 1 => percent)
    watch_ratio = avg_watch_ms / 1000 / duration_s   (linked posts only)
    share_rate  = shares / reach,  save_rate = saves / reach
    composite   = mean of the within-account z-scores of the labels above
                  (over the last WINDOW=60 labelled posts; a label with no
                  spread scores 0)
    success     = composite >= the median composite of those posts
Beta-Bernoulli per (maker niche, hook family) with prior Beta(1, 1):
alpha = 1 + successes, beta = 1 + failures, n = posts; `global` pools the
niches per family. learned/priors.json follows learned/README.md exactly
(schema_version 1, updated_at, metric "composite", families, global).
Paths: config.learned_dir() / config.priors_path() (VSP_LEARNED_DIR).
"""
import argparse
import hashlib
import json
import math
import os
import re
import statistics
import sys
from datetime import timedelta

from vsp import config

CHECKPOINTS = (24, 48, 168, 672)          # hours: ~24 h, 48 h, 7 d, 28 d
WINDOW = 60
METRIC = "composite"
LABELS = ("hook_rate", "watch_ratio", "share_rate", "save_rate")
SUMMARY_KEYS = ("prompt", "niche", "hook_family", "hook_source", "hook", "presenter",
                "format", "duration_s", "seed", "candidate_seed", "script_sha256")
INSIGHT_COLUMNS = {"views": "views", "reach": "reach", "likes": "likes",
                   "comments": "comments", "shares": "shares", "saved": "saves",
                   "reposts": "reposts", "ig_reels_avg_watch_time": "avg_watch_ms",
                   "ig_reels_video_view_total_time": "total_watch_ms",
                   "reels_skip_rate": "skip_rate"}
_SHA = re.compile(r"^[0-9a-f]{64}$")
_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv"}


class LinkError(ValueError):
    pass


def _util():
    from vsp.ingest import util
    return util


def tag_for(sha256):
    return "vsp-" + str(sha256)[:8].lower()


# ------------------------------------------------------------------ link
def load_summary(manifest_path):
    """-> the script summary for a run (see module doc). Raises LinkError."""
    mp = os.path.abspath(manifest_path)
    if os.path.isdir(mp):
        mp = os.path.join(mp, "manifest.json")
    if not os.path.isfile(mp):
        raise LinkError(f"manifest not found: {mp}")
    try:
        with open(mp, encoding="utf-8") as f:
            man = json.load(f)
    except (OSError, ValueError) as e:
        raise LinkError(f"manifest {mp} is not valid JSON: {e}")
    if not isinstance(man, dict):
        raise LinkError(f"manifest {mp} must be a JSON object")
    ss = man.get("script_summary")
    if isinstance(ss, dict) and ss.get("script_sha256"):
        out = {k: ss.get(k) for k in SUMMARY_KEYS}
        out["from"] = "script_summary"
    else:
        sp = os.path.join(os.path.dirname(mp), "script.json")
        if not os.path.isfile(sp):
            raise LinkError(f"{mp} has no script_summary and there is no script.json "
                            f"next to it")
        with open(sp, "rb") as f:
            raw = f.read()
        try:
            s = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as e:
            raise LinkError(f"{sp} is not valid JSON: {e}")
        hook = None
        try:
            from vsp.rubric import hook_line
            hook = hook_line(s) or None
        except Exception:  # noqa: BLE001 — rubric optional here
            for h in s.get("hook_stack") or []:
                if isinstance(h, dict) and h.get("dialogue"):
                    hook = h["dialogue"]
                    break
        seeds = man.get("seeds") if isinstance(man.get("seeds"), dict) else {}
        args = man.get("args") if isinstance(man.get("args"), dict) else {}
        sel = man.get("selected") if isinstance(man.get("selected"), dict) else {}
        out = {"prompt": s.get("prompt"), "niche": s.get("niche"),
               "hook_family": s.get("hook_family"), "hook_source": s.get("hook_source"),
               "hook": hook, "presenter": s.get("presenter"), "format": s.get("format"),
               "duration_s": s.get("duration_s"),
               "seed": s.get("seed", seeds.get("root", args.get("seed"))),
               "candidate_seed": sel.get("seed"),
               "script_sha256": hashlib.sha256(raw).hexdigest(), "from": "script.json"}
    sha = str(out.get("script_sha256") or "").lower()
    if not _SHA.match(sha):
        raise LinkError(f"{mp}: script_sha256 {out.get('script_sha256')!r} is not a "
                        f"sha256 hex digest")
    out["script_sha256"] = sha
    try:
        out["duration_s"] = float(out["duration_s"]) if out.get("duration_s") is not None \
            else None
    except (TypeError, ValueError):
        out["duration_s"] = None
    for k in ("seed", "candidate_seed"):
        try:
            out[k] = int(out[k]) if out.get(k) is not None else None
        except (TypeError, ValueError):
            out[k] = None
    out["manifest_path"] = mp
    out["slug"] = os.path.basename(os.path.dirname(mp))
    out["tag"] = tag_for(sha)
    return out


def link(con, media_id, manifest_path, trial=False, now=None, summary=None):
    """Link one posted reel to the run that produced it. -> posts row dict."""
    u = _util()
    mid = str(media_id or "").strip()
    if not re.fullmatch(r"[0-9]{5,25}", mid):
        raise LinkError(f"--media-id {media_id!r} must be the numeric Instagram media id "
                        f"(GET /{{ig-user-id}}/media, or `python3 -m vsp.ingest own`)")
    s = summary or load_summary(manifest_path)
    now_ts = u.sql_ts(u.parse_ts(now) or u.utcnow())
    reel = con.execute("SELECT url, posted_at, is_own FROM reels WHERE platform="
                       "'instagram' AND media_id=?", (mid,)).fetchone()
    if reel is not None and not reel["is_own"]:
        raise LinkError(f"media {mid} is in the research DB as someone else's reel "
                        f"(is_own=0) — only your own reels can be linked")
    row = {"media_id": mid, "permalink": reel["url"] if reel else None,
           "posted_at": reel["posted_at"] if reel else None,
           "script_sha256": s["script_sha256"], "slug": s.get("slug"),
           "prompt": s.get("prompt"), "niche": s.get("niche"),
           "hook_family": s.get("hook_family"), "hook_source": s.get("hook_source"),
           "presenter": s.get("presenter"), "format": s.get("format"),
           "duration_s": s.get("duration_s"), "seed": s.get("seed"),
           "manifest_path": s.get("manifest_path"), "is_trial": 1 if trial else 0,
           "linked_at": now_ts, "hook": s.get("hook"),
           "candidate_seed": s.get("candidate_seed")}
    old = con.execute("SELECT is_trial FROM posts WHERE media_id=?", (mid,)).fetchone()
    if old is not None:
        row["is_trial"] = 1 if (trial or old["is_trial"]) else 0
        sets = ", ".join(f"{k}=?" for k in row if k != "media_id")
        con.execute(f"UPDATE posts SET {sets} WHERE media_id=?",
                    [v for k, v in row.items() if k != "media_id"] + [mid])
    else:
        cols = list(row)
        con.execute(f"INSERT INTO posts({', '.join(cols)}) VALUES "
                    f"({', '.join('?' for _ in cols)})", [row[c] for c in cols])
    if reel is not None:
        con.execute("UPDATE reels SET script_slug=?, is_trial=MAX(COALESCE(is_trial, 0), ?) "
                    "WHERE platform='instagram' AND media_id=?",
                    (s["tag"], row["is_trial"], mid))
    con.commit()
    return row


def search_roots(extra=None, env=None):
    e = os.environ if env is None else env
    roots = [config.outputs_dir()]
    roots += [p for p in (e.get("VSP_FEEDBACK_SEARCH") or "").split(os.pathsep) if p]
    roots += list(extra or [])
    out = []
    for r in roots:
        a = os.path.abspath(os.path.expanduser(r))
        if a not in out and os.path.isdir(a):
            out.append(a)
    return out


def index_manifests(roots, max_files=20000):
    """{sha8: {script_sha256: [(mtime, manifest_path)]}} for every readable
    manifest.json under `roots`."""
    idx, seen = {}, 0
    for root in roots:
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d not in _SKIP_DIRS]
            if "manifest.json" not in fns:
                continue
            seen += 1
            if seen > max_files:
                return idx
            mp = os.path.join(dp, "manifest.json")
            try:
                s = load_summary(mp)
            except LinkError:
                continue
            idx.setdefault(s["script_sha256"][:8], {}).setdefault(
                s["script_sha256"], []).append((os.path.getmtime(mp), mp))
    return idx


def link_auto(con, roots=None, now=None):
    """Link own reels whose caption carries #vsp-<sha8> (see module doc)."""
    from vsp.ingest.jobs import script_tag
    rows = con.execute(
        "SELECT r.media_id, r.caption, r.script_slug FROM reels r WHERE r.is_own = 1 "
        "AND r.platform = 'instagram' AND r.media_id IS NOT NULL AND NOT EXISTS "
        "(SELECT 1 FROM posts p WHERE p.media_id = r.media_id) ORDER BY r.posted_at"
    ).fetchall()
    rep = {"candidates": len(rows), "linked": [], "untagged": 0, "unmatched": [],
           "ambiguous": [], "roots": list(roots or [])}
    todo = []
    for r in rows:
        tag = r["script_slug"] or script_tag(r["caption"])
        if not tag:
            rep["untagged"] += 1
            continue
        todo.append((r["media_id"], tag))
    if not todo:
        return rep
    idx = index_manifests(rep["roots"])
    for mid, tag in todo:
        cands = idx.get(tag[4:12], {})
        if not cands:
            rep["unmatched"].append({"media_id": mid, "tag": tag})
            continue
        if len(cands) > 1:
            rep["ambiguous"].append({"media_id": mid, "tag": tag,
                                     "scripts": sorted(cands)})
            continue
        (sha, paths), = cands.items()
        mp = max(paths)[1]                      # the newest run of that script
        row = link(con, mid, mp, now=now)
        rep["linked"].append({"media_id": mid, "tag": tag, "manifest": mp,
                              "niche": row["niche"], "hook_family": row["hook_family"]})
    return rep


# ------------------------------------------------------------------ pull
def bucket(age_h):
    """Largest checkpoint <= age_h (None below the first)."""
    got = [c for c in CHECKPOINTS if age_h is not None and age_h >= c]
    return got[-1] if got else None


def pull(con, client, now=None, link_first=True, roots=None, log=None):
    """Insight snapshots for own reels at the due checkpoints -> reel_metrics."""
    from vsp.ingest.graph import GraphError, RateLimited
    u = _util()
    log = log or (lambda m: None)
    now_dt = u.parse_ts(now) or u.utcnow()
    now_ts = u.sql_ts(now_dt)
    rep = {"job": "pull", "at": now_ts, "snapshots": 0, "due": 0, "skipped": {},
           "vanished": [], "errors": [], "stopped": None, "calls0": client.calls}
    if link_first:
        rep["link"] = link_auto(con, roots=roots if roots is not None else search_roots(),
                                now=now_dt)

    def skip(why):
        rep["skipped"][why] = rep["skipped"].get(why, 0) + 1
    rows = con.execute("SELECT media_id, posted_at FROM reels WHERE is_own = 1 AND "
                       "platform = 'instagram' AND media_id IS NOT NULL AND "
                       "purge_after IS NULL ORDER BY posted_at DESC").fetchall()
    for r in rows:
        mid = r["media_id"]
        age = u.hours_between(now_dt, r["posted_at"])
        due = bucket(age)
        if due is None:
            skip("younger than 24 h" if age is not None else "no posted_at")
            continue
        have = {bucket(a[0]) for a in con.execute(
            "SELECT age_h FROM reel_metrics WHERE media_id=?", (mid,))}
        if due in have:
            skip("checkpoint already captured")
            continue
        rep["due"] += 1
        try:
            ins = client.media_insights(mid)
        except RateLimited as e:
            rep["stopped"] = f"rate_limited: {e}"
            break
        except GraphError as e:
            if e.not_found:
                con.execute("UPDATE reels SET purge_after=? WHERE platform='instagram' "
                            "AND media_id=?", (now_ts, mid))
                rep["vanished"].append(mid)
                continue
            if e.token_problem or e.permission_problem:
                rep["stopped"] = f"{'token' if e.token_problem else 'permission'}: {e}"
                break
            rep["errors"].append(f"{mid}: {e}")
            continue
        if not ins:
            skip("no data yet (insights lag up to 48 h)")
            continue
        vals = {col: ins.get(name) for name, col in INSIGHT_COLUMNS.items()}
        con.execute(
            "INSERT OR REPLACE INTO reel_metrics(media_id, captured_at, age_h, views, "
            "reach, likes, comments, shares, saves, reposts, avg_watch_ms, "
            "total_watch_ms, skip_rate, source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (mid, now_ts, int(age), vals["views"], vals["reach"], vals["likes"],
             vals["comments"], vals["shares"], vals["saves"], vals["reposts"],
             vals["avg_watch_ms"], vals["total_watch_ms"], vals["skip_rate"], "api"))
        con.execute("UPDATE reels SET views=COALESCE(?, views), like_count=COALESCE(?, "
                    "like_count), comments=COALESCE(?, comments), shares=COALESCE(?, "
                    "shares), saves=COALESCE(?, saves) WHERE platform='instagram' AND "
                    "media_id=?", (vals["views"], vals["likes"], vals["comments"],
                                   vals["shares"], vals["saves"], mid))
        rep["snapshots"] += 1
        log(f"{mid}: snapshot at {int(age)} h (checkpoint {due} h)")
    con.execute("UPDATE posts SET permalink=(SELECT url FROM reels WHERE reels.media_id="
                "posts.media_id AND reels.platform='instagram'), posted_at=(SELECT "
                "posted_at FROM reels WHERE reels.media_id=posts.media_id AND "
                "reels.platform='instagram') WHERE (permalink IS NULL OR posted_at IS "
                "NULL) AND EXISTS (SELECT 1 FROM reels WHERE reels.media_id="
                "posts.media_id)")
    con.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('last_run:pull', ?)",
                (now_ts,))
    con.commit()
    rep["api_calls"] = client.calls - rep.pop("calls0")
    if client.dropped_metrics:
        rep["dropped_metrics"] = sorted(client.dropped_metrics)
    return rep


# ---------------------------------------------------------------- labels
def _ratio(a, b):
    if a is None or b in (None, 0):
        return None
    try:
        return float(a) / float(b)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def labels(con, window=WINDOW):
    """Per-post labels (module doc). -> {"posts": [...newest first], "median",
    "window", "skip_scale", "stats", "pending": {...}}"""
    rows = con.execute(
        "SELECT r.media_id, r.url, r.posted_at, r.hook_text, r.is_trial AS reel_trial, "
        "p.niche, p.hook_family, p.hook_source, p.hook, p.duration_s, p.is_trial, "
        "p.presenter, p.format, p.slug, p.media_id AS linked FROM reels r LEFT JOIN "
        "posts p ON p.media_id = r.media_id WHERE r.is_own = 1 AND r.platform = "
        "'instagram' AND r.media_id IS NOT NULL AND r.purge_after IS NULL "
        "ORDER BY r.posted_at DESC").fetchall()
    snaps = {}
    for s in con.execute("SELECT * FROM reel_metrics WHERE age_h IS NULL OR age_h >= 24 "
                         "ORDER BY media_id, age_h, captured_at"):
        snaps[s["media_id"]] = s                        # keeps the latest per media
    skips = [s["skip_rate"] for s in snaps.values() if s["skip_rate"] is not None]
    scale = 100.0 if any(float(v) > 1.0 for v in skips) else 1.0
    posts, pending = [], {"no snapshot >= 24 h": 0}
    for r in rows:
        s = snaps.get(r["media_id"])
        if s is None:
            pending["no snapshot >= 24 h"] += 1
            continue
        hr = None
        if s["skip_rate"] is not None:
            hr = min(1.0, max(0.0, 1.0 - float(s["skip_rate"]) / scale))
        wr = _ratio(_ratio(s["avg_watch_ms"], 1000.0), r["duration_s"])
        if wr is not None:
            wr = min(wr, 3.0)                           # replays: cap outliers
        p = {"media_id": r["media_id"], "url": r["url"], "posted_at": r["posted_at"],
             "niche": r["niche"], "hook_family": r["hook_family"],
             "hook_source": r["hook_source"], "hook": r["hook"] or r["hook_text"],
             "presenter": r["presenter"], "format": r["format"], "slug": r["slug"],
             "linked": r["linked"] is not None,
             "trial": bool(r["is_trial"] or r["reel_trial"]),
             "age_h": s["age_h"], "views": s["views"], "reach": s["reach"],
             "hook_rate": hr, "watch_ratio": wr,
             "share_rate": _ratio(s["shares"], s["reach"]),
             "save_rate": _ratio(s["saves"], s["reach"])}
        if all(p[k] is None for k in LABELS):
            pending["snapshot without usable metrics"] = \
                pending.get("snapshot without usable metrics", 0) + 1
            continue
        posts.append(p)
    posts = posts[:window]
    stats = {}
    for k in LABELS:
        xs = [p[k] for p in posts if p[k] is not None]
        mu = statistics.mean(xs) if xs else None
        sd = statistics.pstdev(xs) if len(xs) >= 2 else 0.0
        stats[k] = {"n": len(xs), "mean": mu, "sd": sd}
    for p in posts:
        zs = []
        for k in LABELS:
            if p[k] is None:
                continue
            sd = stats[k]["sd"]
            zs.append((p[k] - stats[k]["mean"]) / sd if sd and sd > 1e-12 else 0.0)
            p["z_" + k] = zs[-1]
        p["composite"] = sum(zs) / len(zs)
    med = statistics.median([p["composite"] for p in posts]) if posts else None
    for p in posts:
        p["success"] = bool(p["composite"] >= med - 1e-12)
    return {"posts": posts, "median": med, "window": window,
            "skip_scale": "percent" if scale == 100.0 else "fraction",
            "stats": stats, "pending": pending}


def posteriors(lab):
    """-> (families {niche: {family: {alpha, beta, n}}}, global {family: ...})"""
    from vsp.ingest.settings import MAKER_NICHES
    from vsp.research import maker_hook_families
    fams = set(maker_hook_families())
    per, glob = {}, {}
    for p in lab["posts"]:
        n, f = p.get("niche"), p.get("hook_family")
        if not p["linked"] or n not in MAKER_NICHES or f not in fams:
            continue
        for tbl in (per.setdefault(n, {}), glob):
            e = tbl.setdefault(f, {"alpha": 1.0, "beta": 1.0, "n": 0})
            e["alpha" if p["success"] else "beta"] += 1.0
            e["n"] += 1
    return ({n: dict(sorted(t.items())) for n, t in sorted(per.items())},
            dict(sorted(glob.items())))


def validate_priors(obj):
    """learned/README.md schema v1 -> list of problems ([] = valid)."""
    errs = []
    if not isinstance(obj, dict):
        return ["priors must be a JSON object"]
    want = {"schema_version", "updated_at", "metric", "families", "global"}
    if set(obj) != want:
        errs.append(f"top-level keys {sorted(obj)} != {sorted(want)}")
    if obj.get("schema_version") != 1:
        errs.append("schema_version must be 1")
    if _util().parse_ts(obj.get("updated_at")) is None:
        errs.append("updated_at must be an ISO timestamp")
    if not isinstance(obj.get("metric"), str) or not obj.get("metric"):
        errs.append("metric must be a non-empty string")

    def entry(where, e):
        if not isinstance(e, dict) or set(e) != {"alpha", "beta", "n"}:
            errs.append(f"{where} must be {{alpha, beta, n}}")
            return
        a, b, n = e["alpha"], e["beta"], e["n"]
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                   and math.isfinite(v) for v in (a, b)) or a <= 0 or b <= 0:
            errs.append(f"{where}: alpha/beta must be positive numbers")
        if not isinstance(n, int) or isinstance(n, bool) or n < 0:
            errs.append(f"{where}: n must be a non-negative integer")
        elif abs((a + b - 2.0) - n) > 1e-9:
            errs.append(f"{where}: alpha + beta - 2 != n (prior Beta(1,1))")
    fams = obj.get("families")
    if not isinstance(fams, dict):
        errs.append("families must be an object")
    else:
        for niche, tbl in fams.items():
            if not isinstance(tbl, dict):
                errs.append(f"families[{niche!r}] must be an object")
                continue
            for fam, e in tbl.items():
                entry(f"families[{niche!r}][{fam!r}]", e)
    glob = obj.get("global")
    if not isinstance(glob, dict):
        errs.append("global must be an object")
    else:
        for fam, e in glob.items():
            entry(f"global[{fam!r}]", e)
    return errs


def _write_atomic(path, text):
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def learn(con, now=None, path=None, window=WINDOW):
    """labels -> posteriors -> learned/priors.json. -> report."""
    u = _util()
    now_dt = u.parse_ts(now) or u.utcnow()
    lab = labels(con, window=window)
    fams, glob = posteriors(lab)
    pri = {"schema_version": 1, "updated_at": u.iso_ts(now_dt), "metric": METRIC,
           "families": fams, "global": glob}
    errs = validate_priors(pri)
    if errs:                      # never write a file the maker would reject
        raise ValueError("priors failed validation: " + "; ".join(errs))
    p = path or config.priors_path()
    _write_atomic(p, json.dumps(pri, indent=1, sort_keys=False) + "\n")
    con.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('last_run:learn', ?)",
                (u.sql_ts(now_dt),))
    con.commit()
    return {"job": "learn", "priors": p, "labelled": len(lab["posts"]),
            "linked": sum(1 for x in lab["posts"] if x["linked"]),
            "median_composite": lab["median"], "skip_scale": lab["skip_scale"],
            "families": {n: {f: e["n"] for f, e in t.items()} for n, t in fams.items()},
            "global": {f: e["n"] for f, e in glob.items()}, "pending": lab["pending"]}


# ---------------------------------------------------------------- report
def _betacf(a, b, x):
    tiny, eps = 1e-300, 3e-14
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 301):
        m2 = 2 * m
        for aa in (m * (b - m) * x / ((qam + m2) * (a + m2)),
                   -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))):
            d = 1.0 + aa * d
            d = 1.0 / (d if abs(d) > tiny else tiny)
            c = 1.0 + aa / c
            c = c if abs(c) > tiny else tiny
            h *= d * c
        if abs(d * c - 1.0) < eps:
            break
    return h


def beta_cdf(x, a, b):
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbt = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
           + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(lbt) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbt) * _betacf(b, a, 1.0 - x) / b


def beta_ppf(q, a, b):
    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if beta_cdf(mid, a, b) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def interval90(a, b):
    return beta_ppf(0.05, a, b), beta_ppf(0.95, a, b)


def _pct(v, digits=0):
    return "—" if v is None else f"{100.0 * v:.{digits}f}%"


def _verdict(e, min_n=3):
    mean = e["alpha"] / (e["alpha"] + e["beta"])
    if e["n"] < min_n:
        return "too early", mean
    lo, hi = interval90(e["alpha"], e["beta"])
    if mean >= 0.6 and lo > 0.3:
        return "working", mean
    if mean <= 0.4 and hi < 0.7:
        return "not working", mean
    return "mixed", mean


def report(con, now=None, path=None, window=WINDOW):
    """-> (path, text) of learned/PERFORMANCE.md."""
    u = _util()
    now_dt = u.parse_ts(now) or u.utcnow()
    lab = labels(con, window=window)
    fams, glob = posteriors(lab)
    posts = lab["posts"]
    L = [f"# PERFORMANCE — what is working for this account", "",
         f"Updated {u.sql_ts(now_dt)} UTC by `python3 -m vsp.feedback report`. "
         f"{len(posts)} labelled own reels (last {window}), "
         f"{sum(1 for p in posts if p['linked'])} linked to a script. A post is a "
         f"**success** when its composite score (mean within-account z-score of hook "
         f"rate = 1 − skip rate, watch ratio, share rate, save rate) is at or above the "
         f"account median"
         + (f" ({lab['median']:+.2f})." if lab["median"] is not None else ".")
         + " Posteriors are Beta(1 + wins, 1 + losses); the maker only lets families "
           "with n ≥ 3 steer its hook choice.", ""]
    L += ["## Niche × hook family", ""]
    if fams:
        L += ["| niche | hook family | n | wins | posterior mean | ~90% interval | verdict |",
              "|---|---|---:|---:|---:|---|---|"]
        for niche, tbl in fams.items():
            for fam, e in sorted(tbl.items(), key=lambda kv: -kv[1]["alpha"] /
                                 (kv[1]["alpha"] + kv[1]["beta"])):
                lo, hi = interval90(e["alpha"], e["beta"])
                v, mean = _verdict(e)
                L.append(f"| {niche} | {fam} | {e['n']} | {int(e['alpha'] - 1)} | "
                         f"{_pct(mean)} | {_pct(lo)}–{_pct(hi)} | {v} |")
    else:
        L.append("_No linked, labelled posts yet._ Tag captions with `#vsp-<sha8>` "
                 "(see below), run `python3 -m vsp.ingest own` and "
                 "`python3 -m vsp.feedback pull`, and wait ≥ 24 h.")
    L += ["", "## All niches (global)", ""]
    if glob:
        L += ["| hook family | n | posterior mean | ~90% interval | verdict |",
              "|---|---:|---:|---|---|"]
        for fam, e in sorted(glob.items(), key=lambda kv: -kv[1]["alpha"] /
                             (kv[1]["alpha"] + kv[1]["beta"])):
            lo, hi = interval90(e["alpha"], e["beta"])
            v, mean = _verdict(e)
            L.append(f"| {fam} | {e['n']} | {_pct(mean)} | {_pct(lo)}–{_pct(hi)} | {v} |")
    else:
        L.append("_Nothing yet._")

    def line(p):
        who = " / ".join(x for x in (p.get("niche"), p.get("hook_family")) if x) or \
            "unlinked"
        hook = (p.get("hook") or "").strip()
        return (f"- {p.get('url') or p['media_id']} — {who}"
                + (f" — “{hook[:90]}”" if hook else "")
                + f" — composite {p['composite']:+.2f} (hook rate {_pct(p['hook_rate'])}, "
                  f"watch {_pct(p['watch_ratio'])}, shares {_pct(p['share_rate'], 1)}, "
                  f"saves {_pct(p['save_rate'], 1)}"
                + (", trial" if p.get("trial") else "") + ")")
    ranked = sorted(posts, key=lambda p: -p["composite"])
    k = min(3, max(1, len(ranked) // 2)) if ranked else 0
    L += ["", "## Best posts", ""] + ([line(p) for p in ranked[:k]] or ["_None yet._"])
    L += ["", "## Worst posts", ""] + ([line(p) for p in ranked[::-1][:k]]
                                       if len(ranked) > 1 else ["_None yet._"])
    L += ["", "## What's working", ""] + _plain_english(lab, fams, glob)
    acct = _account_lines(con, posts, now_dt)
    if acct:
        L += ["", "## Follows by posting day (account insights)", ""] + acct
    pend = dict(lab["pending"])
    unlinked = con.execute("SELECT COUNT(*) FROM reels r WHERE r.is_own = 1 AND "
                           "r.purge_after IS NULL AND NOT EXISTS (SELECT 1 FROM posts p "
                           "WHERE p.media_id = r.media_id)").fetchone()[0]
    L += ["", "## Pending", "",
          f"- {unlinked} own reels are not linked to a script (no `#vsp-` tag, or no "
          f"matching manifest.json) — they count toward the account median only.",
          f"- {pend.get('no snapshot >= 24 h', 0)} own reels have no insights snapshot "
          f"at ≥ 24 h yet."]
    L += ["", "## How the loop works", "",
          "1. Post the reel with `#vsp-<first 8 hex of script_sha256>` in the caption "
          "(manifest.json → script_summary.script_sha256), or link it by hand: "
          "`python3 -m vsp.feedback link --media-id ID --manifest outputs/<slug>/"
          "manifest.json [--trial]`.",
          "2. Hourly: `python3 -m vsp.ingest own && python3 -m vsp.feedback pull` "
          "(snapshots at ~24 h, 48 h, 7 d, 28 d).",
          "3. Daily: `python3 -m vsp.feedback learn && python3 -m vsp.feedback report` "
          "→ learned/priors.json + this file."]
    text = "\n".join(L) + "\n"
    p = path or os.path.join(config.learned_dir(), "PERFORMANCE.md")
    _write_atomic(p, text)
    return p, text


def _plain_english(lab, fams, glob):
    out = []
    posts = lab["posts"]
    if len(posts) < 2:
        return ["- Not enough labelled posts yet to say anything (need ≥ 2; the maker "
                "needs ≥ 3 per family before priors steer it)."]
    for niche, tbl in fams.items():
        judged = [(fam, e) + _verdict(e) for fam, e in tbl.items()]
        good = sorted([j for j in judged if j[2] == "working"], key=lambda j: -j[3])
        bad = sorted([j for j in judged if j[2] == "not working"], key=lambda j: j[3])
        for fam, e, _, mean in good[:2]:
            out.append(f"- In **{niche}**, **{fam}** hooks beat your median "
                       f"{int(e['alpha'] - 1)} of {e['n']} times (posterior {_pct(mean)})"
                       f" — keep using them.")
        for fam, e, _, mean in bad[:1]:
            out.append(f"- In **{niche}**, **{fam}** hooks underperform ("
                       f"{int(e['alpha'] - 1)} of {e['n']} above median, posterior "
                       f"{_pct(mean)}) — try another family.")
        early = [j for j in judged if j[2] == "too early"]
        if early and not good and not bad:
            best = max(early, key=lambda j: j[3])
            out.append(f"- In **{niche}**, too early to call: the best early signal is "
                       f"**{best[0]}** ({int(best[1]['alpha'] - 1)} of {best[1]['n']}); "
                       f"post ≥ 3 per family.")
    if glob:
        fam, e = max(glob.items(), key=lambda kv: kv[1]["alpha"] / (kv[1]["alpha"] +
                                                                    kv[1]["beta"]))
        out.append(f"- Across niches, **{fam}** leads ({int(e['alpha'] - 1)} of {e['n']} "
                   f"above median).")
    wins = [p for p in posts if p["success"]]
    rest = [p for p in posts if not p["success"]]
    names = {"hook_rate": "hook rate (1 − 3-second skip rate)",
             "watch_ratio": "watch ratio (avg watch ÷ duration)",
             "share_rate": "share rate", "save_rate": "save rate"}
    diffs = []
    for k in LABELS:
        sd = lab["stats"][k]["sd"]
        a = [p[k] for p in wins if p[k] is not None]
        b = [p[k] for p in rest if p[k] is not None]
        if a and b and sd:
            diffs.append(((statistics.mean(a) - statistics.mean(b)) / sd, k,
                          statistics.mean(a), statistics.mean(b)))
    if diffs:
        d, k, a, b = max(diffs)
        digits = 1 if k in ("share_rate", "save_rate") else 0
        out.append(f"- The biggest gap between your winners and the rest is "
                   f"{names[k]}: {_pct(a, digits)} vs {_pct(b, digits)}.")
    st = lab["stats"]["hook_rate"]
    if st["n"]:
        out.append(f"- Average hook rate across the last {len(posts)} posts: "
                   f"{_pct(st['mean'])} of viewers stay past 3 seconds.")
    trials = [p for p in posts if p.get("trial")]
    if trials:
        tw = sum(1 for p in trials if p["success"])
        out.append(f"- Trial Reels: {tw} of {len(trials)} beat the median (trials reach "
                   f"non-followers first, so compare them with care).")
    return out or ["- No clear pattern yet."]


def _account_lines(con, posts, now_dt):
    u = _util()
    since = (now_dt - timedelta(days=14)).strftime("%Y-%m-%d")
    rows = con.execute("SELECT date, breakdown, value FROM account_metrics WHERE metric="
                       "'follows_and_unfollows' AND date >= ? ORDER BY date DESC",
                       (since,)).fetchall()
    if not rows:
        return []
    by_day = {}
    for r in rows:
        by_day.setdefault(r["date"], {})[r["breakdown"] or "total"] = r["value"]
    out = []
    for day, v in sorted(by_day.items(), reverse=True)[:7]:
        todays = [p for p in posts if str(p.get("posted_at") or "")[:10] == day]
        total = v.get("total")
        out.append(f"- {day}: {total if total is not None else '?'} follows "
                   f"(followers {v.get('follower', '?')}, non-followers "
                   f"{v.get('non_follower', '?')}) — {len(todays)} post(s) that day"
                   + (": " + ", ".join((p.get("hook_family") or "unlinked")
                                       for p in todays) if todays else ""))
    return out


def status(con, now=None):
    u = _util()
    now_dt = u.parse_ts(now) or u.utcnow()
    one = lambda q, a=(): con.execute(q, a).fetchone()[0]  # noqa: E731
    due = 0
    for r in con.execute("SELECT media_id, posted_at FROM reels WHERE is_own = 1 AND "
                         "purge_after IS NULL AND media_id IS NOT NULL"):
        b = bucket(u.hours_between(now_dt, r["posted_at"]))
        if b is not None and b not in {bucket(a[0]) for a in con.execute(
                "SELECT age_h FROM reel_metrics WHERE media_id=?", (r["media_id"],))}:
            due += 1
    pri = config.priors_path()
    info = None
    if os.path.isfile(pri):
        try:
            with open(pri, encoding="utf-8") as f:
                obj = json.load(f)
            info = {"path": pri, "updated_at": obj.get("updated_at"),
                    "niches": len(obj.get("families") or {}),
                    "global_families": len(obj.get("global") or {}),
                    "valid": not validate_priors(obj)}
        except (OSError, ValueError):
            info = {"path": pri, "valid": False}
    return {"own_reels": one("SELECT COUNT(*) FROM reels WHERE is_own = 1"),
            "own_tagged": one("SELECT COUNT(*) FROM reels WHERE is_own = 1 AND "
                              "script_slug IS NOT NULL"),
            "linked": one("SELECT COUNT(*) FROM posts"),
            "trials": one("SELECT COUNT(*) FROM posts WHERE is_trial = 1"),
            "snapshots": one("SELECT COUNT(*) FROM reel_metrics"),
            "checkpoints_due": due,
            "vanished": one("SELECT COUNT(*) FROM reels WHERE is_own = 1 AND "
                            "purge_after IS NOT NULL"),
            "last_runs": {k.split(":", 1)[1]: v for k, v in con.execute(
                "SELECT key, value FROM meta WHERE key IN ('last_run:pull', "
                "'last_run:learn', 'last_run:own')")},
            "priors": info,
            "performance_md": os.path.join(config.learned_dir(), "PERFORMANCE.md")
            if os.path.isfile(os.path.join(config.learned_dir(), "PERFORMANCE.md"))
            else None}


# --------------------------------------------------------------- selfcheck
def selfcheck():
    """Hermetic self-check -> (ok, lines): temp DB (VSP_VIRAL_DB), temp
    learned dir (VSP_LEARNED_DIR), canned Graph API responses from
    tests/fixtures/ig, network disabled; the caller's env is restored."""
    from vsp.ingest.checks import run_feedback
    return run_feedback()


# --------------------------------------------------------------------- CLI
def _parser():
    ap = argparse.ArgumentParser(
        prog="python3 -m vsp.feedback",
        description="Closed performance-feedback loop over YOUR posted reels.",
        epilog="caption tag: #vsp-<first 8 hex chars of script_sha256> "
               "(manifest.json -> script_summary.script_sha256). Hermes cron: hourly "
               "`python3 -m vsp.ingest own && python3 -m vsp.feedback pull`; daily "
               "`python3 -m vsp.feedback learn && python3 -m vsp.feedback report`. "
               "Docs: docs/ws-data-notes.md")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--db", help="research DB path (sets VSP_VIRAL_DB)")
    sub = ap.add_subparsers(dest="cmd", metavar="command")
    p = sub.add_parser("link", help="link posted reels to the runs that made them")
    p.add_argument("--media-id")
    p.add_argument("--manifest", help="outputs/<slug>/manifest.json (or its folder)")
    p.add_argument("--trial", action="store_true", help="it was posted as a Trial Reel")
    p.add_argument("--auto", action="store_true",
                   help="match own-media captions carrying #vsp-<sha8>")
    p.add_argument("--search", action="append", default=[],
                   help="extra folder to search for manifest.json (repeatable)")
    p = sub.add_parser("pull", help="insight snapshots at ~24h/48h/7d/28d")
    p.add_argument("--no-link", action="store_true", help="skip `link --auto` first")
    p.add_argument("--search", action="append", default=[])
    sub.add_parser("learn", help="labels -> learned/priors.json")
    sub.add_parser("report", help="learned/PERFORMANCE.md")
    sub.add_parser("status")
    sub.add_parser("selfcheck")
    return ap


def _out(obj, as_json, text):
    print(json.dumps(obj, indent=1, default=str, ensure_ascii=False) if as_json else text)


def main(argv=None):
    if config.REPO not in sys.path:
        sys.path.insert(0, config.REPO)
    ap = _parser()
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help()
        return 2
    if a.db:
        os.environ["VSP_VIRAL_DB"] = os.path.abspath(a.db)
    if a.cmd == "selfcheck":
        ok, lines = selfcheck()
        _out({"ok": ok, "lines": lines}, a.json,
             "\n".join(lines) + "\nvsp.feedback selfcheck: " + ("OK" if ok else "FAILED"))
        return 0 if ok else 1
    from vsp.ingest import db as idb
    try:
        con = idb.connect()
    except (idb.DBMissing, idb.MigrationError) as e:
        print(str(e), file=sys.stderr)
        return 2
    try:
        if a.cmd == "link":
            if a.auto:
                rep = link_auto(con, roots=search_roots(a.search))
                _out(rep, a.json, f"linked {len(rep['linked'])} of {rep['candidates']} "
                     f"unlinked own reels; untagged {rep['untagged']}, no manifest for "
                     f"{[u['tag'] for u in rep['unmatched']]}, ambiguous "
                     f"{len(rep['ambiguous'])}; searched {rep['roots']}")
                return 0
            if not (a.media_id and a.manifest):
                print("link needs --media-id ID --manifest PATH (or --auto)",
                      file=sys.stderr)
                return 2
            try:
                row = link(con, a.media_id, a.manifest, trial=a.trial)
            except LinkError as e:
                print(f"link refused: {e}", file=sys.stderr)
                return 2
            _out(row, a.json, f"linked {row['media_id']} -> {row['manifest_path']} "
                 f"({row['niche']} / {row['hook_family']}, tag vsp-"
                 f"{row['script_sha256'][:8]}{', trial' if row['is_trial'] else ''})")
            return 0
        if a.cmd == "pull":
            from vsp.ingest import jobs
            from vsp.ingest import settings as S
            from vsp.ingest.graph import NotConfigured
            try:
                cfg = S.load(required=False)
            except S.ConfigError:
                cfg = dict(S.DEFAULTS)
            try:
                client = jobs.make_client(con, cfg,
                                          log=lambda m: print(m, file=sys.stderr))
            except NotConfigured as e:
                print(str(e), file=sys.stderr)
                return 2
            rep = pull(con, client, link_first=not a.no_link,
                       roots=search_roots(a.search),
                       log=None if a.json else (lambda m: print(m, file=sys.stderr)))
            _out(rep, a.json, f"{rep['snapshots']} snapshots ({rep['due']} due, "
                 f"{rep['api_calls']} API calls); skipped {rep['skipped']}; vanished "
                 f"{rep['vanished']}; errors {rep['errors']}"
                 + (f"; linked {len(rep['link']['linked'])}" if rep.get("link") else "")
                 + (f"\nSTOPPED: {rep['stopped']}" if rep["stopped"] else ""))
            st = rep["stopped"] or ""
            return 3 if st.startswith("rate_limited") else (2 if st else 0)
        if a.cmd == "learn":
            rep = learn(con)
            _out(rep, a.json, f"wrote {rep['priors']}: {rep['labelled']} labelled posts "
                 f"({rep['linked']} linked), median composite {rep['median_composite']}, "
                 f"families {rep['families']}")
            return 0
        if a.cmd == "report":
            p, text = report(con)
            _out({"path": p}, a.json, f"wrote {p}\n\n{text}")
            return 0
        if a.cmd == "status":
            rep = status(con)
            _out(rep, a.json, json.dumps(rep, indent=1, default=str))
            return 0
    finally:
        con.close()
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
