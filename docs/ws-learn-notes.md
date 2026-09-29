# WS-LEARN notes — variants + priors v2 (branch ws/learn)

**Commits:** 3ab38ab migration · fd5c985 variant linking · 4a55453 priors v2 · e24e780 `variants` · 4aa7a37 report sections + status · 908b2b3 unknown-letter warning · e0b6b76 learned/README · 2c3e7f0 inconclusive action · this notes commit.

**CLI additions**
- `link --variant B`.
- `link --auto` also reads `#vsp-<sha8><letter>` tags. For untagged captions it uses the fingerprint: the first line normalised, matched exactly or at Jaccard ≥ 0.8, against runs created before the post and at most 60 days earlier. The best match is picked deterministically.
- `variants [--slug S | --sha SHA8] [--json]` writes `learned/VARIANTS.md`.
- `status` gains `variant_linked` and `variants_md`.

**Schema changes**
- `posts` gains `variant_id`, `hook_archetype`, `visual_type`, `vibe`, `tone` and `primary_keyword`. The migration is additive (`OPTIONAL_COLUMNS`); the ingest schema stays at 1.
- `priors.json` v2 = v1 plus `sections` {archetype, visual_type, vibe, tone} × {by_niche, global}.
- **Deviation from the brief:** while no post carries a v2.1 key, `learn` writes the file exactly as v1. The ingest selfcheck, which I may not edit, pins the v1 key list.

**VARIANTS.md (selfcheck fixtures)**
```
## electric-milk-frother — `vsp-76ef25df` — WINNER FOUND: B
| **B** | proof-first | result-reveal | Trial Reel | 1,800 | 1,296 | 72.0% | 70.2%–73.7% | 100.0% | 0.00 pts |
- **Action:** Graduate the winning Trial Reel B (…/FIXTUREv21FB/) … Then run B as the main cut …
- Drop C: P(hold < 50%) = 94% — a failing hook
## sunset-lamp — `vsp-c486ac95` — INCONCLUSIVE   (futility: leader B 58.9% < 80% at 168 h)
```

**Selfchecks** (all pass on python3.9 and python3.12)
- `pipeline.py --self-test` passes.
- `vsp.feedback`: 29 passed, plus 40 new v2.1 checks passed.
- `vsp.ingest`: 79 passed.
- The v2.1 checks cover:
  - fingerprint links to variants A, B and C, including the time-window and Jaccard 0.8 vs 0.73 edges;
  - the migration on a legacy DB;
  - the priors v2 round-trip through `vsp.priors`;
  - a clear winner, an inconclusive test and a keep-testing test, with the Monte Carlo result checked against numerical integration;
  - the report sections;
  - determinism across runs and under `PYTHONHASHSEED`.

**Limits**
- A variant post keeps the script's `hook_family`.
- The variant prior is Beta(1, 1), as the brief asks. VARIANT_POLICY suggests a strength-20 prior centred on the account median.
