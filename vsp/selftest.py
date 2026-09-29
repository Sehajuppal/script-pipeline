"""Hermetic self-test: the gates must pass the good fixture and fail every bad
fixture loudly — without touching the repo.

pre-2.0 the self-test wrote into git-tracked outputs/test-product*/ and
outputs/x/, and gate 2 needed the private ~/workspace viral.db, so it could
only be green on one machine. Now every child run gets:
  VSP_OUTPUTS   -> <tmp>/outputs        (outputs never land in the repo)
  VSP_VIRAL_DB  -> <tmp>/fixture viral.db (vsp/fixtures.py)
  VSP_FIXTURE_OK=1                       (FIXTURE reels allowed, D151)
and the runner asserts the repo's outputs/ tree is byte-for-byte unchanged.

Cases (vsp/selftest_cases.py) are (name, script, want_pass, want_msgs) —
the 17 legacy tuples are untouched — optionally with a 5th element of
options for pipeline-v2 cases:
  {"only": "D136"}              every failure message must start with D136
  {"env": {"VSP_FIXTURE_OK": None}}  per-case env override (None = unset)
unit_cases() are in-process contract checks (registry order, DELIVERABLE
sync, a brief make_shotlist can never emit, the learned-state readers, ...),
run after the pipeline cases. e2e_checks() are full 10-stage CLI runs
(fn(harness) -> [problems]); every child also reads an empty temp learned/
dir. Last, OPTIONAL_SELFCHECKS (vsp.ingest, vsp.feedback, vsp.improve —
built on other branches) run in a child each when importlib.util.find_spec
finds them: selfcheck() -> (ok, lines) must return ok; an absent module (or
one without selfcheck()) is only noted.

Pipeline v2.1 (WS-EVAL, RULES.md §68): creative_cases() add the D154 / D155
/ D156 / D158 gate-1 cases (synthetic contract-valid direction /
hook_variants / discovery + one failing case per clause); the v21-* unit
checks build a synthetic v2.1 brief for D157 / D159 / D160 and cover the
R21-R28 rubric, vsp.creative_eval and the schema $defs; e2e-creative-keys
runs once vsp.direction / vsp.hooks / vsp.discovery exist (else it is
noted as skipped); OPTIONAL_SELFCHECKS also lists vsp.direction, vsp.hooks,
vsp.discovery and vsp.shotplan. Checks may leave notes in h.state["notes"]
(printed with the summary line).
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

from vsp import config
from vsp.fixtures import build_fixture_db
from vsp.selftest_cases import (OPTIONAL_SELFCHECKS, all_cases, e2e_checks,
                                unit_cases)


def _tree_digest(root):
    h = hashlib.sha256()
    if not os.path.isdir(root):
        return "absent"
    for dp, dns, fns in sorted(os.walk(root)):
        dns.sort()
        for fn in sorted(fns):
            p = os.path.join(dp, fn)
            h.update(os.path.relpath(p, root).encode())
            with open(p, "rb") as f:
                h.update(hashlib.sha256(f.read()).digest())
        h.update(b"dir:" + os.path.relpath(dp, root).encode())
    return h.hexdigest()


def _run(cmd, env):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                          env=env)


_GATE_LINE = re.compile(r"^gate [12] \((?:script|brief)\): FAIL — (.*)$", re.M)


def _gate_messages(stdout):
    """Failure messages from the report's gate lines ('; '-joined)."""
    return [m.strip() for line in _GATE_LINE.findall(stdout)
            for m in line.split("; ") if m.strip()]


class _Harness:
    """What the end-to-end checks (selftest_cases.e2e_checks) get: full
    pipeline runs in the hermetic env, fresh temp dirs, shared state."""

    def __init__(self, pipeline_path, tmp, env):
        self.pipeline, self.tmp, self.env = pipeline_path, tmp, env
        self.repo = config.REPO
        self.state = {}

    def _env(self, learned=None, env=None):
        e = dict(self.env)
        if learned:
            e["VSP_LEARNED_DIR"] = learned
        for k, v in (env or {}).items():      # per-run overrides; None = unset
            if v is None:
                e.pop(k, None)
            else:
                e[k] = str(v)
        return e

    def run(self, args, learned=None, timeout=300, env=None):
        return subprocess.run([sys.executable, self.pipeline] + list(args),
                              capture_output=True, text=True, timeout=timeout,
                              env=self._env(learned, env))

    def py(self, code, learned=None, timeout=300, args=(), env=None):
        return subprocess.run([sys.executable, "-c", code] + list(args),
                              capture_output=True, text=True, timeout=timeout,
                              env=self._env(learned, env))

    def out(self, name):
        p = os.path.join(self.tmp, "e2e", name)
        shutil.rmtree(p, ignore_errors=True)
        return p

    def learned(self, name):
        p = os.path.join(self.tmp, "learned-" + name)
        shutil.rmtree(p, ignore_errors=True)
        os.makedirs(os.path.join(p, "hook_packs"))
        return p


# Runs one optional module's selfcheck() -> (ok, lines) in a child process
# (isolated globals/env; the module may be a package with a selfcheck
# submodule). The result follows a marker line (the check may print).
_SELFCHECK_CODE = r"""
import importlib, json, sys, types
sys.path.insert(0, sys.argv[1])
name = sys.argv[2]
mod = importlib.import_module(name)
fn = getattr(mod, "selfcheck", None)
if isinstance(fn, types.ModuleType):
    fn = getattr(fn, "selfcheck", None)
if fn is None:
    try:
        fn = getattr(importlib.import_module(name + ".selfcheck"), "selfcheck", None)
    except ModuleNotFoundError as e:
        if e.name != name + ".selfcheck":
            raise
        fn = None
if not callable(fn):
    print("\n@@SELFCHECK@@" + json.dumps({"skip": "no selfcheck()"}))
    sys.exit(0)
res = fn()
ok, lines = res
print("\n@@SELFCHECK@@" + json.dumps({"ok": bool(ok),
                                      "lines": [str(x) for x in (lines or [])]}))
"""


def _optional_selfchecks(h):
    """-> (problems, notes). A module that is absent is fine; one that
    exists must import and its selfcheck() must return ok."""
    import importlib.util
    probs, notes = [], []
    for name in OPTIONAL_SELFCHECKS:
        try:
            spec = importlib.util.find_spec(name)
        except (ImportError, ValueError):
            spec = None
        if spec is None:
            notes.append(f"{name} absent")
            continue
        try:
            r = h.py(_SELFCHECK_CODE, timeout=900, args=(h.repo, name))
        except subprocess.TimeoutExpired:
            probs.append(f"selfcheck {name}: timed out")
            continue
        blob = r.stdout.rsplit("@@SELFCHECK@@", 1)
        try:
            res = json.loads(blob[1]) if len(blob) == 2 else None
        except ValueError:
            res = None
        if r.returncode != 0 or not isinstance(res, dict):
            probs.append(f"selfcheck {name}: exit {r.returncode}\n"
                         f"{r.stdout[-400:]}{r.stderr[-600:]}")
        elif res.get("skip"):
            notes.append(f"{name} {res['skip']}")
        elif not res.get("ok"):
            probs.append(f"selfcheck {name}: not ok\n  " +
                         "\n  ".join(res.get("lines", [])[-15:]))
        else:
            notes.append(f"{name} ok ({len(res.get('lines', []))} lines)")
    return probs, notes


def _case_env(env, opts):
    out = dict(env)
    for k, v in (opts.get("env") or {}).items():
        if v is None:
            out.pop(k, None)
        else:
            out[k] = str(v)
    return out


def run(pipeline_path, keep=False):
    tmp = tempfile.mkdtemp(prefix="pipe_selftest_")
    repo_outputs = os.path.join(config.REPO, "outputs")
    repo_learned = os.path.join(config.REPO, "learned")
    before_tree = _tree_digest(repo_outputs)
    before_learned = _tree_digest(repo_learned)
    # WS-INT: children read an empty temp learned/ (no priors, no packs), so
    # the self-test never depends on — or writes — the repo's learned state
    learned = os.path.join(tmp, "learned")
    os.makedirs(os.path.join(learned, "hook_packs"))
    env = dict(os.environ,
               VSP_OUTPUTS=os.path.join(tmp, "outputs"),
               VSP_VIRAL_DB=build_fixture_db(os.path.join(tmp, "viral.db")),
               VSP_FIXTURE_OK="1", PYTHONDONTWRITEBYTECODE="1",
               PYTHONIOENCODING="utf-8", VSP_LEARNED_DIR=learned)
    for k in ("VSP_NO_HOOK_PACKS", "VSP_NO_PRIORS"):
        env.pop(k, None)
    good, cases = all_cases()
    fails = []
    for case in cases:
        name, script, want_pass, want_msgs = case[:4]
        opts = case[4] if len(case) > 4 else {}
        p = os.path.join(tmp, name + ".json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(script, f)
        r = _run([sys.executable, pipeline_path,
                  script.get("prompt", "x"), "--script-json", p],
                 _case_env(env, opts))
        ok = (r.returncode == 0) == want_pass
        if not want_pass:
            ok = ok and all(m in r.stdout for m in want_msgs)
            if opts.get("only"):
                stray = [m for m in _gate_messages(r.stdout)
                         if not m.startswith(opts["only"])]
                if stray:
                    ok = False
                    want_msgs = list(want_msgs) + [f"ONLY {opts['only']}; "
                                                   f"stray: {stray}"]
        if not ok:
            fails.append(f"{name}: expected "
                         f"{'pass' if want_pass else 'fail(' + ','.join(want_msgs) + ')'}, "
                         f"got exit {r.returncode}\n{r.stdout[:400]}{r.stderr[-400:]}")
    # in-process contract checks (no files written)
    units = unit_cases()
    for name, fn in units:
        try:
            probs = fn()
        except Exception as e:  # noqa: BLE001 — a crashing check is a failure
            probs = [f"crashed: {type(e).__name__}: {e}"]
        fails += [f"unit {name}: {pr}" for pr in probs]
    # D79: --script-json must never rewrite the input file, even when the
    # input lives under outputs/<prompt-slug>/ (cycle-3 incident that
    # overwrote outputs/hair-wax-stick/script.json). Now inside the tmp
    # outputs root, never the repo's.
    noclob_dir = os.path.join(env["VSP_OUTPUTS"], "test-product")
    os.makedirs(noclob_dir, exist_ok=True)
    noclob = os.path.join(noclob_dir, "script.json")
    with open(noclob, "w", encoding="utf-8") as f:
        json.dump(good, f)
    with open(noclob, "rb") as f:
        before = f.read()
    # gauntlet cycle 4: --script-json without a positional prompt must not
    # crash — the prompt is re-derived from the JSON, so omit the arg here.
    r = _run([sys.executable, pipeline_path, "--script-json", noclob], env)
    with open(noclob, "rb") as f:
        if f.read() != before:
            fails.append("no-clobber: --script-json rewrote the input file")
    if r.returncode != 0:
        fails.append(f"no-clobber: good fixture should still pass, got exit "
                     f"{r.returncode}\n{r.stdout[:400]}{r.stderr[-400:]}")
    # --out-dir pointing at the input's own directory must be refused (D79)
    r = _run([sys.executable, pipeline_path, "--script-json", noclob,
              "--out-dir", noclob_dir], env)
    with open(noclob, "rb") as f:
        if f.read() != before:
            fails.append("no-clobber: --out-dir onto the input rewrote it")
    # WS-INT: full 10-stage runs (normal run, seed parity, replay, --json,
    # hook packs, priors, repair, loud failure), then the other workstreams'
    # optional selfcheck()s
    h = _Harness(pipeline_path, tmp, env)
    e2e = e2e_checks()
    for name, fn in e2e:
        try:
            probs = fn(h)
        except Exception as e:  # noqa: BLE001 — a crashing check is a failure
            probs = [f"crashed: {type(e).__name__}: {e}"]
        fails += [f"e2e {name}: {pr}" for pr in probs]
    sc_fails, sc_notes = _optional_selfchecks(h)
    fails += sc_fails
    sc_notes = list(h.state.get("notes", [])) + sc_notes   # e2e skips / scope
    # hermeticity: the repo's outputs/ and learned/ trees must be untouched
    if _tree_digest(repo_outputs) != before_tree:
        fails.append("hermeticity: self-test modified the repo's outputs/")
    if _tree_digest(repo_learned) != before_learned:
        fails.append("hermeticity: self-test modified the repo's learned/")
    if not keep:
        shutil.rmtree(tmp, ignore_errors=True)
    if fails:
        print("SELF-TEST FAILED:\n" + "\n".join(fails))
        return 1
    print(f"self-test: all {len(cases)} gate cases + {len(units)} unit checks "
          f"+ {len(e2e)} end-to-end checks + no-clobber behave correctly "
          f"(hermetic: repo outputs/ and learned/ untouched)"
          + (f"; optional selfchecks: {', '.join(sc_notes)}" if sc_notes else ""))
    return 0
