---
trigger: glob
globs: "**/voice_plan.json"
---

# Cartesia voice rules

`voice_plan.json` holds one entry per spoken line (dialogue and rehook, timeline order) with its `transcript`, `window`, `anchor`, `wpm` and `generation_config`. `cartesia_vo.py` sends them; these rules explain what it does and what you must never change.

## The request (one per line)

`POST https://api.cartesia.ai/tts/sse` with `Authorization: Bearer $CARTESIA_API_KEY`, `Cartesia-Version: 2026-08-14`, `Content-Type: application/json`.

```json
{"model_id": "sonic-3.6-2026-08-27", "transcript": "Follow, comment lamp for the link list.",
 "voice": "<voice id>", "locale": "en-US", "normalization": "auto",
 "output_format": {"container": "raw", "encoding": "pcm_s16le", "sample_rate": 48000},
 "add_timestamps": true,
 "generation_config": {"speed": 1.0, "volume": 1.05, "emotion": "confident"}}
```

- The stream sends `data: <json>` frames: `chunk` (base64 PCM in `data`), `timestamps` (`word_timestamps {words[], start[], end[]}` in seconds), `done`, `error`. Concatenate every chunk and every timestamps event in order.
- Pin the dated snapshot `sonic-3.6-2026-08-27`; never `sonic-preview` or `sonic-latest`. Set `locale` or `language`, never both.
- One voice, one model and one output format for every line of a video. Takes are not repeatable (there is no seed): keep the accepted WAVs, not just the requests.

## Controls

- `generation_config`: `speed` 0.6-1.5 (house range 0.9-1.15), `volume` 0.5-2.0 (house range 0.9-1.2), `emotion` from the 58-value enum. They are guidance, not exact multipliers. Cartesia advises leaving prosody alone for a well-punctuated line; the plan sets speed only to reach the target wpm and volume only to follow the energy curve (payoff loudest at 1.15, the line after it back to 1.0).
- `emotion` only on a voice with the Emotive tag. The six primary emotions (neutral, calm, angry, content, sad, scared) are the most reliable; for others the plan gives `emotion_fallback`. For any other voice run `cartesia_vo.py --no-emotion`. Proof, price and guarantee lines stay neutral.
- Inline tags exist (`<speed ratio="1.1"/>`, `<volume ratio="0.9"/>`, `<emotion value="calm"/>`, `<break time="400ms"/>`, `<spell>AB12</spell>`), but the plan uses none by default. At most one `<break>` of 200-600 ms inside a line, never next to `<spell>`, never at a line seam (breaks split the generation). **No nonverbal tags**: never `[laughter]` or any other bracket tag.

## Transcripts

- `display` is the caption text; `transcript` is what Cartesia hears. They differ only in casing, punctuation and normalisation-safe rewrites; the words are the same. Never change the words: a word change goes back to the pipeline, which re-captions.
- Hygiene already applied: the comment keyword in lower case ("comment lamp", not "LAMP", which is read letter by letter); initialisms kept in caps (LED); no emoji, arrows, "·", hashtags or parentheses; ranges written with "to"; numbers as written ("$25", "12%"); every line ends with ., ? or !.
- A brand name or a code that is misread gets a pronunciation dictionary entry (`pronunciation_dict_id` in the engine block) or `<spell>`, never a respelling in the transcript.

## Placement and timing

- Line mode: one request per line, placed on the master timeline by its anchor. Dialogue speech starts at the window start + 0.1 s; a rehook's speech ends at the window end - 0.1 s.
- Gaps: at least 0.3 s between lines, 0.5 s before the payoff and 0.4 s after it. A gap over 1 s gets room tone or SFX, never digital silence.
- Trim each clip to 40 ms before its first word and 80 ms after its last, and shift its word times by the same amount.
- `wpm.floor` is the beat's sizing: never read slower than it. Effective wpm = words / speech time x 60: fail above 200, warn above 190 or more than 10 under the floor.
- A line that overruns its window: first let the measured take decide; then raise speed once (1.15 at most); if it still overruns, send it back to the pipeline to cut words. Never time-stretch, never truncate audio.
- `words.json`: `{"words": [{"word", "start", "end"}], "duration_s"}` on the master timeline, sorted, each start clamped to the previous word's end.

## Voice choice and calibration

- `GET https://api.cartesia.ai/voices?language=en&gender=<feminine|masculine>&q=conversational&expand[]=preview_file_url`, then `q=casual|friendly|natural`. Drop any voice described as narrator, announcer, trailer, commercial or radio.
- Match the presenter's apparent age and gender; a mismatched face and voice reads as uncanny. Audition the plan's `audition_lines` (hook, payoff, CTA), 3 takes each; keep a voice that reads about 165-185 wpm at speed 1.0 without drifting in timbre.
- Lock one voice per persona for good (`CARTESIA_VOICE_ID` or `--voice-id`), then run `cartesia_vo.py --calibrate` once: it measures the wpm at speeds 0.9/1.0/1.1/1.2 into `vo/calibration.json`, and later runs interpolate each line's speed from it.

## Lanes

| | `ai_persona` | `creator_clone` | `real_voice` |
|---|---|---|---|
| voice | a licensed library voice (or a voice actor's licensed clone) | the creator's own IVC/PVC | the creator on the day |
| consent | licence for the voice | `consent_ref` plus approval of every first-person line | n/a |
| first-person claims | never ("I tried", "my skin" ...): the persona never used the product | only true and `creator_approved` | only true |
| engine | TTS per this file | TTS per this file | none: the plan is a read guide |
| disclosure | TikTok `is_aigc`, Instagram AI label, YouTube altered/synthetic, caption line, frame-0 label | TikTok and Instagram on; YouTube only if the visuals are AI | set by the visuals alone |
| TikTok Shop | no | no | yes |
| words.json | from Cartesia timestamps | from Cartesia timestamps | none (the caption stage aligns) |

- Never clone or imitate a real person's voice without their written consent (Cartesia's use policy, publicity-right laws). Never a sound-alike of a celebrity.
- Cartesia commercial use needs a Pro plan or higher.

## Mix

VO clips at one loudness, ±1-2 dB of clip gain for the energy curve (payoff loudest), matching room tone under the dry TTS, ambience about -12 dB, no music. Master at -14 LUFS integrated, true peak -1 dBTP, 48 kHz.
