"""vsp.improve — the pipeline's self-improvement engine.

    python3 -m vsp.improve <cmd>

    measure        scorecard golden + holdout (+ capability) -> learned/evals/
    diagnose       ranked opportunities + agent tasks -> learned/DIAGNOSIS.md, TASKS.md
    evolve         GEPA / MAP-Elites-lite hook templates -> learned/hook_packs/ (proposed)
    promote PACK   full-scorecard A/B of a pack -> approved | rejected + LEDGER.md
    verify         --base REF --cand REF: self-test + scorecards + guard -> ACCEPT | REJECT
    golden-refresh trending products -> evals/capability.jsonl (never golden/holdout)
    delegate ID    hand a task to Muse Code (`muse exec`) in a fresh worktree, then verify
    cycle          health -> measure -> diagnose -> evolve -> promote -> ledger
    selfcheck      hermetic checks (no network): selfcheck() -> (ok, lines)

Guardrails (docs/ws-improve-notes.md): automation never edits gate or rule
code to pass, never pushes to main and never merges its own PRs; every change
goes through verify; holdout and audit-only checks detect gaming; the LLM is
advisory and never a gate; every decision lands in learned/LEDGER.md.
"""

VERSION = "1.0"


def selfcheck(verbose=False):
    """Hermetic self-check (MockProvider, a localhost stub server, synthetic
    scorecards). -> (ok, lines). Never touches the network or the repo."""
    from vsp.improve.selfcheck import selfcheck as _run
    return _run(verbose=verbose)
