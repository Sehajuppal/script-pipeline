#!/usr/bin/env python3
"""RULES.md <-> code coverage report (automates RULES.md D60: a rule is a
draft until it is code-traceable).

    python3 tools/rule_coverage.py                 # write docs/RULE-COVERAGE.md
    python3 tools/rule_coverage.py --check         # exit 1 on a D60 violation
    python3 tools/rule_coverage.py --json -        # JSON summary to stdout
    python3 tools/rule_coverage.py --tree DIR --no-write   # another checkout

Definitions parsed from RULES.md: bullets "- D17. TITLE…", "- D17b. …",
"- **D63 TITLE**: …", "- B4a. …" (every D-number and every lettered
sub-id such as B4a; the
duplicated letter series A1/B1/… are section-local and not tracked) and
headings "### D105 TITLE" (upper-case title; "### D58 repairs (no new rule
number…)" is a note, not a definition).

Every .py file in the tree (this tool excluded) is scanned for word-boundary
tokens. Classes, first match wins:
  GATE      covered by a vsp.rules REGISTRY rule (Rule.covers); trees without
            vsp/rules.py fall back to "token appears in vsp/gates.py"
  MAKER     token in viral_script_maker.py
  SHOTLIST  token in make_shotlist.py
  PIPELINE  token in any other .py (pipeline.py, vsp/*, research_bridge.py,
            evals/*, tools/*)
  DOC-ONLY  no code hit

--check (D60) fails when a rule RULES.md §66 or §68 (CHECKED_SECTIONS: the
pipeline v2 and v2.1 entries) marks as enforced has no code hit, when such a
rule said to be enforced in "gate 1"/"gate 2" (or listed under "Existing
rules made gate-enforced") is not in the REGISTRY, or when a tracked id is
defined twice. Entries marked "PENDING INTEGRATION" are reported, not
failed (and flagged once they become code-traceable).
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TREE = os.path.dirname(HERE)
SELF = os.path.abspath(__file__)

DEF_BULLET = re.compile(r"^\s*[-*]\s+((?:D\d+[a-z]?)|(?:[A-Z]\d+[a-z]))\.\s+(.*)")
# "- **D63 SPOKEN VOICE, NOT WRITTEN VOICE**: ..." (cycle-32-era bold form)
DEF_BOLD = re.compile(r"^\s*[-*]\s+\*\*(D\d+[a-z]?)[.:]?\s+([A-Z][^*]{3,})\*\*")
DEF_HEADING = re.compile(r"^#{2,4}\s+(D\d+[a-z]?)\s+([A-Z][A-Z0-9 /+'’&:,()-]{3,}.*)")
SECTION = re.compile(r"^##\s+(.+?)\s*$")
CLASSES = ("GATE", "MAKER", "SHOTLIST", "PIPELINE", "DOC-ONLY")

# code-tag aliases the rulebook documents (RULES.md §66 housekeeping)
ALIASES = [
    ("D47", "viral_script_maker.py", "maker comments tagged 'D47 (judge loop, "
     "cycle 13)' mean RULES D51 (routine class); RULES D47 = shot-scale "
     "rotation (gate 2)"),
    ("D75", "vsp/selftest_cases.py", "the gap-in-timeline self-test comment "
     "'D75' is the old number of D78 (dead-air gap)"),
]


def _sort_key(rid):
    m = re.match(r"([A-Z])(\d+)([a-z]?)", rid)
    return (m.group(1) != "D", m.group(1), int(m.group(2)), m.group(3))


def parse_rules(path):
    """-> (defs {id: {section, title, line}}, duplicates [(id, line)])"""
    defs, dups = {}, []
    section = ""
    in_fence = False
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if line.startswith("```"):
                in_fence = not in_fence
            if in_fence:
                continue
            m = SECTION.match(line)
            if m and not line.startswith("###"):
                section = m.group(1)[:60]
            m = (DEF_BULLET.match(line) or DEF_BOLD.match(line)
                 or DEF_HEADING.match(line))
            if not m:
                continue
            rid, rest = m.group(1), m.group(2)
            title = re.split(r":\s|\.\s| \(|\*\*", rest.strip(), 1)[0]
            title = title.strip(" *:")[:70]
            if rid in defs:
                dups.append((rid, n))
                continue
            defs[rid] = {"section": section, "title": title, "line": n}
    return defs, dups


# RULES.md sections whose entries carry "Enforced in:" / "Verification:" and
# are held to D60 by --check: §66 (pipeline v2) and §68 (v2.1 creative layer)
CHECKED_SECTIONS = ("66", "68")


def section66(path, num="66"):
    """Parse RULES.md §66 (or §<num>) -> {"entries": {id: enforced_text},
    "gate_listed": [ids under 'Existing rules made gate-enforced']}"""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"^## §%s\b.*?(?=^## (?!#)|\Z)" % re.escape(num), text,
                  re.M | re.S)
    out = {"entries": {}, "gate_listed": [], "present": bool(m)}
    if not m:
        return out
    body = m.group(0)
    for em in re.finditer(r"^- (D\d+[a-z]?)\.\s(.*?)(?=^- |^### |\Z)", body,
                          re.M | re.S):
        e = re.search(r"Enforced in:(.*?)(?:\n\s*Verification:|\Z)", em.group(2),
                      re.S)
        if e:
            out["entries"][em.group(1)] = " ".join(e.group(1).split())
    gm = re.search(r"^### Existing rules made gate-enforced.*?(?=^### |\Z)",
                   body, re.M | re.S)
    if gm:
        out["gate_listed"] = re.findall(r"^- (D\d+[a-z]?)\b", gm.group(0), re.M)
    return out


def py_files(tree):
    out = []
    for dp, dns, fns in os.walk(tree):
        dns[:] = sorted(d for d in dns if not d.startswith(".")
                        and d not in ("__pycache__", "outputs", "results"))
        for fn in sorted(fns):
            p = os.path.join(dp, fn)
            if fn.endswith(".py") and os.path.abspath(p) != SELF:
                out.append(p)
    return out


def code_hits(tree, ids):
    """{id: {relpath: count}} for word-boundary tokens (D17 never matches
    D17b; D1 never matches D10)."""
    hits = {i: {} for i in ids}
    rx = re.compile(r"(?<![A-Za-z0-9])(" + "|".join(
        sorted(map(re.escape, ids), key=len, reverse=True)) + r")(?![A-Za-z0-9])")
    for p in py_files(tree):
        rel = os.path.relpath(p, tree)
        with open(p, encoding="utf-8", errors="replace") as f:
            for tok in rx.findall(f.read()):
                hits[tok][rel] = hits[tok].get(rel, 0) + 1
    return hits


def registry_covers(tree):
    """-> (set of covered ids, source) — REGISTRY coverage, or the pre-v2
    fallback (tokens in vsp/gates.py)."""
    if os.path.isfile(os.path.join(tree, "vsp", "rules.py")):
        sys.path.insert(0, tree)
        try:
            for k in [k for k in sys.modules if k == "vsp" or k.startswith("vsp.")]:
                del sys.modules[k]
            from vsp import rules
            cov = set()
            for r in rules.REGISTRY:
                cov |= set(rules.covers(r))
            return cov, "vsp.rules.REGISTRY"
        finally:
            sys.path.remove(tree)
    g = os.path.join(tree, "vsp", "gates.py")
    if not os.path.isfile(g):
        g = os.path.join(tree, "pipeline.py")
    toks = set(re.findall(r"(?<![A-Za-z0-9])([A-Z]\d+[a-z]?)(?![A-Za-z0-9])",
                          open(g, encoding="utf-8").read()))
    return toks, f"tokens in {os.path.relpath(g, tree)} (pre-registry tree)"


def classify(rid, hits, covered):
    files = hits.get(rid) or {}
    if rid in covered:
        return "GATE"
    if "viral_script_maker.py" in files:
        return "MAKER"
    if "make_shotlist.py" in files:
        return "SHOTLIST"
    if files:
        return "PIPELINE"
    return "DOC-ONLY"


def analyze(tree):
    rules_md = os.path.join(tree, "RULES.md")
    defs, dups = parse_rules(rules_md)
    ids = sorted(defs, key=_sort_key)
    hits = code_hits(tree, ids)
    covered, cov_src = registry_covers(tree)
    rows = []
    for rid in ids:
        rows.append({"id": rid, "class": classify(rid, hits, covered),
                     "section": defs[rid]["section"],
                     "title": defs[rid]["title"], "line": defs[rid]["line"],
                     "files": dict(sorted(hits[rid].items()))})
    counts = {c: sum(1 for r in rows if r["class"] == c) for c in CLASSES}
    base = [r for r in rows if re.fullmatch(r"D\d+", r["id"])]
    counts_d = {c: sum(1 for r in base if r["class"] == c) for c in CLASSES}
    sections = {num: section66(rules_md, num) for num in CHECKED_SECTIONS}
    s66 = sections["66"]
    problems, pending, notices = [], [], []
    by_id = {r["id"]: r for r in rows}
    for num, sec in sections.items():
        for rid, enf in sorted(sec["entries"].items(),
                               key=lambda kv: _sort_key(kv[0])):
            r = by_id.get(rid)
            if r is None:
                problems.append(f"{rid}: listed in §{num} but not parsed as a "
                                f"definition")
                continue
            is_pending = "PENDING INTEGRATION" in enf
            head = enf.split("gated by")[0]
            wants_gate = bool(re.search(r"\bgate [12]\b", head))
            if is_pending:
                (notices if r["files"] else pending).append(
                    f"{rid}: code-traceable now — drop 'PENDING INTEGRATION' "
                    f"from RULES.md §{num}" if r["files"] else
                    f"{rid}: pending integration — "
                    f"{head.replace('— PENDING INTEGRATION', '').strip(' .')[:70]}")
                continue
            if not r["files"]:
                problems.append(f"{rid}: §{num} says enforced ({head.strip()[:60]}) "
                                f"but no code references it (D60)")
            elif wants_gate and r["class"] != "GATE":
                problems.append(f"{rid}: §{num} says gate-enforced but no "
                                f"REGISTRY rule covers it")
        for rid in sec["gate_listed"]:
            if by_id.get(rid, {}).get("class") != "GATE":
                problems.append(f"{rid}: listed as made gate-enforced in §{num} "
                                f"but no REGISTRY rule covers it")
    for rid, n in dups:
        problems.append(f"{rid}: defined twice (RULES.md line {n})")
    return {"tree": os.path.abspath(tree), "rules_md": rules_md,
            "gate_source": cov_src, "total": len(rows), "counts": counts,
            "counts_d_numbers": counts_d, "d_numbers": len(base),
            "rows": rows, "section66": s66, "section68": sections["68"],
            "problems": problems,
            "pending": pending, "notices": notices,
            "aliases": [{"id": a, "file": f, "note": n} for a, f, n in ALIASES]}


def summary(res):
    return {"total": res["total"], "counts": res["counts"],
            "d_numbers": res["d_numbers"],
            "counts_d_numbers": res["counts_d_numbers"],
            "gate_source": res["gate_source"],
            "gate": [r["id"] for r in res["rows"] if r["class"] == "GATE"],
            "doc_only": [r["id"] for r in res["rows"] if r["class"] == "DOC-ONLY"],
            "problems": res["problems"], "pending": res["pending"],
            "notices": res["notices"]}


def render_md(res):
    c, cd = res["counts"], res["counts_d_numbers"]
    L = ["# Rule coverage — RULES.md ↔ code",
         "",
         "Generated by `python3 tools/rule_coverage.py` — do not edit by hand. "
         "Classes (first match wins): **GATE** = covered by a "
         "`vsp.rules.REGISTRY` rule; **MAKER** = referenced in "
         "viral_script_maker.py; **SHOTLIST** = make_shotlist.py; "
         "**PIPELINE** = any other code (pipeline.py, vsp/, research_bridge.py, "
         "evals/, tools/); **DOC-ONLY** = no code reference (a draft per D60). "
         f"Gate source: {res['gate_source']}.",
         "",
         "| class | all tracked ids | D-numbers only |",
         "|---|---|---|"]
    for k in CLASSES:
        L.append(f"| {k} | {c[k]} | {cd[k]} |")
    L.append(f"| **total** | **{res['total']}** | **{res['d_numbers']}** |")
    L += ["", "Tracked ids: every D-number plus lettered sub-ids (D17b, D89b, "
          "D90b, B4a). The section-local letter series (A1–A7, B1–B20, …) "
          "are defined twice in RULES.md and are not tracked.", ""]
    if res["problems"]:
        L += ["## D60 problems (`--check` fails)", ""]
        L += [f"- {p}" for p in res["problems"]] + [""]
    if res["pending"] or res["notices"]:
        L += ["## §66 pending integration", ""]
        L += [f"- {p}" for p in res["pending"] + res["notices"]] + [""]
    L += ["## Code-tag aliases", ""]
    L += [f"- `{a['id']}` in {a['file']}: {a['note']}" for a in res["aliases"]]
    L += ["", "## All rules", "", "| id | class | title | section | code references |",
          "|---|---|---|---|---|"]
    for r in res["rows"]:
        refs = ", ".join(f"{f}×{n}" for f, n in r["files"].items()) or "—"
        title = r["title"].replace("|", "/")
        sec = r["section"].replace("|", "/")
        sec = sec if len(sec) <= 48 else sec[:47] + "…"
        L.append(f"| {r['id']} | {r['class']} | {title} | {sec} | {refs} |")
    L += ["", "## JSON summary", "", "```json",
          json.dumps(summary(res), indent=1, ensure_ascii=False), "```", ""]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--tree", default=DEFAULT_TREE,
                    help="checkout to analyze (default: this repo)")
    ap.add_argument("--out", default=None,
                    help="markdown report path (default <tree>/docs/RULE-COVERAGE.md)")
    ap.add_argument("--json", default=None,
                    help="also write the JSON summary to PATH ('-' = stdout)")
    ap.add_argument("--no-write", action="store_true",
                    help="do not write the markdown report")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 on any D60 problem")
    a = ap.parse_args(argv)
    res = analyze(a.tree)
    if not a.no_write:
        out = a.out or os.path.join(a.tree, "docs", "RULE-COVERAGE.md")
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(render_md(res))
    if a.json:
        js = json.dumps(summary(res), indent=1, ensure_ascii=False)
        if a.json == "-":
            print(js)
        else:
            with open(a.json, "w", encoding="utf-8") as f:
                f.write(js + "\n")
    c = res["counts_d_numbers"]
    print(f"rule coverage: {res['total']} tracked ids ({res['d_numbers']} "
          f"D-numbers): " + " / ".join(f"{k} {res['counts'][k]}" for k in CLASSES)
          + f"  [D-numbers: " + " / ".join(f"{k} {c[k]}" for k in CLASSES) + "]",
          file=sys.stderr)
    for p in res["pending"] + res["notices"]:
        print(f"  pending: {p}", file=sys.stderr)
    for p in res["problems"]:
        print(f"  PROBLEM: {p}", file=sys.stderr)
    if a.check and res["problems"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
