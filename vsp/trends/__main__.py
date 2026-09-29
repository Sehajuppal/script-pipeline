"""python3 -m vsp.trends <command> — see `python3 -m vsp.trends --help`.

Exit codes (vsp.ingest's convention): 0 ok · 1 error (invalid or rejected
rows, a failed check) · 2 usage / configuration missing (no dataset, no
API key, no research DB) · 3 nothing to do (empty dataset, no fitting
recipe, nothing matched, or stopped by the YouTube quota: resume next run).
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

from vsp import config

if config.REPO not in sys.path:          # the router's maker voter lives at the root
    sys.path.insert(0, config.REPO)

HELP = """commands:
  init [--git]                       create the dataset layout (trends-db-template/)
  add FILE|-                         JSON / JSONL / CSV observations: validate + append
  observe --platform P --permalink URL [...]   one post, flags form (agent/user)
  validate                           validate every file in the dataset
  import-ingest [--db PATH] [--days 30]   reels from the vsp.ingest research DB
  youtube --query Q [--region US] [--max 25] [--days 7] [--niche N] [--dry-run] [--fixture DIR]
  tiktok-cc FILE [--region R] [--industry I] [--date D]   hand-copied Creative Center list
  score                              -> derived/outliers.jsonl
  lifecycle                          -> derived/trends.json
  synth [--niche N] [--presenter ai|human] [--k 10] [--invent 3]   -> derived/recipes.jsonl
  digest [--date D]                  -> digests/D.md (prints the path)
  recipes [--niche N] [--top 5] [--id ID]
  steer "<prompt>" [--presenter ai|human] [--format F] [--recipe ID]
  watchlist-suggest [--min-x 5] [--cap 150] [--apply] [--config PATH]
  purge --creator H | --source S | --older-than DAYS | --expired  [--platform P] [--dry-run]
  status                             counts, last imports, quota
  selfcheck                          hermetic self-check (no network)

global flags (before or after the command): --dir DIR (else VSP_TRENDS_DIR, else
~/viral-trends-db), --json, --today YYYY-MM-DD (pins the clock at 12:00 UTC)
env: VSP_TRENDS_DIR, VSP_YT_API_KEY, VSP_TRENDS_NICHES, VSP_VIRAL_DB, VSP_INGEST_CONFIG
docs: docs/ws-trends-notes.md, .agents/skills/vsp-trends/SKILL.md"""

EXIT_OK, EXIT_ERR, EXIT_USAGE, EXIT_NOTHING = 0, 1, 2, 3


def _common():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--dir", default=argparse.SUPPRESS, help="dataset directory")
    p.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                   help="machine-readable output")
    p.add_argument("--today", default=argparse.SUPPRESS, help="YYYY-MM-DD (tests)")
    return p


def _parser():
    common = _common()
    ap = argparse.ArgumentParser(prog="python3 -m vsp.trends", parents=[common],
                                 description="Trend intelligence for the script pipeline.",
                                 epilog=HELP,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", metavar="command")

    def cmd(name, **kw):
        return sub.add_parser(name, parents=[common], **kw)
    cmd("init").add_argument("--git", action="store_true",
                             help="also `git init` with HEAD on branch data")
    p = cmd("add")
    p.add_argument("file", help="JSON / JSONL / CSV file, or - for stdin")
    p.add_argument("--source", help="default source for rows without one")
    p.add_argument("--niche", help="default niche for rows without one")
    p = cmd("observe")
    for flag in ("--platform", "--permalink"):
        p.add_argument(flag, required=True)
    for flag in ("--post-id", "--posted-at", "--handle", "--first-words", "--archetype",
                 "--frame0", "--on-screen-text", "--format-key", "--audio-type",
                 "--sound-id", "--sound-title", "--emotion", "--participation", "--cta",
                 "--vibe", "--production-cost", "--notes", "--niche", "--topic",
                 "--language", "--region", "--beats", "--tags", "--trend-keys"):
        p.add_argument(flag)
    for flag in ("--views", "--followers", "--likes", "--comments", "--shares", "--saves",
                 "--replicability", "--median-views", "--baseline-n"):
        p.add_argument(flag, type=int)
    for flag in ("--duration", "--cuts-per-10s"):
        p.add_argument(flag, type=float)
    for flag in ("--payoff-reveal", "--loop", "--series", "--needs-real-person"):
        p.add_argument(flag, choices=("yes", "no"))
    p.add_argument("--source", default="agent_observed",
                   choices=("agent_observed", "user_shared", "tiktok_creative_center"))
    cmd("validate")
    p = cmd("import-ingest")
    p.add_argument("--db", help="research DB (default VSP_VIRAL_DB)")
    p.add_argument("--days", type=int, default=30, help="rows seen in the last N days")
    p = cmd("youtube")
    p.add_argument("--query", required=True)
    p.add_argument("--region", default="US")
    p.add_argument("--max", type=int, default=25)
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--niche")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--fixture", help="directory of canned API responses (tests)")
    p = cmd("tiktok-cc")
    p.add_argument("file")
    p.add_argument("--region")
    p.add_argument("--industry")
    p.add_argument("--date")
    cmd("score")
    cmd("lifecycle")
    p = cmd("synth")
    p.add_argument("--niche", action="append", default=[],
                   help="repeatable or comma-separated (default VSP_TRENDS_NICHES, else "
                        "the maker niches seen in the data)")
    p.add_argument("--presenter", choices=("ai", "human"))
    p.add_argument("--k", type=int, default=10)
    p.add_argument("--invent", type=int, default=3)
    cmd("digest").add_argument("--date")
    p = cmd("recipes")
    p.add_argument("--niche")
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--id")
    p = cmd("steer")
    p.add_argument("prompt")
    p.add_argument("--presenter", choices=("ai", "human"))
    p.add_argument("--format")
    p.add_argument("--recipe", default="auto")
    p = cmd("watchlist-suggest")
    p.add_argument("--min-x", type=float, default=5.0)
    p.add_argument("--cap", type=int, default=150)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--config", help="vsp.ingest config (default VSP_INGEST_CONFIG)")
    p = cmd("purge")
    p.add_argument("--creator")
    p.add_argument("--platform")
    p.add_argument("--source")
    p.add_argument("--older-than", type=int, metavar="DAYS")
    p.add_argument("--expired", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    cmd("status")
    cmd("selfcheck")
    return ap


def _err(msg):
    print(msg, file=sys.stderr)


def _out(obj, as_json, text):
    if as_json:
        print(json.dumps(obj, indent=1, sort_keys=True, default=str, ensure_ascii=False))
    elif text is not None:
        print(text)


def _now(today):
    if not today:
        return datetime.now(timezone.utc).replace(microsecond=0)
    try:
        d = datetime.strptime(today, "%Y-%m-%d")
    except ValueError:
        raise SystemExit(_usage(f"--today must be YYYY-MM-DD, got {today!r}"))
    return d.replace(hour=12, tzinfo=timezone.utc)


def _usage(msg):
    _err(msg)
    return EXIT_USAGE


def _rejections(rep):
    lines = []
    for r in rep.get("rejected") or []:
        where = r.get("permalink") or r.get("video") or f"row {r.get('row')}"
        lines.append(f"  rejected {where}: " + "; ".join(r.get("errors") or []))
    return lines


def _observe_raw(a):
    yn = {"yes": True, "no": False, None: None}
    raw = {"platform": a.platform, "permalink": a.permalink, "post_id": a.post_id,
           "posted_at": a.posted_at, "source": a.source, "handle": a.handle,
           "followers": a.followers, "median_views": a.median_views,
           "baseline_n": a.baseline_n, "views": a.views, "likes": a.likes,
           "comments": a.comments, "shares": a.shares, "saves": a.saves,
           "first_words": a.first_words, "archetype": a.archetype, "frame0": a.frame0,
           "on_screen_text": a.on_screen_text, "format_key": a.format_key,
           "audio_type": a.audio_type, "sound_id": a.sound_id, "sound_title": a.sound_title,
           "emotion": a.emotion, "participation": a.participation, "cta": a.cta,
           "vibe": a.vibe, "production_cost": a.production_cost,
           "replicability": a.replicability, "notes": a.notes, "niche": a.niche,
           "topic": a.topic, "language": a.language, "region": a.region,
           "duration_s": a.duration, "cuts_per_10s": a.cuts_per_10s, "beats": a.beats,
           "payoff_reveal": yn[a.payoff_reveal], "loop": yn[a.loop], "series": yn[a.series],
           "needs_real_person": yn[a.needs_real_person], "tags": a.tags,
           "trend_keys": a.trend_keys}
    return {k: v for k, v in raw.items() if v is not None}


def _add_text(rep):
    head = (f"accepted {rep['accepted']} of {rep['rows']} ({rep.get('new', 0)} new, "
            f"{rep.get('updated', 0)} updated, {rep.get('refreshed', 0)} refreshed, "
            f"{rep.get('unchanged', 0)} unchanged)"
            + (f" -> {rep['file']}" if rep.get("file") else ""))
    return "\n".join([head] + _rejections(rep))


def _add_code(rep):
    if rep["rejected"]:
        return EXIT_ERR
    changed = rep.get("new", 0) + rep.get("updated", 0) + rep.get("refreshed", 0)
    return EXIT_OK if changed else EXIT_NOTHING


def _niches(values):
    out = []
    for v in values or []:
        out += [x.strip() for x in str(v).split(",") if x.strip()]
    return out


def main(argv=None):
    ap = _parser()
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help()
        return EXIT_USAGE
    as_json = bool(getattr(a, "json", False))
    if a.cmd == "selfcheck":
        from vsp.trends.selfcheck import selfcheck
        ok, lines = selfcheck()
        if as_json:
            _out({"ok": ok, "lines": lines}, True, None)
        else:
            print("\n".join(lines))
            print("vsp.trends selfcheck: " + ("OK" if ok else "FAILED"))
        return EXIT_OK if ok else EXIT_ERR
    now = _now(getattr(a, "today", None))
    from vsp.trends import importers as IM
    from vsp.trends import jobs, store
    d = store.dataset_dir(getattr(a, "dir", None))
    try:
        return _dispatch(a, d, now, as_json, jobs, store, IM)
    except store.NotInitialized as e:
        return _usage(str(e))
    except IM.NotConfigured as e:
        return _usage(f"not configured: {e}")
    except IM.ImportFailed as e:
        _err(f"import failed: {e}")
        return EXIT_USAGE if "not found" in str(e) else EXIT_ERR


def _dispatch(a, d, now, as_json, jobs, store, IM):
    if a.cmd == "init":
        created = store.init(d)
        rep = {"dir": d, "created": created}
        if a.git:
            rep["git"] = store.git_init_data_branch(d)
        _out(rep, as_json, f"{d}: created {len(created)} file(s)" +
             (f"; {rep['git']}" if a.git else ""))
        return EXIT_OK
    if a.cmd == "add":
        raws, fmt = IM.read_records(a.file)
        if not raws:
            _out({"rows": 0, "format": fmt}, as_json, "nothing to add (empty input)")
            return EXIT_NOTHING
        defaults = {k: v for k, v in (("source", a.source), ("niche", a.niche)) if v}
        rep = jobs.run_add(d, raws, now, defaults=defaults)
        rep["format"] = fmt
        _out(rep, as_json, _add_text(rep))
        return _add_code(rep)
    if a.cmd == "observe":
        rep = jobs.run_add(d, [_observe_raw(a)], now)
        _out(rep, as_json, _add_text(rep))
        return _add_code(rep)
    if a.cmd == "validate":
        rep = jobs.validate_dataset(d, now)
        text = "\n".join([f"checked {rep['checked']}: " +
                          ("OK" if rep["ok"] else f"{len(rep['problems'])} problem(s)")]
                         + [f"  {p}" for p in rep["problems"][:200]]
                         + [f"  warning: {w}" for w in rep["warnings"]])
        _out(rep, as_json, text)
        return EXIT_OK if rep["ok"] else EXIT_ERR
    if a.cmd == "import-ingest":
        db = os.path.abspath(a.db) if a.db else config.viral_db_path()
        rep = IM.import_ingest(d, db, now, days=a.days)
        text = "\n".join([f"import-ingest {db}: read {rep['read']}, candidates "
                          f"{rep['candidates']}, new {rep.get('new', 0)}, updated "
                          f"{rep.get('updated', 0)}, refreshed {rep.get('refreshed', 0)}, "
                          f"unchanged {rep['unchanged']}; creators {rep['creators']}"]
                         + [f"  skipped {k}: {v}" for k, v in sorted(rep["skipped"].items())]
                         + _rejections(rep))
        _out(rep, as_json, text)
        if rep["rejected"]:
            return EXIT_ERR
        return EXIT_OK if (rep.get("new") or rep.get("updated") or rep.get("refreshed")) \
            else EXIT_NOTHING
    if a.cmd == "youtube":
        rep = IM.youtube(d, now, a.query, region=a.region, max_results=a.max, days=a.days,
                         niche=a.niche, dry_run=a.dry_run, fixture=a.fixture)
        if a.dry_run:
            text = "\n".join(["dry run (no network unless --fixture; nothing written):"] +
                             [f"  GET {u}" for u in rep["requests"]] +
                             ([f"  estimated units: {rep['estimated_units']}"]
                              if "estimated_units" in rep else
                              [f"  units: {rep['units']}, observations: "
                               f"{rep['observations']}"]))
        else:
            text = "\n".join([f"youtube {a.query!r}: {rep['shorts']} Shorts of {rep['videos']} "
                              f"videos, {rep['channels']} channels ({rep['baselines']} "
                              f"baselines); new {rep.get('new', 0)}, updated "
                              f"{rep.get('updated', 0)}; {rep['units']} units "
                              f"(today {rep['quota_today']['units']}, search "
                              f"{rep['quota_today']['search_calls']})"]
                             + ([f"  STOPPED: {rep['stopped']}"] if rep["stopped"] else [])
                             + _rejections(rep))
        _out(rep, as_json, text)
        if rep.get("stopped"):
            return EXIT_NOTHING
        return EXIT_ERR if rep["rejected"] else EXIT_OK
    if a.cmd == "tiktok-cc":
        rep = IM.tiktok_cc(d, a.file, now, region=a.region, industry=a.industry, date=a.date)
        text = "\n".join([f"tiktok-cc: accepted {rep['accepted']} of {rep['rows']} signals "
                          f"({rep['new']} new, {rep['updated']} updated, "
                          f"{rep['unchanged']} unchanged)"] + _rejections(rep))
        _out(rep, as_json, text)
        if rep["rejected"]:
            return EXIT_ERR
        return EXIT_OK if (rep["new"] or rep["updated"]) else EXIT_NOTHING
    if a.cmd == "score":
        rep = jobs.run_score(d, now)
        _out(rep, as_json, f"scored {rep['scored']} of {rep['observations']} posts "
                           f"({rep['unscored']} unscored); {rep['outliers']} outliers "
                           f"{rep['by_band']}" + (f" -> {rep['file']}" if rep["file"] else ""))
        return EXIT_OK if rep["observations"] else EXIT_NOTHING
    if a.cmd == "lifecycle":
        rep = jobs.run_lifecycle(d, now)
        doc = rep.pop("doc")
        rep["top"] = [{k: c[k] for k in ("key", "stage", "speed", "creators_7d", "growth")}
                      for c in doc["trends"][:10]]
        _out(rep, as_json, f"{rep['trends']} trends {rep['by_stage']}; "
                           f"{rep['signals_only']} signal-only keys"
                           + (f" -> {rep['file']}" if rep["file"] else ""))
        return EXIT_OK if rep["observations"] else EXIT_NOTHING
    if a.cmd == "synth":
        rep = jobs.run_synth(d, now, niches=_niches(a.niche), presenter=a.presenter,
                             k=max(0, a.k), invent=max(0, a.invent))
        rep.pop("new", None)
        if not rep["recipes"]:
            _out(rep, as_json, f"synth: nothing to do ({rep.get('reason', 'no recipe')})")
            return EXIT_NOTHING
        _out(rep, as_json, "\n".join(
            [f"synth: {rep['recipes']} recipes for {', '.join(rep['niches'])} "
             f"({', '.join(rep['lanes'])}) {rep['by_operator']} -> {rep['file']}"] +
            [f"  {t['recipe_id']} {t['score']:.3f} [{t['niche']}/{t['operator']}] {t['title']}"
             for t in rep["top"]]))
        return EXIT_OK
    if a.cmd == "digest":
        rep = jobs.run_digest(d, now, a.date)
        _out(rep, as_json, rep["file"])
        return EXIT_OK
    if a.cmd == "recipes":
        return _recipes(a, d, as_json, store)
    if a.cmd == "steer":
        from vsp.trends import steer
        st = steer.for_run(a.prompt, presenter=a.presenter, fmt=a.format, dataset_dir=d,
                           recipe_id=a.recipe, today=now.date())
        if st is None:
            _out({"steer": None}, as_json, "no fitting recipe (steer = None)")
            return EXIT_NOTHING
        md = steer.brief_md(st)
        if as_json:
            _out({"steer": st, "brief_md": md}, True, None)
        else:
            print(json.dumps(st, indent=1, sort_keys=True, ensure_ascii=False))
            print()
            print(md)
        return EXIT_OK
    if a.cmd == "watchlist-suggest":
        rep = jobs.watchlist_suggest(d, now, min_x=a.min_x, cap=a.cap, config_path=a.config,
                                     apply=a.apply)
        lines = [f"watchlist {rep['watchlist_size']}/{rep['cap']} handles "
                 f"({rep['config']}); {len(rep['suggestions'])} suggestion(s)"]
        lines += [f"  @{s['handle']} {s['tier']} {s['outliers']} outlier(s), best "
                  f"{s['best_x']:g}x, niche {s['niche']}" for s in rep["suggestions"][:30]]
        if a.apply:
            lines.append(f"  added: {', '.join(rep['added']) or 'none'}")
        if rep.get("error"):
            lines.append(f"  error: {rep['error']}")
        _out(rep, as_json, "\n".join(lines))
        if rep.get("error"):
            return EXIT_USAGE
        return EXIT_OK if rep["suggestions"] else EXIT_NOTHING
    if a.cmd == "purge":
        if not (a.creator or a.source or a.older_than is not None or a.expired):
            return _usage("purge needs --creator, --source, --older-than or --expired")
        rep = jobs.run_purge(d, now, creator=a.creator, platform=a.platform, source=a.source,
                             older_than=a.older_than, expired=a.expired, dry_run=a.dry_run)
        total = sum(rep["removed"].values())
        lines = [f"{'would remove' if a.dry_run else 'removed'} {rep['removed']} "
                 f"{rep['by_reason']}"]
        for k in ("files_rewritten", "files_deleted", "digests_scrubbed", "regenerated"):
            if rep[k]:
                lines.append(f"  {k}: {', '.join(rep[k])}")
        if rep.get("git_history_note"):
            lines.append(f"  NOTE: {rep['git_history_note']}")
        _out(rep, as_json, "\n".join(lines))
        return EXIT_OK if total else EXIT_NOTHING
    if a.cmd == "status":
        rep = jobs.status(d, now)
        _out(rep, as_json, json.dumps(rep, indent=1, sort_keys=True, default=str))
        return EXIT_OK
    return _usage(f"unknown command {a.cmd}")


def _recipes(a, d, as_json, store):
    store.require(d)
    recipes = store.load_recipes(d)
    if a.id:
        rec = next((r for r in recipes if r["recipe_id"] == a.id), None)
        if rec is None:
            _err(f"no recipe {a.id}")
            return EXIT_NOTHING
        _out(rec, True, None)
        return EXIT_OK
    pool = [r for r in recipes if not r.get("used") and (not a.niche or r["niche"] == a.niche)]
    if not pool:
        _out({"recipes": []}, as_json, "no recipes (run synth)")
        return EXIT_NOTHING
    latest = {}
    for r in pool:
        latest[r["niche"]] = max(latest.get(r["niche"], ""), r["date"])
    pool = [r for r in pool if r["date"] == latest[r["niche"]]]
    pool.sort(key=lambda r: (r["niche"], -r["score"], r["recipe_id"]))
    out, per = [], {}
    for r in pool:
        per[r["niche"]] = per.get(r["niche"], 0) + 1
        if per[r["niche"]] <= a.top:
            out.append(r)
    _out({"recipes": out}, as_json, "\n".join(
        f"{r['recipe_id']} {r['score']:.3f} [{r['niche']}/{r['operator']}/"
        f"{'+'.join(r['lanes'])}] {r['title']}" for r in out))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
