---
name: omni-render
description: Renders the generated shots of a render.json with Gemini Omni (gemini-omni-1.1-flash) through the Interactions API, for draft (360p) and final (1080p) passes, edit turns and fallbacks, with budget, attempt and seed handling. Use when asked to validate a render job, render or re-render a shot, make a draft or final pass, fix a clip with an edit turn, or switch a shot to its fallback.
---

# omni-render

Script: `.agents/skills/omni-render/scripts/omni_render.py` (stdlib Python 3.9+). Key: `GEMINI_API_KEY` from the environment. Needs `read_url(generativelanguage.googleapis.com)`.

## Commands

```
python3 .agents/skills/omni-render/scripts/omni_render.py --job jobs/<slug> --validate
python3 .agents/skills/omni-render/scripts/omni_render.py --job jobs/<slug> --pass draft
python3 .agents/skills/omni-render/scripts/omni_render.py --job jobs/<slug> --pass draft --shot 3a --redo
python3 .agents/skills/omni-render/scripts/omni_render.py --job jobs/<slug> --shot 3a --edit "Make the glow warmer."
python3 .agents/skills/omni-render/scripts/omni_render.py --job jobs/<slug> --shot 3a --use-fallback
python3 .agents/skills/omni-render/scripts/omni_render.py --job jobs/<slug> --pass final
python3 .agents/skills/omni-render/scripts/omni_render.py --job jobs/<slug> --dry-run [--full]
```

| flag | meaning |
|---|---|
| `--validate` | pre-flight: prompts, tasks, durations, refs on disk, key, ffmpeg; prints clips, seconds, estimate, cap and the shots to film. Exit 1 on any ERROR. |
| `--pass draft\|final` | draft = 360p inline; final = 1080p with URI delivery (downloaded at once; Files are kept 48 h). |
| `--shot N` | only these shots (repeat or comma list). A `mode: real` shot is refused (exit 2). |
| `--redo` | another take of a shot that already has an ok clip for the pass. |
| `--edit TEXT` | an edit turn on the last ok take (`previous_interaction_id`, task `edit`); one `--shot`. |
| `--use-fallback` | render the shot's `ai_fallback` (prompt, task, inputs, duration from render.json); one `--shot`. |
| `--background` | send `background: true` and poll `GET /v1beta/interactions/{id}`. |
| `--dry-run` | print one request JSON line per call and exit; no network, no key. `--full` inlines the real base64. |
| `--force` / `--force-budget` | ignore `max_attempts` / the budget cap. Only with explicit human approval. |

## What it does

- Builds each body from render.json: images from `refs/<ref id>.<png|jpg|jpeg|webp|heic>` as base64 `data` + `mime_type`, one per distinct ref in `inputs[]` order, then the prompt text; `response_format {type video, aspect_ratio 9:16, resolution, duration "<n>s", delivery}`; `generation_config {video_config {task}, seed}`; `store: true`.
- Retries 429, 5xx and network errors with backoff (5, 15, 45, 90 s). When the API rejects `seed`, resends once without it and logs `seed_dropped`.
- Reads the video from `steps[]` → `model_output` → `content` `video` (`data` or `uri`); tolerates an SDK-style `output_video` field. A URI is polled on the Files API until ACTIVE and downloaded with the key.
- Writes `clips/shot-<n>-<pass>-a<attempt>.mp4` and appends to `render_log.jsonl`: `ts, shot, pass, attempt, variant (primary|edit|fallback), interaction_id, previous_interaction_id, model, seed, seed_dropped, resolution, task, duration_s, cost_usd_est, usage, status, error, file`.
- Skips shots that already have an ok clip for the pass (so a batch can resume), refuses a take past `passes.<pass>.max_attempts`, and refuses a call that would push the logged spend over `budget_usd.cap`.

## Rules

- Never generate a `mode: real` shot, never write a new prompt when render.json has one, never send brief text.
- Draft everything first and get human approval on the contact sheet and the draft cut before `--pass final`.
- A safety block is reported with its reason; do not rephrase to get around a filter.
- After each batch, read `spent so far` against the cap and report before you would cross it.
