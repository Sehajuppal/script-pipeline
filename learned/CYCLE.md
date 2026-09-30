# CYCLE — latest self-improvement cycle

`python3 -m vsp.improve cycle --budget small` · 2026-09-29T05:40:33+00:00 → 2026-09-29T05:41:47+00:00 · git `b867500` on `ws/improve`

- health: self-test green · research pack age 16.01 h (stale False) · hook packs {} · maker loader absent (A/B shim only)
- measure golden: 330 runs · e2e 1.0 · shippable 1.0 · rubric 99.9 (audit 100.0) · compliance 0 · hooks distinct 0.4455 · distinct-2 0.1648
- measure holdout: 350 runs · e2e 1.0 · shippable 1.0 · rubric 99.9 (audit 100.0) · compliance 0 · hooks distinct 0.4857 · distinct-2 0.1583
- measure capability: 220 runs · e2e 1.0 · shippable 1.0 · rubric 100.0 (audit 100.0) · compliance 0 · hooks distinct 0.5818 · distinct-2 0.1745
- diagnose: 15 opportunities, 15 tasks
- evolve: proposed (offline preview: more distinct hooks, no gate/rubric loss) · 8 templates · 2026-09-29-evolve-01 · preview distinct 0.28 → 0.33 · llm off · holdout opened: never
- promote 2026-09-29-evolve-01: ACCEPT → approved
  - golden hook distinct 0.4455 → 0.4758 · distinct-2 0.1648 → 0.1641
  - holdout hook distinct 0.4857 → 0.5086 · distinct-2 0.1583 → 0.1667
- task 1: T-HOOK-DIVERSITY (16.6) Grow the hook template pool where it is thinnest
- task 2: T-DRIFT-FAMILIES (13.9) Follow the live hook-family ranking (D148)
- task 3: T-RUBRIC-R14 (3.7) Raise R14: caption echoes the comment keyword
- took 73.4 s

## Evolved pack

| fitness | gain | quality | novelty | family | template | operator |
|---|---|---|---|---|---|---|
| 0.11063 | 0.11645 | 1.0 | 0.875 | bold-claim | `Day {ndays} with the {category}. Zero failures.` | slot_swap |
| 0.10537 | 0.10537 | 1.0 | 1.0 | curiosity-gap | `The {category}. Worth it?` | slot_swap |
| 0.05878 | 0.06451 | 1.0 | 0.7778 | curiosity-gap | `I lived with the {category} for {ndays} days.` | slot_swap |
| 0.05277 | 0.05863 | 1.0 | 0.75 | transformation | `{product}. Here's the after.` | tail_swap |
| 0.10537 | 0.10537 | 1.0 | 1.0 | curiosity-gap | `{product}: the honest verdict.` | tail_swap |
| 0.04018 | 0.04537 | 1.0 | 0.7143 | transformation | `{product} after {ndays} days. Worth it?` | tail_swap |
| 0.0539 | 0.05863 | 0.975 | 0.8571 | bold-claim | `Most {category_pl} fail. Not this one.` | tail_swap |
| 0.04925 | 0.05863 | 1.0 | 0.6 | transformation | `This is the after with {product}.` | opener_swap |

## Top tasks

- `T-HOOK-DIVERSITY` (16.6): Grow the hook template pool where it is thinnest — acceptance `python3 -m vsp.improve verify --base b867500 --cand HEAD`; engine: `python3 -m vsp.improve evolve --budget full && python3 -m vsp.improve promote <new pack>`
- `T-DRIFT-FAMILIES` (13.9): Follow the live hook-family ranking (D148) — acceptance `python3 -m vsp.improve verify --base b867500 --cand HEAD`
- `T-RUBRIC-R14` (3.7): Raise R14: caption echoes the comment keyword — acceptance `python3 -m vsp.improve verify --base b867500 --cand HEAD`
