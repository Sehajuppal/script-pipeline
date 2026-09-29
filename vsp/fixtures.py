"""Hermetic fixture viral.db for the self-test and the eval harness.

The real research DB lives at ~/workspace/viral-research/viral.db and is not
part of the repo. Gate 2 fails without reference reels (never weakened), so
hermetic runs point the pipeline at this fixture instead via VSP_VIRAL_DB
(or HOME=<dir> for the pre-2.0 code, which hard-codes the ~ path).

Every fixture reel URL contains "FIXTURE" so a fixture reference can never be
mistaken for a real one: gate 2 rejects FIXTURE references unless the run
explicitly opts in with VSP_FIXTURE_OK=1 (self-test / evals only).

Schema reconstructed from every query in research_bridge.py and
make_shotlist.py (reels / hooks / patterns).
"""
import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS patterns(
    pattern_id INTEGER PRIMARY KEY, pattern_name TEXT, niche TEXT,
    times_seen INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS hooks(
    hook_category TEXT, niche TEXT, times_seen INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS reels(
    id INTEGER PRIMARY KEY, url TEXT, username TEXT, niche TEXT,
    like_count INTEGER, notes TEXT, hook_text TEXT, pattern_id INTEGER,
    analyzed_at TEXT);
"""

# maker niches plus a few research-DB niche spellings
NICHES = ["gadgets", "tools", "beauty", "wellness", "automotive", "pets",
          "home", "outdoors", "fitness", "food", "finance", "education",
          "commentary", "default", "fashion-beauty", "ugc-ads"]

PATTERNS = ["talking-head-ugc", "before-after", "b-roll-captions",
            "day-in-life", "problem-solution"]

HOOK_FAMILIES = ["curiosity-gap", "bold-claim", "problem-solution",
                 "before-after", "pov"]


def build_fixture_db(path):
    """Create (or rebuild) a fixture viral.db at `path`. Returns the path."""
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    try:
        con.executescript(SCHEMA)
        for pid, name in enumerate(PATTERNS, 1):
            con.execute("INSERT INTO patterns VALUES (?,?,?,?)",
                        (pid, name, "ugc-ads", 10 - pid))
        rid = 0
        for ni, niche in enumerate(NICHES):
            for fi, fam in enumerate(HOOK_FAMILIES[:3]):
                con.execute("INSERT INTO hooks VALUES (?,?,?)",
                            (HOOK_FAMILIES[(ni + fi) % len(HOOK_FAMILIES)],
                             niche, 30 - 5 * fi))
            for k in range(3):
                rid += 1
                con.execute(
                    "INSERT INTO reels VALUES (?,?,?,?,?,?,?,?,?)",
                    (rid,
                     f"https://www.instagram.com/reel/FIXTURE-{niche}-{k + 1}/",
                     f"fixture_{niche.replace('-', '_')}_{k + 1}",
                     niche, 100000 - 1000 * rid,
                     f"FIXTURE reference ({niche} #{k + 1}) — hermetic test "
                     f"data, not a real reel",
                     f"The {niche} detail nobody shows you",
                     1 + (rid % len(PATTERNS)),
                     "2026-09-27 12:00:00"))
        con.commit()
    finally:
        con.close()
    return path


def fixture_home(root):
    """Lay out <root>/workspace/viral-research/viral.db (the legacy ~ path)
    and return (home_dir, db_path)."""
    db = os.path.join(root, "workspace", "viral-research", "viral.db")
    build_fixture_db(db)
    return root, db


# ---------------------------------------------------------------------------
# vsp.ingest / vsp.feedback fixtures (pipeline v2, WS-DATA). Everything below
# is additive: build_fixture_db / fixture_home above are unchanged.
#
#   IG_FIXTURES_DIR            tests/fixtures/ig/ — canned Graph API / ASR
#                              responses (every permalink contains FIXTURE)
#   load_ig_fixture(name)      parsed JSON (or raw text for non-.json files)
#   FixtureTransport(routes)   a vsp.ingest.graph transport serving canned
#                              responses; records every call; unmatched
#                              requests raise LookupError (never the network)
#   build_ingest_fixture_db(p) the legacy fixture DB migrated to the ingest
#                              schema plus a few ingested FIXTURE reels
#   hermetic_ingest_env()      context manager: temp VSP_VIRAL_DB /
#                              VSP_LEARNED_DIR / VSP_RESEARCH_PACK /
#                              VSP_OUTPUTS / VSP_INGEST_CONFIG /
#                              VSP_DOSSIER_DIR, credentials unset, urlopen
#                              disabled; restores the caller's env on exit
# ---------------------------------------------------------------------------
IG_FIXTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "tests", "fixtures", "ig")


def load_ig_fixture(name):
    import json
    p = os.path.join(IG_FIXTURES_DIR, name)
    with open(p, encoding="utf-8") as f:
        return json.load(f) if name.endswith(".json") else f.read()


class FixtureTransport:
    """Canned responses for vsp.ingest.graph.GraphClient (and the ASR call).

    routes: list of dicts, first match wins:
      {"method": "GET", "path": r"regex on the URL path (after /vXX.X/)",
       "params": {"name": r"regex" | None (must be absent)},
       "response": R | [R, R, ...]}      a list is consumed in order, the
                                          last element then repeats
    R: {"fixture": "file.json", "key": "k" (optional sub-key),
        "body": obj (instead of fixture), "status": 200,
        "headers": {...}}  or a callable(method, path, params) -> R.
    Every call is recorded in .calls as {method, path, version, params,
    headers, body}."""

    def __init__(self, routes, fixtures_dir=None):
        self.routes = [dict(r) for r in routes]
        for r in self.routes:
            r["_i"] = 0
        self.dir = fixtures_dir or IG_FIXTURES_DIR
        self.calls = []

    def _body(self, spec):
        import json
        if "body" in spec:
            obj = spec["body"]
        else:
            with open(os.path.join(self.dir, spec["fixture"]), encoding="utf-8") as f:
                obj = json.load(f)
            if spec.get("key") is not None:
                obj = obj[spec["key"]]
        if isinstance(obj, (bytes, bytearray)):
            return bytes(obj)
        return json.dumps(obj).encode("utf-8")

    def __call__(self, method, url, headers=None, body=None, timeout=None):
        import re
        import urllib.parse
        from vsp.ingest.graph import Response
        parts = urllib.parse.urlsplit(url)
        params = dict(urllib.parse.parse_qsl(parts.query, keep_blank_values=True))
        m = re.match(r"^/(v\d+\.\d+)/(.*)$", parts.path)
        version, path = (m.group(1), m.group(2)) if m else (None, parts.path.lstrip("/"))
        self.calls.append({"method": method, "host": parts.netloc, "path": path,
                           "version": version, "params": params,
                           "headers": dict(headers or {}), "body": body})
        for r in self.routes:
            if r.get("method", "GET") != method:
                continue
            if not re.fullmatch(r["path"], path):
                continue
            ok = True
            for k, rx in (r.get("params") or {}).items():
                if rx is None:
                    ok = ok and k not in params
                else:
                    ok = ok and k in params and re.search(rx, params[k]) is not None
            if not ok:
                continue
            resp = r["response"]
            if isinstance(resp, list):
                spec = resp[min(r["_i"], len(resp) - 1)]
                r["_i"] += 1
            else:
                spec = resp
            if callable(spec):
                spec = spec(method, path, params)
            hdrs = {str(k).lower(): v for k, v in (spec.get("headers") or {}).items()}
            return Response(int(spec.get("status", 200)), hdrs, self._body(spec))
        raise LookupError(f"FixtureTransport: no route for {method} /{path} "
                          f"params={sorted(k for k in params if k not in ('access_token', 'appsecret_proof'))}")

    def count(self, path_rx):
        import re
        return sum(1 for c in self.calls if re.fullmatch(path_rx, c["path"]))


def build_ingest_fixture_db(path):
    """The legacy fixture DB (build_fixture_db) migrated to the ingest schema,
    plus FIXTURE rows the way vsp.ingest writes them (hashtag + Business
    Discovery + one own reel). -> path."""
    build_fixture_db(path)
    from vsp.ingest import db as idb
    from vsp.ingest.normalize import normalize_item, upsert_reel
    now = "2026-09-28 12:00:00"
    items = [
        ("ig_hashtag_top", "#skincareroutine", "beauty", None, None,
         {"id": "17900000000000901", "media_type": "VIDEO", "like_count": 5100,
          "comments_count": 88, "timestamp": "2026-09-27T09:00:00+0000",
          "permalink": "https://www.instagram.com/reel/FIXTUREdb01/",
          "caption": "POV: your serum finally stopped pilling \u2728\n#skincareroutine"}),
        ("ig_bd", "@fixture_glowlab", "beauty", "fixture_glowlab", 48000,
         {"id": "17900000000000902", "media_type": "VIDEO",
          "media_product_type": "REELS", "like_count": 40210, "comments_count": 812,
          "view_count": 1250000, "timestamp": "2026-09-26T15:00:00+0000",
          "permalink": "https://www.instagram.com/reel/FIXTUREdb02/",
          "caption": "I tested every viral lip oil so you don't have to"}),
        ("ig_hashtag_top", "#homeworkout", "fitness", None, None,
         {"id": "17900000000000903", "media_type": "VIDEO", "like_count": 900,
          "comments_count": 12, "timestamp": "2026-09-27T20:00:00+0000",
          "permalink": "https://www.instagram.com/reel/FIXTUREdb03/",
          "caption": "Day 1 vs day 30 of 10-minute core workouts"}),
    ]
    con = idb.connect(path)
    try:
        for source, q, niche, user, followers, it in items:
            row, _ = normalize_item(it, source=source, source_query=q, niche=niche,
                                    username=user, followers=followers, now=now)
            upsert_reel(con, row)
        own, _ = normalize_item(
            {"id": "17900000000000904", "media_type": "VIDEO",
             "media_product_type": "REELS", "like_count": 310, "comments_count": 9,
             "timestamp": "2026-09-25T18:00:00+0000",
             "permalink": "https://www.instagram.com/reel/FIXTUREdb04/",
             "caption": "This is the after. #vsp-0a1b2c3d"},
            source="ig_own", niche=None, username="fixture_own_account", now=now,
            is_own=True)
        upsert_reel(con, own)
        con.commit()
    finally:
        con.close()
    return path


_CREDENTIAL_ENV = ("VSP_IG_ACCESS_TOKEN", "VSP_IG_USER_ID", "VSP_IG_APP_SECRET",
                   "VSP_IG_APP_ID", "VSP_IG_GRAPH_VERSION", "VSP_ASR_API_KEY",
                   "VSP_LLM_API_KEY", "VSP_LLM_MODEL", "VSP_LLM_PROVIDER",
                   "VSP_LLM_URL", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
                   "MODEL_API_KEY", "META_API_KEY", "META_MODEL_API_KEY",
                   "VSP_EXCLUDE_VENDOR", "VSP_FIXTURE_OK")


class _Ctx:
    pass


def hermetic_ingest_env(prefix="vsp_ingest_check_"):
    """Context manager for the vsp.ingest / vsp.feedback self-checks. The
    maker and research_bridge are imported FIRST, under the caller's env, so
    their import-time pack caches never see the temp paths."""
    import contextlib
    import shutil
    import sys
    import tempfile
    import urllib.request

    @contextlib.contextmanager
    def _cm():
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if repo not in sys.path:
            sys.path.insert(0, repo)
        for mod in ("research_bridge", "viral_script_maker"):
            try:
                __import__(mod)
            except Exception:  # noqa: BLE001 — optional for the checks
                pass
        saved_env = dict(os.environ)
        saved_urlopen = urllib.request.urlopen
        tmp = tempfile.mkdtemp(prefix=prefix)
        ctx = _Ctx()
        ctx.tmp = tmp
        ctx.db = os.path.join(tmp, "viral.db")
        ctx.learned = os.path.join(tmp, "learned")
        ctx.pack = os.path.join(tmp, "research_pack.json")
        ctx.outputs = os.path.join(tmp, "outputs")
        ctx.config = os.path.join(tmp, "ingest.json")
        ctx.dossiers = os.path.join(tmp, "dossiers")
        for d in (ctx.learned, ctx.outputs, ctx.dossiers):
            os.makedirs(d, exist_ok=True)

        def _no_network(*a, **k):
            raise AssertionError("network access attempted inside a hermetic "
                                 "self-check")
        try:
            for k in _CREDENTIAL_ENV:
                os.environ.pop(k, None)
            os.environ.update({"VSP_VIRAL_DB": ctx.db, "VSP_LEARNED_DIR": ctx.learned,
                               "VSP_RESEARCH_PACK": ctx.pack,
                               "VSP_OUTPUTS": ctx.outputs,
                               "VSP_INGEST_CONFIG": ctx.config,
                               "VSP_DOSSIER_DIR": ctx.dossiers})
            urllib.request.urlopen = _no_network
            yield ctx
        finally:
            urllib.request.urlopen = saved_urlopen
            os.environ.clear()
            os.environ.update(saved_env)
            shutil.rmtree(tmp, ignore_errors=True)
    return _cm()


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "fixture-viral.db"
    print(build_fixture_db(out))
