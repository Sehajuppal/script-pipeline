# WS-SHOTS notes: shot recommender (v2.1, branch ws/shots)

## Commits
f246c64 data tables · 50728a9 `vsp/shotplan.py` + make_shotlist wiring · 6a3785c exporters · efacb62 `selfcheck()` · cb6bb66 product fit, recipe order · 11510b4 shoot-plan setups · b814168 robustness on malformed input · 9295462 time-marker rule · 5f19669 frame 0 from variant A · 2f5a4b5 visual-type sweep · then this notes commit.

## What each shot now carries
Every `### Shot` block gets `- Shot type: <id> · <scale> · <move> · <purpose> · energy <n> · AI risk <risk>` right after `- Camera:`. AI-presenter proof shots also get `- REAL FOOTAGE REQUIRED: <why> — do not generate`. shots.json holds the §1.4 keys plus `why`, `light_preset`, `ai_swapped_from` and `real_footage_why`. shotlist.csv adds the 8 new columns.

## Stats
Sample: golden × 5 formats × 2 presenters, 30 s, seed 1 (330 bundles, 13.6 shots each, 47 of 58 types used).
- **Top 10 shot types:** reaction-cutaway-3q 287, mws-cta-to-camera 278, talking-head-mcu 277, pov-hands-first-use 248, vo-over-hands-broll 240, macro-texture-ecu 230, loop-return-frame 224, product-operating-cu 224, matched-before 183, split-before-after 176.
- **AI risk:**
  - all shots: low 34%, med 33%, high 32%;
  - shots the AI actually renders in AI bundles: low 50%, med 50%, **high 0%**.
- **Real-footage shots per AI bundle:** mean 4.0. By format: demo 3.3, review 3.4, talking-head 3.3, pov-vlog 3.0, transformation 7.1. Range 0–9.

## Before → after (milk-frother sample script, AI, demo)
**Shot block.** Before, one PAYOFF shot:
`- Camera: Presenter to camera, product in hand. Slow push-in…` with the line "before and after, side by side", but no BEFORE was ever filmed.

After, a matched BEFORE is added at 4a, then:
```
### Shot 5a (21.9–23.6s) — PAYOFF
- Camera: Split-screen BEFORE | AFTER built in the edit: two matched clips from one taped phone spot, same lens and light, locked-off
- Shot type: split-before-after · MS · static · proof · energy 4 · AI risk high
- REAL FOOTAGE REQUIRED: before/after is evidence; film both states from one taped phone spot — do not generate
```
Shot 5b brings the face back as a reaction.

**AI prompt, shot 3a.**
- Before: `<persona>. Tight macro detail — product texture/label in frame… Any on-screen text is bold sans`, followed by the line in quotes.
- After:
  - `Extreme close-up, macro lens, very slow push-in across the texture of the electric milk frother, shallow depth of field… Product: … Vertical 9:16 phone footage. Single continuous shot, no scene cuts. One camera move only. No on-screen text…`
  - No persona text; the audio line reads `Maya says: Hormozi said it best…`.

## Results
**fast_eval (py3.9, --gate2).** 100% gate-1 and 100% e2e on every run:

| run | scripts |
|---|---|
| golden | 990 |
| holdout | 1,050 |
| 15/60 s | 660 |
| holdout 15/60 s | 700 |

**Self-test:** green on both 3.9 and 3.12 at every commit.

**`python3 -m vsp.shotplan`:** ok.
- 490 bundles pass gate 2 plus the §1.4/D157/D160 checks.
- Output is byte-identical across PYTHONHASHSEED values.
- `plan()` averages 2.6 ms.
- 24/24 synthetic-contract bundles pass, and 66/66 hook visual types are honoured at frame 0.
- An extra sweep (golden and holdout × 15/30/60 s × seeds 1–2, 4,080 bundles) is clean.

## Unmet / for other workstreams
- **Soft, not enforced:**
  - TikTok Shop: ≥3 s of continuous live action;
  - AI lane: at most 2 med-risk shots in a row, and low-risk shots ≥30% of runtime.
- **Left to the rubric:** vibe cadence band, product share, and 3 distinct scales per 15 s.
- **AI transformation** is not re-routed to demo (that is the maker's call). It carries about 7 real-footage shots.
- **Direction and discovery sections** were verified only against contract stubs, since those modules don't exist in this worktree yet.
- **WS-EVAL:** add `vsp.shotplan` to `OPTIONAL_SELFCHECKS`. `check_bundle()` is a reference implementation of D157 and D160.
- **Proposed vocab ids.** Until they exist, each is mapped to the nearest existing id:

  | proposed | used meanwhile |
  |---|---|
  | purpose `loop` | `cta` / `transition` |
  | move `punch-in` | `push-in` |
  | angles `selfie`, `mirror` | `eye-level` |
  | `AI_RISK`, `SHOT_NEEDS`, `LIGHT_PRESETS` | research values |
