# WS-TRENDS notes (branch ws/trends)

Trend intelligence as new files only: the `vsp/trends/` package, `trends-db-template/`, the `vsp-trends` skill, the `vsp-trends-daily.sh` cron script and these notes. No existing file was changed. Constants and their sources: [research/trend-discovery-rules.md](research/trend-discovery-rules.md).

## Design

- **Dataset.** A directory that is its own private git repo on branch `data`: `--dir` > `VSP_TRENDS_DIR` > `~/viral-trends-db`. Layout and privacy policy: `trends-db-template/README.md`.
  - Observations are append-only JSONL snapshots: one line per post, per source, per day.
  - Readers merge a post's snapshots by `obs_id` = sha1(`platform:post_id`)[:16]. The latest non-null value of each field wins, and `trend_keys` are unioned.
  - `post_id` is taken from the permalink when possible (the Instagram shortcode), so API rows and agent rows of the same reel merge.
  - Lines are compact, key-sorted JSON and writes are atomic, so re-runs are byte-identical.
- **Validation** (`schema.py`) rejects: missing required fields, bad enums (creative-vocab ids), `first_words` over 12 words, media/CDN URLs anywhere, instruction-like text in any free-text field (flagged, never stripped), future timestamps, off-platform or non-https permalinks, and unknown fields. A whole caption is an unknown field.
- **Scoring** (`score.py`):
  - `outlier_x` = views ÷ the creator's median. The baseline is ≥5 posts older than 7 days, taken from the inline creator block, else the creator snapshot, else the creator's other observations.
  - Fallbacks: `reach_x` (views ÷ followers), then the engagement proxy for rows without views.
  - `vph`, bands and tiers.
  - `inspiration_score` = saturating multiple × tier weight × recency (half-life 7 days) × replicability ÷ 5 × basis weight.
- **Lifecycle** (`lifecycle.py`):
  - One card per `trend_key` with ≥2 distinct creators. Anonymous hashtag rows count one creator per post.
  - Each card carries windowed creator counts, growth, stage, speed and jump-in advice.
  - `related` lists keys whose posts overlap ≥80%: the same trend's other elements (its sound and hashtags).
  - TikTok Creative Center signals attach to matching cards; keys seen only in signals go to `signals_only` ("verify first").
- **Synthesis** (`synth.py`):
  - 10 operators; `invent` carries a signature, a slot, a hypothesis and a Trial Reels test plan.
  - Score = evidence × velocity × novelty × feasibility.
  - One representative card per trend (format first), so a trend's sound and hashtags don't yield duplicate recipes.
  - Greedy per niche and lane, with novelty recomputed after each pick and at most 3 recipes per operator.
  - Recipes are vocab-mapped; an empty `hook_archetypes` list means "no evidence, no hook steering".
  - A synth run supersedes the unused recipes of its niches. Used recipes are kept for 180 days, and `usage/used.jsonl` is the durable novelty memory.
- **Compliance:**
  - Sources are official APIs plus human-scale observation only.
  - Whole captions and media are never stored.
  - YouTube rows and creators get `purge_after` = observed + 30 days, which a refresh extends. `purge` also scrubs digests and recipe evidence.
  - Vendor, own and legacy research-DB rows are skipped.

## Integration contract (keep these names)

```python
from vsp.trends import steer
steer.for_run(prompt, presenter=None, fmt=None, niche=None, concept=None,
              dataset_dir=None, recipe_id=None, today=None) -> dict | None
steer.brief_md(steer) -> str            # "" for None; starts "## TREND — what this video rides"
steer.mark_used(recipe_id, dataset_dir=None, script_sha=None) -> bool
vsp.trends.selfcheck() -> (ok, lines)   # hermetic, ~1 s
```

**`for_run` behaviour:**
- `recipe_id`:
  - `None` or `"auto"`: the best unused recipe of the niche's latest batch.
  - `"none"`: no steering.
  - an id: that recipe.
- It is read-only and never raises.
- It returns `None` when:
  - there is no dataset or recipe
  - the batch is older than 7 days
  - no recipe scores ≥ 0.05 (auto mode only)
  - nothing is feasible for the presenter
- Pass the pipeline's own `route()` niche and concept to skip re-routing. Otherwise it calls `vsp.router.route(prompt, pack=False)`.
- Ranking = score × concept fit × format fit.

What the pipeline should do with each key:

| key | use |
|---|---|
| `recipe_id` | record in `manifest.json` → `script_summary.trend_recipe_id`; after a passing run call `mark_used(recipe_id, script_sha=<script_sha256>)` |
| `title`, `operator`, `trend_keys`, `stage`, `score` | manifest + `trend.md`. `stage == "invented"`: post as Trial Reels, never as a normal post |
| `hook_archetypes` | preference order for the primary hook and the alternates (vsp.hooks): take the first one the maker can render that passes the gates. Empty = keep the maker's choice. Gates always win. Already filtered: human_only dropped for `presenter="ai"`, `proof-first` dropped, `price-anchor` only with a prompt price |
| `frame0_visual_type` | the primary opening's frame-0 visual; alternates must still differ in visual_type |
| `vibe` | a vsp.direction vibe override when valid for the lane; otherwise keep direction's pick and warn |
| `format`, `duration_s` | only when the user did not pass `--format` / `--duration` explicitly (the pipeline defaults are demo / 30) |
| `beats_note`, `audio_note`, `text_note`, `participation_note` | editor-facing notes in `direction.md` / `brief.md` / `posting.md` (not spoken script text). They are D46-safe (no link phrases) and free of BUNDLE_FORBIDDEN phrases |
| `originality` | the brief's "must be ours / changed" list (keep 2 of a trend's 4 elements, change 2) |
| `evidence` | `trend.md` only, never the script or captions. FIXTURE permalinks are dropped unless `VSP_FIXTURE_OK=1` (as gate 2 / D151 does) |
| `risk` | non-fatal pipeline warnings + `trend.md` |

**Suggested pipeline wiring:**
- Add a flag `--trend auto|none|<recipe_id>`, default `auto`; it is a no-op without a dataset.
- Add `--trends-dir DIR`, falling back to `VSP_TRENDS_DIR`.
- Write `trend.md` = `brief_md(steer)` next to `brief.md`.
- The self-test, evals and `vsp.improve` must run with `--trend none` (or `VSP_TRENDS_DIR` pointed at a missing dir), so scorecards stay reproducible.

## CLI

`python3 -m vsp.trends` with the global flags `--dir`, `--json` and `--today YYYY-MM-DD` (before or after the command). The commands:
- setup: `init [--git]`
- adding data: `add FILE|-`, `observe …`, `import-ingest [--db] [--days]`, `youtube --query Q [--region] [--max] [--days] [--niche] [--dry-run] [--fixture DIR]`, `tiktok-cc FILE`
- deriving: `score`, `lifecycle`, `synth [--niche] [--presenter] [--k] [--invent]`, `digest [--date]`
- reading: `recipes [--niche] [--top] [--id]`, `steer "<prompt>"`, `status`
- maintenance: `validate`, `watchlist-suggest [--min-x] [--cap] [--apply] [--config]`, `purge --creator|--source|--older-than|--expired [--platform] [--dry-run]`
- `selfcheck`

Exit codes:
- 0: ok
- 1: error (invalid or rejected input; for automated imports, only when nothing could be imported)
- 2: usage or configuration missing
- 3: nothing to do, or stopped by the YouTube quota

Canned YouTube responses for manual tries: `python3 -m vsp.trends.fixtures youtube DIR`.

## For the integrator

1. Add `"vsp.trends"` to `OPTIONAL_SELFCHECKS` in `vsp/selftest_cases.py`.
2. Wire `for_run` / `brief_md` / `mark_used` into `pipeline.py` as above. Add `trend.md` to the artifacts list and to the README outputs table.
3. `agent/hermes/config.yaml` → `terminal.env_passthrough`: add `VSP_TRENDS_DIR`, `VSP_YT_API_KEY` and `VSP_TRENDS_NICHES`.
4. `agent/README.md`:
   - `hermes -p vsp cron create "every day at 7:15am" --no-agent --script vsp-trends-daily.sh --deliver local --name vsp-trends-daily` (after vsp-feed-daily)
   - an agent job such as `"every day at 8am" "Follow the vsp-trends skill: steps (b), (c) and (f)" --skill vsp-trends`
   - The profile's `git push * main*` deny rule stays; the dataset pushes to `data`.
5. AGENTS.md: a fifth job row (`vsp-trends`, `python3 -m vsp.trends …`); rules 7 and 8 already cover it.
6. Optional: store Business Discovery `followers_count` in a reels column in vsp.ingest. `import-ingest` currently parses it from the `notes` summary.

## Known limits

- **Hashtag rows.** Instagram Hashtag Search rows have no handle and no views. They are unscored unless followers are known, and they count one creator per post.
- **Speed classes and retention.** Speed is measured over retained rows, and API rows expire after 30 days. A long-lived trend is recognised through agent- or user-observed rows (kept until purged).
- **Silence rule.** "No sighting for 14 days" is implied by growth ≤ 0.5: both windows are then empty, so growth = 0.
- **TikTok.** No official trend API: Creative Center lists are hand-copied aggregate signals, and individual TikTok posts come from human-scale observation.
- **Engagement baselines.** The micro and mid tiers are interpolated (grade A).
- **Unmergeable links.** Short links (vm.tiktok.com, youtu.be without an id) don't carry a post id, so they don't merge with the canonical permalink.
- **Heuristics.** Novelty is token Jaccard, not semantic similarity. Invented-trend signatures come from a fixed bank of 8 graphic/sound devices, picked deterministically. The format and vibe mappings from slugs and emotions are heuristic (grade A).
- **Quota day.** The YouTube quota day is a fixed UTC−8, never later than the real Pacific reset. The API's own 403 `quotaExceeded` still stops a run (exit 3).
- **Git history.** Purges clean the working tree only. Rewriting git history for deletion requests is a human task (README, Deletion).
- **Superseded recipes.** A recipe id disappears once its niche is re-synthesised unused, so `mark_used` on it returns False.
