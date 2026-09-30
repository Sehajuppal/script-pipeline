# verify — ACCEPT

- base `8d7f87d` (worktree 8d7f87d5394b) · cand `HEAD` (worktree cefcf7c19f1d)
- budget small (seeds 1); yardstick = the base tree's scorecard, rubric and suites; engine `cefcf7c`
- self-test green (3.9.25 rc 0, 3.12.14 rc 0)

## Checks

| check | ok | detail |
|---|---|---|
| golden:R1-e2e | ✅ | e2e flips 0 up / 0 down, McNemar p=1 |
| golden:R2-shippable | ✅ | shippable flips 0 up / 0 down, McNemar p=1 |
| golden:R3-rubric-ci | ✅ | rubric Δ +5.71 [95% CI +4.82, +6.60] (floor -0.5) |
| golden:R4-audit | ✅ | audit-only mean 95.1 → 95.8 (max drop 0.5) |
| golden:R6-compliance | ✅ | candidate compliance flags: 0 |
| golden:R8-coverage | ✅ | 330 paired runs, 0 base cases missing in cand |
| holdout:R1-e2e | ✅ | e2e flips 0 up / 0 down, McNemar p=1 |
| holdout:R2-shippable | ✅ | shippable flips 0 up / 0 down, McNemar p=1 |
| holdout:R3-rubric-ci | ✅ | rubric Δ +5.15 [95% CI +4.40, +5.92] (floor -0.5) |
| holdout:R4-audit | ✅ | audit-only mean 93.3 → 94.1 (max drop 0.5) |
| holdout:R6-compliance | ✅ | candidate compliance flags: 0 |
| holdout:R8-coverage | ✅ | 350 paired runs, 0 base cases missing in cand |
| holdout:R5-not-lower | ✅ | holdout e2e 1.0 → 1.0, shippable 1.0 → 1.0, rubric 92.8 → 97.9 |
| R7-selftest | ✅ | self-test green |
| R9-guard | ✅ | no gate/rule/lexicon weakening |

## Headline

- golden: e2e 1.0→1.0 (flips +0/−0, p=1) · shippable 1.0→1.0 · rubric 93.2→98.9 Δ +5.71 [+4.82, +6.60] · audit 95.1→95.8 · compliance 0 · hooks changed 168/330 · distinct 0.5909→0.6333 · distinct-2 0.1941→0.2102
- holdout: e2e 1.0→1.0 (flips +0/−0, p=1) · shippable 1.0→1.0 · rubric 92.8→97.9 Δ +5.15 [+4.40, +5.92] · audit 93.3→94.1 · compliance 0 · hooks changed 187/350 · distinct 0.5543→0.58 · distinct-2 0.187→0.1948

## Diversity

- golden: hook distinct ratio 0.5909 → 0.6333 (+0.0424) · distinct-2 0.1941 → 0.2102 (+0.0161) · per-cell seed diversity None → None
- holdout: hook distinct ratio 0.5543 → 0.58 (+0.0257) · distinct-2 0.187 → 0.1948 (+0.0078) · per-cell seed diversity None → None

## Weakening guard

- guarded files changed: none
- yardstick changed: none
- registry rules 46 → 46; self-test cases 112 → 112 (legacy 17 → 17)
- no weakening found

## Diff (22 files)

- `.agents/skills/vsp-feedback/SKILL.md` +17 −9
- `.agents/skills/vsp-produce/SKILL.md` +17 −9
- `AGENTS.md` +20 −3
- `README.md` +43 −19
- `RULES.md` +105 −0
- `agent/README.md` +6 −3
- `agent/hermes/scripts/vsp-variants.sh` +11 −0
- `docs/RULE-COVERAGE.md` +47 −47
- `docs/SCORECARD-v2.1.md` +78 −0
- `evals/results/baseline-v21.json` +104201 −0
- `evals/results/v2.0-holdout-v21.json` +106897 −0
- `evals/results/v2.0-v21.json` +100744 −0
- `evals/results/v2.1-holdout.json` +99594 −0
- `evals/results/v2.1.json` +93470 −0
- `pipeline.py` +73 −7
- `viral_script_maker.py` +99 −6
- `vsp/creative.py` +44 −0
- `vsp/direction.py` +35 −2
- `vsp/hooks.py` +281 −21
- `vsp/repair.py` +10 −0
- `vsp/selftest_cases.py` +56 −2
- `vsp/shotplan.py` +46 −7

## Scorecard compare reports

- golden: `learned/verify/20260929T184339Z-8d7f87d5394b-cefcf7c19f1d/golden-compare.md`
- holdout: `learned/verify/20260929T184339Z-8d7f87d5394b-cefcf7c19f1d/holdout-compare.md`
