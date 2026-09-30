# Rendering our bundles with Gemini Omni in Google Antigravity (checked 2026-09-29)

**Scope.** How the downstream Antigravity agent should turn a bundle (`brief.md`, `shots.json`) into Gemini Omni renders, and what the rules pack and the per-run `render.json` must carry. Cartesia voice is covered elsewhere; it appears here only where it meets Omni (audio input, lip-sync, native audio). Shot grammar and AI-risk ratings are in [shots-cinematography.md](shots-cinematography.md) ("shots"); disclosure law is in [short-form-virality.md](short-form-virality.md) §6 ("virality").

**Grades.** [P] official platform/vendor docs · [S] independent study/test · [M] marketing, blog or vendor-run test · [A] our assumption. **UNVERIFIED** = no primary source confirmed it. **Docs disagree** = two official pages conflict.

## TL;DR

1. **Model:** `gemini-omni-1.1-flash`, the stable Gemini API model (paid tier only), called through the Interactions API. `gemini-omni-flash-preview` is the older preview; Vertex serves `gemini-omni-1.1-flash-preview` [P].
2. **One call returns 3–10 s at 24 fps** in 16:9 (default) or 9:16. 720p is native and the default, 360p is a draft tier, and 1080p/4K are upscales. Clips extend at the end in steps of up to 10 s, to 40 s in total [P].
3. **Our shots run 0.5–2.5 s, the model's floor is 3 s.** Render each AI shot as its own clip of 3 s or more and record the planned window in `render.json`; Marlowe cuts. Omni outputs 24 fps and the render spec says 30: conform, never motion-interpolate [P/A].
4. **Price per output second:** ≈$0.034 (360p), $0.101 (720p), $0.152 (1080p), $0.304 (4K) [P]. About 55 s of output per bundle costs ≈$1.9 as a 360p draft and ≈$8.4 as a 1080p final, before retries [A].
5. **No system-instruction, temperature or negative-prompt field.** Every constraint, "No …" lines included, goes inside each shot prompt [P].
6. **Omni cuts between shots by default,** so every prompt needs "single continuous shot, no scene cuts" [P].
7. **Consistency comes from references, not wording alone:** up to 10 images per prompt (Vertex) and 3 video refs of ≤3 s, with role tags `<FIRST_FRAME>`, `<LAST_FRAME>`, `<IMAGE_REF_N>`; one still as both first and last frame makes a loop. Uploads of certain recognisable people are blocked, so we use a synthetic presenter sheet [P].
8. **The API cannot take an external audio track or edit voice** [P]. Lip-sync path: VO over B-roll by default; for on-camera lines, Omni native dialogue (≤6 s, one speaker), then a dedicated lip-sync pass against the Cartesia segment, then replace the audio [P/M/A].
9. **Audio is always generated.** B-roll prompts must say "No dialogue, no voiceover, no music" and name the ambience wanted under the VO [P/A].
10. **360p drafts cost about a third and render up to 60% faster** [P]. No documented call upscales one exact take, so a final is a re-render or an edit turn; test both (UNVERIFIED).
11. **Antigravity:** persistent instructions go in `AGENTS.md`/`GEMINI.md` (no frontmatter) or `.agents/rules/*.md` (YAML `trigger:` required); procedures go in `.agents/skills/<name>/SKILL.md`; workflows retire on 1 Nov 2026 [P].
12. **Every output carries SynthID, and platforms auto-label C2PA-tagged uploads.** AI toggles and the D138 disclosure stay mandatory; Google's use policy bans passing generated content off as human-made to deceive [P].

## 1. Gemini Omni: family, capabilities, API

### 1.1 Models and ids

| Surface | Model id | Status | Notes |
|---|---|---|---|
| Gemini API | `gemini-omni-1.1-flash` | Stable, paid tier, released 27 Aug 2026 | In: text, image, video. Out: 3–10 s, 360p–4K, 24 FPS ([model page](https://ai.google.dev/gemini-api/docs/models/gemini-omni-flash); [blog](https://blog.google/innovation-and-ai/technology/developers-tools/build-with-gemini-omni-1-1-flash/)) [P] |
| Gemini API | `gemini-omni-flash-preview` | Preview (May 2026 original) | 720p only ([Vertex preview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/omni-flash-preview)) [P] |
| Vertex / Agent Platform | `gemini-omni-1.1-flash-preview` | Preview | Global endpoint ([Vertex 1.1](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/omni-1-1-flash)) [P] |
| Consumer | Gemini app, Flow, YouTube | Live | Omni replaces Veo in the Gemini app ([Gemini](https://gemini.google/overview/video-generation/)) [P] |
| Fallback | `veo-3.1-generate-preview`, `veo-3.1-fast-generate-preview`, `veo-3.1-lite-generate-preview` | Preview | Operations API ([Veo](https://ai.google.dev/gemini-api/docs/veo)) [P] |

- **Omni is Google's recommended default.** The same overview still credits Veo 3.1 with extension and last-frame control, which Omni 1.1 now has, so that text looks stale ([video overview](https://ai.google.dev/gemini-api/docs/video)) [P].
- **Token limits, docs disagree:** a 1,048,576-token context on the Gemini API page vs 131,072 in / 57,920 out on Vertex [P]. 57,920 = 10 s × 5,792 tokens/s at 720p, i.e. the 10-s cap [A].

### 1.2 Inputs
- **No audio input through the API.** The model card lists audio among the inputs the model understands ([card](https://deepmind.google/models/model-cards/gemini-omni-flash/)) [P], but the API docs say audio references can't be uploaded in the current version, and Vertex marks audio input "Not supported" ([Omni docs](https://ai.google.dev/gemini-api/docs/omni); [Vertex 1.1](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/omni-1-1-flash)) [P]. DeepMind's demos prompt with `<audio>` ([DeepMind](https://deepmind.google/models/gemini-omni/)) [P]; that is not an API path.
- **Image roles are set by tags:** `<FIRST_FRAME>`, `<LAST_FRAME>` (only with `<FIRST_FRAME>`), `<IMAGE_REF_N>` (subject or style, counted from 0) and `<VIDEO_REF_N>`. For several inputs, declare a header such as `[# Sources <FIRST_FRAME>@Image1] [# References <IMAGE_REF_0>@Image2]` and end the prompt with one sentence per input saying how to use it (e.g. references are not literal first frames) [P].
- **Image limits:** ≤10 images per prompt; PNG, JPEG, WebP, HEIC or HEIF; ≤20 MB inline (Vertex) [P]. The Gemini app caps photo refs at 5 [P].
- **Video limits:** ≤3 reference clips of ≤3 s (their audio is ignored; best for likenesses); ≤10 s for edit or extension inputs; no YouTube URLs; no reasoning across several videos [P].
- **"Ingredients"** is Veo 3.1's term for ≤3 asset images of one person, character or product [P]; Omni's equivalent is `<IMAGE_REF_N>`.
- **Personal avatars are app-only** (Gemini, Flow, YouTube): the account owner records their own face and voice; 18+, personal account, English, not in EEA/CH/UK; only the owner can use it ([help](https://support.google.com/gemini/answer/16984474)) [P]. No API parameter exists, so avatars can't give us a reusable synthetic presenter [P/A]. A vendor test rated the avatar voice clone strong ([invideo](https://invideo.io/blog/gemini-omni-flash-review/)) [M].

### 1.3 Outputs
- **Duration:** 3–10 s per call via `response_format.duration`, a string of whole seconds such as `"8s"` ([API ref](https://ai.google.dev/api/interactions-api); [Vertex T2V](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/generate-videos-from-text)) [P]. The Gemini API documents no default; fal's wrapper defaults to 8 s ([fal](https://fal.ai/learn/tools/how-to-use-gemini-omni-flash-1-1)) [M].
- **Frame rate:** 24 fps [P]. A vendor test saw occasional drops to a choppy 8–12 fps look ([invideo](https://invideo.io/blog/gemini-omni-flash-review/)) [M].
- **Format:** `aspect_ratio` `"16:9"` (default) or `"9:16"`; `resolution` `"360p"`, `"720p"` (default), `"1080p"` or `"4k"`, the last two upscaled [P]. Pixel sizes are undocumented; we assume 720×1280 for 9:16 at 720p [A].
- **Extension:** appends 3–10 s at the end only, up to 40 s total, using the last 10 s as context and editing some final input frames so the join is seamless. Uploaded inputs must be ≤10 s; new dialogue can only be added when extending Omni's own clips multi-turn; uploaded-video extension is blocked in EEA/CH/UK [P].
- **Delivery:** base64 inline by default; `delivery: "uri"` for files over 4 MB (above 720p). Gemini API URIs are Files API objects kept 48 h ([Files](https://ai.google.dev/gemini-api/docs/files)); Vertex writes to `gcs_uri` [P].

### 1.4 Native audio
- **Every call returns audio** (dialogue, SFX, ambience, music); no parameter turns it off. Describe the audio in the prompt, especially music ("No music", "Sound design: …") [P].
- **Dialogue syntax, docs disagree:** Vertex best practice puts speech after a colon without quotes so it isn't drawn as text ([best practice](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/best-practice)) [P]; the Veo guide and DeepMind's Omni demos use quotes [P]. Keep our colon rule (D160).
- **Language:** only English has been evaluated [P].
- **Lip-sync quality** [M]: single-speaker sync held about 6–7 s, then drifted, and two speakers in one frame got mixed up ([invideo](https://invideo.io/blog/gemini-omni-flash-review/)); another review reports drift and floaty motion ([BuildFast](https://blog.buildfastwithai.com/gemini-omni-1-1-flash-review-accuracy-price-is-it-worth-it-2026)).

### 1.5 Camera, keyframes, timing
- **Camera is prompt-only** (no parameter). Google's guide covers static, pan, tilt, dolly, truck, pedestal, zoom, crane, aerial, handheld, whip pan and arc, and lens terms such as wide, telephoto, shallow depth of field, rack focus and dolly zoom; some advanced ones are "not officially supported" ([prompt guide](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/video-gen-prompt-guide)) [P]. A camera move over a static scene is the most reliable motion [P].
- **First/last frames:** two images, or `<FIRST_FRAME> <LAST_FRAME>`; the same image in both slots makes a loop [P].
- **Timing:** plain language ("after 3 seconds …") or timecodes (`[0-3s] … [3-6s] …`); in an extension, 0 s is where the new part starts [P]. A vendor test found timecodes closely followed [M].

### 1.6 Conversational editing
- **How:** send `previous_interaction_id` with a short instruction; each turn returns a new, complete video that keeps what you didn't mention. Add "Keep everything else the same" and keep edit prompts simple. Own clips of ≤10 s can be edited via the Files API, except in EEA/CH/UK ([Omni docs](https://ai.google.dev/gemini-api/docs/omni)) [P].
- **Storage:** `store=false` speeds one-shot calls but rules out later edit turns. Paid-tier interactions are kept 55 days, configurable to 7/14/28/55 ([Interactions](https://ai.google.dev/gemini-api/docs/interactions)) [P]. Vertex retention, docs disagree: 7 days on one page, 14 on another [P].
- **Limits:** voice editing is unsupported; the model can change what people say, but Google restricts that; consistency across edits is not guaranteed ([card](https://deepmind.google/models/model-cards/gemini-omni-flash/)) [P].

### 1.7 Character and product consistency
- **Google's recipe:** a named character with a fixed, detailed description pasted unchanged into every prompt, plus the same seed ([best practice](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/best-practice)) [P].
- **Seed:** the Interactions API has `generation_config.seed` ([API ref](https://ai.google.dev/api/interactions-api)), but the Omni page lists it as neither supported nor unsupported: UNVERIFIED for Omni. For Veo a seed only slightly improves determinism [P].
- **References:** image refs for people and products; video refs work best for likenesses [P]. A vendor says face, clothing and voice carry over ([fal](https://fal.ai/learn/tools/how-to-use-gemini-omni-flash-1-1)) [M].
- **Image-to-video:** prompt only the motion, call the subject "the woman" or "he", and start from a sharp, well-lit image [P].

### 1.8 SynthID and C2PA
- Every Omni video carries an invisible, programmatically detectable SynthID watermark [P]. Vertex lists C2PA Content Credentials as supported for Omni 1.1 [P], and Gemini app, Flow and YouTube output carries SynthID plus C2PA ([DeepMind](https://deepmind.google/models/gemini-omni/)) [P].
- Whether Gemini API MP4s carry C2PA is undocumented: check with a C2PA reader, and expect re-encoding to drop the manifest [A].

### 1.9 Safety: real people, minors, public figures, brands
- **Omni docs** [P]: uploading or editing images of certain recognisable people is blocked; images with minors can't be uploaded or edited in EEA/CH/UK; filters check prompts and outputs and vary by region.
- **Vertex safety codes** ([RAI](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/responsible-ai-and-usage-guidelines)) [P]: Child (rejected unless the person setting or a project allowlist permits it), Celebrity (photorealistic prominent people rejected), Third-party content, Prohibited content. They are documented for Veo; we assume Omni shares them [A].
- **Brands:** no Omni brand or logo rule found, and the model card lists accurate text as unsolved [P]. Never ask for a logo; composite the real packshot in the edit [A].
- **Google's Prohibited Use Policy** bans impersonating someone without disclosure and presenting generated content as made solely by a human, in order to deceive ([policy](https://policies.google.com/terms/generative-ai/use-policy)) [P].

### 1.10 Request shape, latency, cost
**Gemini API** (key in `x-goog-api-key`): `POST https://generativelanguage.googleapis.com/v1beta/interactions` [P]. Parameter names are from the docs; the values are one of our shots.
```text
{"model": "gemini-omni-1.1-flash", "store": true,
 "input": [{"type": "image", "data": "<b64>", "mime_type": "image/png"},
           {"type": "text", "text": "[# Sources <FIRST_FRAME>@Image1] ... Use Image1 as the starting frame."}],
 "response_format": {"type": "video", "aspect_ratio": "9:16", "resolution": "360p", "duration": "4s", "delivery": "uri"},
 "generation_config": {"video_config": {"task": "image_to_video"}}}
```
- **Fields:** also `previous_interaction_id`, `background`, `stream`. `task` takes `text_to_video | image_to_video | reference_to_video | edit | extend`; omit it and the model infers [P].
- **Result:** the SDK exposes `interaction.output_video`; over REST, read `steps[]` → `type: "model_output"` → the `content[]` item of `type: "video"` (`data` or `uri`) [P].
- **Vertex:** `POST https://aiplatform.googleapis.com/v1beta1/projects/{PROJECT}/locations/global/interactions` with an OAuth bearer token; samples send `response_format` as an array; `gcs_uri` is required with URI delivery; calls are synchronous, streaming, or `background: true` and polled, and background needs `store` on ([Vertex T2V](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/generate-videos-from-text)) [P].
- **Latency:** Vertex says a generation can take over a minute; 360p renders up to 60% faster than 720p; no SLA or p95 is published, and quotas are shown per project in AI Studio, not in the docs [P]. Launch-week tests hit repeated 500 errors ([MindStudio](https://www.mindstudio.ai/blog/gemini-omni-1-1-flash-video-model)) [M], so retry with backoff [A]. Veo takes 11 s to 6 min [P].
- **Price** ([Vertex pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing); [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing)) [P]: video output $17.50 per 1M tokens; input $1.50 per 1M (1,120 tokens per image, 5,792 per second of input video); thinking tokens billed as text output at $9 per 1M; no free tier. fal resells at the same per-second rates [M].

| Resolution | Output tokens/s | USD/s | 4-s clip | Use |
|---|---|---|---|---|
| 360p | 1,931 | 0.034 | 0.14 | drafts: composition, move, identity |
| 720p | 5,792 | 0.101 | 0.41 | native quality check |
| 1080p (upscaled) | 8,688 | 0.152 | 0.61 | finals for the 1080×1920 master |
| 4K (upscaled) | 17,376 | 0.304 | 1.22 | never needed for 9:16 social [A] |

### 1.11 Veo 3.1 as fallback
From [Veo](https://ai.google.dev/gemini-api/docs/veo) and [Vertex T2V](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/generate-videos-from-text) [P]:
- **Clips:** 4, 6 or 8 s (8 s required with reference images, 1080p, 4K or extension); 24 fps; 9:16; audio always on; ≤3 reference "asset" images plus first and last frames; extension 7 s at a time, up to 20 times, to 148 s, at 720p.
- **Parameters:** `personGeneration` (`allow_all` for text-to-video, `allow_adult` with image inputs, and only `allow_adult` in EU/UK/CH/MENA), `seed`, and on Vertex `negativePrompt`, written as nouns.
- **Price per second:** Standard $0.40; Fast $0.10 (720p), $0.12 (1080p), $0.30 (4K); Lite $0.05/$0.08. DeepMind says Veo needs more precise prompts than Omni ([Omni guide](https://deepmind.google/models/gemini-omni/prompt-guide/)).

## 2. Prompting best practice

### 2.1 Structure
- **Google's anatomy** (Omni and Veo): subject; action; scene/context; camera angle, movement, lens and optics; style (lighting, mood, art style, ambiance); temporal effects; audio in separate sentences ([prompt guide](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/video-gen-prompt-guide)) [P].
- **DeepMind's Omni advice:** state the intent and let world knowledge fill in the rest [P]. We still spell out whatever we must control (framing, move, subject, audio, no text) and leave incidental detail to the model [A].
- **One focused moment per short clip:** literal wording beats rambling; split "A, then B, then C" into separate clips ([best practice](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/best-practice)) [P].
- **Meta-prompts:** asking for natural micro-detail, expression and timing is an official lever [P].

### 2.2 Dialogue meant for lip-sync
- **One speaker, one line per clip, ≤6 s** (≈15 words at 150 wpm) [M/A]; face large and toward the camera; line after a colon, no quotes; add a voice description and the delivery ([best practice](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/best-practice)) [P].
- **Match clip length to the line and timecodes,** or voice and picture drift apart ([Atlas](https://www.atlascloud.ai/blog/tips/how-to-make-ai-ugc-ads)) [M].

### 2.3 Keeping text out of the frame
- **Omni draws text when asked** and fills in naturally occurring text you describe [P], so any quoted string, sign or label invites text. Its text is still unreliable: the model card calls exact text a challenge [P], and most text-to-video systems failed a legibility benchmark ([arXiv 2505.04946](https://arxiv.org/abs/2505.04946)) [S].
- **Rules:** no quotes anywhere; end every prompt with "No on-screen text, captions, subtitles, logos or watermarks"; film labels for real or composite them [P/A].

### 2.4 Negatives
- Omni has no negative-prompt field: write short negatives into the prompt ("No dialogue", "No embellishments", "No extra sound effects") ([Omni docs](https://ai.google.dev/gemini-api/docs/omni)) [P]. Veo's `negativePrompt` takes plain nouns ("wall, frame"), not instructions [P].
- Keep Omni prompts to the 3–6 negatives that matter for the shot, not our 10-item NEGATIVE PROMPT block [A].

### 2.5 Continuity across shots
- **In every call:** the same reference set (presenter sheet, real product photos, a set plate), identical subject text, and the same seed if Omni honours it [P/A].
- **Still first:** make or photograph the opening frame, then animate it with `image_to_video`; Google's Veo examples start from Nano Banana stills ([Veo](https://ai.google.dev/gemini-api/docs/veo)) [P].
- **Chaining without a cut:** clip N's last frame becomes clip N+1's `<FIRST_FRAME>` [P mechanism, A procedure], or extend via `previous_interaction_id`, which keeps voice and motion [P]. At a real cut to a new angle, shared references beat chaining [A].
- **Loop:** shot 1's frame-0 still is shot 8's `<LAST_FRAME>` [P mechanism].

### 2.6 What fails most, and the fix

| Failure | Evidence | Mitigation (in `render.json`) |
|---|---|---|
| Complex or articulated motion; heads/limbs detaching; object permanence | model card [P]; [MindStudio](https://www.mindstudio.ai/blog/gemini-omni-1-1-flash-video-model) [M] | One simple action in beats, one slow move; else the shot's `ai_fallback` [A] |
| Hands on small objects | shots §4.2 [M]; not re-tested on Omni | Hands at the frame edge; demo/proof shots stay `real_footage` [A] |
| Text, labels, logos | model card [P]; [arXiv](https://arxiv.org/abs/2505.04946) [S] | No quotes; real label footage; composite the packshot [A] |
| Lip-sync past 6–7 s; two speakers | [invideo](https://invideo.io/blog/gemini-omni-flash-review/), BuildFast [M] | One speaker, ≤6 s, then a lip-sync pass (§3) [A] |
| Unwanted cuts | multi-shot by default [P] | Single-shot line; scene-cut QA [P/A] |
| Unwanted music or voice | audio always generated [P] | An explicit audio sentence in every prompt [P] |
| Contact damped; object physics right about half the time | invideo [M] | No drops or throws; film real stress tests [A] |
| Frame-rate wobble (8–12 fps look) | invideo [M] | Duplicate-frame QA; regenerate [A] |
| Identity drift over edits and extensions | model card [P]; BuildFast [M] | References in every call; ≤2 edit turns, then re-render [A] |

## 3. Can Omni lip-sync to our TTS track?

**No, not in the current API** [P]: audio references can't be uploaded (Vertex: audio input "Not supported"), voice editing is unsupported, and audio inside video refs is ignored. Speech editing exists in the model but Google restricts it ([card](https://deepmind.google/models/model-cards/gemini-omni-flash/)) [P]. DeepMind reports image-plus-audio-to-video results scored on "speech adherence" ([DeepMind](https://deepmind.google/models/gemini-omni/)) [P], so the capability exists; watch the changelog.

| Path | Result | Cost | Use |
|---|---|---|---|
| A. VO over B-roll, hands, product or reaction cutaways (no visible mouth) | No sync risk | Lowest | Default for every shot not to camera; vendors treat overlay as the baseline and lip-sync only to-camera beats ([invideo FAQ](https://invideo.io/faq/should-i-use-lip-sync-or-voiceover-overlay-for-ai/)) [M] |
| B. Keep Omni's native voice | Sync holds ≈6–7 s [M] | Low | Never: not the Cartesia voice, and it drifts shot to shot [A] |
| C. Omni says the same line natively → dedicated lip-sync to the Cartesia segment → replace the audio | Best available | +$0.02–0.133/s on sync.so; lipsync-2/2-pro at 512×512 face resolution, sync-3 at 4K with close-ups and extreme angles; MP4 + WAV/MP3 in ([sync.so](https://sync.so/docs/introduction)) [P] | Lines where the viewer watches the mouth |
| D. Mouth moves with no audio → lip-sync | UNVERIFIED | As C | Test only |
| E. Gemini personal avatar | Apps only | n/a | Not usable (§1.2) [P] |

- **Order** [A]: (1) Cartesia VO and word timings; (2) lock the B-roll, which is cheap and has no mouths [M]; (3) talking heads last, via path C.
- **Tolerance:** viewers notice more than +45 ms of audio lead or −125 ms of lag and reject beyond +90/−185 ms ([ITU-R BT.1359-1](https://www.itu.int/dms_pubrec/itu-r/rec/bt/R-REC-BT.1359-1-199811-I!!PDF-E.pdf)) [P]; at 24 fps, audio may lead by at most one frame [A].
- **Native audio:** keep Omni's audio as ambience under the VO on B-roll; drop it on lip-synced shots, since it holds Omni's own voice [A].

## 4. Google Antigravity (v2.18.1, 28 Sep 2026)

### 4.1 Persistent instructions: rules
From [Rules](https://antigravity.google/docs/rules/) [P], valid on Antigravity 2.0, the CLI and the IDE:
- **Workspace/directory:** `AGENTS.md` or `GEMINI.md`, `.agents/AGENTS.md` or `.agents/GEMINI.md`, and `.agents/rules/*.md` (legacy `.agent/rules/`), in the root or any subfolder, loaded walking up from the file being read or edited. Rules add up across scopes; the more specific directory wins a conflict.
- **Global:** always-on `~/.gemini/AGENTS.md`, `~/.gemini/GEMINI.md`, `~/.gemini/config/{AGENTS,GEMINI}.md`; modular `~/.gemini/config/rules/*.md` (frontmatter required); CLI also `~/.gemini/antigravity-cli/rules/*.md` and plugin rules.
- **Format:** `AGENTS.md`/`GEMINI.md` are plain Markdown, no frontmatter, always on. Each file in `rules/` starts with YAML: `trigger:` (`always_on | model_decision | glob | manual`, snake_case; an invalid value silently drops the rule), `description:` (required for `model_decision`) and `globs:` (quoted, comma-separated, for `glob`). `model_decision` indexes only path and description and loads the body on demand; `manual` loads only on an @-mention.
- **Limits:** only direct children of `.agents/rules/` are scanned (nest via `.agents/rules.json` `inherits`/`entries`); 24,000 bytes per file after includes; global plus `always_on` rules share a 20,000-token budget, and the largest files are demoted to pointers on overflow.
- **Includes:** `@[label](path)` inlines a file; `@path` only references it (added in v2.11.0, [changelog](https://antigravity.google/docs/changelog/)) [P].

### 4.2 Workflows are retired; use skills
- **Workflows:** `.agents/workflows/<name>.md` or `~/.gemini/config/workflows/`; title, description and steps, ≤12,000 characters, run as `/name`. Deprecated and retired on 1 Nov 2026; `/migrate-workflows` converts them ([Workflows](https://antigravity.google/docs/ide/workflows/); [migration](https://antigravity.google/docs/migration/workflows-to-skills/)) [P].
- **Skills** (open agentskills standard): `.agents/skills/<name>/SKILL.md` with optional `scripts/`, `references/`, `examples/`, `resources/`; global `~/.gemini/config/skills/<name>/`. Frontmatter: `name` (optional, defaults to the folder) and `description` (required; third person, trigger keywords). Loaded by progressive disclosure, invoked as `/name`; a skill beats a same-named workflow ([Skills](https://antigravity.google/docs/skills/)) [P]. Our repo already uses `.agents/skills/` for Hermes [A].

### 4.3 Artifacts, task lists, Knowledge
- **Artifacts:** implementation plans, diffs, diagrams, screenshots, browser recordings, walkthroughs. The agent pauses for plan review unless the review policy is "Always Proceed"; users comment inline; `/plan` forces a plan ([Artifacts](https://antigravity.google/docs/artifacts/); [plan](https://antigravity.google/docs/implementation-plan/); [walkthrough](https://antigravity.google/docs/walkthrough/)) [P].
- **Task Groups (IDE):** planning mode splits big tasks into subtasks with progress updates and collects steps needing approval at the end ([Task Groups](https://antigravity.google/docs/tools/)) [P].
- **Knowledge Items:** a core component, stored in the app data folder (`~/.gemini/antigravity/`; IDE `~/.gemini/antigravity-ide/`), and can be switched off in settings ([Agent](https://antigravity.google/docs/agent/); [settings](https://antigravity.google/docs/agent-settings/)) [P]. No authoring format is documented; forum users describe auto-written summaries of past conversations ([forum](https://discuss.ai.google.dev/t/knowledge-feature-failure/129021)) [M]. Don't put rules in them [A].

### 4.4 Terminal, network, MCP
- **Terminal sandbox** (macOS/Linux, on by default): workspace and temp writable; `~/.ssh` and `.env` files blocked; network only to approved domains. Presets: Default, Request Review, Turbo. Rules: `command(prefix|regex:…)`, `read_url(domain)` (also opens sandbox egress), `execute_url`, `mcp(server/tool)`; Deny > Ask > Allow ([Sandbox](https://antigravity.google/docs/sandbox/); [Permissions](https://antigravity.google/docs/permissions/)) [P].
- **MCP:** `mcpServers` in `.agents/mcp_config.json` or `~/.gemini/config/mcp_config.json`. Stdio servers take `command`, `args`, `env`, `cwd`; remote servers take `serverUrl` (not `url`) and `headers`; also `authProviderType: "google_credentials"` and `disabledTools` ([MCP](https://antigravity.google/docs/mcp/)) [P].
- **GenMedia MCP:** Google's experimental servers include Gemini Omni (Vertex, ADC auth) and an ffmpeg AVTool, and ship Antigravity skills ([GenMedia](https://github.com/GoogleCloudPlatform/vertex-ai-creative-studio/tree/main/experiments/mcp-genmedia)) [P, experimental].
- **Headless:** the Gemini API's managed agent `antigravity-preview-09-2026` runs the same harness in a Google sandbox, reads a mounted `AGENTS.md` and `.agents/skills/`, and reaches APIs via code execution, function calls or remote MCP (Streamable HTTP, lowercase server names). It accepts only text and image inputs ([Antigravity agent](https://ai.google.dev/gemini-api/docs/antigravity-agent)) [P].

## 5. AI-UGC production practice (2026)

- **Length per generation:** one scene per clip [P]; one clip per shot at max(3 s, shot + ≈1 s) [A]; spoken lines ≤6 s [M].
- **Draft, then final:** explore at 360p, approve, then render finals ([blog](https://blog.google/innovation-and-ai/technology/developers-tools/build-with-gemini-omni-1-1-flash/)) [P]; reviewers recommend the same ([BuildFast](https://blog.buildfastwithai.com/gemini-omni-1-1-flash-review-accuracy-price-is-it-worth-it-2026)) [M]. One vendor found cheap tiers held identity and lip-sync as well as dear ones for UGC (tested on Seedance, [Atlas](https://www.atlascloud.ai/blog/tips/how-to-make-ai-ugc-ads)) [M]. Google suggests Gemini as a "second pair of eyes" to check outputs against brand guidelines [P].
- **Realism cues** (vendor practice [M]; [Atlas](https://www.atlascloud.ai/blog/tips/how-to-make-ai-ugc-ads); [invideo FAQ](https://invideo.io/faq/should-i-use-lip-sync-or-voiceover-overlay-for-ai/)):
  - **Picture:** handheld phone perspective with natural micro-shake; a named light source (window left, bedside lamp) with some unevenness, never just "good lighting"; real skin texture with no beauty-filter look; a lived-in background with one imperfect detail.
  - **Performance and sound:** blinks, one gaze break, one filler word, one pause; phone-mic voice over room tone; no music.
  - **Edit and batch:** cut the dead air and tighten pauses as with real footage; vary person, room and light across a batch, because repetition is the top tell.
- **Disclosure** (details in virality §6):
  - **TikTok** requires a label on realistic AIGC and auto-labels C2PA uploads ([TikTok](https://support.tiktok.com/en/using-tiktok/creating-videos/ai-generated-content); [newsroom](https://newsroom.tiktok.com/more-ways-to-spot-shape-and-understand-ai-content)) [P].
  - **Meta** applies "AI info" when it detects industry-standard AI signals or the uploader discloses, including on ads made with third-party AI tools ([Meta](https://transparency.meta.com/governance/tracking-impact/labeling-ai-content); [ads](https://www.meta.com/help/artificial-intelligence/355108217670024/)) [P]. Self-disclosure is required for photorealistic video or realistic audio ([PCMag](https://www.pcmag.com/news/meta-will-label-ai-generated-content-but-theres-a-catch), via virality §6) [M].
  - **YouTube** requires the "AI use" disclosure for realistic generated scenes and auto-labels C2PA content with a label creators can't remove ([YouTube](https://support.google.com/youtube/answer/14328491)) [P].
  - **Realism doesn't lift the duty to disclose:** Google's policy and the FTC rules (virality §6) still apply [P].

## 6. Design implications for our pipeline

### 6.0 Per-shot recipe (summary of §6.2–§6.7) [P mechanisms, A policy]
1. **Before any call:** render the Cartesia VO and word timings; build the reference pack; pick one seed per run.
2. **Route the shot:** `mode` real, edit-only or ai. For ai, set `task`: `image_to_video` if a still or product photo is the opening frame, `reference_to_video` for refs only, else `text_to_video`.
3. **Request:** `aspect_ratio "9:16"`, `duration` from §6.3, `resolution "360p"` for drafts, `store: true`, `delivery "uri"`.
4. **Prompt:** one string from the §6.2 template, with role tags and a closing sentence per input.
5. **Draft QA** (§6.7), then fix via an edit turn or regenerate (≤3 tries), else `ai_fallback`. Human approval comes via the draft artifact.
6. **Final:** re-render at `"1080p"` with the same inputs, then QA again. Run lip-sync only on to-camera shots (§6.6).
7. **Assemble:** conform 24 → master fps and concatenate every generated second in shot order, with windows in `render.json`.

### 6.1 Gaps between today's brief and Omni
Seen in `v2.1-sample/sunrise-alarm-lamp` [A]:
1. **B-roll prompts carry "The presenter says: …"** (3a, 4a, 5a); sent to Omni, the B-roll gets a voice. Only on-camera lip-sync shots may carry the line.
2. **VISUAL PROMPT, AUDIO and DELIVERY are separate blocks,** but Omni takes one text field, so `render.json` assembles one prompt string per shot.
3. **An electric-blue/hot-pink/lime palette is asked for in a calm bedroom lit by a soft warm lamp;** Omni will try to satisfy both. Put the palette in wardrobe and props, or grade it in the edit.
4. **Shot lengths and frame rate don't fit:** shots of 0.5–2.5 s against a 3-s floor, and 30 fps in the render spec against Omni's 24.
5. **The voice spec (real voice, no TTS) contradicts a Cartesia run.** `render.json` needs `presenter_mode`; in human mode, Omni renders only shots with no face.

### 6.2 Prompt template: one string per shot [P structure, A order]
`{sources_header} {scale}, {angle}, {one move}: {subject_lock | hands_ref | product-only} {one action in beats, already in motion at the first frame} in {setting}, lit by {named light source}. Vertical 9:16 smartphone footage{, handheld with natural micro-shake}. Single continuous shot, no scene cuts. {Sound: ambience/SFX}. {No dialogue, no voiceover. | <Name>, <voice>, says: <line>. Delivery: <delivery>.} No music. No on-screen text, captions, subtitles, logos or watermarks. {2–4 shot-specific negatives}. {one closing sentence per input stating its role}`
- **Keep:** the subject lock for face shots only (D160) [A]; image-to-video prompts describe motion only [P].
- **Leave out:** quotes, "render exactly", palette lists, the 10-item negative block [P/A].

### 6.3 Durations and timing [A]
- **Clip length:** `gen_duration_s = clamp(ceil(planned_s + 1.0), 3, 10)`; lip-sync shots use `clamp(ceil(line_s + 1.0), 3, 7)`, and gate 2 rejects any on-camera line over 6 s.
- **Windows:** `window_in_s = 0.5`, `window_out_s = in + planned_s`, recorded for Marlowe. The master stays uncut and DELIVERABLE is untouched.
- **Frame rate:** the source is 24 fps. Set the master to 24 fps for Omni bundles, or conform to 30 by duplicating frames; no optical-flow interpolation.
- **Calls:** one per shot by default. A timecoded multi-shot call (`[0-1.7s] …`) is allowed only for faceless B-roll in one setup.

### 6.4 Draft and final settings
- **Draft:** `resolution: "360p"`, `store: true`, one take per shot, all shots first. Review as an Antigravity artifact (contact sheet plus a 360p cut); this is the brief's "send a draft for review" step [P/A].
- **Final:** `resolution: "1080p"`, the same inputs and seed, `delivery: "uri"`, downloaded at once (48-h Files retention); no 4K [P/A].
- **Retries:** ≤3 attempts at draft and ≤2 at final, then the shot's `ai_fallback`; never drop a beat. Edit turns only for local fixes ("… Keep everything else the same"), ≤2 per clip [P/A].

### 6.5 Continuity method [P mechanisms, A policy]
- **Reference pack per run** (≤10 images per call): a presenter sheet (front and ¾ stills of a synthetic adult from an image model), 2–3 real product photos, one set plate.
- **Per call:** `<IMAGE_REF_N>` for the pack, plus a still-first `<FIRST_FRAME>` for hero shots. Send the seed and retry without it if the API rejects it.
- **Loop and chaining:** shot 8's `<LAST_FRAME>` = shot 1's frame-0 still. Chain clip N's last frame into clip N+1's `<FIRST_FRAME>` only for continuous action within one setup.

### 6.6 Lip-sync and audio
- **Default:** VO over B-roll (path A) [M/A].
- **To-camera lines:** path C, via a `lipsync-pass` skill. It takes the Cartesia segment cut by the `words.json` timings, and the result must land within +45/−125 ms [P basis, A policy].
- **Native audio:** B-roll keeps Omni's ambience ducked under the VO; lip-synced shots drop Omni audio; no music in the master, per the brief [P/A].

### 6.7 QA gate (per clip, automatable checks first) [A unless marked]
1. **ffprobe:** aspect 9:16 within 1%, 24 fps, duration ≥ `window_out_s`, an audio stream present; no letterbox (ffmpeg `cropdetect`).
2. **No cuts:** zero scene cuts inside a single-shot clip (ffmpeg scene score >0.4) [P basis: multi-shot default].
3. **No text:** no legible text outside approved real-label shots (OCR or a Gemini video judge).
4. **Gemini judge** on stills and clip [P basis: "second pair of eyes"]: the same presenter as the reference (hair, glasses, hoodie); the product matches its reference with no invented logo; five fingers, no fusion, plausible contact (at final resolution); no morphing or detaching parts.
5. **Audio:** on B-roll, voice-activity detection finds no speech and there is no music; on lip-sync shots, the offset is inside the ITU window.
6. **Motion:** the duplicate-frame ratio catches the 8–12 fps wobble. **Framing:** key action inside the virality §2 safe box.
7. **Log** model id, seed, interaction id, cost and verdict to `trace.jsonl`.

### 6.8 Antigravity rules pack layout [P paths, A contents]
- **`AGENTS.md`** (always on, <24 KB): 9:16 only; never render text; never edit DELIVERABLE; synthetic adult presenters only (no real, recognisable or minor people); one shot per call; draft before final; a budget cap per run; disclosure (D137/D138).
- **`.agents/rules/omni-prompting.md`** (`trigger: glob`, `globs: "**/render.json, **/brief.md"`): §6.2, the tag syntax and the audio rules. **`.agents/rules/qa-gate.md`** (`trigger: model_decision`): §6.7.
- **Skills, not workflows,** each with `scripts/`: `.agents/skills/omni-render/` (call, poll, download, frame extract, conform), `.agents/skills/lipsync-pass/`, `.agents/skills/qa-judge/`.
- **Permissions:** `read_url(generativelanguage.googleapis.com)`, `read_url(api.cartesia.ai)`, `read_url(api.sync.so)`, `command(ffmpeg)`, `command(ffprobe)`, `command(python3 .agents/skills/omni-render/scripts/…)`.
- **Keys:** the sandbox blocks `.env` files, so keys come from the environment; how they reach the sandbox is UNVERIFIED. An optional `.agents/mcp_config.json` can add GenMedia (Omni on Vertex), but terminal scripts stay the default because they are testable.

### 6.9 `render.json` fields (per run)

| Field | Content |
|---|---|
| `schema_version`, `slug`, `presenter_mode` | `ai`, `human` or `hybrid` |
| `model` | `{"id": "gemini-omni-1.1-flash", "api": "gemini", "fallback": "veo-3.1-fast-generate-preview"}` |
| `format` | `aspect_ratio "9:16"`, `source_fps 24`, `master {1080x1920, fps, conform}` |
| `passes` | `draft {resolution "360p", max_attempts 3}`, `final {resolution "1080p", max_attempts 2}`, `budget_usd` |
| `seed` | integer or null |
| `refs[]` | `id`, `path`, `kind` (presenter, product, set, frame0), `synthetic`, `source` |
| `audio` | `vo_source "cartesia"`, `vo_path`, `words_json`, `music: false` |
| `shots[]` | `n`, `mode` (ai, real, edit-only), `task`, `gen_duration_s`, `window_in_s`/`window_out_s`, `prompt` (assembled), `inputs[]` (tag → ref id), `dialogue` (to-camera only), `lipsync {required, audio_in_s, audio_out_s}`, `native_audio` (keep/drop), `qa[]`, `ai_fallback` |
| `disclosure` | `synthid: true`, `c2pa_check`, platform toggles copied from `posting.md` |

### 6.10 OMNI_CAPS

```json
{
  "OMNI_CAPS": {
    "checked": "2026-09-29",
    "model_ids": {"gemini_api_stable": "gemini-omni-1.1-flash", "gemini_api_preview": "gemini-omni-flash-preview",
                  "vertex_preview": ["gemini-omni-1.1-flash-preview", "gemini-omni-flash-preview"],
                  "veo_fallback": ["veo-3.1-generate-preview", "veo-3.1-fast-generate-preview", "veo-3.1-lite-generate-preview"]},
    "endpoints": {"gemini_api": "POST https://generativelanguage.googleapis.com/v1beta/interactions",
                  "vertex": "POST https://aiplatform.googleapis.com/v1beta1/projects/{PROJECT_ID}/locations/global/interactions",
                  "gemini_api_auth_header": "x-goog-api-key"},
    "clip_s": {"min": 3, "max": 10, "integer_only": true, "default": null}, "fps": 24,
    "extend": {"append_s": [3, 10], "max_total_s": 40, "context_s": 10, "uploaded_input_max_s": 10, "prepend_or_middle": false},
    "aspect_ratios": ["16:9", "9:16"], "aspect_default": "16:9",
    "resolutions": ["360p", "720p", "1080p", "4k"], "resolution_default": "720p", "upscaled": ["1080p", "4k"], "pixel_dims_9_16": null,
    "inputs": {"text": true, "image": true, "video": true, "audio_api": false, "max_images_per_prompt": 10, "image_inline_max_mb": 20,
               "video_refs_max": 3, "video_ref_max_s": 3, "video_ref_audio": "ignored", "edit_input_max_s": 10,
               "youtube_urls": false, "multi_video_reasoning": false},
    "tags": ["<FIRST_FRAME>", "<LAST_FRAME>", "<IMAGE_REF_N>", "<VIDEO_REF_N>", "<VIDEO_0>", "<PREVIOUS_VIDEO>",
             "[# Sources <ROLE>@ImageN]", "[# References <ROLE>@ImageN]"],
    "params": {"top_level": ["model", "input", "previous_interaction_id", "response_format", "generation_config", "background", "store", "stream"],
               "response_format": ["type", "aspect_ratio", "resolution", "duration", "delivery", "gcs_uri"], "delivery": ["inline", "uri"],
               "video_config.task": ["text_to_video", "image_to_video", "reference_to_video", "edit", "extend"],
               "generation_config.seed": "exists in API; Omni support unverified"},
    "unsupported": ["system_instruction", "temperature", "top_p", "stop_sequences", "negative_prompt",
                    "audio_reference_upload", "voice_editing", "provisioned_throughput_gemini_api"],
    "native_audio": {"always_on": true, "dialogue": true, "sfx": true, "music": true, "off_param": null},
    "lip_sync_to_external_audio": false, "lip_sync_reliable_s_single_speaker": 6, "languages_evaluated": ["en"],
    "pricing_usd": {"video_out_per_1m_tokens": 17.5, "input_per_1m_tokens": 1.5, "text_out_per_1m_tokens": 9.0,
                    "tokens_per_s": {"360p": 1931, "720p": 5792, "1080p": 8688, "4k": 17376},
                    "per_s": {"360p": 0.034, "720p": 0.101, "1080p": 0.152, "4k": 0.304}, "free_tier": false},
    "latency_s": {"typical": ">60 (Vertex note)", "p50": null, "p95": null, "draft_360p_speedup_max": 0.6}, "rate_limits": null,
    "retention": {"interactions_paid_days": 55, "files_api_hours": 48, "vertex_days": [7, 14]},
    "watermark": {"synthid": true, "c2pa_vertex": true, "c2pa_gemini_api": null},
    "regional_blocks_eea_ch_uk": ["edit_or_extend_uploaded_video", "minor_image_uploads", "personal_avatars"],
    "veo_3_1": {"durations_s": [4, 6, 8], "fps": 24, "refs_max": 3, "extend_step_s": 7, "extend_max_total_s": 148,
                "params": ["aspectRatio", "durationSeconds", "resolution", "personGeneration", "seed", "negativePrompt (Vertex)"],
                "per_s": {"standard": 0.40, "fast_720p": 0.10, "fast_1080p": 0.12, "lite_720p": 0.05}}
  }
}
```

### 6.11 Open unknowns (spike before coding)
1. Does Omni honour `generation_config.seed`? The Gemini API calls temperature unsupported, yet Vertex lists temperature/topP defaults for Omni 1.1 (docs disagree).
2. What are the default `duration` and the exact 9:16 pixel sizes per resolution?
3. Can an approved 360p take reach 1080p unchanged (an edit turn at a higher `resolution`), or does every final re-sample?
4. Do Gemini API MP4s carry C2PA? What are Omni's quotas and p50/p95 latency?
5. When will audio references (audio-driven lip-sync) reach the API, and does a silent "mouth moving" take (path D) lip-sync better than native dialogue?
6. Do Vertex's Veo safety codes apply to Omni? How do secrets reach Antigravity's sandboxed terminal? Do Knowledge Items have an authoring format?

## Sources
- **Gemini API:** [Omni guide](https://ai.google.dev/gemini-api/docs/omni) · [model page](https://ai.google.dev/gemini-api/docs/models/gemini-omni-flash) · [video overview](https://ai.google.dev/gemini-api/docs/video) · [Interactions reference](https://ai.google.dev/api/interactions-api) · [Interactions guide](https://ai.google.dev/gemini-api/docs/interactions) · [Files](https://ai.google.dev/gemini-api/docs/files) · [pricing](https://ai.google.dev/gemini-api/docs/pricing) · [Veo](https://ai.google.dev/gemini-api/docs/veo) · [Antigravity agent](https://ai.google.dev/gemini-api/docs/antigravity-agent)
- **Google Cloud:** [Omni 1.1](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/omni-1-1-flash) · [Omni preview](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/omni-flash-preview) · [text-to-video](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/generate-videos-from-text) · [references](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/generate-videos-from-references) · [extend](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/extend-videos) · [best practices](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/best-practice) · [prompt guide](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/video-gen-prompt-guide) · [responsible AI](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/responsible-ai-and-usage-guidelines) · [pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing) · [GenMedia MCP](https://github.com/GoogleCloudPlatform/vertex-ai-creative-studio/tree/main/experiments/mcp-genmedia)
- **Google DeepMind and product pages:** [Omni 1.1 blog](https://blog.google/innovation-and-ai/technology/developers-tools/build-with-gemini-omni-1-1-flash/) · [model card](https://deepmind.google/models/model-cards/gemini-omni-flash/) · [Omni page](https://deepmind.google/models/gemini-omni/) · [Omni prompt guide](https://deepmind.google/models/gemini-omni/prompt-guide/) · [Gemini app Omni](https://gemini.google/overview/video-generation/) · [avatars help](https://support.google.com/gemini/answer/16984474) · [Prohibited Use Policy](https://policies.google.com/terms/generative-ai/use-policy)
- **Antigravity:** [Rules](https://antigravity.google/docs/rules/) · [Workflows](https://antigravity.google/docs/ide/workflows/) · [Workflows→Skills](https://antigravity.google/docs/migration/workflows-to-skills/) · [Skills](https://antigravity.google/docs/skills/) · [Artifacts](https://antigravity.google/docs/artifacts/) · [Implementation Plan](https://antigravity.google/docs/implementation-plan/) · [Walkthrough](https://antigravity.google/docs/walkthrough/) · [Task Groups](https://antigravity.google/docs/tools/) · [Agent](https://antigravity.google/docs/agent/) · [Agent settings](https://antigravity.google/docs/agent-settings/) · [MCP](https://antigravity.google/docs/mcp/) · [Sandbox](https://antigravity.google/docs/sandbox/) · [Permissions](https://antigravity.google/docs/permissions/) · [Changelog](https://antigravity.google/docs/changelog/) · [forum: Knowledge Items](https://discuss.ai.google.dev/t/knowledge-feature-failure/129021)
- **Platforms and standards:** [YouTube AI disclosure](https://support.google.com/youtube/answer/14328491) · [TikTok AIGC](https://support.tiktok.com/en/using-tiktok/creating-videos/ai-generated-content) · [TikTok newsroom](https://newsroom.tiktok.com/more-ways-to-spot-shape-and-understand-ai-content) · [Meta labeling](https://transparency.meta.com/governance/tracking-impact/labeling-ai-content) · [Meta ads AI info](https://www.meta.com/help/artificial-intelligence/355108217670024/) · [PCMag on Meta self-disclosure](https://www.pcmag.com/news/meta-will-label-ai-generated-content-but-theres-a-catch) · [ITU-R BT.1359-1](https://www.itu.int/dms_pubrec/itu-r/rec/bt/R-REC-BT.1359-1-199811-I!!PDF-E.pdf)
- **Vendors and reviews:** [sync.so docs](https://sync.so/docs/introduction) · [invideo review](https://invideo.io/blog/gemini-omni-flash-review/) · [invideo lip-sync vs overlay](https://invideo.io/faq/should-i-use-lip-sync-or-voiceover-overlay-for-ai/) · [BuildFast review](https://blog.buildfastwithai.com/gemini-omni-1-1-flash-review-accuracy-price-is-it-worth-it-2026) · [MindStudio](https://www.mindstudio.ai/blog/gemini-omni-1-1-flash-video-model) · [fal guide](https://fal.ai/learn/tools/how-to-use-gemini-omni-flash-1-1) · [Atlas Cloud UGC workflow](https://www.atlascloud.ai/blog/tips/how-to-make-ai-ugc-ads)
- **Studies:** [T2V text-rendering benchmark, arXiv 2505.04946](https://arxiv.org/abs/2505.04946)
- **Internal:** [shots-cinematography.md](shots-cinematography.md) §4 · [short-form-virality.md](short-form-virality.md) §2, §6

Content was rephrased for compliance with licensing restrictions.
