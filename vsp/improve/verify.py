"""verify --base REF --cand REF — ACCEPT or REJECT a candidate change.

  1. materialize both refs: temporary `git worktree add --detach` trees; when
     .git is read-only (Muse Code's sandbox) `git archive` instead. "." (or
     any directory) = that working tree, copied as-is (uncommitted edits too).
  2. weakening guard (guard.check): gates / rules / lexicon / self-test may
     never be weakened, D136-D141 never removed, the yardstick never edited.
  3. the candidate's self-test under every interpreter (python3.9 and
     python3.12 when present).
  4. scorecard golden + holdout on both trees with the BASE's yardstick
     (abtest.run_ab), then `evals/scorecard.py compare` per suite.
  5. decide.decide: R1-R8 + R9 guard (diversity is reported as evidence).

Prints ACCEPT/REJECT; writes learned/verify/<stamp>-<base>-<cand>/
{evidence.json, evidence.md, golden-compare.md, holdout-compare.md} (raw
scorecards: learned/verify/results/, git-ignored); appends learned/LEDGER.md.
Temporary worktrees are always removed (git worktree remove + prune).
"""
import io
import os
import shutil
import subprocess
import tarfile

from vsp.improve import abtest as A
from vsp.improve import common as C
from vsp.improve import decide as D
from vsp.improve import guard as G
from vsp.improve import ledger


def materialize(ref, dest, repo=None):
    """-> info {kind: dir|worktree|archive, ref, sha, path}."""
    repo = repo or C.REPO
    if ref in (".", "WORKTREE") or (os.path.isdir(ref) and not _is_ref(ref, repo)):
        src = repo if ref in (".", "WORKTREE") else os.path.abspath(ref)
        C.copy_tree(src, dest)
        return {"kind": "dir", "ref": ref, "src": src, "path": dest,
                "sha": C.git_sha(repo=src), "dirty": C.git_dirty(src)}
    r = C.git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], cwd=repo)
    sha = r["out"].strip()
    if r["rc"] != 0 or not sha:
        raise C.ImproveError(f"unknown git ref {ref!r}")
    w = C.git(["worktree", "add", "--detach", dest, sha], cwd=repo, timeout=300)
    if w["rc"] == 0:
        return {"kind": "worktree", "ref": ref, "sha": sha[:12], "path": dest}
    # read-only .git (e.g. Muse Code's sandbox): export the commit instead
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest, exist_ok=True)
    p = subprocess.run(["git", "archive", "--format=tar", sha], cwd=repo,
                       capture_output=True, timeout=300)
    if p.returncode != 0:
        raise C.ImproveError(f"cannot materialize {ref!r}: worktree failed "
                             f"({C.tail(w['err'], 160)}) and git archive failed "
                             f"({p.stderr.decode('utf-8', 'replace')[-160:]})")
    with tarfile.open(fileobj=io.BytesIO(p.stdout)) as tf:
        if hasattr(tarfile, "data_filter"):
            tf.extractall(dest, filter="data")
        else:  # pragma: no cover — older 3.9 patch levels
            tf.extractall(dest)
    return {"kind": "archive", "ref": ref, "sha": sha[:12], "path": dest,
            "worktree_error": C.tail(w["err"], 160)}


def _is_ref(ref, repo):
    r = C.git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], cwd=repo)
    return r["rc"] == 0 and bool(r["out"].strip())


def release(info, repo=None):
    if not info:
        return
    if info.get("kind") == "worktree":
        C.git(["worktree", "remove", "--force", info["path"]], cwd=repo or C.REPO)
        C.git(["worktree", "prune"], cwd=repo or C.REPO)
    shutil.rmtree(info["path"], ignore_errors=True)


def diff_summary(bi, ci, repo=None):
    """git diff numstat between the two refs (both git refs only)."""
    if bi.get("kind") == "dir" or ci.get("kind") == "dir":
        return None
    r = C.git(["diff", "--numstat", bi["sha"], ci["sha"]], cwd=repo or C.REPO)
    if r["rc"] != 0:
        return None
    rows = []
    for ln in r["out"].splitlines():
        parts = ln.split("\t")
        if len(parts) == 3:
            rows.append({"file": parts[2], "added": parts[0], "removed": parts[1]})
    return {"files": len(rows), "rows": rows[:60]}


def verify(base_ref, cand_ref, budget="full", python=None, log=None, keep=False, pys=None):
    say = log or (lambda m: None)
    started = C.now_utc()
    tmp = C.mkdtemp("vsp-verify-")
    bi = ci = None
    try:
        bi = materialize(base_ref, os.path.join(tmp, "base"))
        ci = materialize(cand_ref, os.path.join(tmp, "cand"))
        say(f"verify: base {base_ref} ({bi['kind']} {bi.get('sha')}) vs cand {cand_ref} "
            f"({ci['kind']} {ci.get('sha')}{' dirty' if ci.get('dirty') else ''})")
        findings, gev = G.check(bi["path"], ci["path"], python)
        say(f"verify: weakening guard — {len(findings)} finding(s)")
        label = f"verify-{C.slug(base_ref, 20)}-{C.slug(cand_ref, 20)}"
        def _name(info, ref):
            if info.get("kind") == "dir":
                return f"dir-{os.path.basename(os.path.abspath(ref)) or 'tree'}"
            return info.get("sha") or ref
        ev_dir = C.learned("verify", f"{C.stamp(started)}-{C.slug(_name(bi, base_ref), 16)}"
                                     f"-{C.slug(_name(ci, cand_ref), 16)}")
        ab = A.run_ab(bi["path"], ci["path"], budget=budget, python=python, label=label,
                      raw_dir=C.learned("verify", "results"), evidence_dir=ev_dir, log=say,
                      pys=pys)
        dec = D.decide(ab["stats"], ab["selftest"]["ok"], guard_findings=findings)
        res = {"base": {k: v for k, v in bi.items() if k != "path"},
               "cand": {k: v for k, v in ci.items() if k != "path"},
               "verdict": dec["verdict"], "decision": dec, "budget": budget,
               "seeds": ab["seeds"], "started": started.isoformat(), "finished": C.now_iso(),
               "engine_sha": C.git_sha(), "guard": gev, "stats": ab["stats"],
               "selftest": ab["selftest"], "diversity": A.diversity(ab["results"]),
               "compare": ab["compare"], "raw": ab["raw"],
               "diff": diff_summary(bi, ci)}
        return _record(res, ev_dir, say)
    finally:
        if not keep:
            release(ci)
            release(bi)
            shutil.rmtree(tmp, ignore_errors=True)


def _record(res, ev_dir, say):
    ev_json = os.path.join(ev_dir, "evidence.json")
    ev_md = os.path.join(ev_dir, "evidence.md")
    C.write_json(ev_json, res)
    C.write_text(ev_md, render_md(res))
    b, c = res["base"], res["cand"]
    subject = f"{b['ref']} ({b.get('sha')}) → {c['ref']} ({c.get('sha')}" \
              f"{', dirty' if c.get('dirty') else ''})"
    lines = [f"budget {res['budget']} (seeds {res['seeds']}), yardstick = base tree"]
    lines += D.headline(res["stats"])
    lines += A.diversity_lines(res["diversity"])
    lines.append(A.selftest_line(res["selftest"]))
    g = res["guard"]
    lines.append(f"weakening guard: {len(g['findings'])} finding(s); guarded files changed: "
                 f"{', '.join(g['guarded_changed']) or 'none'}; yardstick changed: "
                 f"{', '.join(g['yardstick_changed']) or 'none'}")
    lines += ["failed: " + r for r in res["decision"]["reasons"][:6]]
    ledger.append("verify", subject, res["verdict"], lines, evidence=[ev_json, ev_md])
    res["evidence"] = [C.rel(ev_json), C.rel(ev_md)]
    say(f"verify: {res['verdict']}")
    return res


def render_md(res):
    b, c, dec = res["base"], res["cand"], res["decision"]
    L = [f"# verify — {res['verdict']}", "",
         f"- base `{b['ref']}` ({b['kind']} {b.get('sha')}) · cand `{c['ref']}` ({c['kind']} "
         f"{c.get('sha')}{', dirty working tree' if c.get('dirty') else ''})",
         f"- budget {res['budget']} (seeds {res['seeds']}); yardstick = the base tree's "
         f"scorecard, rubric and suites; engine `{res.get('engine_sha')}`",
         f"- {A.selftest_line(res['selftest'])}", "", "## Checks", "",
         "| check | ok | detail |", "|---|---|---|"]
    L += [f"| {x['id']} | {'✅' if x['ok'] else '❌'} | {x['detail']} |" for x in dec["checks"]]
    L += ["", "## Headline", ""] + [f"- {x}" for x in D.headline(res["stats"])]
    L += ["", "## Diversity", ""] + [f"- {x}" for x in A.diversity_lines(res["diversity"])]
    g = res["guard"]
    L += ["", "## Weakening guard", "",
          f"- guarded files changed: {', '.join(g['guarded_changed']) or 'none'}",
          f"- yardstick changed: {', '.join(g['yardstick_changed']) or 'none'}",
          f"- registry rules {g['registry']['base']} → {g['registry']['cand']}; self-test cases "
          f"{g['selftest_cases']['base']} → {g['selftest_cases']['cand']} (legacy "
          f"{g['selftest_cases']['legacy_base']} → {g['selftest_cases']['legacy_cand']})"]
    L += [f"- ❌ {x}" for x in g["findings"]] or ["- no weakening found"]
    if res.get("diff"):
        L += ["", f"## Diff ({res['diff']['files']} files)", ""]
        L += [f"- `{r['file']}` +{r['added']} −{r['removed']}" for r in res["diff"]["rows"][:30]]
    if res.get("compare"):
        L += ["", "## Scorecard compare reports", ""]
        L += [f"- {s}: `{v}`" for s, v in res["compare"].items()]
    return "\n".join(L) + "\n"


def render(res):
    b, c = res["base"], res["cand"]
    L = [f"{res['verdict']}  verify {b['ref']} ({b.get('sha')}) → {c['ref']} ({c.get('sha')})"]
    L += ["  " + x for x in D.headline(res["stats"])]
    L += ["  " + x for x in A.diversity_lines(res["diversity"])]
    L.append("  " + A.selftest_line(res["selftest"]))
    L.append(f"  weakening guard: {len(res['guard']['findings'])} finding(s)")
    L += [f"  ✗ {r}" for r in res["decision"]["reasons"][:10]]
    L.append("  evidence: " + ", ".join(res.get("evidence") or []))
    return "\n".join(L)
