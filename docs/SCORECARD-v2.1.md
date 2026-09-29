# Scorecard — pipeline v2.1 (creative layer)

The v2.1 harness (`evals/scorecard.py`, rubric R01–R28, `vsp/creative_eval.py`) re-scored all three versions. Every run uses the hermetic fixture reference DB. Pairs share the same prompt, format, presenter and seed. "Holdout" (`evals/holdout.jsonl`) was only measured, never tuned against. Raw results are in `evals/results/{baseline-v21,v2.0-v21,v2.0-holdout-v21,v2.1,v2.1-holdout}.json`.

## Baseline → v2.1 (golden, 990 runs)

| metric | baseline | v2.1 | change |
|---|---|---|---|
| e2e pass | 0.0% | 100.0% | ∞ |
| gate 1 pass | 1.5% | 100.0% | 65.8× |
| crash rate | 9.7% | 0.0% | eliminated |
| rubric mean (R01–R28) | 56.2 | 98.7 | +42.5 |
| rubric mean, v2.0 scale (R01–R20) | 70.9 | 100.0 | +29.1 |
| fallback-hook rate | 58.4% | 0.0% | eliminated |
| hook distinct-2 | 0.0229 | 0.0935 | 4.1× |
| compliance flags | 162 | 0 | eliminated |
| hook strength (independent scorer) | 45.3 | 75.5 | +30.3 |
| hook variants / script | 0 | 4.73 | new |
| keyword placement pass (D161) | 0% | 93.2% | new |
| shot plan pass (typed, D157-clean) | 0% | 100% | new |

McNemar on e2e: 990 fail→pass, 0 pass→fail (p = 1.9e-298). Paired rubric Δ is +47.9 (95% CI +43.9 to +53.4, prompt-clustered bootstrap).

## v2.0 → v2.1 (golden 990 runs / holdout 1050 runs)

| metric | v2.0 golden | v2.1 golden | v2.0 holdout | v2.1 holdout |
|---|---|---|---|---|
| e2e pass | 100% | 100% | 100% | 100% |
| rubric mean (R01–R28) | 77.6 | 98.7 | 77.6 | 97.7 |
| rubric audit-only mean | 60.0 | 94.5 | 60.0 | 92.8 |
| hook distinct (share of runs) | 28.5% | 38.5% | 27.6% | 33.9% |
| hook distinct-2 | 0.0784 | 0.0935 | 0.0776 | 0.0868 |
| hook strength (independent scorer) | 62.9 | 75.5 | 63.2 | 72.7 |
| hook variants / script (distinct archetypes + frame-0 types) | 0 | 4.73 | 0 | 4.62 |
| keyword spoken/on screen by 3 s + caption line 1 + tag (D161) | 0% | 93.2% | 0% | 76.8% |
| shot list typed, D157-clean | 0% | 100% | 0% | 100% |
| shot cadence inside the direction's band | — | 72.8% | — | 70.6% |
| bundle creative sections (of 4) | 0 | 4 | 0 | 4 |
| gate-1 creative findings (D154–D156, D158) | — | 0 | — | 0 |
| runtime / run | 0.535 s | 1.389 s | 0.548 s | 1.53 s |

Paired rubric Δ is +21.0 on golden (95% CI +20.5 to +21.4) and +20.1 on holdout (+19.3 to +20.9). e2e has 0 flips in either direction.

## Finishing pass (integration build 8d7f87d → final)

`tools/fast_eval.py --gate2` ran golden + holdout at 15/30/60 s with seeds 1 and 2: 4,080 runs per build, maker-level with no best-of-8. Both builds pass 100% e2e with 0 gate failures.

| rubric check (fail runs) | 8d7f87d | final |
|---|---|---|
| R21 direction coherent (vibe cadence) | 2762 | 0 |
| R22 variants diverse (unique cards, archetypes) | 2991 | 168 |
| R24 keyword by 3 s (D161) | 2244 | 789 |
| R27 no near-duplicate openings (audit) | 360 | 0 |
| rubric mean | 91.6 | 97.8 |
| distinct primary hooks per 1,360 runs (maker level) | 725 | 650 |

The drop in maker-level distinct hooks is the cost of preferring lines that speak the search keyword. At pipeline level (best-of-8 plus selection), distinct hooks still rose from 28.5% (v2.0) to 38.5%.

## Known gaps (next work, not hidden)

- **R23 (audit only, 262 golden runs):** the independent evaluator does not count "here's what 7 days showed" as paid by a transformation payoff. The generator's scorer does. This is an evaluator/generator disagreement. It is left as-is and needs human labels to settle.
- **R24 residual:** the keyword is not spoken when:
  - practice-challenge pins say "Day 30 of reading 10 pages", but the keyword is "30 day reading challenge";
  - advice keywords such as "hook tips" are not spoken;
  - 3-word product keywords do not fit an 8-word hook.
- **Calm-vibe cadence:** fixed short structural shots pull the average shot length under the band for cozy-calm (band 3.0–4.5 s). These are the 0.5 s frame 0 and the split payoff.
- **Advice mode** is creator-specific ("fix the first 3 seconds"). Non-creator topics need topic content, from an LLM or topic packs.
- **Runtime:** 2.6× slower (creative layer plus shot plan), still about 1.4 s per full 10-stage run.

## Reproduce

```bash
python3 evals/scorecard.py run --label v2.1 --workers 12 --out evals/results/v2.1.json
python3 evals/scorecard.py run --label v2.1-holdout --golden evals/holdout.jsonl --workers 12 --out evals/results/v2.1-holdout.json
python3 evals/scorecard.py run --label v2.0 --repo <worktree at f6d93dd> --workers 12 --out evals/results/v2.0-v21.json
python3 evals/scorecard.py run --label baseline --repo <worktree at d8f8759> --python python3.12 --workers 12 --out evals/results/baseline-v21.json
python3 evals/scorecard.py compare evals/results/v2.0-v21.json evals/results/v2.1.json
```
