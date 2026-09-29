# WS-DISCOVERY notes (branch ws/discovery, pipeline v2.1)

Owns: maker caption region (`build_caption`, `CAPTION_TAGS`, `_scoped_tags` +
helpers, `_cta_word`, `NICHE_COMMENT_WORD`, beauty sub-category tags),
`vsp/discovery.py`, `vsp/data/discovery.json`.

## Commits (on d903c22)

| commit | what |
|---|---|
| e7563e5 | `vsp/data/discovery.json`: research JSON blocks transcribed verbatim (parsed from the doc) + ENGINE tables |
| 5536572 | keyword engine + maker caption region (keyword in line 1, tags, comment word, routine R14 echo) |
| d790249 | `build()`: keywords, placement, cover, 3 platform packages, posting, checklist, own D155 checker |
| d97c4a5 | head noun skips frame words ("no sugar challenge" -> sugar) |
| b028b6b | `render_md` + `render_problems` |
| ed15b85 | `selfcheck()` + CLI (`selfcheck`, `show`) |
| 0497cdc | keyword hardening (offers and marketing words never enter the keyword; accents; casing) |
| 3c2abb6 | legacy / `--script-json` scripts package cleanly without the maker |

## Keyword placement, golden matrix (33 prompts x 5 formats x 2 presenters, seed 1)

| slot | before (d903c22) | after |
|---|---|---|
| spoken by 3.0 s (head noun) | — | 329/330 (full keyword: 162/330) |
| on screen by 3.0 s (head noun) | — | 310/330 |
| caption line 1, first 60 chars | 162/330 | 330/330 |
| compact keyword hashtag | 10/330 | 330/330 |
| runs with an off-topic tag | 130/330 | 0 |

On the holdout set: 329/350, 298/350, 350/350 and 350/350. Rubric R14 failures on golden went from 30 to 0: the routine caption now echoes the bait's ROUTINE.

## Sample defects: before -> after

- **Milk frother** (demo, AI): `#organization #kitchentok #amazonfinds` -> `#milkfrother #coffeetok #latteathome`. Comment word stays FROTHER.
- **Silk pillowcase** (review, human):
  - Line 1: "The pillowcase after 7 days: buy or skip?" -> the same hook + "Silk pillowcase review: the full verdict."
  - Comment word: GLOW -> PILLOWCASE.
  - Tags: `#silkpillowcase` added.
- **Sugar 21** (pov-vlog, human):
  - Line 1: "21 days without sugar." -> the same + "No sugar challenge, day by day."
  - Tags: `#30daychallenge #selfimprovement` -> `#nosugarchallenge #21daychallenge #selfimprovement`.
- **One caption on every platform**: fixed. The three platforms now get different captions, with the same line 1 so the posts can still be matched back to the script.

## Example package: milk frother, AI presenter

- TikTok caption: "You're using the electric milk frother wrong. / What to check before buying a milk frother. / Comment FROTHER for the full link list 👇 / made with an AI persona / #milkfrother #coffeetok #latteathome"
  - `is_aigc=true`
  - Manage Keywords: milk frother, latte at home, cold foam
- Instagram caption: same line 1, then the alt-text substitute "An AI persona demonstrates a milk frother up close, from first use to the result.", then the same CTA, disclosure and tags.
  - `is_ai_generated=true`
  - Trial Reels protocol included
- YouTube Shorts:
  - Title: "Milk frother test: what to check before buying"
  - Description: keyword line + "Related: latte at home.", the disclosure, "Comment FROTHER for the full list.", Part 2 as the related video, `#milkfrother #coffeetok`
  - `containsSyntheticMedia=true`
- Cover: frame 21.9 s, text "MILK FROTHER TEST", safe box x120-888 y420-1248.

## Selfcheck

`python3 -m vsp.discovery selfcheck` is ok on Python 3.9 and 3.12 over 680 scripts:
- 0 D155 errors, 0 gate-1 errors, 0 `creative_warnings`
- the keyword is in caption line 1 on every script, and no off-topic tags
- R14 and the `render_md` contract hold
- deterministic, including child processes with `PYTHONHASHSEED` 0 and 4242
- `build()` averages about 0.5 ms (max under 3 ms)

The selfcheck caught 7 of 7 deliberately injected defects. Beyond the selfcheck:
- self-test is green on both Pythons
- `fast_eval --gate2` is at 100% gate-1 and e2e on golden and holdout
- appending `render_md` to 680 real bundles adds no gate-2 failures

## Not met / notes

- **Comment words fixed in `build_beats`** (outside my region): the challenge word DAY1 is kept, and the caption echoes it. The advice word (HOOKS) and routine word (ROUTINE) are already keyword words.
- **"Keyword sentence as line 2"**: line 1 must carry the keyword, so the sentence joins line 1 after the hook, or goes before it when the hook is too long. TikTok's line 2 is a search-intent sentence.
- **Spoken and on-screen placement belong to the hook region (WS-HOOKS)**. The full keyword is spoken by 3 s in only 49% of runs. Most on-screen misses are the transformation format's "DAY 1 | DAY 7" frame-0 label.
- **D158 is not in `vsp.lexicon` yet**: my own patterns are used, and a registered D158 rule is picked up automatically. The D155 gate itself is WS-EVAL's; they can use `vsp.discovery.check()`.
- **Secondary keywords**: the current research pack has no `top_reels`, and its fresh lines don't match these niches, so secondary keywords come from the topic table (recorded in `keyword_sources`).
- **Integrator**: write `posting.md` from `render_md` and add `primary_keyword` to the manifest.
