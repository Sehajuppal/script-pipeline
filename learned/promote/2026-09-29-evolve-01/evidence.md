# promote `2026-09-29-evolve-01` — ACCEPT

- pack: `learned/hook_packs/2026-09-29-01.json` → status **approved**
- budget small (seeds 1), loader emulate, engine at `b867500`, 2026-09-29T05:41:06+00:00
- self-test green (3.9.25 rc 0, 3.12.14 rc 0)

## Templates

- `bold-claim`: 'Day {ndays} with the {category}. Zero failures.'
- `bold-claim`: 'Most {category_pl} fail. Not this one.'
- `curiosity-gap`: 'The {category}. Worth it?'
- `curiosity-gap`: 'I lived with the {category} for {ndays} days.'
- `curiosity-gap`: '{product}: the honest verdict.'
- `transformation`: "{product}. Here's the after."
- `transformation`: '{product} after {ndays} days. Worth it?'
- `transformation`: 'This is the after with {product}.'

## Checks

| check | ok | detail |
|---|---|---|
| golden:R1-e2e | ✅ | e2e flips 0 up / 0 down, McNemar p=1 |
| golden:R2-shippable | ✅ | shippable flips 0 up / 0 down, McNemar p=1 |
| golden:R3-rubric-ci | ✅ | rubric Δ +0.00 [95% CI +0.00, +0.00] (floor -0.5) |
| golden:R4-audit | ✅ | audit-only mean 100.0 → 100.0 (max drop 0.5) |
| golden:R6-compliance | ✅ | candidate compliance flags: 0 |
| golden:R8-coverage | ✅ | 330 paired runs, 0 base cases missing in cand |
| holdout:R1-e2e | ✅ | e2e flips 0 up / 0 down, McNemar p=1 |
| holdout:R2-shippable | ✅ | shippable flips 0 up / 0 down, McNemar p=1 |
| holdout:R3-rubric-ci | ✅ | rubric Δ +0.00 [95% CI +0.00, +0.00] (floor -0.5) |
| holdout:R4-audit | ✅ | audit-only mean 100.0 → 100.0 (max drop 0.5) |
| holdout:R6-compliance | ✅ | candidate compliance flags: 0 |
| holdout:R8-coverage | ✅ | 350 paired runs, 0 base cases missing in cand |
| holdout:R5-not-lower | ✅ | holdout e2e 1.0 → 1.0, shippable 1.0 → 1.0, rubric 99.9 → 99.9 |
| R7-selftest | ✅ | self-test green |
| R10-non-vacuous | ✅ | 178 paired run(s) rendered a different hook |
| golden:R11-diversity | ✅ | hook distinct ratio 0.4455 → 0.4758, distinct-2 0.1648 → 0.1641 |
| holdout:R11-diversity | ✅ | hook distinct ratio 0.4857 → 0.5086, distinct-2 0.1583 → 0.1667 |

## Headline

- golden: e2e 1.0→1.0 (flips +0/−0, p=1) · shippable 1.0→1.0 · rubric 99.9→99.9 Δ +0.00 [+0.00, +0.00] · audit 100.0→100.0 · compliance 0 · hooks changed 95/330 · distinct 0.4455→0.4758 · distinct-2 0.1648→0.1641
- holdout: e2e 1.0→1.0 (flips +0/−0, p=1) · shippable 1.0→1.0 · rubric 99.9→99.9 Δ +0.00 [+0.00, +0.00] · audit 100.0→100.0 · compliance 0 · hooks changed 83/350 · distinct 0.4857→0.5086 · distinct-2 0.1583→0.1667

## Diversity (the expected win)

- golden: hook distinct ratio 0.4455 → 0.4758 (+0.0303) · distinct-2 0.1648 → 0.1641 (-0.0007) · per-cell seed diversity None → None
- holdout: hook distinct ratio 0.4857 → 0.5086 (+0.0229) · distinct-2 0.1583 → 0.1667 (+0.0084) · per-cell seed diversity None → None

## Scorecard compare reports

- golden: `learned/promote/2026-09-29-evolve-01/golden-compare.md`
- holdout: `learned/promote/2026-09-29-evolve-01/holdout-compare.md`
