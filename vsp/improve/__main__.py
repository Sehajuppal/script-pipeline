"""CLI: python3 -m vsp.improve <command> [...]  (see vsp/improve/__init__.py)."""
import argparse
import json
import sys


def _log(msg):
    print(msg, file=sys.stderr, flush=True)


def cmd_measure(a):
    from vsp.improve import measure as M
    out = M.measure(budget=a.budget, python=a.python, log=_log)
    print(M.render(out))
    return 0


def cmd_diagnose(a):
    from vsp.improve import common as C
    from vsp.improve import diagnose as D
    out = D.diagnose(base_ref=a.base)
    print(f"wrote {C.rel(C.learned('DIAGNOSIS.md'))}, {C.rel(C.learned('TASKS.md'))} "
          f"({len(out['opportunities'])} opportunities, {len(out['tasks'])} tasks)")
    for t in out["tasks"][:a.top]:
        print(f"  {t['id']:<28} {t['score']:>6}  {t['title']}")
    return 0


def cmd_evolve(a):
    from vsp.improve import evolve as E
    res = E.evolve(budget=a.budget, use_llm=a.llm, seed=a.seed, write=not a.dry_run,
                   log=_log)
    print(E.render(res))
    return 0


def cmd_promote(a):
    from vsp.improve import promote as P
    res = P.promote(a.pack, budget=a.budget, loader=a.loader, python=a.python, log=_log)
    print(P.render(res))
    return 0 if res["verdict"] == "ACCEPT" else 1


def cmd_verify(a):
    from vsp.improve import verify as V
    res = V.verify(a.base, a.cand, budget=a.budget, python=a.python, log=_log)
    print(V.render(res))
    return 0 if res["verdict"] == "ACCEPT" else 1


def cmd_refresh(a):
    from vsp.improve import refresh as R
    res = R.golden_refresh(max_new=a.max_new, dry_run=a.dry_run, log=_log)
    print(R.render(res))
    return 0


def cmd_delegate(a):
    from vsp.improve import delegate as G
    res = G.delegate(a.task_id, timeout=a.timeout, budget=a.budget, log=_log)
    print(G.render(res))
    return 0 if res.get("ok") else 1


def cmd_cycle(a):
    from vsp.improve import cycle as Y
    res = Y.cycle(budget=a.budget, use_llm=a.llm, python=a.python, log=_log)
    print(Y.render(res))
    return 0 if res.get("ok") else 1


def cmd_selfcheck(a):
    from vsp.improve.checks import selfcheck
    ok, lines = selfcheck(verbose=a.verbose)
    print("\n".join(lines))
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m vsp.improve",
                                 description="viral script pipeline self-improvement engine")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def budget(p, default):
        p.add_argument("--budget", choices=("small", "full"), default=default)

    p = sub.add_parser("measure", help="scorecard golden + holdout (+ capability)")
    budget(p, "full")
    p.add_argument("--python", default=None, help="interpreter for pipeline runs")
    p.set_defaults(fn=cmd_measure)

    p = sub.add_parser("diagnose", help="DIAGNOSIS.md + TASKS.md from the latest measure")
    p.add_argument("--base", default=None, help="base ref for acceptance commands")
    p.add_argument("--top", type=int, default=5)
    p.set_defaults(fn=cmd_diagnose)

    p = sub.add_parser("evolve", help="evolve hook templates into a proposed pack")
    budget(p, "full")
    p.add_argument("--llm", choices=("auto", "on", "off"), default="auto",
                   help="LLM reflective mutations (auto = only if configured)")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--dry-run", action="store_true", help="do not write a pack")
    p.set_defaults(fn=cmd_evolve)

    p = sub.add_parser("promote", help="A/B a pack with the full scorecard")
    p.add_argument("pack", help="pack path, file name or id")
    budget(p, "full")
    p.add_argument("--loader", choices=("auto", "native", "emulate"), default="auto")
    p.add_argument("--python", default=None)
    p.set_defaults(fn=cmd_promote)

    p = sub.add_parser("verify", help="ACCEPT/REJECT a candidate ref against a base ref")
    p.add_argument("--base", required=True, help="git ref or directory")
    p.add_argument("--cand", required=True, help="git ref or directory ('.' = working tree)")
    budget(p, "full")
    p.add_argument("--python", default=None)
    p.set_defaults(fn=cmd_verify)

    p = sub.add_parser("golden-refresh", help="trending products -> evals/capability.jsonl")
    p.add_argument("--max-new", type=int, default=10)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_refresh)

    p = sub.add_parser("delegate", help="hand a task to Muse Code, then verify")
    p.add_argument("task_id")
    p.add_argument("--timeout", type=int, default=3600)
    budget(p, "full")
    p.set_defaults(fn=cmd_delegate)

    p = sub.add_parser("cycle", help="health -> measure -> diagnose -> evolve -> promote")
    budget(p, "small")
    p.add_argument("--llm", choices=("auto", "on", "off"), default="auto")
    p.add_argument("--python", default=None)
    p.set_defaults(fn=cmd_cycle)

    p = sub.add_parser("selfcheck", help="hermetic checks (no network)")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(fn=cmd_selfcheck)

    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except KeyboardInterrupt:
        return 130
    except Exception as e:  # noqa: BLE001 — one clear line, exit 2
        from vsp.improve.common import ImproveError
        if isinstance(e, ImproveError):
            print(f"vsp.improve {a.cmd}: {e}", file=sys.stderr)
            return 2
        raise


if __name__ == "__main__":
    sys.exit(main())
