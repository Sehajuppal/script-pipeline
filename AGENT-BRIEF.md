# AGENT BRIEF — for the other agent improving this repo

> **Superseded by `AGENTS.md` (pipeline v2, 2026-09-29).** Kept for history.
> Status of the open items below: §45 numbering fixed (§45b/§49b/§50b/§51b);
> D103 vs D62/D83 resolved by D142 compressed payoff cards (≤12 tokens,
> ≤20 cps); the input-side prompt→fit classifier is built (`vsp/router.py`,
> D147); §65 remains pending loop verification.

This is the **viral script pipeline**: a research-grounded generator that turns a
product prompt into a shoot-ready viral short-form script plus a production
bundle (script JSON + shot list + a render brief for a downstream video agent).

## Layout
- `viral_script_maker.py` — the generator. `pipeline.py` — the orchestrator you
  must run. `make_shotlist.py` — beats → shots + render brief.
- `RULES.md` — the rulebook: ~135 dated, verified findings (D1–D135) that the
  gates enforce. Read the sections relevant to whatever you touch.
- `research_bridge.py` / `research_pack.json` — daily-refreshed research pack
  (hook rankings per niche, fresh examples). Rebuild with
  `python3 research_bridge.py --refresh`.
- `personas.json` — locked persona entries (e.g. "Maya"). Never edit a shipped
  entry in place; add new ones.
- `outputs/<slug>/` — past production bundles: `script.json`, `bundle.md`,
  `brief.md`, `validation-report.md`. Reference, don't edit.

## The pipeline (everything goes through it)
```
python3 pipeline.py "<product>" [--presenter ai|human] [--format demo|talking-head|pov-vlog|transformation|review] [--duration 30] [--seed N]
```
Stages: maker → GATE 1 (script checks) → shot-list → GATE 2 (brief checks).
Gates **fail loudly** (exit 1 + validation-report.md). Never ship a bundle a
gate rejected, and never weaken a gate to make a script pass — fix the maker.

## Non-negotiables while improving
1. `python3 pipeline.py --self-test` must stay green (gate cases + no-clobber).
2. New rules get dated D-numbers in RULES.md and real gate/maker code, not
   comments-only. A "patched" claim = rule greppable in code + seed re-run +
   regression seeds passing (see §64-era notes).
3. Rules are verified against real seed runs (document the seed + before/after).
4. The DELIVERABLE block in `make_shotlist.py` must stay verbatim — a
   downstream agent parses it.
5. No prices in scripts unless the prompt supplied them (D37).

## Known open items (as of 2026-09-28)
- RULES.md §65 (attention-engineering doctrine) is PENDING loop verification.
- §45 section numbering is duplicated; needs cleanup.
- D103 vs D62/D83: the 12-word on-screen cap rejects the 28-word TEST/VERDICT
  card the payoff contract mandates — unresolved, belongs to the judge loop.
- Prompt→fit classifier: only the output side exists; the input-side half
  (niche/fit) was never built.
