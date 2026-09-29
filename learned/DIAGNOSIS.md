# DIAGNOSIS — ranked improvement opportunities

Generated 2026-09-29T04:46:22+00:00 by `python3 -m vsp.improve diagnose` from measure `20260929T044606Z` at `333f695` (dirty tree) (budget small, seeds 1, 3.9.25). Scores are a transparent heuristic (share of runs × severity); compliance and a red self-test outrank everything. Tasks: `learned/TASKS.md`.

| suite | runs | e2e | shippable | rubric | selection | audit | compliance | hook distinct | s/run |
|---|---|---|---|---|---|---|---|---|---|
| golden | 330 | 1.0 | 1.0 | 99.9 | 99.9 | 100.0 | 0 | 0.4455 | 0.167 |
| holdout | 350 | 1.0 | 1.0 | 99.9 | 99.8 | 100.0 | 0 | 0.4857 | 0.169 |

## Ranked opportunities

1. **hook-family mix ignores the live niche ranking in 16 niche×presenter cells** — `drift` · score 22.4 · task `T-DRIFT-FAMILIES`
   - the market moved; the maker's family choice did not
   - gadgets/ai: live negative-command (ugc-ads:problem-solution) vs used {'curiosity-gap': 24, 'transformation': 4, 'bold-claim': 2} (mismatch 100%, n=30)
   - gadgets/human: live negative-command (ugc-ads:problem-solution) vs used {'curiosity-gap': 30} (mismatch 100%, n=30)
   - fitness/ai: live curiosity-gap (fitness:day-counter) vs used {'bold-claim': 15} (mismatch 100%, n=15)
   - fitness/human: live story-time (fitness:gym-relatable) vs used {'bold-claim': 15} (mismatch 100%, n=15)
2. **hook diversity is low (45% distinct hooks on golden)** — `diversity` · score 16.6 · task `T-HOOK-DIVERSITY`
   - few top-tied templates per niche family → seeds cannot vary the hook
   - golden: hooks distinct 0.4455 · distinct-2 0.1648 · seed diversity None · fallback 0.0 · product families {'bold-claim': '18 distinct / 48 runs', 'curiosity-gap': '70 distinct / 118 runs', 'negative-command': '2 distinct / 3 runs', 'story-time': '3 distinct / 6 runs', 'transformation': '34 distinct / 75 runs'}
3. **R14 (caption echoes the comment keyword) fails in 20/350 holdout runs** — `rubric` · score 3.7 · task `T-RUBRIC-R14`
   - tier O
   - golden: by concept {'routine': 10}; by format {'demo': 2, 'pov-vlog': 2, 'review': 2, 'talking-head': 2, 'transformation': 2}; by presenter {'ai': 5, 'human': 5}
   - holdout: by concept {'routine': 20}; by format {'demo': 4, 'pov-vlog': 4, 'review': 4, 'talking-head': 4, 'transformation': 4}; by presenter {'ai': 10, 'human': 10}
   - e.g. `h-gym-routine|demo|ai|1` hook 'Day 14 of the 6AM routine.' · overlay '6AM ROUTINE'
    repro: `python3 pipeline.py 'my 6am gym routine' --format demo --presenter ai --seed 1 --duration 30 --out-dir /tmp/vsp-repro-h-gym-routine-demo-ai-1 ; python3 vsp/rubric.py /tmp/vsp-repro-h-gym-routine-demo-ai-1/script.json`
   - e.g. `h-gym-routine|demo|human|1` hook 'Day 14 of my 6AM routine.' · overlay '6AM ROUTINE'
    repro: `python3 pipeline.py 'my 6am gym routine' --format demo --presenter human --seed 1 --duration 30 --out-dir /tmp/vsp-repro-h-gym-routine-demo-human-1 ; python3 vsp/rubric.py /tmp/vsp-repro-h-gym-routine-demo-human-1/script.json`
   - e.g. `h-gym-routine|pov-vlog|ai|1` hook 'Day 14 of the 6AM routine.' · overlay '6AM ROUTINE'
    repro: `python3 pipeline.py 'my 6am gym routine' --format pov-vlog --presenter ai --seed 1 --duration 30 --out-dir /tmp/vsp-repro-h-gym-routine-pov-vlog-ai-1 ; python3 vsp/rubric.py /tmp/vsp-repro-h-gym-routine-pov-vlog-ai-1/script.json`
4. **D124 Frame-0 Visual Collision Outranks Motion is DOC-ONLY** — `doc-only` · score 2.0 · task `T-D60-D124`
   - D60: a rule is a draft until code-traceable
   - section §54b — 2026-09-28 — judge loop cycle 32 (heated…
5. **D127 Borrowed-Interest Hook Frames is DOC-ONLY** — `doc-only` · score 2.0 · task `T-D60-D127`
   - D60: a rule is a draft until code-traceable
   - section §56 USER-SUPPLIED: BORROWED-INTEREST HOOK FRAME…
6. **D131 The Combo Method As The D124 Context-Flip Generator is DOC-ONLY** — `doc-only` · score 2.0 · task `T-D60-D131`
   - D60: a rule is a draft until code-traceable
   - section §60 USER-SUPPLIED: THE COMBO METHOD + EMOTION-G…
7. **D145 Hook Provenance Is Honest is DOC-ONLY** — `doc-only` · score 2.0 · task `T-D60-D145`
   - D60: a rule is a draft until code-traceable
   - section §66 — PIPELINE v2 (2026-09-28)
8. **D152 Export Contract is DOC-ONLY** — `doc-only` · score 2.0 · task `T-D60-D152`
   - D60: a rule is a draft until code-traceable
   - section §66 — PIPELINE v2 (2026-09-28)
9. **D153 Manifest + Trace On Every Run is DOC-ONLY** — `doc-only` · score 2.0 · task `T-D60-D153`
   - D60: a rule is a draft until code-traceable
   - section §66 — PIPELINE v2 (2026-09-28)
10. **D3 Ai-Lane Mystery Plant is DOC-ONLY** — `doc-only` · score 2.0 · task `T-D60-D3`
   - D60: a rule is a draft until code-traceable
   - section 10. JUDGE-LOOP PATCHES — 2026-09-27 (script-vs-…
11. **D4 Human Transformation Journey Grammar is DOC-ONLY** — `doc-only` · score 2.0 · task `T-D60-D4`
   - D60: a rule is a draft until code-traceable
   - section 10. JUDGE-LOOP PATCHES — 2026-09-27 (script-vs-…
12. **D49 Design The Conversion Shot is DOC-ONLY** — `doc-only` · score 2.0 · task `T-D60-D49`
   - D60: a rule is a draft until code-traceable
   - section 27. SHOTS & CUTS PATCHES (hair wax stick bundle…
13. **D50 Mark The Match-Cuts is DOC-ONLY** — `doc-only` · score 2.0 · task `T-D60-D50`
   - D60: a rule is a draft until code-traceable
   - section 27. SHOTS & CUTS PATCHES (hair wax stick bundle…
14. **D51 Routine/Daily-Vlog Concept Class is DOC-ONLY** — `doc-only` · score 2.0 · task `T-D60-D51`
   - D60: a rule is a draft until code-traceable
   - section 26. JUDGE-LOOP PATCHES (cycle 13) — 2026-09-27 …
15. **D60 Rule Status Is Draft Until Code-Traceable is DOC-ONLY** — `doc-only` · score 2.0 · task `T-D60-D60`
   - D60: a rule is a draft until code-traceable
   - section 30. JUDGE-LOOP PATCHES (cycle 15) — 2026-09-27 …

## Signals checked

- golden: selection 99.9 vs audit-only 100.0 (overall)
- golden: largest group gap hook_family=transformation (n=75) selection 100.0 vs audit 100.0 (gap +0.0)
- golden: largest group gap hook_family=listicle (n=20) selection 100.0 vs audit 100.0 (gap +0.0)
- holdout: selection 99.8 vs audit-only 100.0 (overall)
- holdout: largest group gap hook_family=transformation (n=61) selection 100.0 vs audit 100.0 (gap +0.0)
- holdout: largest group gap hook_family=listicle (n=20) selection 100.0 vs audit 100.0 (gap +0.0)
- golden vs holdout: e2e 1.0 vs 1.0, rubric 99.9 vs 99.9
- golden: hooks distinct 0.4455 · distinct-2 0.1648 · seed diversity None · fallback 0.0 · product families {'bold-claim': '18 distinct / 48 runs', 'curiosity-gap': '70 distinct / 118 runs', 'negative-command': '2 distinct / 3 runs', 'story-time': '3 distinct / 6 runs', 'transformation': '34 distinct / 75 runs'}
- holdout: hooks distinct 0.4857 · distinct-2 0.1583 · seed diversity None · fallback 0.0 · product families {'bold-claim': '10 distinct / 16 runs', 'curiosity-gap': '111 distinct / 173 runs', 'transformation': '30 distinct / 61 runs'}
- research pack: generated 2026-09-28T13:40:04+00:00 · age 15.11 h · stale False · sha e67ee781af40 · errors none
- drift beauty/ai: live transformation (research fashion-beauty:grwm-hook, seen 17) vs used {'transformation': 19, 'bold-claim': 1} → mismatch 5%
- drift beauty/human: live transformation (research fashion-beauty:grwm-hook, seen 17) vs used {'transformation': 19, 'bold-claim': 1} → mismatch 5%
- drift default/ai: live negative-command (research ugc-ads:problem-solution, seen 4) vs used {'curiosity-gap': 4, 'bold-claim': 1} → mismatch 100%
- drift default/human: live negative-command (research ugc-ads:problem-solution, seen 4) vs used {'curiosity-gap': 5} → mismatch 100%
- drift fitness/ai: live curiosity-gap (research fitness:day-counter, seen 10) vs used {'bold-claim': 15} → mismatch 100%
- drift fitness/human: live story-time (research fitness:gym-relatable, seen 13) vs used {'bold-claim': 15} → mismatch 100%
- drift gadgets/ai: live negative-command (research ugc-ads:problem-solution, seen 4) vs used {'curiosity-gap': 24, 'transformation': 4, 'bold-claim': 2} → mismatch 100%
- drift gadgets/human: live negative-command (research ugc-ads:problem-solution, seen 4) vs used {'curiosity-gap': 30} → mismatch 100%
- drift home/ai: live negative-command (research ugc-ads:problem-solution, seen 4) vs used {'transformation': 6, 'negative-command': 3, 'curiosity-gap': 1} → mismatch 70%
- drift home/human: live negative-command (research ugc-ads:problem-solution, seen 4) vs used {'story-time': 6, 'transformation': 4} → mismatch 100%
- drift outdoors/ai: live negative-command (research ugc-ads:problem-solution, seen 4) vs used {'curiosity-gap': 4, 'bold-claim': 1} → mismatch 100%
- drift outdoors/human: live negative-command (research ugc-ads:problem-solution, seen 4) vs used {'curiosity-gap': 5} → mismatch 100%
- drift pets/ai: live negative-command (research ugc-ads:problem-solution, seen 4) vs used {'transformation': 10} → mismatch 100%
- drift pets/human: live negative-command (research ugc-ads:problem-solution, seen 4) vs used {'transformation': 10} → mismatch 100%
- drift tools/ai: live negative-command (research ugc-ads:problem-solution, seen 4) vs used {'curiosity-gap': 8, 'transformation': 1, 'bold-claim': 1} → mismatch 100%
- drift tools/human: live negative-command (research ugc-ads:problem-solution, seen 4) vs used {'curiosity-gap': 10} → mismatch 100%
- drift wellness/ai: live negative-command (research ugc-ads:problem-solution, seen 4) vs used {'bold-claim': 5} → mismatch 100%
- drift wellness/human: live negative-command (research ugc-ads:problem-solution, seen 4) vs used {'bold-claim': 5} → mismatch 100%
- priors: learned/priors.json absent (python3 -m vsp.feedback learn writes it from posted-reel performance) — skipped
- rule coverage: 157 tracked ids, 12 DOC-ONLY (D60 drafts): D3, D4, D49, D50, D51, D60, D124, D127, D131, D145, D152, D153
- runtime golden: 0.167s/run · wall 7.6s · slowest door-lock|transformation|ai|1 0.226s, braces-prompt|pov-vlog|ai|1 0.221s, braces-prompt|transformation|human|1 0.218s
- runtime holdout: 0.169s/run · wall 8.1s · slowest h-knife|review|ai|1 0.261s, h-steamer|review|ai|1 0.223s, h-leash|review|ai|1 0.214s
