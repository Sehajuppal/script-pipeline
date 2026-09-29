"""Weakening guard for verify: automation may never weaken the gates, the
rule registry, the shared lexicon or the self-test — and may never touch the
yardstick. check(base_tree, cand_tree) -> (findings, evidence); any finding
REJECTs (decide R9).

What is compared (a snapshot of each tree, taken in a child process that
imports THAT tree's modules — never the engine's):
  vsp/rules.py     REGISTRY: every base (id, stage) still present, severity
                   never error -> warn, covers never shrink; LEGACY_IDS order
                   kept; the compliance rules D136-D141 present at severity
                   error in the candidate, always (automation may never
                   remove them); public module regexes (below).
  vsp/lexicon.py   every public name kept. Regexes are compared by BEHAVIOUR:
                   strings generated from the base pattern's own syntax tree
                   (every alternative, case variants) plus a fixed probe
                   corpus — each string the base matched must still match.
                   Regex lists: every base probe matched by some candidate
                   item. Deny sets (GENERIC_TAGS ...) never lose members,
                   allow sets (LABEL_WORDS) never gain any; nested/string
                   lists never lose members; limits (MAX_HASHTAGS, WPS_*,
                   SLACK) never grow; other numbers never change.
  vsp/gates.py     every g1_/g2_ check kept, LEGACY_GATE1/2 order kept,
                   public constants and regexes as for the lexicon,
                   DELIVERABLE_BLOCK never loses text.
  self-test        legacy case count never drops and every legacy case keeps
                   its (name, want_pass, want_msgs); the total case count
                   never drops, base case and unit-check names all kept.
  yardstick        evals/golden.jsonl, evals/holdout.jsonl, evals/scorecard.py
                   and vsp/rubric.py byte-identical (a human changes the
                   yardstick in its own reviewed PR, never automation).
"""
import hashlib
import json
import os
import re

from vsp.improve import common as C

ALLOW_SETS = {"LABEL_WORDS"}                    # allow-lists: growth weakens
LIMITS_UP_WEAKENS = {"MAX_HASHTAGS", "WPS_BRISK", "WPS_SLOW", "SLACK"}
COMPLIANCE = C.COMPLIANCE_RULES                  # D136..D141
PROBES = [
    # D136 social proof
    "4.9 stars", "4.9★", "5 star", "12,000+ orders", "10k reviews", "1M sold",
    "500 customers", "sold out twice", "best seller", "bestseller", "best-seller",
    # D37 prices
    "$12", "$12.99", "20 dollars", "15 bucks", "30 USD", "10 euros", "5 pounds",
    # D137 AI lived experience
    "I tried it", "I used it", "I woke up", "I slept better", "I've been using it",
    "I've tried it", "I love it", "I use this", "my skin", "my hair", "my back",
    "changed my life", "saved my mornings", "I swear by it", "I was skeptical",
    # D139 bait
    "like if you agree", "tag a friend", "tag someone", "comment yes", "type yes",
    "share this with", "double tap", "smash that", "like and subscribe", "drop a like",
    # D141 absolutes
    "guaranteed", "guarantee", "cures acne", "a miracle", "the #1 lamp", "number one",
    "the cheapest", "lowest price", "best lamp ever", "best ever", "100% effective",
    "100% safe", "risk-free", "risk free", "clinically proven",
    # slop / leaks / hooks
    "game changer", "game-changer", "you won't believe", "wait for it", "hey guys",
    "in today's video", "let's dive in", "life-changing", "must-have", "trust me",
    "D136", "playbook", "F103", "(split-screen", "85%", "sound-off", "safe zone",
    "gate 1", "nobody mentions the lamp flaw", "nobody mentions it", "this is crazy",
    "watch this", "must see", "part 2", "part two",
    # disclosure
    "made with an AI persona", "AI-generated presenter", "created with AI",
    "https://www.instagram.com/reel/FIXTURE-x-1/", "#skincare", "#fyp",
    '"AI persona" label on frame 0',
]

SNAPSHOT_CODE = r'''
import json, re, sys
tree = sys.argv[1]
sys.path.insert(0, tree)
out = {"errors": {}}
PAT = type(re.compile(""))

def pat(rx):
    return {"pattern": rx.pattern, "flags": int(rx.flags)}

def classify(mod, public_only=True):
    res = {}
    for name in sorted(vars(mod)):
        if name.startswith("__") or (public_only and name.startswith("_")):
            continue
        v = getattr(mod, name)
        try:
            if isinstance(v, PAT):
                res[name] = {"kind": "re", **pat(v)}
            elif isinstance(v, (list, tuple)) and v and all(isinstance(x, PAT) for x in v):
                res[name] = {"kind": "re_list", "items": [pat(x) for x in v]}
            elif isinstance(v, (set, frozenset)) and all(isinstance(x, str) for x in v):
                res[name] = {"kind": "set", "items": sorted(v)}
            elif isinstance(v, str):
                res[name] = {"kind": "str", "value": v}
            elif isinstance(v, (list, tuple)) and all(isinstance(x, str) for x in v):
                res[name] = {"kind": "str_list", "items": list(v)}
            elif isinstance(v, (list, tuple)) and v and all(
                    isinstance(x, (list, tuple)) and all(isinstance(y, str) for y in x) for x in v):
                res[name] = {"kind": "nested", "items": sorted(" | ".join(x) for x in v)}
            elif isinstance(v, bool):
                continue
            elif isinstance(v, (int, float)):
                res[name] = {"kind": "num", "value": v}
            elif callable(v) and getattr(v, "__module__", None) == mod.__name__:
                res[name] = {"kind": "func"}
        except Exception as e:
            res[name] = {"kind": "error", "value": repr(e)}
    return res

try:
    from vsp import lexicon as L
    out["lexicon"] = classify(L)
except Exception as e:
    out["errors"]["lexicon"] = repr(e)
try:
    from vsp import rules as R
    out["registry"] = [{"id": r.id, "stage": r.stage, "severity": r.severity,
                        "covers": list(R.covers(r))} for r in R.REGISTRY]
    out["legacy_ids"] = {k: list(v) for k, v in getattr(R, "LEGACY_IDS", {}).items()}
    out["rules_consts"] = {k: v for k, v in classify(R).items() if v["kind"] != "func"}
except Exception as e:
    out["errors"]["rules"] = repr(e)
try:
    from vsp import gates as G
    c = classify(G)
    out["gates"] = {"checks": sorted(n for n in vars(G) if re.match(r"g[12]_", n)
                                     and callable(getattr(G, n))),
                    "legacy1": [f.__name__ for f in getattr(G, "LEGACY_GATE1", ())],
                    "legacy2": [f.__name__ for f in getattr(G, "LEGACY_GATE2", ())],
                    "consts": {k: v for k, v in c.items() if v["kind"] != "func"}}
except Exception as e:
    out["errors"]["gates"] = repr(e)
try:
    from vsp import selftest_cases as S
    good, legacy = S.legacy_cases()
    _g, cases = S.all_cases()
    out["selftest"] = {"legacy": len(legacy),
                       "legacy_cases": [[c[0], bool(c[2]), list(c[3])] for c in legacy],
                       "all": len(cases), "names": [c[0] for c in cases],
                       "units": [n for n, _f in S.unit_cases()]}
except Exception as e:
    out["errors"]["selftest"] = repr(e)
print(json.dumps(out))
'''


# ---------------------------------------------------------------- snapshot
def snapshot(tree, python=None):
    py = python or C.default_python()
    r = C.run([py, "-c", SNAPSHOT_CODE, tree], cwd=tree,
              env=C.child_env({"VSP_NO_HOOK_PACKS": "1"}), timeout=300)
    if r["rc"] != 0:
        return {"errors": {"snapshot": C.tail(r["err"] or r["out"], 400)}}
    try:
        return json.loads(r["out"].strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"errors": {"snapshot": "unparseable output: " + C.tail(r["out"], 200)}}


def file_hashes(tree, files):
    out = {}
    for f in files:
        p = os.path.join(tree, f)
        out[f] = C.sha256_file(p) if os.path.isfile(p) else None
    return out


# ------------------------------------------------------- regex behaviour
def _parser():
    try:
        import re._parser as p      # 3.11+
        return p
    except ImportError:             # 3.9 / 3.10
        import sre_parse as p
        return p


_CAT = {"CATEGORY_DIGIT": "1", "CATEGORY_SPACE": " ", "CATEGORY_WORD": "a",
        "CATEGORY_NOT_DIGIT": "a", "CATEGORY_NOT_SPACE": "a", "CATEGORY_NOT_WORD": " "}
CAP = 64


def _in_char(av):
    neg = False
    for op, v in av:
        name = str(op)
        if name == "NEGATE":
            neg = True
            continue
        if neg:
            return "x" if name != "LITERAL" or chr(v) != "x" else "y"
        if name == "LITERAL":
            return chr(v)
        if name == "RANGE":
            return chr(v[0])
        if name == "CATEGORY":
            return _CAT.get(str(v), "a")
    return "x"


def _cross(a, b):
    out = [x + y for x in a for y in b]
    return out[:CAP]


def _expand(items):
    """Finite sample strings from an sre parse tree (every branch, repeats
    once — or zero times when optional)."""
    acc = [""]
    for op, av in items:
        name = str(op)
        if name == "LITERAL":
            acc = [s + chr(av) for s in acc]
        elif name == "NOT_LITERAL":
            acc = [s + ("x" if chr(av) != "x" else "y") for s in acc]
        elif name == "ANY":
            acc = [s + "x" for s in acc]
        elif name == "IN":
            acc = [s + _in_char(av) for s in acc]
        elif name == "CATEGORY":
            acc = [s + _CAT.get(str(av), "a") for s in acc]
        elif name in ("MAX_REPEAT", "MIN_REPEAT", "POSSESSIVE_REPEAT"):
            lo, _hi, sub = av
            one = _expand(sub)
            opts = one if lo <= 1 else [x * lo for x in one]
            if lo == 0:
                opts = [""] + opts
            acc = _cross(acc, opts)
        elif name in ("SUBPATTERN", "ATOMIC_GROUP"):
            sub = av[-1] if name == "SUBPATTERN" else av
            acc = _cross(acc, _expand(sub))
        elif name == "BRANCH":
            opts = []
            for alt in av[1]:
                opts += _expand(alt)
            acc = _cross(acc, opts[:CAP])
        # AT (anchors), ASSERT/ASSERT_NOT (lookarounds), GROUPREF: no text
    return acc


def regex_samples(pattern, flags=0):
    """Strings the pattern itself should match: generated from its syntax
    tree + case variants, then the fixed probe corpus; kept only if the
    pattern really matches them."""
    try:
        rx = re.compile(pattern, flags)
    except re.error:
        return []
    try:
        gen = _expand(list(_parser().parse(pattern, flags)))
    except Exception:  # noqa: BLE001 — exotic syntax: corpus only
        gen = []
    cands = []
    for s in gen:
        s = s.strip()
        if s:
            cands += [s, s.upper(), s[:1].upper() + s[1:], f"so {s} here"]
    cands += PROBES
    seen, out = set(), []
    for s in cands:
        if s not in seen and rx.search(s):
            seen.add(s)
            out.append(s)
    return out


def _lost(base_items, cand_items):
    """Samples the base patterns match that no candidate pattern matches."""
    try:
        cand_rx = [re.compile(i["pattern"], i["flags"]) for i in cand_items]
    except re.error as e:
        return [f"<candidate pattern does not compile: {e}>"]
    lost = []
    for it in base_items:
        for s in regex_samples(it["pattern"], it["flags"]):
            if not any(rx.search(s) for rx in cand_rx):
                lost.append(s)
    return sorted(set(lost))


# ----------------------------------------------------------------- compare
def compare_consts(where, base, cand):
    """Findings for one module's public constants (lexicon / gates / rules)."""
    out = []
    for name, b in sorted((base or {}).items()):
        c = (cand or {}).get(name)
        tag = f"{where}.{name}"
        if c is None:
            out.append(f"{tag} removed")
            continue
        kind = b["kind"]
        if kind == "re":
            if c["kind"] not in ("re", "re_list"):
                out.append(f"{tag} is no longer a regex")
                continue
            items = [c] if c["kind"] == "re" else c["items"]
            lost = _lost([b], items)
            if lost:
                out.append(f"{tag} no longer matches {', '.join(repr(x) for x in lost[:4])}"
                           + (f" (+{len(lost) - 4} more)" if len(lost) > 4 else ""))
        elif kind == "re_list":
            if c["kind"] not in ("re", "re_list"):
                out.append(f"{tag} is no longer a regex list")
                continue
            items = [c] if c["kind"] == "re" else c["items"]
            lost = _lost(b["items"], items)
            if lost:
                out.append(f"{tag} no longer matches {', '.join(repr(x) for x in lost[:4])}"
                           + (f" (+{len(lost) - 4} more)" if len(lost) > 4 else ""))
        elif kind == "set":
            bs, cs = set(b["items"]), set(c.get("items") or [])
            if name in ALLOW_SETS:
                if cs - bs:
                    out.append(f"{tag} (allow-list) gained {sorted(cs - bs)[:5]}")
            elif bs - cs:
                out.append(f"{tag} lost {sorted(bs - cs)[:5]}")
        elif kind in ("str_list", "nested"):
            bs, cs = set(b["items"]), set(c.get("items") or [])
            if bs - cs:
                out.append(f"{tag} lost {sorted(bs - cs)[:4]}")
        elif kind == "str":
            if c.get("kind") != "str" or b["value"] not in c.get("value", ""):
                out.append(f"{tag} changed (base text no longer contained)")
        elif kind == "num":
            bv, cv = b["value"], c.get("value")
            if not isinstance(cv, (int, float)):
                out.append(f"{tag} is no longer a number")
            elif name in LIMITS_UP_WEAKENS:
                if cv > bv:
                    out.append(f"{tag} loosened {bv} -> {cv}")
            elif cv != bv:
                out.append(f"{tag} changed {bv} -> {cv} (direction unknown)")
        elif kind == "func" and c.get("kind") != "func":
            out.append(f"{tag} is no longer a function")
    return out


def compare(base, cand):
    """Findings (weakening) between two snapshots."""
    f = []
    be, ce = base.get("errors") or {}, cand.get("errors") or {}
    for mod, err in sorted(ce.items()):
        if mod not in be:
            f.append(f"candidate cannot import {mod}: {err[:160]}")
    # registry
    breg = {(r["id"], r["stage"]): r for r in base.get("registry") or []}
    creg = {(r["id"], r["stage"]): r for r in cand.get("registry") or []}
    for key, r in sorted(breg.items()):
        c = creg.get(key)
        if c is None:
            f.append(f"rules.REGISTRY lost {key[0]} ({key[1]})")
            continue
        if r["severity"] == "error" and c["severity"] != "error":
            f.append(f"rules.REGISTRY {key[0]} downgraded error -> {c['severity']}")
        lost = set(r.get("covers") or []) - set(c.get("covers") or [])
        if lost:
            f.append(f"rules.REGISTRY {key[0]} covers lost {sorted(lost)}")
    if "registry" in cand:
        present = {r["id"] for r in cand.get("registry") or [] if r["severity"] == "error"
                   and r["stage"] == "script"}
        miss = [x for x in COMPLIANCE if x not in present]
        if miss:
            f.append(f"compliance rules missing at severity error: {', '.join(miss)} "
                     f"(automation may never remove D136–D141)")
    for stage, ids in sorted((base.get("legacy_ids") or {}).items()):
        cids = (cand.get("legacy_ids") or {}).get(stage) or []
        if list(cids[:len(ids)]) != list(ids):
            f.append(f"rules.LEGACY_IDS[{stage}] order/content changed")
    f += compare_consts("lexicon", base.get("lexicon"), cand.get("lexicon"))
    f += compare_consts("rules", base.get("rules_consts"), cand.get("rules_consts"))
    bg, cg = base.get("gates") or {}, cand.get("gates") or {}
    if bg:
        lost = sorted(set(bg.get("checks") or []) - set(cg.get("checks") or []))
        if lost:
            f.append(f"gates lost checks {lost}")
        for k in ("legacy1", "legacy2"):
            b, c = bg.get(k) or [], cg.get(k) or []
            if b and list(c[:len(b)]) != list(b):
                f.append(f"gates.{'LEGACY_GATE1' if k == 'legacy1' else 'LEGACY_GATE2'} "
                         f"order/content changed")
        f += compare_consts("gates", bg.get("consts"), cg.get("consts"))
    bs, cs = base.get("selftest") or {}, cand.get("selftest") or {}
    if bs:
        if (cs.get("legacy") or 0) < bs["legacy"]:
            f.append(f"self-test legacy cases dropped {bs['legacy']} -> {cs.get('legacy')}")
        cl = {c[0]: c for c in cs.get("legacy_cases") or []}
        for c in bs.get("legacy_cases") or []:
            if cl.get(c[0]) != c:
                f.append(f"self-test legacy case {c[0]!r} changed or removed")
        if (cs.get("all") or 0) < bs.get("all", 0):
            f.append(f"self-test cases dropped {bs['all']} -> {cs.get('all')}")
        lost = sorted(set(bs.get("names") or []) - set(cs.get("names") or []))
        if lost:
            f.append(f"self-test cases removed: {lost[:5]}")
        lost = sorted(set(bs.get("units") or []) - set(cs.get("units") or []))
        if lost:
            f.append(f"self-test unit checks removed: {lost[:5]}")
    return f


def check(base_tree, cand_tree, python=None):
    """-> (findings, evidence)."""
    bs, cs = snapshot(base_tree, python), snapshot(cand_tree, python)
    findings = compare(bs, cs)
    guarded = {"base": file_hashes(base_tree, C.GUARDED_FILES),
               "cand": file_hashes(cand_tree, C.GUARDED_FILES)}
    yard = {"base": file_hashes(base_tree, C.YARDSTICK_FILES),
            "cand": file_hashes(cand_tree, C.YARDSTICK_FILES)}
    for fpath in C.YARDSTICK_FILES:
        if yard["base"][fpath] != yard["cand"][fpath]:
            findings.append(f"yardstick changed: {fpath} (automation never edits the yardstick)")
    changed = [p for p in C.GUARDED_FILES if guarded["base"][p] != guarded["cand"][p]]
    ev = {"guarded_changed": changed,
          "yardstick_changed": [p for p in C.YARDSTICK_FILES
                                if yard["base"][p] != yard["cand"][p]],
          "snapshot_errors": {"base": bs.get("errors"), "cand": cs.get("errors")},
          "registry": {"base": len(bs.get("registry") or []),
                       "cand": len(cs.get("registry") or [])},
          "selftest_cases": {"base": (bs.get("selftest") or {}).get("all"),
                             "cand": (cs.get("selftest") or {}).get("all"),
                             "legacy_base": (bs.get("selftest") or {}).get("legacy"),
                             "legacy_cand": (cs.get("selftest") or {}).get("legacy")},
          "lexicon_names": {"base": len(bs.get("lexicon") or {}),
                            "cand": len(cs.get("lexicon") or {})},
          "findings": findings}
    return findings, ev


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:12]

