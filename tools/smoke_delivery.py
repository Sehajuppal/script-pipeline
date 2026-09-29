#!/usr/bin/env python3
"""Smoke / measurement harness for the SO-3 delivery modules (hermetic).

    python3 tools/smoke_delivery.py                  # full matrix, all sections
    python3 tools/smoke_delivery.py --limit 5 --sections gate2,captions
    python3 tools/smoke_delivery.py --json results.json

Matrix: evals/golden.jsonl x formats x presenters x seeds (default 1,2,3),
generated in-process with viral_script_maker.generate (no subprocess).

Sections
  gate2     vsp.repair.repair(script, gate1) -> gate-1 passes -> make_shotlist
            .build_bundle -> vsp.gates.gate2 (fixture viral.db, VSP_FIXTURE_OK=1)
  captions  vsp.captions.build_cues + lint over every gate-2 pass
  exports   vsp.exporters.write_exports on a sample (files parse back)
  schema    vsp.schema.validate on every raw maker output (+ repaired)
  select    vsp.select.run best-of-N on a sample of prompts
  replay    pipeline.py run -> manifest -> vsp.manifest.replay on a sample
Nothing is written into the repo (temp dirs only).
"""
import argparse
import collections
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import viral_script_maker as vsm  # noqa: E402
import make_shotlist  # noqa: E402
from vsp import gates  # noqa: E402
from vsp.fixtures import build_fixture_db  # noqa: E402

FORMATS = ["demo", "talking-head", "pov-vlog", "transformation", "review"]
PRESENTERS = ["human", "ai"]


def load_golden(path):
    return [json.loads(x) for x in open(path, encoding="utf-8")
            if x.strip() and not x.startswith("//")]


def rule_id(msg):
    m = re.match(r"\s*(D\d+[a-z]?|B4a)\b", msg)
    if m:
        return m.group(1)
    for pre, rid in (("DELIVERABLE", "DELIVERABLE"), ("no 9:16", "RENDER-9x16"),
                     ("words.json", "WORDS-JSON"), ("Do-NOT", "DO-NOT"),
                     ("no reference reels", "REF-REELS"),
                     ("shot timeline", "SHOT-DRIFT"),
                     ("hashtag/niche mismatch", "TAG-MISMATCH"),
                     ("missing time window", "D43-NO-WINDOW")):
        if pre in msg:
            return rid
    return "OTHER:" + "-".join(msg.split()[:3])


def matrix(a):
    golden = load_golden(os.path.join(ROOT, "evals", "golden.jsonl"))
    if a.limit:
        golden = golden[:a.limit]
    fmts = FORMATS if a.formats == "all" else a.formats.split(",")
    prs = PRESENTERS if a.presenters == "all" else a.presenters.split(",")
    seeds = [int(x) for x in a.seeds.split(",")]
    for g in golden:
        for f in fmts:
            for p in prs:
                for sd in seeds:
                    yield g, f, p, sd


def gen(g, f, p, sd, duration=30):
    s = vsm.generate(g["prompt"], presenter=p, fmt=f, duration=duration,
                     seed=sd)
    return json.loads(json.dumps(s))


def pct(k, n):
    return f"{k}/{n} = {100.0 * k / n:.1f}%" if n else f"{k}/0"


# ------------------------------------------------------------------ gate 2
SHOTLIST_RULES = {"D47", "D48", "D43", "SHOT-DRIFT", "DELIVERABLE", "RENDER-9x16",
                  "WORDS-JSON", "DO-NOT", "D46", "D138"}


def section_gate2(a, R):
    from vsp.repair import repair
    from vsp.select import gate_cascade
    n = pre = rep_ok = g2_ok = g2_ok_casc = 0
    g1_left, g2_fail, g2_casc_fail = (collections.Counter(), collections.Counter(),
                                      collections.Counter())
    g2_examples, shot_fail = {}, 0
    passes = []
    for g, f, p, sd in matrix(a):
        n += 1
        s = gen(g, f, p, sd)
        if not gates.gate1(s):
            pre += 1
        s2, log, ok = repair(s, gates.gate1)
        if not ok:
            for m in gates.gate1(s2):
                g1_left[rule_id(m)] += 1
            continue
        rep_ok += 1
        bundle, shots, vo = make_shotlist.build_bundle(s2)
        g2 = gates.gate2(bundle, s2)
        if g2:
            rids = {rule_id(m) for m in g2}
            shot_fail += bool(rids & SHOTLIST_RULES)
            for m in g2:
                rid = rule_id(m)
                g2_fail[rid] += 1
                g2_examples.setdefault(rid, f"{g['id']}|{f}|{p}|{sd}: {m}")
            # stage-8 variant: the rule-keyed repair over the gate cascade
            s3, _, ok3 = repair(s2, gate_cascade)
            if ok3:
                g2_ok_casc += 1
                bundle, shots, vo = make_shotlist.build_bundle(s3)
                passes.append((g, f, p, sd, s3, shots, vo))
            else:
                for m in gate_cascade(s3):
                    g2_casc_fail[rule_id(m)] += 1
        else:
            g2_ok += 1
            g2_ok_casc += 1
            passes.append((g, f, p, sd, s2, shots, vo))
    R["gate2"] = {"runs": n, "gate1_pass_raw": pre, "repair_pass": rep_ok,
                  "gate1_unrepaired": dict(g1_left.most_common()),
                  "gate2_pass": g2_ok, "gate2_fail_rules": dict(g2_fail.most_common()),
                  "gate2_shotlist_attributable_fail": shot_fail,
                  "gate2_pass_after_cascade_repair": g2_ok_casc,
                  "gate2_cascade_fail_rules": dict(g2_casc_fail.most_common()),
                  "gate2_examples": g2_examples}
    print(f"[gate2] runs {n} | raw gate-1 pass {pct(pre, n)} | repaired gate-1 "
          f"pass (repair(s, gate1)) {pct(rep_ok, n)}")
    print(f"[gate2] gate-2 pass on gate-1 passes {pct(g2_ok, rep_ok)} | shot-list-"
          f"attributable gate-2 failures {pct(shot_fail, rep_ok)}")
    print(f"[gate2] gate-2 failure rules: {dict(g2_fail.most_common())}")
    print(f"[gate2] after stage-8 repair(s, select.gate_cascade): gate-2 pass "
          f"{pct(g2_ok_casc, rep_ok)} (left: {dict(g2_casc_fail.most_common())})")
    print(f"[gate2] unrepaired gate-1 rules: {dict(g1_left.most_common())}")
    for rid, ex in list(g2_examples.items())[:12]:
        print(f"    e.g. {ex[:220]}")
    return passes


# ---------------------------------------------------------------- captions
def section_captions(a, R, passes):
    from vsp import captions
    scripts_warn = cues_total = cues_warn = 0
    kinds = collections.Counter()
    for g, f, p, sd, s, shots, vo in passes:
        cues = captions.build_cues(s, shots)
        warns = captions.lint(cues)
        cues_total += len(cues)
        bad = {w.split(":")[0] for w in warns}
        cues_warn += len({w.split(" ")[1] for w in warns if w.startswith("cue ")})
        if warns:
            scripts_warn += 1
        for w in warns:
            kinds[re.sub(r"^cue \d+: ", "", w).split(" ")[0]] += 1
        # round-trip sanity: SRT/VTT/Remotion render without error
        captions.to_srt(cues), captions.to_vtt(cues), captions.to_remotion(cues)
    n = len(passes)
    R["captions"] = {"scripts": n, "scripts_with_warnings": scripts_warn,
                     "cues": cues_total, "cues_with_warnings": cues_warn,
                     "warning_kinds": dict(kinds.most_common())}
    print(f"[captions] scripts with lint warnings {pct(scripts_warn, n)} | cues "
          f"with warnings {pct(cues_warn, cues_total)} | kinds {dict(kinds.most_common())}")


# ----------------------------------------------------------------- exports
def section_exports(a, R, passes):
    import csv
    import io
    from vsp import exporters
    tmp = tempfile.mkdtemp(prefix="vsp_exp_")
    ok = 0
    sample = passes[:: max(1, len(passes) // 25)][:25]
    try:
        for i, (g, f, p, sd, s, shots, vo) in enumerate(sample):
            out = os.path.join(tmp, str(i))
            paths = exporters.write_exports(out, s, shots, vo)
            want = {"captions.srt", "captions.vtt", "captions.json",
                    "shotlist.csv", "shots.json"}
            assert want <= {os.path.basename(x) for x in paths.values()}, paths
            rows = list(csv.DictReader(io.open(paths["shotlist.csv"],
                                               encoding="utf-8", newline="")))
            assert len(rows) == len(shots), (len(rows), len(shots))
            json.load(open(paths["captions.json"], encoding="utf-8"))
            json.load(open(paths["shots.json"], encoding="utf-8"))
            assert open(paths["captions.vtt"], encoding="utf-8").read().startswith("WEBVTT")
            ok += 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    R["exports"] = {"sample": len(sample), "ok": ok}
    print(f"[exports] write_exports round-trip OK {pct(ok, len(sample))}")


# ------------------------------------------------------------------ schema
def section_schema(a, R):
    from vsp import schema
    from vsp.repair import repair
    n = bad = bad_rep = 0
    errs = collections.Counter()
    for g, f, p, sd in matrix(a):
        n += 1
        s = gen(g, f, p, sd)
        e = schema.validate(s)
        if e:
            bad += 1
            for x in e:
                errs[x[:90]] += 1
        s2, _, _ = repair(s, gates.gate1)
        if schema.validate(s2):
            bad_rep += 1
    R["schema"] = {"scripts": n, "invalid_raw": bad, "invalid_repaired": bad_rep,
                   "errors": dict(errs.most_common(10))}
    print(f"[schema] invalid maker outputs {pct(bad, n)} | invalid after repair "
          f"{pct(bad_rep, n)} {dict(errs.most_common(5))}")


# ------------------------------------------------------------------ select
def section_select(a, R):
    from vsp import select
    from vsp.rubric import score
    golden = load_golden(os.path.join(ROOT, "evals", "golden.jsonl"))[:a.select_prompts]
    won = 0
    rows = []
    for g in golden:
        for f in ("demo", "talking-head"):
            def gen_fn(seed, _g=g, _f=f):
                return vsm.generate(_g["prompt"], presenter="human", fmt=_f,
                                    duration=30, seed=seed)
            res = select.run(gen_fn, 701, a.candidates, gates.gate1, score)
            won += res["winner"] is not None
            rows.append({"id": g["id"], "format": f, "winner": res["winner"],
                         "passes": sum(c["passed"] for c in res["candidates"]),
                         "duplicates": sum(bool(c.get("duplicate_of") is not None)
                                           for c in res["candidates"]),
                         "best_failing": res["best_failing"][:3]})
    R["select"] = {"runs": len(rows), "with_winner": won, "rows": rows}
    print(f"[select] best-of-{a.candidates} runs with a gate-1 winner (no repair) "
          f"{pct(won, len(rows))}")


# ------------------------------------------------------------------ replay
def section_replay(a, R):
    from vsp import manifest
    tmp = tempfile.mkdtemp(prefix="vsp_replay_")
    env = dict(os.environ)
    ok_n = 0
    rows = []
    try:
        env["VSP_VIRAL_DB"] = build_fixture_db(os.path.join(tmp, "viral.db"))
        env["VSP_FIXTURE_OK"] = "1"
        env["VSP_OUTPUTS"] = os.path.join(tmp, "outputs")
        cases = [("portable door lock", "demo", "human", 701),
                 ("hair wax stick", "review", "ai", 3),
                 ("I quit sugar for 21 days", "pov-vlog", "human", 11)]
        for prompt, fmt, pr, sd in cases[:a.replay_samples]:
            out = os.path.join(tmp, re.sub(r"\W+", "-", prompt))
            argv = [prompt, "--presenter", pr, "--format", fmt, "--seed", str(sd)]
            r = subprocess.run([sys.executable, os.path.join(ROOT, "pipeline.py")]
                               + argv + ["--out-dir", out], capture_output=True,
                               text=True, env=env, timeout=300)
            args = {"prompt": prompt, "presenter": pr, "format": fmt,
                    "seed": sd, "duration": 30, "out_dir": out}
            m = manifest.build_manifest(argv=argv + ["--out-dir", out], args=args,
                                        seed=sd, candidate_seeds=[sd],
                                        outdir=out, repo=ROOT)
            mp = manifest.write_manifest(out, m)
            old = dict(os.environ)
            os.environ.update(env)
            try:
                ok, det = manifest.replay(mp)
            finally:
                os.environ.clear()
                os.environ.update(old)
            ok_n += ok
            rows.append({"prompt": prompt, "rc": r.returncode, "ok": ok,
                         "expected": det.get("expected_sha256"),
                         "actual": det.get("actual_sha256")})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    R["replay"] = {"samples": len(rows), "ok": ok_n, "rows": rows}
    print(f"[replay] manifest replay reproduces script.json sha256 "
          f"{pct(ok_n, len(rows))}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--formats", default="all")
    ap.add_argument("--presenters", default="all")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sections",
                    default="gate2,captions,exports,schema,select,replay")
    ap.add_argument("--candidates", type=int, default=8)
    ap.add_argument("--select-prompts", type=int, default=10)
    ap.add_argument("--replay-samples", type=int, default=3)
    ap.add_argument("--json", default=None, help="write the results here")
    a = ap.parse_args()
    secs = set(a.sections.split(","))
    tmp = tempfile.mkdtemp(prefix="vsp_smoke_")
    old_env = dict(os.environ)
    os.environ["VSP_VIRAL_DB"] = build_fixture_db(os.path.join(tmp, "viral.db"))
    os.environ["VSP_FIXTURE_OK"] = "1"
    R = {"python": sys.version.split()[0], "sections": sorted(secs)}
    t0 = time.time()
    try:
        passes = []
        if secs & {"gate2", "captions", "exports"}:
            passes = section_gate2(a, R)
        if "captions" in secs:
            section_captions(a, R, passes)
        if "exports" in secs:
            section_exports(a, R, passes)
        if "schema" in secs:
            section_schema(a, R)
        if "select" in secs:
            section_select(a, R)
    finally:
        os.environ.clear()
        os.environ.update(old_env)
        shutil.rmtree(tmp, ignore_errors=True)
    if "replay" in secs:
        section_replay(a, R)
    R["wall_s"] = round(time.time() - t0, 1)
    print(f"[done] python {R['python']} in {R['wall_s']}s")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(R, f, indent=1, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
