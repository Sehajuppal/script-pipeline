"""Shared A/B machinery for promote and verify.

One yardstick for both sides: the BASE tree's evals/scorecard.py (which
imports the base's vsp/rubric.py and vsp/fixtures.py) and the base's
golden.jsonl / holdout.jsonl — a candidate can never grade itself with an
edited scorecard, rubric or suite. The candidate's self-test runs under every
interpreter tried (python3.9 and python3.12 when present).

    run_ab(base, cand, budget, ...) -> {stats, selftest, results, raw, compare, seeds}
    diversity(results) -> {suite: {distinct_ratio: [base, cand], distinct2: [...], ...}}
"""
import os
import sys

from vsp.improve import common as C
from vsp.improve import decide as D
from vsp.improve import measure as M

SUITES_AB = ("golden", "holdout")


def run_ab(base_tree, cand_tree, budget="full", python=None, label="ab", raw_dir=None,
           evidence_dir=None, log=None, selftest=True, env_base=None, env_cand=None,
           pys=None):
    say = log or (lambda m: None)
    if budget not in C.BUDGETS:
        raise C.ImproveError(f"budget must be one of {C.BUDGETS}")
    seeds = C.SEEDS[budget]
    sc = os.path.join(base_tree, "evals", "scorecard.py")
    if not os.path.isfile(sc):
        raise C.ImproveError(f"base tree has no evals/scorecard.py ({base_tree})")
    raw_dir = raw_dir or C.mkdtemp("vsp-ab-raw-")
    results, raw = {"base": {}, "cand": {}}, {}
    for suite in SUITES_AB:
        sf = C.suite_path(suite, base_tree)
        if not os.path.isfile(sf):
            raise C.ImproveError(f"base tree has no evals/{suite}.jsonl")
        for side, tree, env in (("base", base_tree, env_base), ("cand", cand_tree, env_cand)):
            out = os.path.join(raw_dir, f"{C.slug(label, 60)}-{side}-{suite}.json")
            say(f"{label}: scorecard {suite} on {side} (seeds {seeds}) ...")
            results[side][suite] = M.run_scorecard(
                tree, sf, out, python=python, label=f"{label}-{side}-{suite}", seeds=seeds,
                scorecard=sc, extra_env=env)
            raw[f"{side}-{suite}"] = out
    if selftest:
        say(f"{label}: self-test on the candidate ...")
        st = C.selftest(cand_tree, pys=pys)
    else:
        st = {"ok": True, "runs": [], "skipped": True}
    stats = {s: D.paired(results["base"][s], results["cand"][s]) for s in SUITES_AB}
    compare = {}
    if evidence_dir:
        os.makedirs(evidence_dir, exist_ok=True)
        for s in SUITES_AB:
            md = os.path.join(evidence_dir, f"{s}-compare.md")
            r = C.run([sys.executable, sc, "compare", raw[f"base-{s}"], raw[f"cand-{s}"],
                       "--out", md], cwd=base_tree, env=C.child_env(), timeout=600)
            compare[s] = C.rel(md) if r["rc"] == 0 else \
                f"compare failed (rc {r['rc']}): {C.tail(r['err'], 200)}"
    C.prune(raw_dir)
    return {"stats": stats, "selftest": st, "results": results, "seeds": seeds,
            "raw": {k: C.rel(v) for k, v in raw.items()}, "compare": compare}


def diversity(results):
    """Hook diversity from the scorecard summaries (evidence + promote's R11)."""
    out = {}
    for s in SUITES_AB:
        hb = ((results.get("base", {}).get(s) or {}).get("summary") or {}).get("hooks") or {}
        hc = ((results.get("cand", {}).get(s) or {}).get("summary") or {}).get("hooks") or {}
        if not hb and not hc:
            continue
        out[s] = {k: [hb.get(k), hc.get(k)] for k in
                  ("distinct_ratio", "distinct2", "per_cell_seed_diversity", "fallback_rate")}
    return out


def diversity_lines(div):
    L = []
    for s, d in div.items():
        dr, d2, sd = d["distinct_ratio"], d["distinct2"], d["per_cell_seed_diversity"]
        L.append(f"{s}: hook distinct ratio {dr[0]} → {dr[1]}"
                 + (f" ({dr[1] - dr[0]:+.4f})" if None not in dr else "")
                 + f" · distinct-2 {d2[0]} → {d2[1]}"
                 + (f" ({d2[1] - d2[0]:+.4f})" if None not in d2 else "")
                 + f" · per-cell seed diversity {sd[0]} → {sd[1]}")
    return L


def selftest_line(st):
    if st.get("skipped"):
        return "self-test: skipped"
    return "self-test " + ("green" if st.get("ok") else "RED") + " (" + ", ".join(
        f"{r.get('version') or r.get('python')} rc {r.get('rc')}" for r in st.get("runs", [])) + ")"
