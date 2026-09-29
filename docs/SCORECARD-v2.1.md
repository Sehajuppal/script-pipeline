# Scorecard — pipeline v2.1 (creative layer)

The v2.1 harness (`evals/scorecard.py`, rubric R01–R28, `vsp/creative_eval.py`) re-scored all three versions. Every run uses the hermetic fixture reference DB. Pairs share the same prompt, format, presenter and seed. "Holdout" (`evals/holdout.jsonl`) was only measured, never tuned against. Raw results are in `evals/results/{baseline-v21,v2.0-v21,v2.0-holdout-v21,v2.1,v2.1-holdout}.json`.

## Baseline → v2.1 (golden, 990 runs)

| metric | baseline | v2.1 | change |
|---|---|---|---|
| e2e pass | 0.0% | 100.0% | ∞ |
| gate 1 pass | 1.5% | 100.0% | 65.8× |
| crash rate | 9.7% | 0.0% | eliminated |
| rubric mean (R01–R28) | 56.2 | 98.9 | +42.7 |
| rubric mean, v2.0 scale (R01–R20) | 70.9 | 100.0 | +29.1 |
| fallback-hook rate | 58.4% | 0.0% | eliminated |
| hook distinct-2 | 0.0229 | 0.0935 | 4.1× |
| compliance flags | 162 | 0 | eliminated |
| hook strength (independent scorer) | 45.3 | 75.5 | +30.3 |
| hook variants / script | 0 | 4.55 | new |
| keyword placement pass (D161) | 0% | 93.2% | new |
| shot plan pass (typed, D157-clean) | 0% | 100% | new |

McNemar on e2e: 990 fail→pass, 0 pass→fail (p = 1.9e-298). Paired rubric Δ is +48.2 (95% CI +44.2 to +53.6, prompt-clustered bootstrap).

## v2.0 → v2.1 (golden 990 runs / holdout 1050 runs)

| metric | v2.0 golden | v2.1 golden | v2.0 holdout | v2.1 holdout |
|---|---|---|---|---|
| e2e pass | 100% | 100% | 100% | 100% |
| rubric mean (R01–R28) | 77.6 | 98.9 | 77.6 | 97.9 |
| rubric audit-only mean | 60.0 | 95.8 | 60.0 | 94.1 |
| hook distinct (share of runs) | 28.5% | 38.5% | 27.6% | 33.9% |
| hook distinct-2 | 0.0784 | 0.0935 | 0.0776 | 0.0868 |
| hook strength (independent scorer) | 62.9 | 75.5 | 63.2 | 72.7 |
| hook variants / script (distinct archetypes + frame-0 types) | 0 | 4.55 | 0 | 4.45 |
| keyword spoken/on screen by 3 s + caption line 1 + tag (D161) | 0% | 93.2% | 0% | 76.8% |
| shot list typed, D157-clean | 0% | 100% | 0% | 100% |
| shot cadence inside the direction's band | — | 72.8% | — | 70.6% |
| bundle creative sections (of 4) | 0 | 4 | 0 | 4 |
| gate-1 creative findings (D154–D156, D158) | — | 0 | — | 0 |
| runtime / run | 0.535 s | 1.482 s | 0.548 s | 1.541 s |

Paired rubric Δ is +21.3 on golden (95% CI +20.7 to +21.7) and +20.3 on holdout (+19.5 to +21.2). e2e has 0 flips in either direction.

## Finishing pass (integration build 8d7f87d → final)

`tools/fast_eval.py --gate2` ran golden + holdout at 15/30/60 s with seeds 1 and 2: 4,080 runs per build, maker-level with no best-of-8. Both builds pass 100% e2e with 0 gate failures.

| rubric check (fail runs) | 8d7f87d | final |
|---|---|---|
| R21 direction coherent (vibe cadence) | 2762 | 0 |
| R22 variants diverse (unique cards, archetypes) | 2991 | 168 |
| R24 keyword by 3 s (D161) | 2244 | 789 |
| R27 no near-duplicate openings (audit) | 360 | 0 |
| R23 opening strength (audit) | 984 | 1040 |
| rubric mean | 91.6 | 98.0 |
| distinct primary hooks per 1,360 runs (maker level) | 725 | 650 |

The drop in maker-level distinct hooks is the cost of preferring lines that speak the search keyword. At pipeline level (best-of-8 plus selection), distinct hooks still rose from 28.5% (v2.0) to 38.5%.

## Known gaps (next work, not hidden)

- **R23 (audit only, 200 golden runs):** the independent evaluator does not count "here's what 7 days showed" as paid by a transformation payoff. The generator's scorer does. This is an evaluator/generator disagreement and needs human labels to settle. The finishing pass first *raised* R23; `vsp.improve verify` rejected that build. Alternates now clear HOOK-08's floor by the scorer tie margin (0.58), and a 5th opening needs 0.65.
- **R24 residual:** the keyword is not spoken when:
  - practice-challenge pins say "Day 30 of reading 10 pages", but the keyword is "30 day reading challenge";
  - advice keywords such as "hook tips" are not spoken;
  - 3-word product keywords do not fit an 8-word hook.
- **Calm-vibe cadence:** fixed short structural shots pull the average shot length under the band for cozy-calm (band 3.0–4.5 s). These are the 0.5 s frame 0 and the split payoff.
- **Advice mode** is creator-specific ("fix the first 3 seconds"). Non-creator topics need topic content, from an LLM or topic packs.
- **Runtime:** 2.6× slower (creative layer plus shot plan), still about 1.4 s per full 10-stage run.

## Acceptance

`python3 -m vsp.improve verify --base 8d7f87d --cand cefcf7c` returned ACCEPT. The evidence is in `learned/verify/20260929T184339Z-*/`:

| check | golden | holdout |
|---|---|---|
| rubric (with 95% CI) | 93.2 → 98.9 (Δ +5.71, CI +4.82 to +6.60) | 92.8 → 97.9 |
| audit | 95.1 → 95.8 | 93.3 → 94.1 |
| e2e flips | 0 | 0 |

The self-test was green on 3.9 and 3.12, and the weakening guard found nothing. The first verify of this pass rejected the build (golden audit fell 95.1 → 94.4). That is why the alternate floors above changed.

## Reproduce

```bash
python3 evals/scorecard.py run --label v2.1 --workers 12 --out evals/results/v2.1.json
python3 evals/scorecard.py run --label v2.1-holdout --golden evals/holdout.jsonl --workers 12 --out evals/results/v2.1-holdout.json
python3 evals/scorecard.py run --label v2.0 --repo <worktree at f6d93dd> --workers 12 --out evals/results/v2.0-v21.json
python3 evals/scorecard.py run --label baseline --repo <worktree at d8f8759> --python python3.12 --workers 12 --out evals/results/baseline-v21.json
python3 evals/scorecard.py compare evals/results/v2.0-v21.json evals/results/v2.1.json
```
