---
name: vsp-produce
description: Produce a shoot-ready viral short-form script bundle for a product
version: 2.0.0
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
4. Deliver from `outdir`: `brief.md` (the video agent's prompt, includes the
   shot list), `script.json`, `captions.srt`, `shotlist.csv`. Post the
   caption from the bundle as-is. For feedback later, the caption carries
   (or add) the tag `#vsp-<first 8 chars of script_sha256>` from
   `manifest.json` → `script_summary.script_sha256`.
5. Want variants? Re-run with different `--seed` values; the pipeline already
   picks the best of 8 candidates per run (`--candidates N`).

## Pitfalls
- Exit 1 means a gate failed. Read `validation-report.md`; do not hand-edit
  the script to get past a gate. Report the failing rule id instead.
- `--script-json` validates a hand-finished script; it never repairs it.
- The bundle's DELIVERABLE block must reach the video agent verbatim.

## Verification
`status == "pass"`, exit code 0, and `validation-report.md` shows
`gate 1 (script): PASS` and `gate 2 (brief): PASS`.
