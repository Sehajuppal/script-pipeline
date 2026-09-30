---
name: assemble-master
description: Assembles the uncut 1080x1920 30 fps master from a render job with ffmpeg, trimming each clip to its planned window, conforming 24 to 30 fps by frame duplication, cropping (never letterboxing), concatenating in shot order and mixing VO, ambience and SFX to -14 LUFS / -1 dBTP with no music; also builds the 360p draft review cut and the contact sheet. Use when asked to assemble, edit together, conform, mix, master, export or deliver the video, or to make the draft cut or contact sheet for review.
---

# assemble-master

Script: `.agents/skills/assemble-master/scripts/assemble.py` (stdlib Python 3.9+, ffmpeg and ffprobe on PATH; ffmpeg 4.4 or newer for `amix normalize`).

## Commands

```
python3 .agents/skills/assemble-master/scripts/assemble.py --job jobs/<slug> --dry-run
python3 .agents/skills/assemble-master/scripts/assemble.py --job jobs/<slug> --pass draft --allow-placeholders
python3 .agents/skills/assemble-master/scripts/assemble.py --job jobs/<slug> --pass draft --contact-sheet
python3 .agents/skills/assemble-master/scripts/assemble.py --job jobs/<slug>
```

- Final (default): `deliverables/<slug>-master.mp4`, H.264 yuv420p 1080x1920 at 30 fps, AAC 48 kHz, `+faststart`, exactly `duration_s` long; copies `<slug>-words.json` next to it and writes `deliverables/assemble_report.json`.
- `--pass draft`: the same timeline from the 360p takes as `deliverables/<slug>-draft.mp4` at 540x960, for human review.
- `--contact-sheet`: the middle frame of every generated clip, 6 per row, `deliverables/contact_sheet.jpg`.
- `--allow-placeholders`: a grey slate for a shot that has no source yet (review cuts only; listed in the report). Without it a missing shot stops the build: never drop a beat.
- `--dry-run` prints every ffmpeg command and runs nothing.

## Sources per shot

`selects.json` wins; a lip-synced shot uses `lipsync/shot-<n>.mp4`; a generated shot the latest ok take of the pass in `render_log.jsonl` (trimmed from `window_in_s`); a filmed shot `real/shot-<n>.mp4` (from `in_s` in `real/shot-<n>.json`, else 0); an edit shot `edit/shot-<n>.mp4`, and a jump-cut punch-in falls back to a 1.3x crop of the previous take; a loop that was not generated reuses shot 1's source.

## The chain

1. Per shot: `-ss <in> -t <window length>`, `fps=30` (frame duplication; never `minterpolate` or any optical-flow filter), `scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920` (fill and crop, never pad), libx264 CRF 17.
2. Per shot audio: the clip's own sound at -12 dB when `native_audio` is `keep_ambience`, silence when `drop` (lip-synced shots) or when the clip has no audio.
3. Concatenate video and the ambience bed in shot order.
4. Mix the bed, `vo/<slug>-vo.wav` and the SFX (`sfx/track.wav`, or `sfx/shot-<n>.wav` delayed to each shot's start) with `amix normalize=0`, then two-pass `loudnorm=I=-14:TP=-1:LRA=11` (measure, then apply linearly).
5. Mux: the video stream copied, AAC 192 kbps, cut to `duration_s`.

## Rules

- The master is the full planned timeline: every beat at its planned length, in order. No trims beyond the windows, no tightening, no variant cuts, no captions, no overlays, no music. The full clips stay in `clips/` as handles for the editor.
- Probe the result with `qa_probe.py --master` and check loudness before delivery.
