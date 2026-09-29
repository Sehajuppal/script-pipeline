"""Hermetic self-checks behind vsp.ingest.selfcheck() and
vsp.feedback.selfcheck() -> (ok: bool, lines: list[str]).

Everything runs inside vsp.fixtures.hermetic_ingest_env(): a temp research
DB (VSP_VIRAL_DB), temp learned dir (VSP_LEARNED_DIR), temp research pack
(VSP_RESEARCH_PACK), temp outputs / config / dossiers, credentials unset,
urllib.request.urlopen disabled, the caller's environment restored after.
Graph API and ASR responses are the canned JSON in tests/fixtures/ig/,
served by vsp.fixtures.FixtureTransport; ffmpeg is a fake runner that writes
a WAV. Time is pinned (NOW) so the checks never depend on the date.

run()           ingest: migration, pagination, budget, usage backoff +
                retries + rate-limit stop, normalization, upsert
                idempotency + legacy adoption, importers (vendor warning,
                refusal, dedupe, CSV, own export), classification (maker
                HOOKS families, aggregates idempotent + VACUUM-safe, LLM
                path), transcription (no-op without a key, multipart call,
                audio deleted), research pack refresh (views->likes ranking,
                top_reels, keep-last-good), purge, doctor, CLI, and the
                legacy make_shotlist.niche_references on the migrated DB
run_feedback()  feedback: link (manifest script_summary, script.json
                fallback, --auto via #vsp-<sha8>, manual --trial), pull
                (checkpoints, idempotent, metric drop + retry, vanished
                media), labels -> priors (learned/README.md schema), report,
                status, legacy reader
"""
import contextlib
import hashlib
import io
import json
import os
import shutil
import sqlite3
import traceback
from datetime import timedelta

NOW = "2026-09-28 12:00:00"


class _Checks:
    def __init__(self, title):
        self.title, self.lines, self.ok = title, [], True

    def check(self, name, cond, detail=""):
        cond = bool(cond)
        self.lines.append(f"{'PASS' if cond else 'FAIL'} {name}"
                          + (f" — {detail}" if detail not in ("", None) else ""))
        self.ok = self.ok and cond
        return cond

    def step(self, name, fn, *a):
        try:
            return fn(*a)
        except Exception as e:  # noqa: BLE001 — a crash is a failure, never fatal
            tb = traceback.format_exc().strip().splitlines()[-4:]
            self.check(name, False, f"crashed: {type(e).__name__}: {e} | " +
                       " | ".join(t.strip() for t in tb))
            return None

    def result(self):
        n_fail = sum(1 for x in self.lines if x.startswith("FAIL"))
        self.lines.append(f"{self.title}: {len(self.lines) - n_fail} passed, "
                          f"{n_fail} failed")
        return self.ok, list(self.lines)


def _quiet():
    return contextlib.ExitStack()


@contextlib.contextmanager
def _silenced():
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        yield out, err


def _sha(path):
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


INGEST_CFG = {
    "niches": {
        "beauty": {"hashtags": ["skincareroutine", "makeuphacks"],
                   "handles": ["fixture_glowlab", "fixture_personal"]},
        "fitness": {"hashtags": ["homeworkout"], "handles": []},
    },
    "hashtag_niche_map": {"skincare": "beauty", "gym": "fitness"},
    "budget": {"max_active_hashtags": 3},
    "transcribe": {"enabled": False},
}
ENV = {"VSP_IG_ACCESS_TOKEN": "FIXTURE-TOKEN-NOT-REAL", "VSP_IG_USER_ID": "17841400000000001",
       "VSP_IG_APP_SECRET": "fixture-app-secret", "VSP_IG_GRAPH_VERSION": "v26.0"}


def _fake_ffmpeg(calls):
    import wave

    class _R:
        returncode, stderr = 0, b""

    def runner(cmd, timeout):
        calls.append(list(cmd))
        with wave.open(cmd[-1], "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(b"\x00\x00" * 16000 * 3)
        return _R()
    return runner


def _write_cfg(path, cfg):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f)


# ===================================================================== ingest
def run():
    from vsp.fixtures import hermetic_ingest_env
    C = _Checks("vsp.ingest selfcheck")
    try:
        with hermetic_ingest_env() as ctx:
            _ingest_checks(C, ctx)
    except Exception as e:  # noqa: BLE001
        C.check("selfcheck harness", False, f"{type(e).__name__}: {e} | "
                + traceback.format_exc().strip().splitlines()[-1])
    return C.result()


def _ingest_checks(C, ctx):
    from vsp import config
    from vsp.fixtures import FixtureTransport, build_fixture_db, graph_routes
    from vsp.ingest import db as idb
    from vsp.ingest import jobs
    from vsp.ingest import settings as S
    from vsp.ingest.util import parse_ts
    now = parse_ts(NOW)
    clock = {"now": now}
    repo_pack = os.path.join(config.REPO, "research_pack.json")
    repo_pack_sha = _sha(repo_pack)
    C.check("hermetic env", config.viral_db_path() == ctx.db and
            config.learned_dir() == ctx.learned and
            config.research_pack_path() == ctx.pack and
            not os.environ.get("VSP_IG_ACCESS_TOKEN"), ctx.tmp)
    _write_cfg(ctx.config, INGEST_CFG)
    cfg = S.load()
    C.check("config loads + validates", cfg.get("_path") == ctx.config)
    bad = S.validate(S._merge(S.DEFAULTS, {"niches": {"beauty": {"hashtags": [
        "a1", "b2", "c3", "d4"]}, "nope": {}}}))
    C.check("config validation names problems", any("max 3 per niche" in b for b in bad)
            and any("unknown niche" in b for b in bad), "; ".join(bad)[:120])

    # ---------------------------------------------------------- migration
    build_fixture_db(ctx.db)
    legacy_cols = idb.table_columns(sqlite3.connect(ctx.db), "reels")
    con = idb.connect(ctx.db)
    acts = list(con.migration_actions)
    C.check("migration adds the §9 columns + tables", {"reels +media_id",
            "reels +source", "reels +views", "created table reel_metrics",
            "created table posts", "created table hashtag_budget",
            "created index reels_media"} <= set(acts) and len(legacy_cols) == 9,
            f"{len(acts)} actions")
    C.check("migration is idempotent", idb.migrate(con) == [] and
            idb.schema_version(con) == idb.SCHEMA_VERSION)
    C.check("legacy rows keep media_id NULL (never duplicates)", con.execute(
        "SELECT COUNT(*) FROM reels WHERE media_id IS NULL").fetchone()[0] == 48)
    C.step("legacy reader on the migrated DB", _check_legacy_reader, C, ctx)
    # a research-agent row for a reel the API will return (adoption test)
    con.execute("INSERT INTO reels(url, username, niche, like_count, notes, hook_text, "
                "pattern_id, analyzed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("https://www.instagram.com/reel/FIXTUREht06/", "agent_seen", "beauty",
                 11000, "research agent row", "Retinol purging: the timeline nobody shares",
                 2, "2026-09-26 08:00:00"))
    con.commit()

    # ----------------------------------------------- hashtags: pages + budget
    tr = FixtureTransport(graph_routes())
    slept = []
    client = jobs.make_client(con, cfg, env=ENV, transport=tr,
                              clock=lambda: clock["now"], sleep=slept.append)
    rep = jobs.run_hashtags(con, client, cfg, now=now)
    calls = [(c["path"], c["params"]) for c in tr.calls]
    top101 = [p.get("after") for path, p in calls if path == "17843000000000101/top_media"]
    C.check("pagination: 2 pages followed, page 3 never fetched (top_pages=2)",
            top101 == [None, "QVFIUk1"], str(top101))
    C.check("pagination: duplicate id across pages kept once", con.execute(
        "SELECT COUNT(*) FROM reels WHERE media_id='17900000000000101'").fetchone()[0] == 1)
    C.check("budget: recently_searched_hashtags checked before opening slots",
            calls and calls[0][0].endswith("/recently_searched_hashtags"))
    refused = [r["tag"] for r in (rep.get("budget") or {}).get("refused", [])]
    hw_calls = [1 for path, p in calls if p.get("q") == "homeworkout" or
                path.startswith("17843000000000103")]
    C.check("budget: over-limit hashtag refused BEFORE any call", refused == ["homeworkout"]
            and not hw_calls, f"refused {refused}, homeworkout calls {len(hw_calls)}")
    C.check("budget: remote-only hashtag counted as a placeholder slot",
            rep.get("remote_placeholders") == 1 and rep["budget"]["used_after"] == 3)
    C.check("usage header >= 80% -> backoff sleep", any("usage 85" in w for _, w in
                                                         client.slept) and slept)
    C.check("transient 5xx retried with jittered backoff", rep.get("retries") == 1 and
            any("retry 1: HTTP 500" in w for _, w in client.slept))
    C.check("every call pinned to v26.0 with appsecret_proof, token never logged",
            {c["version"] for c in tr.calls} == {"v26.0"} and
            all("appsecret_proof" in c["params"] for c in tr.calls) and
            "FIXTURE-TOKEN-NOT-REAL" not in json.dumps(rep, default=str))
    C.check("hashtag job report", rep["inserted"] == 4 and rep["adopted"] == 1 and
            rep["skipped"].get("not a reel") == 3 and rep["skipped"].get("too old") == 1
            and rep["stopped"] is None,
            f"ins {rep['inserted']} adopted {rep['adopted']} skipped {rep['skipped']}")

    # -------------------------------------------------------- normalization
    r101 = con.execute("SELECT * FROM reels WHERE media_id='17900000000000101'").fetchone()
    r103 = con.execute("SELECT * FROM reels WHERE media_id='17900000000000103'").fetchone()
    C.check("normalize: §9 mapping (url, niche, username NULL, analyzed_at format)",
            r101 and r101["url"] == "https://www.instagram.com/reel/FIXTUREht01/" and
            r101["niche"] == "beauty" and r101["username"] is None and
            r101["source"] == "ig_hashtag_top" and r101["source_query"] == "#skincareroutine"
            and r101["analyzed_at"] == NOW and r101["purge_after"] == "2026-10-28 12:00:00"
            and r101["posted_at"] == "2026-09-27 09:00:00")
    C.check("normalize: caption hook (emoji/mention/URL/hashtags stripped, hidden likes)",
            r101["hook_text"] == "POV: your serum finally stopped pilling" and
            r101["hook_source"] == "caption" and r103 is not None and
            r103["hook_text"] == "Stop rubbing your face dry after cleansing" and
            r103["like_count"] is None and "likes hidden" in (r103["notes"] or ""),
            f"{r103['hook_text'] if r103 else None!r}")
    blob = json.dumps([dict(x) for x in con.execute("SELECT * FROM reels")], default=str)
    C.check("normalize: media_url never persisted", "cdninstagram" not in blob and
            "_nc_sig" not in blob and "media_url" not in idb.table_columns(con, "reels"))
    adopted = con.execute("SELECT * FROM reels WHERE url LIKE '%FIXTUREht06%'").fetchall()
    C.check("upsert: research-agent row adopted, curated hook kept (no duplicate)",
            len(adopted) == 1 and adopted[0]["media_id"] == "17900000000000106" and
            adopted[0]["hook_source"] == "curated" and adopted[0]["classified_by"] is None
            and adopted[0]["hook_text"].startswith("Retinol purging"))

    # ------------------------------------------------- upsert idempotency
    n_before = con.execute("SELECT COUNT(*) FROM reels").fetchone()[0]
    clock["now"] = now + timedelta(hours=1)
    tr.calls.clear()
    rep2 = jobs.run_hashtags(con, client, cfg, now=now + timedelta(hours=1))
    n_after = con.execute("SELECT COUNT(*) FROM reels").fetchone()[0]
    C.check("upsert idempotent: re-run updates, inserts nothing", rep2["inserted"] == 0
            and rep2["updated"] == 5 and n_before == n_after,
            f"ins {rep2['inserted']} upd {rep2['updated']} rows {n_before}->{n_after}")
    C.check("budget: repeats inside the window are free (ids cached, no search call)",
            not [c for c in tr.calls if c["path"] == "ig_hashtag_search"] and
            not [c for c in tr.calls if c["path"].endswith("recently_searched_hashtags")])
    C.step("budget unit checks", _check_budget_unit, C, con, now)
    clock["now"] = now

    # --------------------------------------------------------- watchlist
    rep3 = jobs.run_watchlist(con, client, cfg, now=now)
    r401 = con.execute("SELECT * FROM reels WHERE media_id='17900000000000401'").fetchone()
    C.check("business discovery: unsupported field dropped + retried, views kept",
            r401 is not None and r401["views"] == 1250000 and r401["username"] ==
            "fixture_glowlab" and "outlier 26.0x" in (r401["notes"] or "") and
            "media_product_type" not in client._bd_fields)
    C.check("business discovery: personal/unknown handle is a per-handle error",
            rep3["stopped"] is None and any("fixture_personal" in e and "Business/Creator"
                                            in e for e in rep3["errors"]))
    rep4 = jobs.run_watchlist(con, client, cfg, now=now + timedelta(hours=3))
    C.check("watchlist: once per handle per day", rep4["skipped"].get(
        "fetched < 20 h ago") == 2 and rep4.get("api_calls") == 0, str(rep4["skipped"]))
    C.step("rate-limit stop", _check_rate_limit_stop, C, con, cfg, now)

    # --------------------------------------------------------- own + insights
    rep5 = jobs.run_own(con, client, cfg, now=now)
    C.check("own media: 2 pages, REELS only, #vsp- tags -> script_slug",
            rep5["inserted"] == 11 and rep5["skipped"].get("not a reel") == 1 and
            con.execute("SELECT script_slug FROM reels WHERE media_id='17900000000001001'"
                        ).fetchone()[0] == "vsp-11111111" and
            con.execute("SELECT COUNT(*) FROM reels WHERE is_own=1 AND niche IS NOT NULL"
                        ).fetchone()[0] == 0, f"inserted {rep5['inserted']}")
    rep6 = jobs.run_account_insights(con, client, cfg, now=now)
    C.check("account insights -> account_metrics (follow_type breakdown)",
            rep6["values"] == 18 and con.execute(
                "SELECT value FROM account_metrics WHERE metric='follows_and_unfollows' "
                "AND breakdown='follower' LIMIT 1").fetchone()[0] == 41)

    # ---------------------------------------------------------- importers
    C.step("importers", _check_importers, C, ctx, con, cfg)
    # ---------------------------------------------------------- classify
    C.step("classification", _check_classify, C, con, cfg)
    # --------------------------------------------------------- transcribe
    C.step("transcribe", _check_transcribe, C, con, cfg)
    # -------------------------------------------------------- pack refresh
    C.step("pack refresh", _check_pack, C, ctx, con, now)
    C.check("repo research_pack.json untouched", _sha(repo_pack) == repo_pack_sha)
    # ------------------------------------------------------------- purge
    C.step("purge", _check_purge, C, con, cfg, now)
    # -------------------------------------------------------- doctor + CLI
    C.step("doctor", _check_doctor, C, ctx)
    C.step("cli", _check_cli, C, ctx)
    C.step("legacy reader after ingest", _check_legacy_reader, C, ctx, True)
    con.close()


def _check_legacy_reader(C, ctx, after=False):
    import make_shotlist
    lines = make_shotlist.niche_references("beauty", db_path=ctx.db)
    fb = make_shotlist.niche_references("no-such-niche", db_path=ctx.db)
    C.check("legacy make_shotlist.niche_references on the migrated DB"
            + (" (after ingest)" if after else ""),
            len(lines) == 3 and all(ln.startswith("- https://www.instagram.com/") and
                                    "likes" in ln for ln in lines) and len(fb) == 3,
            lines[0][:70] if lines else "no lines")


def _check_budget_unit(C, con, now):
    from vsp.fixtures import FixtureTransport, graph_routes
    from vsp.ingest.graph import BudgetExceeded, GraphClient, HashtagBudget
    t = {"now": now}
    b = HashtagBudget(con, limit=5, clock=lambda: t["now"])
    con.execute("DELETE FROM hashtag_budget")
    for tag in ("aa1", "bb2", "cc3", "dd4", "ee5"):
        b.reserve(tag)
    tr = FixtureTransport(graph_routes())
    cl = GraphClient("FIXTURE", "17841400000000001", transport=tr, budget=b,
                     sleep=lambda s: None)
    try:
        cl.top_media("ff6")
        refused = False
    except BudgetExceeded:
        refused = True
    C.check("budget unit: 6th unique tag refused with no HTTP call",
            refused and not tr.calls)
    C.check("budget unit: active tag is free", b.reserve("aa1") is False and b.used() == 5)
    t["now"] = now + timedelta(days=7, minutes=1)
    C.check("budget unit: rolling 7-day window frees slots", b.used() == 0 and
            b.reserve("ff6") is True)
    try:
        GraphClient("FIXTURE", "17841400000000001", transport=tr).top_media("aa1")
        nobudget = False
    except RuntimeError:
        nobudget = True
    C.check("budget unit: a client without a budget refuses hashtag calls",
            nobudget and not tr.calls)
    C.check("budget unit: never above Instagram's 30", HashtagBudget(con, limit=99).limit
            == 30)
    con.execute("DELETE FROM hashtag_budget WHERE tag IN ('aa1','bb2','cc3','dd4','ee5',"
                "'ff6')")
    con.commit()


def _check_rate_limit_stop(C, con, cfg, now):
    from vsp.fixtures import FixtureTransport, graph_routes, load_ig_fixture
    from vsp.ingest import jobs
    stop = load_ig_fixture("errors.json")["usage_stop_headers"]
    extra = [{"path": "17841400000000001",
              "params": {"fields": r"^business_discovery\.username\(fixture_glowlab\)"
                                   r"(?!.*media_product_type)"},
              "response": {"fixture": "business_discovery.json",
                           "key": "fixture_glowlab_p1", "headers": stop}}]
    tr = FixtureTransport(graph_routes(extra=extra))
    cl = jobs.make_client(con, cfg, env=ENV, transport=tr, sleep=lambda s: None)
    cl._bd_fields = [f for f in cl._bd_fields if f != "media_product_type"]
    rep = jobs.run_watchlist(con, cl, cfg, force=True, now=now)
    C.check("usage >= 95% -> job stops cleanly (resume next run), data kept",
            (rep["stopped"] or "").startswith("rate_limited") and len(tr.calls) == 1
            and rep["updated"] + rep["inserted"] >= 1, str(rep["stopped"])[:80])


def _check_importers(C, ctx, con, cfg):
    from vsp.fixtures import IG_FIXTURES_DIR
    from vsp.ingest import importers as I
    from vsp.ingest import jobs
    vend = os.path.join(IG_FIXTURES_DIR, "import_vendor_apify.json")
    warned = []
    rep = jobs.run_import(con, vend, "vendor:apify", cfg=cfg, now=NOW, warn=warned.append,
                          classify_after=False)
    C.check("importer: vendor:* import warns about Instagram's Terms (research doc §7)",
            warned and "Instagram's Terms" in warned[0] and rep["warnings"])
    C.check("importer: validated + deduped (dup, carousel, non-Instagram URL skipped)",
            rep["inserted"] == 2 and rep["skipped"].get("duplicate in file") == 1 and
            rep["skipped"].get("not an instagram.com URL") == 1 and
            any(k.startswith("not a reel") for k in rep["skipped"]), str(rep["skipped"]))
    rows = {r["media_id"]: r for r in con.execute(
        "SELECT * FROM reels WHERE source='vendor:apify'")}
    r1 = rows.get("3470000000000000501_900")
    C.check("importer: niche from caption hashtags, views kept, media URLs dropped",
            r1 is not None and r1["niche"] == "beauty" and r1["views"] == 380000 and
            rows.get("sc:FIXTUREvn03") is not None and
            rows["sc:FIXTUREvn03"]["niche"] == "fitness" and
            rows["sc:FIXTUREvn03"]["like_count"] == 1200 and
            "cdninstagram" not in json.dumps([dict(r) for r in rows.values()]))
    rep2 = jobs.run_import(con, vend, "vendor:apify", cfg=cfg, now=NOW, classify_after=False)
    C.check("importer: re-import is idempotent", rep2["inserted"] == 0 and
            rep2["updated"] == 2)
    try:
        I.import_file(con, vend, "import:apify")
        refused = False
    except I.ImportError_:
        refused = True
    C.check("importer: known scraper refused under import:*", refused)
    try:
        I.import_file(con, vend, "scraped")
        bad_tag = False
    except I.ImportError_:
        bad_tag = True
    C.check("importer: source must be import:<name> | vendor:<name>", bad_tag)
    sp = jobs.run_import(con, os.path.join(IG_FIXTURES_DIR, "import_sprout.csv"),
                         "import:sprout", niche="beauty", cfg=cfg, now=NOW,
                         classify_after=False)
    s1 = con.execute("SELECT * FROM reels WHERE url LIKE '%FIXTUREsp01%'").fetchone()
    C.check("importer: official-API vendor CSV (';' delimited, --niche)",
            sp["inserted"] == 2 and not sp["warnings"] and sp["format"] == "csv" and
            s1 is not None and s1["views"] == 210000 and s1["like_count"] == 9800 and
            s1["hook_text"] == "POV: you finally found a sunscreen with no white cast"
            and s1["source"] == "import:sprout" and s1["niche"] == "beauty",
            dict(s1) if s1 else None)
    own = jobs.run_import(con, os.path.join(IG_FIXTURES_DIR, "import_business_suite.csv"),
                          "import:business-suite", cfg=cfg, own=True, now=NOW)
    snap = con.execute("SELECT * FROM reel_metrics WHERE media_id='17900000000001008'"
                       ).fetchone()
    C.check("importer: own Business Suite export -> own row + metrics snapshot",
            own["updated"] == 1 and own["metrics_snapshots"] == 1 and snap is not None
            and snap["views"] == 1700 and snap["reach"] == 1500 and
            snap["source"] == "import:business-suite", str(own["skipped"]))
    con.execute("DELETE FROM reel_metrics WHERE media_id='17900000000001008'")
    con.commit()


def _check_classify(C, con, cfg):
    import viral_script_maker as vsm
    from vsp.ingest import classify as K
    rep = K.classify(con, cfg=cfg, llm="off")
    fams = set(vsm.HOOKS)
    got = {r["media_id"]: (r["hook_category"], r["hook_family"]) for r in con.execute(
        "SELECT media_id, hook_category, hook_family FROM reels WHERE classified_by "
        "IS NOT NULL")}
    want = {"17900000000000101": ("pov", "story-time"),
            "17900000000000103": ("problem-solution", "negative-command"),
            "17900000000000201": ("controversy", "contrarian-reframe"),
            "17900000000000401": ("payoff-tease", "curiosity-gap"),
            "17900000000000403": ("problem-solution", "negative-command"),
            "3470000000000000501_900": ("curiosity-gap", "curiosity-gap")}
    wrong = {k: (got.get(k), v) for k, v in want.items() if got.get(k) != v}
    C.check("classify: hook_category -> maker HOOKS family", not wrong, str(wrong)[:160])
    C.check("classify: families read from viral_script_maker.HOOKS at runtime",
            rep["families_source"] == "viral_script_maker.HOOKS" and
            set(rep["families"]) == fams and
            {f for _, f in got.values() if f} <= fams)
    C.check("classify: curated (research-agent) rows never re-labelled",
            "17900000000000106" not in got)
    C.check("classify: own reels not classified", not con.execute(
        "SELECT COUNT(*) FROM reels WHERE is_own=1 AND classified_by IS NOT NULL"
    ).fetchone()[0])

    def sums():
        return {(r[0], r[1]): r[2] for r in con.execute(
            "SELECT hook_category, niche, SUM(times_seen) FROM hooks GROUP BY 1, 2")}, \
            {(r[0], r[1]): r[2] for r in con.execute(
                "SELECT pattern_name, niche, SUM(times_seen) FROM patterns GROUP BY 1, 2")}
    h1, p1 = sums()
    hooks, pats = K.aggregate_counts(con, cfg)
    ours = {(r["name"], r["niche"]): r["times_seen"] for r in con.execute(
        "SELECT * FROM ingest_aggregates WHERE kind='hooks'")}
    C.check("classify: aggregates = counts of classified reels", ours == hooks and
            h1.get(("pov", "beauty"), 0) >= hooks.get(("pov", "beauty"), 0) > 0, str(hooks))
    K.classify(con, cfg=cfg, llm="off", reclassify=True)
    h2, p2 = sums()
    con.execute("DELETE FROM hooks WHERE rowid IN (SELECT rowid FROM hooks WHERE "
                "niche='default' LIMIT 1)")          # a gap, so VACUUM renumbers
    con.commit()
    h1b, p1b = sums()
    con.execute("VACUUM")
    K.rebuild_aggregates(con, cfg)
    con.commit()
    h3, p3 = sums()
    C.check("classify: re-run + VACUUM never double counts", h1 == h2 and p1 == p2 and
            h1b == h3 and p1b == p3)
    os.environ["VSP_EXCLUDE_VENDOR"] = "1"
    try:
        hv, _ = K.aggregate_counts(con, cfg)
    finally:
        os.environ.pop("VSP_EXCLUDE_VENDOR", None)
    C.check("classify: VSP_EXCLUDE_VENDOR drops vendor rows from the aggregates",
            sum(hv.values()) == sum(hooks.values()) - 2)
    # LLM path (vsp.llm.complete_json contract: -> dict | None, never raises)
    asked = []

    def fake(prompt, schema, system=None, max_tokens=None):
        asked.append(prompt)
        assert "<<<" in prompt and schema["properties"]["hook_category"]["enum"]
        return {"hook_category": "question", "pattern": "none"}
    rid = con.execute("SELECT id FROM reels WHERE media_id='17900000000000301'").fetchone()
    con.execute("UPDATE reels SET classified_by=NULL WHERE media_id IN "
                "('17900000000000101', '17900000000000201')")
    r = K.classify(con, cfg=cfg, llm=fake)
    lab = con.execute("SELECT hook_category, classified_by FROM reels WHERE "
                      "media_id='17900000000000101'").fetchone()
    C.check("classify: LLM labels used when a model answers (schema-enforced)",
            r["llm"] == 2 and tuple(lab) == ("question", "llm") and len(asked) == 2 and
            rid is None)
    none_calls = []
    con.execute("UPDATE reels SET classified_by=NULL WHERE source IS NOT NULL")
    r = K.classify(con, cfg=cfg, llm=lambda *a, **k: none_calls.append(1))
    C.check("classify: LLM None -> rules fallback, stops asking after 3",
            len(none_calls) == 3 and r["llm"] == 0 and r["rules"] == r["candidates"])

    def boom(*a, **k):
        raise RuntimeError("model down")
    con.execute("UPDATE reels SET classified_by=NULL WHERE media_id='17900000000000101'")
    r = K.classify(con, cfg=cfg, llm=boom)
    C.check("classify: a raising LLM never propagates", r["rules"] == 1 and r["llm"] == 0)
    C.check("classify: resolve_llm('auto') never raises", K.resolve_llm("auto") is None or
            callable(K.resolve_llm("auto")))
    K.classify(con, cfg=cfg, llm="off", reclassify=True)


def _check_transcribe(C, con, cfg):
    from vsp.fixtures import FixtureTransport, graph_routes
    from vsp.ingest import transcribe as T
    on = {"transcribe": {"enabled": True, "keywords": ["GlowLab"]}}
    cands = [("17900000000000401",
              "https://scontent.cdninstagram.com/v/FIXTURE-bd01.mp4?_nc_sig=FIXTURE",
              "media_url")]
    tr = FixtureTransport(graph_routes())
    ff_calls = []
    rep = T.run(con, cands, cfg=on, env={}, transport=tr, runner=_fake_ffmpeg(ff_calls),
                ffmpeg="/bin/true")
    C.check("transcribe: graceful no-op without a key (no ffmpeg, no HTTP)",
            rep["transcribed"] == 0 and not tr.calls and not ff_calls and
            any("no API key" in k for k in rep["skipped"]), str(rep["skipped"])[:90])
    rep = T.run(con, cands, cfg={}, env={"VSP_ASR_API_KEY": "k"}, transport=tr,
                runner=_fake_ffmpeg(ff_calls), ffmpeg="/bin/true")
    C.check("transcribe: off unless configured", rep["transcribed"] == 0 and not tr.calls
            and any("disabled" in k for k in rep["skipped"]))
    rep = T.run(con, cands, cfg=on, env={"VSP_ASR_API_KEY": "k"}, transport=tr,
                runner=_fake_ffmpeg(ff_calls), ffmpeg=None)
    st = T.status(on, {"VSP_ASR_API_KEY": "k", "VSP_FFMPEG": "/nonexistent/ffmpeg"})
    C.check("transcribe: graceful no-op without ffmpeg", not st["ready"] and
            "ffmpeg" in (st["reason"] or ""))
    tmpdirs = []
    orig = T.tempfile.mkdtemp

    def spy(*a, **k):
        d = orig(*a, **k)
        tmpdirs.append(d)
        return d
    T.tempfile.mkdtemp = spy
    try:
        rep = T.run(con, cands + [("17900000000001001", "/no/such/render.mp4",
                                   "own_render"),
                                  ("17900000000000101", "/local/file.mp4", "own_render")],
                    cfg=on, env={"VSP_LLM_API_KEY": "fallback-key"}, transport=tr,
                    runner=_fake_ffmpeg(ff_calls), ffmpeg="/bin/true")
    finally:
        T.tempfile.mkdtemp = orig
    asr = [c for c in tr.calls if c["path"] == "v1/asr/transcribe"]
    body = asr[0]["body"] if asr else b""
    C.check("transcribe: multipart POST to api.meta.ai/v1/asr/transcribe?sessionId=",
            len(asr) == 1 and asr[0]["host"] == "api.meta.ai" and
            asr[0]["params"].get("sessionId", "").startswith("vsp-17900000000000401-") and
            asr[0]["headers"].get("Authorization") == "Bearer fallback-key" and
            asr[0]["headers"].get("Content-Type", "").startswith("multipart/form-data"))
    req = b'{"mode": "ENDPOINTING", "model": "muse-voice-transcribe-1.0", ' \
          b'"audioEncoding": "WAV", "keywords": ["GlowLab"]}'
    C.check("transcribe: request JSON part + audio WAV part (key fallback VSP_LLM_API_KEY)",
            b'name="request"' in body and req in body and
            b'name="audio"; filename="clip.wav"' in body and b"RIFF" in body)
    cmd = ff_calls[-1] if ff_calls else []
    C.check("transcribe: ffmpeg first 3.5 s -> mono 16-bit 16 kHz WAV",
            cmd[5:9] == ["-y", "-t", "3.5", "-i"] and ["-ac", "1"] == cmd[11:13] and
            ["-ar", "16000"] == cmd[13:15] and "pcm_s16le" in cmd and cmd[-2:-1] ==
            ["wav"], " ".join(cmd[10:18]))
    row = con.execute("SELECT transcript, hook_text, hook_source, classified_by FROM reels "
                      "WHERE media_id='17900000000000401'").fetchone()
    C.check("transcribe: text kept, first turn becomes the hook (hook_source asr)",
            row["transcript"].startswith("I tested every viral lip oil") and
            row["hook_text"] == "I tested every viral lip oil so you don't have to." and
            row["hook_source"] == "asr" and row["classified_by"] is None)
    C.check("transcribe: audio deleted, media never stored",
            tmpdirs and not any(os.path.exists(d) for d in tmpdirs) and
            "cdninstagram" not in json.dumps([dict(r) for r in con.execute(
                "SELECT * FROM reels")], default=str))
    C.check("transcribe: only own renders / API media_url (others refused)",
            rep["skipped"].get("render file not found") == 1 and
            rep["skipped"].get("own_render for a reel that is not yours") == 1)


def _check_pack(C, ctx, con, now):
    import research_bridge
    from vsp import research
    from vsp.ingest.classify import classify
    classify(con, llm="off")
    con.commit()
    with _silenced():
        code = research_bridge.refresh(now=now)
    pack, meta = research.load_pack(ctx.pack)
    C.check("pack refresh: written to VSP_RESEARCH_PACK and schema-valid",
            code == 0 and pack is not None and not meta["errors"] and
            research_bridge.pack_path() == ctx.pack, "; ".join(meta["errors"])[:100])
    if not pack:
        return
    legacy = {"generated_at", "schema_version", "sources", "reels_total",
              "reels_analyzed_last_7d", "top_hooks", "top_patterns", "niche_hooks",
              "fresh_hook_lines", "niche_map", "verified_rules"}
    C.check("pack refresh: every legacy key kept (+ top_reels)", legacy <= set(pack) and
            "top_reels" in pack, str(sorted(set(pack) - legacy)))
    fl = pack["fresh_hook_lines"]
    views_rank = [f.get("views") is not None for f in fl]
    C.check("pack refresh: fresh hook lines ranked by views, then likes",
            fl and fl[0].get("views") == 1250000 and views_rank == sorted(
                views_rank, reverse=True) and all(
                (a.get("likes") or 0) >= (b.get("likes") or 0) for a, b in zip(fl, fl[1:])
                if a.get("views") is None and b.get("views") is None and
                a.get("likes") is not None and b.get("likes") is not None))
    niches = {f["niche"] for f in fl}
    C.check("pack refresh: fresh lines across niches, own reels excluded",
            {"beauty", "fitness", "gadgets", "home"} <= niches and not any(
                "FIXTUREown" in (f.get("url") or "") for f in fl), str(len(niches)))
    tb = pack["top_reels"].get("beauty") or []
    C.check("pack refresh: top_reels per niche (url, views/likes, hook_text)",
            tb and tb[0]["url"].endswith("/FIXTUREbd01/") and tb[0]["views"] == 1250000
            and all({"url", "views", "likes", "hook_text"} <= set(x) for x in tb)
            and len(tb) <= 5)
    os.environ["VSP_EXCLUDE_VENDOR"] = "1"
    try:
        p2 = research_bridge.build_pack(now=now)
    finally:
        os.environ.pop("VSP_EXCLUDE_VENDOR", None)
    C.check("pack refresh: vendor rows excluded on request",
            not any(str(f.get("source") or "").startswith("vendor:")
                    for f in p2["fresh_hook_lines"]) and any(
                str(f.get("source") or "").startswith("vendor:") for f in fl))
    before = _sha(ctx.pack)
    saved = os.environ["VSP_VIRAL_DB"]
    os.environ["VSP_VIRAL_DB"] = os.path.join(ctx.tmp, "missing.db")
    try:
        with _silenced():
            code = research_bridge.refresh(now=now)
    finally:
        os.environ["VSP_VIRAL_DB"] = saved
    C.check("pack refresh: keeps the last good pack when the DB is missing",
            code == 1 and _sha(ctx.pack) == before and
            not os.path.exists(os.path.join(ctx.tmp, "missing.db")))


def _check_purge(C, con, cfg, now):
    from vsp.ingest import jobs
    con.execute("UPDATE reels SET purge_after='2026-09-01 00:00:00' WHERE "
                "media_id='17900000000000202'")
    con.execute("INSERT INTO reel_metrics(media_id, captured_at, age_h, views) VALUES "
                "('17900000000001012', ?, 900, 10)", (NOW,))
    con.execute("UPDATE reels SET purge_after=? WHERE media_id='17900000000001012'", (NOW,))
    con.commit()
    dry = jobs.purge(con, cfg, now=now, dry_run=True)
    rep = jobs.purge(con, cfg, now=now, vendor=True)
    gone = lambda m: con.execute("SELECT COUNT(*) FROM reels WHERE media_id=?",  # noqa
                                 (m,)).fetchone()[0] == 0
    C.check("purge: expired + vanished + vendor rows deleted (own metrics too)",
            dry["reels"] == 2 and rep["reels"] == 4 and gone("17900000000000202") and
            gone("17900000000001012") and con.execute(
                "SELECT COUNT(*) FROM reel_metrics WHERE media_id='17900000000001012'"
            ).fetchone()[0] == 0 and not con.execute(
                "SELECT COUNT(*) FROM reels WHERE source LIKE 'vendor:%'").fetchone()[0],
            f"dry {dry['reels']} deleted {rep['reels']}")


def _check_doctor(C, ctx):
    from vsp.fixtures import FixtureTransport, graph_routes
    from vsp.ingest import doctor
    res = doctor.run(env={}, offline=True)
    text = doctor.render(res)
    C.check("doctor: missing token -> FAIL + exact setup steps", not res["ok"] and
            "token" in res["step_keys"] and "user_id" in res["step_keys"] and
            "pca" in res["step_keys"] and "fb_exchange_token" in text and
            "instagram_business_account" in text)
    tr = FixtureTransport(graph_routes())
    res = doctor.run(env=dict(ENV, VSP_IG_APP_ID="900000000000001"), transport=tr)
    lv = {c["check"]: c["level"] for c in res["checks"]}
    C.check("doctor: online checks via the transport (/me, permissions, expiry, "
            "account, Public Content Access)",
            lv.get("token /me") == "OK" and lv.get("permissions") == "OK" and
            lv.get("token expiry") == "OK" and lv.get("instagram account") == "OK" and
            lv.get("Public Content Access") == "OK" and
            "FIXTURE-TOKEN-NOT-REAL" not in doctor.render(res), str(lv)[:160])
    miss = FixtureTransport(graph_routes(extra=[
        {"path": r"me/permissions", "response": {"fixture": "graph_identity.json",
                                                 "key": "permissions_missing"}},
        {"path": r"17841400000000001/recently_searched_hashtags",
         "response": {"status": 400, "fixture": "errors.json", "key": "permission"}}]))
    res = doctor.run(env=ENV, transport=miss)
    lv = {c["check"]: (c["level"], c["detail"]) for c in res["checks"]}
    C.check("doctor: names the missing permission / feature",
            lv.get("permissions", ("",))[0] == "FAIL" and
            "instagram_manage_insights" in lv["permissions"][1] and
            lv.get("Public Content Access", ("",))[0] == "FAIL" and
            "Instagram Public Content Access" in lv["Public Content Access"][1] and
            "pca" in res["step_keys"])


def _check_cli(C, ctx):
    from vsp.ingest.__main__ import main
    with _silenced() as (out, err):
        code = main(["--json", "status"])
    try:
        st = json.loads(out.getvalue())
    except ValueError:
        st = {}
    C.check("cli: python3 -m vsp.ingest --json status", code == 0 and
            st.get("schema_version") == 1 and st.get("own_reels") == 10,
            f"exit {code}, own_reels {st.get('own_reels')}")
    with _silenced() as (out, err):
        code = main(["hashtags"])
    C.check("cli: not configured -> exit 2 with setup pointer", code == 2 and
            "doctor" in err.getvalue())


# =================================================================== feedback
def run_feedback():
    from vsp.fixtures import hermetic_ingest_env
    C = _Checks("vsp.feedback selfcheck")
    try:
        with hermetic_ingest_env("vsp_feedback_check_") as ctx:
            _feedback_checks(C, ctx)
    except Exception as e:  # noqa: BLE001
        C.check("selfcheck harness", False, f"{type(e).__name__}: {e} | "
                + traceback.format_exc().strip().splitlines()[-1])
    return C.result()


FB_RUNS = [  # (tag8, niche, hook_family, duration_s, media_id)
    ("11111111", "beauty", "transformation", 30, "17900000000001001"),
    ("22222222", "beauty", "transformation", 28, "17900000000001002"),
    ("33333333", "beauty", "curiosity-gap", 25, "17900000000001003"),
    ("44444444", "beauty", "curiosity-gap", 30, "17900000000001004"),
    ("55555555", "home", "bold-claim", 30, "17900000000001005"),
    ("66666666", "home", "bold-claim", 22, "17900000000001006"),
]


def _manifest(d, sha, niche, family, duration, summary=True, script=None):
    os.makedirs(d, exist_ok=True)
    man = {"schema_version": 1, "created": "2026-09-20T10:00:00Z",
           "seeds": {"root": 701, "candidates": [701]}, "args": {"seed": 701},
           "outputs": {"script.json": sha}}
    if summary:
        man["script_summary"] = {
            "prompt": f"fixture {family} product", "niche": niche, "hook_family": family,
            "hook_source": "template", "hook": f"The {family} FIXTURE hook.",
            "presenter": "human", "format": "demo", "duration_s": duration, "seed": 701,
            "candidate_seed": 9001, "script_sha256": sha}
    if script is not None:
        with open(os.path.join(d, "script.json"), "wb") as f:
            f.write(script)
    p = os.path.join(d, "manifest.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(man, f)
    return p


def _feedback_checks(C, ctx):
    from vsp import config
    from vsp import feedback as F
    from vsp.fixtures import FixtureTransport, build_fixture_db, graph_routes
    from vsp.ingest import db as idb
    from vsp.ingest import jobs
    from vsp.ingest import settings as S
    from vsp.ingest.util import parse_ts
    now = parse_ts(NOW)
    clock = {"now": now}
    repo_learned = os.path.join(config.REPO, "learned")
    before_learned = sorted(os.listdir(repo_learned)) if os.path.isdir(repo_learned) else []
    _write_cfg(ctx.config, INGEST_CFG)
    cfg = S.load()
    build_fixture_db(ctx.db)
    con = idb.connect(ctx.db)
    # runs the pipeline "made": manifests with script_summary ...
    for tag8, niche, fam, dur, _ in FB_RUNS:
        _manifest(os.path.join(ctx.outputs, f"run-{tag8}"), tag8 + "ab" * 28, niche, fam, dur)
    # ... one without script_summary (read script.json next to it) ...
    script = json.dumps({"prompt": "cable organizer", "niche": "home",
                         "hook_family": "negative-command", "hook_source": "template",
                         "presenter": "ai", "format": "demo", "duration_s": 30,
                         "hook_stack": [{"t": "0.0-0.5s", "on_screen": "CORDS"},
                                        {"t": "0.5-3.0s", "dialogue": "Stop stacking "
                                         "cords behind your desk."}]}).encode("utf-8")
    sha7 = hashlib.sha256(script).hexdigest()
    _manifest(os.path.join(ctx.outputs, "cable-organizer"), sha7, None, None, None,
              summary=False, script=script)
    # ... and a trial whose manifest lives outside the search roots
    trial_man = _manifest(os.path.join(ctx.tmp, "elsewhere", "desk-reset"),
                          "5e5e5e5e" + "cd" * 28, "home", "curiosity-gap", 20)
    tr = FixtureTransport(graph_routes(own_tag="vsp-" + sha7[:8],
                                       now_fn=lambda: clock["now"], extra=[
        {"path": r"17900000000001001/insights",
         "response": [{"status": 400, "fixture": "insights.json",
                       "key": "unsupported_metric"},
                      lambda m, p, q: __import__("vsp.fixtures", fromlist=["x"])
                      .own_insights_response("17900000000001001", now=clock["now"])]}]))
    client = jobs.make_client(con, cfg, env=ENV, transport=tr, clock=lambda: clock["now"],
                              sleep=lambda s: None)
    own = jobs.run_own(con, client, cfg, now=now)
    C.check("own reels registered (ingest `own`)", own["inserted"] == 11, str(own["inserted"]))

    # --------------------------------------------------------------- link
    s7 = F.load_summary(os.path.join(ctx.outputs, "cable-organizer", "manifest.json"))
    C.check("link: script.json fallback when manifest has no script_summary",
            s7["from"] == "script.json" and s7["script_sha256"] == sha7 and
            s7["hook_family"] == "negative-command" and s7["seed"] == 701 and
            s7["hook"] == "Stop stacking cords behind your desk.")
    rep = F.link_auto(con, roots=F.search_roots(), now=now)
    linked = {x["media_id"]: x for x in rep["linked"]}
    C.check("link --auto: #vsp-<sha8> caption tags matched to manifests",
            set(linked) == {m for *_, m in FB_RUNS} | {"17900000000001007"} and
            rep["untagged"] == 1 and sorted(u["tag"] for u in rep["unmatched"]) ==
            ["vsp-12121212", "vsp-5e5e5e5e", "vsp-deadbeef"],
            f"linked {len(linked)}, unmatched {[u['tag'] for u in rep['unmatched']]}")
    p1 = con.execute("SELECT * FROM posts WHERE media_id='17900000000001001'").fetchone()
    C.check("link: posts row carries the script summary", p1 is not None and
            p1["niche"] == "beauty" and p1["hook_family"] == "transformation" and
            p1["duration_s"] == 30 and p1["candidate_seed"] == 9001 and
            p1["permalink"].endswith("/FIXTUREown01/") and
            p1["script_sha256"].startswith("11111111"))
    row = F.link(con, "17900000000001011", trial_man, trial=True, now=now)
    C.check("link --media-id --manifest --trial", row["is_trial"] == 1 and con.execute(
        "SELECT is_trial, script_slug FROM reels WHERE media_id='17900000000001011'"
    ).fetchone()[:] == (1, "vsp-5e5e5e5e"))
    from vsp.ingest.normalize import normalize_item, upsert_reel
    other, _ = normalize_item({"id": "17900000000000401", "media_type": "VIDEO",
                               "permalink": "https://www.instagram.com/reel/FIXTUREbd01/",
                               "caption": "someone else's reel"}, source="ig_bd",
                              source_query="@fixture_glowlab", niche="beauty", now=now)
    upsert_reel(con, other)
    try:
        F.link(con, "17900000000000401", trial_man)
        refused = False
    except F.LinkError:
        refused = True
    C.check("link: refuses someone else's reel", refused and not con.execute(
        "SELECT 1 FROM posts WHERE media_id='17900000000000401'").fetchone())
    C.check("link --auto is idempotent", F.link_auto(con, roots=F.search_roots())[
        "linked"] == [])

    # --------------------------------------------------------------- pull
    p = F.pull(con, client, now=now, link_first=False)
    ages = {r[0]: r[1] for r in con.execute("SELECT media_id, age_h FROM reel_metrics")}
    C.check("pull: one snapshot per due checkpoint (24h/48h/7d/28d)",
            p["snapshots"] == 9 and ages.get("17900000000001008") == 26 and
            ages.get("17900000000001001") == 720 and "17900000000001011" not in ages and
            p["skipped"].get("younger than 24 h") == 1, f"{p['snapshots']} {p['skipped']}")
    C.check("pull: unsupported metric dropped and retried", "reposts" in
            p.get("dropped_metrics", []))
    C.check("pull: deleted media marked for purge", p["vanished"] == ["17900000000001012"])
    n_calls = len(tr.calls)
    p2 = F.pull(con, client, now=now, link_first=False)
    C.check("pull: idempotent within a checkpoint (no API calls)",
            p2["snapshots"] == 0 and len(tr.calls) == n_calls)
    clock["now"] = now + timedelta(hours=30)
    p3 = F.pull(con, client, now=clock["now"], link_first=True)
    new = {r[0] for r in con.execute("SELECT media_id FROM reel_metrics WHERE "
                                     "captured_at > ?", (NOW,))}
    C.check("pull: next checkpoints only (1008 -> 48 h, 1011 -> 24 h)",
            new == {"17900000000001008", "17900000000001011"} and p3["snapshots"] == 2,
            str(sorted(new)))
    snap = con.execute("SELECT * FROM reel_metrics WHERE media_id='17900000000001001'"
                       ).fetchone()
    C.check("pull: insight names -> reel_metrics columns", snap["saves"] == 410 and
            snap["avg_watch_ms"] == 14200 and snap["skip_rate"] == 24.0 and
            snap["total_watch_ms"] == 139160000 and snap["source"] == "api")

    # ------------------------------------------------------ labels + priors
    lab = F.labels(con)
    byid = {x["media_id"]: x for x in lab["posts"]}
    x1 = byid.get("17900000000001001", {})
    C.check("labels: hook_rate = 1 - skip (percent normalised), watch, share, save",
            lab["skip_scale"] == "percent" and abs(x1.get("hook_rate", 0) - 0.76) < 1e-9
            and abs(x1.get("watch_ratio", 0) - 14.2 / 30) < 1e-9 and
            abs(x1.get("share_rate", 0) - 230 / 7600) < 1e-9 and
            abs(x1.get("save_rate", 0) - 410 / 7600) < 1e-9)
    comp = sorted(x["composite"] for x in lab["posts"])
    wins = sum(1 for x in lab["posts"] if x["success"])
    C.check("labels: composite z-scores, success = composite >= account median",
            len(lab["posts"]) == 10 and abs(sum(comp)) < 1.0 and wins == 5 and
            byid["17900000000001001"]["success"] and not byid["17900000000001008"]["success"]
            and byid["17900000000001008"]["watch_ratio"] is None,
            f"n {len(lab['posts'])} wins {wins} median {lab['median']:.3f}")
    lr = F.learn(con, now=clock["now"])
    with open(config.priors_path(), encoding="utf-8") as f:
        pri = json.load(f)
    C.check("learn: learned/priors.json matches learned/README.md schema v1",
            config.priors_path() == os.path.join(ctx.learned, "priors.json") and
            not F.validate_priors(pri) and list(pri) == ["schema_version", "updated_at",
                                                        "metric", "families", "global"],
            "; ".join(F.validate_priors(pri))[:120])
    fam = pri["families"]
    bt = fam.get("beauty", {}).get("transformation", {})
    bc = fam.get("beauty", {}).get("curiosity-gap", {})
    C.check("learn: Beta(1,1) + wins/losses per (niche, family); global pools niches",
            bt == {"alpha": 3.0, "beta": 1.0, "n": 2} and bc.get("n") == 2 and
            fam.get("home", {}).get("negative-command", {}).get("n") == 1 and
            fam.get("home", {}).get("curiosity-gap", {}).get("n") == 1 and
            pri["global"]["curiosity-gap"]["n"] == 3 and
            sum(e["n"] for t in fam.values() for e in t.values()) ==
            sum(e["n"] for e in pri["global"].values()) == 8, json.dumps(fam)[:160])
    C.check("learn: winners outrank losers (beauty transformation > curiosity-gap)",
            bt["alpha"] / (bt["alpha"] + bt["beta"]) >
            bc.get("alpha", 1) / (bc.get("alpha", 1) + bc.get("beta", 1)))
    import importlib.util
    if importlib.util.find_spec("vsp.priors") is not None:
        from vsp import priors as P
        C.check("learn: the maker's reader (vsp.priors) accepts the file",
                P.load_priors(config.priors_path()) is not None)
    C.check("learn: unlinked posts only shape the median", lr["labelled"] == 10 and
            lr["linked"] == 8)
    # ------------------------------------------------------------- report
    path, text = F.report(con, now=clock["now"])
    C.check("report: learned/PERFORMANCE.md (table, ~90% interval, best/worst, "
            "what's working)", path == os.path.join(ctx.learned, "PERFORMANCE.md") and
            os.path.isfile(path) and "| beauty | transformation | 2 | 2 |" in text and
            "~90% interval" in text and "## Best posts" in text and
            "## Worst posts" in text and "## What's working" in text and
            "#vsp-" in text)
    lo, hi = F.interval90(3.0, 1.0)
    C.check("report: Beta quantiles (Beta(2,1) 5% = sqrt(.05), Beta(3,1) 95%)",
            abs(F.beta_ppf(0.05, 2.0, 1.0) - 0.05 ** 0.5) < 1e-6 and
            abs(hi - 0.95 ** (1 / 3.0)) < 1e-6 and 0 < lo < hi < 1)
    st = F.status(con, now=clock["now"])
    C.check("status", st["linked"] == 8 and st["trials"] == 1 and st["priors"]["valid"]
            and st["vanished"] == 1 and st["performance_md"], str(st)[:120])
    with _silenced() as (out, err):
        code = F.main(["--json", "status"])
    C.check("cli: python3 -m vsp.feedback --json status", code == 0 and
            json.loads(out.getvalue() or "{}").get("linked") == 8)
    C.check("hermetic: repo learned/ untouched", (sorted(os.listdir(repo_learned))
                                                 if os.path.isdir(repo_learned) else [])
            == before_learned)
    _check_legacy_reader(C, ctx, True)
    con.close()
