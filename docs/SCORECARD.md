# Scorecard: baseline → v2

Paired runs: 990 (same prompt × format × presenter × seed).

| metric | baseline | v2 | change |
|---|---|---|---|
| e2e pass | 0.0% | 100.0% | ∞ |
| shippable | 0.0% | 100.0% | ∞ |
| gate1 pass | 1.5% | 100.0% | 65.8× |
| crash rate | 9.7% | 0.0% | eliminated |
| rubric mean | 70.9 | 99.9 | +29.0 |
| rubric audit-only mean | 72.7 | 99.9 | +27.2 |
| fallback-hook rate | 58.4% | 0.0% | eliminated |
| hook distinct-2 | 0.0229 | 0.0784 | 3.4× |
| compliance flags (total) | 162 | 0 | eliminated |
| runtime / run (s) | 0.37 | 0.534 | 1.4× |

- e2e pass flips: 990 fail→pass, 0 pass→fail; exact McNemar p = 1.91e-298
- shippable flips: 990 up, 0 down; exact McNemar p = 1.91e-298
- rubric Δ (paired, prompt-clustered bootstrap): +35.9 [95% CI +31.1, +42.6]

## baseline

# Scorecard — baseline (d8f8759, python3.12)
990 runs · 33 prompts × 5 formats × 2 presenters × 3 seeds × 1 durations · wall 33.2s

- crash: 96/990 = 9.7% (95% CI 8.0%–11.7%)
- gate1_pass: 15/990 = 1.5% (95% CI 0.9%–2.5%)
- e2e_pass: 0/990 = 0.0% (95% CI 0.0%–0.4%)
- shippable: 0/990 = 0.0% (95% CI 0.0%–0.4%)
- rubric: mean 70.9 · median 67.6 · p10 62.2 · selection 70.7 · audit 72.7 (n=894)
- hooks: fallback 58.4% · distinct 3.5% · distinct-2 0.0229 · seed diversity 0.3579
- re-hook repeat rate: 0.0%
- compliance flags: {'R06': 162}
- rubric check failures: {'R02': 702, 'R03': 843, 'R04': 87, 'R06': 162, 'R07': 139, 'R08': 606, 'R09': 660, 'R12': 616, 'R13': 120, 'R14': 108, 'R15': 180, 'R20': 786}
- top gate failures: {'D103': 660, 'D43': 609, 'D74': 549, 'D78': 252, 'D94': 243, 'D44': 54, 'TAG-MISMATCH': 30, 'D47': 15, 'D48': 15}
- e2e by concept: {'product': 0.0, 'showcase': 0.0, 'challenge': 0.0, 'advice': 0.0, 'routine': 0.0}
- e2e by format: {'demo': 0.0, 'pov-vlog': 0.0, 'review': 0.0, 'talking-head': 0.0, 'transformation': 0.0}
- runtime: 0.37s/run · artifacts none

## v2

# Scorecard — v2 (1dc5a60, /usr/bin/python3.9)
990 runs · 33 prompts × 5 formats × 2 presenters × 3 seeds × 1 durations · wall 47.7s

- crash: 0/990 = 0.0% (95% CI 0.0%–0.4%)
- gate1_pass: 990/990 = 100.0% (95% CI 99.6%–100.0%)
- e2e_pass: 990/990 = 100.0% (95% CI 99.6%–100.0%)
- shippable: 990/990 = 100.0% (95% CI 99.6%–100.0%)
- rubric: mean 99.9 · median 100.0 · p10 100.0 · selection 99.9 · audit 99.9 (n=990)
- hooks: fallback 0.0% · distinct 28.5% · distinct-2 0.0784 · seed diversity 0.7071
- re-hook repeat rate: 0.0%
- compliance flags: none
- rubric check failures: {'R12': 2, 'R14': 30}
- top gate failures: none
- e2e by concept: {'product': 1.0, 'showcase': 1.0, 'challenge': 1.0, 'advice': 1.0, 'routine': 1.0}
- e2e by format: {'demo': 1.0, 'pov-vlog': 1.0, 'review': 1.0, 'talking-head': 1.0, 'transformation': 1.0}
- runtime: 0.534s/run · artifacts {'captions.srt': 990, 'shotlist.csv': 990, 'manifest.json': 990, 'trace.jsonl': 990, 'captions.vtt': 990, 'gate-report.json': 990}
