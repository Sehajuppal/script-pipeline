# Agent runtime: Hermes Agent + Meta Model API (Muse)

Prepared 2026-09-28. Sources: Hermes Agent `main` at v0.21.5 (tag `v2026.9.24`, [releases](https://github.com/NousResearch/hermes-agent/releases)), docs and source; Meta developer docs (Terms updated 2026-09-18). Everything below was read in docs or source unless marked **UNVERIFIED**. I skipped the community mirror [mudrii/hermes-agent-docs](https://github.com/mudrii/hermes-agent-docs): last pushed 2026-05-18, it still describes v0.2.0.

**Bottom line**
1. **Hermes needs no plugin.** Ship `AGENTS.md` and `.agents/skills/viral-script-pipeline/SKILL.md`, run `hermes skills trust` once, and schedule with `hermes cron create … --skill … --workdir …`. Muse Code reads the same two paths.
2. **Meta is a built-in Hermes provider** (`meta-ai`: `https://api.meta.ai/v1`, key in `MODEL_API_KEY`). Stay on Standard-tier IDs; `-contributor` IDs let Meta train on your data.
3. **Hermes strips keys.** `OPENAI_API_KEY`, `MODEL_API_KEY` and `GH_TOKEN` are removed from every command it runs, so `vsp/llm.py` needs a neutrally named key variable.
4. **Our judge defaults break on Muse Spark.** It is a reasoning model, so a 200-token cap can return empty text; use ≥4,000. It rejects `stop`, `n>1`, `logprobs` and `reasoning_effort:"none"`.
5. **Muse Voice Transcribe has no word timestamps**, only per-turn ones. Word-level hook timing needs another step.

## A. Hermes Agent

### A1. Skills
- **Frontmatter** ([Creating Skills](https://hermes-agent.nousresearch.com/docs/developer-guide/creating-skills)):
  - `name`, `description`, `version`, `author`, `license`, `platforms: [macos, linux, windows]`
  - `metadata.hermes.{tags, category, related_skills, requires_toolsets, requires_tools, fallback_for_toolsets, fallback_for_tools, config[], blueprint}`
  - `required_environment_variables[]` (`name, prompt, help, required_for`), `required_credential_files[]`
  - Body sections: When to Use / Procedure / Pitfalls / Verification.
- **[agentskills.io](https://agentskills.io/specification) compatible**, but its experimental `allowed-tools` field is only logged by the [scanner](https://github.com/NousResearch/hermes-agent/blob/main/tools/skills_guard.py), never enforced.
- **Limits** ([source](https://github.com/NousResearch/hermes-agent/blob/main/tools/skill_manager_tool.py)):
  - name ≤64 chars matching `^[a-z0-9][a-z0-9._-]*$`; description ≤1,024 (house style ≤60).
  - SKILL.md ≤100,000 chars; each supporting file ≤1 MiB.
  - Linter warns past ~24k body chars or 60+ reference files. Name the skill in lowercase-hyphen form matching its folder to stay agentskills-valid.
- **Where skills live** ([Skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills)):
  - User: `~/.hermes/skills/<category>/<name>/SKILL.md`, with optional `references/ templates/ scripts/ examples/ assets/`.
  - Project: `<repo>/.hermes/skills/` or `<repo>/.agents/skills/`. Highest precedence, but loaded only after `hermes skills trust` (saved in `skills.trusted_project_dirs`). Scanned, quarantined if flagged, never edited by the curator.
  - Also `skills.external_dirs` (extra folders) and `skills.create_dir` (where new agent skills go).
- **Loading:** an index (name, description, category; ~3k tokens) is always in the prompt; `skill_view` loads the body, then single reference files. Each skill is a `/<name>` command; `hermes chat -s <name> -q "…"` preloads one; `${HERMES_SKILL_DIR}` expands to the skill's path.
- **Hub:** `hermes skills browse|search|inspect|install|check|update|audit|uninstall|publish`, `hermes skills tap add owner/repo`, or a raw `https://…/SKILL.md`. All installs are security-scanned.

### A2. Scheduled jobs
Sources: [Cron docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron); flags checked in [`cron.py`](https://github.com/NousResearch/hermes-agent/blob/main/hermes_cli/subcommands/cron.py).
- **Runtime:** the gateway daemon ticks every 60 s (`hermes gateway install`). Jobs live in `~/.hermes/cron/jobs.json`; `--deliver local` writes to `~/.hermes/cron/output/`.
- **Create:** via `/cron add`, plain language (the agent's `cronjob` tool), or:
  `hermes cron create "<schedule>" ["<prompt>"] [--skill X]… [--workdir /abs] [--script f] [--no-agent] [--monitor-script f] [--deliver …] [--model … --provider …] [--paused] [--name …]`
- **Manage:** `list | pause | resume | run | edit | remove | status`.
- **Schedules:** `in 30m`, `every 2h`, `weekdays at 9am`, 5-field cron, or an ISO timestamp.
- **Running a skill:** `--skill` (repeatable) loads it before the prompt.
- **Running a script:** `--script` must sit in `~/.hermes/scripts/`. Its stdout feeds the prompt, or is delivered as-is with `--no-agent` (empty = no message). Printing `{"wakeAgent": false}` skips the LLM for that tick.
- **Project context:** `--workdir` loads that folder's `AGENTS.md`, makes it the working directory, and enables its project skills if the repo is trusted.
- **Guardrails:** fresh session per run; cron can't create cron; pre-flight blocks a run (no tokens spent) if a key, a skill's required env var or a delivery target is missing; dangerous commands denied (`approvals.cron_mode: deny`); contributor-tier models refused. Per-job `enabled_toolsets` is settable only via the agent's tool.

### A3. Memory and context files
- **Memory** ([Memory](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory)):
  - `MEMORY.md` (2,200 chars) and `USER.md` (1,375 chars) sit in `~/.hermes/memories/`, one set per profile.
  - They are snapshotted at session start and edited only by the `memory` tool.
  - Past sessions are searchable via `session_search` (SQLite FTS5, `~/.hermes/state.db`).
- **Context files** ([Context Files](https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files)) are the supported way for a project to supply instructions:
  - One type loads, first match wins: `.hermes.md`/`HERMES.md` → `AGENTS.override.md` → `AGENTS.md` → `CLAUDE.md` → `.cursorrules`.
  - Inside git, `AGENTS.md` files from the root down to the working directory are merged; subfolder files are picked up as the agent touches them.
  - Size cap scales with the model's context window (floor 20,000 chars).
  - Files are scanned for injection patterns (e.g. "ignore previous instructions", `cat .env`, hidden HTML comments). A match blocks the file.
  - `SOUL.md` is read from `~/.hermes/` only.
- **For us:** `AGENT-BRIEF.md` is not auto-loaded, so ship it as `AGENTS.md`. Seeding memory by editing `MEMORY.md` directly is undocumented (**UNVERIFIED**); the docs suggest a skill for facts a recurring task needs. Use a dedicated profile (`hermes profile create vsp`, then `hermes -p vsp …`), since the docs warn against two agents sharing one Hermes home.

### A4. Model configuration
- **Built-in Meta provider** ([providers](https://hermes-agent.nousresearch.com/docs/integrations/providers), [plugin source](https://github.com/NousResearch/hermes-agent/blob/main/plugins/model-providers/meta-ai/__init__.py)):
  - Select with `hermes chat --provider meta-ai --model muse-spark-1.3`. Key goes in `~/.hermes/.env` as `MODEL_API_KEY` (aliases `META_API_KEY`, `META_MODEL_API_KEY`); `META_BASE_URL` overrides the endpoint.
  - It calls the Responses API. A source comment reports 93–99% prompt-cache hits there versus none on chat/completions (Hermes's own measurement; Meta's [caching docs](https://ai.developer.meta.com/docs/prompt-caching) say caching is automatic on both, so chat-side hits are **UNVERIFIED**).
  - It maps effort `none` to `minimal`, defaults to 16,384 output tokens, and sends images only on user turns.
- **Contributor-tier guard** ([Configuring Models](https://hermes-agent.nousresearch.com/docs/user-guide/configuring-models)):
  - Interactive selection asks you to confirm. Unattended runs refuse unless `security.allow_data_training_tiers_noninteractive: true`.
  - The plugin's default auxiliary model is `muse-spark-1.2-contributor`. Any `auxiliary.*` slot set to `meta-ai` must also set `model:`.
- **Any OpenAI-compatible endpoint:**
```yaml
model: {provider: custom, default: my-model, base_url: http://localhost:8000/v1, key_env: MY_KEY}
# or a named entry
providers: {glimmer: {api: http://localhost:8000/v1, transport: chat_completions}}
model: {provider: "custom:glimmer", default: muse-glimmer}
```
- Transports: `chat_completions`, `codex_responses`, `anthropic_messages`.
- Tool calling works if the server supports it: add `--jinja` on llama.cpp, or `--enable-auto-tool-choice --tool-call-parser …` on vLLM. Hermes wants ≥64K context per session.

### A5. Tools and safety
- **Toolsets:** `terminal`, `file`, `web`, `browser`, `vision`, `image_gen`, `skills`, `memory`, `cronjob`, `code_execution`, `delegation` ([Tools](https://hermes-agent.nousresearch.com/docs/user-guide/features/tools)); backends include local, Docker, SSH, Modal.
- **MCP** ([MCP](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp)): `mcp_servers:` in config.yaml (`command/args/env` for stdio, `url/headers` for HTTP), with per-server tool filters.
- **Sub-agents** ([Delegation](https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation)):
  - `delegate_task` runs up to 10 children in parallel, each optionally validated against an `output_schema`.
  - Settings: `delegation.{model, provider|base_url, max_iterations, worktree_isolation}`. With isolation on, each child works in `.worktrees/` on its own `hermes-subagent/<id>` branch.
  - `/review` spins up an independent reviewer of the last work product.
- **Approvals** ([Security](https://hermes-agent.nousresearch.com/docs/user-guide/security)):
  - `approvals.mode`: smart / manual / off. `cron_mode`, `single_query_mode`, `unattended_mode`: deny / approve.
  - `approvals.deny` globs apply even under `--yolo`; `command_allowlist` pre-approves commands.
- **Rollback and isolation:**
  - `checkpoints.enabled: true` snapshots before edits and destructive commands (`/rollback`).
  - `hermes -w -z "<task>"` runs one task in a throwaway worktree; it survives only if it has unpushed commits ([Worktrees](https://hermes-agent.nousresearch.com/docs/user-guide/git-worktrees)).
- **Key stripping** ([source](https://github.com/NousResearch/hermes-agent/blob/main/tools/environments/local_env_policy.py)): commands run without any provider key (incl. `OPENAI_API_KEY`, `MODEL_API_KEY`) or `GH_TOKEN`, and passthrough can't restore them. Pass our own keys under neutral names via `terminal.env_passthrough`.

### A6. Self-improvement loop
- **Background review:** after a turn, a forked review can save memory and create or patch skills (`skill_manage` create/patch/delete/write_file/remove_file).
  - Frequency: `memory.nudge_interval`, `skills.creation_nudge_interval`.
  - `/refine` forces a review; `/learn <path|url|text>` writes a skill from a source.
  - `skills.write_approval: true` and `memory.write_approval: true` stage writes for review (`/skills pending|diff|approve`).
- **Curator** ([Curator](https://hermes-agent.nousresearch.com/docs/user-guide/features/curator)) grades and prunes skills:
  - Runs every 7 days once idle ≥2 h, and tracks views, uses and patches per skill.
  - Unused 14 days → stale; 30 days → archived (never deleted). LLM merging is opt-in (`curator.consolidate`).
  - Commands: `hermes curator pin|backup|rollback|run --dry-run`.
  - Exempt: pinned skills, skills referenced by a cron job, hub skills and project skills.
- **[hermes-agent-self-evolution](https://github.com/NousResearch/hermes-agent-self-evolution)** (MIT, last commit 2026-06-17):
  - Uses DSPy + GEPA to evolve SKILL.md files: `python -m evolution.skills.evolve_skill --skill <name> --iterations 10 --eval-source synthetic|sessiondb`.
  - Only skill evolution ships; tool descriptions, prompts and code are planned.
  - Guardrails: the full test suite must pass, skills stay ≤15 KB, and changes go out as human-reviewed PRs.
  - It targets the Hermes repo (`HERMES_AGENT_REPO`). Using it on our repo's skill is **UNVERIFIED**.
- **For our repo:** change code only on branches or worktrees; gate on `python3 pipeline.py --self-test` plus `evals/scorecard.py compare`; merge by PR with branch protection on `main` (the docs say deny rules are not a sandbox).

## B. Meta Model API / Muse

### B1. Basics
| Item | Verified value |
|---|---|
| Base URL | `https://api.meta.ai/v1`; Anthropic SDK uses `https://api.meta.ai` ([Quickstart](https://ai.developer.meta.com/docs/quickstart)) |
| Auth | `Authorization: Bearer $MODEL_API_KEY`; keys look like `LLM\|…`. The OpenAI SDK won't read `MODEL_API_KEY` itself, so pass `api_key=` ([Auth](https://ai.developer.meta.com/docs/authentication), [SDKs](https://ai.developer.meta.com/docs/sdks)) |
| Endpoints | `/responses` (Meta's default; carries reasoning across turns, web search, background runs), `/chat/completions`, `/messages`, `/files`, `/models`, `/images/generations`, `/images/edits`, `/asr/transcribe`, `wss://api.meta.ai/v1/asr/realtime`, `/status`. A batch API is not documented (**UNVERIFIED**) |
| Model IDs | Standard: `muse-spark-1.3` (recommended), `muse-spark-1.2`, `muse-spark-1.1`. Contributor: `muse-spark-1.3-contributor`, `muse-spark-1.2-contributor` ([Models](https://ai.developer.meta.com/docs/models)) |
| Context | 1,048,576 tokens on every version; Meta's OpenCode config uses a 131,072-token output limit |
| Price per 1M tokens | Standard: $1.25 in, $0.15 cached in, $4.25 out. Contributor: $0.10 / $0.002 / $0.20, but Meta may train on your data ([Pricing](https://ai.developer.meta.com/docs/pricing-rate-limits)). Web search: $2.50 per 1k queries |
| Rate limits (per team) | Standard 3,000 RPM / 4M TPM; Contributor 100 RPM / 3M TPM; Muse Image 150 RPM. Quota comes back in `x-ratelimit-*` headers; back off with jitter on 429 |
| Availability | US-only public preview from July 2026 ([blog](https://dev.meta.ai/resources/blog/build-with-muse-spark)); generally available worldwide per Connect 2026 ([recap](https://developers.meta.com/blog/meta-connect-recap/)). The Terms still say "preview" |

### B2. Multimodal input
- **Images:** png/jpeg/gif/webp/ico as a URL, base64 data URL or `file_id`; ≤50 per request ([Images](https://ai.developer.meta.com/docs/image-understanding)).
- **Video: yes, mp4 only** ([Video/audio](https://ai.developer.meta.com/docs/video-understanding)):
  - Send an `input_video` (`video_url`, public or base64) or an uploaded `input_file`; Chat Completions uses a `video_url` part.
  - The model also hears the soundtrack.
  - Size: 50 MB inline, 1 GiB per upload, 100 GiB per team. Uploads never expire unless you set `expires_after` ([Files](https://ai.developer.meta.com/docs/file-handling)).
  - Maximum duration: **UNVERIFIED** (not documented).
- **Audio:** mp3/wav via `input_audio`. Audio quality on 1.3 is flagged as degraded, so use `muse-spark-1.2`, with ≥4,000 output tokens.

### B3. Muse Voice Transcribe
Sources: [guide](https://ai.developer.meta.com/docs/speech-to-text), [API reference](https://ai.developer.meta.com/docs/api-reference/voice/transcribe).
- **Endpoints:** model `muse-voice-transcribe-1.0`. Files go to `POST /v1/asr/transcribe?sessionId=…` (multipart: a `request` JSON part + `audio`). Live audio uses a WebSocket that authenticates in its first frame.
- **Input:** WAV only (mono, 16-bit PCM, 16/24 kHz); ≤32 MB and ≤10 min per request.
- **Modes:** `PUSH_TO_TALK` (default, one transcript), `ENDPOINTING` (split into turns), `DIARIZATION` (speaker labels `A`, `B`, valid within one session).
- **Output:**
  - JSON: `transcript`, `audioDurationMs`, `turns[{turnId, startMs, endMs, transcript, speaker}]`.
  - `Accept: text/event-stream` streams partial results (`partialMode: CUMULATIVE|DELTA`), each with `audioProcessedMs`.
- **Missing:** word-level timestamps, confidence scores, emotion detection.
- **Hints:** 25 languages; `languageBias` and `keywords` steer recognition.
- **Cost/limits:** $0.18 per audio hour; 128 concurrent streams, 16,000 streams per hour.

### B4. Muse Image
- **Endpoints:** `muse-image-1.0` via OpenAI-compatible `/v1/images/generations` and `/v1/images/edits`; multi-turn editing via the Responses API ([guide](https://ai.developer.meta.com/docs/image-generation)).
- **Parameters:** `n` 1–10; `size` "WxH" sets aspect ratio only, not pixels; `output_format` webp/png/jpeg; `response_format` `b64_json` or `url`.
- **Built-in search** is on by default. For product thumbnails, turn it off with `tool_enablement: {enable_web_search: false, enable_image_search: false}` (sent via `extra_body`).
- **Cost:** $0.01 per image.

### B5. Muse Glimmer
Sources: [Overview](https://ai.developer.meta.com/docs/muse-glimmer), [Get the model](https://ai.developer.meta.com/docs/muse-glimmer/get-the-model).
- **Model:** 30B dense, Apache-2.0. Input is text + image only (no video/audio); 128K default context.
- **Weights:** `meta-models/Muse-Glimmer-30B` (bf16, ~60 GB), plus GGUF builds.
- **Serving:**
  - vLLM ([guide](https://ai.developer.meta.com/docs/muse-glimmer/vllm)): image `vllm/vllm-openai:muse-glimmer`, flags `--enable-auto-tool-choice --tool-call-parser muse_glimmer --reasoning-parser muse_glimmer`, ~72 GB VRAM.
  - llama.cpp ([guide](https://ai.developer.meta.com/docs/muse-glimmer/llama-cpp)): `llama-server -m Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf --mmproj … -a muse-glimmer -c 131072 -np 1 --jinja`. The 17 GB quant fits in <24 GB VRAM; `--jinja` is required for tool calls.
  - Ollama ([blog](https://ollama.com/blog/muse-glimmer)): `ollama run muse-glimmer`, or `ollama launch hermes --model muse-glimmer`.
- **Capabilities:** tool calling is native. JSON-schema output on these servers is **UNVERIFIED**.

### B6. Muse Code
Sources: [overview](https://ai.developer.meta.com/docs/muse-code), [extending](https://ai.developer.meta.com/docs/muse-code/extending), [auth](https://ai.developer.meta.com/docs/muse-code/auth).
- **What it is:** Meta's terminal/CI coding agent. Install with `curl -fsSL https://dev.meta.ai/install.sh | sh`; the CLI is `muse`; default model `muse-spark-1.2`.
- **Headless:** `muse exec "<task>"`, with `--json` (JSONL events) and `--max-model-steps`. `--disable-approval` keeps the sandbox on; `--yolo` drops both.
- **Auth:** headless runs read **`META_API_KEY`**, not `MODEL_API_KEY`. Subscription keys work only inside Muse Code.
- **Project files:** reads `AGENTS.md` and `<repo>/.agents/skills/<id>/SKILL.md` once the workspace is trusted.
- **As a coding sub-agent:** viable with glue.
  - Hermes bundles Codex, Claude Code and OpenCode skills but no Muse Code skill. Wrap `muse exec --json` in a project skill.
  - Exit code 0 only means the run ended, so gate on our own tests.
  - Its sandbox keeps `.git` and `.agents` read-only ([Permissions](https://ai.developer.meta.com/docs/muse-code/permissions)), so Hermes should commit.

### B7. Structured output and tool calling
Sources: [Structured output](https://ai.developer.meta.com/docs/structured-output), [Tool calling](https://ai.developer.meta.com/docs/tool-calling), [Chat Completions](https://ai.developer.meta.com/docs/protocols/chat-completions).
- **JSON schema:** `response_format: {type: "json_schema", json_schema: {name, schema}}` on Chat, or `text.format` on Responses.
  - Decoding is constrained to the schema; `strict` only adds validation of the schema itself.
  - No recursive schemas; limits are nesting depth 10, 5,000 properties, 1,000 enum values.
- **Tools:** parallel calls are on by default; `tool_choice` must be `"auto"`; validate arguments yourself.
- **HTTP 400 on:** `stop`, `n>1`, `logprobs`, `logit_bias`, `prediction`, `verbosity`, `modalities`, `audio`, `web_search_options`, effort `"none"`.
- **Reasoning and sampling:** effort runs `minimal`–`xhigh`, plus `max` on Standard 1.3. Leave temperature at 1.0; `seed` is best-effort. Retry 503s after `Retry-After`.

### B8. Data use and policy for ad scripts
- **Terms** ([ToS](https://dev.meta.ai/legal/terms-of-service)):
  - You own inputs and outputs.
  - Standard content is not used for training. Contributor content may be, after de-linking steps, and can be used for safety review without them.
  - You carry any legal duty to label or disclose AI content.
- **Acceptable Use Policy** ([AUP](https://dev.meta.ai/legal/acceptable-use-policy)) bans, among other things:
  - fake reviews or engagement, presenting outputs as human-made, impersonation, or cloning a real person's voice or likeness without consent;
  - manipulative or subliminal techniques that distort behaviour;
  - removing watermarks or provenance labels;
  - agents that evade human oversight.
- **For us:** never present UGC-style testimonials as real reviews; disclose `--presenter ai` output where platforms or law require; audit RULES §65 against the manipulation clause; keep rulebook prompts on Standard tier. Whether Muse Image watermarks output is **UNVERIFIED**.

## C. Recommendations

### C1. Hermes → pipeline
**1. Context file.** Ship `AGENTS.md` (built from `AGENT-BRIEF.md`; avoid injection-looking phrases).

**2. Project skill.** Add `.agents/skills/viral-script-pipeline/SKILL.md`, readable by both Hermes and Muse Code:
```markdown
---
name: viral-script-pipeline
description: Run, gate and improve the viral script pipeline
version: 1.0.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [video, scripts, evals]
    requires_toolsets: [terminal]
---
# Viral script pipeline
## When to Use
Producing a bundle, or changing maker/gate/rule code.
## Procedure
1. `python3 pipeline.py --self-test` must pass before and after any change.
2. Generate: `python3 pipeline.py "<product>" --format demo --duration 30 --seed N`
3. Code changes: new branch; `python3 evals/scorecard.py run --repo <baseline-checkout> --label base`, `run --repo . --label cand`, then `compare`.
## Pitfalls
- Never weaken a gate to pass a script; fix the maker. Never edit shipped personas.
## Verification
Self-test green; scorecard compare shows no pass-rate regression.
```
- Put long RULES excerpts in `references/`.
- Don't declare the optional LLM key in `required_environment_variables`: if it's missing, cron pre-flight blocks the job.

**3. Profile and config.** Run `hermes profile create vsp` and `hermes -p vsp skills trust /abs/script-pipeline`, then use this profile `config.yaml`:
```yaml
model: {provider: meta-ai, default: muse-spark-1.3}
skills: {write_approval: true}
memory: {write_approval: true}
approvals: {cron_mode: deny, deny: ['git push --force*', 'git push * main*']}
checkpoints: {enabled: true}
delegation: {worktree_isolation: true}
terminal: {env_passthrough: [VSP_LLM_API_KEY]}
auxiliary: {background_review: {provider: meta-ai, model: muse-spark-1.3}}
```

**4. Cron jobs.** `~/.hermes/scripts/vsp-selftest.sh` should print nothing when green and the failure tail otherwise.
```bash
hermes -p vsp cron create "every day at 6am" --no-agent --script vsp-selftest.sh --deliver local --name vsp-selftest
hermes -p vsp cron create "every monday 9am" "Follow the viral-script-pipeline skill: take one open item from AGENTS.md, fix it on a new branch, open a PR only if self-test and scorecard compare pass." \
  --skill viral-script-pipeline --workdir /abs/script-pipeline --name vsp-improve --paused
```
- Trial the improvement job with `hermes cron run vsp-improve`, then `hermes cron resume vsp-improve`.
- The curator never touches project skills, so the repo skill won't be archived.
- `GH_TOKEN` is stripped, so `gh` must rely on its stored `gh auth login` credentials.

### C2. Pipeline LLM calls → Muse Spark
**Works today, manual runs only:** `VSP_LLM_PROVIDER=openai VSP_LLM_MODEL=muse-spark-1.3 VSP_LLM_URL=https://api.meta.ai/v1/chat/completions OPENAI_API_KEY=<key>`. Under Hermes it fails because `OPENAI_API_KEY` is stripped.

**`vsp/llm.py` changes:**
- (a) Read `VSP_LLM_API_KEY` first.
- (b) Raise `max_completion_tokens` to ≥4,000 and the timeout to ≥120 s.
- (c) Send `"reasoning_effort":"low"` and a `response_format` json_schema for `{winner: A|B|tie, reason}`.
- (d) Retry 429/503 with jittered backoff, honouring `Retry-After`.
- (e) Never send `stop`, `n` or `logprobs`; loop for multiple candidates.
- (f) Put fixed instructions first and send a stable `prompt_cache_key`, so repeat calls hit the cache.

**Model choice:** Standard tier whenever rulebook text is sent; local Glimmer (`http://localhost:8000/v1/chat/completions`, model `muse-glimmer`) as offline fallback; mock provider for tests.

### C3. Reel audio → Muse Voice Transcribe
1. Extract audio, splitting anything over 10 min: `ffmpeg -i reel.mp4 -vn -ac 1 -ar 24000 -c:a pcm_s16le -map_metadata -1 reel.wav`
2. Transcribe:
```bash
curl --fail-with-body "https://api.meta.ai/v1/asr/transcribe?sessionId=reel-<id>" \
  -H "Authorization: Bearer $MODEL_API_KEY" \
  -F 'request={"mode":"ENDPOINTING","model":"muse-voice-transcribe-1.0","audioEncoding":"WAV","keywords":["<brand>"]};type=application/json' \
  -F 'audio=@reel.wav'
```
3. **Hook:** `turns[0].transcript` with its `startMs`/`endMs` is enough for "hook within N seconds" checks.
4. **Word timing** isn't provided. Options:
   - Our own approximation (**UNVERIFIED** accuracy): stream with `Accept: text/event-stream` + `"partialMode":"DELTA"` and stamp each new chunk with its `audioProcessedMs`.
   - Run a local forced aligner (not evaluated here).
   - Muse Spark video input can describe on-screen hooks, but any timestamps it gives are model estimates.
5. **Housekeeping:** keep `sessionId` for support; a 30-s reel costs ~$0.0015.

Content was rephrased for compliance with licensing restrictions
