"""delegate TASK_ID — hand one learned/tasks.json task to Muse Code, then verify.

With the `muse` CLI (VSP_MUSE_BIN or PATH):
  1. a fresh branch improve/<task>-<stamp> + temporary worktree at the
     current HEAD (never main/master itself);
  2. `muse exec --json --disable-approval "<task + constraints + acceptance>"`
     in that worktree (headless, sandbox kept on; META_API_KEY is filled from
     VSP_LLM_API_KEY when Hermes stripped it). Muse's sandbox keeps .git
     read-only, so it edits files only;
  3. the ENGINE commits whatever changed (outputs/ excluded) on the branch;
  4. verify --base <start sha> --cand <branch> decides ACCEPT / REJECT.
The engine never pushes and never merges: on ACCEPT the operating agent
(Hermes) pushes the branch and opens a PR with the verify evidence.

Without `muse`: prints the task plus exact instructions for the operating
agent to do it on a branch and call verify.
"""
import json
import os
import shutil

from vsp.improve import common as C
from vsp.improve import ledger

DEFAULT_TIMEOUT = 3600


def muse_bin():
    b = os.environ.get("VSP_MUSE_BIN")
    if b:
        return b if os.path.isfile(b) and os.access(b, os.X_OK) else None
    return shutil.which("muse")


def load_task(task_id):
    doc = C.read_json(C.learned("tasks.json")) or {}
    for t in doc.get("tasks") or []:
        if t.get("id") == task_id:
            return t, doc
    ids = ", ".join(t.get("id", "?") for t in (doc.get("tasks") or [])[:8])
    raise C.ImproveError(f"no task {task_id!r} in learned/tasks.json (run diagnose; "
                         f"open tasks: {ids or 'none'})")


def task_prompt(t, base_sha, branch):
    L = [f"You are working in a git worktree of the viral script pipeline, on branch "
         f"{branch} (created from {base_sha}). Task {t['id']}: {t['title']}", "",
         f"Why: {t.get('rationale', '')}"]
    for e in (t.get("evidence") or [])[:4]:
        L.append(f"Evidence: {e}")
    for e in (t.get("examples") or [])[:3]:
        L.append(f"Example: {e}")
    L += ["Files likely involved: " + ", ".join(t.get("files") or []),
          f"Done when: {t.get('done_when', '')}", "", "Hard constraints:"]
    L += [f"- {c}" for c in t.get("constraints") or []]
    L += ["- keep `python3 pipeline.py --self-test` green on python3.9 and python3.12; "
          "stdlib only; no network in tests",
          "- do NOT run git commit/push (.git is read-only in your sandbox; the engine "
          "commits your edits and verifies them)", "",
          f"Check your work with: python3 -m vsp.improve verify --base {base_sha} --cand . "
          f"--budget small",
          f"The engine then runs: python3 -m vsp.improve verify --base {base_sha} --cand "
          f"{branch}"]
    return "\n".join(L)


def instructions(t, base_sha, branch, repo=None):
    repo = repo or C.REPO
    wt = os.path.join(os.path.dirname(repo), ".vsp-worktrees", C.slug(branch, 60))
    return "\n".join([
        f"delegate {t['id']}: the `muse` CLI is not installed — do the task yourself "
        f"(operating agent):",
        f"  1. git -C {repo} worktree add -b {branch} {wt} {base_sha}"
        f"      # a new branch; never commit to main/master",
        f"  2. cd {wt} and implement the task below (never edit vsp/gates.py, vsp/rules.py, "
        f"vsp/lexicon.py or the yardstick)",
        "  3. python3.9 pipeline.py --self-test && python3.12 pipeline.py --self-test",
        f"  4. git add -A && git commit -m \"improve({t['id']}): {t['title'][:60]}\"",
        f"  5. python3 -m vsp.improve verify --base {base_sha} --cand {branch}",
        "  6. ACCEPT: push the branch and open a PR citing learned/verify/<run>/evidence.md; "
        "never merge your own PR. REJECT: fix and re-verify, or drop the branch "
        f"(git worktree remove {wt}; git branch -D {branch}).",
        "", "---- task ----", task_prompt(t, base_sha, branch)])


def parse_events(text):
    """muse exec --json JSONL -> {events, types, last_text}."""
    types, last, n = {}, None, 0
    for ln in (text or "").splitlines():
        ln = ln.strip()
        if not ln.startswith("{"):
            continue
        try:
            ev = json.loads(ln)
        except ValueError:
            continue
        n += 1
        ty = str(ev.get("type") or ev.get("event") or "?")
        types[ty] = types.get(ty, 0) + 1
        for k in ("text", "message", "content", "result", "summary"):
            v = ev.get(k)
            if isinstance(v, str) and v.strip():
                last = v.strip()[:400]
    return {"events": n, "types": types, "last_text": last}


def _mark(task_id, **kw):
    p = C.learned("tasks.json")
    doc = C.read_json(p)
    if not isinstance(doc, dict):
        return
    for t in doc.get("tasks") or []:
        if t.get("id") == task_id:
            t.setdefault("delegation", {}).update(kw)
            if kw.get("status"):
                t["status"] = kw["status"]
    C.write_json(p, doc)


def delegate(task_id, timeout=DEFAULT_TIMEOUT, budget="full", log=None, muse=None,
             python=None):
    say = log or (lambda m: None)
    t, _doc = load_task(task_id)
    base_sha = C.git_sha(short=False)
    if not base_sha:
        raise C.ImproveError("not a git checkout")
    branch = f"improve/{C.slug(task_id, 40)}-{C.stamp().lower()}"
    mb = muse if muse is not None else muse_bin()
    if not mb:
        text = instructions(t, base_sha[:12], branch)
        _mark(task_id, status="handed-off", branch=branch, at=C.now_iso(), mode="instructions")
        ledger.append("delegate", task_id, "HANDED-OFF",
                      [f"`muse` CLI absent: instructions printed for the operating agent "
                       f"(branch {branch} from {base_sha[:12]})"])
        return {"ok": True, "mode": "instructions", "task": task_id, "branch": branch,
                "base": base_sha[:12], "text": text}
    wt = C.mkdtemp("vsp-delegate-")
    shutil.rmtree(wt, ignore_errors=True)
    r = C.git(["worktree", "add", "-b", branch, wt, base_sha], timeout=300)
    if r["rc"] != 0:
        raise C.ImproveError(f"git worktree add failed: {C.tail(r['err'], 200)}")
    res = {"ok": False, "mode": "muse", "task": task_id, "branch": branch,
           "base": base_sha[:12], "worktree": wt}
    try:
        env = C.child_env()
        if not env.get("META_API_KEY") and env.get("VSP_LLM_API_KEY"):
            env["META_API_KEY"] = env["VSP_LLM_API_KEY"]   # Hermes strips provider keys
        cmd = [mb, "exec", "--json", "--disable-approval"]
        steps = os.environ.get("VSP_MUSE_MAX_STEPS")
        if steps:
            cmd += ["--max-model-steps", steps]
        cmd.append(task_prompt(t, base_sha[:12], branch))
        say(f"delegate {task_id}: muse exec in {wt} (branch {branch}) ...")
        m = C.run(cmd, cwd=wt, env=env, timeout=timeout)
        res["muse"] = {"rc": m["rc"], "secs": m["secs"], **parse_events(m["out"]),
                       "stderr_tail": C.tail(m["err"], 300)}
        # the engine commits (Muse's sandbox keeps .git read-only)
        C.git(["add", "-A", "--", ".", ":(exclude)outputs"], cwd=wt)
        st = C.git(["status", "--porcelain"], cwd=wt)
        if not st["out"].strip():
            res["verdict"] = "NO-CHANGES"
            say(f"delegate {task_id}: muse made no changes")
        else:
            who = [] if C.git(["config", "user.email"], cwd=wt)["out"].strip() else \
                ["-c", "user.name=vsp-improve", "-c", "user.email=vsp-improve@localhost"]
            c = C.git(who + ["commit", "-q", "-m",
                       f"improve({task_id}): {t['title'][:60]} [muse exec]\n\n"
                       f"Delegated by `python3 -m vsp.improve delegate {task_id}`; "
                       f"committed by the engine (Muse's sandbox keeps .git read-only)."],
                      cwd=wt)
            if c["rc"] != 0:
                raise C.ImproveError(f"engine commit failed: {C.tail(c['err'], 200)}")
            res["commit"] = C.git_sha(repo=wt)
    finally:
        C.git(["worktree", "remove", "--force", wt])
        C.git(["worktree", "prune"])
        shutil.rmtree(wt, ignore_errors=True)
    if res.get("commit"):
        from vsp.improve import verify as V
        v = V.verify(base_sha, branch, budget=budget, python=python, log=say)
        res["verdict"] = v["verdict"]
        res["verify"] = {"evidence": v.get("evidence"),
                         "reasons": v["decision"]["reasons"][:6]}
        res["ok"] = v["verdict"] == "ACCEPT"
    _mark(task_id, status={"ACCEPT": "accepted", "REJECT": "rejected"}.get(
        res.get("verdict"), "no-changes"), branch=branch, at=C.now_iso(), mode="muse",
        verdict=res.get("verdict"))
    ledger.append("delegate", task_id, res.get("verdict") or "?",
                  [f"muse exec on branch `{branch}` from {base_sha[:12]}: rc "
                   f"{(res.get('muse') or {}).get('rc')}, "
                   f"{(res.get('muse') or {}).get('events')} events",
                   f"engine commit: {res.get('commit') or 'none'}",
                   "never pushed, never merged: on ACCEPT the operating agent opens the PR"]
                  + [f"failed: {x}" for x in (res.get("verify") or {}).get("reasons", [])],
                  evidence=(res.get("verify") or {}).get("evidence"))
    return res


def render(res):
    if res["mode"] == "instructions":
        return res["text"]
    L = [f"delegate {res['task']}: {res.get('verdict')} on branch {res['branch']} "
         f"(from {res['base']})",
         f"  muse: {res.get('muse')}", f"  commit: {res.get('commit') or 'none'}"]
    if res.get("verify"):
        L.append(f"  verify evidence: {', '.join(res['verify']['evidence'] or [])}")
        L += [f"  ✗ {x}" for x in res["verify"]["reasons"]]
    L.append("  next: " + ("push the branch and open a PR with the evidence (never merge it "
                           "yourself)" if res.get("ok") else "fix or drop the branch"))
    return "\n".join(L)
