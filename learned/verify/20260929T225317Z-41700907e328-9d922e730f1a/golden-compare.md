# Scorecard: verify-4170090-head-base-golden → verify-4170090-head-cand-golden

Paired runs: 330 (same prompt × format × presenter × seed).

| metric | verify-4170090-head-base-golden | verify-4170090-head-cand-golden | change |
|---|---|---|---|
| e2e pass | 100.0% | 100.0% | 1.0× |
| shippable | 100.0% | 100.0% | 1.0× |
| gate1 pass | 100.0% | 100.0% | 1.0× |
| crash rate | 0.0% | 0.0% | — |
| rubric mean | 98.9 | 98.9 | +0.0 |
| rubric mean, v2.0 scale (R01-R20) | 100.0 | 100.0 | +0.0 |
| rubric audit-only mean | 95.8 | 95.8 | +0.0 |
| fallback-hook rate | 0.0% | 0.0% | eliminated |
| hook distinct-2 | 0.2102 | 0.2102 | 1.0× |
| compliance flags (total) | 0 | 0 | — |
| runtime / run (s) | 0.933 | 0.977 | 1.0× |
| hook variants / script | 4.548 | 4.548 | +0.00 |
| keyword placement pass (D161) | 93.0% | 93.0% | +0.0 pts |
| shot plan pass (typed, D157-clean) | 100.0% | 100.0% | +0.0 pts |
| hook strength (independent scorer) | 75.6 | 75.6 | +0.0 |
| v2.1 bundle sections / run (of 4) | 4 | 4 | +0.00 |

- e2e pass flips: 0 fail→pass, 0 pass→fail; exact McNemar p = 1
- shippable flips: 0 up, 0 down; exact McNemar p = 1
- rubric Δ (paired, prompt-clustered bootstrap): +0.0 [95% CI +0.0, +0.0]

## verify-4170090-head-base-golden

# Scorecard — verify-4170090-head-base-golden (4170090, /usr/bin/python3.9)
330 runs · 33 prompts × 5 formats × 2 presenters × 1 seeds × 1 durations · wall 43.3s

- crash: 0/330 = 0.0% (95% CI 0.0%–1.1%)
- gate1_pass: 330/330 = 100.0% (95% CI 98.9%–100.0%)
- e2e_pass: 330/330 = 100.0% (95% CI 98.9%–100.0%)
- shippable: 330/330 = 100.0% (95% CI 98.9%–100.0%)
- rubric: mean 98.9 · median 100.0 · p10 96.1 · selection 99.6 · audit 95.8 (n=330)
- hooks: fallback 0.0% · distinct 63.3% · distinct-2 0.2102 · seed diversity None
- re-hook repeat rate: 0.0%
- compliance flags: none
- rubric check failures: {'R22': 5, 'R23': 66, 'R24': 23, 'R26': 8}
- top gate failures: none
- e2e by concept: {'product': 1.0, 'showcase': 1.0, 'challenge': 1.0, 'advice': 1.0, 'routine': 1.0}
- e2e by format: {'demo': 1.0, 'pov-vlog': 1.0, 'review': 1.0, 'talking-head': 1.0, 'transformation': 1.0}
- runtime: 0.933s/run · artifacts {'captions.srt': 330, 'shotlist.csv': 330, 'manifest.json': 330, 'trace.jsonl': 330, 'captions.vtt': 330, 'gate-report.json': 330}
- creative: hook variants/script 4.548 · distinct visual types 4.548 · keyword placement 93.0% · hook strength 75.6 (primary variant 75.6) · vibes {'before-after-reveal': 58, 'clean-aesthetic': 116, 'cozy-calm': 10, 'expert-trust': 22, 'hype-energy': 18, 'playful-comedic': 8, 'raw-ugc': 56, 'story-vlog': 42}
- shot plan: pass 100.0% · typed 100.0% · cadence in band 228/330 · human by 3s 330/330 · frame-0 product/result 330/330 · loop <=15s 0/0 · AI real footage 5/165 · high AI risk 32.7%
- creative sections: 4/4 per run {'CREATIVE DIRECTION': 330, 'ALTERNATE OPENINGS': 330, 'SHOOT PLAN': 330, 'POSTING & DISCOVERY': 330} · with direction/variants/discovery 330/330/330 of 330 · findings D157 0 D159 0 D160 0 · gate-1 D154 0 D155 0 D156 0 D158 0 · creative_warnings runs 0
- rubric on the v2.0 scale (R01-R20; shippable uses it): mean 100.0 · rubric version R01-R28 (pipeline v2.1)

## verify-4170090-head-cand-golden

# Scorecard — verify-4170090-head-cand-golden (9d922e7, /usr/bin/python3.9)
330 runs · 33 prompts × 5 formats × 2 presenters × 1 seeds × 1 durations · wall 45.5s

- crash: 0/330 = 0.0% (95% CI 0.0%–1.1%)
- gate1_pass: 330/330 = 100.0% (95% CI 98.9%–100.0%)
- e2e_pass: 330/330 = 100.0% (95% CI 98.9%–100.0%)
- shippable: 330/330 = 100.0% (95% CI 98.9%–100.0%)
- rubric: mean 98.9 · median 100.0 · p10 96.1 · selection 99.6 · audit 95.8 (n=330)
- hooks: fallback 0.0% · distinct 63.3% · distinct-2 0.2102 · seed diversity None
- re-hook repeat rate: 0.0%
- compliance flags: none
- rubric check failures: {'R22': 5, 'R23': 66, 'R24': 23, 'R26': 8}
- top gate failures: none
- e2e by concept: {'product': 1.0, 'showcase': 1.0, 'challenge': 1.0, 'advice': 1.0, 'routine': 1.0}
- e2e by format: {'demo': 1.0, 'pov-vlog': 1.0, 'review': 1.0, 'talking-head': 1.0, 'transformation': 1.0}
- runtime: 0.977s/run · artifacts {'captions.srt': 330, 'shotlist.csv': 330, 'manifest.json': 330, 'trace.jsonl': 330, 'captions.vtt': 330, 'gate-report.json': 330}
- creative: hook variants/script 4.548 · distinct visual types 4.548 · keyword placement 93.0% · hook strength 75.6 (primary variant 75.6) · vibes {'before-after-reveal': 58, 'clean-aesthetic': 116, 'cozy-calm': 10, 'expert-trust': 22, 'hype-energy': 18, 'playful-comedic': 8, 'raw-ugc': 56, 'story-vlog': 42}
- shot plan: pass 100.0% · typed 100.0% · cadence in band 228/330 · human by 3s 330/330 · frame-0 product/result 330/330 · loop <=15s 0/0 · AI real footage 5/165 · high AI risk 32.7%
- creative sections: 4/4 per run {'CREATIVE DIRECTION': 330, 'ALTERNATE OPENINGS': 330, 'SHOOT PLAN': 330, 'POSTING & DISCOVERY': 330} · with direction/variants/discovery 330/330/330 of 330 · findings D157 0 D159 0 D160 0 · gate-1 D154 0 D155 0 D156 0 D158 0 · creative_warnings runs 0
- rubric on the v2.0 scale (R01-R20; shippable uses it): mean 100.0 · rubric version R01-R28 (pipeline v2.1)
