"""Read-write access to the research DB (config.viral_db_path()) and the
idempotent ingest migrations (research doc instagram-data-access.md §9).

    connect(path=None, create=False, migrate_schema=True) -> sqlite3.Connection
        Opens the DB read-write. A missing (or 0-byte) file raises DBMissing
        unless create=True — only the explicit `python3 -m vsp.ingest init-db`
        passes create=True, so no other command can conjure an empty DB that
        research_bridge would then build an empty pack from.
    migrate(con) -> [actions]      additive + idempotent; safe on the legacy
                                   research-agent DB and on a fresh file
    schema_version(con) -> int | None   (meta table; None = never migrated)

Migrations (schema v1):
  * the legacy tables (patterns / hooks / reels, as in vsp/fixtures.py) are
    created only if absent; missing legacy reels columns are added;
  * reels gains the §9 columns (platform, media_id, source, source_query,
    media_type, media_product_type, media_audio_type, posted_at, caption,
    views, comments, shares, saves, transcript, hook_source, is_own,
    is_trial, script_slug, purge_after) plus four ingest bookkeeping columns
    (hook_category, hook_family, classified_by, last_seen_at), one
    ALTER TABLE ... ADD COLUMN each;
  * UNIQUE INDEX reels_media ON reels(platform, media_id)  (legacy rows keep
    media_id NULL, which SQLite never treats as a duplicate);
  * new tables reel_metrics, posts, hashtag_budget, meta, plus
    account_metrics (daily account insights) and ingest_aggregates (which
    hooks/patterns rows vsp.ingest.classify contributed — so re-running
    classify never double counts and never touches the research agent's
    own rows); posts also carries hook + candidate_seed and reel_metrics a
    source (api | import:<name>) — OPTIONAL_COLUMNS, added when missing.
  * pipeline v2.1 (vsp.feedback, still schema v1: additive only): posts
    gains variant_id (the alternate opening that was posted: A = primary),
    hook_archetype + visual_type (that variant's), vibe, tone (the
    direction's tone.voice) and primary_keyword — OPTIONAL_COLUMNS too, so
    a v2.0 DB gains them on its next connect() and old rows read NULL.
Legacy readers select named columns (make_shotlist.niche_references,
research_bridge), so they keep working on both schemas. External WRITERS
must use named-column INSERTs into reels once it is migrated.

Vendor policy (research doc §7): rows whose source starts with 'vendor:'
may come from scrapers that conflict with Instagram's Terms. NOT_VENDOR_SQL
is the filter gates/readers can add; VSP_EXCLUDE_VENDOR=1 (or "vendor_rows":
"exclude" in config/ingest.json) makes vsp.ingest and research_bridge drop
them everywhere.
"""
import os
import sqlite3

from vsp import config
from vsp.ingest.util import sql_ts

SCHEMA_VERSION = 1

LEGACY_TABLES = {
    "patterns": ("CREATE TABLE IF NOT EXISTS patterns("
                 "pattern_id INTEGER PRIMARY KEY, pattern_name TEXT, niche TEXT, "
                 "times_seen INTEGER DEFAULT 1)"),
    "hooks": ("CREATE TABLE IF NOT EXISTS hooks("
              "hook_category TEXT, niche TEXT, times_seen INTEGER DEFAULT 1)"),
    "reels": ("CREATE TABLE IF NOT EXISTS reels("
              "id INTEGER PRIMARY KEY, url TEXT, username TEXT, niche TEXT, "
              "like_count INTEGER, notes TEXT, hook_text TEXT, pattern_id INTEGER, "
              "analyzed_at TEXT)"),
}
LEGACY_REELS_COLUMNS = [("url", "TEXT"), ("username", "TEXT"), ("niche", "TEXT"),
                        ("like_count", "INTEGER"), ("notes", "TEXT"),
                        ("hook_text", "TEXT"), ("pattern_id", "INTEGER"),
                        ("analyzed_at", "TEXT")]

# research doc §9, in order
REELS_COLUMNS = [
    ("platform", "TEXT DEFAULT 'instagram'"),
    ("media_id", "TEXT"),
    ("source", "TEXT"),
    ("source_query", "TEXT"),
    ("media_type", "TEXT"),
    ("media_product_type", "TEXT"),
    ("media_audio_type", "TEXT"),
    ("posted_at", "TEXT"),
    ("caption", "TEXT"),
    ("views", "INTEGER"),
    ("comments", "INTEGER"),
    ("shares", "INTEGER"),
    ("saves", "INTEGER"),
    ("transcript", "TEXT"),
    ("hook_source", "TEXT"),
    ("is_own", "INTEGER DEFAULT 0"),
    ("is_trial", "INTEGER DEFAULT 0"),
    ("script_slug", "TEXT"),
    ("purge_after", "TEXT"),
]
# vsp.ingest bookkeeping (beyond §9; additive like the rest)
INGEST_COLUMNS = [
    ("hook_category", "TEXT"),     # pack category (what research_bridge ranks)
    ("hook_family", "TEXT"),       # viral_script_maker.HOOKS family or NULL
    ("classified_by", "TEXT"),     # rules | llm
    ("last_seen_at", "TEXT"),      # last time an API call returned the item
]
ALL_REELS_COLUMNS = [c for c, _ in LEGACY_REELS_COLUMNS + REELS_COLUMNS + INGEST_COLUMNS]

NEW_TABLES = [
    ("reel_metrics",
     "CREATE TABLE IF NOT EXISTS reel_metrics("
     "media_id TEXT, captured_at TEXT, age_h INTEGER, views INTEGER, reach INTEGER, "
     "likes INTEGER, comments INTEGER, shares INTEGER, saves INTEGER, reposts INTEGER, "
     "avg_watch_ms INTEGER, total_watch_ms INTEGER, skip_rate REAL, "
     "PRIMARY KEY (media_id, captured_at))",
     ("media_id", "captured_at", "age_h", "views", "reach", "likes", "comments",
      "shares", "saves", "reposts", "avg_watch_ms", "total_watch_ms", "skip_rate")),
    ("posts",
     "CREATE TABLE IF NOT EXISTS posts("
     "media_id TEXT PRIMARY KEY, permalink TEXT, posted_at TEXT, script_sha256 TEXT, "
     "slug TEXT, prompt TEXT, niche TEXT, hook_family TEXT, hook_source TEXT, "
     "presenter TEXT, format TEXT, duration_s REAL, seed INTEGER, manifest_path TEXT, "
     "is_trial INTEGER DEFAULT 0, linked_at TEXT)",
     ("media_id", "permalink", "posted_at", "script_sha256", "slug", "prompt", "niche",
      "hook_family", "hook_source", "presenter", "format", "duration_s", "seed",
      "manifest_path", "is_trial", "linked_at")),
    ("hashtag_budget",
     "CREATE TABLE IF NOT EXISTS hashtag_budget("
     "tag TEXT PRIMARY KEY, first_used_at TEXT, last_used_at TEXT, hashtag_id TEXT)",
     ("tag", "first_used_at", "last_used_at", "hashtag_id")),
    ("meta",
     "CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT)",
     ("key", "value")),
    ("account_metrics",
     "CREATE TABLE IF NOT EXISTS account_metrics("
     "date TEXT, metric TEXT, breakdown TEXT NOT NULL DEFAULT '', value INTEGER, "
     "captured_at TEXT, PRIMARY KEY (date, metric, breakdown))",
     ("date", "metric", "breakdown", "value", "captured_at")),
    ("ingest_aggregates",
     "CREATE TABLE IF NOT EXISTS ingest_aggregates("
     "kind TEXT, name TEXT, niche TEXT, row_id INTEGER, times_seen INTEGER, "
     "updated_at TEXT, PRIMARY KEY (kind, name, niche))",
     ("kind", "name", "niche", "row_id", "times_seen", "updated_at")),
]
# additive columns on the new tables (added when missing, like reels')
OPTIONAL_COLUMNS = {
    "posts": [("hook", "TEXT"), ("candidate_seed", "INTEGER"),
              # v2.1 creative layer (vsp.feedback link; NULL for older scripts)
              ("variant_id", "TEXT"), ("hook_archetype", "TEXT"),
              ("visual_type", "TEXT"), ("vibe", "TEXT"), ("tone", "TEXT"),
              ("primary_keyword", "TEXT")],
    "reel_metrics": [("source", "TEXT")],        # api | import:<name>
}
INDEXES = [
    "CREATE UNIQUE INDEX IF NOT EXISTS reels_media ON reels(platform, media_id)",
    "CREATE INDEX IF NOT EXISTS reels_niche_analyzed ON reels(niche, analyzed_at)",
    "CREATE INDEX IF NOT EXISTS reels_is_own ON reels(is_own)",
]

NOT_VENDOR_SQL = "(source IS NULL OR source NOT LIKE 'vendor:%')"
_TRUE = ("1", "true", "yes", "on")


class DBMissing(RuntimeError):
    pass


class MigrationError(RuntimeError):
    pass


class IngestConnection(sqlite3.Connection):
    """sqlite3.Connection that remembers what migrate() did on open."""
    migration_actions = ()


def db_path(path=None):
    return path or config.viral_db_path()


def exists(path=None):
    return config.db_readable(db_path(path))


def connect(path=None, create=False, migrate_schema=True):
    """Read-write connection (rows are sqlite3.Row). See module doc."""
    p = db_path(path)
    if not exists(p):
        if not create:
            raise DBMissing(
                f"research DB not found at {p} (VSP_VIRAL_DB). Create it with "
                f"`python3 -m vsp.ingest init-db`, or point VSP_VIRAL_DB at the "
                f"research agent's viral.db.")
        d = os.path.dirname(os.path.abspath(p))
        os.makedirs(d, exist_ok=True)
    con = sqlite3.connect(p, timeout=30, factory=IngestConnection)
    con.row_factory = sqlite3.Row
    con.db_path = os.path.abspath(p)
    if migrate_schema:
        try:
            con.migration_actions = tuple(migrate(con))
        except Exception:
            con.close()
            raise
    return con


def connect_ro(path=None):
    """Read-only connection (sqlite3.Row rows) or None if the DB is absent."""
    con = config.connect_ro(db_path(path))
    if con is not None:
        con.row_factory = sqlite3.Row
    return con


def tables(con):
    return {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}


def table_columns(con, table):
    try:
        return [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
    except sqlite3.Error:
        return []


def has_ingest_schema(con):
    """True when the reels table carries the §9 columns (any version)."""
    cols = set(table_columns(con, "reels"))
    return {"media_id", "source", "views", "is_own"} <= cols


def schema_version(con):
    try:
        if "meta" not in tables(con):
            return None
        row = con.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        return int(row[0]) if row and str(row[0]).isdigit() else None
    except sqlite3.Error:
        return None


def get_meta(con, key, default=None):
    try:
        row = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    except sqlite3.Error:
        return default
    return row[0] if row else default


def set_meta(con, key, value):
    con.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                (key, None if value is None else str(value)))


def migrate(con):
    """Bring `con` to SCHEMA_VERSION. Additive and idempotent: returns the
    list of actions performed ([] when already current). One transaction:
    a failure rolls everything back."""
    actions = []
    iso = con.isolation_level
    con.isolation_level = None            # explicit transaction around DDL
    try:
        con.execute("BEGIN IMMEDIATE")
        have = tables(con)
        for name, ddl in LEGACY_TABLES.items():
            if name not in have:
                con.execute(ddl)
                actions.append(f"created table {name}")
        cols = set(table_columns(con, "reels"))
        for name, decl in LEGACY_REELS_COLUMNS + REELS_COLUMNS + INGEST_COLUMNS:
            if name not in cols:
                con.execute(f"ALTER TABLE reels ADD COLUMN {name} {decl}")
                actions.append(f"reels +{name}")
        for name, ddl, need in NEW_TABLES:
            existed = name in have
            con.execute(ddl)
            got = set(table_columns(con, name))
            missing = [c for c in need if c not in got]
            if missing:
                raise MigrationError(
                    f"existing table {name!r} lacks columns {missing} — vsp.ingest "
                    f"needs: {ddl.split('(', 1)[1][:-1]}. Rename the old table or "
                    f"point VSP_VIRAL_DB elsewhere.")
            if not existed:
                actions.append(f"created table {name}")
            for col, decl in OPTIONAL_COLUMNS.get(name, []):
                if col not in got:
                    con.execute(f"ALTER TABLE {name} ADD COLUMN {col} {decl}")
                    if existed:
                        actions.append(f"{name} +{col}")
        dupes = con.execute(
            "SELECT platform, media_id, COUNT(*) FROM reels WHERE media_id IS NOT NULL "
            "GROUP BY 1, 2 HAVING COUNT(*) > 1 LIMIT 3").fetchall()
        if dupes:
            raise MigrationError(
                "reels has duplicate (platform, media_id) rows, e.g. "
                + ", ".join(f"{d[0]}/{d[1]}×{d[2]}" for d in dupes)
                + " — dedupe them before the unique index can be created")
        idx = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='index'")}
        for ddl in INDEXES:
            name = ddl.split(" IF NOT EXISTS ")[1].split(" ")[0]
            if name not in idx:
                con.execute(ddl)
                actions.append(f"created index {name}")
        current = schema_version(con)
        if current is None or current < SCHEMA_VERSION:
            set_meta(con, "schema_version", SCHEMA_VERSION)
            set_meta(con, "migrated_at", sql_ts())
            actions.append(f"schema_version {current} -> {SCHEMA_VERSION}")
        con.execute("COMMIT")
    except Exception:
        try:
            con.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        con.isolation_level = iso
    return actions


def init_db(path=None):
    """Create (if absent) and migrate. -> (path, created, actions)."""
    p = db_path(path)
    created = not exists(p)
    con = connect(p, create=True)
    try:
        return p, created, list(getattr(con, "migration_actions", []))
    finally:
        con.close()


# ------------------------------------------------------------ vendor policy
def exclude_vendor(cfg=None, env=None):
    """True when vendor:* rows must be ignored (VSP_EXCLUDE_VENDOR=1 or
    config "vendor_rows": "exclude")."""
    e = os.environ if env is None else env
    if str(e.get("VSP_EXCLUDE_VENDOR", "")).strip().lower() in _TRUE:
        return True
    return bool(cfg) and str(cfg.get("vendor_rows", "include")).lower() == "exclude"


def is_vendor(source):
    return bool(source) and str(source).lower().startswith("vendor:")
