# WS-DATA notes — Instagram ingestion + the performance-feedback loop

Two packages, stdlib only (Python ≥ 3.9), both runnable by Hermes:

- **`vsp.ingest`** writes the latest Instagram Reels into the research DB (`viral.db`) using official APIs only, and `research_bridge.py` turns them into the research pack.
- **`vsp.feedback`** learns from *your* posted reels. It writes `learned/priors.json` (read by the maker's hook-family choice) and `learned/PERFORMANCE.md`.

Background: [research/instagram-data-access.md](research/instagram-data-access.md) (endpoints, limits, the §9 recipe) and [research/agent-runtime.md](research/agent-runtime.md) §B3 (Muse Voice Transcribe).

## 1. Setup

### Meta side (once)
1. **Account.** Make the posting Instagram account a Business or Creator account and link it to a Facebook Page. Complete **Business Verification** in Business Manager.
2. **App.** Create a Meta app (type Business) at developers.facebook.com. Add **Facebook Login for Business** and **Instagram** (Instagram API with Facebook Login). The code pins Graph **v26.0**.
3. **Permissions:** `instagram_basic`, `instagram_manage_insights`, `pages_show_list`, `pages_read_engagement`. Add `business_management` if the Page comes to you through Business Manager.
   - Standard Access covers accounts that have a role on the app. That is enough for own media and insights. Business Discovery on Standard Access is UNVERIFIED.
4. **Instagram Public Content Access** (needed for Hashtag Search). Request it under App Review → Permissions and Features. It needs App Review *and* Business Verification.
   - **App Review requires a testable UI:** a login button, a screencast per permission, use-case text (frame it as "developing the business's content strategy") and one successful call.
   - Apps without a testable UI can only get `instagram_basic` and `instagram_manage_comments`, so ship a small dashboard.
   - Until review passes, `watchlist` (Business Discovery), `own`, `pull` and `import` all work. `hashtags` fails with a message that names the missing feature.
5. **Token.**
   - In Graph API Explorer, pick your app, add the four permissions and generate a User Token.
   - Exchange it for a 60-day token: `GET /v26.0/oauth/access_token?grant_type=fb_exchange_token&client_id=…&client_secret=…&fb_exchange_token=…`.
   - Refresh it around day 50 by re-running the exchange. Alternatively, use a Page token minted from a long-lived user token, which has no fixed expiry.
   - `doctor` warns when fewer than 10 days are left (this needs `VSP_IG_APP_ID` and `VSP_IG_APP_SECRET`).
6. **Instagram user id:** `GET /v26.0/me/accounts?fields=name,instagram_business_account{id,username}`. Use `instagram_business_account.id`, not the Page id.

`python3 -m vsp.ingest doctor` checks all of the above and prints the exact missing steps, in order.

### Repo side
```bash
cp config/ingest.example.json config/ingest.json   # niches -> hashtags (≤3/niche, ≤25 total) + benchmark handles
export VSP_VIRAL_DB=~/workspace/viral-research/viral.db
python3 -m vsp.ingest init-db       # additive migration of the research agent's DB (or a new one)
python3 -m vsp.ingest doctor
```

## 2. Env vars

| var | use |
|---|---|
| `VSP_IG_ACCESS_TOKEN` | long-lived token (required for API jobs; never printed) |
| `VSP_IG_USER_ID` | Instagram Business account id (required) |
| `VSP_IG_GRAPH_VERSION` | default `v26.0`; env > config `graph_version` > default |
| `VSP_IG_APP_SECRET` / `VSP_IG_APP_ID` | optional: `appsecret_proof` on every call / token-expiry check |
| `VSP_VIRAL_DB`, `VSP_RESEARCH_PACK`, `VSP_LEARNED_DIR`, `VSP_OUTPUTS` | paths (see `vsp/config.py`) |
| `VSP_INGEST_CONFIG` | default `config/ingest.json` |
| `VSP_EXCLUDE_VENDOR=1` | drop `vendor:*` rows from aggregates and the pack (same as `"vendor_rows": "exclude"`) |
| `VSP_ASR_API_KEY` (falls back to `VSP_LLM_API_KEY`) | Muse Voice Transcribe. Hermes strips `MODEL_API_KEY`, so it is never read |
| `VSP_TRANSCRIBE=1/0`, `VSP_FFMPEG`, `VSP_ASR_URL` | force transcription on or off / ffmpeg path / endpoint override |
| `VSP_FEEDBACK_SEARCH` | extra folders (`:`-separated) that `link --auto` searches for `manifest.json` |

Under Hermes, list the `VSP_IG_*`, `VSP_ASR_API_KEY` and `VSP_LLM_API_KEY` vars in `terminal.env_passthrough` of the `vsp` profile.

## 3. CLI

Exit codes:
- `0`: ok
- `1`: failure
- `2`: not configured, or a config / token / permission problem (a human must act)
- `3`: stopped early by rate limits (data kept; the next run resumes)

`--json` gives machine-readable output.

```
python3 -m vsp.ingest init-db | doctor [--offline] | status | selfcheck
python3 -m vsp.ingest hashtags [--niche N] [--recent]   # Job A: top (+recent) reels per hashtag
python3 -m vsp.ingest watchlist [--niche N] [--force]   # Job A: Business Discovery, once/handle/day
python3 -m vsp.ingest own [--since TS]                  # Job B: register own Reels + #vsp- tags
python3 -m vsp.ingest insights [--days 3 | --day D]     # daily account insights
python3 -m vsp.ingest import FILE --source import:<name>|vendor:<name> [--niche N] [--own]
python3 -m vsp.ingest classify [--reclassify] [--no-llm]
python3 -m vsp.ingest transcribe [--own-renders | --file F --media-id ID]
python3 -m vsp.ingest refresh-pack                      # classify pending rows, then research_bridge.refresh()
python3 -m vsp.ingest purge [--vendor] [--source S] [--media-id ID] [--dry-run]

python3 -m vsp.feedback link --media-id ID --manifest outputs/<slug>/manifest.json [--trial]
python3 -m vsp.feedback link --auto [--search DIR]
python3 -m vsp.feedback pull [--no-link] | learn | report | status | selfcheck
```

Job details:
- **`hashtags`:**
  - Plans the configured tags against the rolling-7-day budget. It syncs `recently_searched_hashtags` first, so hashtags searched by other tools on the account are counted. Refused tags are never called.
  - Reads `top_media`, at most 2 pages of 50, and with `--recent` also `recent_media`.
  - Keeps `VIDEO` + `/reel/` items under 7 days old.
- **`watchlist`:** keeps Reels under 30 days old. The notes carry the views ÷ followers outlier score.
- **Both** upsert on `(platform, media_id)`, then classify new rows.

### The caption tag (closed loop)
Put **`#vsp-<first 8 hex chars of script_sha256>`** in the reel's caption, for example `#vsp-0a1b2c3d`.
- `script_sha256` is the sha256 of the run's `script.json` bytes. It is in `manifest.json` → `script_summary.script_sha256`, and also in `outputs["script.json"]`.
- `own` stores the tag as `reels.script_slug`. `link --auto` (which `pull` runs first) finds the matching `manifest.json` under `outputs/` and links the two.
- Instagram treats only `#vsp` as the hashtag. The suffix is parsed from the raw caption and stripped from research hooks.
- Trial Reels have no read-side flag, so record them with `link … --trial`.

## 4. Hermes schedule (suggested)

Scripts live in `~/.hermes/scripts/`. Wrap each body so it prints nothing when green and the failing output otherwise; `--no-agent` then delivers only problems:

```sh
#!/bin/sh
cd /abs/script-pipeline || exit 1
out=$( { BODY; } 2>&1 ) || { rc=$?; printf '%s\n' "$out" | tail -40; exit $rc; }
```

| script | schedule | body |
|---|---|---|
| `vsp-feed-daily.sh` | `every day at 6am` | `python3 -m vsp.ingest hashtags && python3 -m vsp.ingest watchlist && python3 -m vsp.ingest refresh-pack` |
| `vsp-recent.sh` (optional) | `every 8h` | `python3 -m vsp.ingest hashtags --recent` (repeats inside the 7-day window are free) |
| `vsp-own-hourly.sh` | `every 1h` | `python3 -m vsp.ingest own && python3 -m vsp.feedback pull` |
| `vsp-learn-daily.sh` | `every day at 7am` | `python3 -m vsp.ingest insights && python3 -m vsp.feedback learn && python3 -m vsp.feedback report` |
| `vsp-hygiene-weekly.sh` | `every monday 5am` | `python3 -m vsp.ingest purge && python3 -m vsp.ingest doctor` |

```bash
hermes -p vsp cron create "every day at 6am" --no-agent --script vsp-feed-daily.sh --deliver local --name vsp-feed-daily
```

An exit code of 3 just means "resume next tick". An exit code of 2 needs a human, so run `doctor`.

## 5. Schema changes (`vsp/ingest/db.py`, schema v1, additive + idempotent)

- **`reels` + §9 columns:** `platform` (default `instagram`), `media_id`, `source`, `source_query`, `media_type`, `media_product_type`, `media_audio_type`, `posted_at`, `caption`, `views`, `comments`, `shares`, `saves`, `transcript`, `hook_source`, `is_own`, `is_trial`, `script_slug`, `purge_after`.
- **`reels` + bookkeeping:** `hook_category`, `hook_family`, `classified_by`, `last_seen_at`.
- **Indexes:** `UNIQUE reels_media(platform, media_id)`. Legacy rows keep `media_id NULL`, which never collides.
- **New tables:**
  - `reel_metrics` (§9 DDL + `source`)
  - `posts` (the script summary per linked reel + `hook`, `candidate_seed`)
  - `hashtag_budget`
  - `meta` (`schema_version`, last runs, per-handle spacing)
  - `account_metrics`
  - `ingest_aggregates` (which `hooks`/`patterns` rows vsp.ingest owns)
- **Legacy tables are untouched.** `hooks`/`patterns` get *additional* rows written by `classify`, so `research_bridge` rankings include ingested reels.
  - Re-runs update these rows in place and never double count, even after `VACUUM` renumbers `hooks` rowids.
  - Rows adopted from the research agent (`hook_source='curated'`) are never re-labelled or re-counted.
- **Readers:** `make_shotlist.niche_references` and `research_bridge` select named columns and work unchanged. **External writers must use named-column INSERTs** into `reels` after migration.
- **Pack (`research_bridge.py`)**, with the ingest columns present:
  - `fresh_hook_lines` are ranked by views, then likes, across every niche.
  - New keys: `top_reels` per niche (`url`, `views`, `likes`, `hook_text`, …) and `ingest`.
  - Your own reels never feed rankings. Every legacy key is kept, and a legacy DB builds the identical pack.
  - Paths are resolved at call time, and the keep-last-good guard is unchanged.
- **`learned/priors.json`:** exactly the `learned/README.md` v1 schema, with `metric: "composite"`. For labels, see the `vsp/feedback.py` docstring:
  - hook_rate = 1 − skip rate
  - watch_ratio = avg watch ÷ duration
  - share_rate = shares ÷ reach, and save_rate = saves ÷ reach
  - success = composite (mean within-account z-score) ≥ the median of the last 60 posts
  - posteriors: Beta(1,1) per (maker niche, hook family), plus `global`

## 6. Compliance notes

- **Official routes only.** Everything uses Instagram API with Facebook Login for Business. There is no scraping and no oEmbed-derived analytics.
- **Limits are enforced before any call.**
  - Hashtags: 30 unique per rolling 7 days (local cap 25, 5 spare), synced with `recently_searched_hashtags`.
  - `X-App-Usage` / `X-Business-Use-Case-Usage`: back off at ≥ 80 %, stop at ≥ 95 %.
  - Retries use jittered backoff and honour `Retry-After`.
  - Tokens never appear in errors or logs. `appsecret_proof` is sent when the secret is set.
- **Media is never stored.**
  - `media_url` exists only in memory. Transcripts are text only, and the 3.5-second WAV is deleted in a `finally`.
  - ASR runs only on your own renders or on items whose `media_url` the API returned. It is off unless configured.
  - Sending clips to Meta's ASR is processing Platform Data. Confirm this fits your approved use case, and stay on Standard tier.
- **Retention and deletion.**
  - Others' rows get `purge_after` = last seen + 30 days, and `purge` enforces it.
  - Deleted own media is detected by `pull` and purged together with its metrics and link.
  - `purge --media-id` handles deletion requests. Publish a privacy policy.
- **Vendor data.**
  - Imports must be tagged `import:<name>` (your own exports, official-API suites) or `vendor:<name>`.
  - Known scrapers are refused under `import:*`. `vendor:*` imports print the Terms warning from research doc §7.
  - Exclude vendor rows via config/env, or delete them with `purge --vendor`. The legacy `make_shotlist` reader cannot filter them.
  - Keep vendor data out of the Meta app and get legal review first.
- **Use Platform Data only for the approved purpose** (content strategy for this business).

## 7. Verified offline vs. needs a real token

**Verified offline.** `python3.9|3.12 -m vsp.ingest selfcheck` (79 checks) and `-m vsp.feedback selfcheck` (28 checks) use canned `tests/fixtures/ig/*.json` over an injectable transport, a temp DB, temp learned dir and temp pack, with the network disabled. They cover:
- migration and idempotency
- pagination limits and dedupe
- budget refusal before any call, the placeholder sync and the 7-day window
- usage backoff, 5xx retry and the rate-limit stop
- the §9 normalization, and `media_url` never persisted
- upsert idempotency and legacy-row adoption
- Business Discovery field-drop retry
- importers (vendor warning, scraper refusal, dedupe, CSV, own export → snapshot)
- classification (maker `HOOKS` read at runtime, aggregates VACUUM-safe, LLM path with fallbacks)
- transcription (no-op without key/ffmpeg, multipart shape, audio deleted)
- pack refresh (ranking, `top_reels`, vendor exclusion, keep-last-good, repo pack untouched)
- purge, doctor (offline and online via the transport), CLI
- the closed loop in both: link (summary and `script.json` fallback, `--auto`, `--trial`), checkpointed pull, unsupported-metric retry, vanished media, own-render transcription
- labels, the priors schema (and `vsp.priors` when present), and the report
- `make_shotlist.niche_references` on the migrated DB

**Needs a real token or account (UNVERIFIED here):**
- live field availability: `media_product_type` / `media_audio_type` in Business Discovery, `view_count`, and hidden `like_count`
- the units of `ig_reels_avg_watch_time` (assumed ms) and `reels_skip_rate` (percent vs fraction is normalised per account)
- the insight lag and empty responses; metric names accepted on v26.0 (unsupported ones are dropped automatically)
- the `recently_searched_hashtags` semantics; Public Content Access approval; the real usage-header values
- the `follows_and_unfollows` breakdown shape; token expiry via `/debug_token`; system-user tokens for hashtag endpoints
- the Muse ASR response with a real key; ffmpeg against signed CDN URLs (ffmpeg is not installed in this sandbox)
- App Review itself
