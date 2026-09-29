# Viral Script Pipeline (v2.1)

A research-grounded, self-improving generator of shoot-ready short-form
video scripts (Reels / TikTok / Shorts). One command turns a product prompt
into a script, shot list, render brief, captions and a manifest. v2.1 adds
a creative layer on every script: the vibe, tone, pacing and music direction;
a typed shot plan (58 shot types, with real-footage flags for AI presenters);
3–5 A/B alternate openings; and search/posting packaging for TikTok,
Instagram and YouTube Shorts. The pipeline measures itself, learns from the
reels you post (including which opening won), and improves its own hook
templates under statistical guardrails. Built to be run by an agent
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
| 4 | gate 1 | 28 script rules (timing, claims, AI disclosure, hooks, hashtags; v2.1: variants D154, discovery D155, direction D156, no fake urgency D158) |
| 5 | select | best rubric score among candidates that pass every gate |
| 6 | repair | deterministic rule-keyed repairs, only if nothing passed |
| 7 | shot list | shots, identity-locked render brief, DELIVERABLE block |
| 8 | gate 2 | 18 brief rules (v2.1: typed shot plan D157, music lane D159, AI render-prompt hygiene D160) |
| 9 | export | captions (SRT/VTT/Remotion JSON), shotlist.csv, schema check; `direction.md`, `hooks.md`, `posting.md` |
| 10 | manifest | manifest.json (hashes, seeds, scores), trace.jsonl, gate-report.json; `--replay` reproduces a run |

Output lands in `outputs/<slug>/` (or `--out-dir`). Exit code is non-zero
when any gate fails.

What a run gives you (v2.1):

| file | for | what's in it |
|---|---|---|
| `brief.md` | the video agent | shot list with a `- Shot type:` per shot, identity-locked prompts, DELIVERABLE block |
| `bundle.md` | the creator | script, shot list, CREATIVE DIRECTION, ALTERNATE OPENINGS, SHOOT PLAN (setups, props, B-roll), POSTING & DISCOVERY, caption |
| `direction.md` | the creator / editor | vibe + reason, tone, pacing (wpm, average shot, cuts per 10 s, static-shot cap), energy curve, music (never in the master; licensed library per platform), look, camera, text style |
| `hooks.md` | the A/B test | 3–5 openings (A = the master's own; each alternate has its own archetype, frame-0 visual, card and first words), scores, test protocol, Bayesian stop rule |
| `posting.md` | posting | primary keyword (spoken + on screen by 3 s), per-platform caption, ≤5 / ≤5 / ≤15 hashtags, YouTube title, cover frame + text, AI-content toggles, posting checklist |
| `script.json`, `shots.json`, `shotlist.csv`, `captions.*` | tools | machine-readable script, typed shots, captions |
| `manifest.json` | the learning loop | hashes, seeds, scores; `script_summary` links a posted reel to its vibe, opening and keyword |

## Results (`docs/SCORECARD-v2.1.md`, v2.0 detail in `docs/SCORECARD.md`)

The v2.1 harness (rubric R01–R28) ran the same 990 runs for each version (33 prompts × 5 formats × 2 presenters × 3 seeds). The last column is 35 unseen holdout prompts:

| | before (d8f8759) | v2.0 | v2.1 | v2.1 holdout |
|---|---|---|---|---|
| end-to-end pass | 0.0% | 100.0% | 100.0% | 100.0% |
| crashes | 9.7% | 0.0% | 0.0% | 0.0% |
| rubric mean (R01–R28) | 56.2 | 77.6 | 98.7 | 97.7 |
| generic fallback hooks | 58.4% | 0.0% | 0.0% | 0.0% |
| hook diversity (distinct-2) | 0.023 | 0.078 | 0.094 | 0.087 |
| hook strength (independent scorer) | 45.3 | 62.9 | 75.5 | 72.7 |
| openings per script (A + alternates) | 0 | 0 | 4.7 | 4.6 |
| search keyword by 3 s + caption + tag | 0% | 0% | 93.2% | 76.8% |
| typed, D157-clean shot plan | 0% | 0% | 100% | 100% |
| compliance flags (AI lived-experience claims etc.) | 162 | 0 | 0 | 0 |

## The learning loop

- `python3 -m vsp.ingest …` — latest top reels per niche via the official
  Instagram Graph API (hashtag search + Business Discovery) into the research
  DB; `refresh-pack` rebuilds `research_pack.json`.
- `python3 -m vsp.feedback …` — links your posted reels to the runs that made
  them, pulls insights (skip rate, watch time, shares, saves) and learns
  `learned/priors.json`, which steers hook choice. Each alternate opening can
  be posted as a Trial Reel: tag it `#vsp-<sha8><letter>`, or rely on
  caption-fingerprint matching. `variants` then runs the Bayesian A/B
  (`learned/VARIANTS.md`). Priors v2 also learn per archetype, frame-0
  visual type, vibe and tone once there is data.
- `python3 -m vsp.improve cycle` — measure → diagnose → evolve hook templates
  → full A/B on golden + holdout → approve or reject → `learned/LEDGER.md`.
  `verify` accepts code changes only with a green self-test and no
  statistically significant regression; it rejects any gate weakening.

## Map

- `pipeline.py`, `viral_script_maker.py`, `make_shotlist.py`, `research_bridge.py` — entry points
- `vsp/` — support package (v2.1 creative layer: `direction.py`, `hooks.py`, `shotplan.py`, `discovery.py`, `creative.py`, data in `vsp/data/`) · `RULES.md` — rulebook D1–D161 · `schema/` — script JSON Schema
- `evals/` — golden, holdout, capability sets + scorecard harness · `learned/` — loop state
- `docs/` — design (`UPGRADE-PLAN.md`), research (`docs/research/`), per-workstream notes, rule coverage
- `.agents/skills/`, `AGENTS.md`, `agent/` — agent packaging (Hermes / Muse Code)
