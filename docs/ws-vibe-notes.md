# WS-VIBE notes — creative direction (branch ws/vibe)

Files: `vsp/direction.py`, `vsp/data/vibes.json`, this note. Contract: `docs/CREATIVE-PLAN.md` §1.1.

## Commits
- `0029f02` vibes.json: vibe-tone-music §5.1–§5.7 + §6 transcribed verbatim (every evidence ref kept), plus §4 voice table, §2.2 showmanship devices, §2.1 finish, §3.1 TikTok Shop lane, niche/product places, evidence claims
- `6b8b190` `direct()`: concept, vibe resolution + lanes, tone, pacing, energy curve, music/licensing, look/camera/text, showmanship, voice, evidence
- `5e6561c` `render_md`, `style_paragraph`, `voice_spec`, `validate`, hermetic `selfcheck`, CLI
- `361983f` energy-curve fix (a third level never empties a level); selfcheck runs the 39 self-test fixtures without ctx
- `8e30c5c` C6 candid cues for human candid vibes; trend + licence-log line; selfcheck forces `VSP_NO_PRIORS=1`
- this notes commit

## Vibe distribution
Golden matrix: 33 prompts × 5 formats × 2 presenters, seed 1, 30 s.

| vibe | total | AI |
|---|---|---|
| clean-aesthetic | 116 | 107 |
| before-after-reveal | 58 | 29 |
| raw-ugc | 56 | 0 |
| story-vlog | 42 | 0 |
| expert-trust | 22 | 11 |
| hype-energy | 18 | 9 |
| cozy-calm | 10 | 5 |
| playful-comedic | 8 | 4 |

No golden prompt hits the cinematic-premium or asmr-satisfying cues. asmr-satisfying does appear in the 4-duration seed-3 sweep: holdout 24, capability 8.

## Examples
- **Milk frother, AI demo → expert-trust** (demo × tools; secondary clean-aesthetic).
  - Tone: expert, no humour.
  - Pacing: 150–180 wpm; energy curve 3/3/2/3/4/3/3.
  - Music: steady ambient electronic, 80–100 BPM.
  - Set: the kitchen counter, cleared as a work surface.
  - Device: a story turn.
  - Voice: disclosed synthetic voice; any single TTS rate must be at least 180 wpm.
- **Silk pillowcase, human review → cozy-calm** (triggered by the "pillowcase" cue; secondary raw-ugc).
  - Tone: calm.
  - Pacing: 150–180 wpm.
  - Music: warm lo-fi chill, 60–85 BPM.
  - Set: bedroom at dusk, warm practical lights.
  - Device: a soft pause.
  - Voice: real voice, no TTS.
- **"I quit sugar for 21 days", human pov-vlog → story-vlog** (challenge rule).
  - Tone: warm, light humour.
  - Pacing: 160–180 wpm; energy curve 4/4/3/3/5/3/3.
  - Music: optimistic indie pop, 90–115 BPM.
  - Set: the kitchen as the anchor spot revisited every day, with day markers.

## Verification
- `python3.9 -m vsp.direction selfcheck`: OK (4.8 s). `python3.12`: OK (4.1 s). The selfcheck covers:
  - the 330 scripts, run twice, byte-identical;
  - PYTHONHASHSEED 0 and 4242 in subprocesses, identical;
  - `direct()` at 0.3 ms mean;
  - no `creative_warnings`;
  - the no-ctx path, which infers the same concept on 330/330 scripts;
  - the 39 legacy fixtures;
  - synthetic checks of the lanes, tie-break, pack and Shop logic;
  - the 4 research test-vector examples.
- `pipeline.py --self-test`: green on 3.9 and 3.12.
- `fast_eval --gate2`: 990/990 gate-1 and e2e (holdout: 1050/1050).
- A sweep of golden + holdout + capability × 15/30/45/60 s (3,600 scripts) shows 0 problems.
- I simulated the integrator's bundle wiring on 330 bundles:
  - the STYLE body replaced by `style_paragraph`;
  - the section inserted after STYLE;
  - the Voice spec line replaced.

  It produced 0 new gate-2 failures.

## Not met / caveats
- **Calm vibes cannot hold 150–160 wpm.** The maker's fixed deliveries size most beats at 3.0 words/s (180 wpm), and direction never asks for slower speech. So `target_wpm` is raised to cover the per-beat floors (cozy-calm becomes 150–180). The research's §4 TTS band of 155–175 wpm is overridden the same way.
  - **Fix (maker, not mine):** choose delivery slow keys from `resolve_vibe()` before sizing. The proposed VTM1 rule would flag this today.
- **The research pack step never fires with the shipped pack.** The pack has no per-niche patterns; its `fresh_hook_lines` cover comedy only. The global fallback (b-roll-captions, 235/1824 reels = 13%) is below the 25% threshold.
- **AI presenter + TikTok Shop cannot both be satisfied.** The direction says so: post the TikTok cut as a non-Shop video, or re-voice it with a human.
- **The account type is unknown.** Licensing uses the creator cell and merges the "never" lists across all account types.
- **Vocab proposal:** add the §5.7 TRANSITIONS ids to `creative_vocab`. They are used as plain strings for now; no other ids were needed or remapped.

## Integration notes
- **Bundle wiring:**
  - `render_md(d)` goes right after `## STYLE`. It has one `##` heading and no sub-headings.
  - `style_paragraph(d)` replaces the STYLE paragraph.
  - `voice_spec(d)` returns the whole line, `Voice spec: …`.
  - The legacy Do NOT line "No robotic TTS — human voice only" contradicts AI bundles. The `dont` list has replacement wording.
- **Output shape:** `energy_curve[].wpm` appears only on spoken items (VISUAL TRIGGER has none). `music.licensing[p]` holds `{library, note}`, and the lane is stated in the note.
- **Tie-break semantics:** it switches only when the secondary has its own mean with n ≥ 3, that mean beats the primary's (0.5 if the primary has none), and the secondary is lane-approved.
