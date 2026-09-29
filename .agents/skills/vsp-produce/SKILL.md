---
name: vsp-produce
description: Produce a shoot-ready viral short-form script bundle for a product
version: 2.1.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [video, scripts, reels, tiktok]
    category: content
    requires_toolsets: [terminal]
    related_skills: [vsp-research, vsp-feedback]
---
# Produce a script bundle

## When to Use
The user wants a script, video brief or shot list for a product, a
challenge ("I quit sugar for 21 days"), a routine, a showcase ("things in my
kitchen that just make sense") or an advice topic.

## Procedure
1. Pick the presenter. Run the router first if unsure:
   `python3 -m vsp.router "<prompt>"` → read `recommended_presenter` and
   `lane_warnings`. AI personas suit utilitarian products; humans suit
   hedonic ones, challenges and routines (an AI cannot claim lived
   experience).
2. Generate:
   `python3 pipeline.py "<prompt>" --presenter ai|human --format demo|talking-head|pov-vlog|transformation|review --duration 30 --seed <N> --json`
   Quote prompts containing `$` in single quotes. Only include a price if the
   user gave one.
3. Read the JSON: `status`, `outdir`, `artifacts`, `warnings`.
4. Deliver from `outdir`:
   - `brief.md`: the video agent's prompt. It includes the shot list; every shot has a `- Shot type:` line.
   - `direction.md`: vibe, tone, pacing, music and look for the editor.
   - `hooks.md`: the alternate openings.
   - `posting.md`: keyword, per-platform caption, hashtags, YouTube title, cover and the AI-content toggles.
   - `script.json`, `captions.srt` and `shotlist.csv`.

   Summarise the stage-9 `creative:` line for the user (vibe, openings, keyword). Post the caption from `posting.md` for each platform. For feedback later, the caption carries (or you add) the tag `#vsp-<first 8 chars of script_sha256>` from `manifest.json` → `script_summary.script_sha256`.
5. Alternate openings (A/B). `hooks.md` lists 3–5 openings. A is the master's own. B, C… change only the first 3 seconds: frame-0 visual, card and spoken hook. Film each alternate's first 3 seconds and splice it onto the same body. Post the alternates as Trial Reels with the tag `#vsp-<sha8><letter>` (e.g. `#vsp-1a2b3c4dB`), then follow `vsp-feedback`.
6. Want more scripts? Re-run with different `--seed` values. The pipeline already picks the best of 8 candidates per run (`--candidates N`).

## Pitfalls
- Exit 1 means a gate failed. Read `validation-report.md`; do not hand-edit
  the script to get past a gate. Report the failing rule id instead.
- `--script-json` validates a hand-finished script; it never repairs it.
- The bundle's DELIVERABLE block must reach the video agent verbatim.
- Shots marked `REAL FOOTAGE REQUIRED` (AI presenter, proof shots) must be
  filmed, never generated. Music is added at upload from the platform's
  licensed library (`direction.md` lists it), never baked into the master.

## Verification
`status == "pass"`, exit code 0, and `validation-report.md` shows
`gate 1 (script): PASS` and `gate 2 (brief): PASS`; `artifacts` lists
`direction.md`, `hooks.md` and `posting.md` (absent only for a legacy
`--script-json` without creative keys).
