# WS-LEARN notes — variants + priors v2 (ws/learn)

**Commits:** 3ab38ab migration · fd5c985 variant linking · 4a55453 priors v2 · e24e780 `variants` · 4aa7a37 report + status · 908b2b3 unknown-letter warning · e0b6b76 README · 2c3e7f0 inconclusive action · 8d86f9b + this commit: notes.

**CLI**
- `link --variant B`.
- `link --auto` reads `#vsp-<sha8><letter>` tags. Untagged captions match by fingerprint:
  - the first line, normalised;
  - an exact match or Jaccard ≥ 0.8;
  - only runs created before the post and at most 60 days earlier;
  - the best match is picked deterministically.
- `variants [--slug S | --sha SHA8] [--json]` writes `learned/VARIANTS.md`.
- `status` adds `variant_linked` and `variants_md`.

**Schema**
- `posts` gains `variant_id`, `hook_archetype`, `visual_type`, `vibe`, `tone` and `primary_keyword` (additive `OPTIONAL_COLUMNS`; the ingest schema stays at 1).
- `priors.json` v2 = v1 + `sections` {archetype, visual_type, vibe, tone} × {by_niche, global}.
- **Deviation:** until some post has v2.1 data, `learn` writes exact v1. The ingest selfcheck, which I can't edit, pins the v1 key list.

**VARIANTS.md excerpt (fixtures)**
```
## electric-milk-frother — `vsp-76ef25df` — WINNER FOUND: B
| **B** | proof-first | result-reveal | Trial Reel | 1,800 | 1,296 | 72.0% | … | 100.0% | 0.00 pts |
- Action: Graduate the winning Trial Reel B (…/FIXTUREv21FB/) … then run B as the main cut
- Drop C: P(hold < 50%) = 94%
## sunset-lamp — INCONCLUSIVE (futility: leader B 58.9% < 80% at 168 h)
```

**Selfchecks (all pass on 3.9 and 3.12)**
- `pipeline.py --self-test` passes.
- `vsp.ingest`: 79/79.
- `vsp.feedback`: 29/29, plus 40/40 new v2.1 checks. These cover:
  - fingerprint links to A, B and C, including the time-window and Jaccard 0.8-vs-0.73 edges;
  - the migration on a legacy DB;
  - the priors v2 round-trip via `vsp.priors.mean_for`;
  - a winner, an inconclusive test and a keep-testing test (Monte Carlo checked against integration);
  - the report sections;
  - determinism across re-runs and `PYTHONHASHSEED`.

**Limits**
- Variant posts keep the script's `hook_family`.
- The variant prior is Beta(1,1), as the brief asks. VARIANT_POLICY suggests a strength-20 prior at the account median.
