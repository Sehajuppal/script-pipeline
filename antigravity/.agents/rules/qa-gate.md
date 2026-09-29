---
trigger: model_decision
description: QA gate for Gemini Omni clips and the assembled master. Apply when checking, judging, approving or rejecting a draft or final clip, choosing a take, deciding between an edit turn, a re-render and the ai_fallback, or checking the finished master before delivery.
---

# QA gate: every clip, every pass

A clip ships only when every check that applies to it passes. `shots[].qa` in `render.json` lists the check ids for each shot; `qa_gate[]` holds the thresholds. Run the cheap automatic checks first, then the judge.

## 1. Probe (automatic, free): `qa_probe.py`

`python3 .agents/skills/qa-judge/scripts/qa_probe.py --job jobs/<slug> --pass <draft|final> [--shot N] --stills`

| id | check | threshold | on fail |
|---|---|---|---|
| aspect | display aspect of the clip | 9:16 (0.5625) within 1% | re-render |
| fps | frame rate | 24 on Omni clips; 30 on the master | re-render (clip) / rebuild (master) |
| duration | clip length | >= `window_out_s` (master: `duration_s`) | re-render |
| audio_stream | an audio stream is present | 1 or more | re-render |
| letterbox | ffmpeg `cropdetect` bars | none over 8 px | re-render |
| scene_cuts | ffmpeg `select='gt(scene,0.4)'` inside one clip | 0 cuts | re-render (Omni cuts between shots by default) |
| dup_frames | short runs of repeated frames (the 8-12 fps wobble) | ratio <= 0.2 | re-render |

The script exits 0 when every check passes, 1 when one fails, and 3 when ffmpeg/ffprobe are missing ("skipped"): then say so in the report and run the judge on the clip itself.

## 2. Judge (Gemini on stills and the clip)

Extract first, middle and last stills (`--stills`) and give them, the clip and the references (presenter sheet, product photos) to Gemini with the prompt from `qa_probe.py --judge-prompt --shot N`. The rubric:

1. **identity**: the same presenter as the reference sheet (face, hair, glasses, skin, outfit).
2. **product**: matches the product photos (shape, colour, size, finish); no invented logo, brand name or label text.
3. **hands**: five fingers per hand, no fused or extra fingers, plausible grip and contact. Judge hands at the final resolution; drafts only catch gross errors.
4. **morphing**: no melting, warping, flicker or detaching parts; objects stay the same object.
5. **text**: no legible text, captions, subtitles, logos or watermarks anywhere in frame, except the real label photographed in a `label-detail-ecu` first frame.
6. **cuts**: one continuous shot, no scene cut, no jump, no second angle.
7. **safe box**: the key action inside x 120-888, y 288-1248 of the 1080x1920 frame (platform UI covers the rest).
8. **realism**: phone-footage look, natural skin texture, one plausible light source, no CGI sheen.
9. **action**: the planned action happens once, already in motion at the first frame.

Each item is scored 1-5 (5 flawless, 4 shippable, 3 or less fails), or null when it does not apply. Pass = every applicable item scores 4 or more. Answer format (JSON only): `{"identity", "product", "hands", "morphing", "text", "cuts", "safe_box", "realism", "action", "defects": [...], "verdict": "pass|edit|regenerate|fallback", "edit_instruction"}`.

## 3. Audio checks

- **no_speech** (B-roll): voice-activity detection finds no speech in the clip's own audio (under 0.3 s in total) and no music. Otherwise drop the native audio (use room tone) or re-render.
- **no_music**: no music in any clip or in the master. Music is added at upload.
- **lipsync_offset** (lip-sync shots, after the lip-sync pass): audio may lead the picture by at most 45 ms and lag it by at most 125 ms (ITU-R BT.1359); at 24 fps that is about one frame of lead. Otherwise re-run the pass.

## 4. Decide

| result | action |
|---|---|
| everything passes | ship the take; record it in `selects.json` if it is not the latest |
| one local defect (a colour, an object, a small artefact, a stray text patch) | an edit turn: `--edit "<fix>"` ("Keep everything else the same." is appended); at most 2 per clip |
| identity drift, bad hands, a cut, morphing, wrong framing, any probe failure | a new take (`--redo`) with the same inputs |
| 3 failed draft attempts, or 2 failed finals | `--use-fallback` (the shot's `ai_fallback`) |
| the fallback fails too | stop and ask the human; never ship a failing clip, never drop the beat |

Pick the best passing take by judge scores, not the first one that passes, while attempts and budget allow.

## 5. The master

`qa_probe.py --job jobs/<slug> --master`: 1080x1920, 30 fps, duration = `duration_s`, an audio stream, no letterbox. Also check: integrated loudness -14 LUFS (±1) and true peak at or under -1 dBTP (`ffmpeg -i master.mp4 -af ebur128=peak=true -f null -`), every beat present in order, no burned-in captions, and no music.

## 6. Log

`render_log.jsonl` already holds model id, seed, interaction id, cost and status per call. Add the QA verdict per shot (probe result, judge scores, decision) to `render_report.json`.
