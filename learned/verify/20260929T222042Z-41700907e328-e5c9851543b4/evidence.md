# verify — REJECT

- base `4170090` (worktree 41700907e328) · cand `HEAD` (worktree e5c9851543b4)
- budget small (seeds 1); yardstick = the base tree's scorecard, rubric and suites; engine `e5c9851`
- self-test green (3.9.25 rc 0, 3.12.14 rc 0)

## Checks

| check | ok | detail |
|---|---|---|
| golden:R1-e2e | ✅ | e2e flips 0 up / 0 down, McNemar p=1 |
| golden:R2-shippable | ✅ | shippable flips 0 up / 0 down, McNemar p=1 |
| golden:R3-rubric-ci | ✅ | rubric Δ +0.00 [95% CI +0.00, +0.00] (floor -0.5) |
| golden:R4-audit | ✅ | audit-only mean 95.8 → 95.8 (max drop 0.5) |
| golden:R6-compliance | ✅ | candidate compliance flags: 0 |
| golden:R8-coverage | ✅ | 330 paired runs, 0 base cases missing in cand |
| holdout:R1-e2e | ✅ | e2e flips 0 up / 0 down, McNemar p=1 |
| holdout:R2-shippable | ✅ | shippable flips 0 up / 0 down, McNemar p=1 |
| holdout:R3-rubric-ci | ✅ | rubric Δ +0.00 [95% CI +0.00, +0.00] (floor -0.5) |
| holdout:R4-audit | ✅ | audit-only mean 94.1 → 94.1 (max drop 0.5) |
| holdout:R6-compliance | ✅ | candidate compliance flags: 0 |
| holdout:R8-coverage | ✅ | 350 paired runs, 0 base cases missing in cand |
| holdout:R5-not-lower | ✅ | holdout e2e 1.0 → 1.0, shippable 1.0 → 1.0, rubric 97.9 → 97.9 |
| R7-selftest | ✅ | self-test green |
| R9-guard | ❌ | 1 weakening finding(s): yardstick changed: evals/scorecard.py (automation never edits the yardstick) |

## Headline

- golden: e2e 1.0→1.0 (flips +0/−0, p=1) · shippable 1.0→1.0 · rubric 98.9→98.9 Δ +0.00 [+0.00, +0.00] · audit 95.8→95.8 · compliance 0 · hooks changed 0/330 · distinct 0.6333→0.6333 · distinct-2 0.2102→0.2102
- holdout: e2e 1.0→1.0 (flips +0/−0, p=1) · shippable 1.0→1.0 · rubric 97.9→97.9 Δ +0.00 [+0.00, +0.00] · audit 94.1→94.1 · compliance 0 · hooks changed 0/350 · distinct 0.58→0.58 · distinct-2 0.1948→0.1948

## Diversity

- golden: hook distinct ratio 0.6333 → 0.6333 (+0.0000) · distinct-2 0.2102 → 0.2102 (+0.0000) · per-cell seed diversity None → None
- holdout: hook distinct ratio 0.58 → 0.58 (+0.0000) · distinct-2 0.1948 → 0.1948 (+0.0000) · per-cell seed diversity None → None

## Weakening guard

- guarded files changed: none
- yardstick changed: evals/scorecard.py
- registry rules 46 → 46; self-test cases 112 → 112 (legacy 17 → 17)
- ❌ yardstick changed: evals/scorecard.py (automation never edits the yardstick)

## Diff (71 files)

- `.agents/skills/vsp-produce/SKILL.md` +19 −2
- `.agents/skills/vsp-trends/SKILL.md` +181 −0
- `AGENTS.md` +42 −4
- `README.md` +35 −4
- `RULES.md` +101 −0
- `agent/README.md` +48 −0
- `agent/hermes/config.yaml` +3 −0
- `agent/hermes/scripts/vsp-trends-daily.sh` +48 −0
- `antigravity/.agents/rules/omni-prompting.md` +97 −0
- `antigravity/.agents/rules/qa-gate.md` +66 −0
- `antigravity/.agents/rules/voice-cartesia.md` +70 −0
- `antigravity/.agents/skills/assemble-master/SKILL.md` +40 −0
- `antigravity/.agents/skills/assemble-master/scripts/assemble.py` +299 −0
- `antigravity/.agents/skills/cartesia-voice/SKILL.md` +44 −0
- `antigravity/.agents/skills/cartesia-voice/scripts/cartesia_vo.py` +413 −0
- `antigravity/.agents/skills/lipsync-pass/SKILL.md` +38 −0
- `antigravity/.agents/skills/omni-render/SKILL.md` +47 −0
- `antigravity/.agents/skills/omni-render/scripts/omni_render.py` +450 −0
- `antigravity/.agents/skills/qa-judge/SKILL.md` +35 −0
- `antigravity/.agents/skills/qa-judge/scripts/qa_probe.py` +267 −0
- `antigravity/AGENTS.md` +133 −0
- `antigravity/README.md` +89 −0
- `antigravity/examples/ai/render.json` +1854 −0
- `antigravity/examples/ai/render.md` +33 −0
- `antigravity/examples/ai/voice_plan.json` +466 −0
- `antigravity/examples/human-ai-broll/render.json` +1389 −0
- `antigravity/examples/human-ai-broll/render.md` +31 −0
- `antigravity/examples/human-ai-broll/voice_plan.json` +376 −0
- `antigravity/examples/human/render.json` +1258 −0
- `antigravity/examples/human/render.md` +30 −0

## Scorecard compare reports

- golden: `learned/verify/20260929T222042Z-41700907e328-e5c9851543b4/golden-compare.md`
- holdout: `learned/verify/20260929T222042Z-41700907e328-e5c9851543b4/holdout-compare.md`
