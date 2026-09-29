"""promote PACK — full-scorecard A/B of one hook pack, then approve or reject.

    base  = temp copy of the repo WITHOUT the pack (production as it is: the
            other approved packs stay)
    cand  = the same copy + the pack with "status": "approved"
    both  get the A/B loader shim when the maker predates the native loader
          (packs.inject_shim: temp copies only — the repo's maker is never
          edited)

Scorecard golden + holdout on both (one yardstick, abtest.run_ab), the
candidate's self-test on every interpreter, then decide.decide with the
promote extras R10 (non-vacuous: the pack changed >= 1 hook) and R11 (hook
diversity not lower). The pack's status becomes "approved" or "rejected",
its provenance gets the promote evidence, and learned/LEDGER.md gets an entry.

Evidence: learned/promote/<pack-id>/{evidence.json, evidence.md,
golden-compare.md, holdout-compare.md}; raw scorecards in
learned/promote/results/ (git-ignored).
"""
import json
import os
import shutil

from vsp.improve import abtest as A
from vsp.improve import common as C
from vsp.improve import decide as D
from vsp.improve import ledger
from vsp.improve import packs as P


def evidence_dir(pid):
    return C.learned("promote", C.slug(pid, 80))


def raw_dir():
    return C.learned("promote", "results")


def maker_hooks():
    from vsp.improve import evolve as E
    vsm = E.load_maker()
    hooks = {f: list(v) for f, v in vsm.HOOKS.items()}
    known = frozenset(getattr(vsm, "HOOK_SLOTS", None) or P.hook_slots(hooks))
    return hooks, known, vsm


def prepare_trees(pack_path, pack, loader="auto", src=None):
    """-> (tmp root, base tree, cand tree, loader mode used)."""
    src = src or C.REPO
    native = P.native_loader(os.path.join(src, "viral_script_maker.py"))
    if loader == "native" and not native:
        raise C.ImproveError("--loader native: this maker has no hook-pack loader")
    mode = "native" if (native and loader != "emulate") else "emulate"
    tmp = C.mkdtemp("vsp-promote-")
    name = os.path.basename(pack_path)
    trees = []
    for side in ("base", "cand"):
        tree = C.copy_tree(src, os.path.join(tmp, side))
        hp = os.path.join(tree, "learned", "hook_packs")
        if os.path.isdir(hp):
            shutil.rmtree(hp)
        os.makedirs(hp, exist_ok=True)
        live = C.hook_packs_dir()          # the engine's packs (VSP_LEARNED_DIR aware)
        if os.path.isdir(live):
            for n in sorted(os.listdir(live)):
                if n.endswith(".json") and n != name:
                    shutil.copy2(os.path.join(live, n), os.path.join(hp, n))
        if side == "cand":
            approved = dict(pack, status="approved")
            C.write_json(os.path.join(hp, name), approved)
        if mode == "emulate":
            P.inject_shim(os.path.join(tree, "viral_script_maker.py"))
        trees.append(tree)
    return tmp, trees[0], trees[1], mode


def judge(stats, selftest_ok):
    return D.decide(stats, selftest_ok, require_change=True, require_diversity=True)


def promote(ref, budget="full", loader="auto", python=None, log=None, keep=False,
            pys=None):
    say = log or (lambda m: None)
    path = P.resolve_pack(ref)
    if not path:
        raise C.ImproveError(f"no such pack: {ref!r} (path, file name or id)")
    pack = C.read_json(path)
    if not isinstance(pack, dict):
        raise C.ImproveError(f"not a JSON pack: {path}")
    pid = pack.get("id") or os.path.basename(path)
    if pack.get("status") == "approved":
        raise C.ImproveError(f"{pid} is already approved")
    hooks, known, _vsm = maker_hooks()
    probs = P.validate_pack(pack, hooks, known)
    started = C.now_iso()
    ev_dir = evidence_dir(pid)
    os.makedirs(ev_dir, exist_ok=True)
    templates = P.templates_of(pack)
    if probs:
        dec = {"verdict": "REJECT", "checks": [{"id": "R0-contract", "ok": False,
                                               "detail": "; ".join(probs[:5])}],
               "reasons": ["R0-contract: " + "; ".join(probs[:5])]}
        res = {"pack": pid, "path": path, "verdict": "REJECT", "decision": dec,
               "templates": templates, "started": started, "budget": budget,
               "stats": {}, "diversity": {}, "selftest": {"ok": None, "runs": []}}
        return _record(res, path, ev_dir, say)
    say(f"promote {pid}: {len(templates)} template(s); preparing A/B copies ...")
    tmp, base, cand, mode = prepare_trees(path, pack, loader)
    try:
        ab = A.run_ab(base, cand, budget=budget, python=python, label=f"promote-{pid}",
                      raw_dir=raw_dir(), evidence_dir=ev_dir, log=say, pys=pys)
    finally:
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)
    dec = judge(ab["stats"], ab["selftest"]["ok"])
    res = {"pack": pid, "path": path, "verdict": dec["verdict"], "decision": dec,
           "templates": templates, "started": started, "finished": C.now_iso(),
           "budget": budget, "seeds": ab["seeds"], "loader": mode,
           "git_sha": C.git_sha(), "stats": ab["stats"], "selftest": ab["selftest"],
           "diversity": A.diversity(ab["results"]), "raw": ab["raw"],
           "compare": ab["compare"], "tmp": tmp if keep else None}
    return _record(res, path, ev_dir, say)


def _record(res, path, ev_dir, say):
    pid, verdict = res["pack"], res["verdict"]
    status = "approved" if verdict == "ACCEPT" else "rejected"
    res["status"] = status
    ev_json = os.path.join(ev_dir, "evidence.json")
    ev_md = os.path.join(ev_dir, "evidence.md")
    C.write_json(ev_json, {k: v for k, v in res.items() if k not in ("tmp",)})
    C.write_text(ev_md, render_md(res))
    summary = {"verdict": verdict, "at": res.get("finished") or res.get("started"),
               "budget": res.get("budget"), "headline": D.headline(res.get("stats")),
               "diversity": res.get("diversity"),
               "failed": res["decision"]["reasons"], "evidence": C.rel(ev_json)}
    P.set_status(path, status, promote_evidence=summary)
    lines = [f"pack `{C.rel(path)}` → **{status}** ({len(res['templates'])} templates, "
             f"budget {res.get('budget')}, seeds {res.get('seeds')}, loader "
             f"{res.get('loader')})"]
    lines += D.headline(res.get("stats"))
    lines += A.diversity_lines(res.get("diversity") or {})
    lines.append(A.selftest_line(res.get("selftest") or {}))
    if res["decision"]["reasons"]:
        lines += ["failed: " + r for r in res["decision"]["reasons"][:6]]
    else:
        lines.append("all ACCEPT rules hold (R1–R8, R10 non-vacuous, R11 diversity)")
    ledger.append("promote", pid, verdict, lines, evidence=[ev_json, ev_md])
    res["evidence"] = [C.rel(ev_json), C.rel(ev_md)]
    say(f"promote {pid}: {verdict} → {status}")
    return res


def render_md(res):
    dec = res["decision"]
    L = [f"# promote `{res['pack']}` — {res['verdict']}", "",
         f"- pack: `{C.rel(res['path'])}` → status **"
         f"{'approved' if res['verdict'] == 'ACCEPT' else 'rejected'}**",
         f"- budget {res.get('budget')} (seeds {res.get('seeds')}), loader "
         f"{res.get('loader')}, engine at `{res.get('git_sha')}`, {res.get('started')}",
         f"- {A.selftest_line(res.get('selftest') or {})}", "",
         "## Templates", ""]
    L += [f"- `{f}`: {t!r}" for f, t in res["templates"]] + ["", "## Checks", "",
                                                            "| check | ok | detail |",
                                                            "|---|---|---|"]
    L += [f"| {c['id']} | {'✅' if c['ok'] else '❌'} | {c['detail']} |" for c in dec["checks"]]
    L += ["", "## Headline", ""] + [f"- {x}" for x in D.headline(res.get("stats"))]
    L += ["", "## Diversity (the expected win)", ""]
    L += [f"- {x}" for x in A.diversity_lines(res.get("diversity") or {})] or ["- n/a"]
    if res.get("compare"):
        L += ["", "## Scorecard compare reports", ""]
        L += [f"- {s}: `{v}`" for s, v in res["compare"].items()]
    return "\n".join(L) + "\n"


def render(res):
    L = [f"promote {res['pack']}: {res['verdict']} → {res.get('status')}"]
    L += ["  " + x for x in D.headline(res.get("stats"))]
    L += ["  " + x for x in A.diversity_lines(res.get("diversity") or {})]
    L.append("  " + A.selftest_line(res.get("selftest") or {}))
    for r in res["decision"]["reasons"][:8]:
        L.append(f"  ✗ {r}")
    L.append("  evidence: " + ", ".join(res.get("evidence") or []))
    return "\n".join(L)


def load_evidence(pid):
    return C.read_json(os.path.join(evidence_dir(pid), "evidence.json"))


if __name__ == "__main__":  # pragma: no cover
    import sys
    print(json.dumps(promote(sys.argv[1], budget="small"), indent=1, default=str)[:2000])
