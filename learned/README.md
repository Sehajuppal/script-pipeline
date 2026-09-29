# learned/ — state of the self-improving loop

Everything here is produced by the pipeline's own learning loop and is
reviewed like code (it changes what the maker generates).

| file | written by | read by | contract |
|---|---|---|---|
| `priors.json` | `python3 -m vsp.feedback learn` | the maker (hook-family choice) | performance posteriors per (niche, hook family) from YOUR posted reels |
| `hook_packs/*.json` | `python3 -m vsp.improve evolve` | the maker, only `"status": "approved"` packs | evolved hook templates + the evidence that approved them |
| `LEDGER.md` | `python3 -m vsp.improve` | humans + agents | every accepted / rejected change with its scorecard evidence |
| `DIAGNOSIS.md`, `TASKS.md`, `tasks.json` | `python3 -m vsp.improve diagnose` | the operating agent, `delegate` | ranked improvement opportunities and concrete tasks |
| `CYCLE.md` | `python3 -m vsp.improve cycle` | humans + agents | the latest cycle's summary + top tasks |
| `evals/latest.json`, `evals/history.jsonl` | `python3 -m vsp.improve measure` | `diagnose`, trends | headline scorecard metrics (raw JSON in `evals/results/`, git-ignored) |
| `promote/<pack-id>/`, `verify/<run>/` | `promote`, `verify` | reviewers | evidence.json / evidence.md + scorecard compare reports (raw in `*/results/`, git-ignored) |
| `PERFORMANCE.md` | `python3 -m vsp.feedback report` | humans + agents | what is working for this account |

Engine docs: `docs/ws-improve-notes.md`. Only `approved` packs load; `promote` is the
only path from `proposed` to `approved`.

`priors.json` schema (v1):

```json
{"schema_version": 1, "updated_at": "2026-09-28T00:00:00+00:00",
 "metric": "hook_rate",
 "families": {"<maker niche>": {"<hook family>": {"alpha": 3.0, "beta": 2.0, "n": 4}}},
 "global": {"<hook family>": {"alpha": 3.0, "beta": 2.0, "n": 4}}}
```

Hook pack schema (v1):

```json
{"schema_version": 1, "id": "2026-09-28-evolve-01", "status": "proposed|approved|rejected",
 "families": {"<hook family>": ["<template using only known slots>"]},
 "provenance": {"created": "...", "source": "evolve|mined|llm", "evidence": {}}}
```
