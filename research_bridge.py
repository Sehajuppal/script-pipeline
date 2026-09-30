#!/usr/bin/env python3
"""RESEARCH BRIDGE — connects the script maker to the daily viral-reel research.

Sources (all "mind-connected" files):
  1. viral-content research DB (~/workspace/viral-research/viral.db) — the
     reels the research agent dissects daily: hook categories, patterns,
     fresh hook lines, per-niche rankings.
  2. UGC persuasion dossier — VERIFIED findings only.
  3. AI-persona persuasion dossier — VERIFIED findings only.
  4. Hooks mastery playbook — hook families and stack grammar.

Emits a cached research pack (research_pack.json) the script maker loads on
every run, so scripts always ride the latest research, not a frozen rulebook.

Usage:
  python3 research_bridge.py --refresh     # rebuild the pack (daily cron)
  python3 research_bridge.py --json        # print the pack

Pipeline v2 hardening (RULES.md §66 D148):
  * every DB query is guarded: a schema mismatch (sqlite3.OperationalError,
    e.g. a renamed column) warns on stderr, is recorded in the pack's
    "warnings", and the build continues with the other queries;
  * the dossier sentence splitter no longer cuts at "et al.", "Int.",
    "e.g.", "i.e.", "vs." or initials, and reads the bold lead sentence;
  * alternative grade headers are tolerated ("**Grade: VERIFIED**",
    "VERIFIED:", "### VERIFIED", ...);
  * packs carry "schema_version": 2 and a "niche_map" (maker niche -> the
    research niches present in this DB); every v1 key is kept;
  * --refresh keeps the last good pack when the DB is unavailable (unless
    --force) and writes atomically. Validate with vsp.research.load_pack.

Ingested Instagram data (WS-DATA, vsp.ingest; research doc §9) — only when
the reels table carries the ingest columns (media_id, source, views,
is_own), so a legacy research-agent DB builds exactly the pack it always
did:
  * fresh_hook_lines are ranked by views, falling back to likes (rows with
    views first, then by likes, then newest), drawn from reels analyzed in
    the last 7 days in EVERY niche (up to FRESH_PER_NICHE each, plus the
    legacy newest-15), deduped by hook text; entries keep hook / niche /
    likes / account / pattern and add views / url / source / hook_source /
    posted_at. Caption-derived hooks must be >= 3 words and not a bare CTA;
  * "top_reels": {niche: [{url, views, likes, hook_text, account, source,
    hook_category, posted_at}]} — up to TOP_REELS_PER_NICHE per niche;
  * your own reels (is_own=1) never feed the research rankings, and vendor:*
    rows are dropped when VSP_EXCLUDE_VENDOR=1 or config/ingest.json says
    "vendor_rows": "exclude" (the hooks/patterns aggregates follow the same
    setting when `python3 -m vsp.ingest classify` rebuilds them);
  * "ingest": {"by_source": {...}, "vendor_rows_excluded": bool}.
Every legacy key is kept; schema_version stays 2 (vsp.research validates
1..2). Paths are resolved when a function runs (env VSP_VIRAL_DB /
VSP_RESEARCH_PACK / VSP_DOSSIER_DIR at call time, or an explicit argument);
PACK_PATH / DB_PATH / DOSSIERS keep their import-time values for readers,
and assigning them still redirects the functions (old monkeypatch style).
"""
import json, os, re, sqlite3, sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from vsp import config  # noqa: E402  (VSP_VIRAL_DB / VSP_RESEARCH_PACK / VSP_DOSSIER_DIR)

PACK_PATH = config.research_pack_path()
DB_PATH = config.viral_db_path()
DOSSIERS = config.dossier_paths()
_IMPORT_PATHS = (PACK_PATH, DB_PATH, dict(DOSSIERS))
SCHEMA_VERSION = 2
FRESH_LEGACY = 15            # the pre-ingest list: newest 15 hook lines
FRESH_PER_NICHE = 5
FRESH_MAX = 120
TOP_REELS_PER_NICHE = 5

WARNINGS = []   # per-build query warnings (reset by build_pack)


def pack_path():
    """Where refresh() writes: an assigned PACK_PATH, else VSP_RESEARCH_PACK
    (or <repo>/research_pack.json) as of NOW."""
    return PACK_PATH if PACK_PATH != _IMPORT_PATHS[0] else config.research_pack_path()


def db_path():
    return DB_PATH if DB_PATH != _IMPORT_PATHS[1] else config.viral_db_path()


def dossier_paths():
    return DOSSIERS if DOSSIERS != _IMPORT_PATHS[2] else config.dossier_paths()


def _warn(msg):
    if msg in WARNINGS:          # one line per distinct problem
        return
    WARNINGS.append(msg)
    print(f"research_bridge: warning: {msg}", file=sys.stderr)


def _guard(label, fn, default):
    """Run one DB query; a schema mismatch warns and yields `default`."""
    try:
        return fn()
    except sqlite3.OperationalError as e:
        _warn(f"{label}: query failed ({e}) — schema mismatch? skipped")
    except sqlite3.DatabaseError as e:
        _warn(f"{label}: database error ({e}) — skipped")
    return default


def db_connect(path=None):
    # read-only; a missing or 0-byte DB is "absent" (never created here)
    p = path or db_path()
    try:
        return config.connect_ro(p)
    except sqlite3.Error as e:
        _warn(f"cannot open research DB {p}: {e}")
        return None

def hook_rankings(con, niche=None, limit=8):
    q = ("SELECT hook_category, SUM(times_seen) s FROM hooks "
         + ("WHERE niche = ? " if niche else "")
         + "GROUP BY 1 ORDER BY s DESC LIMIT ?")
    args = ([niche, limit] if niche else [limit])
    return [{"category": r[0], "times_seen": r[1]}
            for r in con.execute(q, args) if r[0]]

def pattern_rankings(con, niche=None, limit=8):
    q = ("SELECT pattern_name, SUM(times_seen) s FROM patterns "
         + ("WHERE niche = ? " if niche else "")
         + "GROUP BY 1 ORDER BY s DESC LIMIT ?")
    args = ([niche, limit] if niche else [limit])
    return [{"pattern": r[0], "times_seen": r[1]}
            for r in con.execute(q, args) if r[0]]

def fresh_hook_lines(con, limit=15):
    rows = con.execute(
        """SELECT r.hook_text, r.niche, r.like_count, r.username, p.pattern_name
           FROM reels r LEFT JOIN patterns p ON p.pattern_id = r.pattern_id
           WHERE r.hook_text IS NOT NULL AND r.hook_text != ''
           ORDER BY r.analyzed_at DESC LIMIT ?""", [limit])
    return [{"hook": r[0][:140], "niche": r[1], "likes": r[2],
             "account": r[3], "pattern": r[4]} for r in rows]


# ------------------------------------------------ ingested data (vsp.ingest)
def has_ingest_columns(con):
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(reels)")}
    except sqlite3.Error:
        return False
    return {"media_id", "source", "views", "is_own"} <= cols


def exclude_vendor():
    """VSP_EXCLUDE_VENDOR=1 or config/ingest.json "vendor_rows": "exclude"."""
    try:
        from vsp.ingest.db import exclude_vendor as _ex
        from vsp.ingest.settings import ConfigError, load
        try:
            cfg = load(required=False)
        except ConfigError:
            cfg = None
        return _ex(cfg)
    except Exception:  # noqa: BLE001 — vsp.ingest absent: env only
        return os.environ.get("VSP_EXCLUDE_VENDOR", "").strip().lower() in (
            "1", "true", "yes", "on")


def _sql_ts(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


_CTA_ONLY = re.compile(
    r"^(?:link in (?:my )?bio|follow (?:me |us )?for (?:more|part)|new (?:drop|video|"
    r"post|reel)|part \d+|shop now|swipe|tap (?:the )?link|out now|comment below|"
    r"save (?:this|for later)|giveaway|sale|available now)\b", re.I)


def _usable_caption_hook(text):
    """Caption-derived hooks: >= 3 words and not a bare CTA."""
    t = (text or "").strip()
    return len(re.findall(r"[A-Za-z0-9']+", t)) >= 3 and not _CTA_ONLY.match(t)


def _research_where(vendor_excluded, alias="r"):
    w = f"COALESCE({alias}.is_own, 0) = 0"
    if vendor_excluded:
        w += f" AND ({alias}.source IS NULL OR {alias}.source NOT LIKE 'vendor:%')"
    return w


_RANK = ("ORDER BY (r.views IS NULL), r.views DESC, (r.like_count IS NULL), "
         "r.like_count DESC, r.analyzed_at DESC, r.id DESC")


def ranked_hook_lines(con, since, per_niche=FRESH_PER_NICHE, legacy=FRESH_LEGACY,
                      limit=FRESH_MAX, vendor_excluded=False):
    """fresh_hook_lines for an ingest-schema DB (see module doc)."""
    where = _research_where(vendor_excluded)
    cols = ("r.hook_text, r.niche, r.like_count, r.username, p.pattern_name, r.views, "
            "r.url, r.source, r.hook_source, r.posted_at, r.analyzed_at, r.id")
    base = (f"SELECT {cols} FROM reels r LEFT JOIN patterns p ON p.pattern_id = "
            f"r.pattern_id WHERE r.hook_text IS NOT NULL AND r.hook_text != '' "
            f"AND {where}")
    newest = con.execute(base + " ORDER BY r.analyzed_at DESC LIMIT ?",
                         [legacy]).fetchall()
    fresh = con.execute(base + " AND r.analyzed_at >= ? " + _RANK, [since]).fetchall()
    per, picked = {}, []
    for r in fresh:
        if r[8] == "caption" and not _usable_caption_hook(r[0]):
            continue
        if per.get(r[1], 0) >= per_niche:
            continue
        per[r[1]] = per.get(r[1], 0) + 1
        picked.append(r)
    out, seen = [], set()
    rows = list({tuple(r) for r in picked} | {tuple(r) for r in newest})
    rows.sort(key=lambda r: (str(r[10] or ""), r[11]), reverse=True)     # newest first
    rows.sort(key=lambda r: (r[5] is None, -(r[5] or 0),                 # then views,
                             r[2] is None, -(r[2] or 0)))                # then likes
    for r in rows:
        k = " ".join(r[0].lower().split())
        if k in seen:
            continue
        seen.add(k)
        out.append({"hook": r[0][:140], "niche": r[1], "likes": r[2], "account": r[3],
                    "pattern": r[4], "views": r[5], "url": r[6], "source": r[7],
                    "hook_source": r[8], "posted_at": r[9]})
        if len(out) >= limit:
            break
    return out


def top_reels(con, since, per_niche=TOP_REELS_PER_NICHE, vendor_excluded=False):
    """{niche: [{url, views, likes, hook_text, account, source, hook_category,
    posted_at}]} ranked by views, falling back to likes."""
    where = _research_where(vendor_excluded)
    rows = con.execute(
        "SELECT r.niche, r.url, r.views, r.like_count, r.hook_text, r.username, "
        "r.source, r.hook_category, r.posted_at FROM reels r WHERE r.niche IS NOT NULL "
        "AND r.url IS NOT NULL AND r.url != '' AND r.analyzed_at >= ? AND " + where +
        " " + _RANK, [since]).fetchall()
    out = {}
    for r in rows:
        lst = out.setdefault(r[0], [])
        if len(lst) < per_niche:
            lst.append({"url": r[1], "views": r[2], "likes": r[3],
                        "hook_text": (r[4] or "")[:140] or None, "account": r[5],
                        "source": r[6], "hook_category": r[7], "posted_at": r[8]})
    return out


def ingest_summary(con, vendor_excluded):
    return {"by_source": {(s or "legacy"): n for s, n in con.execute(
                "SELECT source, COUNT(*) FROM reels GROUP BY 1 ORDER BY 2 DESC")},
            "own_reels": con.execute("SELECT COUNT(*) FROM reels WHERE "
                                     "COALESCE(is_own, 0) = 1").fetchone()[0],
            "vendor_rows_excluded": bool(vendor_excluded)}


# ------------------------------------------------------------ dossiers
# tokens that end in "." without ending a sentence (lower-cased, no dot)
_ABBREV = {"al", "int", "e.g", "i.e", "eg", "ie", "vs", "cf", "fig", "figs",
           "no", "nos", "vol", "vols", "pp", "ed", "eds", "dr", "mr", "mrs",
           "ms", "prof", "st", "jr", "sr", "inc", "ltd", "co", "corp",
           "approx", "ca", "dept", "univ", "jan", "feb", "mar", "apr", "jun",
           "jul", "aug", "sep", "sept", "oct", "nov", "dec", "u.s", "u.k",
           "e.u", "rev", "psychol", "res", "consum", "commun", "soc", "pers",
           "appl", "exp", "advert", "mark", "j"}


def first_sentence(text):
    """First sentence of `text`, abbreviation-aware: never splits at
    "et al.", "Int.", "e.g.", "i.e.", "vs.", or initials ("J. Smith")."""
    t = " ".join((text or "").split())
    for m in re.finditer(r"[.!?](?=\s+|$)", t):
        end = m.end()
        before = t[:m.start()]
        tok = re.search(r"([A-Za-z][A-Za-z.]*)$", before)
        word = tok.group(1).lower() if tok else ""
        if m.group(0) == "." and word:
            if word in _ABBREV or word.rstrip(".") in _ABBREV:
                continue
            if len(word) == 1 and word.isalpha():        # an initial: "J."
                continue
            if re.fullmatch(r"(?:[a-z]\.)+[a-z]", word):  # "e.g", "u.s"
                continue
        nxt = t[end:].lstrip()
        if nxt and nxt[0].islower():                     # "vs. the", "approx. 3"
            continue
        return t[:end].strip()
    return t.strip()


_GRADES = ("VERIFIED", "CONTESTED", "INFERENCE", "STRUCK", "KILLED",
           "UNVERIFIED", "PLAUSIBLE", "MIXED", "WEAK", "REJECTED", "PENDING")
_GRADE_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?[*_]{0,3}\s*"
    r"(?:(?:evidence\s+)?grade\s*[:\-\u2013\u2014]?\s*)?"
    r"(" + "|".join(_GRADES) + r")\b[\s*_:]*(?:\([^)]*\))?[\s*_:]*$",
    re.I)


def grade_header(line):
    """'VERIFIED' / 'CONTESTED' / ... when `line` is a grade header in any
    of the accepted spellings (**VERIFIED**, **Grade: VERIFIED**,
    VERIFIED:, ### VERIFIED, ...), else None."""
    m = _GRADE_RE.match(line or "")
    return m.group(1).upper() if m else None


def verified_rules(path, limit=25):
    """First sentence of each bullet under VERIFIED grade headers,
    tagged with the nearest ## question header as topic."""
    if not os.path.exists(path):
        return []
    text = open(path, encoding="utf-8", errors="replace").read().splitlines()
    topic, in_verified, rules = "general", False, []
    for line in text:
        grade = grade_header(line)
        if grade is not None:
            in_verified = grade == "VERIFIED"
        elif line.startswith("## "):
            topic = line[3:].strip()[:80]
            in_verified = False
        elif in_verified and re.match(r"[-*] \*\*", line) and len(rules) < limit:
            body = re.sub(r"\*+", "", line[2:]).strip()
            first = first_sentence(body)
            if len(first) > 40:
                rules.append({"topic": topic, "rule": first[:280]})
        elif in_verified and line.startswith("**"):
            in_verified = False   # any other bold header closes the block
    return rules


def build_pack(now=None, db=None, dossiers=None):
    """The research pack. now (aware datetime; default: the current time)
    anchors the 7-day windows; db / dossiers override the call-time paths."""
    del WARNINGS[:]
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    week_ago = _sql_ts(now - timedelta(days=7))   # == datetime('now','-7 days')
    dbp = db or db_path()
    pack = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "schema_version": SCHEMA_VERSION,
            "sources": {}}
    con = db_connect(dbp)
    if con:
        try:
            pack["reels_total"] = _guard(
                "reels_total",
                lambda: con.execute("SELECT COUNT(*) FROM reels").fetchone()[0], 0)
            pack["reels_analyzed_last_7d"] = _guard(
                "reels_analyzed_last_7d",
                lambda: con.execute("SELECT COUNT(*) FROM reels WHERE analyzed_at "
                                    ">= ?", [week_ago]).fetchone()[0], 0)
            pack["top_hooks"] = _guard("top_hooks", lambda: hook_rankings(con), [])
            pack["top_patterns"] = _guard("top_patterns",
                                          lambda: pattern_rankings(con), [])
            niches = _guard("niche list", lambda: [
                n for (n,) in con.execute(
                    "SELECT DISTINCT niche FROM reels WHERE niche IS NOT NULL")], [])
            pack["niche_hooks"] = {}
            for n in niches:
                pack["niche_hooks"][n] = _guard(
                    "niche_hooks",
                    lambda n=n: hook_rankings(con, niche=n, limit=3), [])
            if _guard("ingest columns", lambda: has_ingest_columns(con), False):
                vend = exclude_vendor()
                pack["fresh_hook_lines"] = _guard(
                    "fresh_hook_lines",
                    lambda: ranked_hook_lines(con, week_ago, vendor_excluded=vend), [])
                pack["top_reels"] = _guard(
                    "top_reels", lambda: top_reels(con, week_ago, vendor_excluded=vend),
                    {})
                pack["ingest"] = _guard("ingest summary",
                                        lambda: ingest_summary(con, vend), {})
            else:
                pack["fresh_hook_lines"] = _guard("fresh_hook_lines",
                                                  lambda: fresh_hook_lines(con), [])
            pack["sources"]["viral_db"] = dbp
        finally:
            con.close()
    else:
        pack["reels_total"] = 0
    try:
        from vsp.research import build_niche_map
        pack["niche_map"] = build_niche_map(sorted(pack.get("niche_hooks") or {}))
    except Exception as e:  # noqa: BLE001 — the map is advisory
        _warn(f"niche_map not built: {e}")
        pack["niche_map"] = {}
    pack["verified_rules"] = []
    for key, path in (dossiers or dossier_paths()).items():
        for r in verified_rules(path):
            r["dossier"] = key
            pack["verified_rules"].append(r)
        pack["sources"][f"dossier_{key}"] = path
    if WARNINGS:
        pack["warnings"] = list(WARNINGS)
    return pack

def refresh(force=False, path=None, now=None, db=None):
    """Build + atomically write the pack to `path` (default: pack_path()).
    -> 0 written, 1 kept the last good pack (DB unavailable, no --force)."""
    out = path or pack_path()
    dbp = db or db_path()
    pack = build_pack(now=now, db=dbp)
    # pipeline v2: a host without the DB used to overwrite the last good pack
    # with an empty one (reels_total 0, no rankings) — the maker then ran on
    # nothing. Keep the last good pack unless --force.
    if not pack.get("reels_total") and os.path.exists(out) and not force:
        print(f"refresh skipped: research DB unavailable at {dbp}; kept "
              f"{out} (use --force to overwrite with an empty pack)",
              file=sys.stderr)
        return 1
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:   # atomic write
        json.dump(pack, f, indent=1)
    os.replace(tmp, out)
    print(f"pack written: {out} "
          f"({pack.get('reels_total', 0)} reels, "
          f"{len(pack['verified_rules'])} verified rules"
          + (f", {sum(len(v) for v in pack['top_reels'].values())} top reels"
             if pack.get("top_reels") else "")
          + (f", {len(pack['warnings'])} warnings" if pack.get("warnings") else "")
          + ")")
    return 0

def load_pack(path=None):
    p = path or pack_path()
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

if __name__ == "__main__":
    if "--refresh" in sys.argv:
        sys.exit(refresh(force="--force" in sys.argv))
    elif "--json" in sys.argv:
        print(json.dumps(load_pack() or build_pack(), indent=1))
    else:
        print("usage: research_bridge.py [--refresh | --json]")
