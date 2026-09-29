#!/usr/bin/env python3
"""pipeline.py — the production pipeline. Everything goes through it.

    python3 pipeline.py "<product>" [--presenter ai|human] [--format ...]
        [--duration 30] [--seed N] [--no-research] [--out-dir DIR]

Stages:
  1. viral_script_maker.generate -> script JSON
  2. GATE 1 (script-level checks; fail loudly)
  3. make_shotlist.build_bundle  -> bundle (shot list + Antigravity brief)
  4. GATE 2 (brief-level checks; fail loudly)

Outputs (outputs/<slug>/ or --out-dir):
  script.json, bundle.md, brief.md (Antigravity brief incl. shot list),
  validation-report.md

Exit code is non-zero when any gate fails. No silent passes.
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

ARTIFACTS = ("script.json", "bundle.md", "brief.md", "validation-report.md")


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt", nargs="?",
                    help="product prompt (not needed with --self-test)")
    ap.add_argument("--presenter", default="human", choices=["ai", "human"])
    ap.add_argument("--format", default="demo",
                    choices=["demo", "talking-head", "pov-vlog", "transformation", "review"])
    ap.add_argument("--duration", type=int, default=30,
                    help="target video length in seconds (5-180, default 30)")
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
    a = ap.parse_args()

    if a.self_test:
        sys.exit(self_test())
    if not a.prompt and not a.script_json:
        ap.error("a prompt is required (or --script-json PATH / --self-test)")
    if not 5 <= a.duration <= 180:
        ap.error("--duration must be between 5 and 180 seconds")

    # Stage 1 input: a finished JSON, or the maker
    script = None
    if a.script_json:
        with open(a.script_json, encoding="utf-8") as f:
            script = json.load(f)
        # D63: hand-finished scripts get the spoken-voice pass too — the bundle
        # renders the final spoken strings, so gates must measure those.
        for b in script.get("beats", []) + script.get("hook_stack", []):
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
                                           slugify(a.prompt) + "-json-check")
        header = (f"seed {script.get('seed', 'n/a')} | {script.get('presenter', '?')} | "
                  f"{script.get('format', '?')} | {script.get('duration_s', 30)}s")
    else:
        outdir = a.out_dir or os.path.join(config.outputs_dir(), slugify(a.prompt))
        header = f"seed {a.seed} | {a.presenter} | {a.format} | {a.duration}s"
    outdir = os.path.abspath(outdir)
    if a.script_json and os.path.abspath(a.script_json) in {
            os.path.join(outdir, f) for f in ARTIFACTS}:
        print(f"D79: refusing to validate into {outdir} — it would overwrite "
              f"the input {a.script_json}. Pick another --out-dir.")
        sys.exit(2)
    os.makedirs(outdir, exist_ok=True)
    # a gate failure must never leave a stale bundle/brief from an earlier run
    for f in ARTIFACTS:
        p = os.path.join(outdir, f)
        if os.path.isfile(p):
            os.remove(p)
    report = [f"# Validation report — {a.prompt}", header, ""]
    report_path = os.path.join(outdir, "validation-report.md")

    def finish(code):
        _write(report_path, "\n".join(report))
        print("\n".join(report))
        sys.exit(code)

    if script is None:
        try:
            import viral_script_maker as vsm
            script = vsm.generate(a.prompt, presenter=a.presenter, fmt=a.format,
                                  duration=a.duration, seed=a.seed,
                                  use_research=not a.no_research,
                                  persona=a.persona)
            script = json.loads(json.dumps(script))  # plain JSON types only
        except Exception:
            report.append(f"STAGE 1 FAILED: maker error\n{traceback.format_exc()[-500:]}")
            finish(1)
        report.append("stage 1 (script): OK")
    else:
        report.append("stage 1 (script): BYPASSED — finished JSON supplied")
    with open(os.path.join(outdir, "script.json"), "w", encoding="utf-8") as f:
        json.dump(script, f, indent=1, ensure_ascii=False)

    # Gate 1
    g1 = gate1(script)
    report.append(f"gate 1 (script): {'PASS' if not g1 else 'FAIL — ' + '; '.join(g1)}")
    if g1:
        finish(1)

    # Stage 2: bundle
    try:
        import make_shotlist
        bundle_text, _shots, _vo = make_shotlist.build_bundle(script)
    except Exception:
        report.append(f"STAGE 2 FAILED: {traceback.format_exc()[-500:]}")
        finish(1)
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
    report.append("stage 2 (bundle): OK")

    # Gate 2
    g2 = gate2(bundle_text, script)
    report.append(f"gate 2 (brief): {'PASS' if not g2 else 'FAIL — ' + '; '.join(g2)}")
    finish(1 if g2 else 0)


if __name__ == "__main__":
    main()
