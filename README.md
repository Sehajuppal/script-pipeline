# Viral Script Maker

A research-grounded short-form script generator. Give it a basic prompt,
get a complete shoot-ready viral script back.

## For Antigravity / the pipeline

```sh
# AI persona demo (default)
python3 viral_script_maker.py 'a $12 LED sunrise alarm lamp'

# Human UGC talking-head, 45 seconds
python3 viral_script_maker.py 'why your hooks fail' --presenter human --format talking-head --duration 45

# Reproducible output (same seed = same script)
python3 viral_script_maker.py 'a $9 posture corrector' --seed 7

# Machine-readable JSON for the pipeline
python3 viral_script_maker.py 'a $15 mini projector' --json > script.json
```

> Quote prompts containing `$` prices in **single quotes** so the shell doesn't eat them.

Formats: `demo` · `talking-head` · `pov-vlog` · `transformation` · `review`
Presenters: `ai` (applies persona constraints) · `human` (UGC mode)

## What comes out

- Hook stack (visual 0–0.5s, verbal ≤8 words, lock by 3s)
- Timestamped beats: education → demo → payoff → comment-bait → CTA
- Re-hook line per beat (open loops, never repeated in one script)
- On-screen text cues (muted-viewer safe)
- Caption + hashtags
- Disclosure / delivery notes per presenter type
- Research notes citing the exact findings behind each choice

## Knowledge base

Combines three research programs:
- `viral-content-research-database` — 349 dissected reels, 19 hook formulas
- `neuro-ad-research-program/files/ugc-persuasion-dossier.md` — 66 VERIFIED persuasion findings
- `neuro-ad-research-program/files/ai-persona-persuasion-dossier.md` — ~144 graded persona findings

Rulebook: `RULES.md`. Generator: `viral_script_maker.py`.

## Live research bridge
`research_bridge.py` connects the maker to the research that never stops:
- the viral-content DB (`~/workspace/viral-research/viral.db`) — every reel the research agent dissects, ranked hook families + patterns, fresh hook lines per niche
- the UGC + AI-persona persuasion dossiers (VERIFIED findings only)
- the hooks mastery playbook

`python3 research_bridge.py --refresh` rebuilds `research_pack.json`; the maker loads it on every run (hook family follows the live per-niche ranking, scripts cite the pack date and fresh DB examples). A daily cron (`script-research-pack-refresh`, ~06:40 PDT) keeps it current. Pass `--no-research` for frozen-rulebook output.
