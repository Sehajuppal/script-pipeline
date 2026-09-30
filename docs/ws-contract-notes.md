# ws/contract — SO-2 Contract & Compliance notes (2026-09-28)

Branch `ws/contract` (from foundation a87fab6), worktree `/projects/wt/contract`.
Not pushed. Self-test green on python3.9 **and** python3.12 at every commit.

## Commits

| sha | subject |
|---|---|
| 2d20eaa | contract: rule registry (vsp/rules.py) + gates split into legacy rules |
| e4795d7 | selftest: v2 gate cases, per-case options, in-process unit checks |
| 94ad39b | research + router: stage-2 pack pinning (D148), stage-1 3-voter router (D147) |
| 711412b | research_bridge: guarded queries, abbreviation-safe splitter, grade-header variants, pack schema v2 |
| 3befffd | RULES.md: §66 pipeline v2 (D136–D153) + section-number cleanup |
| fb3db68 | tools/rule_coverage.py + docs/RULE-COVERAGE.md (D60 automation) |
| 0141821 | lexicon: D138 AI-disclosure-line helper (shared), + self-test case |

(+ this notes commit.)

## Files

- `vsp/gates.py` — legacy gate1/gate2 split one function per check (bodies verbatim, legacy order); `legacy_gate1/2`; registry-driven `gate1(script)`, `gate2(bundle_text, script)` (errors only, legacy first), `gate1_findings` / `gate2_findings` (`{rule, severity, message}` incl. warnings), `REGISTRY` (PEP 562), `DELIVERABLE_BLOCK`. `words_per_sec, parse_t, MISMATCH, STAGE_VERBS, LINK_GROUPS` still importable.
- `vsp/rules.py` (new) — `Rule(id, title, stage, severity, source, check, covers)`, `REGISTRY`, `evaluate(stage, script, bundle_text)`, `registry_table()`, helpers (`viewer_text`, `verbal_hook`, `frame0_item`).
- `vsp/lexicon.py` — extended only: `AI_WORD`, `AI_DISCLOSURE_CUE`, `has_ai_disclosure_line()`.
- `vsp/selftest.py`, `vsp/selftest_cases.py` — per-case options, 21 new cases, 9 unit checks.
- `vsp/router.py` (new), `vsp/research.py` (new), `research_bridge.py` (hardened).
- `RULES.md` (§66 + cleanup), `tools/rule_coverage.py` (new), `docs/RULE-COVERAGE.md` (generated).

Proof of "never weakened": `legacy_gate1/2` are byte-identical to the d8f8759 monoliths on 1,040 scripts (990-run maker matrix + the 17 fixtures + 33 outputs/ scripts), and on all 1,040 `gate1()`/`gate2()` = the legacy messages, unchanged and in order, followed only by v2-rule messages. The one deliberate change is the stated strengthening: DELIVERABLE now requires the full block (same message, same position).

## Registry (39 rules)

| # | id | stage | severity | covers | source |
|---|---|---|---|---|---|
| 1 | REQ-KEYS | gate 1 | error | — | pipeline.py gate1 (legacy) |
| 2 | MIN-BEATS | gate 1 | error | — | pipeline.py gate1 (legacy) |
| 3 | D37 | gate 1 | error | D37, D132 | RULES §24 D37 + §61 D132 (legacy) |
| 4 | TAG-MISMATCH | gate 1 | error | — | pipeline.py gate1 (legacy) |
| 5 | D43 | gate 1 | error | D43 | RULES §25 D43 (legacy; incl. "missing time window") |
| 6 | D44 | gate 1 | error | D44, D58, D126 | RULES §25/§29/§55 (legacy) |
| 7 | D55 | gate 1 | error | D55 | RULES §28 (legacy) |
| 8 | D74 | gate 1 | error | D74 | RULES D74 (legacy) |
| 9 | D78 | gate 1 | error | D78 | RULES D78 (legacy) |
| 10 | D94 | gate 1 | error | D94 | RULES §43 (legacy) |
| 11 | D103 | gate 1 | error | D103 | RULES §46 (legacy) |
| 12 | D111 | gate 1 | error | D111 | RULES §50 (legacy) |
| 13 | D136 | gate 1 | error | D136 | §66; FTC 16 CFR 465 |
| 14 | D137 | gate 1 | error | D137 | §66; FTC 16 CFR 465.2 |
| 15 | D138 | gate 1 | error | D138 | §66; EU AI Act Art. 50, NY law, platform AIGC labels |
| 16 | D139 | gate 1 | error | D139 | §66; Meta engagement-bait, Instagram eligibility |
| 17 | D140 | gate 1 | error | D140 | §66; Instagram 5-hashtag cap |
| 18 | D141 | gate 1 | error | D141 | §66; TikTok ad + Shop policy |
| 19 | D144 | gate 1 | error | D144, D17 | §66; §10 D17/D17b |
| 20 | D31 | gate 1 | error | D31 | RULES D31, gate-enforced per §66 |
| 21 | D73 | gate 1 | error | D73 | RULES §34 D73, gate-enforced per §66 |
| 22 | D93 | gate 1 | error | D93 | RULES D93, gate-enforced per §66 |
| 23 | D146 | gate 1 | error | D146 | §66 (D89 class) |
| 24 | D142 | gate 1 | **warn** | D142 | §66 (PROPOSED); Netflix 20 cps |
| 25 | DELIVERABLE | gate 2 | error | — | AGENT-BRIEF #4 (legacy, **strengthened**: full block) |
| 26 | RENDER-9x16 | gate 2 | error | — | legacy |
| 27 | WORDS-JSON | gate 2 | error | — | legacy |
| 28 | DO-NOT | gate 2 | error | — | legacy |
| 29 | WORDS-SCHEMA | gate 2 | error | — | legacy |
| 30 | REF-REELS | gate 2 | error | — | legacy |
| 31 | D43-BUNDLE | gate 2 | error | D43 | legacy ("D43 warnings present in bundle") |
| 32 | D36 | gate 2 | error | D36 | RULES §23 (legacy) |
| 33 | B4a | gate 2 | error | B4a | RULES §23 (legacy) |
| 34 | D46 | gate 2 | error | D46 | RULES §25 (legacy) |
| 35 | SHOT-DRIFT | gate 2 | error | — | legacy |
| 36 | D48 | gate 2 | error | D48 | RULES §27 (legacy) |
| 37 | D47 | gate 2 | error | D47 | RULES §27 (legacy) |
| 38 | D138 | gate 2 | error | D138 | §66; brief must carry the frame-0 "AI persona" label order |
| 39 | D151 | gate 2 | error | D151 | §66; FIXTURE reels unless VSP_FIXTURE_OK=1 |

Rule details: viewer text = dialogue, rehook, on_screen of hook_stack + beats, plus the caption. D73 counts whitespace tokens like pick_hook (a standalone em dash counts, as in the maker) on every VERBAL HOOK item (and the fixtures' bare `HOOK`). D144 reads the VISUAL TRIGGER card (hook stack first, else hook_stack[0] with on_screen, else the VISUAL TRIGGER beat) against the first verbal-hook line. D141's prompt allow-path matches by claim key (guarantee/guaranteed, cure/cures …). D138 (gate 1) requires a caption line with "AI" **and** a disclosure cue: a product name like "AI note taker" is not a disclosure. A check that raises becomes an error finding ("<id>: check crashed … — failing closed"). v2 messages never contain `; ` (the report separator).

## Self-test (17 legacy + 21 new cases + 9 unit checks, ~1.9 s)

New cases (`only` = every failure message must start with that id): `ai-presenter-good` (pass), `d136-unsourced-social-proof` (only D136), `d136-prompt-supplied-proof` (pass), `d137-ai-lived-experience` (only D137), `d138-ai-no-disclosure-field`, `d138-ai-no-caption-line`, `d138-ai-product-name-is-not-disclosure` (only D138), `d139-engagement-bait` (only D139), `d140-too-many-hashtags`, `d140-generic-only-hashtags` (only D140), `d141-absolute-claim` (only D141), `d141-prompt-supplied-claim` (pass), `d144-overlay-fragment`, `d144-overlay-too-long` (only D144), `d31-raw-template-slot` (only D31), `d73-verbal-hook-over-8` (only D73), `d93-repeated-rehook` (only D93), `d146-unplanned-part2` (only D146), `d146-part2-with-series-plan` (pass), `d142-fast-onscreen-warns-only` (pass), `d151-fixture-reels-rejected` (only D151, runs with `{"env": {"VSP_FIXTURE_OK": None}}`).

Unit checks: `registry-shape` (legacy rules wrap the legacy checks in legacy order), `router-contract`, `research-pack-contract`, `deliverable-block-in-sync`, `deliverable-check-strengthened`, `d138-brief-label-instruction` (a brief make_shotlist never emits), `d142-warning-never-fails`, `legacy-messages-first`, `crashing-check-fails-closed`.

Mutation check: disabling check_d144 / check_d151 / check_d138_brief / check_d73, or reverting the DELIVERABLE strengthening, each turns the self-test red. Legacy tuples are untouched; the legacy `d43-overflow` case now also reports D73 after its D43 message (it still fails with "D43").

## Scorecard on the FOUNDATION maker (label contract-wip, 990 runs, python3.9, 14.7 s)

crash 0 · gate-1 pass 15/990 (unchanged from foundation) · e2e 0/990 (unchanged) · rubric mean 70.5. The 15 gate-1 passes (human × morning-routine) clear every new rule and still fail gate 2 on legacy D48. **No run is blocked by new rules alone**: on the old maker they cost zero passes; they are the generation team's to-do list.

| new rule | runs (of 990) | what fires | owner |
|---|---|---|---|
| D146 | 882 | CTA "Follow, part 2: {next}." with no `series_plan` (= rubric R20) | SO-1 |
| D144 | 688 | "NOBODY MENTIONS FLAW" 582; "BUYING COFFEE DAYS" / "THIRTY DAYS INSTAGRAM" / "THIRTY DAYS SUGAR" 30 each; "THINGS SENSE" 16 (= R08) | SO-1 |
| D137 | 186 (AI only: 186/495) | "I noticed" 80, "I tried" 73, "my face" 15, "I've tried" 12, "I woke" 8, "I slept" 8, "I used" 2 (= R06) | SO-1 |
| D140 | 150 | #viral #fyp #ugc on the 5 default-niche prompts (door lock, silk pillowcase, milk frother, braces bottle, hooks advice) | SO-1 |
| D31 | 36 | review payoff card leaks "{category_s}" on the 6 showcase/challenge prompts | SO-1 |
| D142 (warn) | 744 | payoff cards at 36–50 chars/s (the D103 scripts) | SO-1 |
| D136, D138 (g1), D139, D141, D73, D93 | 0 | — | — |
| D138 (g2), D151 | 0 | in-process gate 2 on all 990 bundles, VSP_FIXTURE_OK=1 | — |

No false positives on the self-test good fixture, the legacy pass control, or the no-clobber fixture (zero v2 findings). Also checked: my gate 2 on 330 bundles built with ws/delivery's new make_shotlist raises no D138/D151/DELIVERABLE finding (its DELIVERABLE block is identical to the gate's copy).

## Router — the 33 golden prompts (`route(prompt)`, repo pack)

Never raises (33 × {None, ai, human} × fmt=review on 3.9 and 3.12). No prompt is below the 2/3 agreement bar; in 6 the maker is outvoted by the other two voters (a route warning naming the maker's niche).

| id | concept | niche | fit | agreement | votes maker · lexicon · research | presenter |
|---|---|---|---|---|---|---|
| sunrise-lamp | product | gadgets | utilitarian | 1.00 | gadgets · gadgets · gadgets | ai |
| projector-decimal | product | gadgets | utilitarian | 1.00 | gadgets · gadgets · gadgets | ai (B15: high complexity) |
| door-lock | product | home | utilitarian | 0.67 | **default** · home · home | ai |
| silk-pillowcase | product | beauty | hedonic | 0.67 | **default** · beauty · beauty | human |
| milk-frother | product | tools | utilitarian | 0.67 | **default** · tools · tools | ai |
| hair-wax | product | beauty | hedonic | 1.00 | beauty · beauty · beauty | human |
| eyelashes | product | beauty | hedonic | 1.00 | beauty · beauty · beauty | human |
| lunch-bag | product | tools | utilitarian | 1.00 | tools · tools · tools | ai |
| car-trash | product | automotive | utilitarian | 1.00 | automotive ×3 | ai |
| bird-feeder | product | pets | utilitarian | 1.00 | pets ×3 | ai |
| bands | product | fitness | utilitarian | 1.00 | fitness ×3 | ai |
| yoga-mat | product | fitness | utilitarian | 1.00 | fitness ×3 | ai |
| power-bank | product | gadgets | utilitarian | 1.00 | gadgets ×3 | ai |
| earbuds | product | gadgets | utilitarian | 1.00 | gadgets ×3 | ai |
| white-noise | product | wellness | utilitarian | 1.00 | wellness ×3 | ai |
| office-chair | product | home | utilitarian | 0.67 | **beauty** (chair ⊃ "hair") · home · home | ai |
| lantern | product | outdoors | utilitarian | 1.00 | outdoors ×3 | ai |
| trunk | product | automotive | utilitarian | 1.00 | automotive ×3 | ai |
| lick-mat | product | pets | utilitarian | 1.00 | pets ×3 | ai |
| posture | product | fitness | utilitarian | 1.00 | fitness ×3 | ai |
| serum | product | beauty | hedonic | 1.00 | beauty ×3 | human |
| inflator | product | automotive | utilitarian | 1.00 | automotive ×3 | ai |
| laptop-stand | product | gadgets | utilitarian | 1.00 | gadgets ×3 | ai |
| phone-clamp | product | gadgets | utilitarian | 1.00 | gadgets ×3 | ai |
| braces-prompt | product | default | neutral | 1.00 | default ×3 (braces stripped, warning) | human |
| kitchen-finds | showcase | tools | utilitarian | 1.00 | tools ×3 | ai |
| car-finds | showcase | automotive | utilitarian | 1.00 | automotive ×3 | ai |
| coffee-30 | challenge | food | hedonic | 1.00 | food ×3 | human (D137) |
| insta-14 | challenge | default | hedonic | 1.00 | default ×3 | human (D137) |
| read-30 | challenge | default | hedonic | 1.00 | default ×3 | human (D137) |
| sugar-21 | challenge | food | hedonic | 0.67 | **default** · food · food | human (D137) |
| morning-routine | routine | wellness | neutral | 1.00 | wellness ×3 | human (D137) |
| hooks-advice | advice | education | neutral | 0.67 | **default** · education · education | human |

Concept votes agree on all 33 (the research voter abstains on concept). Prices: sunrise-lamp "12", projector "12.99", posture "9", else None.

## Research (stage 2) and research_bridge

- `load_pack()` on the repo pack: valid v1 pack, sha256 e67ee781…, age ≈12 h, not stale. `live_hook_family` walks the whole ranked list (fitness + presenter=ai skips "gym-relatable"→story-time and lands on "day-counter"→curiosity-gap); `niche_fresh_lines` drops the pack's annotator lines ("(visual open, …)", "text-only teaser …", "… character skit") — the repo pack's 15 fresh lines are all comedy, so no maker niche gets any.
- research_bridge tested only in scratch (`VSP_VIRAL_DB`/`VSP_RESEARCH_PACK`/`VSP_DOSSIER_DIR`): fixture DB → valid v2 pack (48 reels, niche_map); schema-mismatched DB → 5 warnings, pack built; non-SQLite file with an existing pack → refresh skipped, last good pack byte-identical; missing DB → no DB file created. Synthetic dossier: `**Grade: VERIFIED**`, `### VERIFIED`, `VERIFIED:` accepted, CONTESTED excluded, no cuts at "et al." / "Int." / initials. The repo `research_pack.json` was never rebuilt.

## Coverage (tools/rule_coverage.py, same tool both trees)

| D-numbers | GATE | MAKER | SHOTLIST | PIPELINE | DOC-ONLY | total |
|---|---|---|---|---|---|---|
| before (a87fab6) | 17 | 106 | 1 | 1 | 9 | 134 |
| after (ws/contract) | 30 | 104 | 1 | 6 | 12 | 153 |

"Before" reproduces the plan's 17 / 108 (maker + shotlist + pipeline) / 9. Newly GATE: D17, D31, D73, D93, D136–D142, D144, D146, D151. D7 is no longer GATE: in the old grep it was only a comment token in gates.py, not a check. DOC-ONLY after = the 9 legacy drafts (D3, D4, D49, D50, D51, D60, D124, D127, D131) + D145, D152, D153 (§66 "PENDING INTEGRATION", owned by SO-1/SO-3). `--check` passes on ws/contract; it flags a pending rule once it becomes code-traceable.

## RULES.md changes

§66 appended (D136–D153 with mechanism, linked sources, grade, enforced-in, verification; dated gate-enforcement notes for D17/D31/D73/D93; the DELIVERABLE strengthening). Housekeeping: D65 retro-defined (superseded by D143); second §45/§49/§50/§51 → §45b/§49b/§50b/§51b, D105's "§45" → "§45b"; judge-loop cycle 32 → §54b; §56 and §60–§65 promoted to `##`; alias notes (maker "D47" = RULES D51; self-test "D75" = old D78); title block updated. No historical text rewritten.

## Risks for the integrator

1. **New rules become the main blockers once SO-1 fixes the timeline.** D146 (882), D144 (688), D137 (186), D140 (150), D31 (36) all fire on the foundation maker. The repair loop can key on the ids: D146 → add `series_plan` or drop the part-2 CTA; D144 → first ≤3 hook words or a label; D140 → niche tag / trim to 5; D138 → add the caption line. D137 and D31 need maker fixes.
2. **D141 fires on the showcase + prompt-price surprise** "the cheapest item — under $X — …" (D84 slot). No golden prompt has that shape, so the scorecard can't see it. SO-1 should rephrase it.
3. **Warnings are invisible today.** pipeline.py prints `gate1()` (errors only), so D142 needs `gate1_findings()` to reach validation-report.md / gate-report.json.
4. **D138 exists in both stages.** Findings consumers should key on (stage, rule). The gate's caption check (cue word required) is stricter than rubric R16 (`\bAI\b` anywhere); consider `lexicon.has_ai_disclosure_line` for R16.
5. **DELIVERABLE is now byte-exact.** Any whitespace edit to make_shotlist.DELIVERABLE fails every bundle (intended; ws/delivery's copy is identical today). CRLF is normalized.
6. **D151 in production.** Any gate-2 run on fixture data without `VSP_FIXTURE_OK=1` fails (intended). Keep the env var in self-test/evals and in any new replay/manifest tests.
7. **Fail-closed changes a classification.** A crashing check is now an error finding, not a traceback. Exit is still 1, but the scorecard counts such runs as gate1_fail rather than crash.
8. **The router's voters are correlated.** The lexicon and research voters are both keyword classifiers, so agreement mostly measures maker vs. keywords. `route(pack=None)` loads the configured pack itself; pass stage 2's pack (or `False` for `--no-research`) to avoid a second load. `strict_ok` is the `--strict-route` predicate.
9. **`research.load_pack` returns `None` on a schema-invalid pack** (errors in meta). Stale is only a warning; treat `None` as no research. research_bridge's keep-last-good guard only protects an existing pack: never `--refresh --force` the repo pack without the DB.
10. **Lexicon semantics I rely on but don't own.** `AI_FIRST_PERSON` flags "I noticed" / "I love this", which a curator voice may use. `overlay_is_clean` treats any ":" or "|" overlay as a label form, and its ≤3-word count rejects "DAY 1 | DAY 7" despite the docstring.
