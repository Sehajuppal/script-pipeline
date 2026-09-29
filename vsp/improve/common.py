"""Shared helpers for vsp.improve: paths, clocks, JSON IO, subprocess, git.

Stdlib only; Python >= 3.9. Nothing here touches the network.
"""
import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

from vsp import config

REPO = config.REPO
GOLDEN_NAME = "golden.jsonl"
HOLDOUT_NAME = "holdout.jsonl"          # never read by evolve (fitness)
CAPABILITY_NAME = "capability.jsonl"
SUITES = ("golden", "holdout", "capability")
FORMATS = ("demo", "talking-head", "pov-vlog", "transformation", "review")
PRESENTERS = ("human", "ai")
BUDGETS = ("small", "full")
SEEDS = {"small": "1", "full": "1,2,3"}
# files automation may never weaken (verify's guard) and the yardstick
GUARDED_FILES = ("vsp/gates.py", "vsp/rules.py", "vsp/lexicon.py")
YARDSTICK_FILES = ("evals/golden.jsonl", "evals/holdout.jsonl",
                   "evals/scorecard.py", "vsp/rubric.py")
COMPLIANCE_RULES = ("D136", "D137", "D138", "D139", "D140", "D141")
KEEP_RAW = 12                            # raw scorecard files kept per dir
COPY_IGNORE = (".git", "outputs", "__pycache__", "*.pyc", "results",
               ".pytest_cache", ".worktrees")


class ImproveError(Exception):
    pass


# ------------------------------------------------------------------ paths
def evals_dir(repo=None):
    return os.path.join(repo or REPO, "evals")


def suite_path(suite, repo=None):
    return os.path.join(evals_dir(repo), f"{suite}.jsonl")


def learned_dir():
    return config.learned_dir()


def learned(*parts):
    return os.path.join(learned_dir(), *parts)


def hook_packs_dir():
    return config.hook_packs_dir()


def rel(path, root=None):
    """Repo-relative path for reports (absolute when outside the repo)."""
    try:
        r = os.path.relpath(os.path.abspath(path), root or REPO)
    except ValueError:
        return path
    return path if r.startswith("..") else r


# ------------------------------------------------------------------ clocks
def now_utc():
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)


def now_iso():
    return now_utc().isoformat()


def stamp(t=None):
    return (t or now_utc()).strftime("%Y%m%dT%H%M%SZ")


def today(t=None):
    return (t or now_utc()).strftime("%Y-%m-%d")


def parse_iso(v):
    if not isinstance(v, str) or not v.strip():
        return None
    s = v.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        d = _dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=_dt.timezone.utc)


def age_hours(iso, now=None):
    d = parse_iso(iso)
    if d is None:
        return None
    return round(((now or now_utc()) - d).total_seconds() / 3600.0, 2)


# ------------------------------------------------------------------ JSON IO
def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_text(path, text):
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return path


def write_json(path, obj):
    return write_text(path, json.dumps(obj, indent=1, ensure_ascii=False,
                                       sort_keys=False) + "\n")


def load_jsonl(path):
    """Rows of a golden-style JSONL (blank lines and // comments skipped)."""
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("//"):
                rows.append(json.loads(line))
    return rows


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def slug(s, n=48):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")[:n] or "x"


def prune(dirpath, keep=KEEP_RAW, suffix=".json"):
    """Keep only the newest `keep` files (by name — names start with a
    timestamp) in dirpath."""
    try:
        names = sorted(n for n in os.listdir(dirpath) if n.endswith(suffix))
    except OSError:
        return []
    gone = names[:-keep] if keep and len(names) > keep else []
    for n in gone:
        try:
            os.remove(os.path.join(dirpath, n))
        except OSError:
            pass
    return gone


# --------------------------------------------------------------- processes
def run(cmd, cwd=None, env=None, timeout=1800):
    """-> {rc, out, err, secs}; never raises (rc -9 on timeout, -1 on OSError)."""
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True,
                           text=True, timeout=timeout)
        rc, out, err = r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired as e:
        rc, out, err = -9, (e.stdout or "") if isinstance(e.stdout, str) else "", \
            f"timeout after {timeout}s"
    except OSError as e:
        rc, out, err = -1, "", repr(e)
    return {"rc": rc, "out": out or "", "err": err or "",
            "secs": round(time.time() - t0, 2)}


def tail(text, n=600):
    t = (text or "").strip()
    return t if len(t) <= n else "…" + t[-n:]


def pythons(prefer=("python3.9", "python3.12")):
    """Interpreters to test with: python3.9 and python3.12 when present,
    else the running interpreter."""
    out, seen = [], set()
    for name in prefer:
        p = shutil.which(name)
        if p:
            real = os.path.realpath(p)
            if real not in seen:
                seen.add(real)
                out.append(p)
    if not out:
        out.append(sys.executable)
    return out


def default_python():
    return shutil.which("python3.9") or sys.executable


def py_version(py):
    r = run([py, "-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"],
            timeout=30)
    return r["out"].strip() if r["rc"] == 0 else None


def child_env(extra=None, drop=("VSP_LEARNED_DIR",)):
    """os.environ for child runs: the engine's own learned-dir override never
    leaks into a tree under test (each tree reads its own learned/)."""
    env = dict(os.environ)
    for k in drop:
        env.pop(k, None)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for k, v in (extra or {}).items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = str(v)
    return env


# --------------------------------------------------------------------- git
def git(args, cwd=None, timeout=120):
    return run(["git"] + list(args), cwd=cwd or REPO, timeout=timeout)


def git_sha(ref="HEAD", repo=None, short=True):
    r = git(["rev-parse"] + (["--short"] if short else []) + [ref], cwd=repo)
    return r["out"].strip() if r["rc"] == 0 else None


def git_dirty(repo=None):
    r = git(["status", "--porcelain"], cwd=repo)
    return bool(r["out"].strip()) if r["rc"] == 0 else None


def git_branch(repo=None):
    r = git(["branch", "--show-current"], cwd=repo)
    return r["out"].strip() if r["rc"] == 0 else None


def copy_tree(src, dst):
    """Copy a checkout for a hermetic run (same exclusions as the
    scorecard's copy_repo: .git, outputs, caches, results)."""
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*COPY_IGNORE))
    os.makedirs(os.path.join(dst, "outputs"), exist_ok=True)
    return dst


def mkdtemp(prefix):
    base = os.environ.get("VSP_IMPROVE_TMP") or None
    if base:
        os.makedirs(base, exist_ok=True)
    return tempfile.mkdtemp(prefix=prefix, dir=base)


# ------------------------------------------------------------- self-test
def selftest(tree, pys=None, timeout=900):
    """`pipeline.py --self-test` in `tree` under each interpreter.
    -> {"ok": bool, "runs": [{python, version, rc, secs, tail}]}"""
    runs = []
    for py in pys or pythons():
        r = run([py, os.path.join(tree, "pipeline.py"), "--self-test"],
                cwd=tree, env=child_env(), timeout=timeout)
        runs.append({"python": py, "version": py_version(py), "rc": r["rc"],
                     "secs": r["secs"],
                     "tail": tail(r["out"] + ("\n" + r["err"] if r["rc"] else ""),
                                  400)})
    return {"ok": bool(runs) and all(x["rc"] == 0 for x in runs), "runs": runs}
