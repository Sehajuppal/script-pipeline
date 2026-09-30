# Scorecard: verify-8d7f87d-head-base-holdout → verify-8d7f87d-head-cand-holdout

Paired runs: 350 (same prompt × format × presenter × seed).

| metric | verify-8d7f87d-head-base-holdout | verify-8d7f87d-head-cand-holdout | change |
|---|---|---|---|
| e2e pass | 100.0% | 100.0% | 1.0× |
| shippable | 100.0% | 100.0% | 1.0× |
| gate1 pass | 100.0% | 100.0% | 1.0× |
| crash rate | 0.0% | 0.0% | — |
| rubric mean | 92.8 | 97.9 | +5.1 |
| rubric mean, v2.0 scale (R01-R20) | 100.0 | 100.0 | +0.0 |
| rubric audit-only mean | 93.3 | 94.1 | +0.8 |
| fallback-hook rate | 0.0% | 0.0% | eliminated |
| hook distinct-2 | 0.187 | 0.1948 | 1.0× |
| compliance flags (total) | 0 | 0 | — |
| runtime / run (s) | 0.978 | 1.027 | 1.1× |
| hook variants / script | 4.729 | 4.446 | -0.28 |
| keyword placement pass (D161) | 60.9% | 76.6% | +15.7 pts |
| shot plan pass (typed, D157-clean) | 100.0% | 100.0% | +0.0 pts |
| hook strength (independent scorer) | 70.7 | 72.7 | +1.9 |
| v2.1 bundle sections / run (of 4) | 4 | 4 | +0.00 |

- e2e pass flips: 0 fail→pass, 0 pass→fail; exact McNemar p = 1
- shippable flips: 0 up, 0 down; exact McNemar p = 1
- rubric Δ (paired, prompt-clustered bootstrap): +5.2 [95% CI +4.4, +5.9]

## verify-8d7f87d-head-base-holdout

# Scorecard — verify-8d7f87d-head-base-holdout (8d7f87d, /usr/bin/python3.9)
350 runs · 35 prompts × 5 formats × 2 presenters × 1 seeds × 1 durations · wall 47.9s

- crash: 0/350 = 0.0% (95% CI 0.0%–1.1%)
- gate1_pass: 350/350 = 100.0% (95% CI 98.9%–100.0%)
- e2e_pass: 350/350 = 100.0% (95% CI 98.9%–100.0%)
- shippable: 350/350 = 100.0% (95% CI 98.9%–100.0%)
- rubric: mean 92.8 · median 93.0 · p10 86.3 · selection 92.6 · audit 93.3 (n=350)
- hooks: fallback 0.0% · distinct 55.4% · distinct-2 0.187 · seed diversity None
- re-hook repeat rate: 0.0%
- compliance flags: none
- rubric check failures: {'R21': 247, 'R22': 186, 'R23': 95, 'R24': 137, 'R26': 8, 'R27': 35}
- top gate failures: none
- e2e by concept: {'product': 1.0, 'showcase': 1.0, 'routine': 1.0, 'challenge': 1.0, 'advice': 1.0}
- e2e by format: {'demo': 1.0, 'pov-vlog': 1.0, 'review': 1.0, 'talking-head': 1.0, 'transformation': 1.0}
- runtime: 0.978s/run · artifacts {'captions.srt': 350, 'shotlist.csv': 350, 'manifest.json': 350, 'trace.jsonl': 350, 'captions.vtt': 350, 'gate-report.json': 350}
- creative: hook variants/script 4.729 · distinct visual types 4.729 · keyword placement 60.9% · hook strength 70.7 (primary variant 70.1) · vibes {'asmr-satisfying': 6, 'before-after-reveal': 56, 'clean-aesthetic': 120, 'cozy-calm': 8, 'expert-trust': 28, 'hype-energy': 12, 'playful-comedic': 12, 'raw-ugc': 61, 'story-vlog': 47}
- shot plan: pass 100.0% · typed 100.0% · cadence in band 188/350 · human by 3s 350/350 · frame-0 product/result 350/350 · loop <=15s 0/0 · AI real footage 10/175 · high AI risk 31.9%
- creative sections: 4/4 per run {'CREATIVE DIRECTION': 350, 'ALTERNATE OPENINGS': 350, 'SHOOT PLAN': 350, 'POSTING & DISCOVERY': 350} · with direction/variants/discovery 350/350/350 of 350 · findings D157 0 D159 0 D160 0 · gate-1 D154 0 D155 0 D156 0 D158 0 · creative_warnings runs 0
- rubric on the v2.0 scale (R01-R20; shippable uses it): mean 100.0 · rubric version R01-R28 (pipeline v2.1)

## verify-8d7f87d-head-cand-holdout

# Scorecard — verify-8d7f87d-head-cand-holdout (cefcf7c, /usr/bin/python3.9)
350 runs · 35 prompts × 5 formats × 2 presenters × 1 seeds × 1 durations · wall 49.8s

- crash: 0/350 = 0.0% (95% CI 0.0%–1.1%)
- gate1_pass: 350/350 = 100.0% (95% CI 98.9%–100.0%)
- e2e_pass: 350/350 = 100.0% (95% CI 98.9%–100.0%)
- shippable: 350/350 = 100.0% (95% CI 98.9%–100.0%)
- rubric: mean 97.9 · median 100.0 · p10 93.0 · selection 98.8 · audit 94.1 (n=350)
- hooks: fallback 0.0% · distinct 58.0% · distinct-2 0.1948 · seed diversity None
- re-hook repeat rate: 0.0%
- compliance flags: none
- rubric check failures: {'R22': 12, 'R23': 99, 'R24': 82, 'R26': 8}
- top gate failures: none
- e2e by concept: {'product': 1.0, 'showcase': 1.0, 'routine': 1.0, 'challenge': 1.0, 'advice': 1.0}
- e2e by format: {'demo': 1.0, 'pov-vlog': 1.0, 'review': 1.0, 'talking-head': 1.0, 'transformation': 1.0}
- runtime: 1.027s/run · artifacts {'captions.srt': 350, 'shotlist.csv': 350, 'manifest.json': 350, 'trace.jsonl': 350, 'captions.vtt': 350, 'gate-report.json': 350}
- creative: hook variants/script 4.446 · distinct visual types 4.446 · keyword placement 76.6% · hook strength 72.7 (primary variant 72.7) · vibes {'asmr-satisfying': 6, 'before-after-reveal': 56, 'clean-aesthetic': 120, 'cozy-calm': 8, 'expert-trust': 28, 'hype-energy': 12, 'playful-comedic': 12, 'raw-ugc': 61, 'story-vlog': 47}
- shot plan: pass 100.0% · typed 100.0% · cadence in band 235/350 · human by 3s 350/350 · frame-0 product/result 350/350 · loop <=15s 0/0 · AI real footage 10/175 · high AI risk 32.0%
- creative sections: 4/4 per run {'CREATIVE DIRECTION': 350, 'ALTERNATE OPENINGS': 350, 'SHOOT PLAN': 350, 'POSTING & DISCOVERY': 350} · with direction/variants/discovery 350/350/350 of 350 · findings D157 0 D159 0 D160 0 · gate-1 D154 0 D155 0 D156 0 D158 0 · creative_warnings runs 0
- rubric on the v2.0 scale (R01-R20; shippable uses it): mean 100.0 · rubric version R01-R28 (pipeline v2.1)
