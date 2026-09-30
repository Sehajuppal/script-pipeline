# WS-HOOKS notes (branch ws/hooks)

## Commits
- `b75657d` vsp/data/hooks.json: the research JSON, verbatim, plus maker glue
- `0e9243b` maker: 9 new families, research templates, shared screens, hook-strength tier; research family map
- `e270128` `variants()` first cut, weighted niche family, card fixes
- `b0dba53` §1.2 checker, `render_md`, selfcheck, CLI
- `65dc551` faster `variants()` (13.8 → 6.5 ms), more AI-safe alternates
- `8e60141` number agreement; no invented identities; cleaner cards
- `af75286` selfcheck also runs gate 2 and checks PYTHONHASHSEED determinism
- `797bab1` `score_hook(…, script)` reproduces the stored scores
- (this file)

## Families and templates
- HOOKS went from 8 families / 41 templates to 17 / 174.
- New families: problem-agitate, question, comparison, pov, newness, confession, price-anchor, showcase, day-counter.
- All 103 product-grammar research templates are in, rewritten for the maker's slots.
- The 12 listicle and challenge templates were rewritten into new banks, along with the other streak, list and fix archetypes: `CHALLENGE_ALT_HOOKS` (18), `SHOWCASE_ALT_HOOKS` (10), `ROUTINE_ALT_HOOKS` (8), and 9 new advice forms.
- `HOOK_SLOTS` is unchanged.

## Before → after
| metric | before | after |
|---|---|---|
| fast_eval distinct, golden | 282 (0.285) | 445 (0.449) |
| fast_eval distinct, holdout | 290 | 459 |
| fast_eval distinct, 15/60 s | 156 | 213 |
| scorecard distinct-2 | 0.0784 | 0.1038 |
| scorecard distinct | 28.5% | 45.0% |
| scorecard seed diversity | 0.707 | 0.827 |
| mean primary `score_hook`, golden | 0.676 | 0.773 |
| primaries < 0.60 (golden / holdout) | 173 / 132 | 0 / 0 |

In every run, gate 1, e2e and shippable are 100%, fallback is 0%, rubric is 99.9, and there are no compliance flags.

## Examples (seed 1): archetype / frame 0 | hook | score
**Milk frother, AI, demo**
- A problem-agitate / product-in-action | Why does your milk frother keep failing? | 80
- B bold-claim / result-reveal (real footage) | Most milk frothers fail. This one didn't. | 77
- C curiosity-gap / satisfying-macro | The milk frother: here's what 7 days showed. | 78
- D showcase / pov-hands | The electric milk frother. Here's the after. | 76
- E negative-command / problem-state | Stop buying milk frothers on looks alone. | 71

**Silk pillowcase, human, review**
- A question | The silk pillowcase after 7 days. Worth it? | 80
- B confession / face-reaction | Honestly? I misjudged the silk pillowcase. | 72
- C curiosity-gap | What 7 days revealed about the silk pillowcase. | 69
- D comparison / unboxing | I didn't expect the silk pillowcase to win. | 61
- E showcase / pov-hands | This is the silk pillowcase in action. | 62

**Sugar, 21 days, human, pov-vlog**
- A challenge | Can I last 21 days without sugar? | 79
- B question | Quit sugar for 21 days? | 86
- C day-counter / split | Day 21 of no sugar. | 70
- D story-time | Day 21, and I almost caved. | 54
- E question | Could you go 21 days without sugar? | 76

## Selfcheck
`python3 -m vsp.hooks selfcheck` passes all 29 checks on 3.9 and 3.12. It sweeps 680 scripts (3 variants ×5, 4 ×139, 5 ×536).
- All §1.2 rules hold, and A is always the script's actual hook.
- Output is byte-identical across two runs, across processes and across PYTHONHASHSEED values.
- `variants()` averages 6–7 ms per call.
- No script has `creative_warnings`.
- Every script passes gate 1 and gate 2.

The pipeline self-tests pass on 3.9 and 3.12, and so does `vsp.improve selfcheck`.

## Unmet / caveats
- The HOOK-09 targets (distinct ≥ 0.60, distinct-2 ≥ 0.20) are not reached.
- Several slots are still dead for products, because no new slots were allowed: `{flaw}`, `{after}`, `{moment}`, `{thing}`, `{situation}`, `{timespan}` and `{common}`. Research templates that use them stay inert.
- Some archetypes render only when the prompt supplies what they need:
  - comparison needs a named competitor;
  - proof-first needs proof;
  - price-anchor needs a price;
  - identity-reveal needs a real role from the prompt, which the maker never parses, so it is effectively off.
- The niche family is now a 2× draw weight rather than the final lexicographic key. Before this change, one research category seen only 4 times turned 7 niches into problem-agitate openings.
- The evolve engine still assumes pick_hook draws only from the top of the score tuple, so it slightly underestimates the diversity of each pick.
- For non-creator advice topics, the maker's advice payoff still says "fix the first 3 seconds". That code is outside my region, so those hooks are only nominally paid.

## For the integrator and evaluator
- `vsp.hooks` exports `variants`, `score_hook` (optional `archetype`, `others` and `info` arguments), `render_md` (hooks.md, starting `## HOOK VARIANTS — alternate openings`), `check_variants` (a §1.2 checker D154 can reuse), `payoff_type`, `payoff_compat`, and `frame0_visual_type` / `visual_type_of_direction`.
- pick_hook's score tuple keeps its five slots. The strength tier is nested in slot 2 as `(contract, tier)`.
- `ctx["hook_archetype"]` and `ctx["hook_template"]` record the primary.
