#!/usr/bin/env python3
"""pipeline.py — the production pipeline (v2). Everything goes through it.

    python3 pipeline.py "<product>" [--presenter ai|human] [--format ...]
        [--duration 30] [--seed 701] [--persona NAME] [--no-research]
        [--out-dir DIR] [--candidates 8] [--strict-route]
        [--require-fresh-research] [--llm-judge] [--json]
    python3 pipeline.py --script-json FILE [--out-dir DIR]   (gates only)
    python3 pipeline.py --replay outputs/<slug>/manifest.json
    python3 pipeline.py --self-test

Stages (docs/UPGRADE-PLAN.md §2, RULES.md D147-D153):
   1 ROUTE      vsp.router — input guardrails + 3-voter router. Input errors
                (incl. an unknown --persona) fail as STAGE 1 FAILED, status
                input_error; --strict-route fails a split vote.
   2 RESEARCH   vsp.research.load_pack — pinned by sha256; stale is a
                warning (--require-fresh-research fails); --no-research skips.
   3 GENERATE   N candidates (--candidates, default 8) from derived sub-seeds;
                candidate 0 is the raw seed (--candidates 1 = legacy output).
   4 GATE 1     every candidate, through vsp.select.gate_cascade
                (gate 1 -> shot list -> gate 2, cheapest first).
   5 SELECT     best rubric selection score among cascade passes (D149).
   6 REPAIR     only when nothing passed: vsp.repair over best_failing,
                <= 3 rounds each (D150). Then the legacy gate-1 line.
   7 SHOT LIST  make_shotlist.build_bundle -> bundle.md, brief.md.
   8 GATE 2     brief gate (legacy gate-2 line).
   9 EXPORT     passing runs only: JSON-Schema check, captions (SRT/VTT/
                Remotion JSON), shotlist.csv, shots.json (D152).
  10 MANIFEST   every run, pass or fail, after validation-report.md:
                manifest.json (hashes, seeds, scores, script_summary),
                trace.jsonl, gate-report.json (D153).

Report (validation-report.md, also stdout unless --json): one line per
stage, `stage N (name): OK|FAIL|SKIPPED|BYPASSED — detail`; crashes print
`STAGE N FAILED (name): ...`; the legacy `gate 1 (script): PASS|FAIL — m1;
m2` and `gate 2 (brief): ...` lines are kept verbatim (evals/scorecard.py
parses them); a `warnings:` section closes the report.

Exit code is non-zero when any stage fails. No silent passes. --replay
exits 0 only when script.json's sha256 AND the exit code reproduce.
Gate code lives in vsp/gates.py (re-exported here); the hermetic self-test
lives in vsp/selftest.py (fixtures in vsp/selftest_cases.py).
"""
import argparse, json, os, re, subprocess, sys, traceback

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
from viral_script_maker import humanize_dialogue  # D63: spoken-voice pass
from vsp import config
from vsp.gates import (gate1, gate2, words_per_sec, parse_t,  # noqa: F401
                       MISMATCH, STAGE_VERBS, LINK_GROUPS)  # re-exported API
DB = config.viral_db_path()  # kept for callers that read pipeline.DB

# every file a run may write: all are removed before a run, so a failing run
# never leaves a stale bundle/brief/export from an earlier one (D152/D153)
ARTIFACTS = ("script.json", "bundle.md", "brief.md", "validation-report.md",
             "captions.srt", "captions.vtt", "captions.json", "shotlist.csv",
             "shots.json", "direction.md", "hooks.md", "posting.md",
             "trend.md", "trend.json", "render.json", "voice_plan.json", "render.md",
             "manifest.json", "trace.jsonl", "gate-report.json")
# v2.1 creative layer docs (stage 9): written when the script carries the key
CREATIVE_DOCS = (("direction.md", "direction", "vsp.direction", "Creative direction"),
                 ("hooks.md", "hook_variants", "vsp.hooks", "Hook variants (A/B test sheet)"),
                 ("posting.md", "discovery", "vsp.discovery", "Posting & discovery"))

STAGES = {1: "route", 2: "research", 3: "generate", 4: "gate 1", 5: "select",
          6: "repair", 7: "shot list", 8: "gate 2", 9: "export", 10: "manifest"}
MAX_CANDIDATES = 64
# env that changes what a run produces: recorded in the manifest, pinned by
# --replay (the research pack is also pinned by vsp.manifest.replay)
ENV_KEYS = ("VSP_VIRAL_DB", "VSP_FIXTURE_OK", "VSP_RESEARCH_PACK",
            "VSP_LEARNED_DIR", "VSP_NO_HOOK_PACKS", "VSP_NO_PRIORS",
            "VSP_DOSSIER_DIR")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return r


def self_test():
    """Gates must pass the good fixture and fail each bad fixture loudly
    (hermetic: temp outputs root + fixture viral.db; repo untouched)."""
    from vsp import selftest
    return selftest.run(os.path.abspath(__file__))


def slugify(prompt):
    return re.sub(r"[^a-z0-9]+", "-", (prompt or "x").lower()).strip("-") or "x"


def _write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _sha256_file(path):
    import hashlib
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def _rule_label(msg):
    """D-number of a gate message, else a short label (report summaries)."""
    m = re.match(r"\s*(D\d+[a-z]?|B4a|R\d+)\b", str(msg))
    if m:
        return m.group(1)
    if "hashtag/niche mismatch" in str(msg):
        return "TAG-MISMATCH"
    return " ".join(str(msg).split()[:4]).rstrip(" —-:;,.")


def _tail(tb, n=500):
    return "  " + tb[-n:].strip().replace("\n", "\n  ")


def persona_key(name, path=None):
    """--persona NAME -> (personas.json key, None) or (None, error). NAME
    matches a key or a display name, case-insensitively. The maker falls
    back to "maya" for any unknown name (and to NO persona for "_"-keys), so
    a typo would silently put a different face — or none — on an AI script
    (personas.json: one face across every video); stage 1 fails instead."""
    path = path or os.path.join(BASE, "personas.json")
    try:
        with open(path, encoding="utf-8") as f:
            reg = json.load(f)
    except (OSError, ValueError) as e:
        return None, f"--persona {name!r}: cannot read {os.path.basename(path)} ({e})"
    keys = sorted(k for k, v in reg.items() if not k.startswith("_")
                  and isinstance(v, dict) and v.get("identity"))
    want = str(name).strip().lower()
    for k in keys:
        if want in (k.lower(), str(reg[k].get("name") or "").strip().lower()):
            return k, None
    return None, (f"unknown --persona {name!r} — {os.path.basename(path)} has: "
                  f"{', '.join(keys) or 'no personas'}")


# ------------------------------------------------------------ learned state
def _maker():
    return sys.modules.get("viral_script_maker")


def learned_state():
    """What the self-improving loop fed this run: priors file, hook packs
    (files + the approved ids the maker loaded) — for the manifest and the
    replay drift check."""
    from vsp import priors as vpri
    packs_dir = config.hook_packs_dir()
    files = {}
    try:
        for n in sorted(os.listdir(packs_dir)):
            if n.endswith(".json"):
                files[n] = _sha256_file(os.path.join(packs_dir, n))
    except OSError:
        pass
    vsm = _maker()
    return {"dir": os.path.abspath(config.learned_dir()),
            "priors": vpri.info(),
            "hook_packs": {"dir": os.path.abspath(packs_dir), "files": files,
                           "loaded": list(getattr(vsm, "HOOK_PACKS_LOADED", []) or []),
                           "disabled": os.environ.get("VSP_NO_HOOK_PACKS") == "1"}}


def _learned_drift(recorded, now):
    warns = []
    if not isinstance(recorded, dict):
        return warns
    rp, np_ = recorded.get("priors") or {}, now.get("priors") or {}
    if rp.get("sha256") != np_.get("sha256"):
        warns.append("learned priors.json changed since the run "
                      f"({(rp.get('sha256') or 'absent')[:12]} -> "
                      f"{(np_.get('sha256') or 'absent')[:12]})")
    rh = (recorded.get("hook_packs") or {}).get("files") or {}
    nh = (now.get("hook_packs") or {}).get("files") or {}
    changed = sorted(k for k in set(rh) | set(nh) if rh.get(k) != nh.get(k))
    if changed:
        warns.append("learned hook packs changed since the run: "
                     + ", ".join(changed[:8]))
    return warns


def replay_main(path, as_json=False):
    """--replay: pin the recorded env + learned dir, re-run, compare the
    script.json sha256 (vsp.manifest.replay). Exit 0 iff reproduced."""
    from vsp import manifest as vman
    pre = []
    try:
        m = vman.load_manifest(path)
    except (OSError, ValueError):
        m = {}
    for k, v in sorted((m.get("env") or {}).items()):
        if k not in ENV_KEYS:
            continue
        if v is None:
            os.environ.pop(k, None)
        elif k in ("VSP_VIRAL_DB", "VSP_LEARNED_DIR") and not os.path.exists(v):
            pre.append(f"{k} {v} no longer exists — using the current value")
        else:
            os.environ[k] = str(v)
    ok, det = vman.replay(path)
    try:
        det["warnings"] = (det.get("warnings") or []) + pre + _learned_drift(
            m.get("learned"), learned_state())
    except Exception as e:  # noqa: BLE001 — drift is advisory
        det["warnings"] = (det.get("warnings") or []) + [f"learned drift check: {e!r}"]
    # the verdict must reproduce too: the same script.json under a gate
    # that now answers differently is not the recorded run
    rec = m.get("exit_code")
    if (ok and isinstance(rec, int) and isinstance(det.get("returncode"), int)
            and det["returncode"] != rec):
        ok = False
        det["error"] = (f"script.json reproduced but the replay exited "
                        f"{det['returncode']}, the recorded run exited {rec} "
                        f"(status {m.get('status')!r})")
    if as_json:
        print(json.dumps({"status": "reproduced" if ok else "mismatch",
                          "exit_code": 0 if ok else 1, "replay": det},
                         indent=1, ensure_ascii=False, default=str))
    else:
        print(vman.replay_report(ok, det))
    return 0 if ok else 1


# ------------------------------------------------------------------- run
class _Stop(Exception):
    def __init__(self, code):
        Exception.__init__(self, code)
        self.code = code


class Run:
    """One pipeline run: stage lines, gate results and everything the
    manifest records. finish() is the single exit point for a run."""

    def __init__(self, a, args_record, argv, outdir, script=None):
        self.a, self.args_record, self.argv = a, args_record, argv
        self.outdir = outdir
        self.script = script                  # finished JSON (--script-json)
        self.from_json = script is not None
        self.report, self.stages, self.warnings = [], {}, []
        self.cur = 1                          # stage in progress (crash label)
        self.skip_reason = None
        self.route = self.pack = self.pack_meta = None
        self.sel, self.selected, self.repairs = None, None, []
        self.g1 = self.g2 = None
        self.g1_warn, self.g2_warn = [], []
        self.bundle = self.shots = self.vo = None
        self.exports, self.llm_judge = {}, None
        self.use_research = False
        self.failed_stage = None
        self.crashed = False
        self.input_rejected = False
        self.tr = None
        self.trend, self.trend_note = None, None   # v2.2: set by main()

    # ------------------------------------------------------------ report
    def line(self, n, status, detail=""):
        """One stage line. A FAIL here is not terminal by itself (stage 4/5
        FAIL hands over to repair); stop() marks the stage that ended the run."""
        self.stages[n] = {"n": n, "name": STAGES[n], "status": status,
                          "detail": detail}
        self.report.append(f"stage {n} ({STAGES[n]}): {status}"
                           + (f" — {detail}" if detail else ""))

    def crash(self, n, msg, tb=None, input_error=False):
        """`STAGE N FAILED (name): msg` (+ traceback tail) — the stage line.
        input_error=True: the input was rejected (stage 1 guardrails) — the
        same loud line, but the run status is "input_error", not "crash"."""
        self.stages[n] = {"n": n, "name": STAGES[n], "status": "FAIL",
                          "detail": msg, "crash": not input_error}
        if input_error:
            self.stages[n]["input_error"] = True
        self.report.append(f"STAGE {n} FAILED ({STAGES[n]}): {msg}"
                           + (("\n" + _tail(tb)) if tb else ""))
        self.failed_stage = self.failed_stage or n
        if input_error:
            self.input_rejected = True
        else:
            self.crashed = True

    def warn(self, source, msgs, cap=20):
        msgs = [str(m) for m in (msgs or []) if str(m).strip()]
        for m in msgs[:cap]:
            self.warnings.append(f"{source}: {m}")
        if len(msgs) > cap:
            self.warnings.append(f"{source}: (+{len(msgs) - cap} more)")

    def stop(self, code, reason):
        """End the run at the current stage (finish() skips the rest)."""
        self.skip_reason = reason
        if self.failed_stage is None:
            self.failed_stage = self.cur
        raise _Stop(code)

    def span(self, name, **attrs):
        return self.tr.span(name, **attrs)

    # ------------------------------------------------------------ stages
    def execute(self):
        a = self.a
        from vsp import trace as vtrace
        import vsp
        self.tr = vtrace.Trace(os.path.join(self.outdir, "trace.jsonl"),
                               **{"service.name": "viral-script-pipeline",
                                  "service.version": vsp.__version__})
        code = 1
        try:
            self.stage_route_research()
            if self.from_json:
                for n in (3, 4, 5, 6):
                    self.line(n, "BYPASSED", "finished JSON supplied")
            else:
                self.stage_generate_select()
                self.stage_repair()
            self.stage_gate1()
            self.stage_shotlist()
            self.stage_gate2()
            self.stage_export()
            code = 0
        except _Stop as s:
            code = s.code
        except Exception as e:  # noqa: BLE001 — an orchestrator bug still reports
            self.crash(self.cur, f"unexpected {type(e).__name__}: {e}",
                       traceback.format_exc())
            self.skip_reason = f"stage {self.cur} failed"
            code = 1
        self.finish(code)

    def stage_route_research(self):
        a = self.a
        from vsp import research as vres, router
        # the pack is loaded once, before routing (the router's research
        # voter reads it); stage 2 reports it
        if not a.no_research:
            try:
                self.pack, self.pack_meta = vres.load_pack(config.research_pack_path())
            except Exception as e:  # noqa: BLE001 — load_pack never raises; belt
                self.pack, self.pack_meta = None, {
                    "path": config.research_pack_path(), "sha256": None,
                    "errors": [f"load_pack crashed: {e!r}"], "warnings": [],
                    "stale": None, "age_hours": None}
        # ---- stage 1 ROUTE
        self.cur = 1
        presenter = (self.script or {}).get("presenter") if self.from_json else a.presenter
        fmt = (self.script or {}).get("format") if self.from_json else a.format
        with self.span("stage.route") as sp:
            try:
                self.route = router.route(a.prompt, presenter=presenter, fmt=fmt,
                                          pack=self.pack if self.pack is not None else False)
            except Exception as e:  # noqa: BLE001
                self.crash(1, f"router raised {type(e).__name__}: {e}",
                           traceback.format_exc())
                self.stop(1, "stage 1 failed")
            r = self.route
            sp.set(concept=r.get("concept"), niche=r.get("niche"),
                   agreement=r.get("agreement"), strict_ok=r.get("strict_ok"))
        self.warn("route", r.get("warnings"))
        errs = list(r.get("input_errors") or [])
        if not self.from_json and a.persona is not None:
            if a.presenter != "ai":
                self.warn("route", [f"--persona {a.persona!r} is ignored for "
                                    f"--presenter {a.presenter}"])
            else:
                key, err = persona_key(a.persona)
                if err:
                    errs.append(err)
                else:
                    a.persona = key   # the maker's key (args_record keeps the input)
        if errs:
            self.crash(1, "; ".join(errs), input_error=True)
            self.stop(1, "stage 1 failed")
        summ = router.summary_line(r)
        summ = summ[len("route: "):] if summ.startswith("route: ") else summ
        if a.strict_route and not r.get("strict_ok"):
            self.line(1, "FAIL", f"--strict-route: router agreement "
                      f"{r.get('agreement', 0):.2f} < {router.AGREEMENT_MIN:.2f} ({summ})")
            self.stop(1, "stage 1 failed")
        self.line(1, "OK", summ)
        # ---- stage 2 RESEARCH
        self.cur = 2
        with self.span("stage.research") as sp:
            if a.no_research:
                self.line(2, "SKIPPED", "--no-research: frozen rulebook, the "
                          "research pack is ignored")
                sp.set(skipped=True)
                return
            m = self.pack_meta or {}
            sp.set(sha256=m.get("sha256"), stale=m.get("stale"),
                   age_hours=m.get("age_hours"))
            self.warn("research", m.get("warnings"))
            name = os.path.basename(m.get("path") or config.research_pack_path())
            if self.pack is None:
                err = "; ".join(m.get("errors") or ["unusable"])
                if a.require_fresh_research:
                    self.line(2, "FAIL", f"--require-fresh-research: no usable "
                              f"research pack ({err})")
                    self.stop(1, "stage 2 failed")
                self.warn("research", m.get("errors"))
                self.line(2, "SKIPPED", f"no usable research pack ({err}) — "
                          "frozen rulebook")
                return
            age = m.get("age_hours")
            age_s = f"{age:.1f} h old" if isinstance(age, (int, float)) else "age unknown"
            if m.get("stale") and a.require_fresh_research:
                self.line(2, "FAIL", f"--require-fresh-research: {name} is stale "
                          f"({age_s} > {vres.STALE_HOURS:g} h)")
                self.stop(1, "stage 2 failed")
            self.use_research = True
            self.line(2, "OK", f"{name} sha256 {str(m.get('sha256'))[:12]}, {age_s}"
                      + (" (STALE)" if m.get("stale") else "")
                      + f", {self.pack.get('reels_total', 0)} reels")

    def stage_generate_select(self):
        a = self.a
        import viral_script_maker as vsm
        from vsp import priors as vpri, rubric, select as vsel
        self.cur = 3
        crash_tb = []
        # learned state the maker consumes: skipped hook packs / bad priors
        self.warn("learned", ["hook pack " + w for w in
                              getattr(vsm, "HOOK_PACK_WARNINGS", None) or []])
        pinfo = vpri.info()
        if pinfo["exists"] and not pinfo["valid"] and not pinfo["disabled"]:
            self.warn("learned", [f"{os.path.basename(pinfo['path'])} is not a valid "
                                  f"schema-v1 priors file — ignored"])

        def gen_fn(seed):
            try:
                s = vsm.generate(a.prompt, presenter=a.presenter, fmt=a.format,
                                 duration=a.duration, seed=seed,
                                 use_research=self.use_research, persona=a.persona,
                                 trend=self.trend)
                prov = getattr(vsm, "learned_provenance", dict)()
            except Exception:
                crash_tb.append(traceback.format_exc())
                raise
            if prov:              # priors_used / hook_packs (learned state)
                s = dict(s)
                s.update(prov)
            return s

        with self.span("stage.generate_select", candidates=a.candidates) as sp:
            try:
                sel = vsel.run(gen_fn, seed=a.seed, n=a.candidates,
                               gate_fn=vsel.gate_cascade, score_fn=rubric.score,
                               trace=self.tr)
            except Exception as e:  # noqa: BLE001 — select.run never raises; belt
                self.crash(3, f"candidate generation raised {type(e).__name__}: {e}",
                           traceback.format_exc())
                self.stop(1, "stage 3 failed")
            sp.set(winner=sel["winner"])
        self.sel = sel
        cands = sel["candidates"]
        crashed = [c for c in cands if sel["scripts"][c["index"]] is None]
        live = [c for c in cands if sel["scripts"][c["index"]] is not None]
        if not live:
            self.crash(3, f"all {len(cands)} candidate(s) crashed — "
                       f"{cands[0]['error'] if cands else 'no candidates'}",
                       crash_tb[0] if crash_tb else None)
            self.stop(1, "stage 3 failed")
        self.warn("generate", [f"candidate #{c['index']} (seed {c['seed']}) "
                               f"crashed: {c['error']}" for c in crashed])
        seeds = ", ".join(str(s) for s in sel["seeds"][:4]) + (
            ", …" if len(sel["seeds"]) > 4 else "")
        self.line(3, "OK", f"{len(cands)} candidate(s) (seeds {seeds}); "
                  f"{len(crashed)} crashed")
        # ---- stage 4 GATE 1 (over every candidate, via the cascade)
        self.cur = 4
        from collections import Counter
        g1_ok, rules = 0, Counter()
        for c in live:
            if c["passed"]:
                g1_ok += 1
                continue
            try:
                if not gate1(sel["scripts"][c["index"]]):
                    g1_ok += 1
            except Exception:  # noqa: BLE001 — counted as a gate-1 failure
                pass
            for m in c["gate1"]:
                rules[_rule_label(m)] += 1
        casc = sum(1 for c in live if c["passed"] and not c["error"])
        top = ", ".join(f"{k} ×{v}" for k, v in rules.most_common(4))
        self.line(4, "OK" if g1_ok else "FAIL",
                  f"{g1_ok}/{len(live)} candidate(s) pass gate 1; {casc}/{len(live)} "
                  f"pass the cascade (gate 1 → shot list → gate 2)"
                  + (f"; failing: {top}" if top else ""))
        # ---- stage 5 SELECT
        self.cur = 5
        summ = vsel.summary(sel)
        summ = summ[len("select: "):] if summ.startswith("select: ") else summ
        if sel["winner"] is not None:
            w = sel["winner"]
            self.selected = {"index": w, "seed": sel["seeds"][w], "via": "selection"}
            self.script = sel["script"]
            if a.llm_judge:
                self.judge()
        elif a.llm_judge:
            self.llm_judge = {"status": "skipped", "reason": "no passing candidates"}
        jd = ""
        if self.llm_judge:
            jd = f"; llm-judge (advisory): {self.llm_judge.get('verdict') or self.llm_judge['status']}"
        self.line(5, "OK" if sel["winner"] is not None else "FAIL", summ + jd)

    def judge(self):
        """--llm-judge: advisory pairwise verdict on the top-2 passing
        candidates. Never changes the winner or a gate."""
        sel = self.sel
        ok = sorted((c for c in sel["candidates"] if c["passed"] and not c["error"]),
                    key=lambda c: c["rank"] or 10 ** 6)[:2]
        try:
            from vsp import llm as vllm
            avail = getattr(vllm, "available", None)
            judge = getattr(vllm, "judge_scripts", None)
            if not callable(avail) or not callable(judge):
                self.llm_judge = {"status": "unavailable",
                                  "reason": "vsp.llm has no available()/judge_scripts()"}
            elif not avail():
                self.llm_judge = {"status": "unavailable",
                                  "reason": "no LLM provider configured"}
            elif len(ok) < 2:
                self.llm_judge = {"status": "skipped",
                                  "reason": "fewer than 2 passing candidates"}
            else:
                with self.span("stage.llm_judge"):
                    res = judge(sel["scripts"][ok[0]["index"]],
                                sel["scripts"][ok[1]["index"]])
                res = json.loads(json.dumps(res, default=str))
                v = res.get("verdict") if isinstance(res, dict) else None
                self.llm_judge = {"status": "ok", "a": ok[0]["index"],
                                  "b": ok[1]["index"], "verdict": v,
                                  "agrees_with_selection": v == "A" if v in ("A", "B") else None,
                                  "result": res, "advisory": True}
                self.tr.eval_result("llm.pairwise", v, explanation=json.dumps(
                    res, default=str)[:1500], candidate_a=ok[0]["index"],
                    candidate_b=ok[1]["index"])
        except Exception as e:  # noqa: BLE001 — advisory: never fails a run
            self.llm_judge = {"status": "error", "error": f"{type(e).__name__}: {e}"}

    def stage_repair(self):
        self.cur = 6
        sel = self.sel
        if sel["winner"] is not None:
            self.line(6, "SKIPPED", f"candidate #{sel['winner']} passed; nothing to repair")
            return
        from vsp import repair as vrep, select as vsel
        best = best_n = best_idx = None
        with self.span("stage.repair", candidates=len(sel["best_failing"])) as sp:
            for idx in sel["best_failing"]:
                try:
                    s2, log, ok = vrep.repair(sel["scripts"][idx], vsel.gate_cascade,
                                              max_rounds=3)
                    n_fail = 0 if ok else len(vsel.gate_cascade(s2))
                except Exception as e:  # noqa: BLE001 — try the next candidate
                    self.repairs.append({"candidate": idx, "seed": sel["seeds"][idx],
                                         "passed": False,
                                         "error": f"{type(e).__name__}: {e}"})
                    continue
                self.repairs.append({"candidate": idx, "seed": sel["seeds"][idx],
                                     "passed": ok, "log": log})
                if best is None or n_fail < best_n:
                    best, best_n, best_idx = s2, n_fail, idx
                if ok:
                    self.selected = {"index": idx, "seed": sel["seeds"][idx],
                                     "via": "repair"}
                    break
            sp.set(passed=bool(self.selected), tried=len(self.repairs))
        if best is None:          # every repair crashed: report the best failing
            best_idx = sel["best_failing"][0]
            best = sel["scripts"][best_idx]
        self.script = json.loads(json.dumps(best))
        if self.selected:
            r = self.repairs[-1]
            acts = [e for e in r["log"] if e.get("rule") not in ("regate", "none", "sync")]
            rounds = max([e.get("round", 0) for e in r["log"]] or [0])
            rules = sorted({str(e.get("rule")) for e in acts})
            self.line(6, "OK", f"candidate #{best_idx} (seed {sel['seeds'][best_idx]}) "
                      f"repaired in {rounds} round(s), {len(acts)} action(s)"
                      + (f" [{', '.join(rules)}]" if rules else "")
                      + f"; {len(self.repairs)} candidate(s) tried")
        else:
            self.selected = {"index": best_idx, "seed": sel["seeds"][best_idx],
                             "via": "best_failing"}
            self.line(6, "FAIL", f"{len(self.repairs)} candidate(s) tried, none "
                      f"passes; reporting #{best_idx} (seed {sel['seeds'][best_idx]}, "
                      f"{best_n if best_n is not None else '?'} failure(s) left)")

    def stage_gate1(self):
        self.cur = 4
        from vsp.gates import gate1_findings
        with open(os.path.join(self.outdir, "script.json"), "w", encoding="utf-8") as f:
            json.dump(self.script, f, indent=1, ensure_ascii=False)
        with self.span("stage.gate1") as sp:
            self.g1 = gate1(self.script)
            try:
                self.g1_warn = [f["message"] for f in gate1_findings(self.script)
                                if f.get("severity") != "error"]
            except Exception:  # noqa: BLE001 — warnings are advisory
                self.g1_warn = []
            sp.set(errors=len(self.g1), warnings=len(self.g1_warn))
        self.tr.gate_results("gate1", self.g1)
        self.warn("gate 1", self.g1_warn)
        self.report.append(f"gate 1 (script): "
                           f"{'PASS' if not self.g1 else 'FAIL — ' + '; '.join(self.g1)}")
        if self.g1:
            self.stop(1, "gate 1 failed")

    def stage_shotlist(self):
        self.cur = 7
        a, outdir = self.a, self.outdir
        with self.span("stage.shot_list"):
            try:
                import make_shotlist
                bundle_text, self.shots, self.vo = make_shotlist.build_bundle(self.script)
            except Exception as e:  # noqa: BLE001
                self.crash(7, f"make_shotlist.build_bundle raised {type(e).__name__}: {e}",
                           traceback.format_exc())
                self.stop(1, "stage 7 failed")
        self.bundle = bundle_text
        _write(os.path.join(outdir, "bundle.md"), bundle_text)
        # split the Antigravity brief out — it includes the shot list (Antigravity needs it)
        if "## Shot list" in bundle_text:
            head, brief = bundle_text.split("## Shot list", 1)
            brief = brief.replace("## Antigravity brief\n\n", "", 1)
            _write(os.path.join(outdir, "brief.md"),
                   "# Antigravity brief — " + a.prompt + "\n\n## Shot list" + brief)
        elif "## Antigravity brief" in bundle_text:
            head, brief = bundle_text.split("## Antigravity brief", 1)
            _write(os.path.join(outdir, "brief.md"),
                   "# Antigravity brief — " + a.prompt + "\n\n## Antigravity brief" + brief)
        files = [f for f in ("bundle.md", "brief.md")
                 if os.path.isfile(os.path.join(outdir, f))]
        self.line(7, "OK", f"{len(self.shots or [])} shot(s), {len(self.vo or [])} "
                  f"VO line(s) → {', '.join(files)}")

    def stage_gate2(self):
        self.cur = 8
        from vsp.gates import gate2_findings
        with self.span("stage.gate2") as sp:
            self.g2 = gate2(self.bundle, self.script)
            try:
                self.g2_warn = [f["message"] for f in
                                gate2_findings(self.bundle, self.script)
                                if f.get("severity") != "error"]
            except Exception:  # noqa: BLE001
                self.g2_warn = []
            sp.set(errors=len(self.g2), warnings=len(self.g2_warn))
        self.tr.gate_results("gate2", self.g2)
        self.warn("gate 2", self.g2_warn)
        self.line(8, "OK" if not self.g2 else "FAIL",
                  f"{len(self.g2)} error(s), {len(self.g2_warn)} warning(s)")
        self.report.append(f"gate 2 (brief): "
                           f"{'PASS' if not self.g2 else 'FAIL — ' + '; '.join(self.g2)}")
        if self.g2:
            self.stop(1, "gate 2 failed")

    def stage_export(self):
        self.cur = 9
        from vsp import captions, exporters, schema as vschema
        with self.span("stage.export") as sp:
            errs = vschema.validate(self.script)
            if errs:
                sp.set(schema_errors=len(errs))
                self.line(9, "FAIL", "schema: " + "; ".join(errs[:5])
                          + (f" (+{len(errs) - 5} more)" if len(errs) > 5 else ""))
                self.stop(1, "stage 9 failed")
            try:
                cues = captions.build_cues(self.script, self.shots)
                self.exports = exporters.write_exports(self.outdir, self.script,
                                                       self.shots, self.vo, cues=cues)
                lint = captions.lint(cues)
            except Exception as e:  # noqa: BLE001
                self.crash(9, f"export raised {type(e).__name__}: {e}",
                           traceback.format_exc())
                self.stop(1, "stage 9 failed")
            docs = self.write_creative_docs()
            docs += self.write_trend_doc()
            docs += self.write_render_handoff()
            sp.set(files=len(self.exports) + len(docs), cues=len(cues), lint=len(lint))
        self.warn("captions", lint)
        summary = self.creative_summary()
        self.line(9, "OK", f"{', '.join(sorted(list(self.exports) + docs))}; schema valid; "
                  f"{len(cues)} cue(s), caption lint {len(lint)} warning(s)"
                  + (f"; creative: {summary}" if summary else ""))

    def write_creative_docs(self):
        """v2.1: direction.md (vibe, tone, pacing, music, look), hooks.md (the
        A/B sheet for the alternate openings) and posting.md (keywords and
        per-platform packaging), each from its module's render_md — only for
        the keys the script carries (a legacy --script-json writes none). A
        render error is a warning; the bundle keeps its own sections."""
        import importlib
        s, written = self.script, []
        for fname, key, modname, title in CREATIVE_DOCS:
            val = s.get(key) if isinstance(s, dict) else None
            if not val:
                continue
            try:
                mod = importlib.import_module(modname)
                text = (mod.render_md(val) if key == "direction"
                        else mod.render_md(val, s))
            except Exception as e:  # noqa: BLE001 — advisory docs
                self.warnings.append(f"export: {fname} not written "
                                     f"({type(e).__name__}: {e})")
                continue
            if text and text.strip():
                head = f"# {title} — {s.get('prompt') or self.a.prompt}\n\n"
                _write(os.path.join(self.outdir, fname), head + text.rstrip() + "\n")
                written.append(fname)
        return written

    def write_trend_doc(self):
        """v2.2 (D164): trend.md — the recipe this script rides (evidence,
        what to copy, what to change, licensed audio only). Only when a
        recipe steered the run."""
        if not self.trend or self.from_json:
            return []
        try:
            from vsp.trends import steer as vst
            text = vst.brief_md(self.trend)
        except Exception as e:  # noqa: BLE001 — advisory
            self.warnings.append(f"export: trend.md not written ({type(e).__name__}: {e})")
            return []
        if not (text or "").strip():
            return []
        _write(os.path.join(self.outdir, "trend.md"),
               f"# Trend recipe — {self.a.prompt}\n\n" + text.rstrip() + "\n")
        return ["trend.md"]

    def write_render_handoff(self):
        """v2.2 (D162): render.json + voice_plan.json + render.md for the
        Antigravity render agent (Gemini Omni + Cartesia; antigravity/). A
        lane/consent error fails stage 9 loudly; check problems are
        warnings. The trend recipe (if any) rides along for the editor."""
        from vsp import render as vrender
        a = self.a
        try:
            names = vrender.write(
                self.outdir, self.script, self.shots,
                script_sha=_sha256_file(os.path.join(self.outdir, "script.json")),
                voice_lane=a.voice_lane, ai_broll=bool(a.ai_broll),
                consent_ref=a.consent_ref, voice_id=a.voice_id)
        except ValueError as e:
            self.crash(9, f"render hand-off: {e}")
            self.stop(1, "stage 9 failed")
        rp = os.path.join(self.outdir, "render.json")
        try:
            with open(rp, encoding="utf-8") as f:
                r = json.load(f)
            with open(os.path.join(self.outdir, "voice_plan.json"), encoding="utf-8") as f:
                vp = json.load(f)
            probs = vrender.check_render(r, self.script) + vrender.check_voice_plan(vp, self.script)
            if self.trend:
                t = self.trend
                r["trend"] = {k: t.get(k) for k in (
                    "recipe_id", "title", "operator", "stage", "trend_keys",
                    "beats_note", "audio_note", "text_note", "participation_note",
                    "originality", "risk")}
                with open(rp, "w", encoding="utf-8") as f:
                    json.dump(r, f, indent=1, ensure_ascii=False)
                    f.write("\n")
        except (OSError, ValueError) as e:
            probs = [f"render hand-off unreadable: {e}"]
        self.warn("render", probs)
        return list(names)

    def creative_summary(self):
        """One line for the stage-9 report: vibe/tone, the openings, the
        search keyword."""
        s = self.script if isinstance(self.script, dict) else {}
        parts = []
        d = s.get("direction") if isinstance(s.get("direction"), dict) else {}
        if d.get("vibe"):
            tone = d.get("tone") if isinstance(d.get("tone"), dict) else {}
            parts.append(f"vibe {d['vibe']}" + (f", tone {tone['voice']}"
                                                  if tone.get("voice") else ""))
        hv = [v for v in (s.get("hook_variants") or []) if isinstance(v, dict)]
        if hv:
            arcs = [str(v.get("archetype")) for v in hv]
            parts.append(f"{len(hv)} openings ({'/'.join(v.get('id') or '?' for v in hv)}: "
                         f"{', '.join(arcs)})")
        disc = s.get("discovery") if isinstance(s.get("discovery"), dict) else {}
        if disc.get("primary_keyword"):
            parts.append(f"keyword {disc['primary_keyword']!r}")
        tr = s.get("trend") if isinstance(s.get("trend"), dict) else {}
        if tr.get("recipe_id"):
            parts.append(f"trend {tr['recipe_id']} ({tr.get('operator')}, {tr.get('stage')})")
        return "; ".join(parts)

    # ------------------------------------------------------------ finish
    def status(self, code):
        if code == 0:
            return "pass"
        if self.crashed:
            return "crash"
        if self.input_rejected:
            return "input_error"
        if self.failed_stage == 4 or (self.g1 and self.g2 is None):
            return "gate1_fail"
        if self.failed_stage == 8 or self.g2:
            return "gate2_fail"
        return "fail"

    def script_summary(self):
        s = self.script
        sp = os.path.join(self.outdir, "script.json")
        if not isinstance(s, dict) or not os.path.isfile(sp):
            return None
        try:
            from vsp.rubric import hook_line
            hook = hook_line(s)
        except Exception:  # noqa: BLE001
            hook = None
        d = s.get("direction") if isinstance(s.get("direction"), dict) else {}
        tone = d.get("tone") if isinstance(d.get("tone"), dict) else {}
        hv = [v for v in (s.get("hook_variants") or []) if isinstance(v, dict)]
        prim = next((v for v in hv if v.get("is_primary")), hv[0] if hv else {})
        disc = s.get("discovery") if isinstance(s.get("discovery"), dict) else {}
        return {"prompt": s.get("prompt"), "niche": s.get("niche"),
                "hook_family": s.get("hook_family"),
                "hook_source": s.get("hook_source"), "hook": hook,
                "presenter": s.get("presenter"), "format": s.get("format"),
                "duration_s": s.get("duration_s"),
                "seed": s.get("seed") if self.from_json else self.a.seed,
                "candidate_seed": (self.selected or {}).get("seed"),
                "script_sha256": _sha256_file(sp),
                # v2.1 creative layer (None when the script has no such key):
                # what vsp.feedback links a posted reel's metrics back to
                "vibe": d.get("vibe"), "tone": tone.get("voice"),
                "hook_archetype": prim.get("archetype"),
                "visual_type": prim.get("visual_type"),
                "variant_ids": [v.get("id") for v in hv] or None,
                "primary_keyword": disc.get("primary_keyword"),
                # v2.2: the trend recipe that steered the script (D164)
                "trend_recipe_id": ((s.get("trend") or {}).get("recipe_id")
                                    if isinstance(s.get("trend"), dict) else None)}

    def gate_report(self, code, status):
        cands = []
        for c in (self.sel or {}).get("candidates") or []:
            cands.append({k: c.get(k) for k in ("index", "seed", "passed", "rank",
                                                "error", "gate1", "rubric", "hook")})
        reps = [{"candidate": r.get("candidate"), "seed": r.get("seed"),
                 "passed": r.get("passed"), "error": r.get("error"),
                 "rounds": max([e.get("round", 0) for e in r.get("log") or []] or [0]),
                 "rules": sorted({str(e.get("rule")) for e in r.get("log") or []
                                  if e.get("rule") not in ("regate", "none", "sync")})}
                for r in self.repairs]

        def gate(res, warns):
            return {"result": None if res is None else ("PASS" if not res else "FAIL"),
                    "errors": list(res or []), "warnings": list(warns or [])}
        return {"schema_version": 1, "prompt": self.a.prompt, "status": status,
                "exit_code": code,
                "failed_stage": (None if self.failed_stage is None else
                                 {"n": self.failed_stage,
                                  "name": STAGES[self.failed_stage]}),
                "stages": [self.stages[n] for n in sorted(self.stages)],
                "gate1": gate(self.g1, self.g1_warn),
                "gate2": gate(self.g2, self.g2_warn),
                "selected": self.selected, "candidates": cands, "repairs": reps,
                "llm_judge": self.llm_judge, "warnings": list(self.warnings)}

    def finish(self, code):
        reason = self.skip_reason or "earlier stage failed"
        for n in range(1, 10):
            if n not in self.stages:
                self.line(n, "SKIPPED", reason)
        idx10 = len(self.report)
        self.line(10, "OK", "manifest.json, trace.jsonl, gate-report.json "
                  "(written after this report)")
        self.report.append("")
        self.report.append("warnings:" if self.warnings else "warnings: none")
        self.report += [f"- {w}" for w in self.warnings]
        report_path = os.path.join(self.outdir, "validation-report.md")
        _write(report_path, "\n".join(self.report))
        status = self.status(code)
        rub = None
        try:
            if isinstance(self.script, dict):
                from vsp import rubric
                r = rubric.score(self.script)
                rub = {k: r.get(k) for k in ("score", "selection_score",
                                             "audit_score", "compliance_flags")}
        except Exception:  # noqa: BLE001
            rub = None
        try:
            self.cur = 10
            from vsp import manifest as vman
            with self.span("stage.manifest"):
                gr = self.gate_report(code, status)
                gr["rubric"] = rub
                with open(os.path.join(self.outdir, "gate-report.json"), "w",
                          encoding="utf-8") as f:
                    json.dump(gr, f, indent=1, ensure_ascii=False, default=str)
                    f.write("\n")
                sel = self.sel or {}
                m = vman.build_manifest(
                    argv=self.argv, args=self.args_record,
                    seed=(self.script or {}).get("seed") if self.from_json else self.a.seed,
                    candidate_seeds=sel.get("seeds") or [],
                    research_pack=config.research_pack_path(), route=self.route,
                    research=self.pack_meta, candidates=sel.get("candidates") or [],
                    selected=self.selected, repairs=self.repairs,
                    gates={"gate1": self.g1, "gate2": self.g2,
                           "gate1_warnings": self.g1_warn,
                           "gate2_warnings": self.g2_warn},
                    outdir=self.outdir, timings_ms=self.tr.timings_ms(),
                    exit_code=code, status=status,
                    stages=[self.stages[n] for n in sorted(self.stages)],
                    script_summary=self.script_summary(), rubric=rub,
                    learned=learned_state(),
                    env={k: os.environ.get(k) for k in ENV_KEYS},
                    llm_judge=self.llm_judge, warnings=self.warnings)
                vman.write_manifest(self.outdir, m)
            self.tr.close()
        except Exception:  # noqa: BLE001 — the run's own record failed: loud
            self.report[idx10] = (f"STAGE 10 FAILED ({STAGES[10]}): manifest/trace "
                                  f"write failed\n" + _tail(traceback.format_exc()))
            self.stages[10] = {"n": 10, "name": STAGES[10], "status": "FAIL",
                               "detail": "manifest/trace write failed", "crash": True}
            _write(report_path, "\n".join(self.report))
            code, status = 1, "crash"
            try:
                self.tr.close()
            except Exception:  # noqa: BLE001
                pass
        if (code == 0 and self.trend and not self.from_json
                and not getattr(self.a, "trend_json", None)):
            # v2.2 (D164): a shipped recipe loses novelty for the next picks
            # (a --trend-json replay never marks it twice)
            try:
                from vsp.trends import steer as vst
                vst.mark_used(self.trend.get("recipe_id"), dataset_dir=self.a.trends_dir,
                              script_sha=_sha256_file(os.path.join(self.outdir,
                                                                   "script.json")))
            except Exception as e:  # noqa: BLE001 — advisory, never fails a run
                self.warnings.append(f"trends: mark_used failed ({type(e).__name__}: {e})")
        if self.a.json:
            winner = None
            if self.selected:
                winner = dict(self.selected)
            print(json.dumps({
                "status": status, "exit_code": code, "outdir": self.outdir,
                "artifacts": [f for f in ARTIFACTS
                              if os.path.isfile(os.path.join(self.outdir, f))],
                "winner": winner, "rubric": rub,
                "route": (self._route_summary() if self.route else None),
                "warnings": list(self.warnings),
                "gates": {"gate1": self.g1, "gate2": self.g2},
                "failed_stage": (None if self.failed_stage is None
                                 else STAGES[self.failed_stage]),
                "stages": [f"{s['n']} {s['name']}: {s['status']}"
                           for s in (self.stages[n] for n in sorted(self.stages))],
                "script_summary": self.script_summary(),
            }, indent=1, ensure_ascii=False, default=str))
        else:
            print("\n".join(self.report))
        sys.exit(code)

    def _route_summary(self):
        try:
            from vsp import router
            return router.summary_line(self.route)
        except Exception:  # noqa: BLE001
            return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt", nargs="?",
                    help="product prompt (not needed with --self-test)")
    ap.add_argument("--presenter", default="human", choices=["ai", "human"])
    ap.add_argument("--format", default=None,
                    choices=["demo", "talking-head", "pov-vlog", "transformation", "review"],
                    help="default demo (or the trend recipe's format when --format is not given)")
    ap.add_argument("--duration", type=int, default=None,
                    help="target video length in seconds (5-180, default 30, or the "
                         "trend recipe's when --duration is not given)")
    ap.add_argument("--seed", type=int, default=701)
    ap.add_argument("--persona", default=None,
                    help="house AI persona from personas.json (default: maya for --presenter ai)")
    ap.add_argument("--no-research", action="store_true",
                    help="frozen-rulebook output: ignore research_pack.json")
    ap.add_argument("--out-dir", default=None,
                    help="write artifacts here instead of outputs/<slug>/")
    ap.add_argument("--script-json", default=None,
                    help="skip the maker and run a finished script JSON through the gates")
    ap.add_argument("--self-test", action="store_true",
                    help="run the gates against known-good and known-bad fixtures")
    ap.add_argument("--candidates", type=int, default=8,
                    help="best-of-N candidates (D149; candidate 0 = the raw --seed, "
                         "so 1 reproduces pre-2.0 output; default 8)")
    ap.add_argument("--replay", default=None, metavar="MANIFEST",
                    help="re-run a recorded run and check the script.json hash (D153)")
    ap.add_argument("--strict-route", action="store_true",
                    help="fail stage 1 when the 3-voter router is split (D147)")
    ap.add_argument("--require-fresh-research", action="store_true",
                    help="fail stage 2 on a stale (>48 h) or missing research pack (D148)")
    ap.add_argument("--llm-judge", action="store_true",
                    help="advisory LLM pairwise judge of the top-2 candidates "
                         "(recorded in the manifest; never changes the winner)")
    ap.add_argument("--json", action="store_true",
                    help="print one JSON summary to stdout instead of the report")
    # v2.2 trend intelligence (vsp.trends) and the render hand-off (vsp.render)
    ap.add_argument("--trend", default="auto", metavar="auto|none|RECIPE_ID",
                    help="steer ties with a trend recipe from the trends dataset "
                         "(default auto: the best fitting recent recipe; a no-op "
                         "without a dataset; D164)")
    ap.add_argument("--trends-dir", default=None,
                    help="trends dataset (default $VSP_TRENDS_DIR or ~/viral-trends-db)")
    ap.add_argument("--trend-json", default=None,
                    help="a recorded trend.json (replay pin; overrides --trend)")
    ap.add_argument("--voice-lane", default=None,
                    choices=["ai_persona", "creator_clone", "real_voice"],
                    help="render hand-off voice lane (default: ai_persona for "
                         "--presenter ai, real_voice for human; D162)")
    ap.add_argument("--ai-broll", action="store_true",
                    help="human lane: let the render agent generate faceless "
                         "product B-roll (turns the AI labels on)")
    ap.add_argument("--consent-ref", default=None,
                    help="consent record id, required for --voice-lane creator_clone")
    ap.add_argument("--voice-id", default=None,
                    help="Cartesia voice id for voice_plan.json (else the plan "
                         "says how to pick one)")
    argv = sys.argv[1:]
    a = ap.parse_args(argv)
    args_record = dict(vars(a))   # before any mutation (manifest + --replay)

    if a.self_test:
        sys.exit(self_test())
    if a.replay:
        sys.exit(replay_main(a.replay, as_json=a.json))
    if not a.prompt and not a.script_json:
        ap.error("a prompt is required (or --script-json PATH / --self-test)")
    if a.voice_lane == "creator_clone" and not a.consent_ref:
        ap.error("--voice-lane creator_clone needs --consent-ref (the creator's "
                 "recorded consent to clone their voice; D162)")
    # v2.2: the trend recipe is resolved before routing, so a recipe's
    # format/duration apply when the user left them unset (explicit wins)
    steer, trend_note = (None, "n/a (--script-json)") if a.script_json else resolve_trend(a)
    if steer:
        if a.format is None and steer.get("format"):
            a.format = steer["format"]
        if a.duration is None and steer.get("duration_s"):
            a.duration = int(steer["duration_s"])
    a.format = a.format or "demo"
    a.duration = 30 if a.duration is None else a.duration
    if not 5 <= a.duration <= 180:
        ap.error("--duration must be between 5 and 180 seconds")
    if not 1 <= a.candidates <= MAX_CANDIDATES:
        ap.error(f"--candidates must be between 1 and {MAX_CANDIDATES}")

    # Input: a finished JSON, or the maker
    script = None
    if a.script_json:
        try:
            with open(a.script_json, encoding="utf-8") as f:
                script = json.load(f)
        except (OSError, ValueError) as e:
            ap.error(f"--script-json: cannot read {a.script_json}: {e}")
        if not isinstance(script, dict):
            ap.error("--script-json must hold a JSON object")
        # D63: hand-finished scripts get the spoken-voice pass too — the bundle
        # renders the final spoken strings, so gates must measure those.
        for b in script.get("beats", []) + script.get("hook_stack", []):
            if not isinstance(b, dict):
                continue
            if b.get("dialogue"):
                b["dialogue"] = humanize_dialogue(b["dialogue"])
            if b.get("rehook"):
                b["rehook"] = humanize_dialogue(b["rehook"])
        a.prompt = script.get("prompt") or a.prompt or "x"
        # D79: validation is read-only on the input. Deriving the outdir from
        # the JSON's own prompt used to point it back at the input file's home
        # directory, silently overwriting the source script.json (and its
        # validation report) with the humanized copy — this ate the
        # hair-wax-stick passing fixture in gauntlet cycle 3. Validate into an
        # isolated directory instead.
        outdir = a.out_dir or os.path.join(config.outputs_dir(),
                                           _slug(a.prompt) + "-json-check")
        header = (f"seed {script.get('seed', 'n/a')} | {script.get('presenter', '?')} | "
                  f"{script.get('format', '?')} | {script.get('duration_s', 30)}s")
    else:
        outdir = a.out_dir or os.path.join(config.outputs_dir(), _slug(a.prompt))
        header = f"seed {a.seed} | {a.presenter} | {a.format} | {a.duration}s"
    outdir = os.path.abspath(outdir)
    if a.script_json and os.path.abspath(a.script_json) in {
            os.path.join(outdir, f) for f in ARTIFACTS}:
        print(f"D79: refusing to validate into {outdir} — it would overwrite "
              f"the input {a.script_json}. Pick another --out-dir.")
        sys.exit(2)
    os.makedirs(outdir, exist_ok=True)
    # a failing run must never leave a stale bundle/brief/export from an earlier run
    for f in ARTIFACTS:
        p = os.path.join(outdir, f)
        if os.path.isfile(p):
            os.remove(p)
    if not a.script_json:
        # replay pin: --replay re-applies this exact recipe (or none), never
        # whatever the dataset holds on the replay day
        if steer:
            tj = os.path.join(outdir, "trend.json")
            with open(tj, "w", encoding="utf-8") as f:
                json.dump(steer, f, indent=1, ensure_ascii=False, sort_keys=True)
                f.write("\n")
            args_record["trend"], args_record["trend_json"] = None, tj
        else:
            args_record["trend"], args_record["trend_json"] = "none", None
    r = Run(a, args_record, argv, outdir, script=script)
    r.trend, r.trend_note = steer, trend_note
    r.report += [f"# Validation report — {a.prompt}", header, f"trend: {trend_note}", ""]
    r.execute()


def resolve_trend(a):
    """-> (steer dict | None, note) for this run (D164). --trend-json (a
    recorded trend.json, the replay pin) wins; --trend none -> None; else
    vsp.trends.steer.for_run (auto: the best fitting recipe of the latest
    batch; or a recipe id). Read-only, never raises, None without a dataset."""
    if a.trend_json:
        try:
            with open(a.trend_json, encoding="utf-8") as f:
                st = json.load(f)
        except (OSError, ValueError) as e:
            return None, f"--trend-json unreadable ({e})"
        if isinstance(st, dict) and st.get("recipe_id"):
            return st, f"{st['recipe_id']} (pinned by --trend-json)"
        return None, "none (pinned by --trend-json)"
    t = str(a.trend or "auto").strip()
    if t.lower() == "none":
        return None, "off (--trend none)"
    if (t.lower() == "auto" and os.environ.get("VSP_FIXTURE_OK") == "1"
            and not a.trends_dir):
        # evaluations (self-test, scorecards, vsp.improve) run in fixture
        # mode and must never be steered by whatever dataset the machine
        # holds; an explicit --trends-dir still tests steering (D164)
        return None, ("off in fixture mode (VSP_FIXTURE_OK=1 without "
                      "--trends-dir: evaluations stay trend-free)")
    try:
        from vsp.trends import steer as vst
        st = vst.for_run(a.prompt, presenter=a.presenter, fmt=a.format,
                         dataset_dir=a.trends_dir,
                         recipe_id=None if t.lower() == "auto" else t)
    except Exception as e:  # noqa: BLE001 — trends are advisory
        return None, f"trend lookup failed ({type(e).__name__}: {e})"
    if not st:
        return None, ("no fitting recipe (no dataset, a stale batch, or none "
                      "feasible)" if t.lower() == "auto"
                      else f"recipe {t} not found or not feasible for --presenter "
                           f"{a.presenter}")
    return st, (f"{st['recipe_id']} — {st.get('title')} ({st.get('operator')}, "
                f"{st.get('stage')}, score {st.get('score')})")


def _slug(prompt):
    """slugify(), capped so a long prompt cannot exceed the filesystem's
    name limit (the router rejects > 300 chars; the report must still land)."""
    s = slugify(prompt)
    return s if len(s) <= 200 else s[:200].rstrip("-")


if __name__ == "__main__":
    main()
