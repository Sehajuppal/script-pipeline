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
"""
import json, os, re, sqlite3, sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
PACK_PATH = os.path.join(HERE, "research_pack.json")
DB_PATH = os.path.expanduser("~/workspace/viral-research/viral.db")
DOSSIERS = {
    "ugc": os.path.expanduser("~/workspace/goals/neuro-ad-research-program/files/ugc-persuasion-dossier.md"),
    "persona": os.path.expanduser("~/workspace/goals/neuro-ad-research-program/files/ai-persona-persuasion-dossier.md"),
}

def db_connect():
    if not os.path.exists(DB_PATH):
        return None
    return sqlite3.connect(DB_PATH)

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

def verified_rules(path, limit=25):
    """First sentence of each bullet under **VERIFIED** grade headers,
    tagged with the nearest ## question header as topic."""
    if not os.path.exists(path):
        return []
    text = open(path, encoding="utf-8", errors="replace").read().splitlines()
    topic, in_verified, rules = "general", False, []
    for line in text:
        if line.startswith("## "):
            topic = line[3:].strip()[:80]
            in_verified = False
        elif line.strip() == "**VERIFIED**":
            in_verified = True
        elif in_verified and line.startswith("- **") and len(rules) < limit:
            first = re.split(r"\.\s", line[4:].strip(), 1)[0].strip()
            first = re.sub(r"\*+", "", first)
            if len(first) > 40:
                rules.append({"topic": topic, "rule": first[:280]})
        elif in_verified and line.startswith("**") and line.strip() != "**VERIFIED**":
            in_verified = False
    return rules

def build_pack():
    pack = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sources": {}}
    con = db_connect()
    if con:
        pack["reels_total"] = con.execute("SELECT COUNT(*) FROM reels").fetchone()[0]
        pack["reels_analyzed_last_7d"] = con.execute(
            "SELECT COUNT(*) FROM reels WHERE analyzed_at >= datetime('now','-7 days')").fetchone()[0]
        pack["top_hooks"] = hook_rankings(con)
        pack["top_patterns"] = pattern_rankings(con)
        pack["niche_hooks"] = {n: hook_rankings(con, niche=n, limit=3)
                               for (n,) in con.execute(
                                   "SELECT DISTINCT niche FROM reels WHERE niche IS NOT NULL")}
        pack["fresh_hook_lines"] = fresh_hook_lines(con)
        pack["sources"]["viral_db"] = DB_PATH
        con.close()
    else:
        pack["reels_total"] = 0
    pack["verified_rules"] = []
    for key, path in DOSSIERS.items():
        for r in verified_rules(path):
            r["dossier"] = key
            pack["verified_rules"].append(r)
        pack["sources"][f"dossier_{key}"] = path
    return pack

def refresh():
    pack = build_pack()
    with open(PACK_PATH, "w") as f:
        json.dump(pack, f, indent=1)
    print(f"pack written: {PACK_PATH} "
          f"({pack.get('reels_total', 0)} reels, "
          f"{len(pack['verified_rules'])} verified rules)")

def load_pack():
    if os.path.exists(PACK_PATH):
        try:
            return json.load(open(PACK_PATH))
        except Exception:
            return None
    return None

if __name__ == "__main__":
    if "--refresh" in sys.argv:
        refresh()
    elif "--json" in sys.argv:
        print(json.dumps(load_pack() or build_pack(), indent=1))
    else:
        print("usage: research_bridge.py [--refresh | --json]")
