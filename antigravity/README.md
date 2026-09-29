# Antigravity rules pack: Gemini Omni + Cartesia render agent

This folder is the "prompt for the render pipeline": the instructions, rules, skills and scripts a Google Antigravity agent needs to turn one pipeline bundle into a finished vertical video. **Gemini Omni** (`gemini-omni-1.1-flash`) renders the generated shots, **Cartesia Sonic** (`sonic-3.6-2026-08-27`) voices the lines, a lip-sync vendor (sync.so in the examples) fixes the to-camera mouths, and ffmpeg assembles the master.

The pipeline writes the machine-readable hand-off per run (`vsp/render.py`):

- `render.json`: every shot's mode (ai, real, edit, reuse), Omni task, clip length, windows, finished prompt, reference inputs, lip-sync plan, audio, QA checks and fallback, plus budget, seed, reference pack, disclosure and workflow.
- `voice_plan.json`: every spoken line's transcript, window, anchor, wpm and Cartesia settings, plus lane, voice choice and mix.
- `render.md`: a short human summary.

## Layout

```
AGENTS.md                                  always-on instructions (role, rules, production order)
.agents/rules/omni-prompting.md            glob: **/render.json, **/brief.md
.agents/rules/voice-cartesia.md            glob: **/voice_plan.json
.agents/rules/qa-gate.md                   model_decision: the QA gate
.agents/skills/omni-render/                SKILL.md + scripts/omni_render.py
.agents/skills/cartesia-voice/             SKILL.md + scripts/cartesia_vo.py
.agents/skills/lipsync-pass/               SKILL.md (vendor-agnostic procedure)
.agents/skills/qa-judge/                   SKILL.md + scripts/qa_probe.py
.agents/skills/assemble-master/            SKILL.md + scripts/assemble.py
examples/                                  generated hand-offs for the LED sunrise alarm lamp
```

Every script is stdlib Python 3.9+, has `--help`, and runs its `--dry-run` fully offline (no key, no network).

## Install

1. Copy `AGENTS.md` and `.agents/` into the root of the Antigravity workspace. If the workspace already has an `AGENTS.md`, keep this one in a subfolder instead (for example `render/AGENTS.md` with the jobs under `render/jobs/`): Antigravity loads rules walking up from the file being worked on.
2. Put each bundle in `jobs/<slug>/`: the whole pipeline run folder, at least `render.json`, `voice_plan.json`, `brief.md`, `hooks.md` and `posting.md`. For a run made before stage 9 writes these files, build them in the repo with `python3 -m vsp.render build outputs/<slug>` (it reads `script.json` and `shots.json`; `--voice-lane`, `--ai-broll`, `--consent-ref`, `--voice-id` as needed).
3. Add the reference pack under `jobs/<slug>/refs/` (see `render.json` `refs[]`: real product photos, the set plate, the frame-0 still; the agent generates the synthetic presenter sheet itself) and any filmed shots under `jobs/<slug>/real/shot-<n>.mp4`.
4. Ask the agent: "Render jobs/<slug>". It validates, voices, drafts, waits for your approval of the contact sheet and the draft cut, then finishes and reports.

## Environment

| variable | needed for |
|---|---|
| `GEMINI_API_KEY` | Omni (paid tier; the Interactions API) and the Gemini judge |
| `CARTESIA_API_KEY` | Cartesia TTS (a Pro plan or higher for commercial use) |
| `CARTESIA_VOICE_ID` | optional: the locked voice for this persona (else `--voice-id`, else the plan) |
| `SYNC_API_KEY` | the lip-sync vendor, when shots need a lip-sync pass |

Keys are read from the environment only. The Antigravity terminal sandbox blocks `.env` files, and the scripts never read them. How secrets reach the sandbox depends on your setup (for example your shell profile before launching Antigravity); check it once with `python3 .agents/skills/omni-render/scripts/omni_render.py --job jobs/<slug> --validate`.

## Sandbox permissions to allow

```
read_url(generativelanguage.googleapis.com)
read_url(api.cartesia.ai)
read_url(api.sync.so)
command(ffmpeg)
command(ffprobe)
command(python3 .agents/skills/omni-render/scripts/omni_render.py)
command(python3 .agents/skills/cartesia-voice/scripts/cartesia_vo.py)
command(python3 .agents/skills/qa-judge/scripts/qa_probe.py)
command(python3 .agents/skills/assemble-master/scripts/assemble.py)
```

`read_url(domain)` also opens sandbox egress to that domain. Deny rules win over allow rules.

## Cost notes

- **Omni** bills output seconds: $0.034/s at 360p (drafts), $0.101/s at 720p, $0.152/s at 1080p (finals, upscaled). A clip is 3-10 s, so each planned shot costs at least 3 s. `render.json` `budget_usd` gives the run's `draft`, `final`, `estimate` (one take each) and `cap` (every retry used); the script refuses a call past the cap. The AI-lane lamp example: 13 clips, 41 s generated, about $1.39 draft + $6.23 final = $7.62, cap $16.63. Image inputs add about $0.002 each.
- **Cartesia** bills about 1 credit per character per take (a 30 s VO is about 400-600 characters); failed requests are free. Calibration costs 12 short takes once per voice.
- **Lip-sync** (sync.so) is about $0.02-0.133 per second of video; `budget_usd.lipsync_max` gives the upper bound for the run.
- Human-lane jobs without AI B-roll generate nothing: the agent only lists what to film.

## Lanes in one line each

- **AI lane** (`presenter_mode "ai"`, voice `ai_persona`): Omni renders the synthetic presenter from a generated presenter sheet; proof shots stay real footage; every AI disclosure is on.
- **Human lane** (`presenter_mode "human"`, voice `real_voice`): the creator films every face and hands shot and records the voice; Omni renders faceless product B-roll only when the run sets `ai_broll`, which turns the AI toggles on.
- **Creator clone** (`voice_lane "creator_clone"`, needs `consent_ref`): the creator's own cloned voice on Cartesia, first-person lines approved one by one, to-camera takes lip-synced to it.

## Examples

`examples/ai/`, `examples/human/` and `examples/human-ai-broll/` hold `render.json`, `voice_plan.json` and `render.md` for the v2.1 sample bundle (LED sunrise alarm lamp): the AI lane regenerated with `presenter ai`, the human lane from the sample's own `script.json` + `shots.json`, and the same human run with AI B-roll. They are generated job data, not instructions (the AI-lane `render.json` is larger than a rules file may be; Antigravity never loads it as a rule).

## Try it offline

```
python3 .agents/skills/omni-render/scripts/omni_render.py --job examples/ai --validate --dry-run
python3 .agents/skills/omni-render/scripts/omni_render.py --job examples/ai --dry-run --shot 2
python3 .agents/skills/cartesia-voice/scripts/cartesia_vo.py --job examples/ai --dry-run
python3 .agents/skills/assemble-master/scripts/assemble.py --job examples/ai --dry-run
python3 .agents/skills/qa-judge/scripts/qa_probe.py --job examples/ai --judge-prompt --shot 2
```

(Run from this folder. `--validate` reports the missing reference photos, which is expected for the examples.)
