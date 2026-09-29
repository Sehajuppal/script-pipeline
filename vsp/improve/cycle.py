"""cycle — one scheduled turn of the self-improvement loop.

  health    self-test (python3.9 + python3.12), research-pack age, hook packs
  measure   scorecard golden + holdout (+ capability) -> learned/evals/
  diagnose  -> learned/DIAGNOSIS.md, TASKS.md, tasks.json
  evolve    -> learned/hook_packs/<date>-<nn>.json (proposed)
  promote   the new pack (else the newest pending proposed pack): full-scorecard
            A/B -> approved | rejected
  ledger    one cycle entry in learned/LEDGER.md; learned/CYCLE.md = summary

--budget small: seeds 1 everywhere and 10 evolve prompts; full: seeds 1,2,3
and every golden product prompt. A red self-test halts the loop after
diagnose (nothing may change until it is green). The cycle never pushes,
never merges and never edits gate/rule code; code changes go through
`delegate` + `verify`.
"""
import os
import time

from vsp.improve import common as C
from vsp.improve import ledger
from vsp.improve import packs as P


def health():
    st = C.selftest(C.REPO)
    try:
        from vsp import research
        _pack, meta = research.load_pack()
        rp = {"age_hours": meta.get("age_hours"), "stale": meta.get("stale"),
              "errors": meta.get("errors"), "generated_at": meta.get("generated_at")}
    except Exception as e:  # noqa: BLE001
        rp = {"errors": [repr(e)]}
    packs = P.list_packs()
    by = {}
    for _p, pk in packs:
        by[pk.get("status")] = by.get(pk.get("status"), 0) + 1
    approved = [pk for _p, pk in packs if pk.get("status") == "approved"]
    newest = max((pk.get("provenance", {}).get("created") or "" for pk in approved), default=None)
    native = P.native_loader(os.path.join(C.REPO, "viral_script_maker.py"))
    return {"selftest": st, "research_pack": rp,
            "packs": {"by_status": by, "newest_approved": newest,
                      "newest_approved_age_h": C.age_hours(newest) if newest else None,
                      "maker_loader": "native" if native else "absent (A/B shim only)"},
            "git": {"sha": C.git_sha(), "branch": C.git_branch(), "dirty": C.git_dirty()}}


def pending_pack():
    props = [p for p, pk in P.list_packs(status="proposed")]
    return props[-1] if props else None


def cycle(budget="small", use_llm="auto", python=None, log=None, seed=None):
    say = log or (lambda m: None)
    t0 = time.time()
    from vsp.improve import diagnose as Dg
    from vsp.improve import evolve as E
    from vsp.improve import measure as M
    from vsp.improve import promote as PR
    out = {"budget": budget, "started": C.now_iso(), "steps": {}, "ok": True}
    say("cycle: health ...")
    h = health()
    out["health"] = h
    out["steps"]["health"] = {"selftest_ok": h["selftest"]["ok"],
                              "research_pack_age_h": h["research_pack"].get("age_hours"),
                              "research_pack_stale": h["research_pack"].get("stale"),
                              "packs": h["packs"]["by_status"]}
    say("cycle: measure ...")
    latest = M.measure(budget=budget, python=python, log=say)
    out["steps"]["measure"] = {s: v["headline"] for s, v in latest["suites"].items()}
    say("cycle: diagnose ...")
    dg = Dg.diagnose(latest=latest, health=h)
    out["steps"]["diagnose"] = {"opportunities": len(dg["opportunities"]),
                                "tasks": len(dg["tasks"])}
    out["top_tasks"] = [{"id": t["id"], "score": t["score"], "title": t["title"],
                         "acceptance": t["acceptance"], "self_serve": t.get("self_serve")}
                        for t in dg["tasks"][:3]]
    if not h["selftest"]["ok"]:
        out["ok"] = False
        out["halted"] = "self-test RED: evolve/promote skipped until it is green"
    else:
        seed = seed if seed is not None else int(C.today().replace("-", "")) % 100000
        say(f"cycle: evolve (seed {seed}) ...")
        ev = E.evolve(budget=budget, use_llm=use_llm, seed=seed, write=True, log=say)
        out["steps"]["evolve"] = {"verdict": ev["verdict"], "why": ev["why"], "id": ev["id"],
                                  "path": C.rel(ev["path"]) if ev.get("path") else None,
                                  "templates": len(ev["pack"]), "preview": ev["preview"],
                                  "llm": ev["llm"], "secs": ev["secs"],
                                  "holdout_opened": ev["holdout_opened"]}
        out["evolve_pack"] = ev["pack"]
        target = ev.get("path") or pending_pack()
        if target:
            say(f"cycle: promote {os.path.basename(target)} ...")
            pr = PR.promote(target, budget=budget, python=python, log=say)
            out["steps"]["promote"] = {"pack": pr["pack"], "verdict": pr["verdict"],
                                       "status": pr["status"], "diversity": pr["diversity"],
                                       "reasons": pr["decision"]["reasons"][:6],
                                       "evidence": pr.get("evidence")}
        else:
            out["steps"]["promote"] = {"verdict": "SKIPPED", "reasons": ["no proposed pack"]}
    out["secs"] = round(time.time() - t0, 1)
    out["finished"] = C.now_iso()
    lines = summary_lines(out)
    C.write_text(C.learned("CYCLE.md"), render_md(out, lines))
    verdict = "HALTED" if out.get("halted") else \
        (out["steps"].get("promote") or {}).get("verdict", "DONE")
    ledger.append("cycle", f"budget {budget}", verdict, lines,
                  evidence=[C.learned("CYCLE.md"), C.learned("DIAGNOSIS.md"),
                            C.learned("TASKS.md")])
    return out


def summary_lines(out):
    L = []
    s = out["steps"]
    h = s.get("health", {})
    L.append(f"health: self-test {'green' if h.get('selftest_ok') else 'RED'} · research pack "
             f"age {h.get('research_pack_age_h')} h (stale {h.get('research_pack_stale')}) · "
             f"hook packs {h.get('packs') or {}} · maker loader "
             f"{out['health']['packs']['maker_loader']}")
    for suite, hl in (s.get("measure") or {}).items():
        L.append(f"measure {suite}: {hl['runs']} runs · e2e {hl['e2e_pass']} · shippable "
                 f"{hl['shippable']} · rubric {hl['rubric_mean']} (audit {hl['audit_mean']}) · "
                 f"compliance {hl['compliance_flags']} · hooks distinct {hl['hook_distinct']} "
                 f"· distinct-2 {hl['hook_distinct2']}")
    d = s.get("diagnose") or {}
    L.append(f"diagnose: {d.get('opportunities')} opportunities, {d.get('tasks')} tasks")
    ev = s.get("evolve")
    if ev:
        pv = ev.get("preview") or {}
        L.append(f"evolve: {ev['verdict']} ({ev['why']}) · {ev['templates']} templates"
                 + (f" · {ev['id']}" if ev.get("id") else "")
                 + (f" · preview distinct {pv.get('distinct_base')} → {pv.get('distinct_cand')}"
                    if pv else "") + f" · llm {'used' if ev['llm'].get('used') else 'off'}"
                 + f" · holdout opened: {ev['holdout_opened'] or 'never'}")
    pr = s.get("promote")
    if pr:
        L.append(f"promote {pr.get('pack', '-')}: {pr['verdict']}"
                 + (f" → {pr['status']}" if pr.get("status") else "")
                 + ("; " + "; ".join(pr["reasons"][:2]) if pr.get("reasons") else ""))
        for suite, dd in (pr.get("diversity") or {}).items():
            L.append(f"  {suite} hook distinct {dd['distinct_ratio'][0]} → "
                     f"{dd['distinct_ratio'][1]} · distinct-2 {dd['distinct2'][0]} → "
                     f"{dd['distinct2'][1]}")
    if out.get("halted"):
        L.append(out["halted"])
    for i, t in enumerate(out.get("top_tasks") or [], 1):
        L.append(f"task {i}: {t['id']} ({t['score']}) {t['title']}")
    L.append(f"took {out.get('secs')} s")
    return L


def render_md(out, lines):
    L = ["# CYCLE — latest self-improvement cycle", "",
         f"`python3 -m vsp.improve cycle --budget {out['budget']}` · {out['started']} → "
         f"{out.get('finished')} · git `{out['health']['git']['sha']}` on "
         f"`{out['health']['git']['branch']}`", ""]
    L += [f"- {x}" for x in lines]
    if out.get("evolve_pack"):
        L += ["", "## Evolved pack", "", "| fitness | gain | quality | novelty | family | "
              "template | operator |", "|---|---|---|---|---|---|---|"]
        for e in out["evolve_pack"]:
            L.append(f"| {e['fitness']} | {e['gain']} | {e['quality']} | {e['novelty']} | "
                     f"{e['family']} | `{e['template']}` | {e['operator']} |")
    L += ["", "## Top tasks", ""]
    for t in out.get("top_tasks") or []:
        L.append(f"- `{t['id']}` ({t['score']}): {t['title']} — acceptance `{t['acceptance']}`"
                 + (f"; engine: `{t['self_serve']}`" if t.get("self_serve") else ""))
    return "\n".join(L) + "\n"


def render(out):
    return "\n".join(["cycle " + ("OK" if out.get("ok") else "HALTED") +
                      f" (budget {out['budget']})"] + ["  " + x for x in summary_lines(out)])
