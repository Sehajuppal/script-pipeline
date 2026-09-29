# TASKS — agent-executable improvement tasks

Generated 2026-09-29T05:40:59+00:00 by `python3 -m vsp.improve diagnose` (ranked; machine-readable twin: `learned/tasks.json`; `python3 -m vsp.improve delegate <id>` hands one to Muse Code).

Rules for every task: work on a new branch/worktree (never main); never edit `vsp/gates.py`, `vsp/rules.py` or `vsp/lexicon.py` to make a check pass — fix the generator; never touch the yardstick (`evals/golden.jsonl`, `evals/holdout.jsonl`, `evals/scorecard.py`, `vsp/rubric.py`); a task is done only when its acceptance command prints ACCEPT; open a PR with the evidence and never merge it yourself.

## 1. `T-HOOK-DIVERSITY` — Grow the hook template pool where it is thinnest

- **score** 16.6 · kind `diversity` · first seen 2026-09-29
- **why**: pick_hook draws among the top-scored templates of the niche's family; families with 1-2 fitting templates ship the same hook for every seed.
- **evidence**: golden: hooks distinct 0.4455 · distinct-2 0.1648 · seed diversity None · fallback 0.0 · product families {'bold-claim': '18 distinct / 48 runs', 'curiosity-gap': '70 distinct / 118 runs', 'negative-command': '2 distinct / 3 runs', 'story-time': '3 distinct / 6 runs', 'transformation': '34 distinct / 75 runs'}
- **files likely involved**: `learned/hook_packs/ (via evolve + promote)`, `viral_script_maker.py (HOOKS)`
- **done when**: golden hook distinct ratio up with verify ACCEPT
- **engine can do it**: `python3 -m vsp.improve evolve --budget full && python3 -m vsp.improve promote <new pack>`
- **acceptance**: `python3 -m vsp.improve verify --base b867500 --cand HEAD`

## 2. `T-DRIFT-FAMILIES` — Follow the live hook-family ranking (D148)

- **score** 13.9 · kind `drift` · first seen 2026-09-29
- **why**: pick_hook should prefer vsp.research.live_hook_family(pack, niche, presenter) (whole ranked list, mapped research niches) over the static NICHE_HOOK map.
- **evidence**: fitness/ai: live curiosity-gap (fitness:day-counter, seen 10) vs used {'bold-claim': 15} (mismatch 100%, n=15)
- **evidence**: fitness/human: live story-time (fitness:gym-relatable, seen 13) vs used {'bold-claim': 15} (mismatch 100%, n=15)
- **evidence**: gadgets/ai: live negative-command (ugc-ads:problem-solution, seen 4, thin) vs used {'curiosity-gap': 24, 'transformation': 4, 'bold-claim': 2} (mismatch 100%, n=30)
- **files likely involved**: `viral_script_maker.py (pick_hook, NICHE_HOOK)`, `vsp/research.py`
- **done when**: golden family mismatch vs live ranking < 50% per cell with verify ACCEPT
- **acceptance**: `python3 -m vsp.improve verify --base b867500 --cand HEAD`

## 3. `T-RUBRIC-R14` — Raise R14: caption echoes the comment keyword

- **score** 3.7 · kind `rubric` · first seen 2026-09-29
- **why**: R14 fails on 5.7% of holdout runs ({'routine': 20}). 
- **evidence**: golden: by concept {'routine': 10}; by format {'demo': 2, 'pov-vlog': 2, 'review': 2, 'talking-head': 2, 'transformation': 2}; by presenter {'ai': 5, 'human': 5}
- **evidence**: holdout: by concept {'routine': 20}; by format {'demo': 4, 'pov-vlog': 4, 'review': 4, 'talking-head': 4, 'transformation': 4}; by presenter {'ai': 10, 'human': 10}
- **example**: `h-gym-routine|demo|ai|1` hook 'Day 14 of the 6AM routine.' · overlay '6AM ROUTINE'
    repro: `python3 pipeline.py 'my 6am gym routine' --format demo --presenter ai --seed 1 --duration 30 --out-dir /tmp/vsp-repro-h-gym-routine-demo-ai-1 ; python3 vsp/rubric.py /tmp/vsp-repro-h-gym-routine-demo-ai-1/script.json`
- **example**: `h-gym-routine|demo|human|1` hook 'Day 14 of my 6AM routine.' · overlay '6AM ROUTINE'
    repro: `python3 pipeline.py 'my 6am gym routine' --format demo --presenter human --seed 1 --duration 30 --out-dir /tmp/vsp-repro-h-gym-routine-demo-human-1 ; python3 vsp/rubric.py /tmp/vsp-repro-h-gym-routine-demo-human-1/script.json`
- **files likely involved**: `viral_script_maker.py (build_caption, _cta_word)`
- **done when**: R14 failures on holdout drop (target 0) with verify ACCEPT
- **acceptance**: `python3 -m vsp.improve verify --base b867500 --cand HEAD`

## 4. `T-D60-D124` — Make D124 (Frame-0 Visual Collision Outranks Motion) code-traceable or mark it superseded

- **score** 2.0 · kind `doc-only` · first seen 2026-09-29
- **why**: D124 has no code reference (docs/RULE-COVERAGE.md). Implement it in the maker/shot list with a self-test case, or record in RULES.md why it is superseded (humans own RULES.md).
- **evidence**: section §54b — 2026-09-28 — judge loop cycle 32 (heated…
- **files likely involved**: `viral_script_maker.py or make_shotlist.py`, `vsp/selftest_cases.py (new case)`, `RULES.md (human review)`
- **done when**: tools/rule_coverage.py no longer lists D124 as DOC-ONLY, verify ACCEPT
- **acceptance**: `python3 -m vsp.improve verify --base b867500 --cand HEAD`

## 5. `T-D60-D127` — Make D127 (Borrowed-Interest Hook Frames) code-traceable or mark it superseded

- **score** 2.0 · kind `doc-only` · first seen 2026-09-29
- **why**: D127 has no code reference (docs/RULE-COVERAGE.md). Implement it in the maker/shot list with a self-test case, or record in RULES.md why it is superseded (humans own RULES.md).
- **evidence**: section §56 USER-SUPPLIED: BORROWED-INTEREST HOOK FRAME…
- **files likely involved**: `viral_script_maker.py or make_shotlist.py`, `vsp/selftest_cases.py (new case)`, `RULES.md (human review)`
- **done when**: tools/rule_coverage.py no longer lists D127 as DOC-ONLY, verify ACCEPT
- **acceptance**: `python3 -m vsp.improve verify --base b867500 --cand HEAD`

## 6. `T-D60-D131` — Make D131 (The Combo Method As The D124 Context-Flip Generator) code-traceable or mark it superseded

- **score** 2.0 · kind `doc-only` · first seen 2026-09-29
- **why**: D131 has no code reference (docs/RULE-COVERAGE.md). Implement it in the maker/shot list with a self-test case, or record in RULES.md why it is superseded (humans own RULES.md).
- **evidence**: section §60 USER-SUPPLIED: THE COMBO METHOD + EMOTION-G…
- **files likely involved**: `viral_script_maker.py or make_shotlist.py`, `vsp/selftest_cases.py (new case)`, `RULES.md (human review)`
- **done when**: tools/rule_coverage.py no longer lists D131 as DOC-ONLY, verify ACCEPT
- **acceptance**: `python3 -m vsp.improve verify --base b867500 --cand HEAD`

## 7. `T-D60-D145` — Make D145 (Hook Provenance Is Honest) code-traceable or mark it superseded

- **score** 2.0 · kind `doc-only` · first seen 2026-09-29
- **why**: D145 has no code reference (docs/RULE-COVERAGE.md). Implement it in the maker/shot list with a self-test case, or record in RULES.md why it is superseded (humans own RULES.md).
- **evidence**: section §66 — PIPELINE v2 (2026-09-28)
- **files likely involved**: `viral_script_maker.py or make_shotlist.py`, `vsp/selftest_cases.py (new case)`, `RULES.md (human review)`
- **done when**: tools/rule_coverage.py no longer lists D145 as DOC-ONLY, verify ACCEPT
- **acceptance**: `python3 -m vsp.improve verify --base b867500 --cand HEAD`

## 8. `T-D60-D152` — Make D152 (Export Contract) code-traceable or mark it superseded

- **score** 2.0 · kind `doc-only` · first seen 2026-09-29
- **why**: D152 has no code reference (docs/RULE-COVERAGE.md). Implement it in the maker/shot list with a self-test case, or record in RULES.md why it is superseded (humans own RULES.md).
- **evidence**: section §66 — PIPELINE v2 (2026-09-28)
- **files likely involved**: `viral_script_maker.py or make_shotlist.py`, `vsp/selftest_cases.py (new case)`, `RULES.md (human review)`
- **done when**: tools/rule_coverage.py no longer lists D152 as DOC-ONLY, verify ACCEPT
- **acceptance**: `python3 -m vsp.improve verify --base b867500 --cand HEAD`

## 9. `T-D60-D153` — Make D153 (Manifest + Trace On Every Run) code-traceable or mark it superseded

- **score** 2.0 · kind `doc-only` · first seen 2026-09-29
- **why**: D153 has no code reference (docs/RULE-COVERAGE.md). Implement it in the maker/shot list with a self-test case, or record in RULES.md why it is superseded (humans own RULES.md).
- **evidence**: section §66 — PIPELINE v2 (2026-09-28)
- **files likely involved**: `viral_script_maker.py or make_shotlist.py`, `vsp/selftest_cases.py (new case)`, `RULES.md (human review)`
- **done when**: tools/rule_coverage.py no longer lists D153 as DOC-ONLY, verify ACCEPT
- **acceptance**: `python3 -m vsp.improve verify --base b867500 --cand HEAD`

## 10. `T-D60-D3` — Make D3 (Ai-Lane Mystery Plant) code-traceable or mark it superseded

- **score** 2.0 · kind `doc-only` · first seen 2026-09-29
- **why**: D3 has no code reference (docs/RULE-COVERAGE.md). Implement it in the maker/shot list with a self-test case, or record in RULES.md why it is superseded (humans own RULES.md).
- **evidence**: section 10. JUDGE-LOOP PATCHES — 2026-09-27 (script-vs-…
- **files likely involved**: `viral_script_maker.py or make_shotlist.py`, `vsp/selftest_cases.py (new case)`, `RULES.md (human review)`
- **done when**: tools/rule_coverage.py no longer lists D3 as DOC-ONLY, verify ACCEPT
- **acceptance**: `python3 -m vsp.improve verify --base b867500 --cand HEAD`

## 11. `T-D60-D4` — Make D4 (Human Transformation Journey Grammar) code-traceable or mark it superseded

- **score** 2.0 · kind `doc-only` · first seen 2026-09-29
- **why**: D4 has no code reference (docs/RULE-COVERAGE.md). Implement it in the maker/shot list with a self-test case, or record in RULES.md why it is superseded (humans own RULES.md).
- **evidence**: section 10. JUDGE-LOOP PATCHES — 2026-09-27 (script-vs-…
- **files likely involved**: `viral_script_maker.py or make_shotlist.py`, `vsp/selftest_cases.py (new case)`, `RULES.md (human review)`
- **done when**: tools/rule_coverage.py no longer lists D4 as DOC-ONLY, verify ACCEPT
- **acceptance**: `python3 -m vsp.improve verify --base b867500 --cand HEAD`

## 12. `T-D60-D49` — Make D49 (Design The Conversion Shot) code-traceable or mark it superseded

- **score** 2.0 · kind `doc-only` · first seen 2026-09-29
- **why**: D49 has no code reference (docs/RULE-COVERAGE.md). Implement it in the maker/shot list with a self-test case, or record in RULES.md why it is superseded (humans own RULES.md).
- **evidence**: section 27. SHOTS & CUTS PATCHES (hair wax stick bundle…
- **files likely involved**: `viral_script_maker.py or make_shotlist.py`, `vsp/selftest_cases.py (new case)`, `RULES.md (human review)`
- **done when**: tools/rule_coverage.py no longer lists D49 as DOC-ONLY, verify ACCEPT
- **acceptance**: `python3 -m vsp.improve verify --base b867500 --cand HEAD`

## 13. `T-D60-D50` — Make D50 (Mark The Match-Cuts) code-traceable or mark it superseded

- **score** 2.0 · kind `doc-only` · first seen 2026-09-29
- **why**: D50 has no code reference (docs/RULE-COVERAGE.md). Implement it in the maker/shot list with a self-test case, or record in RULES.md why it is superseded (humans own RULES.md).
- **evidence**: section 27. SHOTS & CUTS PATCHES (hair wax stick bundle…
- **files likely involved**: `viral_script_maker.py or make_shotlist.py`, `vsp/selftest_cases.py (new case)`, `RULES.md (human review)`
- **done when**: tools/rule_coverage.py no longer lists D50 as DOC-ONLY, verify ACCEPT
- **acceptance**: `python3 -m vsp.improve verify --base b867500 --cand HEAD`

## 14. `T-D60-D51` — Make D51 (Routine/Daily-Vlog Concept Class) code-traceable or mark it superseded

- **score** 2.0 · kind `doc-only` · first seen 2026-09-29
- **why**: D51 has no code reference (docs/RULE-COVERAGE.md). Implement it in the maker/shot list with a self-test case, or record in RULES.md why it is superseded (humans own RULES.md).
- **evidence**: section 26. JUDGE-LOOP PATCHES (cycle 13) — 2026-09-27 …
- **files likely involved**: `viral_script_maker.py or make_shotlist.py`, `vsp/selftest_cases.py (new case)`, `RULES.md (human review)`
- **done when**: tools/rule_coverage.py no longer lists D51 as DOC-ONLY, verify ACCEPT
- **acceptance**: `python3 -m vsp.improve verify --base b867500 --cand HEAD`

## 15. `T-D60-D60` — Make D60 (Rule Status Is Draft Until Code-Traceable) code-traceable or mark it superseded

- **score** 2.0 · kind `doc-only` · first seen 2026-09-29
- **why**: D60 has no code reference (docs/RULE-COVERAGE.md). Implement it in the maker/shot list with a self-test case, or record in RULES.md why it is superseded (humans own RULES.md).
- **evidence**: section 30. JUDGE-LOOP PATCHES (cycle 15) — 2026-09-27 …
- **files likely involved**: `viral_script_maker.py or make_shotlist.py`, `vsp/selftest_cases.py (new case)`, `RULES.md (human review)`
- **done when**: tools/rule_coverage.py no longer lists D60 as DOC-ONLY, verify ACCEPT
- **acceptance**: `python3 -m vsp.improve verify --base b867500 --cand HEAD`
