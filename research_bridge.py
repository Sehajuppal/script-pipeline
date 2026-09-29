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
"""
import json, os, re, sqlite3, sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from vsp import config  # noqa: E402  (VSP_VIRAL_DB / VSP_RESEARCH_PACK / VSP_DOSSIER_DIR)

PACK_PATH = config.research_pack_path()
DB_PATH = config.viral_db_path()
DOSSIERS = config.dossier_paths()
SCHEMA_VERSION = 2

WARNINGS = []   # per-build query warnings (reset by build_pack)


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


def db_connect():
    # read-only; a missing or 0-byte DB is "absent" (never created here)
    try:
        return config.connect_ro(DB_PATH)
    except sqlite3.Error as e:
        _warn(f"cannot open research DB {DB_PATH}: {e}")
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


def build_pack():
    del WARNINGS[:]
    pack = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "schema_version": SCHEMA_VERSION,
            "sources": {}}
    con = db_connect()
    if con:
        try:
            pack["reels_total"] = _guard(
                "reels_total",
                lambda: con.execute("SELECT COUNT(*) FROM reels").fetchone()[0], 0)
            pack["reels_analyzed_last_7d"] = _guard(
                "reels_analyzed_last_7d",
                lambda: con.execute("SELECT COUNT(*) FROM reels WHERE analyzed_at "
                                    ">= datetime('now','-7 days')").fetchone()[0], 0)
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
            pack["fresh_hook_lines"] = _guard("fresh_hook_lines",
                                              lambda: fresh_hook_lines(con), [])
            pack["sources"]["viral_db"] = DB_PATH
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
    for key, path in DOSSIERS.items():
        for r in verified_rules(path):
            r["dossier"] = key
            pack["verified_rules"].append(r)
        pack["sources"][f"dossier_{key}"] = path
    if WARNINGS:
        pack["warnings"] = list(WARNINGS)
    return pack

def refresh(force=False):
    pack = build_pack()
    # pipeline v2: a host without the DB used to overwrite the last good pack
    # with an empty one (reels_total 0, no rankings) — the maker then ran on
    # nothing. Keep the last good pack unless --force.
    if not pack.get("reels_total") and os.path.exists(PACK_PATH) and not force:
        print(f"refresh skipped: research DB unavailable at {DB_PATH}; kept "
              f"{PACK_PATH} (use --force to overwrite with an empty pack)",
              file=sys.stderr)
        return 1
    tmp = PACK_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:   # atomic write
        json.dump(pack, f, indent=1)
    os.replace(tmp, PACK_PATH)
    print(f"pack written: {PACK_PATH} "
          f"({pack.get('reels_total', 0)} reels, "
          f"{len(pack['verified_rules'])} verified rules"
          + (f", {len(pack['warnings'])} warnings" if pack.get("warnings") else "")
          + ")")
    return 0

def load_pack():
    if os.path.exists(PACK_PATH):
        try:
            with open(PACK_PATH, encoding="utf-8") as f:
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
