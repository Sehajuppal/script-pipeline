---
name: cartesia-voice
description: Voices a voice_plan.json with Cartesia Sonic (sonic-3.6-2026-08-27) over SSE, one request per line, and builds the placed 48 kHz VO track and the words.json word timings; also calibrates a voice's speed-to-wpm curve and prints the read guide for real-voice jobs. Use when asked to make the voiceover, TTS, word timestamps or words.json, to re-voice one line, to pick or calibrate a Cartesia voice, or to check VO pacing.
---

# cartesia-voice

Script: `.agents/skills/cartesia-voice/scripts/cartesia_vo.py` (stdlib Python 3.9+). Keys: `CARTESIA_API_KEY`, optional `CARTESIA_VOICE_ID`, from the environment. Needs `read_url(api.cartesia.ai)`.

## Commands

```
python3 .agents/skills/cartesia-voice/scripts/cartesia_vo.py --job jobs/<slug> --dry-run
python3 .agents/skills/cartesia-voice/scripts/cartesia_vo.py --job jobs/<slug> --voice-id <id> --calibrate
python3 .agents/skills/cartesia-voice/scripts/cartesia_vo.py --job jobs/<slug> --voice-id <id>
python3 .agents/skills/cartesia-voice/scripts/cartesia_vo.py --job jobs/<slug> --line L6
python3 .agents/skills/cartesia-voice/scripts/cartesia_vo.py --job jobs/<slug> --no-emotion
```

| flag | meaning |
|---|---|
| `--voice-id` | the voice (else `CARTESIA_VOICE_ID`, else `voice.id` in the plan). Without one the script stops and prints the selection query. |
| `--line L1,L6` | re-voice only these lines (WAV + events). Run once without `--line` to place and mix everything. |
| `--calibrate` | the plan's 3 audition lines at speeds 0.9/1.0/1.1/1.2 (12 requests) → `vo/calibration.json`; later runs interpolate each line's speed from it. |
| `--no-emotion` | drop `emotion` (for voices without the Emotive tag). |
| `--dry-run` | print one request JSON line per call; no network, no key. |

## Outputs

- `vo/<id>.wav` (48 kHz mono, trimmed to 40 ms before the first word and 80 ms after the last) and `vo/<id>.events.json` (the timestamp events).
- `vo/<slug>-vo.wav`: the whole timeline, each line placed by its anchor (dialogue speech at window start + 0.1 s, a rehook ending at window end - 0.1 s), never closer than the plan's gap to the previous line.
- `<slug>-words.json`: `{"words": [{"word", "start", "end"}], "duration_s"}` on the master timeline (research §4.4 order and clamping).
- `vo/voice_report.json`: per line `audio_file, placed_s, speech_s, effective_wpm, speed, qa`.

Exit 0 ok, 1 when a line fails QA (over 200 wpm) or the API, 2 usage, 3 refused (the `real_voice` lane, or `creator_clone` without `consent_ref`).

## Rules

- Voice first: make the VO before any final video, because the lip-sync pass and the windows depend on it.
- Never edit a transcript's words; a wording problem goes back to the pipeline. Casing, punctuation and pronunciation dictionaries are fine.
- Keep one voice and one model snapshot for every line, and keep the accepted WAVs: Cartesia has no seed.
- A line more than 0.3 s past its window: re-voice it once; if it still overruns, report it for a word cut. Never time-stretch.
- In the `real_voice` lane the script prints the read guide (window, target and floor wpm, tone, delivery per line) for the creator and exits 3; there is no words.json.
- Rules and lanes: `.agents/rules/voice-cartesia.md`.
