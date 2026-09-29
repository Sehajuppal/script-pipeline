# Pipeline v2 — upgrade plan (2026-09-28)

Evidence: `evals/results/baseline.json` (990 runs of d8f8759) and the three
research reports in `docs/research/` (lab techniques, short-form virality
evidence, OSS pipeline survey — all with inline sources).

## 1. Baseline (what we are fixing)

| metric (990 runs) | baseline |
|---|---|
| crash | 9.7% — `$12.99` (int(price)), literal `{braces}`, review × challenge/showcase (KeyError) |
| gate 1 pass | 1.5% |
| end-to-end pass | **0.0%** |
| rubric mean | 70.9 / 100 |
| fallback hook ("Nobody mentions the X flaw.") | 58.4% of scripts |
| AI persona lived-experience claims ("I woke up…") | 162 scripts |
| top gate failures | D103 660 · D43 609 · D74 549 · D78 252 · D94 243 |

Root causes: beat windows are fixed fractions of the duration, never sized to
the words in them (D43/D55/D74/D78/D94); payoff cards run 24–34 words (D103);
multi-word products overflow every hook template (fallback); single candidate
per seed, no selection; the self-test and gate 2 need a private DB.

## 2. Target: a 10-stage pipeline

Every stage fails loudly (exit 1 + `validation-report.md`). Gate lines keep
their legacy text (`gate 1 (script): …`, `gate 2 (brief): …`).

| # | stage | module | output |
|---|---|---|---|
| 1 | ROUTE — input guardrails + 3-voter prompt router (concept/niche/fit, presenter & lane advice) | `vsp/router.py` | route record |
| 2 | RESEARCH — load + validate + hash-pin the research pack, staleness check | `vsp/research.py` | pack meta |
| 3 | GENERATE — N candidates from derived sub-seeds (candidate 0 = raw seed) | `viral_script_maker.generate`, `vsp/select.py` | candidates |
| 4 | GATE 1 — script gate on every candidate | `vsp/gates.py` + `vsp/rules.py` | findings |
| 5 | SELECT — rubric selection score, best gate-1 pass wins | `vsp/rubric.py`, `vsp/select.py` | winner |
| 6 | REPAIR — rule-keyed deterministic repairs, ≤3 rounds, only if nothing passed | `vsp/repair.py` | repaired script |
| 7 | SHOT LIST — shots + brief | `make_shotlist.build_bundle` | bundle.md, brief.md |
| 8 | GATE 2 — brief gate | `vsp/gates.py` | findings |
| 9 | EXPORT — captions (SRT/VTT/Remotion JSON), shotlist.csv, JSON-Schema check | `vsp/captions.py`, `vsp/exporters.py`, `vsp/schema.py` | files |
| 10 | MANIFEST — manifest.json (hashes, seeds, scores), trace.jsonl, gate-report.json | `vsp/manifest.py`, `vsp/trace.py` | files |

New CLI (all optional, defaults keep old behaviour where it existed):
`--duration N` (documented in AGENT-BRIEF, never existed) · `--no-research` ·
`--out-dir DIR` · `--candidates N` (default 8) · `--replay manifest.json` ·
`--strict-route` · `--require-fresh-research` · `--llm-judge` (advisory only).

## 3. Package layout (stdlib only, Python ≥ 3.9)

```
pipeline.py            orchestrator (10 stages) — owner: integration
viral_script_maker.py  generator (generate() signature unchanged)
make_shotlist.py       shots + brief (CLI unchanged; build_shots/build_bundle API)
research_bridge.py     research pack builder (cron entry point unchanged)
vsp/config.py          paths + env (VSP_VIRAL_DB, VSP_RESEARCH_PACK, VSP_DOSSIER_DIR, VSP_FIXTURE_OK)
vsp/lexicon.py         shared claim/bait/testimonial/slop patterns (gates + rubric)
vsp/timing.py          content-sized beat layout (the D43/D74/D78/D94 root-cause fix)
vsp/seeding.py         derive_seed(root, *path) — sha256, never hash()
vsp/gates.py           gate1/gate2 (legacy checks verbatim + registry rules)
vsp/rules.py           declarative rule registry (id, stage, severity, source, check)
vsp/selftest.py        hermetic self-test runner; cases in vsp/selftest_cases.py
vsp/router.py          stage 1
vsp/research.py        stage 2
vsp/select.py          stages 3+5
vsp/repair.py          stage 6
vsp/captions.py        SRT/VTT/Remotion cues + lint
vsp/exporters.py       shotlist.csv etc.
vsp/schema.py          script JSON Schema (draft 2020-12) + subset validator
vsp/manifest.py        manifest + replay
vsp/trace.py           trace.jsonl (OTel GenAI evaluation-result shaped)
vsp/llm.py             optional LLM judge adapter (off by default, advisory)
vsp/rubric.py          quality rubric (R01–R20, P1–P3; audit-only R12/R15/R17/P2)
vsp/fixtures.py        hermetic fixture viral.db
evals/                 golden set + scorecard harness + results
tools/rule_coverage.py RULES.md ↔ code coverage report
```

## 4. Shared interfaces (contracts between workstreams)

- `viral_script_maker.generate(prompt, presenter="ai", fmt="demo", duration=30,
  seed=None, use_research=True, persona=None) -> dict`. Additive keys only:
  `series_plan` (D146), `hook_source` (D145).
- `vsp.gates.gate1(script) -> list[str]` and `gate2(bundle_text, script) -> list[str]`
  (error messages, legacy order first). `vsp.gates.gate1_findings / gate2_findings`
  return structured findings `{rule, severity, message}` incl. warnings.
- `vsp.timing.layout(body_beats, duration, start=3.0) -> (beats, info)`.
- `make_shotlist.build_bundle(script) -> (bundle_text, shots, vo_lines)`.
- `vsp.rubric.score(script) -> {...}`; `selection_score` excludes audit checks.
- `vsp.select.run(gen_fn, n, seed, ...) -> {winner, candidates}`.

## 5. New rules (RULES.md §66, dated 2026-09-28)

| id | rule | enforced in |
|---|---|---|
| D136 | No unsourced social proof (★ ratings, order/review counts, "sold out", best-seller) unless the prompt supplies it | gate 1 + maker (`{proof}` slot) |
| D137 | AI persona never claims lived experience (I woke/slept/tried/used…, my skin/hair/body…, "changed my life") — FTC 16 CFR 465.2 | gate 1 + maker (AI lane rewrites) |
| D138 | AI disclosure carried: `disclosure` field + caption AI line (gate 1) + frame-0 "AI persona" label in the brief (gate 2) | gates |
| D139 | No generic engagement bait (like if, tag a friend, comment YES, share this with, double tap…); keyword→DM CTA is not bait | gate 1 |
| D140 | Hashtags: 1–5, not generic-only (#fyp #viral #ugc) | gate 1 + maker |
| D141 | No absolute/guarantee claims (guaranteed, cure, miracle, #1, cheapest, best…ever, 100% effective, risk-free, clinically proven) unless in the prompt | gate 1 |
| D142 | Payoff card compressed form (resolves D103 vs D62/D83, PROPOSED for judge-loop ratification): D83 elements in ≤12 tokens, ≤20 cps over its window | maker; gated by D103 + D142 cps |
| D143 | Timeline from content: windows sized to words at the gate's own rate (rehook words included), tiled from 3.0 s to duration, payoff in the D7 band, contract written from the actual PAYOFF start; over-budget lines trimmed at sentence boundaries or swapped for a fitting variant | maker (`vsp/timing.py`); gated by D43/D55/D74/D78/D94 |
| D144 | Frame-0 overlay is a contiguous ≤3-word phrase of the hook (or a label form) — no "NOBODY MENTIONS FLAW" fragments | gate 1 (+ D17) + maker |
| D145 | `hook_family`/`hook_source` report what actually rendered (fallback/pinned are named) | maker |
| D146 | A part-2 CTA must be backed by `series_plan` in the script | gate 1 + maker |
| D147 | Input router (stage 1): 3 voters; <2/3 agreement = route warning (`--strict-route` fails); F32/B15 presenter advice; TikTok-Shop × AI lane warning | pipeline |
| D148 | Research pack pinning: schema-valid, sha256 in manifest, >48 h = stale warning (`--require-fresh-research` fails) | pipeline |
| D149 | Best-of-N: N candidates (default 8), candidate 0 = raw seed; winner = best rubric selection score among gate-1 passes; audit checks never select | pipeline |
| D150 | Repair loop: deterministic rule-keyed repairs only, ≤3 rounds, all logged; still failing = loud failure | pipeline |
| D151 | FIXTURE reference reels are rejected by gate 2 unless VSP_FIXTURE_OK=1 | gate 2 |
| D152 | Export contract: captions + shotlist.csv + schema-valid script.json on every passing run | pipeline |
| D153 | Manifest + trace on every run; `--replay` must reproduce the script hash | pipeline |

Existing maker-only rules that become gate-enforced (no new number, per the
cycle-4 precedent): D17 (frame-0 ≤3 words), D31 (no raw `{slot}`), D73 (hook
≤8 words), D93 (no repeated re-hook).

## 6. Workstreams (parallel, isolated git worktrees)

| sub-orchestrator | branch | owns |
|---|---|---|
| SO-1 Generation | `ws/gen` | `viral_script_maker.py` (timing via vsp/timing, budget-aware banks, payoff cards, hooks + fallback, overlay, AI curator voice, proof slot, hashtags, series_plan, niche word-boundary routing, research-notes niche filter) |
| SO-2 Contract | `ws/contract` | `vsp/rules.py`, `vsp/gates.py`, `vsp/selftest_cases.py`, `vsp/router.py`, `vsp/research.py`, `research_bridge.py`, `RULES.md`, `tools/rule_coverage.py` |
| SO-3 Delivery | `ws/delivery` | `make_shotlist.py` (D47/D48 rotation, AI identity fallback, niche keys, meta-note stripping, dynamic fallbacks), `vsp/captions.py`, `vsp/exporters.py`, `vsp/schema.py`, `schema/`, `vsp/manifest.py`, `vsp/trace.py`, `vsp/select.py`, `vsp/repair.py`, `vsp/llm.py` |
| integration (orchestrator) | `kiro/pipeline-v2` | `pipeline.py`, `vsp/config.py`, `vsp/timing.py`, `vsp/lexicon.py`, `evals/`, docs |

## 7. Acceptance (the "5–10×" bar, measured by `evals/scorecard.py`)

- self-test green on Python 3.9 and 3.12; every legacy case still fails with
  its original message; every new gate rule has a failing case.
- 0% crashes; end-to-end pass ≥ 90% (baseline 0%); shippable (pass + rubric
  ≥ 75 + no compliance flag) ≥ 85% (baseline 0%).
- rubric mean ≥ 88 (baseline 70.9); audit-only mean not lower than baseline.
- fallback hooks ≤ 10% (baseline 58%); AI lived-experience flags = 0 (162).
- gates never weakened; DELIVERABLE verbatim; outputs/ and personas.json
  untouched.
