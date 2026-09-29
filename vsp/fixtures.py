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


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "fixture-viral.db"
    print(build_fixture_db(out))
