"""python3 -m vsp.ingest <command> — see `python3 -m vsp.ingest --help`.

Exit codes: 0 ok · 1 failure (selfcheck/doctor problems, unexpected error)
· 2 not configured / config, token or permission problem (a human must act)
· 3 stopped early by rate limits (partial data kept; resume next run).
"""
import argparse
import json
import os
import sys

from vsp import config

if config.REPO not in sys.path:          # research_bridge / the maker live at the root
    sys.path.insert(0, config.REPO)

HELP = """commands:
  init-db                      create / migrate the research DB (VSP_VIRAL_DB)
  doctor [--offline]           env, token, permissions, budget, schema, pack age + setup steps
  hashtags [--niche N] [--recent]   Job A: top (+ recent) reels per configured hashtag
  watchlist [--niche N] [--force]   Job A: Business Discovery on benchmark handles
  own [--since TS]             Job B: register your own Reels (#vsp-<sha8> caption tag)
  insights [--days 3|--day D]  Job B: daily account insights -> account_metrics
  import FILE --source S [--niche N] [--own]   JSON/CSV export (import:<name> | vendor:<name>)
  classify [--reclassify]      hook_category / hook family / pattern + aggregates
  transcribe [--own-renders]   optional ASR of your own renders (media_url items: during fetch)
  refresh-pack                 classify pending rows, then research_bridge.refresh()
  purge [--vendor] [--source S] [--media-id ID]  retention + deletion requests
  status                       what is in the DB
  selfcheck                    hermetic self-check (no network)

env: VSP_IG_ACCESS_TOKEN, VSP_IG_USER_ID, VSP_IG_GRAPH_VERSION (default v26.0),
     VSP_IG_APP_SECRET / VSP_IG_APP_ID (optional), VSP_VIRAL_DB, VSP_INGEST_CONFIG,
     VSP_RESEARCH_PACK, VSP_ASR_API_KEY (-> VSP_LLM_API_KEY), VSP_EXCLUDE_VENDOR
config: config/ingest.json (template config/ingest.example.json)
docs: docs/ws-data-notes.md"""


def _parser():
    ap = argparse.ArgumentParser(prog="python3 -m vsp.ingest",
                                 description="Compliant Instagram Reels ingestion "
                                             "for the research DB.",
                                 epilog=HELP,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--db", help="research DB path (sets VSP_VIRAL_DB)")
    ap.add_argument("--config", help="ingest config path (sets VSP_INGEST_CONFIG)")
    sub = ap.add_subparsers(dest="cmd", metavar="command")
    sub.add_parser("init-db")
    p = sub.add_parser("doctor")
    p.add_argument("--offline", action="store_true", help="skip Graph API calls")
    p = sub.add_parser("hashtags")
    p.add_argument("--niche")
    p.add_argument("--recent", action="store_true",
                   help="also recent_media (24 h window; run every 8 h)")
    p.add_argument("--no-classify", action="store_true")
    p = sub.add_parser("watchlist")
    p.add_argument("--niche")
    p.add_argument("--force", action="store_true",
                   help="ignore the once-per-handle-per-day spacing")
    p.add_argument("--no-classify", action="store_true")
    p = sub.add_parser("own")
    p.add_argument("--since", help="UTC timestamp / date (default: last seen - 2 days)")
    p = sub.add_parser("insights")
    p.add_argument("--days", type=int, default=3)
    p.add_argument("--day", help="one UTC day YYYY-MM-DD")
    p = sub.add_parser("import")
    p.add_argument("file")
    p.add_argument("--source", required=True, help="import:<name> or vendor:<name>")
    p.add_argument("--niche", help="maker niche for rows without one")
    p.add_argument("--own", action="store_true",
                   help="your own export: is_own=1 + metrics snapshots")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-classify", action="store_true")
    p = sub.add_parser("classify")
    p.add_argument("--reclassify", action="store_true")
    p.add_argument("--limit", type=int)
    p.add_argument("--no-llm", action="store_true")
    p = sub.add_parser("transcribe")
    p.add_argument("--own-renders", action="store_true",
                   help="renders next to linked manifests (default)")
    p.add_argument("--file", help="a local render of one of your reels")
    p.add_argument("--media-id", help="with --file: the reel's media id")
    p = sub.add_parser("refresh-pack")
    p.add_argument("--no-classify", action="store_true")
    p = sub.add_parser("purge")
    p.add_argument("--vendor", action="store_true", help="delete every vendor:* row")
    p.add_argument("--source", help="delete every row with this source")
    p.add_argument("--media-id", action="append", default=[],
                   help="delete this media (repeatable; deletion requests)")
    p.add_argument("--dry-run", action="store_true")
    sub.add_parser("status")
    sub.add_parser("selfcheck")
    return ap


def _err(msg):
    print(msg, file=sys.stderr)


def _print(obj, as_json, text=None):
    if as_json:
        print(json.dumps(obj, indent=1, default=str, ensure_ascii=False))
    else:
        print(text if text is not None else _summary(obj))


def _summary(rep):
    if not isinstance(rep, dict):
        return str(rep)
    keys = ("job", "inserted", "updated", "adopted", "api_calls", "retries", "slept_s")
    head = " ".join(f"{k}={rep[k]}" for k in keys if k in rep)
    out = [head] if head else []
    for q in rep.get("queries") or []:
        out.append(f"  {q.get('query')} {q.get('edge', '')}: {q.get('items', 0)} items, "
                   f"{q.get('kept', 0)} kept")
    if rep.get("skipped"):
        out.append("  skipped: " + ", ".join(f"{k} x{v}" for k, v in rep["skipped"].items()))
    b = rep.get("budget")
    if b:
        out.append(f"  hashtag budget: {b.get('used_after', b.get('used_before'))}/"
                   f"{b.get('limit')} used, {b.get('remaining', '?')} left")
    for k in ("classify", "transcribe"):
        if isinstance(rep.get(k), dict):
            sub = rep[k]
            if k == "classify":
                out.append(f"  classify: {sub.get('rules', 0)} rules, {sub.get('llm', 0)} "
                           f"llm, {sub.get('unknown', 0)} unknown, aggregates "
                           f"{sub.get('aggregates')}")
            else:
                out.append(f"  transcribe: {sub.get('transcribed', 0)} transcribed, "
                           f"skipped {sub.get('skipped')}")
    for w in rep.get("warnings") or []:
        out.append(f"  warning: {w}")
    for e in rep.get("errors") or []:
        out.append(f"  error: {e}")
    if rep.get("stopped"):
        out.append(f"  STOPPED: {rep['stopped']}")
    return "\n".join(out)


def _code(rep):
    st = (rep or {}).get("stopped") or ""
    if st.startswith("rate_limited"):
        return 3
    if st:
        return 2
    return 0


def _not_configured(e, as_json):
    msg = str(e)
    if as_json:
        _print({"error": "not_configured", "missing": getattr(e, "missing", []),
                "message": msg}, True)
    else:
        _err(msg)
    return 2


def main(argv=None):
    ap = _parser()
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help()
        return 2
    if a.db:
        os.environ["VSP_VIRAL_DB"] = os.path.abspath(a.db)
    if a.config:
        os.environ["VSP_INGEST_CONFIG"] = os.path.abspath(a.config)
    if a.cmd == "selfcheck":
        from vsp.ingest import selfcheck
        ok, lines = selfcheck()
        if a.json:
            _print({"ok": ok, "lines": lines}, True)
        else:
            print("\n".join(lines))
            print("vsp.ingest selfcheck: " + ("OK" if ok else "FAILED"))
        return 0 if ok else 1
    from vsp.ingest import db as idb
    from vsp.ingest import jobs
    from vsp.ingest import settings as S
    from vsp.ingest.graph import GraphError, NotConfigured
    if a.cmd == "init-db":
        p, created, actions = idb.init_db()
        _print({"db": p, "created": created, "actions": actions}, a.json,
               f"{'created' if created else 'migrated'} {p}: " +
               (", ".join(actions) if actions else "already current"))
        return 0
    if a.cmd == "doctor":
        from vsp.ingest import doctor
        res = doctor.run(offline=a.offline)
        _print(res, a.json, doctor.render(res))
        return 0 if res["ok"] else 1
    needs_cfg = a.cmd in ("hashtags", "watchlist")
    try:
        cfg = S.load(required=needs_cfg)
    except S.ConfigError as e:
        _err("config error:\n  " + "\n  ".join(e.problems))
        return 2
    try:
        con = idb.connect()
    except idb.DBMissing as e:
        _err(str(e))
        return 2
    except idb.MigrationError as e:
        _err(f"migration refused: {e}")
        return 2
    log = (lambda m: None) if a.json else (lambda m: _err(m))
    try:
        if a.cmd in ("hashtags", "watchlist", "own", "insights"):
            try:
                client = jobs.make_client(con, cfg, log=log)
            except NotConfigured as e:
                return _not_configured(e, a.json)
            if a.cmd == "hashtags":
                rep = jobs.run_hashtags(con, client, cfg, niche=a.niche, recent=a.recent,
                                        classify_after=not a.no_classify, log=log)
            elif a.cmd == "watchlist":
                rep = jobs.run_watchlist(con, client, cfg, niche=a.niche, force=a.force,
                                         classify_after=not a.no_classify, log=log)
            elif a.cmd == "own":
                rep = jobs.run_own(con, client, cfg, since=a.since, log=log)
            else:
                rep = jobs.run_account_insights(con, client, cfg, days=a.days, day=a.day)
            _print(rep, a.json)
            return _code(rep)
        if a.cmd == "import":
            from vsp.ingest.importers import ImportError_
            try:
                rep = jobs.run_import(con, a.file, a.source, niche=a.niche, cfg=cfg,
                                      own=a.own, dry_run=a.dry_run,
                                      classify_after=not a.no_classify, warn=_err)
            except ImportError_ as e:
                _err(f"import refused: {e}")
                return 2
            _print(rep, a.json, _summary(dict(rep, job="import",
                                              warnings=[]))
                   + f"\n  rows read {rep['rows_read']} ({rep['format']}), metrics "
                     f"snapshots {rep['metrics_snapshots']}")
            return 0 if not rep["errors"] else 1
        if a.cmd == "classify":
            rep = jobs.run_classify(con, cfg, reclassify=a.reclassify, limit=a.limit,
                                    llm="off" if a.no_llm else "auto")
            _print(rep, a.json, f"classified {rep['candidates']} reels: {rep['rules']} "
                   f"rules, {rep['llm']} llm ({rep['llm_calls']} calls), "
                   f"{rep['unknown']} unknown; families from {rep['families_source']}; "
                   f"aggregates {rep['aggregates']}")
            return 0
        if a.cmd == "transcribe":
            cands = []
            if a.file:
                if not a.media_id:
                    _err("--file needs --media-id (the reel's Instagram media id)")
                    return 2
                cands.append((a.media_id, os.path.abspath(a.file), "own_render"))
            rep = jobs.run_transcribe(con, cfg, candidates=cands,
                                      own_renders=a.own_renders or not a.file, log=log)
            _print(rep, a.json, f"transcribed {rep['transcribed']} of "
                   f"{rep['candidates']} (no speech {rep['no_speech']}); skipped "
                   f"{rep['skipped']}; errors {rep['errors']}")
            return 0 if not rep["errors"] else 1
        if a.cmd == "refresh-pack":
            cl = None if a.no_classify else jobs.run_classify(con, cfg)
            if cl is None:
                from vsp.ingest.classify import rebuild_aggregates
                rebuild_aggregates(con, cfg)
                con.commit()
            con.close()
            con = None
            import research_bridge
            code = research_bridge.refresh()
            if a.json:
                _print({"classify": cl, "refresh_exit": code,
                        "pack": config.research_pack_path()}, True)
            return 0 if code == 0 else 1
        if a.cmd == "purge":
            rep = jobs.purge(con, cfg, vendor=a.vendor, media_ids=a.media_id,
                             source=a.source, dry_run=a.dry_run)
            _print(rep, a.json, f"{'would delete' if a.dry_run else 'deleted'} "
                   f"{rep['reels']} reels ({rep['own']} own; {rep['by_source']}), "
                   f"{rep['metrics']} metric snapshots, {rep['posts']} posts")
            return 0
        if a.cmd == "status":
            rep = jobs.status(con, cfg)
            rep["db"] = con.db_path
            _print(rep, a.json, json.dumps(rep, indent=1, default=str))
            return 0
    except GraphError as e:
        _err(f"Graph API error: {e}")
        return 2
    finally:
        if con is not None:
            con.close()
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
