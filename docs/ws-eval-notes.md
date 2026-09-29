# WS-EVAL notes (ws/eval)

**Commits** (on d903c22): 157ab6d lexicon · 0aeb1ec gate-1 rules · ddce108 gate-2 rules · b076889 rubric · 92ea16b creative_eval · 28687ed scorecard · fc8aabc schema · a1a88df gate shape errors · 9bd5fc1 self-test · a129925 RULES §68 · 70c6137 frame-0 audit · 58b20e6 e2e tags · 62604d1 review fixes · feab58c §68 refinements · cbe47e9/d84f16a notes.

**Rules** (all errors, appended after existing rules)

| id | stage | checks | silent when |
|---|---|---|---|
| D154 | gate 1 | 3–5 variants; A = script hook + overlay; distinct visual types, first 3 words; hook screens on every variant; schema shape | no `hook_variants` |
| D155 | gate 1 | hashtag caps 5/5/15, YouTube limits, caption screens, one CTA, AI line and toggles, keyword in line 1 and title, cover | no `discovery` |
| D156 | gate 1 | valid ids; 140–200 wpm ≥ beat sizing; static ≤3.5 s; music off-master, 3 lanes; AI voice disclosed; curve entry per item | no `direction` |
| D158 | gate 1 | fake urgency/scarcity/offers vs `offer_in` | no phrase matches |
| D157 | gate 2 | shots typed; frame 0; face/hands by 3 s; ≤2 same-scale in a row; moves on long shots; AI proof = REAL FOOTAGE; loop at ≤15 s | no `- Shot type:` line |
| D159 | gate 2 | upload-time library lane; no track titles; no TikTok AI music | no CREATIVE DIRECTION section |
| D160 | gate 2 | no in-frame text; no quoted dialogue; identity lock only on face shots | no `- Shot type:` line |

D161 is rubric-only (R24).

**Rubric** (id tier/weight): R21 I/2 · R22 I/2 · R23 I/2 audit · R24 I/2 · R25 I/2 · R26 O/1 audit · R27 O/1 audit · R28 I/2 audit.

**creative_eval**: variant counts, vibe, keyword placement, hook strength, typed share, cadence in band, human by 3 s, frame-0 checks, loop, real-footage marks, high-AI-risk share, sections, alternate openings, shot-plan pass, D157/D159/D160 findings; `summarize()`.

**Self-test**: 112 gate cases (74 new), 21 unit checks (9 new), 11 e2e checks (1 new, skipped until the modules exist), 7 optional selfchecks. Green on 3.9 and 3.12.

**Results**
- fast_eval --gate2: 990 runs, gate 1 100%, e2e 100%. Rubric mean 99.9 → 77.6 (R21–R27 fail on absent keys, expected).
- Holdout at 15/30/60 s: 3,150 runs, 100%.
- Smoke: 120 runs, e2e and shippable 100%.
- Baseline worktree: creative metrics all zero.
- Legacy snapshot: 0 findings changed, best-of-8 winners unchanged.
