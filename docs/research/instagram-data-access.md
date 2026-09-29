# Instagram (plus TikTok/YouTube) data access for the pipeline (checked 2026-09-28)

Compliant routes to (1) feed `viral.db` → `reels` with current top Reels per niche and (2) measure the Reels we post, with other routes covered neutrally. **UNVERIFIED** = not confirmed in primary docs.

## TL;DR

- Use **Instagram API with Facebook Login for Business** (Graph API **v26.0**), the only setup with Hashtag Search and Business Discovery.
- **Niche feed:** Hashtag Search (30 unique hashtags per account per 7 days; no usernames or views) plus Business Discovery on benchmark accounts (returns `view_count`). Licensed-music Reels usually lack `media_url`, so captions are the fallback hook source.
- **Closed loop:** per-reel `views`, `reach`, `saved`, `shares`, `reposts`, watch time and `reels_skip_rate`. Skip rate counts 3-second skips, so it measures the hook directly. There are no per-reel follows and no webhook, and data lags up to 48 h.
- **Not usable:** Meta Content Library, the TikTok Research API and [DSA Art. 40](https://digital-strategy.ec.europa.eu/en/news/commission-adopts-delegated-act-data-access-under-digital-services-act) access are restricted to research.
- **Scraping vendors** conflict with Instagram's Terms, which now cover logged-out collection. The Bright Data ruling is not a licence.

## 1. Instagram Platform basics

- **Version:** v26.0 was released 29 Jul 2026. v20.0 was removed 24 Sep 2026, and v21.0 expires 21 Jan 2027 ([versions](https://developers.facebook.com/docs/graph-api/changelog/versions/)). Pin the version in URLs.
- **Configurations** ([overview, updated 28 Sep 2026](https://developers.facebook.com/docs/instagram-platform/overview)):

| | Instagram Login | Facebook Login for Business |
|---|---|---|
| Host, token | graph.instagram.com, Instagram User token | graph.facebook.com, Facebook User or Page token |
| Facebook Page | not needed | must be linked |
| Scopes | `instagram_business_basic`, `instagram_business_manage_insights` (+ publish/comments) | `instagram_basic`, `instagram_manage_insights`, `pages_show_list`, `pages_read_engagement` (+ `ads_management`/`ads_read` or `business_management` if the Page role comes via Business Manager) |
| Hashtag Search / Business Discovery | no / not documented | yes (Instagram Public Content Access feature) / yes |
| `media_product_type`, ad-inclusive `total_*` metrics | no | yes |
| Own insights, publishing | yes | yes |

- **Access and App Review:**
  - Apps serving only accounts you own run on Standard Access, which needs no review ([App Review](https://developers.facebook.com/docs/instagram-platform/app-review)). But the Public Content Access feature requires App Review and Business Verification before returning live data ([feature](https://developers.facebook.com/docs/features-reference/instagram-public-content-access)), so plan for review.
  - Reviewers need a testable UI with a login button, a screencast per permission, use-case text and one successful call. Untestable apps (no UI, intranet, no Facebook Login) can only get `instagram_basic` and `instagram_manage_comments`, so ship a small dashboard.
- **Tokens:** a 1 h auth code yields a 1 h token, exchanged for a 60-day refreshable one ([overview](https://developers.facebook.com/docs/instagram-platform/overview)). Instagram Login refreshes via `graph.instagram.com/refresh_access_token` after 24 h ([ref](https://developers.facebook.com/docs/instagram-platform/reference/refresh_access_token)); Page tokens minted from a long-lived user token have no fixed expiry ([Facebook Login](https://developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived)).
- **Rate limits:** 4,800 × account impressions per rolling 24 h per app–user pair. Business Discovery and Hashtag Search use Platform Rate Limits instead (200 × daily users per hour per app; per-user caps undisclosed). Watch `X-App-Usage` ([rate limiting](https://developers.facebook.com/docs/graph-api/overview/rate-limiting)).

## 2. Hashtag Search

`GET /ig_hashtag_search?user_id=&q=` returns a static, global ID, so cache it. Then call `/{id}/top_media` or `/recent_media?user_id=&fields=` ([guide](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/hashtag-search), [top](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-hashtag/top-media), [recent](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-hashtag/recent-media), [search](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-hashtag-search)).

- **Fields:**
  - Available: `caption`, `children`, `comments_count`, `id`, `like_count` (omitted if hidden), `media_type`, `media_url`, `permalink`, `timestamp`.
  - There is no `username`.
  - `media_product_type` isn't listed, so detect Reels by `VIDEO` plus a `/reel/` permalink (heuristic, UNVERIFIED).
  - Share, save and repost counts are not returned ([IG Media](https://developers.facebook.com/docs/instagram-platform/reference/instagram-media)).
- **`media_url` is withheld** for:
  - video with copyrighted or licensed audio, including Instagram's music library
  - video with a copyright flag
  - others' reels whose owner disabled downloads
- **Limits:**
  - 30 unique hashtags per account per rolling 7 days. Media calls count even with a cached ID. Repeats are free and don't reset the clock. `/{ig-user-id}/recently_searched_hashtags` lists the active set.
  - `recent_media` covers only 24 h and isn't strictly chronological.
  - Results are public and ad-free, at most 50 per page, with one constant `after` cursor.
  - "Top" ranks by views plus interactions.
- **Fit:** the allowed uses include developing a business's content strategy ([feature](https://developers.facebook.com/docs/features-reference/instagram-public-content-access)). Frame the review that way.

## 3. Business Discovery

`GET /{our-ig-id}?fields=business_discovery.username(handle){followers_count,media{…}}` requires `instagram_basic`, `instagram_manage_insights` and `pages_read_engagement` ([ref](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/business_discovery), [guide](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/business-discovery)).

- **Returns** for other Business/Creator accounts:
  - `caption`, `like_count`, `comments_count`, `permalink`, `timestamp`, `media_type` and `media_url` (same omissions as above).
  - Reels `view_count`, which covers organic and paid views and may include Facebook crossposts.
  - `media_product_type`, `media_audio_type` (MUSIC/ORIGINAL_SOUND) and `thumbnail_url` are public fields, but whether Business Discovery expands them is UNVERIFIED.
  - `shares_count`, `saved_count` and `total_views_count` are excluded ([IG Media](https://developers.facebook.com/docs/instagram-platform/reference/instagram-media)).
- **Constraints and use:** no personal or age-gated accounts; manual cursors; handles are required, so this is a watchlist tool rather than search. Views ÷ followers gives an outlier score.

## 4. Own-reel insights (closed loop)

`GET /{media-id}/insights?metric=…` works on both configurations ([reference, updated 11 Sep 2026](https://developers.facebook.com/docs/instagram-platform/reference/instagram-media/insights)).

| Reels metric | Notes |
|---|---|
| `views` | Instagram plays; replaces plays/impressions; "in development" |
| `reach` | unique accounts; estimated |
| `likes`, `comments`, `saved`, `shares`, `reposts`, `total_interactions` | organic only |
| `ig_reels_avg_watch_time` | unit undocumented; milliseconds per [Phyllo](https://www.getphyllo.com/post/real-time-reels-analytics-using-instagram-reels-api-iv) and [Windsor](https://windsor.ai/instagram-reels-retention-chatgpt/) |
| `ig_reels_video_view_total_time` | includes replays |
| `reels_skip_rate` | share of initial views skipped within 3 s; estimated |
| `crossposted_views`, `facebook_views` | only if shared to Facebook |
| `total_views`, `total_likes`, `total_comments` | include ads; Facebook Login only |

- **Not available for Reels:** `follows`, `profile_visits` and `profile_activity`. Use account-level `follows_and_unfollows` (daily; needs ≥100 followers), `profile_links_taps`, `views` and `reach` instead ([account insights](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/insights)). No retention curve is documented.
- **Deprecated** ([Dataddo](https://community.dataddo.com/t/deprecation-of-certain-metrics-in-instagram-datasets-via-facebook-graph-v2-connector/58), [Metricool](https://help.metricool.com/instagram-replaces-impressions-with-views-what-you-need-to-know-f6n8j)):
  - `impressions` for media created after 2 Jul 2024.
  - `plays`, `clips_replays_count`, `ig_reels_aggregated_all_plays_count` and account-level `impressions`, removed 21 Apr 2025 (v22) in favour of `views`.
- **Timing:** lifetime only; up to 48 h lag; kept 2 years; missing data returns an empty set, not 0.
- **Webhooks:** none for Reels insights (only `story_insights`, and none on Instagram Login) ([webhooks](https://developers.facebook.com/docs/instagram-platform/webhooks)); poll instead.
- **December 2025 additions:** skip rate, reposts, crossposted views, Trial Reels publishing and media deletion ([Social Schmuck, relaying Meta](https://socialschmuck.com/instagram-marketing-api-updates-announced-by-meta/)).
  - Trials publish with `trial_params.graduation_strategy` set to `MANUAL` or `SS_PERFORMANCE` ([publishing](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/)).
  - `is_ai_generated` self-labels AI-persona content.
  - There is no read-side trial flag (UNVERIFIED), so record trial status at publish time.

## 5. Meta Content Library and API

- **Coverage** ([Transparency Center](https://transparency.meta.com/researchtools/meta-content-library)):
  - public content from Facebook, Instagram, Threads (UI only) and WhatsApp Channels
  - on Instagram: business/creator accounts plus personal accounts that are verified or have ≥100 followers, including Reels
- **Capabilities:** keyword search (including text in images for about 180 days), sorting by views and up to 100k results per query ([IG posts guide](https://developers.facebook.com/docs/content-library-api/guide-ig-posts)). Media is available only inside a cleanroom: Meta's free Secure Research Environment or SOMAR's enclave ($371/month plus $1,000 onboarding for new users, [SOMAR](https://www.icpsr.umich.edu/sites/somar/somar-newsletter-archive/somar-newsletter-winter-2026)).
- **Eligibility:** accredited not-for-profit academic institutions or public-interest research non-profits. CASD reviews first, then Meta, each taking about 2–3 weeks ([get access](https://developers.facebook.com/docs/content-library-and-api/get-access)).
- **Verdict:** a commercial pipeline doesn't qualify, and the data stays in the cleanroom.

## 6. Other official surfaces

- **oEmbed** (`/instagram_oembed`, 1,000 calls/h):
  - Metadata may be used only for front-end display. Analytics and persistence are explicitly banned ([oEmbed](https://developers.facebook.com/docs/instagram-platform/oembed)).
  - Author and thumbnail fields were removed on 3 Nov 2025 ([oEmbed Read](https://developers.facebook.com/docs/features-reference/oembed_read)).
  - Vendors report tokenless access since 15 Jun 2026 ([Spotlight](https://spotlightwp.com/instagram-embed-wordpress/), [Smash Balloon](https://smashballoon.com/important-facebook-api-changes-image-optimization-and-more/)). No official announcement was found.
  - Use it only to render reference reels in a review UI.
- **Creator Marketing Hub** (Sep 2026, brand-facing):
  - The Creator Marketplace API (creator discovery, insights, media) now includes Facebook creators and adds `total_views`/`account_interactions` ([changelog](https://developers.facebook.com/docs/instagram-platform/changelog)).
  - An expanded Content Discovery API recommends top organic creator content, with keyword search and insights ([TechWyse](https://www.techwyse.com/news/platform-updates/meta-creator-marketing-hub-partnership-ads), [Affiverse](https://www.affiversemedia.com/meta-creator-marketing-hub-partnership-ads/)).
  - This is the closest official trend feed. Eligibility for non-brands is UNVERIFIED.
- **Trending audio / Reels trends:** no official API found (UNVERIFIED). `audio_name` only renames original audio.

## 7. Third-party providers and legal landscape

| Provider | Route | Offer | Price (indicative) |
|---|---|---|---|
| Apify actors | unofficial, logged-off | reels, captions, views, video URLs, transcripts | ~$0.35–1.75 per 1k reels; ~$2.50 per 1k transcripts ([1](https://apify.com/dami_studio/instagram-reel-scraper), [2](https://apify.com/omaraw/instagram-scraper), [3](https://apify.com/dami_studio/instagram-transcript-scraper)) |
| Bright Data | unofficial scraper APIs + datasets | claims 104.8M+ reel records | ~$0.75 per 1k requests ([reels](https://brightdata.com/solutions/data-extraction/instagram/reels), [blog](https://brightdata.com/blog/web-data/best-instagram-scrapers)) |
| HikerAPI | unofficial API | 100+ endpoints | $0.60–1 per 1k requests ([pricing](https://hikerapi.com/pricing)) |
| Data365 | unofficial API | posts, hashtags, media | ~€300/mo per a competitor (UNVERIFIED) ([Data365](https://data365.co/pricing)) |
| Phyllo | creator-consented OAuth + public data | connected creators' private metrics | quote ([Phyllo](https://www.getphyllo.com/post/universal-api-for-influencer-marketing)) |
| Brandwatch, Sprout, Emplifi, Dash Hudson, Later | official-API suites | owned analytics, benchmarks and hashtag tracking under the same limits (Brandwatch: 30 hashtags per account, ~400 days for non-owned accounts) | enterprise ([Brandwatch](https://www.brandwatch.com/blog/best-instagram-coverage/), [data](https://www.brandwatch.com/datanetworks/instagram/), [Sprout](https://support.sproutsocial.com/hc/en-us/articles/4416568353933-How-do-I-use-the-Competitor-Posts-Report)); Dash Hudson/Later UNVERIFIED |

**Rules**
- Instagram's Terms ban automated access or collection without express permission, logged in or not; selling, licensing or buying its data; and circumventing technical limits. Automated-access claims are excluded from arbitration ([Terms](https://www.facebook.com/help/instagram/581066165581870)).
- Meta's Platform Terms ban buying or selling Platform Data and processing it outside documented purposes ([Platform Terms](https://developers.facebook.com/terms/dfc_platform_terms/)).

**Case law**
- *Meta v. Bright Data* (N.D. Cal., 23 Jan 2024): Judge Chen granted Bright Data summary judgment because Meta's terms then didn't cover logged-off scraping of public data and no logged-in scraping was shown ([Farella Braun](https://www.fbm.com/alex-reese/publications/major-decision-affects-law-of-scraping-and-online-data-collection-meta-platforms-v-bright-data/), [Courthouse News](https://www.courthousenews.com/federal-judge-rules-against-meta-in-data-scraping-case/)). Meta dropped its remaining claims in Feb 2024 ([TechCrunch](https://techcrunch.com/2024/02/26/meta-drops-lawsuit-against-web-scraping-firm-bright-data-that-sold-millions-of-instagram-records/)).
- Meta then added logged-out language to its terms (Facebook: from 1 Jan 2025, [McNutt](https://www.mcnuttpartners.com/what-you-need-to-know-about-metas-new-terms-of-service/)). Whether it binds non-users is untested (UNVERIFIED).
- Fake-account scraping remains actionable: *Meta v. Voyager Labs* was allowed to proceed in May 2024 ([Courthouse News](https://www.courthousenews.com/meta-can-proceed-with-data-scraping-suit-against-uk-surveillance-startup/)).
- Copyright and GDPR/CCPA apply separately.

**Risk and recommendation.** Our posting account is bound by these Terms: buying scraped data or scraping while logged in risks restriction, and mixing it into the Meta app risks app-level action (inference). Go official first. If a vendor fills gaps, use logged-off public data only, keep it outside the Meta app tagged `source='vendor:*'`, get legal review, and store text and numbers, never media.

## 8. TikTok and YouTube

**TikTok**
- **Research API:** for not-for-profit academics (US, EEA, UK, Canada, Switzerland) and some EU non-profits. Commercial users are ineligible ([product](https://developers.tiktok.com/products/research-api), [FAQ](https://developers.tiktok.com/doc/research-api-faq)).
- **Display API** (`video.list`): our public videos' view, like, comment and share counts, plus duration, description and `is_aigc`. There is no watch time ([video object](https://developers.tiktok.com/doc/tiktok-api-v2-video-object)).
- **Organic API** ([TikTok](https://ads.tiktok.com/help/article/marketing-api?lang=en)):
  - Accounts: watch time, completion rate, reach and new followers (fields per [Adriel](https://docs.adriel.com/data-sources/o-z/tiktok-organic/data-reference), UNVERIFIED).
  - **Discovery:** trending hashtags, themes and Commercial Music Library tracks. This is the compliant trend feed.
- **[Creative Center](https://ads.tiktok.com/help/article/creative-center?lang=en):** a free UI for trends and top ads. No official API is documented (UNVERIFIED).

**YouTube**
- **Data API v3** ([quota](https://developers.google.com/youtube/v3/determine_quota_cost), [revisions](https://developers.google.com/youtube/v3/revision_history)):
  - `videos.list` costs 1 unit per 50 IDs.
  - Since 1 Jun 2026, `search.list` has its own 100-calls/day bucket.
  - `videos.batchGetStats` arrived on 3 Jun 2026.
  - There's no Shorts flag (UNVERIFIED), so infer Shorts from duration.
  - `mostPopular` stopped mirroring Trending on 21 Jul 2025.
  - Shorts views have counted every start or replay since 31 Mar 2025; on 27 Aug 2026 YouTube announced play-start counting for all formats.
- **Analytics API** (own channel, `creatorContentType==SHORTS`; [dimensions](https://developers.google.com/youtube/analytics/dimensions), [metrics](https://developers.google.com/youtube/analytics/metrics), [revisions](https://developers.google.com/youtube/analytics/revision_history)):
  - `views`, `engagedViews`, `averageViewDuration` and `subscribersGained`.
  - A real retention curve: `audienceWatchRatio` over `elapsedVideoTimeRatio`.
  - Latency is 48–72 h.
- **[Developer Policies](https://developers.google.com/youtube/terms/developer-policies):**
  - Refresh or delete others' public stats within 30 days.
  - Don't store audiovisual content, so no ASR on others' Shorts.
  - Don't derive new metrics or scores from API data.
  - Own analytics may be kept if authorization is re-checked every 30 days.

## 9. Practical recipe

**Setup**
1. Make the posting account Business/Creator, linked to a Facebook Page, and complete Business Verification.
2. Create a Meta app with Facebook Login for Business requesting `instagram_basic`, `instagram_manage_insights`, `pages_show_list`, `pages_read_engagement` (+ `business_management` if needed) and Public Content Access. Add a small review UI; pin v26.0.
3. Keep the long-lived token as a secret, refreshed around day 50 (system-user tokens for hashtag endpoints: UNVERIFIED).

**Job A: niche feed (daily 06:00 UTC, about 100–300 calls)**
1. Keep a `hashtag_budget` table of 25 or fewer active hashtags (about 3 per niche) plus 5 spare. Check `recently_searched_hashtags` before adding one.
2. For each hashtag, call `top_media?fields=id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count&limit=50` (at most 2 pages). Keep `VIDEO` + `/reel/` items under 7 days old.
3. Every 8 h, call `recent_media` to catch rising reels, then re-rank them on the next pull.
4. Run Business Discovery on 10–30 benchmark handles per niche, once per handle per day, requesting `media.limit(25){caption,permalink,timestamp,media_product_type,media_audio_type,like_count,comments_count,view_count,media_url}`. Score reels by views ÷ followers.
5. Upsert on media ID and set `analyzed_at=datetime('now')`, the format `research_bridge`'s 7-day filter expects.

**Job B: our reels (hourly)**
1. Call `GET /{ig-user-id}/media?fields=id,caption,media_product_type,permalink,timestamp&since=<last>`. Register each new `REELS` item with `is_own=1` and a `script_slug` taken from the publish response or a caption tag.
2. Snapshot insights at about 24 h, 48 h, 7 d and 28 d: `views,reach,likes,comments,saved,shares,reposts,total_interactions,ig_reels_avg_watch_time,ig_reels_video_view_total_time,reels_skip_rate`.
3. Pull account insights daily (`follows_and_unfollows`, `profile_links_taps`, `views`; `period=day&metric_type=total_value`) and attribute follows to that day's posts.
4. Compute labels:
   - hook = 1 − skip_rate (normalized to 0–1)
   - hold = average watch time ÷ duration
   - share rate = shares ÷ reach, and save rate = saves ÷ reach
   - trial vs. non-trial

**Hook extraction**
- **`hook_text`:** the first non-empty caption line with hashtags, mentions, URLs and emojis stripped, capped at 150 characters. Set `hook_source='caption'`, because spoken hooks often differ.
- **`transcript`:** only when `media_url` exists: `ffmpeg -t 3.5 -i "$URL" -vn -ac 1 -ar 16000 clip.wav` → local ASR → keep the text, delete the audio. For our own reels, transcribe the local render. Expect gaps for library-music reels.
- **Storage:** never persist `media_url`; CDN links expire, and deleted media must drop out.
- Sanitize and cap text before it goes into prompts ([oss-pipelines](oss-pipelines.md) #16).

**SQLite mapping.** Existing readers select named columns, so adding columns is safe.

| Column | Source |
|---|---|
| `url` | `permalink` |
| `username` | Business Discovery or own account. Hashtag rows have none, so store NULL (`make_shotlist` then prints `@None`) |
| `niche` | hashtag→niche map, or the watchlist niche |
| `like_count` | `like_count` (NULL if hidden) |
| `notes` | source plus a metrics summary |
| `hook_text` | caption line or transcript |
| `pattern_id` | pipeline classifier |
| `analyzed_at` | `datetime('now')` |

Add these columns, one `ALTER TABLE reels ADD COLUMN` each:
- `platform` (default `'instagram'`)
- `media_id` (Instagram media ID, TikTok `item_id` or YouTube ID)
- `source` (`ig_hashtag_top|ig_hashtag_recent|ig_bd|ig_own|tt_*|yt_*|vendor:*`) and `source_query` (the hashtag or handle)
- `media_type`, `media_product_type`, `media_audio_type`, `posted_at` (UTC) and `caption`
- `views`, `comments`, and `shares`/`saves` (own reels only)
- `transcript` and `hook_source` (`caption|asr|own_render`)
- `is_own`, `is_trial` and `script_slug`
- `purge_after` (e.g. 30 days after fetch for YouTube stats)

```sql
CREATE UNIQUE INDEX IF NOT EXISTS reels_media ON reels(platform, media_id);
CREATE TABLE IF NOT EXISTS reel_metrics(
  media_id TEXT, captured_at TEXT, age_h INTEGER, views INTEGER, reach INTEGER,
  likes INTEGER, comments INTEGER, shares INTEGER, saves INTEGER, reposts INTEGER,
  avg_watch_ms INTEGER, total_watch_ms INTEGER, skip_rate REAL,
  PRIMARY KEY (media_id, captured_at));
```

**Guardrails**
- Use Platform Data only for the approved purpose.
- Publish a privacy policy and honour deletion requests.
- Purge rows whose media has vanished, and enforce `purge_after`.
- Let gates filter on `source` so vendor rows can be excluded.

Content was rephrased for compliance with licensing restrictions.
