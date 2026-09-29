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

## 2. Schedules

```bash
hermes -p vsp cron create "every day at 6am" --no-agent --script vsp-selftest.sh --deliver local --name vsp-selftest
hermes -p vsp cron create "every day at 6:30am" --no-agent --script vsp-feed-daily.sh --deliver local --name vsp-feed-daily
hermes -p vsp cron create "every 1h" --no-agent --script vsp-feedback-hourly.sh --deliver local --name vsp-feedback-hourly
hermes -p vsp cron create "every 12h" --no-agent --script vsp-variants.sh --deliver local --name vsp-variants
hermes -p vsp cron create "every day at 7am" \
  "Follow the vsp-feedback skill: run learn and report, then summarise what changed in learned/PERFORMANCE.md and which alternate openings learned/VARIANTS.md says to graduate." \
  --skill vsp-feedback --workdir "$VSP_REPO" --name vsp-learn
hermes -p vsp cron create "every monday 9am" \
  "Follow the vsp-self-improve skill: run a full cycle, then take the top task from learned/TASKS.md, work it on a new branch, and open a PR only if 'python3 -m vsp.improve verify' prints ACCEPT." \
  --skill vsp-self-improve --workdir "$VSP_REPO" --name vsp-improve --paused
```

Trial the improvement job with `hermes -p vsp cron run vsp-improve`, review
its PR, then `hermes -p vsp cron resume vsp-improve`.

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
