# WS-RENDER notes: the Gemini Omni + Cartesia hand-off (v2.2, branch ws/render)

New files only: `vsp/render.py`, `antigravity/` (the Antigravity rules pack), this note. Nothing existing was edited; the integrator wires stage 9 and the self-test.

## What it produces

Per run, from `script.json` + the shot list, three files:

- `render.json`: the Omni shot plan;
- `voice_plan.json`: the Cartesia line plan;
- `render.md`: a short human summary, starting `## RENDER HANDOFF — Gemini Omni + Cartesia`.

Sources: `docs/research/video-generation-omni.md` §6 (+ OMNI_CAPS) and `docs/research/voice-cartesia.md` §7 (+ CARTESIA_CAPS). The request shapes and the `[# Sources …]` / `[# References …]` tag syntax were also checked against the live Omni guide and the Interactions and Cartesia SSE references (2026-09-29).

```
build_render(script, shots, slug=None, script_sha=None, voice_lane=None, ai_broll=False, consent_ref=None) -> dict
omni_prompt(shot, ctx) -> str                          # ctx = context(script, voice_lane, ai_broll)
build_voice_plan(script, shots=None, voice_lane=None, consent_ref=None, voice_id=None) -> dict
check_render(r, script) -> [str]        check_voice_plan(vp, script) -> [str]
render_md(r, vp) -> str                 build_all(script, shots, **kw) -> (r, vp)
write(outdir, script, shots, **kw) -> ["render.json", "voice_plan.json", "render.md"]
selfcheck() -> (ok, lines)
python3 -m vsp.render selfcheck | build <outdir> [--voice-lane L --ai-broll --consent-ref ID --voice-id ID] | check <outdir> | show <outdir>
```

`shots` may be the in-process list from `make_shotlist.build_shots` (s/e), the shots.json dict or its list (start_s/end_s), or None (built here). All three give byte-identical output; the selfcheck asserts it. Times are the shot list's rounded times, so render.json agrees with shots.json and the bundle headings.

## Lanes

| | presenter ai | presenter human (default) | human + `ai_broll=True` | `voice_lane="creator_clone"` |
|---|---|---|---|---|
| `presenter_mode` / `voice_lane` | ai / ai_persona | human / real_voice | human / real_voice | human / creator_clone (`consent_ref` required, else ValueError) |
| mode ai | every generatable shot | none | faceless product shots only | as its visual lane |
| mode real | `real_footage` proof shots, "Not generated" types | everything else | face/hands, proof, "Not generated" | as its visual lane |
| edit / reuse | Edit-only types / the loop-return frame (a reuse of shot 1, generated from the frame-0 still only when shot 1 is) | same | same | same |
| disclosure | all toggles on, D138 caption line, frame-0 label | all off | all on + "Some shots in this video are AI-generated." | TikTok + Instagram on; YouTube only with AI visuals |

A presenter/lane mismatch (ai with real_voice, human with ai_persona) or an unknown lane raises ValueError too.

## render.json

| field | content |
|---|---|
| `schema_version`, `slug`, `sha8`, `prompt`, `duration_s` | 1; slug as in the render spec; sha8 = first 8 hex of the script.json sha256 (stage 4 bytes; `script_sha256(script)` reproduces them in-process) |
| `presenter_mode`, `voice_lane`, `consent_ref`, `ai_broll` | the lane |
| `model` | `{id: gemini-omni-1.1-flash, api: gemini, endpoint, auth_header: x-goog-api-key, fallback: veo-3.1-fast-generate-preview}` |
| `format` | `{aspect_ratio 9:16, source_fps 24, master {1080, 1920, fps 30, conform}}` |
| `passes` | `draft {360p, max_attempts 3, delivery inline, store true}`, `final {1080p, max_attempts 2, delivery uri, store true}`, `edit_turns_max 2` |
| `budget_usd` | `generated_s`, `per_s`, `draft`, `final`, `estimate` (one take each), `cap` (draft x3 + final x2), `lipsync_max` (sync.so upper rate), `note` |
| `seed` | `int(sha8, 16) % 2147483647`, or null when nothing is generated |
| `identity` | `presenter_text` (the lock, verbatim), `synthetic`, `hands_text`, `product_text`, `setting`, `light` (one named source), `voice` |
| `refs[]` | `id, path (refs/<id>.png), kind (presenter, product, set, frame0), synthetic, source, how, prompt (image-model prompt where useful), required, used_by`. Ids: presenter_sheet (AI lane only), product_front, product_side, product_hero, label_photo, flatlay_photo, set_plate, frame0 |
| `audio` | `vo_source` (cartesia, creator, none), `vo_file`, `words_json` (`<slug>-words.json`, null for real_voice), `music: false`, `ambience[] {n, sound, native_audio}`, `mix` (-14 LUFS, -1 dBTP, ambience -12 dB, music duck -8 dB), `sync_tolerance_ms` |
| `counts` | per mode + generated, generated_s, lipsync |
| `shots[]` | below |
| `disclosure` | `ai_generated, synthid, c2pa_check, platform_toggles` (copied from discovery.platforms.*.toggles, forced to the lane with a note when they disagree), `caption_line, frame0_label, tiktok_shop, notes` |
| `deliverables` | `master <slug>-master.mp4, words, vo, clips_dir, report render_report.json` |
| `qa_gate[]` | 17 checks `{id, stage (probe, judge, audio, log), check, threshold, on_fail}` (research §6.7) |
| `workflow[]` | the 11 steps with commands; steps that do not apply to the lane carry `skip: true` |
| `trend` | null (for the integrator) |

`shots[]`, one per shot in shots.json order:

| field | content |
|---|---|
| `n, window [s, e], planned_s, beat, shot_type, scale, angle, move, purpose, needs, real_footage` | from the shot list |
| `mode` | ai, real, edit, reuse; `reuse_of` on the loop |
| `task` | image_to_video (frame 0, the loop, "Image-to-video from the real … photo" types), reference_to_video (presenter/product refs), text_to_video; null when not generated |
| `gen_duration_s` | `clamp(ceil(planned + 1), 3, 10)`; lip-sync `clamp(ceil(max(speech, planned) + 1), 3, 7)`, so the clip always covers the window |
| `window_in_s / window_out_s` | 0.5 / 0.5 + planned (generated shots) |
| `prompt`, `inputs [{tag, ref}]` | the §6.2 string; tags `<FIRST_FRAME>`, `<LAST_FRAME>`, `<IMAGE_REF_N>` |
| `dialogue` | only when `lipsync.required` (the Cartesia transcript form, so mouth shapes match) |
| `lipsync` | `{required, line_id, audio_in_s, audio_out_s, method (native-then-lipsync-pass, or creator-take-then-lipsync-pass for creator_clone takes), clip_in_s, speech_s, tone, delivery}` |
| `native_audio` | drop on lip-synced shots, else keep_ambience |
| `overlay_text, sfx, qa[], ai_fallback {shot_type, task, gen_duration_s, prompt, inputs}, human_instructions, real_footage_why, notes` | |

Lip-sync applies to the types whose library prompt carries `{name} says` (talking-head-mcu, talking-head-product-in-hand, selfie-walk-talk, mws-cta-to-camera, green-screen-explainer), when a VO line overlaps the shot by more than 0.25 s. A continuation shot (the line started on an earlier shot) says the rest of the line. Lines over 6 s or clips over 7 s are not lip-synced; they get a note and the ai_fallback.

## voice_plan.json

| field | content |
|---|---|
| `schema_version, run, slug, prompt, duration_s, presenter, lane, read_guide` | read_guide = real_voice |
| `engine` | `{provider cartesia, base_url, api_version 2026-08-14, endpoint /tts/sse, mode line, model_id sonic-3.6-2026-08-27, locale en-US, normalization auto, pronunciation_dict_id null, add_timestamps true, output_format raw/pcm_s16le/48000}`; null for real_voice |
| `voice` | `id, source (library, ivc, creator), emotive, gender, age, style, consent_ref, calibration_wpm {0.9..1.2}, speed_basis, selection {query, then, reject_if_description_has, match, emotive_shortlist, audition_lines, accept_wpm_at_1_0, takes_per_line, lock}` |
| `disclosure` | the §7.5 lane row |
| `mix`, `timing`, `qa` | -14 LUFS / -1 dBTP / duck -8 dB, room tone; anchor offset 0.1 s, gaps 0.3/0.5/0.4 s, trims 40/80 ms; wpm 200 fail / 190 warn / floor - 10 |
| `lines[]` | `id L1.., beat, role, window, anchor (start or end), place_s (estimate), display, transcript, tone, energy, wpm {floor, target, max}, speech_s_est, delivery, shots, fits, flags, emotion_fallback, generation_config {speed, volume, emotion}, gap_before_s, gap_after_s, first_person_claim, creator_approved (creator_clone only)` |
| `outputs`, `cost` | `<slug>-vo.wav`, `<slug>-words.json` (null for real_voice), `vo/`; about 1 credit per character |

Rules applied: target wpm = the floor on slow-key beats, else max(floor, tone band midpoint) capped at 190; speed interpolated from the voice calibration (uncalibrated: 175 wpm at 1.0), clamped to 0.9-1.15, snapped to 1.0 within ±0.05; volume by energy (1.15 on the payoff only; 1.0 right after it); emotion only for an Emotive voice (the ai_persona default); per-line tones follow the beat (hook confident, payoff excited when the vibe allows it, post-peak warm, rehooks curious, price and guarantee lines serious/neutral) within `direction.tone.allowed`. Hygiene: comment keyword lowered, initialisms kept, emoji, arrows, "·", hashtags and parentheses stripped, ranges with "to", terminal punctuation; `display` stays the caption.

## Wiring stage 9 (for the integrator)

```python
# pipeline.py, Run.stage_export, after write_creative_docs():
from vsp import render as vrender
try:
    names = vrender.write(self.outdir, self.script, self.shots,
                          script_sha=_sha256_file(os.path.join(self.outdir, "script.json")))
    probs = vrender.check_render(json.load(open(os.path.join(self.outdir, "render.json"))), self.script)
    self.warn("render", probs)
except ValueError as e:              # a lane/consent error: fail loudly
    self.crash(9, f"render hand-off: {e}"); self.stop(1, "stage 9 failed")
```

- Add `"render.json", "voice_plan.json", "render.md"` to `pipeline.ARTIFACTS`, so a failing run never leaves a stale hand-off.
- Add `"vsp.render"` to `OPTIONAL_SELFCHECKS` in `vsp/selftest_cases.py` (about 16 s, hermetic, temp dirs only).
- Optional CLI flags passed through to `write()`: `--voice-lane`, `--ai-broll`, `--consent-ref`, `--voice-id`.
- `trend` is null; fill it after `write()` if the trends workstream lands.

## Brief changes to make in make_shotlist.py (not edited here)

1. **B-roll prompts carry the line.** `AUDIO (voiceover for this shot …): The presenter says: …` sits under B-roll shots (sample 3a, 4a, 5a). Sent to Omni, the B-roll talks. Only to-camera shots should carry the says line; B-roll should say "No dialogue, no voiceover" and name its ambience. render.json does this already.
2. **Voice-spec lane text.** "Real voice, recorded on the day; no TTS" contradicts a Cartesia render. The spec should name the lane (ai_persona, creator_clone, real_voice) and, for TTS lanes, point to voice_plan.json.
3. **Render spec fps.** "1080x1920, 30fps" should add "Omni renders 24 fps: conform to 30 by frame duplication, never optical-flow interpolation" (or set 24 fps masters for Omni bundles).
4. **Palette in every prompt.** "Palette: electric blue, hot pink, acid lime, black" fights "soft warm bedside-lamp light". Move the palette to wardrobe/props or the grade; render.json leaves it out.
5. **The 10-item NEGATIVE PROMPT block and the whole-brief read.** Omni has no negative field; per-shot 2-4 negatives work better. The brief should say the SHOT PROMPTS are superseded by render.json for Omni.
6. **"Photorealistic AI woman" in persona identity locks.** The word "AI" may push Omni toward a synthetic look; disclosure belongs to the caption, the toggles and the frame-0 label. *Done at integration:* render.py drops "AI" before the person noun in every image and video prompt (`_omni_identity`: face shots, the presenter sheet, frame 0). `identity.presenter_text` and `personas.json` keep the lock verbatim (D160 parity, append-only registry). The render selfcheck asserts 0 AI-lane prompts still carry the word.
7. **Alternate openings "3 s or less".** Omni's floor is 3 s; say "one 3 s clip".
8. **Micro-shake vs F133.** direction drops "handheld" for AI personas (faked shake on an AI render). *Resolved for F133 at integration:*
   - AI-lane prompts get no "handheld with natural micro-shake" line.
   - A planned `handheld` move is written "slow dolly" in AI-lane prompts, and `speed-ramp` "fast push-in that slows sharply" (`MOVE_PROMPT_AI`). This covers shots, fallbacks and the frame-0 still.
   - Human-lane AI B-roll keeps the shake so it matches the phone footage.
   - Before the fix, 160 of 165 AI golden scripts still said "handheld" in an Omni prompt. The selfcheck now asserts 0.
   - A handheld *product* ("a handheld milk frother") is not a camera move and stays.

## Known unknowns

- `generation_config.seed` on Omni: sent; resent once without it on a 400 that names the seed (tested with a stub).
- 9:16 pixel sizes per resolution and the default duration are undocumented; the probe checks aspect within 1%, not pixels. The assembler scales and crops to 1080x1920 whatever arrives.
- Audio input: not in the API (native-then-lipsync path). When audio references ship, lip-sync shots could send the Cartesia segment directly.
- Lip-sync vendor: sync.so is the worked example; its field names are left to its live docs (the skill is vendor-agnostic).
- Edit turns: `response_format` without `duration` is our assumption; a 1080p edit of an approved 360p take (vs a re-render) is untested.
- Background runs: status names polled as completed/failed/cancelled; `--background` is optional.
- Files API URIs: polled for `state: ACTIVE`, then downloaded with `alt=media`.
- C2PA on Gemini API MP4s, quotas and p50/p95 latency: unknown.
- Cartesia: whether `generation_config` or inline tags win, and whether timestamps include punctuation tokens. The script concatenates events and clamps starts.

## Checks run

- `python3.9 -m vsp.render selfcheck` and `python3.12 -m vsp.render selfcheck`: ok, about 16 s each. It covers 410 scripts (33 golden x 5 formats x 2 presenters at 30 s, plus 4 prompts at 15 and 60 s) with check_render + check_voice_plan clean, and the shots.json route identical. It also checks: the lane assertions; ai_broll and creator_clone variants; determinism (in-process and in PYTHONHASHSEED 0/4242 children); unit checks; every pack script's `--help` and dry runs (request shapes validated); the real_voice refusal; and stubbed Omni (seed retry, 429 backoff) and Cartesia (placed VO, words.json) runs.
- A real ffmpeg 7.0 run of the scripts, done outside the repo:
  - `qa_probe.py` catches letterbox bars, a hard cut and 12/8 fps wobble, and passes a static shot;
  - `assemble.py` builds a 1080x1920 30 fps master at -14.0 LUFS integrated, plus a contact sheet.
- No crashes on the 113 self-test fixture scripts. The malformed ones are flagged by the timeline checks, as intended.
- The example `render.json` files are generated job data (AI lane about 59 KB). The 24 KB limit applies to Antigravity rules; AGENTS.md is 15 KB.
