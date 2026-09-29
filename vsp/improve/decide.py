"""The ACCEPT rules shared by promote and verify, on scorecard JSONs.

Statistics mirror evals/scorecard.py `compare` exactly (exact McNemar on
pass/fail flips; prompt-clustered paired bootstrap, seed 0, 2000 resamples,
missing script = rubric 0), so the numbers here match the compare report.

ACCEPT only if every rule holds (each on golden AND holdout):
  R1 no significant e2e regression   flips down <= flips up, or McNemar p > 0.05
  R2 no significant shippable regr.  same test on shippable (pass + rubric
                                     >= 75 + no compliance flag)
  R3 rubric                          paired Δ 95% CI lower bound >= -0.5
  R4 audit-only                      audit mean not lower by more than 0.5
                                     (audit checks never select: gaming probe)
  R5 holdout not lower               holdout e2e rate, shippable rate and
                                     rubric mean (as reported) >= base
  R6 compliance                      zero compliance flags in the candidate
  R7 self-test                       green on every interpreter tried
  R8 paired coverage                 the candidate ran every base case
  R9 guard (verify)                  no gate/rule/lexicon weakening
  R10 non-vacuous (promote)          the pack changed >= 1 hook, else the A/B
                                     proves nothing and nothing is approved
  R11 diversity (promote)            hook distinct ratio not lower on golden
                                     and holdout: a pack exists to ADD variety

Diversity (hook distinct ratio, distinct-2, per-cell seed diversity from the
scorecard summary) is always reported in the evidence; for promote it is also
the expected win — a pack that raises it with no quality loss.
"""
import math
import random

MCNEMAR_ALPHA = 0.05
RUBRIC_CI_FLOOR = -0.5
AUDIT_DROP_MAX = 0.5
SHIP_MIN_RUBRIC = 75.0
BOOT_N = 2000


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def shippable(r):
    return (r.get("status") == "pass" and r.get("rubric", 0) >= SHIP_MIN_RUBRIC
            and not r.get("compliance_flags"))


def bootstrap_ci(ra, rb, keys, n=BOOT_N, seed=0):
    """Prompt-clustered paired bootstrap of the rubric delta (scorecard's
    compare). -> (mean, lo, hi)."""
    by_prompt = {}
    for k in keys:
        d = rb[k].get("rubric", 0.0) - ra[k].get("rubric", 0.0)
        by_prompt.setdefault(ra[k].get("id"), []).append(d)
    clusters = list(by_prompt.values())
    flat_all = [x for c in clusters for x in c]
    if not flat_all:
        return 0.0, 0.0, 0.0
    rng = random.Random(seed)
    means = []
    for _ in range(n):
        pick = [clusters[rng.randrange(len(clusters))] for _ in clusters]
        flat = [x for c in pick for x in c]
        means.append(sum(flat) / len(flat))
    means.sort()
    mean_d = sum(flat_all) / len(flat_all)
    return mean_d, means[int(0.025 * len(means))], means[int(0.975 * len(means)) - 1]


def _summ(res, *path, default=None):
    cur = (res or {}).get("summary") or {}
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def paired(base, cand):
    """Paired statistics for one suite (two scorecard result dicts)."""
    ra = {r["key"]: r for r in (base or {}).get("runs") or []}
    rb = {r["key"]: r for r in (cand or {}).get("runs") or []}
    keys = sorted(set(ra) & set(rb))
    e_down = sum(1 for k in keys if ra[k]["status"] == "pass" and rb[k]["status"] != "pass")
    e_up = sum(1 for k in keys if ra[k]["status"] != "pass" and rb[k]["status"] == "pass")
    s_down = sum(1 for k in keys if shippable(ra[k]) and not shippable(rb[k]))
    s_up = sum(1 for k in keys if not shippable(ra[k]) and shippable(rb[k]))
    mean_d, lo, hi = bootstrap_ci(ra, rb, keys)
    hook_changes = sum(1 for k in keys if (ra[k].get("hook") or "") != (rb[k].get("hook") or ""))
    comp_c = sum((_summ(cand, "compliance_flag_counts", default={}) or {}).values())
    comp_b = sum((_summ(base, "compliance_flag_counts", default={}) or {}).values())
    return {
        "n_base": len(ra), "n_cand": len(rb), "n_paired": len(keys),
        "missing_in_cand": len(set(ra) - set(rb)),
        "e2e": {"base": _summ(base, "e2e_pass", "rate"), "cand": _summ(cand, "e2e_pass", "rate"),
                "down": e_down, "up": e_up, "p": mcnemar_exact(e_down, e_up)},
        "shippable": {"base": _summ(base, "shippable", "rate"), "cand": _summ(cand, "shippable", "rate"),
                      "down": s_down, "up": s_up, "p": mcnemar_exact(s_down, s_up)},
        "rubric": {"base": _summ(base, "rubric", "mean"), "cand": _summ(cand, "rubric", "mean"),
                   "delta": round(mean_d, 3), "ci95": [round(lo, 3), round(hi, 3)]},
        "audit": {"base": _summ(base, "rubric", "audit_mean"), "cand": _summ(cand, "rubric", "audit_mean")},
        "selection": {"base": _summ(base, "rubric", "selection_mean"),
                      "cand": _summ(cand, "rubric", "selection_mean")},
        "compliance_flags": {"base": comp_b, "cand": comp_c},
        "hooks": {"changed_runs": hook_changes,
                  "distinct_base": _summ(base, "hooks", "distinct_ratio"),
                  "distinct_cand": _summ(cand, "hooks", "distinct_ratio"),
                  "distinct2_base": _summ(base, "hooks", "distinct2"),
                  "distinct2_cand": _summ(cand, "hooks", "distinct2")},
        "runtime_s": {"base": _summ(base, "runtime_mean_s"), "cand": _summ(cand, "runtime_mean_s")},
    }


def _ge(a, b):
    """a >= b for reported (possibly None) metrics; None never passes."""
    return a is not None and b is not None and a >= b - 1e-12


DIVERSITY_TOL = 0.0


def decide(stats, selftest_ok, guard_findings=None, require_change=False,
           require_diversity=False):
    """stats = {"golden": paired(...), "holdout": paired(...)} (a missing
    suite fails). -> {"verdict": "ACCEPT"|"REJECT", "checks": [...],
    "reasons": [...]}"""
    checks = []

    def chk(cid, ok, detail):
        checks.append({"id": cid, "ok": bool(ok), "detail": detail})

    for suite in ("golden", "holdout"):
        s = (stats or {}).get(suite)
        if not s or not s.get("n_paired"):
            chk(f"{suite}:present", False, f"no paired {suite} scorecard")
            continue
        e, sh, rb, au = s["e2e"], s["shippable"], s["rubric"], s["audit"]
        chk(f"{suite}:R1-e2e", e["down"] <= e["up"] or e["p"] > MCNEMAR_ALPHA,
            f"e2e flips {e['up']} up / {e['down']} down, McNemar p={e['p']:.3g}")
        chk(f"{suite}:R2-shippable", sh["down"] <= sh["up"] or sh["p"] > MCNEMAR_ALPHA,
            f"shippable flips {sh['up']} up / {sh['down']} down, McNemar p={sh['p']:.3g}")
        chk(f"{suite}:R3-rubric-ci", rb["ci95"][0] >= RUBRIC_CI_FLOOR,
            f"rubric Δ {rb['delta']:+.2f} [95% CI {rb['ci95'][0]:+.2f}, {rb['ci95'][1]:+.2f}]"
            f" (floor {RUBRIC_CI_FLOOR})")
        ok_audit = (au["base"] is not None and au["cand"] is not None
                    and au["cand"] >= au["base"] - AUDIT_DROP_MAX - 1e-9)
        chk(f"{suite}:R4-audit", ok_audit,
            f"audit-only mean {au['base']} → {au['cand']} (max drop {AUDIT_DROP_MAX})")
        chk(f"{suite}:R6-compliance", s["compliance_flags"]["cand"] == 0,
            f"candidate compliance flags: {s['compliance_flags']['cand']}")
        chk(f"{suite}:R8-coverage", s["missing_in_cand"] == 0 and s["n_cand"] >= s["n_base"],
            f"{s['n_paired']} paired runs, {s['missing_in_cand']} base cases missing in cand")
        if suite == "holdout":
            ok = (_ge(e["cand"], e["base"]) and _ge(sh["cand"], sh["base"])
                  and _ge(rb["cand"], rb["base"]))
            chk("holdout:R5-not-lower", ok,
                f"holdout e2e {e['base']} → {e['cand']}, shippable {sh['base']} → "
                f"{sh['cand']}, rubric {rb['base']} → {rb['cand']}")
    chk("R7-selftest", selftest_ok, "self-test green" if selftest_ok else "self-test RED")
    if guard_findings is not None:
        chk("R9-guard", not guard_findings,
            "no gate/rule/lexicon weakening" if not guard_findings else
            f"{len(guard_findings)} weakening finding(s): " + "; ".join(guard_findings[:3]))
    if require_change:
        n = sum(((stats or {}).get(s) or {}).get("hooks", {}).get("changed_runs", 0)
                for s in ("golden", "holdout"))
        chk("R10-non-vacuous", n > 0,
            f"{n} paired run(s) rendered a different hook" if n else
            "vacuous: no paired run changed its hook (loader absent or no template "
            "selected) — the A/B proves nothing")
    if require_diversity:
        for suite in ("golden", "holdout"):
            h = ((stats or {}).get(suite) or {}).get("hooks") or {}
            a, b = h.get("distinct_base"), h.get("distinct_cand")
            chk(f"{suite}:R11-diversity", _ge(b, (a or 0) - DIVERSITY_TOL) and a is not None,
                f"hook distinct ratio {a} → {b}, distinct-2 {h.get('distinct2_base')} → "
                f"{h.get('distinct2_cand')}")
    reasons = [f"{c['id']}: {c['detail']}" for c in checks if not c["ok"]]
    return {"verdict": "REJECT" if reasons else "ACCEPT", "checks": checks,
            "reasons": reasons}


def headline(stats):
    """One line per suite for summaries and the ledger."""
    out = []
    for suite in ("golden", "holdout"):
        s = (stats or {}).get(suite)
        if not s:
            continue
        e, sh, rb, au = s["e2e"], s["shippable"], s["rubric"], s["audit"]
        out.append(f"{suite}: e2e {e['base']}→{e['cand']} (flips +{e['up']}/−{e['down']}, "
                   f"p={e['p']:.3g}) · shippable {sh['base']}→{sh['cand']} · rubric "
                   f"{rb['base']}→{rb['cand']} Δ {rb['delta']:+.2f} [{rb['ci95'][0]:+.2f}, "
                   f"{rb['ci95'][1]:+.2f}] · audit {au['base']}→{au['cand']} · compliance "
                   f"{s['compliance_flags']['cand']} · hooks changed "
                   f"{s['hooks']['changed_runs']}/{s['n_paired']} · distinct "
                   f"{s['hooks']['distinct_base']}→{s['hooks']['distinct_cand']} · distinct-2 "
                   f"{s['hooks'].get('distinct2_base')}→{s['hooks'].get('distinct2_cand')}")
    return out
