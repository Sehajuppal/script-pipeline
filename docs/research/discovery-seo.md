# Discovery and search packaging for short-form bundles (checked 2026-09-29)

**Scope.** This covers what each bundle needs so TikTok, Instagram Reels and YouTube Shorts can index, surface and rank it: keywords and where they go, per-platform packaging, covers, posting guidance and gates. It adds to [short-form-virality.md](short-form-virality.md) §3 and [instagram-data-access.md](instagram-data-access.md) without repeating them. That means it doesn't restate the 57%/25% TikTok search figures, Mosseri's January 2025 top-three signals, the 5-hashtag cap, Trial Reels' +80%, YouTube's 60-hashtag rule, or the Graph API setup.

**Grades.** [P] platform rule or official doc · [S] strong (an official statement relayed by reliable press, or a large dataset) · [M] moderate (consistent industry or vendor evidence) · [A] anecdotal or inference. **UNVERIFIED** means no primary source confirmed it.

## TL;DR

- **One primary keyword per video**, 2–4 words in the form people search. It goes in five places:
  - spoken by 3.0 s
  - on screen by 3.0 s
  - within the first 60 characters of caption line 1
  - one hashtag
  - the cover text

  All three match queries on text. YouTube and TikTok (for search ads) also match on video content ([YouTube](https://support.google.com/youtube/answer/16090438?hl=en), [TikTok Ads](https://ads.tiktok.com/resources/help/article/search-ads-creative), [Instagram](https://about.instagram.com/blog/announcements/break-down-how-instagram-search-works/)).
- **Hard limits depend on how you post.**
  - TikTok: 4,000 characters in the app, but 2,200 UTF-16 units through the Content Posting API.
  - Instagram: 2,200 characters and 5 hashtags.
  - YouTube: a 100-character title and a 5,000-**byte** description [P].
- **Hashtags label content; they don't earn reach.** Use 3 relevant tags on TikTok and Instagram, 2–3 on Shorts. Some of our current tags are off-topic: #organization on a milk frother, #30daychallenge on a 21-day video.
- **None of the three platforms supports custom alt text on video.** The alt-text slot becomes one plain descriptive caption sentence, plus uploaded captions (`captions.srt`).
- **Design each cover for one text box: x 120–888, y 420–1248 on a 1080×1920 frame.** It survives Instagram's 3:4 grid, the legacy 1:1 crop and the in-feed UI.
- **Posting time is a weak lever; frequency raises the ceiling, not the median.** `online_followers` has gone from the v26 metrics table.
- **New this cycle:**
  - TikTok "Manage Keywords" (April 2026)
  - custom Shorts thumbnails for YouTube Partner Program (YPP) channels (July 2026)
  - "content gaps for Shorts" in Studio's Trends tab
  - Instagram's `is_ai_generated` flag (June 2026)
  - the `config_issue: CAPTION_NOT_ATTACHED` publish warning (September 2026)

## 1. What the current bundles ship

| Bundle | Caption line 1 | Implied primary keyword | Gaps |
|---|---|---|---|
| electric-milk-frother (AI, demo) | "Stop buying milk frothers on looks alone." | milk frother | #organization is off-topic. #amazonfinds implies an Amazon listing, so use it only if one exists (D37 spirit). No #milkfrother tag. |
| silk-pillowcase (human, review) | "The silk pillowcase after 7 days. Worth it?" | is a silk pillowcase worth it | Line 1 is good. The comment-word GLOW is off-keyword. No #silkpillowcase tag. |
| sugar-21 (human, challenge) | "21 days without sugar." | no sugar challenge | #30daychallenge contradicts the 21 days. On-screen "SUGAR" is too thin. The comment-word DAY1 is off-keyword. |

All three reuse one caption on every platform. None has a YouTube title or description, a cover spec, platform toggles (AI label, paid partnership) or a record of the chosen keyword.

## 2. TikTok

**Search demand.** Adobe's January 2026 survey of 807 US consumers found that 49% had used TikTok as a search engine (41% in 2024), including 65% of Gen Z ([Adobe](https://www.adobe.com/express/learn/blog/using-tiktok-as-a-search-engine)). But only 4% of Gen Z now prefer TikTok to Google, down from 8% ([SEJ](https://searchenginejournal.com/gen-z-preference-for-tiktok-over-google-drops-50-data-shows/568267)) [M]. Treat TikTok search as an extra surface, not a replacement for Google.

**How videos get matched**
- **Official ranking inputs.** The For You ranker weighs interactions plus "video information" (captions, sounds, hashtags). Finishing a longer video is a strong signal, and follower count isn't a direct factor ([TikTok Newsroom](https://newsroom.tiktok.com/en-us/how-tiktok-recommends-videos-for-you)) [P].
- **Search ads.** Creative is chosen on relevance between the query, the keywords and the creative content. TikTok recommends a "text hook", meaning keywords as on-screen text in the first frames ([TikTok Ads Help](https://ads.tiktok.com/resources/help/article/search-ads-creative)) [P for ads, M for organic].
- **Speech and on-screen text.** Indexing spoken words (ASR) and on-screen text (OCR) for organic search is industry consensus, but TikTok doesn't document it ([example](https://www.bytecap.io/blog/short-form-video-seo-transcript-indexing)) [M; UNVERIFIED officially].
- **Manage Keywords (April 2026).** TikTok now shows the keywords it auto-assigned to a post from popular searches. Creators can suggest or block terms, and TikTok reviews the changes ([Social Media Today](https://www.socialmediatoday.com/news/tiktok-lets-users-add-relevant-keywords-to-metadata/818507/), [Neil Patel](https://neilpatel.com/blog/tiktok-keyword-metadata/)) [S].
- **Search recommendations.** These are the suggested queries shown over a video, above its comments or highlighted inside them. According to TikTok's Creator Academy, as summarized by researchers, they come from comments and from what people search after watching. Creators can suppress words with comment filters ([Utrecht/WZB paper](https://arxiv.org/html/2505.08385v1)) [S].
  - By inference [A]: a comment-word that matches the keyword's head noun (FROTHER) seeds a useful suggestion; GLOW or DAY1 seeds nothing.

**Limits**
- **Caption.** 4,000 characters in the app ([wordcount.com](https://wordcount.com/guides/character-limits-social-media)) [S]. In the Direct Post API, `title` holds up to 2,200 UTF-16 runes and parses # and @ ([TikTok for Developers](https://developers.tiktok.com/doc/content-posting-api-reference-direct-post)) [P].
- **Hashtags.** Since August 2025 the app blocks a sixth hashtag with a "Maximum 5 hashtags" prompt ([Search Engine Land](https://searchengineland.com/tiktok-limits-hashtags-460894), [Distractify](https://www.distractify.com/p/why-is-tiktok-limiting-my-hashtags)) [S]. It isn't in the help docs, and whether the API enforces it is UNVERIFIED.
- **Visible caption.** About 100 characters before truncation ([Hootsuite](https://www.hootsuite.com/social-media-tools/social-media-caption-preview)) [M].
- **Cover.** The API can only pick a frame (`video_cover_timestamp_ms`, default the first frame). It can't upload an image [P]. Covers reportedly can't be changed after posting ([Famety](https://www.famety.net/blog/how-to-edit-tiktok-thumbnail-after-posting)) [A].
- **Disclosure** [P]:
  - `is_aigc` adds a "Creator labeled as AI-generated" tag.
  - `brand_content_toggle` marks paid third-party content.
  - `brand_organic_toggle` marks promotion of your own business.
- **Alt text.** Available on photo posts only ([TikTok Newsroom](https://newsroom.tiktok.com/en-us/celebrating-global-accessibility-awareness)) [P].

**Tools**
- **Creator Search Insights.** Find it by searching its name in-app. It shows frequently searched topics (by category or "For You"), a content-gap filter and search performance for your own posts. "Search value" also feeds the Creator Rewards formula ([TikTok Newsroom](https://newsroom.tiktok.com/en-us/creator-search-insights), [paper](https://arxiv.org/html/2505.08385v1)) [P].
- **Creative Center, now inside TikTok One.** It has Top Ads, Trends (hashtags) and keyword examples in the Inspiration tab. The old Keyword Insights URL now redirects to a generic Creative Center page, so whether standalone Keyword Insights still exists is UNVERIFIED ([TikTok Ads Help](https://ads.tiktok.com/help/article/keyword-insights)). TikTok One's advertiser-side Custom insights covers keywords and hashtags ([TikTok](https://ads.tiktok.com/resources/help/article/about-custom-insights-in-tiktok-one)) [P].
- **Search Ads keyword tool.** Available in Ads Manager (US/UK). It suggests keywords and predicts monthly impressions ([TikTok](https://ads.tiktok.com/business/en-GB/blog/introducing-search-ads-campaign)) [P].
- **Search Hubs (May 2026).** A paid product that puts brand pages at the top of search results ([TikTok Newsroom](https://newsroom.tiktok.com/en-us/tiktok-world-26-turning-discovery-into-business-growth-with-ai-powered-innovations-vertical-experiences-and-high-impact-brand-solutions)) [P]. No feature named "Search Highlights" was found (UNVERIFIED).

**Shop videos**
- The creator adds the product link at posting and types a product name. The link shows above the username after an extra review ([TikTok Ads Help](https://ads.tiktok.com/help/article/add-product-links-tiktok-videos?lang=en)) [P].
- Name it with the primary keyword plus one attribute. TikTok's catalog rules ban emoji and promotional filler such as "free shipping" ([TikTok](https://ads.tiktok.com/resources/help/article/catalog-product-parameters)) [P].
- The name's character limit is UNVERIFIED. Shop quality rules and caps are in virality §3.

**Frequency and time**
- **Frequency.** Buffer studied 11.4M posts from over 150k accounts, using fixed-effects regressions ([Buffer](https://buffer.com/resources/how-often-should-you-post-on-tiktok/)) [M]. Compared with one post a week:
  - 2–5 posts a week gave +17% views per post
  - 6–10 gave +29%
  - 11+ gave +34%

  Median views stayed around 500, while the 90th percentile rose from 3,722 to 14,401. So posting more raises the ceiling, not the typical post.
- **Time of day.** Buffer's 7.1M-post median-engagement heatmap favours Sunday 9 am, Monday 1 pm and evenings. Buffer itself notes that other studies disagree ([Buffer](https://buffer.com/library/best-time-to-post-on-tiktok/)) [A for any specific slot]. Use TikTok Studio → Followers → Most active times instead.
- **Eligibility pre-check.** Content Check Lite in TikTok Studio on the web checks For You feed eligibility before you post ([TikTok Newsroom](https://newsroom.tiktok.com/en-us/new-tools-for-creators)) [P].

## 3. Instagram

**Search**
- The query is matched against usernames, profile names, bios, captions, hashtags and places. Keywords belong in the caption, not the comments ([Instagram](https://about.instagram.com/blog/announcements/break-down-how-instagram-search-works/)) [P].
- Meta's Transparency Center (updated 23 June 2026) lists query–username and query–profile-name similarity, and exact-match suggested keywords, among the signals ([Meta](https://transparency.meta.com/features/explaining-ranking/ig-search/)) [P].
- So put the niche keyword in the profile name, for example "Maya | kitchen gadget tests" [A].
- Whether Reels search reads on-screen text or speech is UNVERIFIED.

**Hashtags**
- Instagram cut the limit to 5 per post and Reel in December 2025. It said a few targeted tags work better than many generic ones ([SMT](https://www.socialmediatoday.com/news/instagram-implements-new-limits-on-hashtag-use/808309/), [statement](https://www.academyofcontinuingeducation.com/blog/instagram-institutes-a-5-hashtag-limit)) [P].
- Mosseri described hashtags as organizing content rather than driving reach ([Times of India](https://timesofindia.indiatimes.com/technology/social/after-instagram-head-adam-mosseri-says-hashtags-are-myths-app-limits-hashtag-count-on-posts/articleshow/126082966.cms)) [S].
- The API reference still says 30, which is stale. Gate at 5.

**Google indexing (from 10 July 2025)**
- Search engines can show public posts, including Reels, from professional accounts owned by adults. The eligible window reportedly starts with posts from 1 January 2020 ([PPC Land](https://ppc.land/instagram-content-becomes-searchable-on-google-starting-july-10/), [Tech Times](https://www.techtimes.com/articles/320199/20260712/instagram-posts-now-rank-google-how-measure-win-search-traffic.htm), [Iconosquare](https://www.iconosquare.com/blog/how-to-make-your-instagram-post-show-up-on-google)) [S].
- Accounts opt out with the privacy toggle "Allow public photos and videos to appear in search engine results". The exact help-page wording is UNVERIFIED.
- Caption line 1 doubles as the search-result snippet, so write it as a natural sentence that contains the keyword.

**Trial Reels**
- **How they work.** Trials go to non-followers first. Metrics arrive after about 24 h, and Instagram can auto-share a trial to followers if its views in the first 72 h are strong ([Meta](https://about.fb.com/news/2024/12/trial-reels-try-content-non-followers-first-see-what-perfoms-best/)) [P].
- **API.** `trial_params.graduation_strategy` takes `MANUAL` or `SS_PERFORMANCE` ([Meta for Developers](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/)) [P].
- **Eligibility.** The follower threshold is reported as 200 or 1,000 (UNVERIFIED).
- **Hook-test protocol** (proposal, [A]):
  1. Make 2–3 variants that differ only in 0–3 s (visual, spoken hook, on-screen keyword) and in the cover.
  2. Post them as `MANUAL` trials on the same day.
  3. At 24–72 h, compare `reels_skip_rate`, average watch time and shares ÷ reach, then graduate the winner.
  4. Log trial status at publish, because there's no read-side flag.
- Whether near-duplicate trials trip originality checks is UNVERIFIED, so keep the variants materially different.

**Grid and covers**
- The profile grid moved to 3:4 in January 2025 ([Engadget](https://www.engadget.com/social-media/instagram-swoops-in-with-3-minute-reels-and-rectangular-profile-grids-as-the-tiktok-ban-gets-real-201316339.html)), and 3:4 photo uploads followed in May 2025 ([The Verge](https://www.theverge.com/news/676549/instagram-3-4-aspect-ratio-photos-phones-square-rectangle)) [S].
- API covers (`cover_url`, JPEG ≤8 MB) are centre-cropped to 9:16. For a feed share, the doc still says a centre 1:1 square is used ([Meta for Developers](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/)) [P].
- So cover text must survive y 240–1680 (the 3:4 crop) and ideally y 420–1500 (the 1:1 crop).

**Alt text**
- Photos get alt text in the app (Advanced settings → Accessibility) and through the API. The API's `alt_text` holds up to 1,000 characters and explicitly excludes Reels and Stories (added 24 March 2025) ([Meta for Developers](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/)) [P].
- In-app custom alt text for Reels isn't documented (UNVERIFIED). Put a one-sentence plain description in the caption instead.

**Ranking signals, 2025–26**
- Mosseri added that likes weigh slightly more with followers, and sends slightly more with non-followers ([quoted here](https://keywordseverywhere.com/news/instagram-algorithm-updates/how-the-instagram-algorithm-works/)) [S].
- No ranking change was confirmed in 2026. Vendor ratios such as "one send ≈ 15 likes" are [A] and UNVERIFIED.
- Asking for sends is engagement bait, which Meta demotes and D139 bans. Sends have to be earned with useful verdicts.
- "Your Algorithm" lets users view and edit the topics shaping their recommendations. It launched on Reels on 10 December 2025 ([TechCrunch](https://techcrunch.com/2025/12/10/instagrams-new-your-algorithm-tool-gives-you-more-control-over-the-reels-you-see/)), then spread to Explore and Feed in 2026 ([SocialPilot](https://www.socialpilot.co/instagram-marketing/how-instagram-algorithm-works)) [S]. That makes staying on one topic per account matter more.

**Originality, collabs, location and caption add-ons**
- **Originality.** To be recommended, content can't carry a visible watermark. When identical copies exist, only the original is recommended ([Instagram](https://creators.instagram.com/recommendations-and-originality?locale=en_US)) [P].
- **Collabs.** The API allows up to 3 collaborators per Reel [P]; the app reportedly allows 5 ([Shopify](https://www.shopify.com/ca/blog/how-to-collab-post-on-instagram)) [S].
- **Location.** `location_id` is supported, and places are part of the search inventory [P]. Tag only a true location.
- **Caption add-ons (September 2026).** The API can now attach a poll or a comment prompt (Facebook Login only) ([changelog](https://developers.facebook.com/docs/instagram-platform/changelog)) [P]. The wording still has to pass D139.
- **Dropped captions.** A publish can succeed while its caption fails an integrity check and is dropped. The response now carries `config_issue: CAPTION_NOT_ATTACHED` ([changelog](https://developers.facebook.com/docs/instagram-platform/changelog)) [P]. Check every publish response.
- **Comment-to-DM funnel.** A comment-word funnel on Instagram can use Private Replies: one DM per comment, within 7 days ([Meta](https://developers.facebook.com/docs/messenger-platform/instagram/features/private-replies)) [P]. A compliant TikTok equivalent is UNVERIFIED.

**Posting time**
- **`online_followers` is effectively gone.** It's missing from the v26 IG User Insights metrics table (updated 16 June 2026). Only a leftover limitations note and a 2021 changelog entry mention it ([reference](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/insights/)).
  - Treat it as unavailable. Whether calls still return data is UNVERIFIED.
  - Use the app's "most active times" view by hand, or our own 24 h reach curves.
- **Timing.** Mosseri advises posting shortly before followers' peak ([Buffer](https://buffer.com/resources/when-is-the-best-time-to-post-on-instagram/)) [S as a statement; M as an effect].
- **Frequency.** Buffer's 2M-post study found that 3–5 posts a week more than doubles follower growth compared with 1–2 ([SMT](https://socialmediatoday.com/news/study-shows-posting-more-instagram-leads-to-more-reach/757633/)) [M].

## 4. YouTube Shorts

**Limits** [P]
- Title: 100 characters, with no `<` or `>`.
- Description: 5,000 **bytes**. Each emoji costs 4 or more bytes.
- Tags: 500 characters in total. YouTube says they play a minimal role except for misspellings ([Help](https://support.google.com/youtube/answer/57407?hl=en), [Data API](https://developers.google.com/youtube/v3/docs/videos)).

**Hashtags** [P] ([Help](https://support.google.com/youtube/answer/6390658?hl=en))
- They work in the title or description and are clickable.
- Up to three "most engaging" description tags appear next to the title.
- With more than 60, all are ignored.
- Misleading tags risk removal, and plain tag lists in descriptions are prohibited.

**What counts as a Short** [P]. Any square or vertical upload of 3 minutes or less, for uploads since 15 October 2024 ([Help](https://support.google.com/youtube/answer/15424877?hl=en)). Adding "#Shorts" isn't needed.

**Ranking** [P]
- **Search** weighs three things ([Help](https://support.google.com/youtube/answer/16090438?hl=en)):
  - relevance: title, tags, description and video content
  - engagement: watch time for that query
  - quality
- **The Shorts feed** uses several signals, and YouTube says there's no minimum posting cadence ([Help](https://support.google.com/youtube/answer/11914225?co=YOUTUBE._YTVideoType%3Dshorts&hl=en)):
  - the share of viewers who chose to watch
  - average view duration and average percentage viewed
  - likes
  - survey responses
- **"Get feedback"** at upload analyses the hook and pacing ([Help](https://support.google.com/youtube/answer/10059070?hl=en)).

**Related video** [P]. A Short can link any public or unlisted video on the channel from the Shorts player. It needs advanced features ([Help](https://support.google.com/youtube/answer/57407?hl=en)). That makes it the natural home for our `series_plan` "Part 2".

**Thumbnails** [S]
- Custom Shorts thumbnails rolled out to YPP creators from 24 July 2026. They work in desktop Studio only, alongside three suggested frames, and can't be A/B tested ([Tubefilter](https://www.tubefilter.com/2026/07/24/youtube-shorts-custom-thumbnails-neal-mohan-feature-update/), [PPC Land](https://ppc.land/youtube-ends-2-year-wait-for-shorts-thumbnails-but-blocks-a-b-testing/)).
- Other channels pick a frame.
- Thumbnails appear in search, on channel pages and on the home feed, but not in the swipe feed [M].

**Research** [P]
- Studio's Trends tab, part of the updated Studio rolling out since July 2026, shows top searches, breakout videos and "Content gaps for Shorts" ([Help](https://support.google.com/youtube/answer/11962757?hl=en)).
- The Inspiration tab adds AI-generated ideas ([Help](https://support.google.com/youtube/answer/15575509?hl=en)).

**Disclosure and links** [P] ([Data API](https://developers.google.com/youtube/v3/docs/videos))
- `status.containsSyntheticMedia` discloses realistic altered or synthetic content.
- `paidProductPlacementDetails.hasPaidProductPlacement` discloses paid placement.
- URLs in descriptions are clickable only on verified channels or those with advanced features. So the single CTA on Shorts (D46) should be the comment-word or the Related video, not a link.

## 5. Cross-platform

- **Clean masters.** Export one clean master per platform with no other platform's watermark. Instagram requires this for recommendation [P], and TikTok forbids integrations from adding watermarks or branding ([TikTok for Developers](https://developers.tiktok.com/docs/en/content-sharing-guidelines)) [P].
- **Native captions.**
  - Upload `captions.srt` to YouTube, which accepts plain UTF-8 SRT ([Help](https://support.google.com/youtube/answer/2734698?hl=en)) [P].
  - Turn on auto-captions on TikTok and Instagram and proofread them. Auto-captions alone don't meet accessibility requirements ([UC Berkeley](https://dap.berkeley.edu/social-media/video-caption-support)) [S].
  - Claims that captions lift SEO are vendor claims [A].
- **Series.**
  - TikTok playlists are reportedly limited to accounts with 10k+ followers ([Fone.tips](https://fone.tips/how-to-make-playlists-on-tiktok)) [A].
  - YouTube has playlists plus the Related video link [P].
  - On Instagram, repeat a consistent series name in caption line 2 [A].
- **Pinned comments and video replies.** A pinned comment should repeat the keyword and the single CTA. Comment filters keep off-topic words out of TikTok's search suggestions [S/A]. Video replies to comments are [A].
- **Collabs.** Instagram collabs put the post on every co-author's grid, and the API allows 3 collaborators [P]. The reach effect is [A].
- **Myths**
  - File names: no platform documents them as a signal. YouTube's list is title, tags, description and content. [myth]
  - A universal "best time" to post [weak]
  - Hashtag stuffing, given the caps and YouTube's ignore-all rule [myth]
  - #fyp or #viral tags [myth, A]
  - #Shorts [myth]

## 6. Compliant keyword research

**Sources, in priority order**
1. **Own research DB** (`viral.db` captions and hook_text from the Graph API, which is already compliant). Mine 1–4-word phrase frequencies in the niche's top reels from the last 7–30 days, weighted by views, with hashtags and emoji removed.
2. **TikTok Creator Search Insights** (manual). Note any content-gap flags [P].
3. **YouTube Studio Trends tab**, especially content gaps for Shorts [P].
4. **Google Trends** with the YouTube Search filter. Trends samples Google and YouTube searches ([Google](https://developers.google.com/search/docs/monitor-debug/trends-start)) [P]. The Trends API alpha (since 24 July 2025) is open to a limited set of testers and returns consistently scaled five-year data ([Google](https://developers.google.com/search/blog/2025/07/trends-api)) [P].
5. **TikTok Ads keyword tool** or TikTok One Custom insights, if we have an advertiser account [P].
6. **Platform autocomplete**, typed and logged by a human. Never scrape autocomplete or search pages: Instagram's Terms ban automated collection, and YouTube's developer policies restrict data use (see [instagram-data-access.md](instagram-data-access.md)) [P].

**Choosing the primary keyword**
- Rank candidates by format fit, then evidence of demand, then content-gap bonus, then brevity. The algorithm is in `KEYWORD_RULES.selection_rules`.
- **Guardrails:**
  - Superlative intents such as "best {category} for {use}" may appear only as a question or search label, never as a claim (D141).
  - Price intents need a supplied price (D37).
  - "{product} vs {alternative}" needs real side-by-side footage.
  - A "before and after" intent needs an honest, dated comparison (TikTok's ad policy bans misleading ones).

## 7. Worked example: electric milk frother (AI presenter)

| Slot | Value |
|---|---|
| Primary / secondary | "milk frother" / "latte at home", "cold foam" |
| Spoken by 3.0 s | "Stop buying milk frothers on looks alone." (already compliant) |
| On screen by 3.0 s | "MILK FROTHER TEST" (the current text, "BUYING MILK FROTHERS", also passes) |
| TikTok caption | "Stop buying milk frothers on looks alone. / What to check before buying a milk frother. / Comment FROTHER for the full link list 👇 / made with an AI persona / #milkfrother #coffeetok #latteathome", plus `is_aigc=true` |
| Instagram | Same line 1. Line 2 replaces alt text: "Hands test an electric milk frother on a mug of milk, before and after." Up to 3 hashtags, `is_ai_generated=true`, cover text "MILK FROTHER TEST". |
| YouTube | Title "Milk frother test: what to check before buying" (46 characters). Description line 1 plus the disclosure, then "#milkfrother #coffee". Related video → Part 2. `containsSyntheticMedia=true` because the persona is photorealistic. |

## 8. Deliverables

```json
{
  "PLATFORM_PACKAGING": {
    "tiktok": {
      "caption_max_chars": 2200,
      "caption_max_chars_in_app": 4000,
      "caption_length_unit": "UTF-16 code units (Content Posting API 'title')",
      "caption_recommended_chars": [100, 300],
      "first_line_chars_visible": 100,
      "hashtags": {"min": 1, "max": 5, "recommended": 3},
      "title_max_chars": null,
      "description_max_chars": null,
      "alt_text": {"supported": false, "max_chars": null, "how": "Video posts have no alt-text field (photo posts only). Use one plain descriptive caption sentence containing the primary keyword + auto-captions."},
      "cover": {"aspect": "9:16 (1080x1920)", "safe_crop": "text box x120-888, y420-1248; grid crop assumed centre 3:4 (UNVERIFIED)", "text_max_words": 5, "api": "video_cover_timestamp_ms picks a frame; no image upload; cover reportedly not editable after posting"},
      "keyword_slots": [
        {"slot": "spoken_hook", "required": true, "rule": "primary keyword spoken by 3.0 s"},
        {"slot": "on_screen_text", "required": true, "rule": "primary keyword card visible by 3.0 s for >=1.0 s"},
        {"slot": "caption_line_1", "required": true, "rule": "primary keyword within first 60 chars"},
        {"slot": "hashtag", "required": true, "rule": "one hashtag = compact primary keyword"},
        {"slot": "cover_text", "required": true, "rule": "keyword head noun on the cover frame"},
        {"slot": "comment_word", "required": false, "rule": "comment-word = keyword head noun (seeds search suggestions)"},
        {"slot": "manage_keywords", "required": false, "rule": "after publish: suggest primary + <=2 secondary; block off-topic auto keywords"},
        {"slot": "shop_anchor_name", "required": false, "rule": "Shop videos: product link name = primary keyword + 1 attribute; no promo text, emoji or price"}
      ],
      "disclosure": {"ai_label_toggle": "is_aigc=true (API) / AI-generated content toggle (app)", "paid_partnership": "brand_content_toggle=true (paid third party); brand_organic_toggle=true (own business)"},
      "audio_notes": "Speech is the keyword carrier: keep VO intelligible over ducked music. Shoppable videos: TikTok library music only (virality §3). Sounds are 'video information' for ranking.",
      "sources": [
        "https://developers.tiktok.com/doc/content-posting-api-reference-direct-post",
        "https://wordcount.com/guides/character-limits-social-media",
        "https://searchengineland.com/tiktok-limits-hashtags-460894",
        "https://www.hootsuite.com/social-media-tools/social-media-caption-preview",
        "https://newsroom.tiktok.com/en-us/how-tiktok-recommends-videos-for-you",
        "https://ads.tiktok.com/resources/help/article/search-ads-creative",
        "https://www.socialmediatoday.com/news/tiktok-lets-users-add-relevant-keywords-to-metadata/818507/",
        "https://arxiv.org/html/2505.08385v1",
        "https://ads.tiktok.com/help/article/add-product-links-tiktok-videos?lang=en",
        "https://newsroom.tiktok.com/en-us/celebrating-global-accessibility-awareness"
      ]
    },
    "instagram": {
      "caption_max_chars": 2200,
      "caption_recommended_chars": [125, 400],
      "first_line_chars_visible": 125,
      "hashtags": {"min": 1, "max": 5, "recommended": 3},
      "mentions_max": 20,
      "title_max_chars": null,
      "description_max_chars": null,
      "alt_text": {"supported": false, "max_chars": 1000, "how": "API alt_text works on IMAGE/carousel-image containers only (Reels and Stories unsupported); app: Advanced settings > Accessibility for photos. Reels in-app alt text UNVERIFIED -> put the description sentence in the caption."},
      "cover": {"aspect": "9:16 JPEG <=8MB via cover_url (or thumb_offset ms)", "safe_crop": "grid = centre 3:4 (y240-1680); feed share = centre 1:1 (y420-1500); use text box x120-888, y420-1248", "text_max_words": 5},
      "keyword_slots": [
        {"slot": "spoken_hook", "required": true, "rule": "primary keyword spoken by 3.0 s"},
        {"slot": "on_screen_text", "required": true, "rule": "primary keyword card by 3.0 s"},
        {"slot": "caption_line_1", "required": true, "rule": "keyword within first 60 chars; natural sentence (doubles as Google snippet)"},
        {"slot": "caption_description_sentence", "required": true, "rule": "alt-text substitute: one literal description of what is shown"},
        {"slot": "hashtags", "required": true, "rule": "<=5; one = primary keyword"},
        {"slot": "cover_text", "required": true, "rule": "keyword head noun"},
        {"slot": "profile_name_bio", "required": false, "rule": "account-level niche keyword"},
        {"slot": "audio_name", "required": false, "rule": "original audio can be renamed once; optional '<keyword> test - original audio' [A]"}
      ],
      "disclosure": {"ai_label_toggle": "is_ai_generated=true (API, since 2026-06-22) / AI info label (app)", "paid_partnership": "is_paid_partnership=true or branded_content_sponsor_ids (Facebook Login only)"},
      "extras": {"trial_reels": "trial_params.graduation_strategy MANUAL|SS_PERFORMANCE; metrics ~24 h; auto-share window 72 h", "collaborators_api_max": 3, "location": "location_id only if true", "post_publish_check": "config_issue must not be CAPTION_NOT_ATTACHED"},
      "audio_notes": "Library music withholds media_url from API readers and limits commercial use; original audio + VO keeps the spoken keyword clean.",
      "sources": [
        "https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/",
        "https://developers.facebook.com/docs/instagram-platform/changelog",
        "https://about.instagram.com/blog/announcements/break-down-how-instagram-search-works/",
        "https://transparency.meta.com/features/explaining-ranking/ig-search/",
        "https://www.socialmediatoday.com/news/instagram-implements-new-limits-on-hashtag-use/808309/",
        "https://about.fb.com/news/2024/12/trial-reels-try-content-non-followers-first-see-what-perfoms-best/",
        "https://creators.instagram.com/recommendations-and-originality?locale=en_US",
        "https://ppc.land/instagram-content-becomes-searchable-on-google-starting-july-10/"
      ]
    },
    "youtube_shorts": {
      "caption_max_chars": null,
      "caption_recommended_chars": null,
      "first_line_chars_visible": null,
      "title_max_chars": 100,
      "title_recommended_chars": 60,
      "title_forbidden_chars": ["<", ">"],
      "description_max_chars": 5000,
      "description_length_unit": "UTF-8 bytes (API)",
      "description_recommended_chars": [100, 400],
      "tags_max_chars_total": 500,
      "hashtags": {"min": 1, "max": 3, "recommended": 2, "all_ignored_above": 60},
      "alt_text": {"supported": false, "max_chars": null, "how": "No alt text; upload captions.srt (plain UTF-8) as the accessible text track."},
      "cover": {"aspect": "9:16", "safe_crop": "text box x120-888, y420-1248", "text_max_words": 5, "custom_upload": "YPP channels, desktop Studio, since 2026-07-24, no A/B; otherwise choose a frame"},
      "keyword_slots": [
        {"slot": "title", "required": true, "rule": "primary keyword within first 40 chars; no hashtags beyond 1"},
        {"slot": "spoken_hook", "required": true, "rule": "primary keyword spoken by 3.0 s"},
        {"slot": "on_screen_text", "required": true, "rule": "primary keyword card by 3.0 s"},
        {"slot": "description_line_1", "required": true, "rule": "one sentence with primary + one secondary keyword"},
        {"slot": "hashtags", "required": true, "rule": "2-3 in description; one = primary keyword"},
        {"slot": "captions_track", "required": true, "rule": "upload captions.srt"},
        {"slot": "tags", "required": false, "rule": "misspellings/variants only"},
        {"slot": "related_video", "required": false, "rule": "link the series_plan follow-up"}
      ],
      "disclosure": {"ai_label_toggle": "Altered or synthetic content = Yes / status.containsSyntheticMedia=true", "paid_partnership": "Paid promotion / paidProductPlacementDetails.hasPaidProductPlacement=true"},
      "audio_notes": "Audio Library sounds can surface on sound pages; Content ID changes for 1-3 min Shorts in virality §3.",
      "sources": [
        "https://support.google.com/youtube/answer/57407?hl=en",
        "https://developers.google.com/youtube/v3/docs/videos",
        "https://support.google.com/youtube/answer/6390658?hl=en",
        "https://support.google.com/youtube/answer/15424877?hl=en",
        "https://support.google.com/youtube/answer/16090438?hl=en",
        "https://support.google.com/youtube/answer/11914225?co=YOUTUBE._YTVideoType%3Dshorts&hl=en",
        "https://www.tubefilter.com/2026/07/24/youtube-shorts-custom-thumbnails-neal-mohan-feature-update/"
      ]
    }
  }
}
```

```json
{
  "KEYWORD_RULES": {
    "primary": {
      "count": 1,
      "words": {"min": 2, "max": 4},
      "form": "lowercase search phrase, singular head noun, no brand unless owned",
      "match": "exact phrase, or all content-word lemmas present (order-free); pronouns never count",
      "placement": {
        "spoken": {"by_s": 3.0, "min": 1, "max_per_30s": 3},
        "on_screen": {"by_s": 3.0, "min_duration_s": 1.0, "max_words": 4, "box_1080x1920": {"x": [120, 888], "y": [288, 1248]}, "max_cards_with_keyword": 2},
        "caption_first_line": {"within_chars": 60, "line_max_chars": {"tiktok": 100, "instagram": 125}},
        "yt_title": {"within_chars": 40},
        "alt_text_substitute": "one literal description sentence containing the keyword once",
        "cover_text": {"contains": "head noun", "max_words": 5},
        "hashtag": "exactly one hashtag = primary keyword without spaces"
      }
    },
    "secondary": {"max": 2, "placement": ["caption line 2 or YT description", "optional one hashtag each", "optional one spoken mention in body", "TikTok Manage Keywords suggestions"]},
    "density": {
      "caption_primary_exact_max": 2,
      "caption_plus_hashtags_same_stem_max": 3,
      "hashtags_off_topic_max": 0,
      "banned_filler_tags": ["#fyp", "#foryou", "#foryoupage", "#viral", "#trending", "#explorepage", "#shorts"],
      "yt_description_rules": ["no tag lists", "no repeated sentences"],
      "manage_keywords_suggest_max": 3
    },
    "intent_templates": [
      {"template": "{product} review", "formats": ["review"], "hook_families": ["transformation", "question", "proof-first"]},
      {"template": "is {product} worth it", "formats": ["review"], "hook_families": ["question", "curiosity-gap"]},
      {"template": "{product} vs {alternative}", "formats": ["review", "demo"], "hook_families": ["comparison"], "requires": "real side-by-side footage; factual only"},
      {"template": "how to use {product}", "formats": ["demo"], "hook_families": ["showcase", "listicle"]},
      {"template": "what to know before buying {product}", "formats": ["demo", "review"], "hook_families": ["negative-command", "problem-agitate"]},
      {"template": "{product} mistakes", "formats": ["demo"], "hook_families": ["negative-command", "contrarian-reframe"]},
      {"template": "does {product} work", "formats": ["review", "demo"], "hook_families": ["proof-first", "question"]},
      {"template": "{category} hack", "formats": ["demo"], "hook_families": ["showcase", "newness"]},
      {"template": "{product} for {use}", "formats": ["demo", "review"], "hook_families": ["problem-agitate", "pov"]},
      {"template": "best {category} for {use}", "formats": ["review"], "hook_families": ["question"], "requires": "question/search-label form only, never asserted (D141)"},
      {"template": "{product} before and after", "formats": ["review"], "hook_families": ["transformation", "day-counter"], "requires": "honest, dated comparison"},
      {"template": "{category} under ${price}", "formats": ["review", "demo"], "hook_families": ["price-anchor"], "requires": "price supplied (D37)"},
      {"template": "{n} day {habit} challenge", "formats": ["pov-vlog"], "hook_families": ["challenge", "day-counter"]},
      {"template": "quit {thing} for {n} days", "formats": ["pov-vlog"], "hook_families": ["challenge", "confession"]}
    ],
    "selection_rules": [
      "1. Normalize the product noun phrase from the prompt (singular, lowercase, drop brand unless owned); its last noun is the head noun.",
      "2. Expand candidates with intent_templates allowed for the script's format and hook family.",
      "3. Drop candidates that fail guardrails: unsupported superlative claim (D141), price without a supplied price (D37), health/absolute outcomes, competitor names without real footage.",
      "4. Score demand 0-1: research-DB n-gram frequency in the niche's top reels (7-30 d, views-weighted) 0.5 + human-logged autocomplete or Creator Search Insights/YT Trends hit 0.3 + Google Trends (YouTube Search) non-zero 0.2.",
      "5. Add +0.1 if flagged as a content gap (TikTok Creator Search Insights or YT 'content gaps for Shorts').",
      "6. Require that the video actually answers the query (payoff matches intent); otherwise score 0.",
      "7. Tie-break: fewer words, head noun first, natural fit in the existing spoken hook.",
      "8. Pick exactly one primary; take the next two non-overlapping candidates as secondary; store all in the bundle (keyword, source, score)."
    ],
    "soft_rubric": {"comment_word_equals_head_noun": "warn if the comment-word is not the head noun (TikTok search suggestions draw on comments) [A]"}
  }
}
```

```json
{
  "POSTING_GUIDANCE": [
    {"id": "PG1", "platform": "all", "guidance": "Post shortly before your own audience's active window (TikTok Studio Followers > Most active times; IG app insights; YT 'When your viewers are on YouTube').", "label": "evidence-backed", "grade": "M", "source": "https://buffer.com/resources/when-is-the-best-time-to-post-on-instagram/"},
    {"id": "PG2", "platform": "all", "guidance": "A universal 'best time to post' (e.g. Sun 9 am) will lift reach.", "label": "myth/weak", "grade": "A", "source": "https://buffer.com/library/best-time-to-post-on-tiktok/"},
    {"id": "PG3", "platform": "tiktok", "guidance": "2-5 posts/week vs 1 raises views/post ~17% by lifting the top decile; the median post doesn't improve.", "label": "evidence-backed", "grade": "M", "source": "https://buffer.com/resources/how-often-should-you-post-on-tiktok/"},
    {"id": "PG4", "platform": "instagram", "guidance": "3-5 posts/week roughly doubles follower growth vs 1-2.", "label": "evidence-backed", "grade": "M", "source": "https://socialmediatoday.com/news/study-shows-posting-more-instagram-leads-to-more-reach/757633/"},
    {"id": "PG5", "platform": "youtube_shorts", "guidance": "No minimum posting cadence is required; ranking follows viewer choice, retention and satisfaction.", "label": "evidence-backed", "grade": "P", "source": "https://support.google.com/youtube/answer/11914225?co=YOUTUBE._YTVideoType%3Dshorts&hl=en"},
    {"id": "PG6", "platform": "instagram", "guidance": "Test hooks as Trial Reels (MANUAL), read at 24-72 h, graduate the winner.", "label": "evidence-backed", "grade": "P", "source": "https://about.fb.com/news/2024/12/trial-reels-try-content-non-followers-first-see-what-perfoms-best/"},
    {"id": "PG7", "platform": "all", "guidance": "More hashtags = more reach.", "label": "myth/weak", "grade": "P", "source": "https://www.socialmediatoday.com/news/instagram-implements-new-limits-on-hashtag-use/808309/"},
    {"id": "PG8", "platform": "tiktok", "guidance": "#fyp / #foryou / #viral tags push videos to the For You feed.", "label": "myth/weak", "grade": "A", "source": "https://newsroom.tiktok.com/en-us/how-tiktok-recommends-videos-for-you"},
    {"id": "PG9", "platform": "youtube_shorts", "guidance": "#Shorts is required for a video to be a Short.", "label": "myth/weak", "grade": "P", "source": "https://support.google.com/youtube/answer/15424877?hl=en"},
    {"id": "PG10", "platform": "all", "guidance": "Keyword-rich file names improve ranking.", "label": "myth/weak", "grade": "A", "source": "https://support.google.com/youtube/answer/16090438?hl=en"},
    {"id": "PG11", "platform": "youtube_shorts", "guidance": "Tags drive discovery.", "label": "myth/weak", "grade": "P", "source": "https://support.google.com/youtube/answer/57407?hl=en"},
    {"id": "PG12", "platform": "all", "guidance": "Upload a clean, watermark-free master per platform; watermarked or copied content loses recommendation eligibility on Instagram.", "label": "evidence-backed", "grade": "P", "source": "https://creators.instagram.com/recommendations-and-originality?locale=en_US"},
    {"id": "PG13", "platform": "all", "guidance": "Explicitly asking for shares, tags or likes boosts distribution.", "label": "myth/weak", "grade": "P", "source": "https://transparency.meta.com/features/approach-to-ranking/content-distribution-guidelines/engagement-bait/"},
    {"id": "PG14", "platform": "tiktok", "guidance": "Track search share of views (Creator Search Insights / traffic source) and refine keywords with Manage Keywords.", "label": "evidence-backed", "grade": "S", "source": "https://www.socialmediatoday.com/news/tiktok-lets-users-add-relevant-keywords-to-metadata/818507/"},
    {"id": "PG15", "platform": "instagram", "guidance": "Verify every API publish: config_issue=CAPTION_NOT_ATTACHED means the caption (and its keywords) was dropped.", "label": "evidence-backed", "grade": "P", "source": "https://developers.facebook.com/docs/instagram-platform/changelog"}
  ]
}
```

```json
{
  "DISCOVERY_CHECKLIST": {
    "all": [
      "Choose 1 primary + <=2 secondary keywords (KEYWORD_RULES.selection_rules); record source and score",
      "Primary keyword spoken by 3.0 s and on screen by 3.0 s (>=1 s, safe box)",
      "Comment-word = keyword head noun; exactly one CTA destination per platform (D46)",
      "No bait (D139), invented numbers (D37/D136) or absolute claims (D141) in any caption, title, description, cover or alt-text substitute",
      "AI presenter: caption disclosure line (D138) + each platform's AI toggle",
      "Designate a cover frame/image with <=5 words inside x120-888, y420-1248",
      "Export a clean master per platform (no foreign watermark); attach captions.srt"
    ],
    "tiktok": [
      "Caption line 1 = hook with keyword in first 60 chars, line <=100 chars; total <=2,200 UTF-16 via API",
      "Add one plain description sentence (alt-text substitute)",
      "3 hashtags (max 5): primary keyword, niche community, intent/format; none off-topic",
      "Set video_cover_timestamp_ms to the cover frame",
      "Set is_aigc / brand_content_toggle / brand_organic_toggle as applicable",
      "Shop: product link name = keyword + attribute, no promo text/emoji/price",
      "After publish: pin a comment with keyword + CTA; Manage Keywords suggest/block",
      "Day 7: check search share in Creator Search Insights; log results"
    ],
    "instagram": [
      "Caption line 1 natural sentence with keyword in first 60 chars (<=125); total <=2,200",
      "Description sentence as alt-text substitute; <=5 hashtags (3 recommended)",
      "cover_url JPEG 9:16 with text in the 3:4/1:1-safe box (or thumb_offset)",
      "is_ai_generated / is_paid_partnership as applicable; collaborators <=3; location only if true",
      "Hook test: 2-3 Trial Reels (MANUAL), compare skip rate/watch time/shares at 24-72 h, graduate winner",
      "Check media_publish response: no config_issue CAPTION_NOT_ATTACHED",
      "Comment-word DMs via Private Replies within 7 days (one per comment)"
    ],
    "youtube_shorts": [
      "Title <=100 chars (target <=60), keyword in first 40 chars, no < >",
      "Description <=5,000 bytes: keyword sentence, disclosure, 2-3 hashtags; no tag lists",
      "Tags only for misspellings (<=500 chars)",
      "Upload captions.srt",
      "Altered/synthetic = yes for realistic AI persona; paid promotion if applicable",
      "Custom thumbnail if YPP (desktop), else pick the cover frame",
      "Related video -> series_plan follow-up; CTA = comment-word or Related video, not a link",
      "Day 7/28: Shorts analytics 'chose to view' vs swiped away; Trends tab content gaps for next keyword"
    ]
  }
}
```

**Proposed gate and rubric rules** (IDs chosen to avoid clashing with D-numbers):

```json
{
  "GATE_RULES": [
    {"id": "DISC-01", "name": "keyword_spoken_early", "stage": "gate1", "severity": "error", "check": "primary keyword (exact or all content lemmas) in dialogue whose cue ends <= 3.0 s", "threshold": {"by_s": 3.0, "max_per_30s": 3}, "source": "https://ads.tiktok.com/help/article/creative-best-practices ; https://support.google.com/youtube/answer/16090438?hl=en"},
    {"id": "DISC-02", "name": "keyword_on_screen", "stage": "gate2", "severity": "error", "check": "an on_screen card containing the primary keyword starts <= 3.0 s, lasts >= 1.0 s, <= 4 words, inside x120-888/y288-1248", "threshold": {"by_s": 3.0, "min_s": 1.0}, "source": "https://ads.tiktok.com/resources/help/article/search-ads-creative"},
    {"id": "DISC-03", "name": "caption_first_line", "stage": "gate2", "severity": "error", "check": "primary keyword within the first 60 chars of caption line 1; line 1 <= 100 (TikTok) / 125 (Instagram) chars", "threshold": {"within_chars": 60}, "source": "https://about.instagram.com/blog/announcements/break-down-how-instagram-search-works/"},
    {"id": "DISC-04", "name": "hashtag_budget_relevance", "stage": "gate2", "severity": "error", "check": "count within platform max (TT 5, IG 5, YT 3); exactly one tag = primary keyword; 0 off-topic or filler tags (token overlap with keywords or niche map)", "threshold": {"tiktok_max": 5, "instagram_max": 5, "youtube_max": 3, "off_topic_max": 0}, "source": "https://www.socialmediatoday.com/news/instagram-implements-new-limits-on-hashtag-use/808309/ ; https://support.google.com/youtube/answer/6390658?hl=en"},
    {"id": "DISC-05", "name": "no_keyword_stuffing", "stage": "gate2", "severity": "warn", "check": "primary exact <= 2 in caption; same stem <= 3 across caption+hashtags; YT description has no tag lists or repeated sentences", "threshold": {"caption_exact_max": 2, "stem_max": 3}, "source": "https://support.google.com/youtube/answer/6390658?hl=en"},
    {"id": "DISC-06", "name": "platform_hard_limits", "stage": "export", "severity": "error", "check": "TT caption <= 2,200 UTF-16 units; IG caption <= 2,200 chars, <= 20 mentions; YT title <= 100 chars without < >, description <= 5,000 UTF-8 bytes, tags <= 500 chars", "threshold": {"tt_utf16": 2200, "ig_chars": 2200, "yt_title": 100, "yt_desc_bytes": 5000}, "source": "https://developers.tiktok.com/doc/content-posting-api-reference-direct-post ; https://developers.google.com/youtube/v3/docs/videos"},
    {"id": "DISC-07", "name": "cover_safe", "stage": "gate2", "severity": "error", "check": "cover frame/image designated; cover text <= 5 words, contains head noun, all glyphs inside x120-888/y420-1248", "threshold": {"max_words": 5, "box": {"x": [120, 888], "y": [420, 1248]}}, "source": "https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media/"},
    {"id": "DISC-08", "name": "disclosure_flags", "stage": "export", "severity": "error", "check": "presenter=ai -> TT is_aigc, IG is_ai_generated, YT containsSyntheticMedia all true + caption line (D138); paid -> brand_content_toggle / is_paid_partnership / hasPaidProductPlacement", "threshold": {"missing_allowed": 0}, "source": "https://developers.facebook.com/docs/instagram-platform/changelog ; https://developers.google.com/youtube/v3/docs/videos"},
    {"id": "DISC-09", "name": "compliance_parity", "stage": "gate2", "severity": "error", "check": "D46 one CTA destination, D139 bait lexicon, D37/D136 numbers and D141 absolutes applied to every platform caption, YT title/description, cover text and description sentence; YT CTA is not a URL", "threshold": {"cta_destinations_per_platform": 1, "violations": 0}, "source": "https://transparency.meta.com/features/approach-to-ranking/content-distribution-guidelines/engagement-bait/"},
    {"id": "DISC-10", "name": "clean_master_and_publish_verify", "stage": "publish", "severity": "error", "check": "no foreign-platform watermark in any master; after IG publish, config_issue must be absent (CAPTION_NOT_ATTACHED -> alert)", "threshold": {"watermarks": 0, "config_issue": "none"}, "source": "https://creators.instagram.com/recommendations-and-originality?locale=en_US ; https://developers.facebook.com/docs/instagram-platform/changelog"}
  ]
}
```

## 9. Still UNVERIFIED

- TikTok:
  - whether the API enforces the 5-hashtag cap
  - the profile-grid crop ratio
  - that covers can't be edited after posting
  - whether standalone Keyword Insights still exists, and whether the Creative Center has an API
  - the product-link name limit
  - official documentation of ASR and OCR search indexing
  - any feature called "Search Highlights"
  - a compliant comment-to-DM route
- Instagram:
  - in-app custom alt text for Reels
  - whether Reels search uses on-screen text or speech
  - the Trial Reels follower threshold
  - how near-duplicate trials are treated
  - the exact help-page wording on search-engine indexing
  - whether `online_followers` calls still return data
  - send-to-like weight ratios
- YouTube: the visible title length in the Shorts player, and the crop used for Shorts shelf thumbnails.
- Across platforms: the search effect of uploaded captions, and the "first N seconds" keyword uplift figures quoted by vendors.

Content was rephrased for compliance with licensing restrictions.
