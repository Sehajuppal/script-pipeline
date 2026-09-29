#!/usr/bin/env python3
"""Eval harness / scorecard for the viral script pipeline.

Runs ANY version of the pipeline (this checkout, or an old commit checked out
elsewhere) hermetically over a golden matrix and grades every result:

    python3 evals/scorecard.py run --repo . --label v2
    python3 evals/scorecard.py run --repo /tmp/baseline --python python3.12 --label baseline
    python3 evals/scorecard.py compare evals/results/baseline.json evals/results/v2.json

Hermetic: the target repo is copied to a temp dir (its outputs/ are never
touched), HOME points at a temp dir holding the fixture viral.db, and
VSP_VIRAL_DB / VSP_FIXTURE_OK=1 are set for 2.0+ code.

Per run it records: status (crash | gate1_fail | stage2_fail | gate2_fail |
fail | pass), gate messages -> rule ids, the rubric (vsp/rubric.py) score,
hook line, niche, runtime. The summary adds Wilson 95% intervals; `compare`
adds paired statistics (exact McNemar on pass/fail flips, prompt-clustered
bootstrap on rubric deltas).
"""
import argparse
import concurrent.futures as cf
import datetime as _dt
import json
import math
import os
import random
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from vsp import rubric as RUB          # noqa: E402
from vsp.fixtures import fixture_home  # noqa: E402

FORMATS = ["demo", "talking-head", "pov-vlog", "transformation", "review"]
PRESENTERS = ["human", "ai"]
SHIP_MIN_RUBRIC = 75.0


# ----------------------------------------------------------------- helpers
def slugify(prompt):
    return re.sub(r"[^a-z0-9]+", "-", (prompt or "x").lower()).strip("-")


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (p, max(0.0, c - h), min(1.0, c + h))


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def rule_id(msg):
    m = re.match(r"\s*(D\d+[a-z]?|B4a|R\d+)\b", msg)
    if m:
        return m.group(1)
    table = [("missing/empty required key", "REQ-KEYS"),
             ("fewer than 3 beats", "MIN-BEATS"),
             ("hashtag/niche mismatch", "TAG-MISMATCH"),
             ("missing time window", "D43-NO-WINDOW"),
             ("DELIVERABLE", "DELIVERABLE"),
             ("no 9:16", "RENDER-9x16"),
             ("words.json", "WORDS-JSON"),
             ("Do-NOT", "DO-NOT"),
             ("no reference reels", "REF-REELS"),
             ("shot timeline", "SHOT-DRIFT")]
    for pre, rid in table:
        if pre in msg:
            return rid
    return "OTHER:" + "-".join(msg.split()[:3])


def parse_report(text):
    """Parse validation-report.md (any pipeline version)."""
    out = {"status": "unknown", "gate1": [], "gate2": [], "stages": {}}
    if not text:
        return out
    if "STAGE 1 FAILED" in text or "STAGE 0 FAILED" in text:
        out["status"] = "crash"
    m = re.search(r"gate 1 \(script\): (PASS|FAIL — (.*))", text)
    if m and m.group(1) != "PASS":
        out["gate1"] = [x.strip() for x in m.group(2).split("; ") if x.strip()]
        out["status"] = "gate1_fail"
    if "STAGE 2 FAILED" in text:
        out["status"] = "stage2_fail"
    m = re.search(r"gate 2 \(brief\): (PASS|FAIL — (.*))", text)
    if m:
        if m.group(1) == "PASS":
            out["status"] = "pass"
        else:
            out["gate2"] = [x.strip() for x in m.group(2).split("; ")
                            if x.strip()]
            out["status"] = "gate2_fail"
    return out


def copy_repo(src, dst):
    ign = shutil.ignore_patterns(".git", "outputs", "__pycache__", "*.pyc",
                                 "results", ".pytest_cache")
    shutil.copytree(src, dst, ignore=ign)
    os.makedirs(os.path.join(dst, "outputs"), exist_ok=True)


def git_sha(repo):
    try:
        r = subprocess.run(["git", "-C", repo, "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or None
    except Exception:
        return None


def load_golden(path):
    rows = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("//"):
            rows.append(json.loads(line))
    return rows


# --------------------------------------------------------------------- run
def capabilities(py, repo, env):
    r = subprocess.run([py, os.path.join(repo, "pipeline.py"), "--help"],
                       capture_output=True, text=True, env=env, cwd=repo,
                       timeout=60)
    h = r.stdout + r.stderr
    return {"duration": "--duration" in h, "out_dir": "--out-dir" in h,
            "help_ok": r.returncode == 0}


def run_case(case, py, repo, env, caps, extra, tmpout):
    prompt = case["prompt"]
    key = f"{case['id']}|{case['format']}|{case['presenter']}|{case['seed']}"
    if caps["out_dir"]:
        outdir = os.path.join(tmpout, re.sub(r"[^A-Za-z0-9]+", "_", key))
    else:
        outdir = os.path.join(repo, "outputs", slugify(prompt))
    shutil.rmtree(outdir, ignore_errors=True)
    cmd = [py, os.path.join(repo, "pipeline.py"), prompt,
           "--presenter", case["presenter"], "--format", case["format"],
           "--seed", str(case["seed"])]
    if caps["duration"] and case.get("duration"):
        cmd += ["--duration", str(case["duration"])]
    if caps["out_dir"]:
        cmd += ["--out-dir", outdir]
    cmd += list(extra)
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, env=env,
                           cwd=repo, timeout=600)
        rc, stdout, stderr = r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        rc, stdout, stderr = -9, "", "timeout"
    dt = time.time() - t0
    rep_path = os.path.join(outdir, "validation-report.md")
    report = open(rep_path, encoding="utf-8").read() \
        if os.path.exists(rep_path) else stdout
    parsed = parse_report(report)
    if parsed["status"] == "unknown":
        parsed["status"] = "crash" if rc != 0 else "unknown"
    if parsed["status"] == "pass" and rc != 0:
        parsed["status"] = "fail"   # later stage (export/manifest) failed
    row = {"key": key, **{k: case[k] for k in ("id", "prompt", "concept",
                                               "format", "presenter", "seed")},
           "duration": case.get("duration") or 30,
           "rc": rc, "status": parsed["status"], "runtime_s": round(dt, 3),
           "gate1": parsed["gate1"], "gate2": parsed["gate2"],
           "rules_failed": sorted({rule_id(m) for m in
                                   parsed["gate1"] + parsed["gate2"]}),
           "stderr_tail": (stderr or "")[-300:] if rc not in (0, 1) else ""}
    sp = os.path.join(outdir, "script.json")
    if os.path.exists(sp) and parsed["status"] != "crash":
        try:
            script = json.load(open(sp, encoding="utf-8"))
            res = RUB.score(script)
            row.update({
                "rubric": res["score"], "rubric_selection": res["selection_score"],
                "rubric_audit": res["audit_score"],
                "rubric_failed": [c["id"] for c in res["checks"]
                                  if c["pass"] is False],
                "pitfalls": [p["id"] for p in res["pitfalls"]],
                "compliance_flags": res["compliance_flags"],
                "hook": RUB.hook_line(script),
                "overlay": RUB.frame0_overlay(script),
                "niche": script.get("niche"), "fit": script.get("fit"),
                "hook_family": script.get("hook_family"),
                "rehooks": [b.get("rehook") for b in script.get("beats", [])
                            if b.get("rehook")],
            })
        except Exception as e:  # corrupt script.json counts as a crash
            row.update({"status": "crash", "stderr_tail": f"bad script.json {e!r}"})
    for f in ("captions.srt", "shotlist.csv", "manifest.json", "trace.jsonl",
              "captions.vtt", "gate-report.json"):
        row.setdefault("artifacts", [])
        if os.path.exists(os.path.join(outdir, f)):
            row["artifacts"].append(f)
    return row


def cmd_run(a):
    repo_src = os.path.abspath(a.repo)
    golden = load_golden(a.golden)
    if a.limit:
        golden = golden[: a.limit]
    seeds = [int(x) for x in a.seeds.split(",")]
    formats = FORMATS if a.formats == "all" else a.formats.split(",")
    presenters = PRESENTERS if a.presenters == "all" else a.presenters.split(",")
    durations = [int(x) for x in a.durations.split(",")]
    tmp = tempfile.mkdtemp(prefix="vsp_eval_")
    repo = os.path.join(tmp, "repo")
    copy_repo(repo_src, repo)
    home, db = fixture_home(os.path.join(tmp, "home"))
    env = dict(os.environ, HOME=home, VSP_VIRAL_DB=db, VSP_FIXTURE_OK="1",
               PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    caps = capabilities(a.python, repo, env)
    if not caps["help_ok"]:
        print("warning: pipeline --help failed (target may not import on "
              f"{a.python})", file=sys.stderr)
    cases = []
    for g in golden:
        for fmt in formats:
            for pr in presenters:
                for sd in seeds:
                    for du in durations:
                        cases.append({**g, "format": fmt, "presenter": pr,
                                      "seed": sd, "duration": du})
    by_prompt = {}
    for c in cases:
        by_prompt.setdefault(c["prompt"], []).append(c)
    extra = a.extra.split() if a.extra else []
    tmpout = os.path.join(tmp, "out")
    os.makedirs(tmpout, exist_ok=True)
    rows = []
    t0 = time.time()

    def work(group):
        return [run_case(c, a.python, repo, env, caps, extra, tmpout)
                for c in group]

    with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
        for res in ex.map(work, by_prompt.values()):
            rows.extend(res)
            print(f"  {len(rows)}/{len(cases)} runs", file=sys.stderr)
    rows.sort(key=lambda r: r["key"])
    result = {"label": a.label, "repo": repo_src, "git_sha": git_sha(repo_src),
              "python": a.python,
              "created": _dt.datetime.now(_dt.timezone.utc).isoformat(),
              "capabilities": caps, "extra_args": extra,
              "matrix": {"prompts": len(golden), "formats": formats,
                         "presenters": presenters, "seeds": seeds,
                         "durations": durations},
              "wall_s": round(time.time() - t0, 1),
              "summary": summarize(rows), "runs": rows}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(result, open(a.out, "w", encoding="utf-8"), indent=1,
              ensure_ascii=False)
    if not a.keep:
        shutil.rmtree(tmp, ignore_errors=True)
    print(render_summary(result))
    print(f"\nwrote {a.out}")


# ----------------------------------------------------------------- metrics
def shippable(r):
    return (r["status"] == "pass" and r.get("rubric", 0) >= SHIP_MIN_RUBRIC
            and not r.get("compliance_flags"))


def distinct2(lines):
    grams, total = set(), 0
    for ln in lines:
        w = RUB._norm(ln).split()
        for i in range(len(w) - 1):
            grams.add((w[i], w[i + 1]))
            total += 1
    return len(grams) / total if total else 0.0


def summarize(rows):
    n = len(rows)
    cnt = lambda f: sum(1 for r in rows if f(r))  # noqa: E731
    s = {"runs": n}
    for name, f in [("crash", lambda r: r["status"] == "crash"),
                    ("gate1_pass", lambda r: r["status"] not in
                     ("crash", "gate1_fail", "unknown")),
                    ("e2e_pass", lambda r: r["status"] == "pass"),
                    ("shippable", shippable)]:
        k = cnt(f)
        p, lo, hi = wilson(k, n)
        s[name] = {"k": k, "rate": round(p, 4), "ci95": [round(lo, 4),
                                                          round(hi, 4)]}
    scored = [r for r in rows if "rubric" in r]
    if scored:
        vals = sorted(r["rubric"] for r in scored)
        s["rubric"] = {"n": len(vals), "mean": round(statistics.mean(vals), 1),
                       "median": round(statistics.median(vals), 1),
                       "p10": vals[int(0.1 * (len(vals) - 1))],
                       "p90": vals[int(0.9 * (len(vals) - 1))],
                       "selection_mean": round(statistics.mean(
                           r["rubric_selection"] for r in scored), 1),
                       "audit_mean": round(statistics.mean(
                           r["rubric_audit"] for r in scored), 1)}
        chk = {}
        for r in scored:
            for cid in r["rubric_failed"]:
                chk[cid] = chk.get(cid, 0) + 1
        s["rubric_fail_counts"] = dict(sorted(chk.items()))
        comp = {}
        for r in scored:
            for f in r.get("compliance_flags", []):
                comp[f] = comp.get(f, 0) + 1
        s["compliance_flag_counts"] = comp
        pits = {}
        for r in scored:
            for p in r.get("pitfalls", []):
                pits[p] = pits.get(p, 0) + 1
        s["pitfall_counts"] = pits
        hooks = [r["hook"] for r in scored if r.get("hook")]
        s["hooks"] = {
            "fallback_rate": round(sum(1 for h in hooks if
                                       RUB.FALLBACK_HOOK.match(h.strip()))
                                   / max(1, len(hooks)), 4),
            "distinct_ratio": round(len(set(hooks)) / max(1, len(hooks)), 4),
            "distinct2": round(distinct2(hooks), 4)}
        groups = {}
        for r in scored:
            groups.setdefault((r["id"], r["format"], r["presenter"]),
                              []).append(r.get("hook"))
        multi = [g for g in groups.values() if len(g) > 1]
        s["hooks"]["per_cell_seed_diversity"] = round(
            statistics.mean(len(set(g)) / len(g) for g in multi), 4) \
            if multi else None
        rh_dup = sum(1 for r in scored
                     if len(r.get("rehooks", [])) != len(set(r.get("rehooks", []))))
        s["rehook_repeat_rate"] = round(rh_dup / len(scored), 4)
    rules = {}
    for r in rows:
        for rid in r["rules_failed"]:
            rules[rid] = rules.get(rid, 0) + 1
    s["gate_fail_counts"] = dict(sorted(rules.items(), key=lambda kv: -kv[1]))
    for dim in ("concept", "format", "presenter"):
        d = {}
        for r in rows:
            d.setdefault(r[dim], [0, 0])
            d[r[dim]][1] += 1
            d[r[dim]][0] += r["status"] == "pass"
        s[f"e2e_by_{dim}"] = {k: round(v[0] / v[1], 3) for k, v in d.items()}
    s["runtime_mean_s"] = round(statistics.mean(r["runtime_s"] for r in rows),
                                3) if rows else 0
    arts = {}
    for r in rows:
        for f in r.get("artifacts", []):
            arts[f] = arts.get(f, 0) + 1
    s["artifact_counts"] = arts
    return s


def pct(x):
    return f"{100 * x:.1f}%"


def render_summary(res):
    s = res["summary"]
    L = [f"# Scorecard — {res['label']} ({res.get('git_sha')}, {res['python']})",
         f"{s['runs']} runs · {res['matrix']['prompts']} prompts × "
         f"{len(res['matrix']['formats'])} formats × "
         f"{len(res['matrix']['presenters'])} presenters × "
         f"{len(res['matrix']['seeds'])} seeds × "
         f"{len(res['matrix']['durations'])} durations · wall {res['wall_s']}s",
         ""]
    for k in ("crash", "gate1_pass", "e2e_pass", "shippable"):
        v = s[k]
        L.append(f"- {k}: {v['k']}/{s['runs']} = {pct(v['rate'])} "
                 f"(95% CI {pct(v['ci95'][0])}–{pct(v['ci95'][1])})")
    if "rubric" in s:
        r = s["rubric"]
        L.append(f"- rubric: mean {r['mean']} · median {r['median']} · "
                 f"p10 {r['p10']} · selection {r['selection_mean']} · "
                 f"audit {r['audit_mean']} (n={r['n']})")
        h = s["hooks"]
        L.append(f"- hooks: fallback {pct(h['fallback_rate'])} · distinct "
                 f"{pct(h['distinct_ratio'])} · distinct-2 {h['distinct2']} · "
                 f"seed diversity {h['per_cell_seed_diversity']}")
        L.append(f"- re-hook repeat rate: {pct(s['rehook_repeat_rate'])}")
        L.append(f"- compliance flags: {s['compliance_flag_counts'] or 'none'}")
        L.append(f"- rubric check failures: {s['rubric_fail_counts']}")
    top = list(s["gate_fail_counts"].items())[:12]
    L.append(f"- top gate failures: {dict(top) or 'none'}")
    L.append(f"- e2e by concept: {s['e2e_by_concept']}")
    L.append(f"- e2e by format: {s['e2e_by_format']}")
    L.append(f"- runtime: {s['runtime_mean_s']}s/run · artifacts "
             f"{s['artifact_counts'] or 'none'}")
    return "\n".join(L)


# ----------------------------------------------------------------- compare
def cmd_compare(a):
    A = json.load(open(a.a, encoding="utf-8"))
    B = json.load(open(a.b, encoding="utf-8"))
    ra = {r["key"]: r for r in A["runs"]}
    rb = {r["key"]: r for r in B["runs"]}
    keys = sorted(set(ra) & set(rb))
    b_ = sum(1 for k in keys if ra[k]["status"] == "pass"
             and rb[k]["status"] != "pass")
    c_ = sum(1 for k in keys if ra[k]["status"] != "pass"
             and rb[k]["status"] == "pass")
    p_mc = mcnemar_exact(b_, c_)
    sb = sum(1 for k in keys if shippable(ra[k]) and not shippable(rb[k]))
    sc = sum(1 for k in keys if not shippable(ra[k]) and shippable(rb[k]))
    p_ship = mcnemar_exact(sb, sc)
    # prompt-clustered paired bootstrap on rubric (missing script = 0)
    by_prompt = {}
    for k in keys:
        d = rb[k].get("rubric", 0.0) - ra[k].get("rubric", 0.0)
        by_prompt.setdefault(ra[k]["id"], []).append(d)
    clusters = list(by_prompt.values())
    rng = random.Random(0)
    means = []
    for _ in range(2000):
        pick = [clusters[rng.randrange(len(clusters))] for _ in clusters]
        flat = [x for c in pick for x in c]
        means.append(sum(flat) / len(flat))
    means.sort()
    flat_all = [x for c in clusters for x in c]
    mean_d = sum(flat_all) / len(flat_all) if flat_all else 0.0
    lo, hi = means[int(0.025 * len(means))], means[int(0.975 * len(means)) - 1]
    SA, SB = A["summary"], B["summary"]

    def ratio(x, y):
        if x == 0:
            return "∞" if y > 0 else "—"
        return f"{y / x:.1f}×"

    rows = []
    for name in ("e2e_pass", "shippable", "gate1_pass"):
        x, y = SA[name]["rate"], SB[name]["rate"]
        rows.append((name.replace("_", " "), pct(x), pct(y), ratio(x, y)))
    x, y = SA["crash"]["rate"], SB["crash"]["rate"]
    rows.append(("crash rate", pct(x), pct(y),
                 "eliminated" if y == 0 and x > 0 else ratio(x, y)))
    if "rubric" in SA and "rubric" in SB:
        rows.append(("rubric mean", SA["rubric"]["mean"], SB["rubric"]["mean"],
                     f"{SB['rubric']['mean'] - SA['rubric']['mean']:+.1f}"))
        rows.append(("rubric audit-only mean", SA["rubric"]["audit_mean"],
                     SB["rubric"]["audit_mean"],
                     f"{SB['rubric']['audit_mean'] - SA['rubric']['audit_mean']:+.1f}"))
        hx, hy = SA["hooks"]["fallback_rate"], SB["hooks"]["fallback_rate"]
        rows.append(("fallback-hook rate", pct(hx), pct(hy),
                     ratio(hy, hx) + " fewer" if hy else "eliminated"))
        rows.append(("hook distinct-2", SA["hooks"]["distinct2"],
                     SB["hooks"]["distinct2"], ratio(SA["hooks"]["distinct2"],
                                                     SB["hooks"]["distinct2"])))
        ca = sum(SA["compliance_flag_counts"].values())
        cb = sum(SB["compliance_flag_counts"].values())
        rows.append(("compliance flags (total)", ca, cb,
                     "eliminated" if cb == 0 and ca else ratio(cb, ca) + " fewer"
                     if cb else "—"))
    rows.append(("runtime / run (s)", SA["runtime_mean_s"], SB["runtime_mean_s"],
                 ratio(SA["runtime_mean_s"], SB["runtime_mean_s"])))
    L = [f"# Scorecard: {A['label']} → {B['label']}", "",
         f"Paired runs: {len(keys)} (same prompt × format × presenter × seed).",
         "", "| metric | " + A["label"] + " | " + B["label"] + " | change |",
         "|---|---|---|---|"]
    L += [f"| {m} | {x} | {y} | {r} |" for m, x, y, r in rows]
    L += ["",
          f"- e2e pass flips: {c_} fail→pass, {b_} pass→fail; exact McNemar "
          f"p = {p_mc:.3g}",
          f"- shippable flips: {sc} up, {sb} down; exact McNemar p = {p_ship:.3g}",
          f"- rubric Δ (paired, prompt-clustered bootstrap): {mean_d:+.1f} "
          f"[95% CI {lo:+.1f}, {hi:+.1f}]",
          "", "## " + A["label"], "", render_summary(A), "",
          "## " + B["label"], "", render_summary(B)]
    txt = "\n".join(L)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(txt + "\n")
        print(f"wrote {a.out}")
    print(txt)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--repo", default=ROOT)
    r.add_argument("--python", default=sys.executable)
    r.add_argument("--label", default="current")
    r.add_argument("--golden", default=os.path.join(HERE, "golden.jsonl"))
    r.add_argument("--seeds", default="1,2,3")
    r.add_argument("--formats", default="all")
    r.add_argument("--presenters", default="all")
    r.add_argument("--durations", default="30")
    r.add_argument("--workers", type=int, default=8)
    r.add_argument("--limit", type=int, default=0)
    r.add_argument("--extra", default="", help="extra pipeline args")
    r.add_argument("--out", default=None)
    r.add_argument("--keep", action="store_true", help="keep the temp dir")
    c = sub.add_parser("compare")
    c.add_argument("a")
    c.add_argument("b")
    c.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.cmd == "run":
        a.out = a.out or os.path.join(HERE, "results", f"{a.label}.json")
        cmd_run(a)
    else:
        cmd_compare(a)


if __name__ == "__main__":
    main()
