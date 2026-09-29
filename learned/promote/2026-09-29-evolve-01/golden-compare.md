# Scorecard: promote-2026-09-29-evolve-01-base-golden → promote-2026-09-29-evolve-01-cand-golden

Paired runs: 330 (same prompt × format × presenter × seed).

| metric | promote-2026-09-29-evolve-01-base-golden | promote-2026-09-29-evolve-01-cand-golden | change |
|---|---|---|---|
| e2e pass | 100.0% | 100.0% | 1.0× |
| shippable | 100.0% | 100.0% | 1.0× |
| gate1 pass | 100.0% | 100.0% | 1.0× |
| crash rate | 0.0% | 0.0% | — |
| rubric mean | 99.9 | 99.9 | +0.0 |
| rubric audit-only mean | 100.0 | 100.0 | +0.0 |
| fallback-hook rate | 0.0% | 0.0% | eliminated |
| hook distinct-2 | 0.1648 | 0.1641 | 1.0× |
| compliance flags (total) | 0 | 0 | — |
| runtime / run (s) | 0.173 | 0.175 | 1.0× |

- e2e pass flips: 0 fail→pass, 0 pass→fail; exact McNemar p = 1
- shippable flips: 0 up, 0 down; exact McNemar p = 1
- rubric Δ (paired, prompt-clustered bootstrap): +0.0 [95% CI +0.0, +0.0]

## promote-2026-09-29-evolve-01-base-golden

# Scorecard — promote-2026-09-29-evolve-01-base-golden (None, /usr/bin/python3.9)
330 runs · 33 prompts × 5 formats × 2 presenters × 1 seeds × 1 durations · wall 8.0s

- crash: 0/330 = 0.0% (95% CI 0.0%–1.1%)
- gate1_pass: 330/330 = 100.0% (95% CI 98.9%–100.0%)
- e2e_pass: 330/330 = 100.0% (95% CI 98.9%–100.0%)
- shippable: 330/330 = 100.0% (95% CI 98.9%–100.0%)
- rubric: mean 99.9 · median 100.0 · p10 100.0 · selection 99.9 · audit 100.0 (n=330)
- hooks: fallback 0.0% · distinct 44.5% · distinct-2 0.1648 · seed diversity None
- re-hook repeat rate: 0.0%
- compliance flags: none
- rubric check failures: {'R14': 10}
- top gate failures: none
- e2e by concept: {'product': 1.0, 'showcase': 1.0, 'challenge': 1.0, 'advice': 1.0, 'routine': 1.0}
- e2e by format: {'demo': 1.0, 'pov-vlog': 1.0, 'review': 1.0, 'talking-head': 1.0, 'transformation': 1.0}
- runtime: 0.173s/run · artifacts none

## promote-2026-09-29-evolve-01-cand-golden

# Scorecard — promote-2026-09-29-evolve-01-cand-golden (None, /usr/bin/python3.9)
330 runs · 33 prompts × 5 formats × 2 presenters × 1 seeds × 1 durations · wall 8.1s

- crash: 0/330 = 0.0% (95% CI 0.0%–1.1%)
- gate1_pass: 330/330 = 100.0% (95% CI 98.9%–100.0%)
- e2e_pass: 330/330 = 100.0% (95% CI 98.9%–100.0%)
- shippable: 330/330 = 100.0% (95% CI 98.9%–100.0%)
- rubric: mean 99.9 · median 100.0 · p10 100.0 · selection 99.9 · audit 100.0 (n=330)
- hooks: fallback 0.0% · distinct 47.6% · distinct-2 0.1641 · seed diversity None
- re-hook repeat rate: 0.0%
- compliance flags: none
- rubric check failures: {'R14': 10}
- top gate failures: none
- e2e by concept: {'product': 1.0, 'showcase': 1.0, 'challenge': 1.0, 'advice': 1.0, 'routine': 1.0}
- e2e by format: {'demo': 1.0, 'pov-vlog': 1.0, 'review': 1.0, 'talking-head': 1.0, 'transformation': 1.0}
- runtime: 0.175s/run · artifacts none
