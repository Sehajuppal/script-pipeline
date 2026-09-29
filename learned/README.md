# learned/ — state of the self-improving loop

Everything here is produced by the pipeline's own learning loop and is
reviewed like code (it changes what the maker generates).

| file | written by | read by | contract |
|---|---|---|---|
| `priors.json` | `python3 -m vsp.feedback learn` | the maker (hook-family choice; v2 sections via `vsp.priors.mean_for`) | performance posteriors per (niche, hook family) — and, schema v2, per hook archetype / frame-0 visual type / vibe / tone — from YOUR posted reels |
| `hook_packs/*.json` | `python3 -m vsp.improve evolve` | the maker, only `"status": "approved"` packs | evolved hook templates + the evidence that approved them |
| `LEDGER.md` | `python3 -m vsp.improve` | humans + agents | every accepted / rejected change with its scorecard evidence |
| `DIAGNOSIS.md`, `TASKS.md`, `tasks.json` | `python3 -m vsp.improve diagnose` | the operating agent, `delegate` | ranked improvement opportunities and concrete tasks |
| `CYCLE.md` | `python3 -m vsp.improve cycle` | humans + agents | the latest cycle's summary + top tasks |
| `evals/latest.json`, `evals/history.jsonl` | `python3 -m vsp.improve measure` | `diagnose`, trends | headline scorecard metrics (raw JSON in `evals/results/`, git-ignored) |
| `promote/<pack-id>/`, `verify/<run>/` | `promote`, `verify` | reviewers | evidence.json / evidence.md + scorecard compare reports (raw in `*/results/`, git-ignored) |
| `PERFORMANCE.md` | `python3 -m vsp.feedback report` | humans + agents | what is working for this account (hook families + archetype / visual type / vibe / tone tables) |
| `VARIANTS.md` | `python3 -m vsp.feedback variants` | humans + agents | Bayesian A/B of alternate openings posted as variants (Trial Reels): winner found / keep testing / inconclusive + the action |

Engine docs: `docs/ws-improve-notes.md`, feedback: `docs/ws-data-notes.md`,
`docs/ws-learn-notes.md`. Only `approved` packs load; `promote` is the only path
from `proposed` to `approved`.

`priors.json` schema (v1):

```json
{"schema_version": 1, "updated_at": "2026-09-28T00:00:00+00:00",
 "metric": "hook_rate",
 "families": {"<maker niche>": {"<hook family>": {"alpha": 3.0, "beta": 2.0, "n": 4}}},
 "global": {"<hook family>": {"alpha": 3.0, "beta": 2.0, "n": 4}}}
```

`priors.json` schema v2 (pipeline v2.1) = v1, with `families` / `global` unchanged,
plus `sections`. `learn` writes v2 as soon as one linked, labelled post carries a
v2.1 key; until then it writes exactly v1, so v1-only readers keep working.

```json
{"schema_version": 2, "updated_at": "…", "metric": "composite",
 "families": {…}, "global": {…},
 "sections": {
  "archetype":   {"by_niche": {"<maker niche>": {"<HOOK_ARCHETYPES id>": {"alpha": 3.0, "beta": 2.0, "n": 3}}},
                  "global": {"<HOOK_ARCHETYPES id>": {"alpha": 3.0, "beta": 2.0, "n": 3}}},
  "visual_type": {"by_niche": {…}, "global": {…}},
  "vibe":        {"by_niche": {…}, "global": {…}},
  "tone":        {"by_niche": {…}, "global": {…}}}}
```

- All four sections are always present in v2 (possibly empty). Keys are
  `vsp/creative_vocab.py` ids: the posted variant's `archetype` and `visual_type`
  (`hook_variants[*]`), the script's `direction.vibe` and `direction.tone.voice`.
- Same label and prior as the families: success = composite ≥ the account median;
  `alpha = 1 + wins`, `beta = 1 + losses`, `n = posts` (so `alpha + beta − 2 = n`).
  Only linked posts in a maker niche whose key is known count; `global` pools the niches.
- Read with `vsp.priors.posterior_for(priors, section, niche, key)` / `mean_for(…)`:
  the niche table first, then `global`; `mean_for` is `None` below n = 3. Consumers use it
  only as a tie-break after quality (docs/CREATIVE-PLAN.md §1.5).

Linking a post to its script and variant (`python3 -m vsp.feedback link --auto`):

- Tag: `#vsp-<first 8 hex of script_sha256>` anywhere in the caption; an alternate
  opening adds its variant letter, `#vsp-<sha8>B`. Without a letter the variant comes
  from the caption fingerprint within that script, else the primary (A).
- Caption fingerprint (untagged posts): the caption's first line with words left after
  NFKC, lowercasing and stripping hashtags, @mentions, URLs, emoji and punctuation
  (apostrophes vanish, spaces collapse). It is matched against each candidate script's
  caption first line and Instagram discovery caption first line (= variant A) and every
  `hook_variants[*].caption_line`. Candidates: `manifest.json` under `outputs/`,
  `VSP_FEEDBACK_SEARCH` and `--search`, with `script.json` next to it and a manifest
  `created` (else its mtime) before the post and at most 60 days earlier. Accepted:
  an exact match or token Jaccard ≥ 0.8. The best wins deterministically: exact, then
  higher Jaccard, then the newest run, then script sha, variant order, path.
- By hand: `link --media-id ID --manifest PATH [--trial] [--variant B]`.
- The posts row stores `variant_id`, that variant's `hook_archetype` + `visual_type`,
  `vibe`, `tone`, `primary_keyword` (NULL for scripts made before v2.1).

Hook pack schema (v1):

```json
{"schema_version": 1, "id": "2026-09-28-evolve-01", "status": "proposed|approved|rejected",
 "families": {"<hook family>": ["<template using only known slots>"]},
 "provenance": {"created": "...", "source": "evolve|mined|llm", "evidence": {}}}
```
