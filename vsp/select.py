"""Stages 3 + 5 — best-of-N candidate generation and selection (D149).

    run(gen_fn, seed, n, gate_fn, score_fn) -> {
        "winner": int | None,        # candidate index
        "script": dict | None,       # the winning script
        "seeds": [int, ...],         # vsp.seeding.candidate_seeds(seed, n)
        "candidates": [record, ...], # JSON-safe, manifest-ready (no scripts)
        "best_failing": [int, ...],  # repair order when winner is None
        "scripts": [dict | None, ...]}   # per candidate (not for the manifest)

record = {index, seed, error, gate1 [msgs], passed, rubric {score,
selection_score, audit_score}, hook, rank, duplicate_of, hook_jaccard}

Rules (labs-techniques §2.1, oss-pipelines §2 #8/#9):
  * candidate 0 = the raw seed, so --candidates 1 reproduces pre-2.0 seeds
  * winner = highest rubric selection_score among gate passes; tie -> the
    lowest index. selection_score already excludes the audit-only checks
    (R12/R15/R17/P2) — audit checks never select (they stay a gaming probe)
  * near-duplicate hooks (word-trigram Jaccard > 0.5 vs a higher-ranked
    candidate) are marked duplicate_of (informational: the winner is by
    construction never a duplicate)
  * nothing passes -> winner None and best_failing ordered by (fewest gate
    messages, highest selection_score, lowest index) for the stage-6 repair

gate_cascade(script) is the cheapest-first cascade gate 1 -> shot list ->
gate 2 (labs-techniques §2.1 step 2): pass it as gate_fn so a candidate that
would die at gate 2 (e.g. D36 content) never wins selection.
"""
import json
import re

from vsp import seeding

DUP_THRESHOLD = 0.5


def _plain(obj):
    return json.loads(json.dumps(obj))


def _msg(m):
    if isinstance(m, dict):
        return str(m.get("message") or m.get("rule") or m)
    return str(m)


def _errors(result):
    out = []
    for m in result or []:
        if isinstance(m, dict) and str(m.get("severity", "error")).lower() in (
                "warning", "warn", "info", "note"):
            continue
        out.append(_msg(m))
    return out


def _words(text):
    return re.findall(r"[a-z0-9']+", (text or "").lower().replace("\u2019", "'"))


def trigrams(text):
    w = _words(text)
    if len(w) < 3:
        return {tuple(w)} if w else set()
    return {tuple(w[i:i + 3]) for i in range(len(w) - 2)}


def jaccard(a, b):
    A, B = trigrams(a), trigrams(b)
    if not A and not B:
        return 0.0
    return len(A & B) / len(A | B)


def hook_of(script):
    try:
        from vsp.rubric import hook_line
        return hook_line(script)
    except Exception:
        for h in script.get("hook_stack") or []:
            if h.get("dialogue"):
                return h["dialogue"]
        return ""


def gate_cascade(script, refs=None):
    """gate 1; if clean, shot list + gate 2. Legacy message text verbatim."""
    from vsp.gates import gate1, gate2
    g1 = gate1(script)
    if g1:
        return g1
    import make_shotlist
    bundle, _, _ = make_shotlist.build_bundle(script, refs=refs)
    return gate2(bundle, script)


def _sel(rec):
    r = rec.get("rubric") or {}
    v = r.get("selection_score")
    return float(v) if isinstance(v, (int, float)) else -1.0


def run(gen_fn, seed, n, gate_fn=None, score_fn=None, dup_threshold=DUP_THRESHOLD,
        trace=None):
    """Generate n candidates from derived sub-seeds, gate + score each, pick
    the winner. gen_fn(seed) -> script; gate_fn(script) -> [messages];
    score_fn(script) -> vsp.rubric.score()-shaped dict. Never raises for a
    candidate failure (recorded as `error`)."""
    if gate_fn is None:
        from vsp.gates import gate1 as gate_fn
    if score_fn is None:
        from vsp.rubric import score as score_fn
    seeds = seeding.candidate_seeds(seed, n)
    records, scripts = [], []
    for i, sd in enumerate(seeds):
        rec = {"index": i, "seed": sd, "error": None, "gate1": [], "passed": False,
               "rubric": None, "hook": None, "rank": None, "duplicate_of": None,
               "hook_jaccard": None}
        span = trace.span("candidate", index=i, seed=sd) if trace else None
        if span:
            span.__enter__()
        script = None
        try:
            script = _plain(gen_fn(sd))
        except Exception as e:
            rec["error"] = f"generate: {type(e).__name__}: {e}"
        if script is not None:
            try:
                rec["gate1"] = _errors(gate_fn(script))
                rec["passed"] = not rec["gate1"]
            except Exception as e:
                rec["error"] = f"gate: {type(e).__name__}: {e}"
            try:
                r = score_fn(script)
                rec["rubric"] = {k: r.get(k) for k in
                                 ("score", "selection_score", "audit_score")}
            except Exception as e:
                rec["rubric"] = None
                rec["error"] = rec["error"] or f"score: {type(e).__name__}: {e}"
            rec["hook"] = hook_of(script)
        if trace:
            trace.eval_result("gate", "pass" if rec["passed"] else "fail",
                              explanation="; ".join(rec["gate1"][:5]) or rec["error"],
                              candidate=i)
            if rec["rubric"]:
                trace.eval_result("rubric.selection", "scored",
                                  score=rec["rubric"]["selection_score"], candidate=i)
            span.__exit__(None, None, None)
        records.append(rec)
        scripts.append(script)
    ok = [r for r in records if r["passed"] and r["error"] is None]
    bad = [r for r in records if not (r["passed"] and r["error"] is None)
           and scripts[r["index"]] is not None]
    ok.sort(key=lambda r: (-_sel(r), r["index"]))
    bad.sort(key=lambda r: (len(r["gate1"]) + (1000 if r["error"] else 0),
                            -_sel(r), r["index"]))
    ranked = ok + bad
    for pos, r in enumerate(ranked):
        r["rank"] = pos + 1
        best_j, best_idx = 0.0, None
        for hi in ranked[:pos]:
            j = jaccard(r["hook"] or "", hi["hook"] or "")
            if j > best_j:
                best_j, best_idx = j, hi["index"]
        r["hook_jaccard"] = round(best_j, 3) if best_idx is not None else None
        if best_idx is not None and best_j > dup_threshold:
            r["duplicate_of"] = best_idx
    winner = ok[0]["index"] if ok else None
    return {"winner": winner,
            "script": scripts[winner] if winner is not None else None,
            "seeds": seeds, "candidates": records,
            "best_failing": [] if winner is not None else [r["index"] for r in bad],
            "scripts": scripts}


def summary(result):
    """One line for validation-report.md."""
    c = result["candidates"]
    passed = sum(1 for r in c if r["passed"])
    dups = sum(1 for r in c if r["duplicate_of"] is not None)
    if result["winner"] is None:
        return (f"select: 0/{len(c)} candidates passed; repair order "
                f"{result['best_failing'][:5]}")
    w = c[result["winner"]]
    return (f"select: {passed}/{len(c)} candidates passed; winner #{w['index']} "
            f"(seed {w['seed']}, selection {_sel(w):.1f}); {dups} near-duplicate hooks")
