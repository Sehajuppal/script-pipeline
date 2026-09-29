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
sync, a brief make_shotlist can never emit, ...), run after the pipeline
cases.
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
from vsp.selftest_cases import all_cases, unit_cases


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
    before_tree = _tree_digest(repo_outputs)
    env = dict(os.environ,
               VSP_OUTPUTS=os.path.join(tmp, "outputs"),
               VSP_VIRAL_DB=build_fixture_db(os.path.join(tmp, "viral.db")),
               VSP_FIXTURE_OK="1", PYTHONDONTWRITEBYTECODE="1",
               PYTHONIOENCODING="utf-8")
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
    # hermeticity: the repo's outputs/ tree must be untouched
    if _tree_digest(repo_outputs) != before_tree:
        fails.append("hermeticity: self-test modified the repo's outputs/")
    if not keep:
        shutil.rmtree(tmp, ignore_errors=True)
    if fails:
        print("SELF-TEST FAILED:\n" + "\n".join(fails))
        return 1
    print(f"self-test: all {len(cases)} gate cases + {len(units)} unit checks "
          f"+ no-clobber behave correctly (hermetic: repo outputs/ untouched)")
    return 0
