# LEDGER — the self-improvement loop's decisions

Append-only (newest last). Written by `python3 -m vsp.improve` — `verify`,
`promote` and `cycle`. Every entry names its verdict, the ACCEPT rules it was
judged by, and where the evidence lives. Automation never edits gate or rule
code to pass, never pushes to main and never merges its own PRs.

## 2026-09-29 05:41:47Z · promote · 2026-09-29-evolve-01 · ACCEPT

- pack `learned/hook_packs/2026-09-29-01.json` → **approved** (8 templates, budget small, seeds 1, loader emulate)
- golden: e2e 1.0→1.0 (flips +0/−0, p=1) · shippable 1.0→1.0 · rubric 99.9→99.9 Δ +0.00 [+0.00, +0.00] · audit 100.0→100.0 · compliance 0 · hooks changed 95/330 · distinct 0.4455→0.4758 · distinct-2 0.1648→0.1641
- holdout: e2e 1.0→1.0 (flips +0/−0, p=1) · shippable 1.0→1.0 · rubric 99.9→99.9 Δ +0.00 [+0.00, +0.00] · audit 100.0→100.0 · compliance 0 · hooks changed 83/350 · distinct 0.4857→0.5086 · distinct-2 0.1583→0.1667
- golden: hook distinct ratio 0.4455 → 0.4758 (+0.0303) · distinct-2 0.1648 → 0.1641 (-0.0007) · per-cell seed diversity None → None
- holdout: hook distinct ratio 0.4857 → 0.5086 (+0.0229) · distinct-2 0.1583 → 0.1667 (+0.0084) · per-cell seed diversity None → None
- self-test green (3.9.25 rc 0, 3.12.14 rc 0)
- all ACCEPT rules hold (R1–R8, R10 non-vacuous, R11 diversity)
- evidence: `learned/promote/2026-09-29-evolve-01/evidence.json`, `learned/promote/2026-09-29-evolve-01/evidence.md`

## 2026-09-29 05:41:47Z · cycle · budget small · ACCEPT

- health: self-test green · research pack age 16.01 h (stale False) · hook packs {} · maker loader absent (A/B shim only)
- measure golden: 330 runs · e2e 1.0 · shippable 1.0 · rubric 99.9 (audit 100.0) · compliance 0 · hooks distinct 0.4455 · distinct-2 0.1648
- measure holdout: 350 runs · e2e 1.0 · shippable 1.0 · rubric 99.9 (audit 100.0) · compliance 0 · hooks distinct 0.4857 · distinct-2 0.1583
- measure capability: 220 runs · e2e 1.0 · shippable 1.0 · rubric 100.0 (audit 100.0) · compliance 0 · hooks distinct 0.5818 · distinct-2 0.1745
- diagnose: 15 opportunities, 15 tasks
- evolve: proposed (offline preview: more distinct hooks, no gate/rubric loss) · 8 templates · 2026-09-29-evolve-01 · preview distinct 0.28 → 0.33 · llm off · holdout opened: never
- promote 2026-09-29-evolve-01: ACCEPT → approved
  golden hook distinct 0.4455 → 0.4758 · distinct-2 0.1648 → 0.1641
  holdout hook distinct 0.4857 → 0.5086 · distinct-2 0.1583 → 0.1667
- task 1: T-HOOK-DIVERSITY (16.6) Grow the hook template pool where it is thinnest
- task 2: T-DRIFT-FAMILIES (13.9) Follow the live hook-family ranking (D148)
- task 3: T-RUBRIC-R14 (3.7) Raise R14: caption echoes the comment keyword
- took 73.4 s
- evidence: `learned/CYCLE.md`, `learned/DIAGNOSIS.md`, `learned/TASKS.md`

## 2026-09-29 18:51:16Z · verify · 8d7f87d (8d7f87d5394b) → HEAD (cefcf7c19f1d) · ACCEPT

- budget small (seeds 1), yardstick = base tree
- golden: e2e 1.0→1.0 (flips +0/−0, p=1) · shippable 1.0→1.0 · rubric 93.2→98.9 Δ +5.71 [+4.82, +6.60] · audit 95.1→95.8 · compliance 0 · hooks changed 168/330 · distinct 0.5909→0.6333 · distinct-2 0.1941→0.2102
- holdout: e2e 1.0→1.0 (flips +0/−0, p=1) · shippable 1.0→1.0 · rubric 92.8→97.9 Δ +5.15 [+4.40, +5.92] · audit 93.3→94.1 · compliance 0 · hooks changed 187/350 · distinct 0.5543→0.58 · distinct-2 0.187→0.1948
- golden: hook distinct ratio 0.5909 → 0.6333 (+0.0424) · distinct-2 0.1941 → 0.2102 (+0.0161) · per-cell seed diversity None → None
- holdout: hook distinct ratio 0.5543 → 0.58 (+0.0257) · distinct-2 0.187 → 0.1948 (+0.0078) · per-cell seed diversity None → None
- self-test green (3.9.25 rc 0, 3.12.14 rc 0)
- weakening guard: 0 finding(s); guarded files changed: none; yardstick changed: none
- evidence: `learned/verify/20260929T184339Z-8d7f87d5394b-cefcf7c19f1d/evidence.json`, `learned/verify/20260929T184339Z-8d7f87d5394b-cefcf7c19f1d/evidence.md`

## 2026-09-29 22:28:43Z · verify · 4170090 (41700907e328) → HEAD (e5c9851543b4) · REJECT

- budget small (seeds 1), yardstick = base tree
- golden: e2e 1.0→1.0 (flips +0/−0, p=1) · shippable 1.0→1.0 · rubric 98.9→98.9 Δ +0.00 [+0.00, +0.00] · audit 95.8→95.8 · compliance 0 · hooks changed 0/330 · distinct 0.6333→0.6333 · distinct-2 0.2102→0.2102
- holdout: e2e 1.0→1.0 (flips +0/−0, p=1) · shippable 1.0→1.0 · rubric 97.9→97.9 Δ +0.00 [+0.00, +0.00] · audit 94.1→94.1 · compliance 0 · hooks changed 0/350 · distinct 0.58→0.58 · distinct-2 0.1948→0.1948
- golden: hook distinct ratio 0.6333 → 0.6333 (+0.0000) · distinct-2 0.2102 → 0.2102 (+0.0000) · per-cell seed diversity None → None
- holdout: hook distinct ratio 0.58 → 0.58 (+0.0000) · distinct-2 0.1948 → 0.1948 (+0.0000) · per-cell seed diversity None → None
- self-test green (3.9.25 rc 0, 3.12.14 rc 0)
- weakening guard: 1 finding(s); guarded files changed: none; yardstick changed: evals/scorecard.py
- failed: R9-guard: 1 weakening finding(s): yardstick changed: evals/scorecard.py (automation never edits the yardstick)
- evidence: `learned/verify/20260929T222042Z-41700907e328-e5c9851543b4/evidence.json`, `learned/verify/20260929T222042Z-41700907e328-e5c9851543b4/evidence.md`

