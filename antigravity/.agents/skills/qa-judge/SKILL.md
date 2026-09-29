---
name: qa-judge
description: Checks Gemini Omni clips and the assembled master against the render.json QA gate, first with ffprobe/ffmpeg probes (aspect, fps, duration, audio stream, letterbox, scene cuts, frame-rate wobble), then with a Gemini judge on extracted stills (identity, product, hands, morphing, text, cuts, safe box, realism). Use when asked to QA, check, judge, score, approve or reject a clip, a draft, a final or the master, or to extract stills for review.
---

# qa-judge

Script: `.agents/skills/qa-judge/scripts/qa_probe.py` (stdlib Python 3.9+, uses `ffprobe` and `ffmpeg` from PATH: allow `command(ffmpeg)` and `command(ffprobe)`). Thresholds and decisions: `.agents/rules/qa-gate.md`.

## Commands

```
python3 .agents/skills/qa-judge/scripts/qa_probe.py --job jobs/<slug> --pass draft --stills
python3 .agents/skills/qa-judge/scripts/qa_probe.py --job jobs/<slug> --pass final --shot 2,3a
python3 .agents/skills/qa-judge/scripts/qa_probe.py --job jobs/<slug> --master
python3 .agents/skills/qa-judge/scripts/qa_probe.py --clip some.mp4 --window-out 3.0 --fps 24
python3 .agents/skills/qa-judge/scripts/qa_probe.py --job jobs/<slug> --judge-prompt --shot 2
```

- Per file it prints one JSON report: `{"file", "shot", "checks": [{"id", "ok", "value", "threshold"}], "ok", "stills"}`.
- Exit 0 when every check passes, 1 when one fails, 3 when ffmpeg/ffprobe are missing (`"status": "skipped"`; report it and go on with the judge).
- `--stills` saves first, middle and last frames of the window to `clips/stills/`.

## Probe checks

aspect 9:16 within 1% · fps 24 (master 30) · duration >= `window_out_s` (master >= `duration_s`) · an audio stream · no letterbox bars over 8 px (cropdetect, symmetric bars only) · zero scene cuts at scene score > 0.4 (clips only) · duplicate-frame runs <= 0.2 of frames (clips only: the master duplicates frames by design) · master size 1080x1920.

## The judge

1. `--judge-prompt --shot N` prints the rubric filled in for that shot (presenter and product references, the planned action, which items apply).
2. Give Gemini the prompt, the three stills, the clip and the reference images (presenter sheet, product photos).
3. Read the JSON answer: every applicable item >= 4 passes; `verdict` is pass, edit (with `edit_instruction`), regenerate or fallback.
4. Record probe result, scores and decision per shot in `render_report.json`, then act on the decision table in the QA rules.

Judge hands and faces at the final resolution: a 360p draft only catches gross errors (extra limbs, wrong person, cuts, text).
