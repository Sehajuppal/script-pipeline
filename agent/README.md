# Running the pipeline under Hermes Agent (Meta Muse)

The pipeline is built to be operated and improved by an agent. Hermes (Nous
Research) reads `AGENTS.md` and the project skills in `.agents/skills/`;
Muse Code reads the same two paths.

## 1. One-time setup

```bash
git clone <this repo> ~/script-pipeline && cd ~/script-pipeline
python3 pipeline.py --self-test                 # must be green, no keys needed

hermes profile create vsp
cp agent/hermes/config.yaml ~/.hermes/profiles/vsp/config.yaml   # or merge
hermes -p vsp skills trust "$PWD"               # enables .agents/skills/*
mkdir -p ~/.hermes/scripts && cp agent/hermes/scripts/*.sh ~/.hermes/scripts/
chmod +x ~/.hermes/scripts/vsp-*.sh
```

Secrets go in the profile's `.env` (`~/.hermes/profiles/vsp/.env`). Use
these names — Hermes strips `MODEL_API_KEY`/`OPENAI_API_KEY`/`GH_TOKEN` from
commands, so the pipeline reads neutral ones (all listed in
`terminal.env_passthrough`):

```bash
MODEL_API_KEY=<Meta Model API key>        # for Hermes itself (meta-ai provider)
VSP_REPO=/abs/path/to/script-pipeline     # for the cron scripts
VSP_LLM_PROVIDER=meta
VSP_LLM_MODEL=muse-spark-1.3              # Standard tier, not -contributor
VSP_LLM_API_KEY=<same Meta key>           # for the pipeline's optional LLM calls
VSP_ASR_API_KEY=<same Meta key>           # optional: Muse Voice Transcribe
VSP_IG_ACCESS_TOKEN=<long-lived token>    # see docs/ws-data-notes.md §1
VSP_IG_USER_ID=<IG business account id>
VSP_VIRAL_DB=/abs/path/viral.db
VSP_TRENDS_DIR=/abs/path/viral-trends-db  # the private trends repo (below)
VSP_YT_API_KEY=<YouTube Data API v3 key>  # optional: official Shorts outliers
VSP_TRENDS_NICHES=gadgets,beauty,fitness  # niches the daily scan covers
```

Instagram access needs a Meta app with Facebook Login for Business,
`instagram_basic`, `instagram_manage_insights`, `pages_show_list`,
`pages_read_engagement` and the Instagram Public Content Access feature
(App Review + Business Verification). Full walkthrough: `docs/ws-data-notes.md`.
Then:

```bash
python3 -m vsp.ingest init-db
cp config/ingest.example.json config/ingest.json   # edit niches/hashtags/handles
python3 -m vsp.ingest doctor
```

**Trends database on GitHub** (v2.2):
1. Create a **private** repo, e.g. `viral-trends-db`.
2. Clone it to `$VSP_TRENDS_DIR` and use `data` as its working branch. The
   profile denies pushes to `main`; data never needs review.
3. Initialise it:

```bash
git clone https://github.com/<you>/viral-trends-db.git "$VSP_TRENDS_DIR"
git -C "$VSP_TRENDS_DIR" checkout -b data
python3 -m vsp.trends init --dir "$VSP_TRENDS_DIR"      # layout: trends-db-template/README.md
git -C "$VSP_TRENDS_DIR" add -A && git -C "$VSP_TRENDS_DIR" commit -m "trends db" && git -C "$VSP_TRENDS_DIR" push -u origin data
```

The dataset holds the following, and never media files, whole captions or
private data:
- permalinks
- public metrics
- hook excerpts of 12 words or fewer
- the agent's own analysis

YouTube rows expire after 30 days unless refreshed (Developer Policies).
Delete on request with `python3 -m vsp.trends purge --creator <handle>`.

## 2. Schedules

```bash
hermes -p vsp cron create "every day at 6am" --no-agent --script vsp-selftest.sh --deliver local --name vsp-selftest
hermes -p vsp cron create "every day at 6:30am" --no-agent --script vsp-feed-daily.sh --deliver local --name vsp-feed-daily
hermes -p vsp cron create "every 1h" --no-agent --script vsp-feedback-hourly.sh --deliver local --name vsp-feedback-hourly
hermes -p vsp cron create "every 12h" --no-agent --script vsp-variants.sh --deliver local --name vsp-variants
hermes -p vsp cron create "every day at 7:15am" --no-agent --script vsp-trends-daily.sh --deliver local --name vsp-trends-daily
hermes -p vsp cron create "every day at 8am" \
  "Follow the vsp-trends skill: add promising small and medium creators to the watchlist, analyse today's top outliers by hand (at most 30 posts per platform, official sources or links I sent), log them with vsp.trends observe, rerun synth and digest, push the dataset to branch data, then summarise the digest: what is rising, which small creators popped and why, and the 3 recipes to post this week." \
  --skill vsp-trends --workdir "$VSP_REPO" --name vsp-trends-scan
hermes -p vsp cron create "every day at 7am" \
  "Follow the vsp-feedback skill: run learn and report, then summarise what changed in learned/PERFORMANCE.md and which alternate openings learned/VARIANTS.md says to graduate." \
  --skill vsp-feedback --workdir "$VSP_REPO" --name vsp-learn
hermes -p vsp cron create "every monday 9am" \
  "Follow the vsp-self-improve skill: run a full cycle, then take the top task from learned/TASKS.md, work it on a new branch, and open a PR only if 'python3 -m vsp.improve verify' prints ACCEPT." \
  --skill vsp-self-improve --workdir "$VSP_REPO" --name vsp-improve --paused
```

Trial the improvement job with `hermes -p vsp cron run vsp-improve`, review
its PR, then `hermes -p vsp cron resume vsp-improve`.

## 2b. Hand-off to the Google Antigravity render agent (Gemini Omni + Cartesia)

Every run writes `render.json`, `voice_plan.json` and `render.md` next to
`brief.md`. On the Antigravity side:
1. Copy `antigravity/AGENTS.md` and `antigravity/.agents/` into the
   Antigravity workspace once (details in `antigravity/README.md`: env keys,
   sandbox permissions, cost).
2. For each video, copy the run's outdir to `jobs/<slug>/` in that workspace.
3. Ask the render agent to "render jobs/<slug>".

Rules for the hand-off:
- For a fully generated video, run the pipeline with `--presenter ai`.
- A human-lane bundle keeps its person shots `real` (the creator films
  them). `--ai-broll` lets Antigravity generate faceless product B-roll,
  which turns the AI labels on.
- `--voice-lane creator_clone --consent-ref <id>` voices a consenting
  creator's own Cartesia clone.

## 3. How the self-improvement loop works

```
 Instagram Graph API ──► vsp.ingest ──► viral.db ──► research_pack.json ─┐
 (latest reels per niche)                                                │
                                                                         ▼
 your posted reels ──► vsp.feedback ──► learned/priors.json ──► viral_script_maker
 (skip rate, watch time,   │                                      ▲   (hook choice)
  shares, saves;           └──► variants ──► learned/VARIANTS.md  │
  Trial Reels of the            (A/B of the alternate openings,   │
  alternate openings)            #vsp-<sha8><letter>)             │
                                                                  │
 vsp.improve cycle: measure (golden + holdout + capability)       │
   → diagnose (DIAGNOSIS.md, TASKS.md)                            │
   → evolve hook templates (MAP-Elites + optional Muse Spark) ──► learned/hook_packs/
   → promote: full A/B scorecard, paired stats, holdout ─── ACCEPT → approved
   → LEDGER.md
 code tasks: agent or Muse Code on a branch → vsp.improve verify → PR (human merges)
```

Guardrails: gates/rules can't be weakened by automation (`verify` rejects
it); holdout and audit-only rubric checks detect metric gaming; the LLM is
advisory only; nothing reaches `main` without a human-merged PR.
