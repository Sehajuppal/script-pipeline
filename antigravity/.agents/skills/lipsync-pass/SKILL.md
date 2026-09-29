---
name: lipsync-pass
description: Re-syncs the mouth of a to-camera Gemini Omni clip (or a creator's filmed take in the creator_clone lane) to the matching Cartesia voiceover segment with a dedicated lip-sync model, then replaces the clip's audio. Use for every render.json shot with lipsync.required, when asked to lip-sync, fix mouth sync, dub a talking head, or match a presenter's lips to the VO.
---

# lipsync-pass

Omni cannot take an external audio track: a to-camera shot is rendered with Omni saying the line natively (`native-then-lipsync-pass`), then a lip-sync model re-times the mouth to the Cartesia audio. The vendor is your choice; sync.so is the worked example (`SYNC_API_KEY`, `read_url(api.sync.so)`).

## When

Only shots with `lipsync.required: true`, after their final clip is approved and after `<slug>-words.json` exists. Never on B-roll, never on a real person's face without `consent_ref` (the `creator_clone` lane uses `creator-take-then-lipsync-pass` on the creator's own filmed take).

## Inputs per shot

- The video: the selected final clip (`selects.json`, else the latest ok final in `render_log.jsonl`), or `real/shot-<n>.mp4` for a creator take.
- The audio segment: from `vo/<slug>-vo.wav`, cut from `lipsync.audio_in_s` to `lipsync.audio_out_s` on the master timeline. These are plan estimates: take the real bounds from `<slug>-words.json` (the first and last words of `lipsync.line_id` that fall inside the shot's window) and add 0.1 s of room tone at each end.
- Placement: the segment starts at clip time `lipsync.clip_in_s` (= `window_in_s` + the segment start - the shot's window start). Pad the audio with silence to the clip length so the pass keeps the whole clip.

```
ffmpeg -ss <in_s> -to <out_s> -i vo/<slug>-vo.wav -ac 1 -ar 48000 lipsync/shot-<n>-seg.wav
ffmpeg -i lipsync/shot-<n>-seg.wav -af "adelay=<clip_in_s * 1000>,apad" -t <gen_duration_s> lipsync/shot-<n>-audio.wav
```

## The pass (sync.so example)

1. Upload or host the clip and `shot-<n>-audio.wav` where the vendor can read them.
2. Request a lip-sync generation: video + audio, a model for close-ups (lipsync-2-pro for MCU and CU; sync-3 for extreme angles or 4K), output at the clip's own resolution. Check the vendor's current API docs for field names; send only what they document.
3. Poll until done and download to `lipsync/shot-<n>.mp4`.
4. Replace the audio: the lip-synced clip carries the Cartesia segment only. Omni's native voice is dropped (`native_audio: "drop"`); the assembler adds room tone under it.

## QA

- Offset: audio may lead by at most 45 ms and lag by at most 125 ms (ITU-R BT.1359); at 24 fps that is about one frame of lead. Check on plosives (p, b, m) at the start and end of the segment.
- Judge the mouth, teeth and chin at the final resolution: no smearing, no double lips, identity unchanged (compare with the presenter sheet).
- Failing takes: re-run the pass once with the segment re-cut from words.json; then report the shot. Never keep Omni's own voice as a stand-in: it is not the Cartesia voice and it drifts between shots.

Log every pass (vendor, model, job id, cost, verdict) in `render_report.json`.
