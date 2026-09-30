# Trend discovery rules (the constants vsp.trends implements)

Checked 2026-09-29 (cited evidence: [trend-discovery.md](trend-discovery.md)). Each row is a constant in `vsp/trends/*.py` (module in brackets) and its basis.

Grades:
- **P**: platform documentation, policy or law
- **S**: study
- **M**: practitioner or marketing practice
- **A**: our assumption or inference

Change a constant only together with this table and the selfcheck.

## Data access and retention

| rule | value | module | basis | grade |
|---|---|---|---|---|
| Instagram data | official Graph API only (vsp.ingest Hashtag Search + Business Discovery); no scraping | skill, importers | Instagram Terms; AGENTS.md rule 7; *Meta v. Bright Data* (2024) covers logged-off scraping only, not logged-in automation | P |
| Hashtag Search limit | 30 unique hashtags per 7 days; no username, views or followers in results | (vsp.ingest) | Graph API v26.0 Hashtag Search | P |
| Small/medium creator tracking | Business Discovery on a watchlist; views ÷ creator median | jobs `watchlist_suggest` | Business Discovery returns followers_count and reels view_count | P |
| Watchlist cap | 150 handles; suggest nano/micro/mid with ≥5x | jobs `WATCHLIST_CAP`, `WATCHLIST_MIN_X` | Business Discovery rate limits | A |
| TikTok | Creative Center lists copied by hand; no automated collection | importers `tiktok_cc`, skill | TikTok ToS; the Research API is academic-only; the Display API returns own videos only | P |
| YouTube search | `type=video&videoDuration=short`, then duration ≤ 180 s | importers `SHORT_MAX_S` | Data API v3 (videoDuration short < 4 min; Shorts up to 3 min) | P |
| YouTube costs | search.list 1 unit in its own bucket of 100 calls/day (since 1 Jun 2026); videos/channels/playlistItems.list 1 unit each from the 10,000-unit bucket | importers `YT_COSTS`, `YT_SEPARATE_BUCKET` | [quota costs](https://developers.google.com/youtube/v3/determine_quota_cost), [revision history](https://developers.google.com/youtube/v3/revision_history) | P |
| YouTube derived metrics | views ÷ channel median (and any ratio) is a derived metric: only with the Analytics & Reporting amendment accepted (`VSP_YT_DERIVED_OK=1`); otherwise YouTube rows are kept unscored and no channel baseline is fetched | score `yt_derived_ok`, importers | [Developer Policies](https://developers.google.com/youtube/terms/developer-policies), [derived-metrics amendment](https://developers.google.com/youtube/terms/derived-metrics-policy) | P |
| YouTube stop | before 9,000 of the 10,000 units/day, or 90 of the 100 search.list calls/day | importers `YT_UNIT_STOP`, `YT_SEARCH_STOP` | quota docs (search bucket since 1 Jun 2026); 10 % margin is ours | P / A |
| YouTube quota day | fixed UTC−8 | importers `YT_DAY_OFFSET_H` | the quota resets at midnight Pacific | P / A |
| YouTube retention | `purge_after` = observed + 30 days (rows and creators); refresh-or-purge | schema `YT_RETENTION_DAYS` | Developer Policies (30-day refresh of non-authorized stats); the June 2026 amendment allows 36 months for stats, but we take the conservative 30 days | P |
| Instagram retention | keeps vsp.ingest's `purge_after`; delete on request | importers | Meta Platform Terms (derived data is Platform Data) | P |
| Stored text | ≤ 12-word hook excerpt, ≤ 8-word overlay, ≤ 280-char notes; never whole captions or media | schema `MAX_FIRST_WORDS`, `MAX_ON_SCREEN_WORDS`, `MAX_NOTES` | short phrases are not copyrightable (37 CFR 202.1); public data is still personal data (joint privacy-regulators statement) | P |
| GitHub storage | JSONL, private repo, files < ~1 MB, < ~3,000 entries per directory; history rewrite for deletions | store `SIZE_WARN_BYTES` | GitHub limits | P |
| Hashtags per post | at most 5 caption tags imported | importers `MAX_CAPTION_TAGS` | Instagram 5-hashtag cap (Dec 2025) | P |
| Generic tags | #fyp, #viral, #reels, … dropped from trend keys | schema `GENERIC_TAGS` | carry no trend signal | A |

## Outliers

| rule | value | module | basis | grade |
|---|---|---|---|---|
| Baseline | median of the creator's recent posts; ≥ 5 posts, each ≥ 7 days old, the 30 most recent | score `BASELINE_MIN_POSTS`, `BASELINE_MIN_AGE_DAYS`, `BASELINE_MAX_POSTS` | Eden (median of the last 30 posts); faceless.so (exclude posts < 7 days); YouTube Outlier Tracker (30-day median) | M |
| YouTube channel baseline | the last 15 Shorts uploads older than 7 days | importers `BASELINE_UPLOADS` | as above, fitted to one playlist page | M / A |
| Bands | < 3 normal · 3–5 notable · 5–10 outlier · 10–50 breakout · ≥ 50 mega | score `BAND_BOUNDS` | Eden bands; faceless.so (> 3x = the format changed); Outlier Tracker (5x outlier, 10x breakout); 1of10 | M |
| Fallback multiples | views ÷ followers, then (likes + comments) ÷ followers ÷ the tier's typical rate; else unscored | score | Eden (views per follower) | M |
| Typical engagement | Instagram nano 1.78 %, macro 0.35 %, mega 0.33 %; TikTok nano 11.6 %, mega 6.8 %; micro and mid interpolated | score `ENGAGEMENT_BASELINE` | HypeAuditor 2026 (interpolation ours) | S / A |
| Tiers | emerging < 1k · nano 1k–10k · micro 10k–100k · mid 100k–500k · macro 500k–1M · mega ≥ 1M | schema `TIER_BOUNDS` | HypeAuditor 2026 (emerging tier ours) | S |
| Tier weight | emerging, nano, micro 1.0 · mid 0.9 · macro 0.6 · mega 0.3 (unknown 0.7) | score `TIER_WEIGHTS` | Instagram shows new posts to a small audience first (Apr 2024), so a small account's outlier means the format won; nano accounts dominate the platforms | P / A |
| Recency | weight halves every 7 days | score `RECENCY_HALF_LIFE_DAYS` | Szabo & Huberman 2010 (early views predict later ones); half of top hashtags fade within 5 days (Publicis × TikTok 2026) | S / A |
| Multiple saturation | log(1 + x) ÷ log(51), capped at 50x | score `MULTIPLE_CAP` | the mega band starts at 50x | A |
| Basis weight | median 1.0 · followers 0.8 · engagement 0.6 | score `BASIS_WEIGHTS` | proxies are weaker evidence | A |
| Velocity | vph = views per hour since posting | score | vidIQ VPH | M |

## Trend lifecycle

| rule | value | module | basis | grade |
|---|---|---|---|---|
| A trend | a trend key with ≥ 2 distinct creators | lifecycle `STAGE_RULES.min_creators` | imitation publics (Zulli & Zulli) | S / A |
| Windows | 3d = days 0–2 · 7d = 0–6 · prev7d = 7–13; growth = 7d ÷ max(1, prev7d) | lifecycle | burst detection (Kleinberg 2002); cascades (Cheng et al. 2014) | S / A |
| emerging | first seen ≤ 7 days ago and ≥ 2 creators | `STAGE_RULES` | | A |
| rising | growth ≥ 1.5 and ≥ 3 creators in 7d | `STAGE_RULES` | early growth predicts whether a cascade doubles (about 0.8 accuracy, Cheng et al. 2014); the 1.5 threshold is ours | S / A |
| peak | ≥ 10 creators in 7d and 0.8 ≤ growth < 1.5 | `STAGE_RULES` | | A |
| saturated | ≥ 20 creators in 7d and growth < 0.8 | `STAGE_RULES` | | A |
| declining | growth ≤ 0.5, or no sighting for 14 days (the latter implies growth = 0) | `STAGE_RULES` | 27 % of top hashtags last over 2 weeks (Publicis × TikTok 2026) | S / A |
| steady | otherwise | `STAGE_RULES` | | A |
| Speed | seen < 21 days = moment · 21–180 days = signal · > 180 days = force | lifecycle `SPEED_BOUNDS` | TikTok "Speeds of Culture" (moments, signals, forces) | P |
| Evergreen | a format or topic trend that is a signal or force | lifecycle | utility and cultural codes persist (Publicis × TikTok 2026) | S / A |
| Jump-in advice | emerging, rising: jump in now · peak: only with a twist (combine or transplant) · saturated, declining: skip unless evergreen · steady: base with a twist | lifecycle `JUMP_IN` | TikTok Trend Digest; practitioner timing | P / M |
| Same trend | keys whose posts overlap ≥ 80 % (Jaccard) are one trend's elements | lifecycle `RELATED_OVERLAP` | TikTok Trend Digest (4 elements) | P / A |

## Synthesis and steering

| rule | value | module | basis | grade |
|---|---|---|---|---|
| Keep 2, change 2 | of message, hashtags, sonic identity and visual narrative; which 2 depends on the trend kind | synth `KEEP_BY_KIND` | TikTok Trend Digest | P |
| Originality | own footage and words; no reposts | synth `COMMON_ORIGINALITY` | Instagram: 10+ reposts in 30 days removes recommendation eligibility; TikTok 2026 unoriginal-content rules | P |
| Audio | a trending sound is only a pattern; licensed library music in commercial posts; never another creator's original sound | synth `LICENSED_AUDIO_FACTOR` 0.9, notes | platform commercial-music rules | P |
| Score | evidence × velocity × novelty × feasibility, each in [0, 1] | synth | | A |
| Evidence | 1 − exp(−Σ inspiration); a multi-trend recipe uses the mean of its groups | synth `EVIDENCE_SCALE` 1.0 | | A |
| Velocity | emerging 1.0 · rising 0.9 · peak 0.6 · steady 0.5 · saturated 0.25 · declining 0.1 | lifecycle `STAGE_VELOCITY` | | A |
| Novelty | 1 − max token Jaccard against used recipes (180 days) and earlier picks in the batch | synth, jobs `NOVELTY_MEMORY_DAYS` | | A |
| Feasibility | replicability (0.4 → 1.0) × cost (low 1.0, med 0.8, high 0.5) × lane (needs a real person → 0 for an AI presenter) × licensed audio 0.9 × niche fit (foreign 0.85, transplant 0.8) | synth | D137 (an AI presenter never claims lived experience) | P / A |
| Transplant / substitute | median ≥ 3x in another niche / a single post ≥ 5x | synth `TRANSPLANT_MIN_MULTIPLE`, `SUBSTITUTE_MIN_MULTIPLE` | outlier bands | M |
| Invent | conventional high-evidence format + atypical participation mechanic + high-arousal emotion + named signature + slot + hypothesis + Trial Reels test plan | synth `op_invent`, `HIGH_AROUSAL` | Uzzi 2013 (conventional + atypical combinations); Hekkert MAYA; Boden (combinational creativity); Fauconnier & Turner (blending); Berger & Milkman (high arousal spreads); Shifman 2012; seeded trends (GuacDance, e.l.f. "Eyes Lips Face", "girl dinner", the Wes Anderson trend) | S / M |
| Constraints | one take · 10 seconds · no talking; no price constraint | synth `CONSTRAINTS` | SCAMPER; D37 / D136 (no invented prices) | S / P |
| Batch diversity | ≤ 3 recipes per operator; one representative card per trend | synth `MAX_PER_OPERATOR` | | A |
| Steering | latest batch ≤ 7 days old; score ≥ 0.05; concept miss × 0.85; format miss × 0.8 | steer `MAX_RECIPE_AGE_DAYS`, `MIN_STEER_SCORE`, `CONCEPT_MISS`, `FORMAT_MISS` | trends move fast (see the lifecycle rows above) | A |
| Test protocol | Trial Reels + 3 alternate openings; measure `reels_skip_rate`, shares and saves per reach at 24/48/72 h | synth `op_invent` | Instagram Trial Reels and insights (research doc §4) | P |

## Re-snapshotting (import-ingest)

| rule | value | module | basis | grade |
|---|---|---|---|---|
| New snapshot | a metric grew ≥ 10 %, the last snapshot is ≥ 7 days old, or retention needs a refresh within 7 days | importers `RESNAPSHOT_MIN_GROWTH`, `RESNAPSHOT_MAX_AGE_DAYS`, `REFRESH_WITHIN_DAYS` | keeps daily files well under 1 MB | A |
