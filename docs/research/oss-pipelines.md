# Short-form video/script pipelines: OSS survey + engineering playbook

Prepared 2026-09-28 for the viral-script-maker upgrade (prompt → script JSON + shot list + render brief). Sources are linked inline.

**Bottom line.** Most OSS tools are render-first (topic → MP4) and do little to control script quality. The best 2026 repos add three things: typed artifacts you can replay, rubric scoring with a critic loop that stops after a fixed number of retries, and word-level caption data. Our rulebook and gates already beat them on content. What we lack is a schema, candidate ranking and exports.

## 1. Repo comparison

| Project | Activity | Stages | Config | Outputs | Quality control | Worth stealing |
|---|---|---|---|---|---|---|
| [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) | active 2026 | script → terms → audio → subtitle → materials → video ([`stop_at`](https://raw.githubusercontent.com/harry0703/MoneyPrinterTurbo/main/app/services/task.py)) | `config.toml` + Pydantic [`VideoParams`](https://raw.githubusercontent.com/harry0703/MoneyPrinterTurbo/main/app/models/schema.py); CLI > config > default | MP4, SRT, script + B-roll terms | records `failed_stage`; [re-aligns ASR cues to the script](https://raw.githubusercontent.com/harry0703/MoneyPrinterTurbo/main/app/services/subtitle.py) when similarity > 0.8 | JSONL batch file, fully validated before the first task |
| [ShortGPT](https://github.com/RayVentura/ShortGPT) | 2023-era, ~8k★ | short/video/translation engines + editing engine | .env, Gradio | MP4, captions, YouTube metadata | none explicit | JSON editing blocks an LLM can emit |
| [short-video-maker](https://github.com/gyoridavid/short-video-maker) | last commits [Jun 2025](https://github.com/gyoridavid/short-video-maker/commits/main) | scenes → Kokoro TTS → whisper.cpp → Pexels → Remotion | env + per-request config (voice, music mood, caption position) | MP4 via REST/MCP | fallback search terms when stock search misses | scene = `{text, searchTerms}` |
| [AI-Youtube-Shorts-Generator](https://github.com/SamurAIGPT/AI-Youtube-Shorts-Generator) | 2025–26 | transcribe → classify content type → chunk → LLM rank → dedupe → top-N | .env + constants in `highlights.py` | MP4s + `--output-json` listing all candidates | 0–100 score, hook and reason per clip; >50% overlap → keep the higher score | ranked candidates with reasons |
| [Auto-YouTube-Shorts-Maker](https://github.com/Binary-Bytes/Auto-YouTube-Shorts-Maker) | hobby | text → gTTS → gameplay crop | .env | MP4, no subtitles | none | baseline only |
| [OpenShorts](https://github.com/mutonby/openshorts) | active 2026 | ASR → scene detection → LLM moments → reframe; UGC: hook–problem–solution–CTA → actor → B-roll | .env; local LLM via `LLM_BASE_URL` | MP4, ASS subtitles, hook overlays | notes JSON reliability by model size | MCP/REST/CLI, signed webhooks, SKILL.md |
| [SupoClip](https://github.com/FujiwaraChoki/supoclip) | active 2026 (AGPL) | LLM picks 3–7 segments → score → crop → subtitles → hook title | .env | clips + word-synced subtitles | sub-scores: hook, engagement, value, shareability | multi-axis score |
| [FunClip](https://github.com/modelscope/FunClip) | v2.2.1, Sep 2026 | ASR (hotwords, speaker IDs) → select by text, speaker or LLM → clip | CLI flags | full-video + per-clip SRT | pinned model revision; SHA256SUMS on releases | split CLI (`--stage 1/2`) |
| [@remotion/captions](https://www.remotion.dev/docs/captions/caption) | current v4.0.5xx | `Caption[]` → [TikTok-style pages](https://www.remotion.dev/docs/captions/create-tiktok-style-captions) | function args | pages + token timings; SRT I/O | — | `Caption` JSON as the caption interchange format |
| [n8n 17408](https://n8n.io/workflows/17408/)/[17566](https://n8n.io/workflows/17566/) | 2026 | form → strict-JSON LLM → per-scene items → Edge TTS → FFmpeg karaoke captions | node constants (`TOTAL_WORDS`) | `{scenes:[{voice_over,image_prompt}]}`, MP4 | JSON validation; per-scene word caps | word budget from target length |
| [OpenReels](https://github.com/tsensei/OpenReels) | v0.17, 2026 | research → script → voiceover with word timestamps → visuals → music → captions → assembly → critique | CLI flags, 14 visual styles, `--direction` brief | DirectorScore JSON, MP4 | critic re-runs below threshold; vision model checks stock clips (conf ≥0.6, ≤4 tries) | `--dry-run`/`--score` replay; cost estimate |
| [Verticals v3](https://github.com/rushindrasinha/youtube-shorts-pipeline) | v3.1, 2026 | research → script → visuals → voice → captions → assemble → upload | 15 niche YAML profiles | script + metadata, ASS + SRT, MP4 | research-only facts; forbidden phrases; resumable stages | niche profiles; `draft/produce/upload` subcommands |
| [CutPilot](https://github.com/lablup/cutpilot) | 2026 | ASR → vision-model window scan → text-model candidates → edit plan → ffmpeg | .env, `prompts/*.md` | clips + manifest per clip (captions, reasoning trace) | rubric: hook + self-contained + length fit + visual fit; strict Pydantic output | reasoning trace; unit/integration/e2e test markers |
| [myAiVideos](https://github.com/myccarl/ai-shortVideo-pipeline) | 2025–26 | 7 layers: topic → creative → visual → audio → post → distribution → optimization | Pydantic, .env | MP4, live progress | prompt anchoring; CLIP text-image check; audio/video sync rescue | regenerate one segment |
| [video-use](https://github.com/browser-use/video-use) | 2026 | transcribe → pack → LLM → EDL → render → self-eval | [SKILL.md](https://raw.githubusercontent.com/browser-use/video-use/main/SKILL.md) | `edl.json`, master SRT, MP4 | 12 hard rules; ≤3 self-eval passes; critic sub-agent | hard rules separated from taste |
| [HKUDS VideoAgent](https://github.com/HKUDS/VideoAgent) | EMNLP 2026 | intent parsing → tool filtering → graph-optimized pipeline (30+ agents) | Python | edited/remade video | [87–95% orchestration success](https://arxiv.org/abs/2606.23327) | routes intent to tools |
| [ViMax](https://github.com/HKUDS/ViMax) | v1.2, Jul 2026 | idea/script/novel → characters → storyboard → shots → video | Web UI/TUI | storyboards, renders | reference-image and continuity management | render checkpoints to resume from |
| [Dramatron](https://github.com/google-deepmind/dramatron) | 2022–23 | logline → characters → plot → locations → dialogue | Colab | screenplay | human co-writer; plagiarism and toxicity checks | hierarchical generation |
| [Re3](https://github.com/yangkevin2/emnlp22-re3-story-generation)/[DOC](https://github.com/yangkevin2/doc-story-generation)/[RecurrentGPT](https://github.com/aiwaves-cn/RecurrentGPT) | research, 2022–23 | plan → draft → rerank → edit; detailed outlines; memory kept as plain text | code | long stories | [rerank for coherence and relevance to the premise](https://arxiv.org/abs/2210.06774v2) | outline → beats → rerank |
| [ai-ugc-agent](https://github.com/Nuraveda-Labs/ai-ugc-agent)/[ai-ad-creation](https://github.com/melon0102/ai-ad-creation) | recent | brief (product, audience, hook angles) → script per hook → render | YAML; Zod | 15–30 s ads; ad package + trace | human approval before spend; validated I/O; mock providers | hook-angle A/B; regenerate one section |

## 2. Features to borrow (27)

**Contract & orchestration**
1. **Stop/resume stages** ([MPT](https://github.com/harry0703/MoneyPrinterTurbo), [Verticals](https://github.com/rushindrasinha/youtube-shorts-pipeline), [FunClip](https://github.com/modelscope/FunClip)). *Impl:* `vsm run --stop-at plan|script|shotlist|captions|brief`. Each stage writes a validated artifact plus a done-marker keyed by its input hash; `--force` ignores the marker.
2. **Batch manifests** (MPT). *Impl:* `vsm batch tasks.jsonl` validates every row first, continues past failures, and prints `{total, succeeded, failed, tasks[{index, status, failed_stage, error}]}`.
3. **Single config resolver** (MPT). *Impl:* one function applies CLI > env > `vsm.toml` > defaults, and the resolved config is saved in the manifest.
4. **Dry-run and replay** ([OpenReels](https://github.com/tsensei/OpenReels)). *Impl:* `--dry-run` emits only the plan. `--from script.json` rebuilds the shot list, captions and brief without re-generating the script.
5. **Profiles as data** (Verticals). *Impl:* move hook templates, CTAs, word ranges, forbidden phrases and visual avoid-lists into `templates/niches/*.yaml`, validated by a `NicheProfile` model.
6. **A beat grammar per format** ([video-use](https://raw.githubusercontent.com/browser-use/video-use/main/SKILL.md), [OpenShorts](https://github.com/mutonby/openshorts)). *Impl:* each format declares its ordered beat types, and a rule checks their order and count.
7. **Regenerate one section** ([ai-ad-creation](https://github.com/melon0102/ai-ad-creation), [myAiVideos](https://github.com/myccarl/ai-shortVideo-pipeline)). *Impl:* `vsm regen <run> --section beats[2]` bumps only that section's sub-seed, so the rest stays byte-identical.

**Generation & ranking**
8. **N candidates → rubric → top-k** ([AI-YT-Shorts](https://github.com/SamurAIGPT/AI-Youtube-Shorts-Generator), [SupoClip](https://github.com/FujiwaraChoki/supoclip), [CutPilot](https://github.com/lablup/cutpilot)). *Impl:* `--candidates 8` means 8 sub-seeds. Score each 0–100 on hook, retention, proof, CTA, compliance and caption headroom, and give each a one-line reason.
9. **Dedupe** (AI-YT-Shorts). *Impl:* drop a candidate if its hook+beat token Jaccard similarity to a better-scored one is above 0.5.
10. **Capped critic loop** (OpenReels; video-use allows 3 passes). *Impl:* if the best score is below threshold, redraw at most 3 times, then fail loudly.
11. **Outline → beats → rerank** ([Dramatron](https://github.com/google-deepmind/dramatron), [Re3](https://arxiv.org/abs/2210.06774v2)). *Impl:* a `Plan` stage (angle, proof, payoff, CTA, cites) feeds beat generation. Rerank beat variants for relevance to the premise.
12. **Hook-angle A/B** ([ai-ugc-agent](https://github.com/Nuraveda-Labs/ai-ugc-agent)). *Impl:* generate one script per hook angle listed in the brief, all around a single CTA, and label the variants.

**Quality gates**
13. **Rule registry with codes** ([Ruff](https://docs.astral.sh/ruff/linter/)). *Impl:* `@rule("D037", stage="script", severity="error")`, `--select/--ignore` by prefix, and `vsm rules explain D037`.
14. **Hard rules vs taste** (video-use). *Impl:* tag all 135 findings `error|warn|info`. `error` fails the gate; `warn` lowers the score.
15. **Standard findings format** ([SARIF 2.1.0](https://docs.oasis-open.org/sarif/sarif/v2.1.0/os/sarif-v2.1.0-os.pdf)). *Impl:* write `gate-report.sarif.json` next to `validation-report.md`.
16. **Prompt-injection hygiene** (Verticals truncates research snippets and wraps them in boundary markers). *Impl:* cap and delimit reel text pulled from SQLite, and cite the pack date and sha256 in every script.
17. **Asset acceptance criteria** (OpenReels, myAiVideos). *Impl:* the brief carries `verify: {min_confidence, max_attempts}` plus a per-shot product-consistency anchor.

**Captions & timing**
18. **Remotion `Caption` JSON** ([docs](https://www.remotion.dev/docs/captions/caption)). *Impl:* emit `{text, startMs, endMs, timestampMs, confidence}`, with a space before each word.
19. **Two caption products** (Verticals ships ASS and SRT). *Impl:* kinetic `captions.ass` for burned-in text plus accessibility `.srt`/`.vtt`, each with its own limits (§3).
20. **Kinetic chunking** (video-use). *Impl:* about 2 words per page. Break on punctuation and on pauses ≥0.3 s, merge to 3 words instead of showing a page under 0.35 s, and set `pageBreakAfter` at beat ends.
21. **Timing source + re-alignment** (MPT; [edge-tts](https://github.com/rany2/edge-tts) `--write-subtitles`). *Impl:* a `timing_source: estimate|tts|asr` field, plus `vsm captions align` to snap ASR cues back to the script text.
22. **Word budget per beat** ([n8n](https://n8n.io/workflows/17408/)). *Impl:* budget = beat seconds × words per second. Gate on overruns; never silently truncate.

**Shot list & handoff**
23. **B-roll queries with fallbacks** ([short-video-maker](https://github.com/gyoridavid/short-video-maker)). *Impl:* every shot gets `broll_queries[]` plus niche-safe fallback terms, so the list is never empty.
24. **Editor exports** (§3b). *Impl:* `shotlist.csv`, `markers.edl` (Resolve markers) and `timeline.otio` with placeholder clips.
25. **Manifest with reasoning trace** (CutPilot). *Impl:* record seeds, config, versions, digests, scores, and rejected candidates with the reason each lost.
26. **Agent contract** (OpenShorts and MPT ship SKILL.md). *Impl:* ship `SKILL.md` plus the JSON Schemas, with `status: draft|approved` (the ai-ugc-agent approval gate) so only approved scripts get rendered.
27. **Hermetic test tiers** (CutPilot, [pytest-socket](https://github.com/miketheman/pytest-socket), [syrupy](https://github.com/syrupy-project/syrupy)). *Impl:* default to `pytest -m "not e2e" --disable-socket`, with snapshots per (prompt, seed) and a frozen research-pack fixture.

## 3. Caption timing standards

| Parameter | Netflix | BBC | DCMP | Our 9:16 default |
|---|---|---|---|---|
| Characters per line | 42 ([EN-US](https://partnerhelp.netflixstudios.com/hc/en-us/articles/217350977-English-USA-Timed-Text-Style-Guide)) | 37 on Teletext. Online it's by width: 68% of a 16:9 frame, 90% of a 9:16 frame, ≈25 chars in 9:16 ([BBC](https://www.bbc.co.uk/accessibility/forproducts/guides/subtitles/)) | — | ≤25 (never over 42) |
| Lines | 2 max, prefer 1 ([general](https://partnerhelp.netflixstudios.com/hc/en-us/articles/215758617-Timed-Text-Style-Guide-General-Requirements)) | 2 for 16:9/4:3/1:1; 3 for 9:16 | ≤2 ([DCMP](https://dcmp.org/learn/597-captioning-key---text)) | 2 |
| Reading speed | ≤20 CPS adult, ≤17 children | 160–180 WPM (0.33–0.375 s/word) | ≤130/140/160 WPM by grade level ([DCMP](https://dcmp.org/learn/captioningkey/601)) | target ≤17 CPS, fail >20 |
| Min duration | 5/6 s (20 frames at 24 fps) | ~0.3 s per word | 40 frames | 0.83 s sidecar; 0.35 s kinetic page |
| Max duration | 7 s | — | 6 s | 7 s |
| Gaps | ≥2 frames. At 24 fps, close 3–11-frame gaps to 2 frames, else leave ≥0.5 s ([timing](https://partnerhelp.netflixstudios.com/hc/en-us/articles/360051554394-Timed-Text-Style-Guide-Subtitle-Timing-Guidelines)) | pause gaps ≥1 s (ideally 1.5 s) | — | 2 frames or ≥0.5 s |
| Sync | in-time within 1–2 frames of speech; out-time ~0.5 s after speech ends; snap to shot changes within 0.5 s | appear at speech onset | may borrow up to 15 frames | snap cues to shot-list boundaries |
| Line breaks | break after punctuation or before conjunctions; never split article + noun, a full name, or auxiliary + verb | break at clause boundaries | similar | segmentation rules |
| Size/position | centered, top or bottom | 9:16 line height 4–5% of frame height; avoid the top and bottom 5% | move up if captions cover faces | safe-zone check in the brief |

**Formats.**
- **[WebVTT](https://www.w3.org/TR/webvtt1/):** starts with a `WEBVTT` header; timestamps are `[hh:]mm:ss.ttt`. Cue starts must never decrease. Inline `<mm:ss.ttt>` tags give word-level highlighting.
- **SRT:** `HH:MM:SS,mmm --> HH:MM:SS,mmm`.
- **[CapCut](https://www.capcut.com/help/how-to-import-subtitles):** imports UTF-8 SRT on Desktop and Web only, not mobile.
- **CJK/Thai:** needs character-based limits, because splitting on whitespace fails ([n8n](https://n8n.io/workflows/17566/)).

**Timing math.** Our 3.0 words/s equals 180 WPM, the top of BBC's range. At roughly 5.5–6 characters per word including spaces (a rule of thumb), that's about 16–18 CPS. So on-screen text must be shorter than the voiceover, or we allow up to 20 CPS. The slower 2.5 words/s delivery works out to 150 WPM.

### 3b. Editor interchange

| Target | Import path | Notes |
|---|---|---|
| CMX 3600 EDL | Premiere, Resolve, Avid | Single video track; 8-character reel names; no frame rate in the file ([OTIO adapter](https://github.com/OpenTimelineIO/otio-cmx3600-adapter)); [999 events max](https://community.adobe.com/questions-729/the-maximum-edl-event-limit-what-data-am-i-losing-1621633) |
| Resolve marker EDL | Timelines → Import → [Timeline Markers from EDL](https://help.frame.io/en/articles/4128691-import-comments-into-resolve-with-edl) | One marker per shot; color tokens like `ResolveColorBlue` ([example](https://github.com/jiazheng0609/Davinci-Resolve-clip-marker-from-edl)). Copy the layout from one marker exported by Resolve. |
| Resolve CSV | File → Import Metadata To → Media Pool ([forum](https://forum.blackmagicdesign.com/viewtopic.php?f=21&t=103198)) | After the shoot, tags clips with shot ID and beat, keyed by file name |
| OTIO | Resolve 18.5+, Premiere 25.6+ ([guide](https://convert.remotion.dev/docs/export-opentimeline)) | Times stored as `RationalTime{value, rate}`, holes as `Gap` items; `otioconvert` produces FCP7 XML for older Premiere |
| CapCut | [no import from other editors](https://www.capcut.com/help/how-to-export-pro-project) | Deliver SRT plus a CSV shoot sheet |

## 4. Recommended module layout

```
pyproject.toml          # [project.scripts] vsm = "vsm.cli:main"; entry points: vsm.rules, vsm.exporters
src/vsm/
  cli.py                # run | batch | gate | rules | captions | export | research | schema | selftest
  config.py             # CLI > env > vsm.toml > defaults
  models/               # Pydantic v2 contract: brief, script, shot, caption, render_brief, finding, manifest
  schema/               # generated *.schema.json, committed, drift-checked in CI
  seeding.py            # derive_seed(root, *path)
  stages/               # pure fns (inputs, rng, ctx) -> model: plan, hooks, beats, rehooks, caption_copy, shotlist, render_brief
  templates/            # data only: hook formulas, rehook decks, niches/*.yaml, formats/*.yaml
  research/             # bridge.py (read-only SQLite), pack.py, sanitize.py
  rules/                # registry.py + modules per RULES.md section
  gates/                # script_gate.py, bundle_gate.py
  scoring/              # rubric.py, dedupe.py, rank.py
  captions/             # segment, timing (CPS/min/max/gaps), srt, vtt, ass, remotion
  export/               # csv_shotlist, edl_markers, otio_timeline, bundle_md
  cache.py manifest.py selftest.py
tests/  fixtures/  __snapshots__/  test_*.py
```

**Engineering notes**
- **Schema.** [`model_json_schema()`](https://pydantic.dev/docs/validation/latest/concepts/json_schema/) emits JSON Schema Draft 2020-12; commit the output. Replace `t: "0-3s"` strings with numeric `start_s`/`end_s`.
- **Seeds.** The single shared `random.Random` means one extra draw shifts every later choice. Give each stage and candidate its own stream: `Random(int.from_bytes(sha256(f"{root}|{stage}|{i}".encode()).digest()[:8]))`.
  - Avoid built-in `hash()`: string hashes are salted per process unless [`PYTHONHASHSEED`](https://docs.python.org/3/using/cmdline.html) is set.
  - Only [`random()`'s sequence is guaranteed](https://docs.python.org/3/library/random.html) across Python versions, so log the Python version and pin it for snapshot tests.
  - With NumPy, use [`SeedSequence.spawn`](https://numpy.org/doc/stable/reference/random/parallel.html).
- **Cache.** Content-addressed like [DVC's cache](https://doc.dvc.org/user-guide/project-structure/internal-files). The key is the sha256 of [canonical JSON](https://www.rfc-editor.org/rfc/rfc8785.html) inputs plus the code version; hash files with [`hashlib.file_digest`](https://docs.python.org/3/library/hashlib.html).
- **Manifest.** Record entity/activity/agent fields in the [W3C PROV](https://www.w3.org/TR/prov-overview/) sense: input digests, stage runs with sub-seeds, and tool versions.
- **Plugins.** Discover rules and exporters via [entry points](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/); use [pluggy](https://pluggy.readthedocs.io/en/stable/) only if you need multi-implementation hooks.
- **CLI.** Per [clig.dev](https://clig.dev/): data on stdout, logs on stderr, `--json`, `-n/--dry-run`, and a non-zero exit code when a gate fails.
- **Packaging.** [src layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/), so tests run against the installed package.
- **Migration.** Wrap existing functions as stages and keep `viral_script_maker.py` as a shim. Move one RULES.md section per PR, and require byte-identical output for fixed seeds.

---
Content was rephrased for compliance with licensing restrictions.
