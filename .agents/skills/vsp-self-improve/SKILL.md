---
name: vsp-self-improve
description: Measure, diagnose and safely improve the pipeline itself
version: 2.0.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [evals, self-improvement, code]
    category: engineering
    requires_toolsets: [terminal, file]
    related_skills: [vsp-research, vsp-feedback]
---
# Improve the pipeline itself

## When to Use
Weekly, after a research refresh, after new feedback priors, or when the
user asks to make the pipeline better.

## Procedure
1. Baseline health: `python3 pipeline.py --self-test` (must be green).
2. Run a cycle: `python3 -m vsp.improve cycle --budget small`
   (use `--budget full` weekly). It measures golden + holdout + capability,
   writes `learned/DIAGNOSIS.md` and `learned/TASKS.md`, evolves hook
   templates into a proposed pack, A/B tests it on the full scorecard and
   approves or rejects it, and logs everything in `learned/LEDGER.md`.
3. Read `learned/CYCLE.md`. Commit the tracked `learned/` changes on a new
   branch and open a PR with the CYCLE summary.
4. For a code task from `learned/TASKS.md`:
   - make a branch: `git switch -c improve/<task-id>`
   - either hand it to Muse Code: `python3 -m vsp.improve delegate <TASK_ID>`
     (runs `muse exec` in a worktree), or edit the code yourself
   - accept only if `python3 -m vsp.improve verify --base main --cand HEAD`
     prints ACCEPT, then open a PR with its evidence
5. New trending products: `python3 -m vsp.improve golden-refresh` adds them to
   `evals/capability.jsonl` so the next cycle measures them.

## Pitfalls
- Never edit `vsp/gates.py`, `vsp/rules.py`, `vsp/lexicon.py` or
  `vsp/rubric.py` to make a metric go up. `verify` rejects weakening diffs;
  the rubric's audit-only checks and the holdout set catch gaming.
- Never tune on `evals/holdout.jsonl`. Never merge your own PR or push to
  `main`.
- The LLM (Muse Spark) is advisory: it proposes hook templates and judges
  pairs, it never decides a gate or an acceptance.
- A REJECT is a result, not a failure. Record it and move on.

## Verification
`learned/LEDGER.md` has a new entry with its evidence, the self-test is
green, and any PR carries a `verify` ACCEPT.
