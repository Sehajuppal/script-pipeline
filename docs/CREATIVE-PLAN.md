# Pipeline v2.1 — creative layer plan (2026-09-29)

Goal: every bundle recommends **the shots**, **the vibe and tone**, **the best
hooks with tested alternates**, and **discovery packaging** — compliant,
measured, and learning from posted performance.

Evidence: `docs/research/shots-cinematography.md`, `vibe-tone-music.md`,
`hooks-deep-dive.md`, `discovery-seo.md` (JSON tables inside each are meant
to be transcribed into code). Shared ids: `vsp/creative_vocab.py` (add ids,
never rename or remove).

## 0. Principles

1. **Additive and optional.** New script keys are added by
   `vsp/creative.enrich()` at the end of `viral_script_maker.generate()`.
   A module that is absent adds nothing (v2.0 output byte-identical).
2. **Gates validate what is present; the rubric scores presence + quality.**
   A new gate rule is silent when its key is absent, so legacy fixtures and
   `--script-json` inputs keep their exact outcomes. The rubric penalises
   missing creative keys.
3. **Never weaken a gate.** Never edit the DELIVERABLE block. No invented
   prices, proof, offers, or guarantees; an AI presenter never claims lived
   experience; every AI post carries its disclosure.
4. **Deterministic.** Given (prompt, seed, research pack, priors), output is
   byte-identical across runs, processes and `PYTHONHASHSEED`. Modules derive
   their own RNG with `vsp.seeding.derive_seed(seed, "<module>")` and never
   consume the maker's rng. No set iteration in outputs.
5. **Fast.** Each module adds ≤ 20 ms per script (it runs for all 8
   candidates). No network; the optional LLM layer (`vsp.llm.complete_json`)
   is off unless configured and never required.
6. **AI-rendered proof is not proof.** When the presenter is an AI persona the
   video is generated; any shot that *proves* a result (test result,
   before/after, measurement, durability) must be real footage (hybrid lane)
   or the claim must not be made. (shots-cinematography §4.5)

## 1. Contracts

### 1.1 `script["direction"]` — `vsp.direction.direct(script, ctx=None, seed=None, maker=None) -> dict | None`

```json
{
 "schema_version": 1,
 "vibe": "<VIBES id>", "vibe_reason": "…", "secondary_vibe": "<VIBES id> | null",
 "tone": {"voice": "<TONES id>", "allowed": ["<TONES id>"], "humor": "none|light|high", "notes": "…"},
 "energy": 3,
 "pacing": {"target_wpm": [155, 180], "avg_shot_s": [1.8, 3.0], "cuts_per_10s": [3, 5],
            "max_static_s": 3.5, "pattern_interrupt_s": 4.0},
 "energy_curve": [{"t": "0.0–0.5s", "type": "VISUAL TRIGGER", "energy": 5}],
 "music": {"moods": ["…"], "bpm": [100, 120], "genres": ["…"], "vo_ducking_db": -12,
           "sfx": ["…"], "in_master": false, "search_queries": ["…", "…", "…"],
           "licensing": {"tiktok": {"library": "…", "note": "…"},
                         "instagram": {"library": "…", "note": "…"},
                         "youtube_shorts": {"library": "…", "note": "…"}}},
 "look": {"lighting": "…", "palette_names": ["…"], "palette_hex": ["#RRGGBB"], "grade": "…",
          "set": "…", "wardrobe": "…"},
 "camera": {"style": "…", "lens": "…", "movement": ["<CAMERA_MOVES id>"]},
 "text_style": {"case": "…", "weight": "…", "max_words_per_card": 3, "placement": "…"},
 "transitions": ["…"],
 "showmanship": "one device (vibe-tone-music §2.2)",
 "voice": {"presenter": "ai|human", "spec": "…"},
 "do": ["…"], "dont": ["…"],
 "evidence": [{"claim": "…", "grade": "P|S|M|A", "source": "…"}]
}
```
- `energy_curve`: one entry per hook_stack + beats item, script order.
- Pacing never asks for speech slower than the beat was sized for. The maker
  sizes windows at 3.0 words/s, or 2.5 when the beat's delivery says "slow
  down" / "unhurried" / "never rushed". `target_wpm` stays within 140–200.
- `music.in_master` is false: music is added at upload from the platform's
  commercial library (TikTok CML, Meta Sound Collection, YouTube Audio
  Library). Never name a commercial track. No AI music on TikTok commercial
  content.
- AI presenter: `voice.spec` = a natural-prosody synthetic voice, disclosed,
  never claiming to be human.

Also exported: `render_md(direction) -> str`, which must start with the heading
`## CREATIVE DIRECTION — vibe & tone`; `style_paragraph(direction) -> str`,
which replaces the bundle's `## STYLE` body; and `voice_spec(direction) -> str`,
which replaces the VOICEOVER "Voice spec:" sentence.

### 1.2 `script["hook_variants"]` — `vsp.hooks.variants(script, ctx=None, seed=None, maker=None) -> list | None`

```json
[{"id": "A", "is_primary": true, "archetype": "<HOOK_ARCHETYPES id>", "family": "<HOOKS family>",
  "verbal": "≤8 words", "overlay": "≤3 words", "visual_type": "<VISUAL_TYPES id>",
  "visual": "Frame 0: …", "audio": "…", "caption_line": "…",
  "score": 0.82, "features": {"<feature id>": 0.0}, "reasons": ["…"]}]
```
Hard rules (gate D154, silent when the key is absent):
- 3–5 variants with unique ids A, B, C…. Exactly one `is_primary`: variant A.
  Its `verbal` equals the script's VERBAL HOOK dialogue and its `overlay`
  equals the VISUAL TRIGGER on_screen.
- `visual_type` values are all distinct. The first three words of `verbal`
  differ between variants. At least 3 distinct archetypes when there are
  4 or more variants.
- Every variant passes the same screens as the primary hook:
  - ≤8 whitespace tokens; no `{`/`}`.
  - The overlay is ≤3 words and `lexicon.overlay_is_clean(overlay, verbal)`.
  - D37 (price only if the prompt has one); D136 (SOCIAL_PROOF vs prompt);
    D139 (GENERIC_BAIT); D141 (ABSOLUTE vs prompt); D158 (offer/urgency vs
    prompt).
  - For an AI presenter: D137 (AI_FIRST_PERSON) and no `human_only`
    archetype.
  - `requires_price` / `requires_proof` / `requires_offer` archetypes appear
    only when the prompt supplies that input.
- Every variant's promise is paid by the script's payoff (D35/D5), so the
  archetype must be compatible with the payoff type of the format and concept.

Also exported: `score_hook(verbal, overlay, visual_type, script, ctx=None) ->
(score, features, reasons)` and `render_md(variants, script) -> str` (the
content of hooks.md: a variant table plus the test protocol, as in
hooks-deep-dive VARIANT_POLICY).

### 1.3 `script["discovery"]` — `vsp.discovery.build(script, ctx=None, seed=None, maker=None) -> dict | None`

```json
{"schema_version": 1,
 "primary_keyword": "milk frother", "secondary_keywords": ["latte at home"],
 "search_intents": ["is a milk frother worth it"],
 "placement": {"spoken_by_s": 3.0, "on_screen_by_s": 0.5, "caption_first_60": true,
               "hashtag": "#milkfrother", "cover_text": true},
 "comment_word": "FROTHER",
 "cover": {"frame_s": 21.9, "text": "≤5 words", "safe_box": "x120-888 y420-1248", "why": "…"},
 "platforms": {
  "tiktok": {"caption": "…", "hashtags": ["#…"], "keywords_to_suggest": ["…"],
             "toggles": {"is_aigc": true}, "notes": ["…"]},
  "instagram": {"caption": "…", "hashtags": ["#…"], "description_line": "…",
                "toggles": {"is_ai_generated": true}, "trial_reels": {"recommended": true, "protocol": "…"},
                "notes": ["…"]},
  "youtube_shorts": {"title": "≤100 chars", "description": "≤5000 bytes", "hashtags": ["#…"],
                     "related_video": "…|null", "toggles": {"containsSyntheticMedia": true},
                     "notes": ["…"]}},
 "posting": [{"item": "…", "grade": "P|S|M|A|myth", "source": "…"}],
 "checklist": ["…"]}
```
Hard rules (gate D155, silent when the key is absent):
- Hashtags: TikTok ≤5, Instagram ≤5, YouTube ≤15, and never generic-only
  (D140).
- YouTube title ≤100 chars with no `<` or `>`. YouTube description ≤5,000
  UTF-8 bytes.
- Every platform caption, title and description passes D37, D136, D139, D141
  and D158.
- Each keeps the script caption's single CTA destination (D46 link groups).
- Each carries the AI disclosure line when presenter=ai
  (`lexicon.has_ai_disclosure_line`).
- The primary keyword appears in the first line of each platform caption, and
  in the YouTube title.

Also exported: `render_md(discovery, script) -> str`, which must start with
`## POSTING & DISCOVERY` (it becomes posting.md and a bundle section), and
`keywords_for(script, ctx=None, pack=None) -> (primary, secondary, intents)`.

### 1.4 Shots — `make_shotlist.build_shots` / `vsp/shotplan.py` / shots.json

New keys per shot:

| key | value |
|---|---|
| `shot_type` | SHOT_LIBRARY id |
| `scale` | SHOT_SCALES id |
| `angle` | SHOT_ANGLES id |
| `move` | CAMERA_MOVES id |
| `purpose` | SHOT_PURPOSES id |
| `energy` | 1–5 |
| `needs` | list |
| `ai_risk` | low / med / high |
| `ai_fallback` | id or null |
| `real_footage` | bool: a proof shot that must be filmed |
| `setup` | int, the shooting group |
| `broll` | list |
| `sfx` | str |

Bundle contract. Legacy headings and lines stay unchanged, including
`### Shot N (s–es) — BEAT` and `- Camera:` lines, and the DELIVERABLE text is
verbatim.
- Each `### Shot` block gains one line, written exactly as
  `- Shot type: <shot_type> · <scale> · <move> · <purpose> · energy <n> · AI risk <risk>`.
  A proof shot in an AI-presenter bundle adds
  `- REAL FOOTAGE REQUIRED: <why> — do not generate`.
- New sections, headings exact:
  - `## CREATIVE DIRECTION — vibe & tone`, right after `## STYLE`
    (`vsp.direction.render_md`)
  - `## ALTERNATE OPENINGS — variant cuts`, after `## SHOT PROMPTS` and before
    `## VOICEOVER`. One `#### Alt opening <ID> (0.0–3.0s) — <archetype> /
    <visual_type>` block per non-primary variant. Each is rendered as its own
    ≤3 s clip after the master's last shot, with the same identity lock.
  - `## SHOOT PLAN — setups, props, B-roll`, after ALTERNATE OPENINGS
  - `## POSTING & DISCOVERY`, just before `## Caption + hashtags (post as-is)`
    (`vsp.discovery.render_md`)
- New sections never contain a `### Shot` heading or any
  `creative_vocab.BUNDLE_FORBIDDEN` phrase.
- AI prompt hygiene (D160):
  - on-screen text is an edit overlay, never generated in-frame;
  - no quoted dialogue in visual prompts (use `says:`);
  - the identity lock appears only in shots that show the presenter.
- The loop ending (last shot returns to frame 0) is required when
  duration ≤ 15 s.
- `shotlist.csv` appends these columns: shot_type, scale, move, purpose,
  energy, ai_risk, real_footage, setup.

### 1.5 Priors v2 and feedback

`vsp/priors.py` (done) reads schema v2:
`"sections": {"archetype"|"visual_type"|"vibe"|"tone": {"by_niche": {niche: {key: {alpha, beta, n}}}, "global": {…}}}`
through `posterior_for(priors, section, niche, key)` and `mean_for(...)`.
`vsp.feedback learn` writes these sections from posts linked to a script and
to a variant. Consumers may use `mean_for` only as a tie-break after quality,
and only when n ≥ 3.

A post is linked to its variant by caption fingerprint: the posted caption's
first line is matched against the script caption's first line and each
variant's `caption_line`. The `#vsp-<sha8><variant letter>` tag remains
optional.

### 1.6 Manifest (integrator)

`script_summary` adds: vibe, tone, hook_archetype, visual_type, variant_ids,
primary_keyword.

## 2. New rules (RULES.md §68, written by the evaluator)

| id | rule | where |
|---|---|---|
| D154 | hook-variant integrity (§1.2) | gate 1 |
| D155 | discovery packaging integrity (§1.3) | gate 1 |
| D156 | direction integrity: valid ids; pacing 140–200 wpm; max_static_s ≤ 3.5; music not in master with per-platform licensing; AI voice spec disclosed | gate 1 |
| D157 | shot-plan integrity: every shot typed; frame 0 shows product/result (or subject/problem); a human (face or hands) by 3.0 s; ≤2 consecutive same-scale shots; typed moves for >3.5 s unsplit shots; AI-presenter proof shots marked real footage; loop at ≤15 s | gate 2 (parses `- Shot type:` lines) |
| D158 | no fake urgency, scarcity or offers (limited time, only N left, sale ends, % off) unless the prompt supplies the offer | gate 1 + lexicon |
| D159 | music licensing lane stated in the brief; no commercial track names; no AI music on TikTok commercial content | gate 2 |
| D160 | AI render-prompt hygiene (§1.4) | gate 2 |
| D161 | discovery keyword placement: spoken or on screen by 3.0 s, in the first 60 chars of caption line 1, and in one hashtag | rubric |

## 3. Workstreams (parallel, isolated worktrees under /projects/wt)

| agent | branch | owns |
|---|---|---|
| WS-VIBE | ws/vibe | `vsp/direction.py`, `vsp/data/vibes.json` |
| WS-SHOTS | ws/shots | `make_shotlist.py`, `vsp/shotplan.py`, `vsp/data/shot_library.json`, `vsp/exporters.py` |
| WS-HOOKS | ws/hooks | maker hook region (HOOKS, hook tables, `_hook_candidates`, `pick_hook`, `overlay_truncate`, `_render_hook_line`), `vsp/hooks.py`, `vsp/research.py` family map |
| WS-DISCOVERY | ws/discovery | maker caption region (`build_caption`, `CAPTION_TAGS`, `_scoped_tags`, `_cta_word`, `NICHE_COMMENT_WORD`, beauty sub-cat tags), `vsp/discovery.py` |
| WS-LEARN | ws/learn | `vsp/feedback.py`, `vsp/ingest/db.py` (additive migration), `learned/README.md` |
| WS-EVAL | ws/eval | `vsp/rubric.py`, `vsp/rules.py`, `vsp/lexicon.py`, `vsp/selftest*.py`, `vsp/schema.py` + `schema/`, `vsp/creative_eval.py`, `evals/scorecard.py`, `RULES.md` §68 |
| integrator | kiro/pipeline-v2 | `pipeline.py` (exports: direction.md, hooks.md, posting.md; manifest fields), `vsp/creative.py`, docs, agent skills |
