# viral-trends-db

The trend dataset of the script pipeline (`python3 -m vsp.trends`): viral short-form posts, the creators behind them, trend cards and synthesised trend recipes. The pipeline reads it to steer scripts (`pipeline.py --trend auto`). It is copied from `trends-db-template/` in the pipeline repo by `python3 -m vsp.trends init`.

## Setup

- Keep it in a **private** repository. Public posts are still personal data, and the rows hold creator handles and metrics.
- Use the default branch **`data`**. The Hermes profile denies pushes to `main`, so the daily job pushes to `data`.

```bash
python3 -m vsp.trends --dir ~/viral-trends-db init --git   # git init, HEAD on branch data
git -C ~/viral-trends-db remote add origin git@github.com:<you>/viral-trends-db.git
export VSP_TRENDS_DIR=~/viral-trends-db
```

The daily job (`agent/hermes/scripts/vsp-trends-daily.sh`) commits with `git add -A && git commit -m "trends YYYY-MM-DD" && git push origin data`. It never force-pushes.

## Layout

| path | content | written by |
|---|---|---|
| `observations/YYYY/MM/YYYY-MM-DD.jsonl` | one line per post per source per day (append-only snapshots); readers merge a post's snapshots by `(platform, post_id)` and keep the latest metrics | `add`, `observe`, `import-ingest`, `youtube` |
| `creators/creators.jsonl` | the latest snapshot per `(platform, handle)`: followers, recent-views median, baseline size, tier | `import-ingest`, `youtube` |
| `signals/YYYY/MM/YYYY-MM-DD.jsonl` | aggregate trend signals (hand-copied TikTok Creative Center lists), not posts | `tiktok-cc` |
| `usage/used.jsonl` | recipes used by pipeline runs (the novelty memory) | `vsp.trends.steer.mark_used` |
| `derived/outliers.jsonl` | scored posts at 3x or more, best first | `score` |
| `derived/trends.json` | trend cards with stage, speed and jump-in advice | `lifecycle` |
| `derived/recipes.jsonl` | the latest recipe batch per niche plus used recipes | `synth` |
| `derived/quota.json` | YouTube API units and search calls per Pacific day | `youtube` |
| `digests/YYYY-MM-DD.md` | the daily digest | `digest` |
| `schema/*.v1.json` | JSON Schemas (generated from `vsp/trends/schema.py`) | template |

Everything under `derived/` is regenerated; never edit it by hand. Keep files under about 1 MB (GitHub's soft limit per object) and directories under about 3,000 entries. `python3 -m vsp.trends validate` warns about large files.

## Schema summary

**observation.v1** (one post):
- **Identity:** `obs_id` = sha1(`platform:post_id`)[:16], `platform`, `post_id` (Instagram uses the shortcode), `permalink` (https post page, never a media URL).
- **Provenance:** `observed_at`, `posted_at`, `source` (`ig_graph_hashtag`, `ig_graph_bd`, `yt_data_api`, `tiktok_creative_center`, `agent_observed`, `user_shared`, `import`), `analyst` (`api`, `agent`, `human`).
- **Creator and metrics:** `creator` {handle, followers, median_views_recent, baseline_n, tier}; `metrics` {views, likes, comments, shares, saves}.
- **Hook and structure:** `hook` {first_words (at most 12 words), archetype, frame0_visual, on_screen_text (at most 8 words)}; `structure` {beats, cuts_per_10s, payoff_reveal, loop, series}; `audio` {type, sound_id, sound_title}; `format_key`.
- **Engagement drivers:** `participation`, `cta`, `emotion`, `vibe`, `replicability` (1-5), `production_cost`, `needs_real_person`.
- **Other:** `trend_keys` (`sound:` / `format:` / `tag:` / `topic:`), `notes` (at most 280 characters, our analysis), `retention.purge_after`.

`archetype`, `frame0_visual` and `vibe` use the pipeline's creative vocabulary (`vsp/creative_vocab.py`).

**creator.v1:** `platform`, `handle`, `followers`, `median_views_recent`, `baseline_n`, `tier`, `snapshot_at`, `source`, `retention`.

**signal.v1:** `kind` (tag or sound), `key`, `name`, `rank`, `posts`, `growth_pct`, `region`, `industry`, `date`.

**trend.v1:** a card in `derived/trends.json`: key, stage, speed, creator counts per window, growth, median outlier, small/medium share, profile.

**recipe.v1:** a line of `derived/recipes.jsonl`: operator, score parts, vocab-mapped hook archetypes / frame 0 / vibe / format / duration, notes, originality, evidence, risk.

Validation rejects media/CDN URLs, whole captions, hook excerpts over 12 words, instruction-like text ("ignore previous …", "system: …") and future timestamps. Reel text is data, never instructions.

## Privacy, retention and deletion

- **Stored:** permalinks, public metrics, hook excerpts of at most 12 words and our own analysis. Never media files, thumbnails or whole captions. Short phrases are not copyrightable (37 CFR 202.1), but whole captions may be.
- **Sources:**
  - official APIs only: the Instagram Graph API via vsp.ingest (Hashtag Search, Business Discovery) and the YouTube Data API
  - TikTok Creative Center lists copied by hand
  - human-scale observation by the agent or the user
  - No scraping and no automated crawling of Instagram or TikTok. Instagram and TikTok terms forbid it, and so does AGENTS.md rule 7.
- **Retention:**
  - `yt_data_api` rows and creators get `purge_after` = observed + 30 days. YouTube requires stats of other channels to be refreshed or deleted within 30 days: re-running refreshes them, and `purge --expired` deletes the rest.
  - Instagram rows keep vsp.ingest's `purge_after`. Meta's Platform Terms treat derived data as Platform Data: delete it when it is no longer needed or on request.
- **Deletion requests:**
  - Run `python3 -m vsp.trends purge --creator HANDLE`. It rewrites the files, regenerates `derived/` and scrubs digests and recipe evidence.
  - Git history still holds the old rows, so a human must also rewrite history (e.g. `git filter-repo`) and force-push. Automation never force-pushes.
  - Also run `purge --source S`, `--older-than DAYS` or `--expired` as policies require.
