"""Run manifest + replay (D153) — labs-techniques §7.2, oss-pipelines §4.

    m = build_manifest(argv=sys.argv[1:], args=vars(a), seed=a.seed,
                       candidate_seeds=sel["seeds"], research_pack=pack_path,
                       route=route, research=pack_meta,
                       candidates=sel["candidates"], selected=sel["winner"],
                       repairs=repair_log, gates={"gate1": g1, "gate2": g2},
                       outdir=outdir, timings_ms=trace.timings_ms())
    write_manifest(outdir, m)                  -> <outdir>/manifest.json
    ok, details = replay(path_to_manifest)     re-runs pipeline.py, compares
                                               the script.json sha256

Manifest keys (schema_version 1): pipeline_version, created (UTC ISO), git
{sha, dirty}, python, platform, argv, args, cwd, seeds {root, candidates},
inputs {research_pack {path, sha256, generated_at}, rules_sha256,
personas_sha256, code {relative .py path: sha256}}, route, research,
candidates, selected, repairs, gates, outputs {file: sha256}, timings_ms
(+ any extra keyword part, verbatim).

Hashes: sha256 over file bytes; JSON parts via canonical_json (sorted
keys, compact separators, UTF-8 — RFC 8785-style, not full JCS number
canonicalisation). Stdlib only; git is optional (absent -> nulls).
"""
import datetime as _dt
import glob
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile

import vsp
from vsp import config

SCHEMA_VERSION = 1
MANIFEST_NAME = "manifest.json"
DEFAULT_EXCLUDE = (MANIFEST_NAME, "trace.jsonl")
_SKIP_ARGS = {"out_dir", "replay", "self_test", "prompt"}


# ----------------------------------------------------------------- hashing
def canonical_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, default=str)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_text(text):
    return sha256_bytes((text or "").encode("utf-8"))


def sha256_json(obj):
    return sha256_text(canonical_json(obj))


def sha256_file(path):
    """sha256 of a file's bytes, or None if it does not exist."""
    if not path or not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- inputs
def git_info(repo=None):
    repo = repo or config.REPO
    out = {"sha": None, "dirty": None}
    try:
        r = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            out["sha"] = r.stdout.strip()
            d = subprocess.run(["git", "-C", repo, "status", "--porcelain",
                                "--untracked-files=no"], capture_output=True,
                               text=True, timeout=10)
            if d.returncode == 0:
                out["dirty"] = bool(d.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return out


def code_hashes(repo=None):
    """{relative .py path: sha256} for the code that shapes the output:
    top-level *.py and vsp/**/*.py (sorted, '/' separators)."""
    repo = repo or config.REPO
    paths = glob.glob(os.path.join(repo, "*.py")) + \
        glob.glob(os.path.join(repo, "vsp", "**", "*.py"), recursive=True)
    out = {}
    for p in sorted(paths):
        rel = os.path.relpath(p, repo).replace(os.sep, "/")
        if "__pycache__" not in rel:
            out[rel] = sha256_file(p)
    return out


def research_pack_info(path=None):
    path = path or config.research_pack_path()
    info = {"path": os.path.abspath(path) if path else None,
            "sha256": sha256_file(path), "generated_at": None}
    if info["sha256"]:
        try:
            with open(path, encoding="utf-8") as f:
                info["generated_at"] = json.load(f).get("generated_at")
        except (OSError, ValueError, AttributeError):
            pass
    return info


def output_hashes(outdir, exclude=DEFAULT_EXCLUDE):
    """{file name: sha256} of the top-level files in outdir (manifest and
    trace excluded: they carry timestamps)."""
    if not outdir or not os.path.isdir(outdir):
        return {}
    return {f: sha256_file(os.path.join(outdir, f))
            for f in sorted(os.listdir(outdir))
            if os.path.isfile(os.path.join(outdir, f)) and f not in exclude}


def _now():
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z")


def _plain(obj):
    return json.loads(json.dumps(obj, default=str)) if obj is not None else None


# --------------------------------------------------------------- manifest
def build_manifest(**parts):
    """Assemble the manifest. Known parts: argv, args, seed, candidate_seeds,
    research_pack (path or a ready {path, sha256, generated_at} dict), route,
    research, candidates, selected, repairs, gates, outdir (-> outputs
    hashes), outputs (explicit {file: sha256}), timings_ms, repo, cwd,
    created. Unknown parts are kept verbatim (JSON-safe)."""
    p = dict(parts)
    repo = p.pop("repo", None) or config.REPO
    args = p.pop("args", None)
    if args is not None and not isinstance(args, dict):
        args = vars(args)
    rp = p.pop("research_pack", None)
    pack = rp if isinstance(rp, dict) else research_pack_info(rp)
    outdir = p.pop("outdir", None)
    outputs = p.pop("outputs", None)
    if outputs is None:
        outputs = output_hashes(outdir)
    seed = p.pop("seed", None)
    cands = p.pop("candidate_seeds", None)
    m = {
        "schema_version": SCHEMA_VERSION,
        "pipeline_version": getattr(vsp, "__version__", None),
        "created": p.pop("created", None) or _now(),
        "git": git_info(repo),
        "python": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "argv": list(p.pop("argv", None) or []),
        "args": _plain(args) or {},
        "cwd": p.pop("cwd", None) or os.getcwd(),
        "seeds": {"root": seed, "candidates": list(cands) if cands else []},
        "inputs": {
            "research_pack": pack,
            "rules_sha256": sha256_file(os.path.join(repo, "RULES.md")),
            "personas_sha256": sha256_file(os.path.join(repo, "personas.json")),
            "schema_sha256": sha256_file(os.path.join(repo, "schema",
                                                      "script.schema.json")),
            "code": code_hashes(repo),
        },
        "route": _plain(p.pop("route", None)),
        "research": _plain(p.pop("research", None)),
        "candidates": _plain(p.pop("candidates", None)) or [],
        "selected": _plain(p.pop("selected", None)),
        "repairs": _plain(p.pop("repairs", None)) or [],
        "gates": _plain(p.pop("gates", None)) or {},
        "outputs": dict(outputs or {}),
        "timings_ms": _plain(p.pop("timings_ms", None)) or {},
    }
    for k, v in p.items():          # integrator extras, verbatim
        m[k] = _plain(v)
    return m


def write_manifest(outdir, manifest, name=MANIFEST_NAME):
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
        f.write("\n")
    return path


def load_manifest(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ----------------------------------------------------------------- replay
def replay_argv(manifest):
    """CLI args for the replay, from manifest["args"] (argparse dests:
    store_true flags become bare flags, None/False are dropped, lists are
    repeated values; out_dir/replay/self_test are never replayed; the prompt
    goes last after '--' so a prompt starting with '-' stays positional).
    Falls back to manifest["argv"] minus --out-dir/--replay."""
    args = manifest.get("args") or {}
    if args:
        out = []
        for k, v in sorted(args.items()):
            if k in _SKIP_ARGS or v is None or v is False:
                continue
            flag = "--" + k.replace("_", "-")
            if v is True:
                out.append(flag)
            elif isinstance(v, (list, tuple)):
                out += [flag] + [str(x) for x in v]
            else:
                out += [flag, str(v)]
        if args.get("prompt"):
            out += ["--", str(args["prompt"])]
        return out
    argv, out, skip = list(manifest.get("argv") or []), [], 0
    for i, x in enumerate(argv):
        if skip:
            skip -= 1
            continue
        if x in ("--out-dir", "--replay"):
            skip = 1
            continue
        if x.startswith("--out-dir=") or x.startswith("--replay="):
            continue
        out.append(x)
    return out


def _input_drift(manifest, repo):
    warns = []
    ins = manifest.get("inputs") or {}
    pack = ins.get("research_pack") or {}
    if pack.get("path") and pack.get("sha256"):
        now = sha256_file(pack["path"])
        if now is None:
            warns.append(f"research pack missing: {pack['path']}")
        elif now != pack["sha256"]:
            warns.append("research pack changed since the run (sha256 differs)")
    for key, fn in (("rules_sha256", "RULES.md"), ("personas_sha256", "personas.json")):
        if ins.get(key) and sha256_file(os.path.join(repo, fn)) != ins[key]:
            warns.append(f"{fn} changed since the run")
    code = ins.get("code") or {}
    now = code_hashes(repo)
    changed = sorted(k for k in set(code) | set(now) if code.get(k) != now.get(k))
    if changed:
        warns.append("code changed since the run: " + ", ".join(changed[:12]))
    if manifest.get("python") and manifest["python"] != sys.version.split()[0]:
        warns.append(f"python {sys.version.split()[0]} != recorded {manifest['python']} "
                     "(random.choice/shuffle sequences are only guaranteed per version)")
    return warns


def replay(manifest_path, python=sys.executable, pipeline=None, keep=False,
           timeout=600, repo=None):
    """Re-run pipeline.py with the recorded args into a temp --out-dir and
    compare the script.json sha256. -> (ok, details). The recorded research
    pack is pinned via VSP_RESEARCH_PACK when it still exists. Never raises
    for a failed run (ok=False + details)."""
    details = {"manifest": os.path.abspath(manifest_path), "cmd": None,
               "returncode": None, "expected_sha256": None, "actual_sha256": None,
               "outputs": {}, "warnings": [], "out_dir": None, "error": None}
    try:
        m = load_manifest(manifest_path)
    except (OSError, ValueError) as e:
        details["error"] = f"cannot read manifest: {e}"
        return False, details
    repo = repo or config.REPO
    pipeline = pipeline or os.path.join(repo, "pipeline.py")
    expected = (m.get("outputs") or {}).get("script.json")
    details["expected_sha256"] = expected
    details["warnings"] = _input_drift(m, repo)
    tmp = tempfile.mkdtemp(prefix="vsp_replay_")
    out = os.path.join(tmp, "out")
    argv = replay_argv(m)
    if "--" in argv:
        k = argv.index("--")
        cmd = [python, pipeline] + argv[:k] + ["--out-dir", out] + argv[k:]
    else:
        cmd = [python, pipeline] + argv + ["--out-dir", out]
    details["cmd"] = cmd
    env = dict(os.environ)
    pack = ((m.get("inputs") or {}).get("research_pack") or {}).get("path")
    if pack and os.path.isfile(pack):
        env["VSP_RESEARCH_PACK"] = pack
    cwd = m.get("cwd") if m.get("cwd") and os.path.isdir(m["cwd"]) else repo
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=cwd,
                           timeout=timeout)
        details["returncode"] = r.returncode
        details["stdout_tail"] = r.stdout[-800:]
        details["stderr_tail"] = r.stderr[-800:]
        actual = sha256_file(os.path.join(out, "script.json"))
        details["actual_sha256"] = actual
        for f, h in sorted((m.get("outputs") or {}).items()):
            a = sha256_file(os.path.join(out, f))
            details["outputs"][f] = {"expected": h, "actual": a, "match": a == h}
        ok = expected is not None and actual == expected
        if expected is None:
            details["error"] = "manifest records no script.json hash"
        elif actual is None:
            details["error"] = "replay produced no script.json"
    except (OSError, subprocess.SubprocessError) as e:
        details["error"] = f"replay run failed: {e!r}"
        ok = False
    finally:
        if keep:
            details["out_dir"] = out
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    return ok, details


def replay_report(ok, details):
    """Human-readable lines for validation-report.md / stdout."""
    L = [f"replay: {'OK — script.json sha256 reproduced' if ok else 'MISMATCH'}",
         f"  expected {details.get('expected_sha256')}",
         f"  actual   {details.get('actual_sha256')}"]
    diff = [f for f, x in (details.get("outputs") or {}).items() if not x["match"]]
    if diff:
        L.append("  other outputs differing: " + ", ".join(diff))
    for w in details.get("warnings") or []:
        L.append(f"  warning: {w}")
    if details.get("error"):
        L.append(f"  error: {details['error']}")
    return "\n".join(L)


if __name__ == "__main__":  # python3 -m vsp.manifest --replay manifest.json
    if len(sys.argv) == 3 and sys.argv[1] == "--replay":
        ok_, det = replay(sys.argv[2])
        print(replay_report(ok_, det))
        sys.exit(0 if ok_ else 1)
    print("usage: python3 -m vsp.manifest --replay outputs/<slug>/manifest.json")
    sys.exit(2)
