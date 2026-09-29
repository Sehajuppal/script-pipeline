# Viral Script Pipeline (v2)

A research-grounded, self-improving generator of shoot-ready short-form
video scripts (Reels / TikTok / Shorts). One command turns a product prompt
into a script, shot list, render brief, captions and a manifest; the
pipeline measures itself, learns from the reels you post, and improves its
own hook templates under statistical guardrails. Built to be run by an agent
(Hermes Agent on Meta Muse) — see `AGENTS.md` and `agent/README.md`.

## Quick start

```sh
python3 pipeline.py --self-test          # hermetic, no keys needed (Python 3.9+)

python3 pipeline.py 'a $12 LED sunrise alarm lamp' --presenter ai
python3 pipeline.py 'why your hooks fail' --format talking-head --duration 45
python3 pipeline.py 'silk pillowcase' --presenter human --json   # machine-readable summary
```

Quote prompts containing `$` in single quotes. Formats: `demo` ·
`talking-head` · `pov-vlog` · `transformation` · `review`. Presenters: `ai` ·
`human` (the router recommends one: `python3 -m vsp.router "<prompt>"`).

## The 10 stages

| # | stage | what it does |
|---|---|---|
| 1 | route | input guardrails + 3-voter concept/niche/fit router, presenter advice |
| 2 | research | load + hash-pin the research pack, staleness check |
| 3 | generate | 8 candidates from derived seeds (candidate 0 = your seed) |
| 4 | gate 1 | 24 script rules (timing, claims, AI disclosure, hooks, hashtags…) |
| 5 | select | best rubric score among candidates that pass every gate |
| 6 | repair | deterministic rule-keyed repairs, only if nothing passed |
| 7 | shot list | shots, identity-locked render brief, DELIVERABLE block |
| 8 | gate 2 | 15 brief rules |
| 9 | export | captions (SRT/VTT/Remotion JSON), shotlist.csv, schema check |
| 10 | manifest | manifest.json (hashes, seeds, scores), trace.jsonl, gate-report.json; `--replay` reproduces a run |

Output lands in `outputs/<slug>/` (or `--out-dir`). Exit code is non-zero
when any gate fails.

## Results (`docs/SCORECARD.md`)

Same 990 runs (33 prompts × 5 formats × 2 presenters × 3 seeds), same rubric:

| | before (d8f8759) | v2 |
|---|---|---|
| end-to-end pass | 0.0% | 100.0% (holdout of 35 unseen prompts: 100.0%) |
| crashes | 9.7% | 0.0% |
| rubric mean | 70.9 | 99.9 |
| generic fallback hooks | 58.4% | 0.0% |
| hook diversity (distinct-2) | 0.023 | 0.078 |
| compliance flags (AI lived-experience claims etc.) | 162 | 0 |

## The learning loop

- `python3 -m vsp.ingest …` — latest top reels per niche via the official
  Instagram Graph API (hashtag search + Business Discovery) into the research
  DB; `refresh-pack` rebuilds `research_pack.json`.
- `python3 -m vsp.feedback …` — links your posted reels to the runs that made
  them, pulls insights (skip rate, watch time, shares, saves) and learns
  `learned/priors.json`, which steers hook choice.
- `python3 -m vsp.improve cycle` — measure → diagnose → evolve hook templates
  → full A/B on golden + holdout → approve or reject → `learned/LEDGER.md`.
  `verify` accepts code changes only with a green self-test and no
  statistically significant regression; it rejects any gate weakening.

## Map

- `pipeline.py`, `viral_script_maker.py`, `make_shotlist.py`, `research_bridge.py` — entry points
- `vsp/` — support package · `RULES.md` — rulebook D1–D153 · `schema/` — script JSON Schema
- `evals/` — golden, holdout, capability sets + scorecard harness · `learned/` — loop state
- `docs/` — design (`UPGRADE-PLAN.md`), research (`docs/research/`), per-workstream notes, rule coverage
- `.agents/skills/`, `AGENTS.md`, `agent/` — agent packaging (Hermes / Muse Code)
