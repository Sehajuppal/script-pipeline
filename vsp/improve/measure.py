"""measure — run evals/scorecard.py (subprocess, read-only use) on the
golden and holdout suites (plus the capability suite when present) for the
current tree, and record the results under learned/evals/:

  learned/evals/results/<stamp>-<suite>.json   raw scorecard JSON (git-ignored,
                                               newest 12 kept; the scorecard's
                                               copy_repo skips "results" dirs)
  learned/evals/latest.json                    pointer + headline metrics
  learned/evals/history.jsonl                  one line per measure (trends)
"""
import json
import os
import sys

from vsp.improve import common as C


def evals_out():
    return C.learned("evals")


def raw_dir():
    return os.path.join(evals_out(), "results")


def run_scorecard(tree, suite_file, out_path, python=None, label="run",
                  seeds="1,2,3", scorecard=None, extra_env=None, workers=None,
                  timeout=3600):
    """One `scorecard.py run` over `tree` with `suite_file`. -> result dict.
    Raises ImproveError with the output tail when the scorecard fails."""
    sc = scorecard or os.path.join(tree, "evals", "scorecard.py")
    cmd = [sys.executable, sc, "run", "--repo", tree,
           "--python", python or C.default_python(), "--label", label,
           "--golden", suite_file, "--out", out_path, "--seeds", seeds]
    if workers:
        cmd += ["--workers", str(workers)]
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    r = C.run(cmd, cwd=tree, env=C.child_env(extra_env), timeout=timeout)
    res = C.read_json(out_path) if os.path.exists(out_path) else None
    if r["rc"] != 0 or not isinstance(res, dict) or "summary" not in res:
        raise C.ImproveError(f"scorecard failed on {C.rel(suite_file)} "
                             f"(rc {r['rc']}): {C.tail(r['out'] + r['err'])}")
    res["_wall_s"] = r["secs"]
    return res


def headline(res):
    s = (res or {}).get("summary") or {}
    rub = s.get("rubric") or {}
    hooks = s.get("hooks") or {}
    return {"runs": s.get("runs"),
            "crash": (s.get("crash") or {}).get("rate"),
            "gate1_pass": (s.get("gate1_pass") or {}).get("rate"),
            "e2e_pass": (s.get("e2e_pass") or {}).get("rate"),
            "shippable": (s.get("shippable") or {}).get("rate"),
            "rubric_mean": rub.get("mean"), "selection_mean": rub.get("selection_mean"),
            "audit_mean": rub.get("audit_mean"),
            "compliance_flags": sum((s.get("compliance_flag_counts") or {}).values()),
            "hook_distinct": hooks.get("distinct_ratio"),
            "hook_distinct2": hooks.get("distinct2"),
            "seed_diversity": hooks.get("per_cell_seed_diversity"),
            "fallback_rate": hooks.get("fallback_rate"),
            "runtime_mean_s": s.get("runtime_mean_s"), "wall_s": res.get("wall_s")}


def measure(budget="small", python=None, suites=None, tree=None, label=None,
            log=None):
    """-> the latest.json dict (also written)."""
    if budget not in C.BUDGETS:
        raise C.ImproveError(f"budget must be one of {C.BUDGETS}")
    tree = os.path.abspath(tree or C.REPO)
    python = python or C.default_python()
    seeds = C.SEEDS[budget]
    t = C.now_utc()
    st = C.stamp(t)
    sha = C.git_sha(repo=tree)
    out = {"created": t.isoformat(), "stamp": st, "tree": tree, "git_sha": sha,
           "dirty": C.git_dirty(tree), "budget": budget, "seeds": seeds,
           "python": python, "python_version": C.py_version(python),
           "suites": {}}
    for suite in suites or C.SUITES:
        f = C.suite_path(suite, tree)
        if not os.path.isfile(f):
            continue
        raw = os.path.join(raw_dir(), f"{st}-{suite}.json")
        if log:
            log(f"measure: scorecard {suite} (seeds {seeds}) ...")
        res = run_scorecard(tree, f, raw, python=python,
                            label=f"{label or 'measure'}-{suite}", seeds=seeds)
        out["suites"][suite] = {"raw": C.rel(raw), "file": C.rel(f),
                                "headline": headline(res)}
    C.prune(raw_dir())
    C.write_json(os.path.join(evals_out(), "latest.json"), out)
    with open(os.path.join(evals_out(), "history.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"created": out["created"], "git_sha": sha,
                            "budget": budget, "suites": {k: v["headline"] for k, v
                                                         in out["suites"].items()}},
                           sort_keys=True) + "\n")
    return out


def latest():
    return C.read_json(os.path.join(evals_out(), "latest.json"))


def load_raw(latest_obj, suite):
    """Raw scorecard result for a suite of a latest.json (None if pruned)."""
    s = ((latest_obj or {}).get("suites") or {}).get(suite)
    if not s:
        return None
    p = s["raw"] if os.path.isabs(s["raw"]) else os.path.join(C.REPO, s["raw"])
    return C.read_json(p)


def history(n=20):
    rows = []
    try:
        with open(os.path.join(evals_out(), "history.jsonl"), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except ValueError:
                        pass
    except OSError:
        pass
    return rows[-n:]


def render(latest_obj):
    L = [f"measure {latest_obj.get('stamp')} · {latest_obj.get('git_sha')}"
         f"{' (dirty)' if latest_obj.get('dirty') else ''} · budget "
         f"{latest_obj.get('budget')} (seeds {latest_obj.get('seeds')}) · "
         f"{latest_obj.get('python_version')}"]
    for suite, v in (latest_obj.get("suites") or {}).items():
        h = v["headline"]
        L.append(f"  {suite:<10} runs {h['runs']} · e2e {h['e2e_pass']} · shippable "
                 f"{h['shippable']} · rubric {h['rubric_mean']} (sel "
                 f"{h['selection_mean']}, audit {h['audit_mean']}) · compliance "
                 f"{h['compliance_flags']} · hooks distinct {h['hook_distinct']} · "
                 f"{h['runtime_mean_s']}s/run")
    return "\n".join(L)
