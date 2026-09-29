# Shot recommendations for phone creators and AI video models (checked 2026-09-29)

**Scope.** Which shots the shot list (`shots.json`) and render brief should recommend, for a human filming on a phone and for an AI video model rendering one prompt per shot. Hook timing, safe-zone pixels, platform policy and disclosure are in [short-form-virality.md](short-form-virality.md) ("virality" below); cover frames are in [discovery-seo.md](discovery-seo.md) ("discovery"). This file cites them and doesn't repeat them. All ids come from `vsp/creative_vocab.py`; new ids are in §5.6.

**Grades.** **[P]** platform/legal rule or official doc · **[S]** strong (peer-reviewed or first-party research, large datasets) · **[M]** moderate (vendor datasets, single studies, conference papers) · **[A]** anecdotal, practitioner or our inference. **UNVERIFIED** = no primary source confirmed it.

## TL;DR

1. **Open on the product or the result, not a face.** Less face time before the skip button went with more views, significantly so for utilitarian products ([Hilton et al. 2026](https://link.springer.com/article/10.1007/s11002-026-09839-0)) [S]. Get a human cue in by 3 s, and make it hands on the product. Faces lift early retention only ([Emplifi 2026](https://emplifi.io/resources/facebook-reels-data/)) [M].
2. **Pace to real medians.** Top talking-head TikToks run 1.9–5.2 cuts per 10 s (16th–84th percentile), and faster pacing reduced completion ([Dost & Huang 2026](https://archives.marketing-trends-congress.com/2026/pages/PDF/paper_professor_DOST_HUANG.pdf)) [M]. Both too few and too many shots hurt ([Xiao, Li & Mou 2024](https://www.emerald.com/insight/content/doi/10.1108/INTR-07-2023-0521/full/html)) [S]. `SHOT_RULES.cadence` sets one band per vibe.
3. **Hands: best trust cue for humans, worst risk for AI.** Watching someone touch a product raises purchase intention ([2022](https://link.springer.com/article/10.1007/s12144-022-03221-9)) [S]. Frontier models still show objects passing through hands, moving without contact and deforming ([ABot-PhysWorld 2026](https://arxiv.org/abs/2603.23376)) [M].
4. **Before/after follows the clinical protocol:** taped phone spot, same lens, light and background ([ASDS](https://www.asds.net/Portals/0/PDF/Resident-Kit-Allergan-Before-After-Photo-Guidelines.pdf)) [S]. AI never renders the "after".
5. **Loops pay on short videos:** +18.7% replays and +23.6% reach for Reels of 7 s or less (Emplifi) [M]. Required at ≤15 s.
6. **TikTok Shop sets shot-level rules** [P]:
   - ≥3 s of dynamic, real-setting footage with camera movement, people and a face;
   - a multi-angle demo;
   - stabilised footage;
   - on-screen text in sync with speech.
7. **Sora is gone** (API off 24 Sep 2026). Use Gemini Omni Flash (3–10 s) or Veo 3.1 (4/6/8 s). Kling 3.0 and Seedance 2.0 reach 15 s, Wan 3.0 reaches 30 s, and all render 9:16.
8. **What AI does well and badly.** It renders camera moves over a still product, textures, rooms and silent reactions well. It fails at small-object handling, readable text, rigid or fast physics, identity without references and long lip-synced lines. So every shot carries an `ai_risk` and an `ai_fallback`.
9. **Fixes for today's bundles:**
   - no model-drawn text and no quoted dialogue;
   - no persona text in product-only inserts;
   - film a real BEFORE, or drop the "side by side" payoff line.

## 1. What the current shot lists do (gap check)

| Bundle | What works | Gaps this research addresses |
|---|---|---|
| electric-milk-frother (AI, demo) | Product mid-action at frame 0; D47/D48 pass; three angles in the demo | <ul><li>Ten of 12 shots run 2.5–2.8 s, a flat ≈3.9 cuts/10 s whatever the vibe.</li><li>Shot 1 (hands on a small device) is the riskiest AI shot, placed on the most important frame.</li><li>3a and 3d are the same "macro texture/label" insert, and "label" invites garbled text.</li><li>Every prompt, including product-only macros, starts with the persona description.</li><li>Prompts say "render exactly" for on-screen text and quote the dialogue; Google advises against both ([best practices](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/video/best-practice)).</li><li>The payoff says "before and after, side by side", but there is no BEFORE shot, and an AI render can't prove anything.</li><li>The CTA close-up ≠ frame 0, so there is no loop.</li></ul> |
| silk-pillowcase (human, review) | Product at frame 0; face at 0.5 s | <ul><li>The imperfection beat is one 4.9 s handheld take with no product in it.</li><li>A "7 days" review has no matched morning before/after, no comparison and no time marker.</li><li>The shots are listed in timeline order, with no setups or prop list.</li></ul> |
| sugar-21 (human, challenge, pov-vlog) | Problem-state frame 0 suits a challenge; typed-comment insert | <ul><li>Both story beats repeat the same four-shot template (selfie → insert → ¾ reaction → selfie).</li><li>A day-count story never shows a day counter, a timelapse or a matched before.</li></ul> |

None of the three carries a lighting preset, a setup grouping, per-shot AI risk or a loop plan.

## 2. Shot grammar that performs

### 2.1 First frame and product visibility
- **Product and result early.** Virality §1 already covers this: +65% affinity when the product is on screen, the TikTok Shop hook rule, and OpusClip's showcase hooks.
- **Show it in use.** Showing the product in use beats showing how it looks ([Frontiers 2022](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2022.812579/full)) [S].
- **Keep it on screen.** Google's ABCDs say to show the product from the start and keep it there ([ABCD](https://support.google.com/google-ads/answer/14783551?hl=en)) [P/S]. VidMob's scoring template gives "brand present in ≥50% of duration" as an example guideline ([VidMob](https://help.vidmob.com/en/articles/6519983-what-criteria-are-available-for-creative-scoring)) [M].
- **Rule** [A, derived]:
  - Frame 0 shows the product in use or the result. For no-product concepts, it shows the subject or problem.
  - Never open on a talking head.
  - The product is visible for at least 50% of runtime in product concepts.
- Cover frames: see discovery.

### 2.2 Faces and hands
- **Faces help early, not late.**
  - Human presence lifted Reels ad CTR by 27% (virality §1) [S].
  - A person on screen for at least 1 s in the first 3 s gave +3.6% 3-s and +10.1% 10-s retention. But it gave −2.4% at 30 s and −7.4% reach, across 10k+ brand Reels ([Emplifi](https://emplifi.io/resources/facebook-reels-data/); [SMK summary](https://smk.co/study-human-presence-boosts-reels-retention/)) [M].
  - Pre-skip face time hurt views for utilitarian products and was neutral for hedonic ones (Hilton 2026) [S, pre-roll context].
- **Platforms still want people.** TikTok Shop expects a face on camera ([PPC Land on the May 2026 rules](https://ppc.land/tiktok-shops-quality-rules-ban-ai-voices-and-still-images-from-lives/)) [P]. The ABCDs for Shorts put "show talent using the product" first [P].
- **Hands.**
  - Attention to the dominant hand drove the purchase-intent lift, in both first- and third-person views (Current Psychology 2022) [S, lab].
  - Tactile demonstration videos raise purchase intent ([MDPI 2024](https://www.mdpi.com/2076-328X/14/1/50)) [M].
  - More second-person/POV shots went with higher engagement in TikTok news videos ([SSCR 2023](https://journals.sagepub.com/doi/10.1177/08944393231178603)) [S, other genre].
- **Rule** [A, derived]:
  - Hands on the product at frame 0.
  - Face or hands on screen for ≥1 s by 3.0 s. Human presenters and the Shop lane need a face by 3.0 s.
  - For utilitarian products, face-only framing takes ≤50% of 0–5 s.
  - Bring the face back at the payoff, as a reaction.

### 2.3 Shot-scale mix
- **Close-ups and medium shots.** In 400 TikToks, close-up and medium scales predicted virality (virality §7) [M].
- **Extreme close-ups.** In L'Oréal's analysis, 55% of high-performing creator videos used extreme close-ups; the sample was not disclosed ([Forbes 2026](https://www.forbes.com/sites/jamiegutfreund/2026/01/12/how-loral-unlearned-advertising-and-boosted-creator-results-55/)) [M].
- **Tight framing** is also a Shorts ABCD [P].
- **Rule:**
  - Mostly CU/ECU, anchored by MCU/MS.
  - At least 3 distinct scales per 15 s.
  - Never 3 same-scale shots in a row. This matches RULES D47's text; the gate currently checks talking heads only [A].

### 2.4 Cut cadence, pattern interrupts, B-roll
- **Shot count** has an inverted-U relationship with engagement, in 2,511 seller videos from 60 TikTok shops (Xiao 2024) [S].
- **Jump cuts and pace** (Dost & Huang 2026):
  - Real-world pace: 50 top talking-head TikToks averaged 0.37 cuts/s (range 0.13–0.82).
  - In an experiment (N=242), seamless jump cuts raised likes only at medium or high pace.
  - Overlapping cuts raised completion and rewatch at low and medium pace; at high pace that gain disappeared.
  - The authors advise pacing near the median, not at the extremes [M].
- **Early pace.**
  - TikTok says faster scene changes pull viewers in early ([Creative Codes](https://ads.tiktok.com/business/en/blog/creative-best-practices-top-performing-ads)) [S].
  - Emplifi found pacing mattered little, and a slower start gave +7.7% 30-s retention [M].
  - "A pattern interrupt every 2–5 s" is creator lore [A]. It matches the 1.9–5.2 cuts/10 s band.
- **B-roll share.**
  - A 30-s UGC ad cuts to B-roll 6–10 times for 1–2 s each, i.e. about 20–60% of runtime; organic posts cut less ([Influee 2026](https://influee.co/gb/blog/effectively-use-your-raw-review-videos-and-b-roll-shots)) [A].
  - Speech-led openings beat music-only by +24.7% at 10 s (Emplifi) [M]. So B-roll should usually play under the creator's voice, not replace it.

### 2.5 Shot types
- **Macro and POV hands.** Evidence is in §2.2–2.3. Record the product's real sound (Influee) [A]. Meta suggests the selfie camera for first-person shots ([Meta creators](https://creators.facebook.com/reels-best-practices-tips-tricks)) [P].
- **Before/after.** Use the clinical standard (ASDS) [S]:
  - tripod or taped spot;
  - camera at eye height;
  - fixed distance;
  - marked light position;
  - flash off;
  - same background and frame size.

  Misleading before/afters are banned in TikTok ads (virality §3) [P]. Add a time marker and hold each state ≥1.5 s [A].
- **Reaction cutaways.** Facial expressions predicted views better than text sentiment (virality §7) [M]. Use reactions after the hook (payoff, demo), not as frame 0 (§2.2).
- **Text-first cards.**
  - Text that gets people reading lifts view time and recall (Creative Codes) [S].
  - Text helps music-led Reels (+9.8% at 30 s) but slightly hurts speech-led ones (−6% at 10 s) (Emplifi) [M].
  - VidMob encodes Google's "≤10 words per frame" ([Dec 2025](https://help.vidmob.com/en/articles/14690582-december-2025-product-update)) [M].
  - Our cap stays at ≤3 words at frame 0. Card timing is in virality §2.

### 2.6 Transitions and camera moves
- **Speed changes.**
  - Slow motion raised likes and views of short videos, plus brand liking and willingness to pay, via processing fluency ([Stuppy, Landwehr & McGraw 2024, JMR](https://journals.sagepub.com/doi/full/10.1177/00222437231179187)) [S]. It also amplifies unpleasant imagery ([summary](https://www.productmarketingalliance.com/why-slow-motion-can-improve-product-marketing/)) [M].
  - Fast and slow motion make everyday content awe-inspiring and slow satiation over eight repeat views, but only for movement you can't see in real time. Reverse motion doesn't work ([Stuppy, Anderson & Sellier 2025](https://archives.marketing-trends-congress.com/2025/pages/PDF/039.pdf)) [M].
  - **Use:** slow motion for pours, splashes and drops, and time-lapse for slow processes. Never use reverse, and never slow down something ugly.
- **Transitions and rewatch.** Meta notes a clever transition can prompt a rewatch [P]. TikTok recommends transitions, stickers and graphics to hold engagement ([Ads Help](https://ads.tiktok.com/help/article/creative-best-practices?lang=en)) [P].
- **Whip pans, match cuts, push-ins:** craft practice with no controlled evidence [A].
  - Push-in is the house move because it satisfies D48.
  - "Handheld" must still be stabilised for TikTok Shop [P].
  - Google's prompt guide treats whip pan, arc, match cut and jump cut as promptable terms ([guide](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/video-gen-prompt-guide)) [P].

### 2.7 Loop endings
- **Evidence.**
  - Seamless loops: +18.7% replays, +23.6% reach and +16.1% engagement on videos of 7 s or less, fading with length (Emplifi) [M].
  - The Shorts feed loops by itself, and replays count as views (virality §3; [Google partner deck](https://services.google.com/fh/files/events/partner_center__youtube_shorts_best_practices_and_roadblocks__july_2026.pdf)) [P].
  - Gemini Omni can use one image as both the first and last frame to make a loop ([Omni docs](https://ai.google.dev/gemini-api/docs/omni)) [P]. Luma Ray3.14 has a loop mode ([FAQ](https://lumalabs.ai/learning-hub/ray3-faq)) [P].
- **Rule:**
  - At ≤15 s, the last shot returns to frame 0's framing and motion.
  - Above 15 s, score it as a bonus only.

### 2.8 Phone lighting
- **Official guidance** [P]:
  - Meta: natural light is best; avoid direct sun, overhead light and backlight.
  - TikTok Shop: enough light to show product detail.
  - TikTok's commercial-content standard makes lighting and composition a baseline for image quality ([TikTok CQS](https://ads.tiktok.com/help/article/about-tiktoks-content-quality-standard-for-creator-commercial-content)).
- **Presets** in `SHOOT_PLAN_RULES`: window key, bounce, soft overhead, raking side light, warm practical and ring light [A].
- **Always lock exposure and focus** (touch and hold for AE/AF lock; [Apple](https://support.apple.com/en-gb/guide/iphone/iph3dc593597/ios)) [P].

### 2.9 9:16 composition
Safe zones are in virality §2. Derived framing on a 1080×1920 frame [A]:
- eyes at y≈560–760;
- product hero within x 240–840, y 640–1248;
- hands enter from the bottom edge;
- nothing important on the right rail or in the bottom caption band;
- generate natively in 9:16 rather than cropping 16:9.

### 2.10 Creator shooting efficiency
- **Order the shoot by setup, not story.** Re-sort the shot list by location and light ([example](https://firsttakeguide.com/)) [A].
- **B-roll first,** while the product is still pristine (Influee) [A].
- **Coverage:** roll about 10 s per clip, get 2–3 angles per action, and aim for 20–30 clips per 30-s ad (Influee) [A].
- **Batching** is standard creator practice ([Sprout Social](https://sproutsocial.com/insights/batch-content-tiktok/?amp)) [A]. Rules are in §5.4.

## 3. Platform creative guidance at shot level

| Source | Shot-level guidance | Grade |
|---|---|---|
| TikTok Creative Codes / Ads Help | <ul><li>Faster scene changes early.</li><li>Text overlays lift view time and recall.</li><li>Feature people; a DIY, lightly polished look.</li><li>Transitions, stickers and graphics.</li><li>3–5 creatives per ad group, very different from each other.</li><li>Hook and proposition timing: virality §1.</li></ul> | S/P |
| TikTok commercial-content quality standard | <ul><li>Baselines: clear, stable image; proper light and composition; audio in sync.</li><li>Hook within 6 s; smooth camera work.</li><li>Demonstrate the usage, the effect and the everyday scenario the product belongs to.</li></ul> | P |
| TikTok Shop "High-Quality Videos and LIVEs" (US, 23 May 2026) | <ul><li>≥3 s of dynamic footage with no stills or loops.</li><li>Real-world setting, camera movement, visible people, a face.</li><li>Product from several angles with step-by-step guidance.</li><li>Stabilised footage, adequate light, on-screen text in sync with speech.</li><li>No product-page screenshots. Caps on "non-interactive" videos: virality §3.</li></ul> | P |
| TikTok Symphony product avatar | <ul><li>Upload a product image; an avatar holds, shows or models it.</li><li>The still is generated first, then animated.</li><li>Clothing accessories are not supported; exports carry an AI label ([help](https://ads.tiktok.com/help/article/how-to-generate-a-custom-avatar-with-symphony-creative-studio)).</li></ul> | P |
| Meta | <ul><li>Human presence +27% CTR, and adding at least one native element (virality §1).</li><li>Selfie-cam first-person shots; natural light; vertical; transitions.</li><li>No recycled watermarks or blur.</li><li>Ads with the same opening count as one creative, so alternate openings must change the frame-0 shot type (virality §4).</li></ul> | P/S |
| YouTube ABCDs for Shorts | <ul><li>Connection first: talent using the product; real people with their own POV.</li><li>Attention: announce with audio; be unavoidable; tight framing.</li><li>Organic branding; a clear CTA.</li><li>Core ABCDs: bright, high-contrast visuals; brand from the start and throughout.</li><li>VidMob's Google checks: human presence in the first 5 s, ≤10 words per frame.</li></ul> | P/S; M |

## 4. AI video generation, 2025–2026

### 4.1 Models, clip lengths, 9:16

| Model (status on 2026-09-29) | Clip length | Consistency tools | Notes |
|---|---|---|---|
| **Gemini Omni Flash 1.1** (Google's default since May 2026) [P] | <ul><li>3–10 s per call</li><li>extend in 10-s steps to 40 s</li></ul> | <ul><li>image references</li><li>≤3 video references of ≤3 s</li><li>first/last frame</li></ul> | <ul><li>9:16 supported; native audio.</li><li>Makes several shots by default unless you ask for one continuous shot.</li><li>No negative-prompt parameter: write "Do not…" in the prompt.</li><li>Uploads of recognisable people blocked; SynthID watermark ([docs](https://ai.google.dev/gemini-api/docs/omni)).</li></ul> |
| **Veo 3.1 / Fast / Lite** [P] | <ul><li>4, 6 or 8 s (8 s is required for references, 1080p, 4K and extension)</li><li>extend by 7 s up to 20 times, max 148 s, at 720p</li></ul> | <ul><li>≤3 "asset" references (person, character or product)</li><li>first + last frame</li></ul> | <ul><li>9:16 supported; 24 fps; audio always on ([docs](https://ai.google.dev/gemini-api/docs/veo)).</li></ul> |
| **Sora 2 / 2 Pro**: retired [P] | none | none | <ul><li>App shut 26 Apr 2026; API shut 24 Sep 2026, with no replacement ([OpenAI](https://developers.openai.com/api/docs/guides/video-generation/)).</li><li>Its [prompting guide](https://developers.openai.com/cookbook/examples/sora/sora2_prompting_guide/) is still useful (§4.3).</li></ul> |
| **Kling 3.0 / 3.0 Omni** (Feb 2026) | ≤15 s | <ul><li>references from a video or several images</li><li>storyboard setting size, angle and move per shot</li></ul> | <ul><li>Native multi-language audio.</li><li>Claims logos stay readable (vendor claim, UNVERIFIED) ([PR](https://www.prnewswire.com/news-releases/kling-ai-launches-3-0-model-ushering-in-an-era-where-everyone-can-be-a-director-302679944.html)).</li></ul> |
| **Seedance 2.0** (Feb 2026) | 4–15 s at 480p/720p | ≤9 image, 3 video and 3 audio references | <ul><li>Multi-shot, native audio ([paper](https://huggingface.co/papers/2604.14148)).</li><li>TikTok's Creative Studio page is branded with Dreamina Seedance 2.0.</li><li>A "seedance2_5" id appears in Runway's API list (UNVERIFIED).</li></ul> |
| **Runway Gen-4.5** (Dec 2025) / **Aleph 2.0** (2026) | <ul><li>Gen-4: 5 or 10 s</li><li>Aleph edits clips up to 30 s at 1080p</li></ul> | <ul><li>references (Gen-4)</li><li>localised edits: product or colourway swap, relighting</li></ul> | <ul><li>Officially listed weaknesses: cause after effect, objects vanishing after occlusion, actions that succeed too often ([Gen-4.5](https://runway.com/research/introducing-runway-gen-4.5); [Aleph 2.0](https://runway.com/news/introducing-aleph-2-and-edit-studio)).</li></ul> |
| **Luma Ray3.14 / Ray 3.2** | <ul><li>5 or 10 s</li><li>extend to 30 s</li><li>Modify Video V2 up to 20 s</li></ul> | <ul><li>Ray 3.2: up to 16 keyframes, product swap, reframe</li><li>Ray3.14: no character references</li></ul> | <ul><li>Loop mode; no native audio on 3.14 ([FAQ](https://lumalabs.ai/learning-hub/ray3-faq); [Ray](https://lumalabs.ai/ray)).</li></ul> |
| **Wan 3.0** (24 Aug 2026) | 2–30 s | multimodal references | <ul><li>≤1080p, 9:16; hosted API in preview ([Winbuzzer](https://winbuzzer.com/2026/08/25/alibaba-launches-wan3-0-for-30-second-ai-video-from-documents-xcxwbn/); [HF](https://huggingface.co/wanvideo/wan-3-0-video)).</li></ul> |
| **Meta** | not usable for us | none | <ul><li>Movie Gen is research only.</li><li>The Vibes feed launched in Sep 2025 ([TechCrunch](https://techcrunch.com/2025/09/25/meta-launches-vibes-a-short-form-video-feed-of-ai-slop/)).</li><li>Muse Video is only a preview. Meta itself names audio-video sync and fast motion as gaps ([Meta](https://ai.meta.com/blog/introducing-muse-image-muse-video-msl/)).</li></ul> |

### 4.2 What renders reliably vs poorly

| Capability | Reliability | Evidence |
|---|---|---|
| Camera move over a still product or scene (image-to-video) | High | Google calls camera motion the simplest, most reliable way to add movement [P] |
| Textures, rooms, silent reactions | High–medium | Vendor consensus [A] |
| Liquids, pours, foam | Medium | Physics-IQ: understanding is limited overall, but fluids do better than solid mechanics ([Physics-IQ](https://physics-iq.github.io/)) [S]; Gen-4.5 claims realistic liquids [P, vendor] |
| Hands handling small objects | Low | Penetration and contact failures in Veo 3.1 and Sora 2 Pro (ABot-PhysWorld) [M]; Runway's object-permanence and causality limits [P] |
| Readable text and labels | Low | In a 2025 human-rated benchmark, most of ten systems failed at legible, consistent text ([arXiv 2505.04946](https://arxiv.org/abs/2505.04946)) [S]. Omni and Kling 3.0 claim fixes (UNVERIFIED). |
| Product fidelity across shots | Low without references; medium with them | Shape, logo and texture drift ("texture swimming") is widely reported ([example](https://invideo.io/faq/what-happens-to-ai-generated-product-videos-when-you/)) [A] |
| Fast motion, drops, throws, rigid parts | Low | Meta's Muse gaps [P]; Physics-IQ [S]; Runway's actions that succeed too often [P] |
| Face identity across shots | Medium with references, the same description and the same seed | Google best practices [P]; recognisable real people are blocked (Omni) [P] |
| Lip sync | Medium for 1–2 short lines per ≤8 s clip | Sora guide: long speeches rarely sync [P]; Veo 3.1 customer praise ([Google Cloud](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1)) [A]; Muse's audio-sync gap [P] |

### 4.3 Prompt structure
- **Veo 3.1 formula** [P]: cinematography + subject + action + context + style and ambience. Timestamped segments (e.g. [00:00-00:02]) create multi-shot sequences in one clip. Omni uses the same idea as [0-3s] timecodes.
- **Sora guide** [P, historical]:
  - One camera move and one subject action per shot.
  - Write actions as beats or counts.
  - Name 3–5 palette colours.
  - Reuse the exact character wording.
  - Short clips follow instructions better: two 4-s clips beat one 8-s clip.
- **Google best practices** [P]:
  - One focused scene per short clip.
  - Introduce dialogue after a colon, not in quotes, which can make the model render text.
  - For image-to-video, describe only the motion; don't re-describe the image.
- **Negatives.** Veo's negative prompt wants plain nouns ("wall, frame"). Omni has no negative-prompt parameter, so write "Do not…" in the prompt [P].
- **Pipeline template:** `[scale, angle, move]: [locked subject text] [one action in beats], [setting], [light + palette], vertical phone footage. Single continuous shot, no scene cuts, no on-screen text. Audio: [SFX/ambience]. [Name] says: [line]`

### 4.4 Identity and product consistency
- **Persona.**
  - Approve a reference sheet of stills first.
  - Paste the identical description in every prompt and use the same seed [P].
  - Attach references: Veo takes up to 3; Kling uses a reference video or images; Seedance takes up to 9 images.
  - With a reference loaded, don't re-describe the face ([practitioner playbook](https://github.com/raphaelbgr/ai-video-prompting)) [A].
- **Product.**
  - Use real photos: front, side, back and a detail shot [A].
  - Generate a still first, then animate it. This is how TikTok's Symphony and Google's Nano Banana → Veo workflows run [P].
  - Keep moves slow over labels.
  - Composite the real packshot or label in the edit.
- **Hybrid fallback:** film the real hands with the real product, then AI-edit the background, persona or colourway (Aleph 2.0, Ray 3.2 Modify) [P]. This is the safest route for demo and proof shots.

### 4.5 Safe fallbacks and AI-risk ratings
**Risk factors:**
- hand–object contact;
- readable text or numbers;
- rigid or fast physics;
- several objects that must stay consistent;
- lip-synced speech longer than 2 lines;
- a proof claim.

**Rating** [A, derived from §4.2]: 0 factors = low; 1 = med; 2 or more, or any proof claim = high.

**Fallback order:**
1. Remove the hands: the product operates alone.
2. Move text into edit overlays.
3. Swap a demo for a hero shot with voice-over and a text card.
4. Put voice-over over B-roll instead of on-camera speech.
5. Route to the human or hybrid lane.

Only real footage can serve as evidence. An AI "after", stress test or timestamp would be a fabricated result (FTC and TikTok rules, virality §3 and §6). Runway's own note that AI actions succeed too often makes the same point.

## 5. Deliverables

Short evidence keys used in the JSON resolve through `EVIDENCE_REFS` (§5.0). `virality §n` and `discovery` are the two sibling docs.

### 5.0 EVIDENCE_REFS

```json
{
  "EVIDENCE_REFS": {
    "TT-CreativeCodes": "https://ads.tiktok.com/business/en/blog/creative-best-practices-top-performing-ads",
    "TT-AdsHelp": "https://ads.tiktok.com/help/article/creative-best-practices?lang=en",
    "TT-CQS": "https://ads.tiktok.com/help/article/about-tiktoks-content-quality-standard-for-creator-commercial-content",
    "TT-Shop-2026": "https://ppc.land/tiktok-shops-quality-rules-ban-ai-voices-and-still-images-from-lives/",
    "TT-Symphony-avatar": "https://ads.tiktok.com/help/article/how-to-generate-a-custom-avatar-with-symphony-creative-studio",
    "TT-TopAds-spotlight": "https://ads.tiktok.com/business/creativecenter/tiktok-topads-spotlight/pc/en",
    "Meta-creators": "https://creators.facebook.com/reels-best-practices-tips-tricks",
    "Emplifi-2026": "https://emplifi.io/resources/facebook-reels-data/",
    "ABCD": "https://support.google.com/google-ads/answer/14783551?hl=en",
    "YT-Shorts-deck-2026": "https://services.google.com/fh/files/events/partner_center__youtube_shorts_best_practices_and_roadblocks__july_2026.pdf",
    "VidMob-2025": "https://help.vidmob.com/en/articles/14690582-december-2025-product-update",
    "Xiao-2024": "https://www.emerald.com/insight/content/doi/10.1108/INTR-07-2023-0521/full/html",
    "Dost-Huang-2026": "https://archives.marketing-trends-congress.com/2026/pages/PDF/paper_professor_DOST_HUANG.pdf",
    "Hilton-2026": "https://link.springer.com/article/10.1007/s11002-026-09839-0",
    "Ling-2021": "https://arxiv.org/abs/2111.02452v1",
    "Stuppy-2024": "https://journals.sagepub.com/doi/full/10.1177/00222437231179187",
    "Stuppy-2025": "https://archives.marketing-trends-congress.com/2025/pages/PDF/039.pdf",
    "Touch-2022": "https://link.springer.com/article/10.1007/s12144-022-03221-9",
    "Usage-video-2022": "https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2022.812579/full",
    "Tactile-2024": "https://www.mdpi.com/2076-328X/14/1/50",
    "SecondPerson-2023": "https://journals.sagepub.com/doi/10.1177/08944393231178603",
    "LOreal-2026": "https://www.forbes.com/sites/jamiegutfreund/2026/01/12/how-loral-unlearned-advertising-and-boosted-creator-results-55/",
    "Influee-2026": "https://influee.co/gb/blog/effectively-use-your-raw-review-videos-and-b-roll-shots",
    "ASDS": "https://www.asds.net/Portals/0/PDF/Resident-Kit-Allergan-Before-After-Photo-Guidelines.pdf",
    "Apple-AEAF": "https://support.apple.com/en-gb/guide/iphone/iph3dc593597/ios",
    "Veo-docs": "https://ai.google.dev/gemini-api/docs/veo",
    "Veo-guide": "https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1",
    "Google-best-practices": "https://docs.cloud.google.com/vertex-ai/generative-ai/docs/video/best-practice",
    "Google-prompt-guide": "https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/video-gen-prompt-guide",
    "Omni-docs": "https://ai.google.dev/gemini-api/docs/omni",
    "Sora-shutdown": "https://developers.openai.com/api/docs/guides/video-generation/",
    "Sora-guide": "https://developers.openai.com/cookbook/examples/sora/sora2_prompting_guide/",
    "Kling-3": "https://www.prnewswire.com/news-releases/kling-ai-launches-3-0-model-ushering-in-an-era-where-everyone-can-be-a-director-302679944.html",
    "Seedance-2": "https://huggingface.co/papers/2604.14148",
    "Runway-Gen-4.5": "https://runway.com/research/introducing-runway-gen-4.5",
    "Runway-Aleph-2": "https://runway.com/news/introducing-aleph-2-and-edit-studio",
    "Luma-Ray3.14": "https://lumalabs.ai/learning-hub/ray3-faq",
    "Luma-Ray3.2": "https://lumalabs.ai/ray",
    "Wan-3": "https://winbuzzer.com/2026/08/25/alibaba-launches-wan3-0-for-30-second-ai-video-from-documents-xcxwbn/",
    "Meta-Muse": "https://ai.meta.com/blog/introducing-muse-image-muse-video-msl/",
    "PhysicsIQ": "https://physics-iq.github.io/",
    "ABot-2026": "https://arxiv.org/abs/2603.23376",
    "T2V-text-2025": "https://arxiv.org/abs/2505.04946",
    "Vendor-AI-product": "https://invideo.io/faq/what-happens-to-ai-generated-product-videos-when-you/",
    "Batching": "https://firsttakeguide.com/",
    "virality": "docs/research/short-form-virality.md",
    "discovery": "docs/research/discovery-seo.md",
    "RULES-D47": "RULES.md D47 (scale rotation); vsp/gates.py g2_d47_shot_scale",
    "gate-D48": "vsp/gates.py g2_d48_internal_cuts (MOVE_KW)",
    "vocab-human-only": "vsp/creative_vocab.py HOOK_ARCHETYPES confession human_only"
  }
}
```

### 5.1 SHOT_LIBRARY

58 shot types. Conventions:
- `visual_types: []` means the shot must never be frame 0.
- For no-product concepts, `needs: product` is met by the concept's subject object (the snack drawer, the planner).
- Placeholders such as `{product}`, `{persona}`, `{setting}`, `{light}`, `{line}` and `{result}` are filled by `make_shotlist`.
- `SHOT_RULES.ai.prompt_suffix` is appended to every `ai_prompt`.
- Fragments marked "Not generated" or "Edit-only" are never sent to a model.

```json
{
  "SHOT_LIBRARY": [
    {"id": "hook-hands-mid-action", "name": "Frame-0 hands mid-action", "scale": "CU", "angle": "high", "move": "push-in", "duration_s": [0.5, 1.5], "purposes": ["hook", "demo"], "best_beats": ["VISUAL TRIGGER", "DEMO BEAT"], "visual_types": ["product-in-action"], "vibes": ["raw-ugc", "hype-energy", "clean-aesthetic"], "needs": ["hands", "product"], "ai_risk": "high", "ai_fallback": "product-operating-cu", "human_instructions": "Start using the product before you hit record and trim so frame 0 is already mid-motion, hands and product filling the lower two-thirds.", "ai_prompt": "Close-up, slightly high angle, subtle push-in: hands already mid-motion using {product} on {setting}, {light}.", "evidence": ["TT-CreativeCodes", "virality §1", "Touch-2022", "ABot-2026"]},
    {"id": "result-first-reveal", "name": "Result shown first", "scale": "CU", "angle": "eye-level", "move": "push-in", "duration_s": [0.5, 2.0], "purposes": ["hook", "payoff"], "best_beats": ["VISUAL TRIGGER", "PAYOFF"], "visual_types": ["result-reveal"], "vibes": ["before-after-reveal", "clean-aesthetic", "cinematic-premium", "raw-ugc"], "needs": ["product", "props"], "ai_risk": "med", "ai_fallback": "hero-static-push-in", "human_instructions": "Film the finished result first (the foam, the clean seat, the styled hair) in a steady close-up with the product at the edge of frame.", "ai_prompt": "Close-up, eye level, slow push-in on {result} with {product} at the frame edge, {light}.", "evidence": ["virality §1", "Usage-video-2022", "ABCD"]},
    {"id": "problem-state-open", "name": "Problem at its worst", "scale": "MS", "angle": "high", "move": "handheld", "duration_s": [0.5, 2.0], "purposes": ["hook", "context"], "best_beats": ["VISUAL TRIGGER", "STORY BEAT", "EDUCATION BEAT"], "visual_types": ["problem-state"], "vibes": ["raw-ugc", "playful-comedic", "before-after-reveal", "story-vlog"], "needs": ["location", "props"], "ai_risk": "low", "ai_fallback": "insert-object-detail", "human_instructions": "Hold the phone at chest height over the real mess or failure and drift in slightly as you start recording; do not tidy first.", "ai_prompt": "Medium shot, high angle, handheld phone look: {problem} at its worst in {setting}, {light}.", "evidence": ["virality §1", "TT-AdsHelp"]},
    {"id": "split-before-after", "name": "Split-screen before/after", "scale": "MS", "angle": "split", "move": "static", "duration_s": [1.5, 3.0], "purposes": ["hook", "proof", "payoff"], "best_beats": ["VISUAL TRIGGER", "EVIDENCE BEAT", "PAYOFF"], "visual_types": ["before-after-split"], "vibes": ["before-after-reveal", "expert-trust"], "needs": ["product", "location"], "ai_risk": "high", "ai_fallback": "text-card-over-motion", "human_instructions": "In the edit, put the matched BEFORE (left) and AFTER (right) clips side by side, both shot from the same taped phone spot, lens and light.", "ai_prompt": "Not generated: split-screen built in the edit from two real matched clips.", "evidence": ["ASDS", "virality §3", "virality §6"]},
    {"id": "pov-hands-first-use", "name": "POV hands using the product", "scale": "CU", "angle": "pov", "move": "handheld", "duration_s": [1.0, 3.0], "purposes": ["hook", "demo"], "best_beats": ["VISUAL TRIGGER", "DEMO BEAT", "RITUAL BEAT"], "visual_types": ["pov-hands"], "vibes": ["raw-ugc", "story-vlog", "asmr-satisfying"], "needs": ["hands", "product"], "ai_risk": "high", "ai_fallback": "product-operating-cu", "human_instructions": "Hold the phone at your eye line pointing down at your hands and use the product as a first-timer would, both hands in frame.", "ai_prompt": "First-person POV close-up, handheld: two hands use {product} with one simple motion, {setting}, {light}.", "evidence": ["Meta-creators", "SecondPerson-2023", "Touch-2022", "ABot-2026"]},
    {"id": "face-reaction-product", "name": "Reaction with product in frame", "scale": "MCU", "angle": "eye-level", "move": "handheld", "duration_s": [0.8, 2.0], "purposes": ["hook", "reaction", "emotion"], "best_beats": ["VISUAL TRIGGER", "DEMO BEAT", "PAYOFF"], "visual_types": ["face-reaction"], "vibes": ["playful-comedic", "raw-ugc", "hype-energy"], "needs": ["face", "product"], "ai_risk": "med", "ai_fallback": "reaction-cutaway-3q", "human_instructions": "Frame chest-up with the product or result in the lower third and film a genuine first reaction without speaking.", "ai_prompt": "Medium close-up, eye level, handheld: {persona} reacts with raised eyebrows to {product} held in the lower third, no speech, {light}.", "evidence": ["virality §7", "Emplifi-2026", "Hilton-2026"]},
    {"id": "text-card-over-motion", "name": "Text-first card over moving B-roll", "scale": "CU", "angle": "eye-level", "move": "push-in", "duration_s": [0.8, 2.0], "purposes": ["hook", "context", "transition"], "best_beats": ["VISUAL TRIGGER", "EDUCATION BEAT", "TEACHING BEAT", "CTA"], "visual_types": ["text-first"], "vibes": ["hype-energy", "expert-trust", "clean-aesthetic", "playful-comedic"], "needs": ["product"], "ai_risk": "low", "ai_fallback": "hero-static-push-in", "human_instructions": "Film 3 s of slow push-in on the product (or the concept's subject) and add the 3-word card in the edit, inside the safe zone.", "ai_prompt": "Close-up, slow push-in on {product} on {setting}, {light}, clean negative space in the upper-middle frame for a card added later.", "evidence": ["TT-CreativeCodes", "Emplifi-2026", "VidMob-2025", "virality §2"]},
    {"id": "unboxing-mid-open", "name": "Unboxing mid-open", "scale": "CU", "angle": "overhead", "move": "handheld", "duration_s": [1.0, 3.0], "purposes": ["hook", "demo"], "best_beats": ["VISUAL TRIGGER", "DEMO BEAT", "STORY BEAT"], "visual_types": ["unboxing"], "vibes": ["raw-ugc", "asmr-satisfying", "hype-energy"], "needs": ["hands", "product", "props"], "ai_risk": "high", "ai_fallback": "flat-lay-reveal", "human_instructions": "Shoot top-down with the box already half-open when you hit record, and keep the real tape and flap sounds.", "ai_prompt": "Overhead close-up: a box lid lifts to reveal {product} inside, hands only at the frame edge, {light}.", "evidence": ["Influee-2026", "virality §1", "Runway-Gen-4.5"]},
    {"id": "comparison-side-by-side", "name": "Side-by-side with the alternative", "scale": "MS", "angle": "eye-level", "move": "pan", "duration_s": [1.5, 3.5], "purposes": ["proof", "hook"], "best_beats": ["VISUAL TRIGGER", "EVIDENCE BEAT", "REJECTION HISTORY"], "visual_types": ["comparison"], "vibes": ["expert-trust", "raw-ugc", "playful-comedic"], "needs": ["product", "props"], "ai_risk": "med", "ai_fallback": "text-card-over-motion", "human_instructions": "Put the product and the old alternative (brand taped over) on one surface under one light and pan slowly from the alternative to the product.", "ai_prompt": "Medium shot, eye level, slow pan left to right from an unbranded {alt} to {product} on {setting}, {light}.", "evidence": ["TT-TopAds-spotlight", "virality §3"]},
    {"id": "day-counter-selfie", "name": "Day-N selfie check-in", "scale": "MCU", "angle": "eye-level", "move": "handheld", "duration_s": [1.0, 2.5], "purposes": ["hook", "context"], "best_beats": ["VISUAL TRIGGER", "VERBAL HOOK + LOCK", "STORY BEAT", "RITUAL BEAT", "PAYOFF"], "visual_types": ["day-counter"], "vibes": ["story-vlog", "raw-ugc"], "needs": ["face", "location"], "ai_risk": "med", "ai_fallback": "insert-object-detail", "human_instructions": "Film a front-camera check-in at the same spot and time each day, arm's length, eyes in the upper third; the Day N marker goes on in the edit.", "ai_prompt": "Selfie-style medium close-up, handheld front camera: {persona} in {setting}, {light}, glancing at the lens.", "evidence": ["Meta-creators", "Google-best-practices"]},
    {"id": "macro-texture-ecu", "name": "Macro texture / sound moment", "scale": "ECU", "angle": "eye-level", "move": "push-in", "duration_s": [1.0, 3.0], "purposes": ["hook", "b-roll", "proof"], "best_beats": ["VISUAL TRIGGER", "EDUCATION BEAT", "RITUAL BEAT"], "visual_types": ["satisfying-macro"], "vibes": ["asmr-satisfying", "cinematic-premium", "clean-aesthetic"], "needs": ["product"], "ai_risk": "low", "ai_fallback": "hero-static-push-in", "human_instructions": "Switch to macro (or 2x from about 10 cm), lock focus and exposure on the texture, and record the real sound up close.", "ai_prompt": "Extreme close-up, macro lens, very slow push-in across the texture of {material}, shallow depth of field, {light}; sound design: {sound}.", "evidence": ["LOreal-2026", "Tactile-2024", "Apple-AEAF"]},
    {"id": "label-detail-ecu", "name": "Label / spec detail", "scale": "ECU", "angle": "three-quarter", "move": "tilt", "duration_s": [1.0, 2.0], "purposes": ["proof", "b-roll"], "best_beats": ["EDUCATION BEAT", "EVIDENCE BEAT"], "visual_types": [], "vibes": ["expert-trust", "clean-aesthetic"], "needs": ["product"], "ai_risk": "high", "ai_fallback": "macro-texture-ecu", "human_instructions": "Tilt slowly down the real label or spec plate, holding each readable line for a full second.", "ai_prompt": "Image-to-video from the real label photo only: slow tilt down, no other motion, letters unchanged.", "evidence": ["T2V-text-2025", "Vendor-AI-product", "Google-best-practices"]},
    {"id": "talking-head-mcu", "name": "Talking head, direct to camera", "scale": "MCU", "angle": "eye-level", "move": "static", "duration_s": [1.5, 3.5], "purposes": ["context", "emotion"], "best_beats": ["VERBAL HOOK + LOCK", "TEACHING BEAT", "STORY BEAT", "REJECTION HISTORY", "COMMENT BAIT"], "visual_types": [], "vibes": ["raw-ugc", "expert-trust", "story-vlog", "cozy-calm"], "needs": ["face"], "ai_risk": "med", "ai_fallback": "vo-over-hands-broll", "human_instructions": "Prop the phone at eye height about an arm's length away, face the window, lock exposure on your face and say the line to the lens.", "ai_prompt": "Medium close-up, eye level, static: {persona} speaks to the lens in {setting}, {light}. {name} says: {line}", "evidence": ["Ling-2021", "Dost-Huang-2026", "Google-best-practices"]},
    {"id": "talking-head-product-in-hand", "name": "To camera, product in hand", "scale": "MCU", "angle": "eye-level", "move": "push-in", "duration_s": [1.5, 3.5], "purposes": ["proof", "payoff", "cta"], "best_beats": ["VERBAL HOOK + LOCK", "PAYOFF", "EDUCATION BEAT", "CTA"], "visual_types": ["face-reaction"], "vibes": ["raw-ugc", "expert-trust", "hype-energy"], "needs": ["face", "hands", "product"], "ai_risk": "high", "ai_fallback": "talking-head-mcu", "human_instructions": "Hold the product beside your face at chin height, front toward the lens, and deliver the line with the phone on a stand.", "ai_prompt": "Medium close-up, eye level, slow push-in: {persona} holds {product} at chin height, front toward camera. {name} says: {line}", "evidence": ["ABCD", "TT-Shop-2026", "TT-Symphony-avatar", "ABot-2026"]},
    {"id": "selfie-walk-talk", "name": "Selfie walk-and-talk", "scale": "MCU", "angle": "eye-level", "move": "tracking", "duration_s": [2.0, 5.0], "purposes": ["context", "emotion"], "best_beats": ["STORY BEAT", "VERBAL HOOK + LOCK", "TEACHING BEAT"], "visual_types": ["day-counter"], "vibes": ["story-vlog", "raw-ugc"], "needs": ["face", "location"], "ai_risk": "med", "ai_fallback": "talking-head-mcu", "human_instructions": "Walk slowly with the front camera at arm's length just above eye level, stabilisation on, talking in the present tense.", "ai_prompt": "Selfie-style tracking shot, medium close-up: {persona} walks slowly through {setting} talking to the lens, {light}. {name} says: {line}", "evidence": ["Meta-creators", "TT-Shop-2026"]},
    {"id": "mws-cta-to-camera", "name": "Medium-wide CTA to camera", "scale": "MWS", "angle": "eye-level", "move": "push-in", "duration_s": [1.5, 3.0], "purposes": ["cta"], "best_beats": ["COMMENT BAIT", "CTA"], "visual_types": [], "vibes": ["raw-ugc", "expert-trust", "hype-energy", "clean-aesthetic", "story-vlog"], "needs": ["face", "product", "location"], "ai_risk": "med", "ai_fallback": "end-card-hero", "human_instructions": "Step back so your hips and the product on the counter are in frame and push the phone in slightly while you say the comment prompt.", "ai_prompt": "Medium-wide, eye level, slow push-in: {persona} beside {product} on {setting} speaks to camera, {light}. {name} says: {line}", "evidence": ["ABCD", "RULES-D47"]},
    {"id": "reaction-cutaway-3q", "name": "Reaction cutaway, three-quarter", "scale": "MCU", "angle": "three-quarter", "move": "static", "duration_s": [0.8, 2.0], "purposes": ["reaction", "emotion"], "best_beats": ["DEMO BEAT", "EVIDENCE BEAT", "STORY BEAT", "PAYOFF"], "visual_types": ["face-reaction"], "vibes": ["playful-comedic", "raw-ugc", "story-vlog", "expert-trust"], "needs": ["face"], "ai_risk": "low", "ai_fallback": "insert-object-detail", "human_instructions": "Move the phone 45 degrees off your eye line and film a silent nod or look at the result as it happens.", "ai_prompt": "Medium close-up, three-quarter angle, static: {persona} looks down at {subject} and nods slightly, eyes off-lens, no speech, {light}.", "evidence": ["virality §7", "Emplifi-2026"]},
    {"id": "profile-look-cutaway", "name": "Profile look at product or result", "scale": "MCU", "angle": "profile", "move": "static", "duration_s": [0.8, 2.0], "purposes": ["reaction", "transition"], "best_beats": ["EDUCATION BEAT", "STORY BEAT", "RITUAL BEAT"], "visual_types": [], "vibes": ["cozy-calm", "cinematic-premium", "story-vlog"], "needs": ["face", "product"], "ai_risk": "low", "ai_fallback": "insert-object-detail", "human_instructions": "Film side-on at face height while you look at the product, with the window lighting the far side of your face.", "ai_prompt": "Medium close-up, profile, static: {persona} studies {product} in {setting}, soft side light.", "evidence": ["Google-prompt-guide"]},
    {"id": "jump-cut-punch-in", "name": "Jump-cut punch-in", "scale": "CU", "angle": "eye-level", "move": "push-in", "duration_s": [1.0, 2.5], "purposes": ["emotion", "transition"], "best_beats": ["VERBAL HOOK + LOCK", "TEACHING BEAT", "STORY BEAT", "REJECTION HISTORY", "PAYOFF"], "visual_types": [], "vibes": ["hype-energy", "playful-comedic", "raw-ugc", "expert-trust"], "needs": ["face"], "ai_risk": "low", "ai_fallback": "talking-head-mcu", "human_instructions": "Record the talking head in 4K and punch in 1.3-1.5x in the edit on the key word; nothing extra to film.", "ai_prompt": "Edit-only: crop the previous talking-head clip 1.3x on the emphasised word; no new generation.", "evidence": ["Dost-Huang-2026"]},
    {"id": "confession-handheld-cu", "name": "Candid handheld confession", "scale": "CU", "angle": "eye-level", "move": "handheld", "duration_s": [2.0, 4.0], "purposes": ["emotion"], "best_beats": ["IMPERFECTION BEAT", "STORY BEAT", "REJECTION HISTORY"], "visual_types": [], "vibes": ["raw-ugc", "story-vlog"], "needs": ["face"], "ai_risk": "high", "ai_fallback": "vo-over-hands-broll", "human_instructions": "Hold the phone yourself, a little closer than your talking-head framing, and say the flaw in one unrehearsed take.", "ai_prompt": "Not generated: confession is human-only and an AI presenter cannot claim experience.", "evidence": ["vocab-human-only", "virality §6"]},
    {"id": "over-shoulder-demo", "name": "Over-shoulder demo", "scale": "MS", "angle": "over-shoulder", "move": "handheld", "duration_s": [1.5, 4.0], "purposes": ["demo"], "best_beats": ["DEMO BEAT", "TEACHING BEAT", "RITUAL BEAT"], "visual_types": ["product-in-action", "pov-hands"], "vibes": ["raw-ugc", "expert-trust", "story-vlog"], "needs": ["hands", "product", "location"], "ai_risk": "high", "ai_fallback": "product-operating-cu", "human_instructions": "Have a helper, or a tall stand behind you, film over your shoulder while you do the real task start to finish.", "ai_prompt": "Over-the-shoulder medium shot, handheld: hands use {product} with one simple motion on {setting}, {light}.", "evidence": ["TT-Shop-2026", "ABot-2026"]},
    {"id": "overhead-hands-demo", "name": "Top-down hands demo", "scale": "MS", "angle": "overhead", "move": "static", "duration_s": [1.5, 3.5], "purposes": ["demo", "context"], "best_beats": ["DEMO BEAT", "TEACHING BEAT", "RITUAL BEAT", "EDUCATION BEAT"], "visual_types": ["pov-hands", "product-in-action"], "vibes": ["clean-aesthetic", "asmr-satisfying", "expert-trust"], "needs": ["hands", "product", "props"], "ai_risk": "high", "ai_fallback": "flat-lay-reveal", "human_instructions": "Mount the phone flat above the table, have your hands enter from the bottom of frame, and film one step per clip.", "ai_prompt": "Overhead medium shot, static: hands enter from the bottom and perform one step with {product} on {setting}, {light}.", "evidence": ["Influee-2026", "ABot-2026"]},
    {"id": "product-operating-cu", "name": "Product doing its job, hands out", "scale": "CU", "angle": "high", "move": "push-in", "duration_s": [1.0, 3.0], "purposes": ["demo", "proof"], "best_beats": ["DEMO BEAT", "EVIDENCE BEAT", "VISUAL TRIGGER"], "visual_types": ["product-in-action", "satisfying-macro"], "vibes": ["asmr-satisfying", "cinematic-premium", "hype-energy", "clean-aesthetic"], "needs": ["product", "props"], "ai_risk": "med", "ai_fallback": "hero-static-push-in", "human_instructions": "Frame only the working end (whisk in milk, brush on the seat) with hands cropped out and push in slowly as the effect builds.", "ai_prompt": "Close-up, slightly high angle, slow push-in: the working end of {product} {action} in {medium}, hands out of frame, {light}.", "evidence": ["PhysicsIQ", "Google-best-practices"]},
    {"id": "step-insert-cu", "name": "Feature or step insert (press, twist, click)", "scale": "CU", "angle": "high", "move": "static", "duration_s": [0.8, 2.0], "purposes": ["demo", "proof"], "best_beats": ["DEMO BEAT", "TEACHING BEAT", "EDUCATION BEAT"], "visual_types": ["product-in-action"], "vibes": ["expert-trust", "clean-aesthetic", "raw-ugc"], "needs": ["hands", "product"], "ai_risk": "high", "ai_fallback": "feature-callout-hero", "human_instructions": "Film the single finger action in a tight close-up with its sound, one attempt per clip.", "ai_prompt": "Not generated: finger-level manipulation of small parts; use the fallback.", "evidence": ["ABot-2026", "Runway-Gen-4.5"]},
    {"id": "feature-callout-hero", "name": "Feature call-out on a hero shot", "scale": "CU", "angle": "three-quarter", "move": "push-in", "duration_s": [1.0, 2.5], "purposes": ["demo", "proof"], "best_beats": ["EDUCATION BEAT", "TEACHING BEAT", "EVIDENCE BEAT"], "visual_types": [], "vibes": ["expert-trust", "clean-aesthetic"], "needs": ["product"], "ai_risk": "low", "ai_fallback": "hero-static-push-in", "human_instructions": "Film a slow push toward the feature and add the circle or arrow in the edit.", "ai_prompt": "Image-to-video from the real product photo: slow push-in toward the {feature}, no other motion.", "evidence": ["Google-best-practices"]},
    {"id": "timelapse-process", "name": "Time-lapse of a slow process", "scale": "MS", "angle": "high", "move": "static", "duration_s": [1.0, 3.0], "purposes": ["proof", "transition"], "best_beats": ["EVIDENCE BEAT", "RITUAL BEAT", "STORY BEAT", "PAYOFF"], "visual_types": ["result-reveal"], "vibes": ["asmr-satisfying", "story-vlog", "before-after-reveal"], "needs": ["location", "product"], "ai_risk": "med", "ai_fallback": "text-card-over-motion", "human_instructions": "Lock the phone on a stand in Time-lapse mode for the whole slow process and do not touch the frame until it ends.", "ai_prompt": "Time-lapse, static camera, high angle: {process} unfolds over the shot in {setting}, {light}.", "evidence": ["Stuppy-2025", "Google-prompt-guide"]},
    {"id": "slowmo-hero-moment", "name": "Slow-motion hero moment", "scale": "CU", "angle": "eye-level", "move": "speed-ramp", "duration_s": [1.0, 2.5], "purposes": ["payoff", "b-roll", "hook"], "best_beats": ["VISUAL TRIGGER", "PAYOFF", "RITUAL BEAT", "DEMO BEAT"], "visual_types": ["satisfying-macro", "product-in-action"], "vibes": ["cinematic-premium", "asmr-satisfying", "clean-aesthetic", "hype-energy"], "needs": ["product", "props"], "ai_risk": "med", "ai_fallback": "macro-texture-ecu", "human_instructions": "Shoot the fast moment (pour, splash, spritz, fabric drop) in Slo-mo at 120 fps or more on a stand, then ramp into slow motion in the edit.", "ai_prompt": "Close-up, eye level, slow motion: {fast_action} with {product}, droplets and motion detail visible, {light}.", "evidence": ["Stuppy-2024", "Stuppy-2025", "Meta-Muse"]},
    {"id": "pour-dispense-cu", "name": "Pour, pump or dispense close-up", "scale": "CU", "angle": "high", "move": "static", "duration_s": [1.0, 2.5], "purposes": ["demo", "b-roll"], "best_beats": ["DEMO BEAT", "RITUAL BEAT", "EDUCATION BEAT"], "visual_types": ["product-in-action", "satisfying-macro"], "vibes": ["asmr-satisfying", "cozy-calm", "clean-aesthetic"], "needs": ["hands", "product", "props"], "ai_risk": "med", "ai_fallback": "product-operating-cu", "human_instructions": "Frame the receiving cup or palm and pour or pump once, slowly, with the sound close to the mic.", "ai_prompt": "Close-up, high angle, static: {liquid} pours slowly from {product} into {vessel}, {light}.", "evidence": ["PhysicsIQ", "Influee-2026"]},
    {"id": "hand-enters-pickup", "name": "Hand enters and picks up", "scale": "CU", "angle": "eye-level", "move": "static", "duration_s": [1.0, 2.0], "purposes": ["hook", "transition"], "best_beats": ["VISUAL TRIGGER", "CTA", "PAYOFF"], "visual_types": ["product-in-action"], "vibes": ["raw-ugc", "clean-aesthetic", "hype-energy"], "needs": ["hands", "product"], "ai_risk": "med", "ai_fallback": "hero-static-push-in", "human_instructions": "Start on the product alone and let your hand enter within half a second to grab it, so the opening already moves.", "ai_prompt": "Close-up, eye level, static: a hand enters from the frame bottom and lifts {product} (large, easy grip) off {setting}, {light}.", "evidence": ["virality §1", "Touch-2022"]},
    {"id": "turn-in-hand-light", "name": "Turn in hand under window light", "scale": "CU", "angle": "eye-level", "move": "static", "duration_s": [1.5, 3.0], "purposes": ["proof", "b-roll"], "best_beats": ["EDUCATION BEAT", "EVIDENCE BEAT", "PAYOFF"], "visual_types": ["product-in-action"], "vibes": ["clean-aesthetic", "cinematic-premium", "expert-trust"], "needs": ["hands", "product"], "ai_risk": "high", "ai_fallback": "hero-static-push-in", "human_instructions": "Face the window and rotate the product slowly in your hand so the light travels across front, side and back.", "ai_prompt": "Not generated: in-hand rotation makes the model invent unseen sides; use the fallback.", "evidence": ["Influee-2026", "TT-Shop-2026", "Vendor-AI-product"]},
    {"id": "product-hero-orbit", "name": "Orbit around the product", "scale": "CU", "angle": "three-quarter", "move": "orbit", "duration_s": [1.5, 3.5], "purposes": ["payoff", "b-roll"], "best_beats": ["PAYOFF", "EDUCATION BEAT", "CTA"], "visual_types": [], "vibes": ["cinematic-premium", "clean-aesthetic"], "needs": ["product", "props"], "ai_risk": "med", "ai_fallback": "hero-static-push-in", "human_instructions": "Put the product on a lazy Susan, or walk the phone in a slow half-circle around it at product height.", "ai_prompt": "Close-up, three-quarter angle, slow tracking arc around {product} on {setting}, {light}.", "evidence": ["Google-prompt-guide", "Vendor-AI-product"]},
    {"id": "hero-static-push-in", "name": "Product hero, slow push-in", "scale": "CU", "angle": "three-quarter", "move": "push-in", "duration_s": [1.0, 3.0], "purposes": ["payoff", "cta", "b-roll"], "best_beats": ["PAYOFF", "CTA", "EDUCATION BEAT"], "visual_types": [], "vibes": ["clean-aesthetic", "cinematic-premium", "expert-trust", "cozy-calm"], "needs": ["product", "props"], "ai_risk": "low", "ai_fallback": "text-card-over-motion", "human_instructions": "Set the product on a clean surface with side window light and slide the phone slowly toward it along the table.", "ai_prompt": "Image-to-video from the real product photo: slow dolly in, no other motion.", "evidence": ["Google-best-practices", "TT-Symphony-avatar"]},
    {"id": "flat-lay-reveal", "name": "Flat lay: what is included", "scale": "MS", "angle": "overhead", "move": "push-in", "duration_s": [1.0, 2.5], "purposes": ["context", "b-roll"], "best_beats": ["EDUCATION BEAT", "DEMO BEAT", "CTA"], "visual_types": ["unboxing"], "vibes": ["clean-aesthetic", "asmr-satisfying", "expert-trust"], "needs": ["product", "props"], "ai_risk": "low", "ai_fallback": "hero-static-push-in", "human_instructions": "Lay out the product and everything in the box in a grid and record top-down while lowering the phone slightly.", "ai_prompt": "Image-to-video from the real flat-lay photo: slow overhead push-in, objects stay still.", "evidence": ["Influee-2026"]},
    {"id": "lifestyle-context-ws", "name": "Product in its real setting", "scale": "MWS", "angle": "eye-level", "move": "dolly", "duration_s": [1.0, 2.5], "purposes": ["context", "b-roll"], "best_beats": ["EDUCATION BEAT", "STORY BEAT", "RITUAL BEAT", "CTA"], "visual_types": [], "vibes": ["cozy-calm", "clean-aesthetic", "story-vlog"], "needs": ["location", "product"], "ai_risk": "low", "ai_fallback": "establishing-ws", "human_instructions": "Show where the product actually lives (counter, nightstand, car door) with a slow sideways slide of the phone.", "ai_prompt": "Medium-wide, eye level, slow dolly right: {product} in place in {setting}, {light}.", "evidence": ["TT-CQS", "ABCD"]},
    {"id": "establishing-ws", "name": "Establishing wide", "scale": "WS", "angle": "eye-level", "move": "pan", "duration_s": [0.8, 2.0], "purposes": ["context", "transition"], "best_beats": ["STORY BEAT", "RITUAL BEAT"], "visual_types": ["day-counter"], "vibes": ["story-vlog", "cozy-calm", "cinematic-premium"], "needs": ["location"], "ai_risk": "low", "ai_fallback": "lifestyle-context-ws", "human_instructions": "From the doorway, pan slowly across the room or place to set the time and location (morning kitchen, gym, car).", "ai_prompt": "Wide establishing shot, eye level, slow pan across {setting} at {time_of_day}, {light}.", "evidence": ["Google-prompt-guide"]},
    {"id": "matched-before", "name": "Matched BEFORE", "scale": "MS", "angle": "eye-level", "move": "static", "duration_s": [1.5, 2.5], "purposes": ["proof", "context"], "best_beats": ["EVIDENCE BEAT", "VISUAL TRIGGER", "STORY BEAT"], "visual_types": ["problem-state"], "vibes": ["before-after-reveal", "expert-trust", "raw-ugc"], "needs": ["location", "props"], "ai_risk": "high", "ai_fallback": "text-card-over-motion", "human_instructions": "Tape the phone's spot, note the lens and time of day, turn off filters and beauty mode, and record the BEFORE with a clock or date in frame.", "ai_prompt": "Not generated: before/after evidence must be real footage.", "evidence": ["ASDS", "virality §3", "virality §6"]},
    {"id": "matched-after", "name": "Matched AFTER", "scale": "MS", "angle": "eye-level", "move": "static", "duration_s": [1.5, 3.0], "purposes": ["proof", "payoff"], "best_beats": ["EVIDENCE BEAT", "PAYOFF"], "visual_types": ["result-reveal"], "vibes": ["before-after-reveal", "expert-trust", "raw-ugc"], "needs": ["location", "props"], "ai_risk": "high", "ai_fallback": "hero-static-push-in", "human_instructions": "Return the phone to the taped spot with the same lens, light and time of day and record the AFTER with the date visible.", "ai_prompt": "Not generated: before/after evidence must be real footage.", "evidence": ["ASDS", "virality §3"]},
    {"id": "match-cut-transform", "name": "Match-cut transformation", "scale": "MCU", "angle": "eye-level", "move": "whip-pan", "duration_s": [0.5, 1.5], "purposes": ["transition", "payoff"], "best_beats": ["PAYOFF", "EVIDENCE BEAT", "VISUAL TRIGGER"], "visual_types": ["result-reveal"], "vibes": ["before-after-reveal", "hype-energy", "playful-comedic"], "needs": ["location", "product"], "ai_risk": "high", "ai_fallback": "text-card-over-motion", "human_instructions": "End the BEFORE clip on a fast swipe past the lens, start the AFTER clip with the same swipe from the same taped spot, and cut mid-motion.", "ai_prompt": "Edit-only: transition between two real matched clips.", "evidence": ["ASDS", "Google-prompt-guide"]},
    {"id": "timestamp-proof-insert", "name": "Timestamped proof insert", "scale": "CU", "angle": "high", "move": "static", "duration_s": [1.0, 2.5], "purposes": ["proof"], "best_beats": ["EVIDENCE BEAT", "PAYOFF"], "visual_types": ["result-reveal", "day-counter"], "vibes": ["expert-trust", "raw-ugc", "story-vlog"], "needs": ["screen", "props", "hands"], "ai_risk": "high", "ai_fallback": "text-card-over-motion", "human_instructions": "Film the real reading (timer, scale, battery percentage, phone clock) in one steady close-up held long enough to read.", "ai_prompt": "Not generated: readable numbers and evidence must be real footage.", "evidence": ["T2V-text-2025", "Runway-Gen-4.5", "virality §6"]},
    {"id": "screen-insert", "name": "Phone-screen insert", "scale": "CU", "angle": "pov", "move": "static", "duration_s": [1.0, 3.0], "purposes": ["proof", "cta"], "best_beats": ["EVIDENCE BEAT", "EDUCATION BEAT", "COMMENT BAIT"], "visual_types": ["text-first"], "vibes": ["expert-trust", "raw-ugc", "playful-comedic"], "needs": ["screen", "hands"], "ai_risk": "high", "ai_fallback": "text-card-over-motion", "human_instructions": "Screen-record, or film the screen straight-on with brightness up and notifications off; never a product-page screenshot for TikTok Shop.", "ai_prompt": "Not generated: UI text is unreliable; use a real screen recording.", "evidence": ["TT-Shop-2026", "T2V-text-2025"]},
    {"id": "stress-test-action", "name": "Stress or torture test", "scale": "MS", "angle": "low", "move": "handheld", "duration_s": [1.0, 3.0], "purposes": ["proof", "demo"], "best_beats": ["EVIDENCE BEAT", "DEMO BEAT", "VISUAL TRIGGER"], "visual_types": ["product-in-action", "problem-state"], "vibes": ["hype-energy", "playful-comedic", "raw-ugc"], "needs": ["hands", "product", "props"], "ai_risk": "high", "ai_fallback": "product-operating-cu", "human_instructions": "Do the real test once in one unbroken take (drop, spill, stretch) with a second phone catching a wider angle.", "ai_prompt": "Not generated: AI outcomes succeed too often and cannot prove durability.", "evidence": ["Runway-Gen-4.5", "PhysicsIQ", "virality §3"]},
    {"id": "rejection-lineup", "name": "Rejected alternatives line-up", "scale": "MS", "angle": "eye-level", "move": "pan", "duration_s": [1.5, 3.5], "purposes": ["context", "proof"], "best_beats": ["REJECTION HISTORY", "EVIDENCE BEAT"], "visual_types": ["comparison"], "vibes": ["raw-ugc", "playful-comedic", "expert-trust"], "needs": ["props", "product"], "ai_risk": "med", "ai_fallback": "text-card-over-motion", "human_instructions": "Line up the products you gave up on (brands turned away or taped over), the winner last, and pan along them.", "ai_prompt": "Medium shot, eye level, slow pan along a row of unbranded {category} items ending on {product}, {light}.", "evidence": ["virality §3"]},
    {"id": "toss-aside-cutaway", "name": "Toss-aside cutaway", "scale": "MS", "angle": "high", "move": "whip-pan", "duration_s": [0.5, 1.5], "purposes": ["transition", "emotion"], "best_beats": ["REJECTION HISTORY", "IMPERFECTION BEAT"], "visual_types": ["problem-state"], "vibes": ["playful-comedic", "raw-ugc", "hype-energy"], "needs": ["hands", "props"], "ai_risk": "high", "ai_fallback": "rejection-lineup", "human_instructions": "Drop the old item into a drawer or box and whip the phone toward the new product as it lands.", "ai_prompt": "Not generated: thrown-object physics; use the fallback.", "evidence": ["PhysicsIQ", "Meta-Muse"]},
    {"id": "count-off-teaching-ms", "name": "Counting points on fingers", "scale": "MS", "angle": "eye-level", "move": "push-in", "duration_s": [2.0, 3.5], "purposes": ["context"], "best_beats": ["TEACHING BEAT", "EDUCATION BEAT"], "visual_types": [], "vibes": ["expert-trust", "raw-ugc"], "needs": ["face", "hands"], "ai_risk": "high", "ai_fallback": "talking-head-mcu", "human_instructions": "Frame waist-up so your hand is in shot and count the point on your fingers as you say it.", "ai_prompt": "Not generated: finger counts render wrong; use talking-head-mcu with the number as an edit overlay.", "evidence": ["Vendor-AI-product", "ABot-2026"]},
    {"id": "prop-explainer-cu", "name": "Prop explainer", "scale": "CU", "angle": "eye-level", "move": "push-in", "duration_s": [1.5, 3.0], "purposes": ["context", "proof"], "best_beats": ["EDUCATION BEAT", "TEACHING BEAT", "EVIDENCE BEAT"], "visual_types": [], "vibes": ["expert-trust", "cozy-calm", "raw-ugc"], "needs": ["hands", "props"], "ai_risk": "med", "ai_fallback": "insert-object-detail", "human_instructions": "Hold the prop (ingredient, receipt, sketch) close to the lens and steady while you explain it.", "ai_prompt": "Close-up, eye level, slow push-in: a hand holds {prop} steady toward camera, {light}.", "evidence": ["TT-CQS"]},
    {"id": "insert-object-detail", "name": "Insert of what the line is about", "scale": "CU", "angle": "high", "move": "push-in", "duration_s": [1.0, 2.5], "purposes": ["b-roll", "context"], "best_beats": ["STORY BEAT", "EDUCATION BEAT", "TEACHING BEAT"], "visual_types": ["problem-state"], "vibes": ["story-vlog", "cozy-calm", "raw-ugc", "expert-trust"], "needs": ["props"], "ai_risk": "low", "ai_fallback": "establishing-ws", "human_instructions": "Film a tight close-up of the object the sentence mentions (snack drawer, notebook, alarm) while you say it.", "ai_prompt": "Close-up, slightly high angle, slow push-in on {object} in {setting}, {light}.", "evidence": ["Influee-2026"]},
    {"id": "green-screen-explainer", "name": "Green-screen explainer", "scale": "MCU", "angle": "eye-level", "move": "static", "duration_s": [2.0, 3.5], "purposes": ["context", "proof"], "best_beats": ["TEACHING BEAT", "EDUCATION BEAT", "EVIDENCE BEAT"], "visual_types": ["text-first"], "vibes": ["expert-trust", "playful-comedic"], "needs": ["face", "screen"], "ai_risk": "med", "ai_fallback": "talking-head-mcu", "human_instructions": "Use the app's green-screen effect with a real source (chart, article, product photo) behind you and point to it.", "ai_prompt": "Medium close-up, eye level, static: {persona} speaks to camera in front of a plain backdrop, a real image is composited later. {name} says: {line}", "evidence": ["TT-CreativeCodes", "TT-Shop-2026"]},
    {"id": "pov-walk-in", "name": "POV walk-in", "scale": "MWS", "angle": "pov", "move": "tracking", "duration_s": [1.0, 3.0], "purposes": ["context", "transition"], "best_beats": ["STORY BEAT", "RITUAL BEAT", "CTA"], "visual_types": ["day-counter"], "vibes": ["story-vlog", "raw-ugc", "cozy-calm"], "needs": ["location"], "ai_risk": "low", "ai_fallback": "establishing-ws", "human_instructions": "Walk into the room at chest height with the rear camera, stabilisation on, ending on the spot where the routine happens.", "ai_prompt": "First-person POV tracking shot walking into {setting} toward {spot}, {light}.", "evidence": ["SecondPerson-2023", "Meta-creators"]},
    {"id": "ritual-step-wide", "name": "Routine step, wide", "scale": "MWS", "angle": "three-quarter", "move": "dolly", "duration_s": [2.0, 4.0], "purposes": ["context", "demo"], "best_beats": ["RITUAL BEAT", "STORY BEAT"], "visual_types": [], "vibes": ["cozy-calm", "story-vlog", "clean-aesthetic"], "needs": ["face", "location", "props"], "ai_risk": "med", "ai_fallback": "lifestyle-context-ws", "human_instructions": "Place the phone at waist height at 45 degrees and slide it slowly while you do the routine step in real time.", "ai_prompt": "Medium-wide, three-quarter angle, slow dolly: {persona} does {step} in {setting}, {light}.", "evidence": ["TT-CQS"]},
    {"id": "mirror-selfie", "name": "Mirror selfie", "scale": "MS", "angle": "eye-level", "move": "handheld", "duration_s": [1.0, 3.0], "purposes": ["context", "demo"], "best_beats": ["RITUAL BEAT", "DEMO BEAT", "STORY BEAT"], "visual_types": ["day-counter"], "vibes": ["story-vlog", "raw-ugc"], "needs": ["face", "location"], "ai_risk": "high", "ai_fallback": "talking-head-mcu", "human_instructions": "Film in a clean mirror with the phone at chest height and the product or outfit centred.", "ai_prompt": "Not generated: mirror reflections and the phone in hand break consistency; use the fallback.", "evidence": ["Runway-Gen-4.5", "Vendor-AI-product"]},
    {"id": "low-angle-hero-payoff", "name": "Low-angle result held to lens", "scale": "MCU", "angle": "low", "move": "push-in", "duration_s": [1.5, 3.0], "purposes": ["payoff", "emotion"], "best_beats": ["PAYOFF"], "visual_types": ["result-reveal"], "vibes": ["hype-energy", "cinematic-premium", "raw-ugc"], "needs": ["face", "hands", "product"], "ai_risk": "high", "ai_fallback": "hero-static-push-in", "human_instructions": "Hold the phone slightly below chest height and bring the result toward the lens while your face stays in the upper third.", "ai_prompt": "Medium close-up, low angle, slow push-in: {persona} holds {result} toward camera, {light}.", "evidence": ["ABot-2026", "virality §1"]},
    {"id": "comment-typing-insert", "name": "Comment keyword typed", "scale": "CU", "angle": "pov", "move": "static", "duration_s": [1.5, 3.0], "purposes": ["cta"], "best_beats": ["COMMENT BAIT"], "visual_types": ["text-first"], "vibes": ["raw-ugc", "playful-comedic", "story-vlog"], "needs": ["screen", "hands"], "ai_risk": "high", "ai_fallback": "mws-cta-to-camera", "human_instructions": "Screen-record typing the keyword into the comment box on your own post, with other handles out of frame.", "ai_prompt": "Not generated: typed UI text is unreliable; screen-record it.", "evidence": ["discovery", "T2V-text-2025"]},
    {"id": "end-card-hero", "name": "End card on product hero", "scale": "CU", "angle": "eye-level", "move": "push-in", "duration_s": [1.0, 2.5], "purposes": ["cta"], "best_beats": ["CTA"], "visual_types": [], "vibes": ["clean-aesthetic", "expert-trust", "cinematic-premium", "cozy-calm"], "needs": ["product"], "ai_risk": "low", "ai_fallback": "text-card-over-motion", "human_instructions": "Reuse the hero push-in and add the CTA card in the edit, product centred above the bottom caption band.", "ai_prompt": "Image-to-video from the real product photo: slow push-in, clear space above the product for a card added later.", "evidence": ["TT-CreativeCodes", "virality §4"]},
    {"id": "loop-return-frame", "name": "Loop-back final frame", "scale": "CU", "angle": "high", "move": "pull-out", "duration_s": [0.5, 1.5], "purposes": ["transition", "cta"], "best_beats": ["CTA", "PAYOFF"], "visual_types": [], "vibes": ["hype-energy", "asmr-satisfying", "playful-comedic", "raw-ugc", "clean-aesthetic", "before-after-reveal"], "needs": ["product"], "ai_risk": "low", "ai_fallback": "hero-static-push-in", "human_instructions": "End on the same framing, position and motion as frame 0 so the jump back to the start is invisible.", "ai_prompt": "Use the frame-0 still as both first and last frame (loop); slow dolly out that settles on the opening composition.", "evidence": ["Emplifi-2026", "Omni-docs", "Luma-Ray3.14"]},
    {"id": "whip-pan-transition", "name": "Whip-pan transition", "scale": "MS", "angle": "eye-level", "move": "whip-pan", "duration_s": [0.3, 0.8], "purposes": ["transition"], "best_beats": ["STORY BEAT", "DEMO BEAT", "PAYOFF"], "visual_types": [], "vibes": ["hype-energy", "playful-comedic", "story-vlog"], "needs": ["location"], "ai_risk": "med", "ai_fallback": "insert-object-detail", "human_instructions": "Whip the phone sideways at the end of one clip and the same way at the start of the next, then cut mid-blur.", "ai_prompt": "Medium shot, fast whip pan to the right ending on {subject} in {setting}, motion blur, {light}.", "evidence": ["Google-prompt-guide", "Meta-creators"]},
    {"id": "speed-ramp-reveal", "name": "Speed-ramp into the reveal", "scale": "CU", "angle": "eye-level", "move": "speed-ramp", "duration_s": [0.8, 2.0], "purposes": ["transition", "payoff"], "best_beats": ["PAYOFF", "VISUAL TRIGGER", "DEMO BEAT"], "visual_types": ["result-reveal", "product-in-action"], "vibes": ["hype-energy", "cinematic-premium"], "needs": ["product"], "ai_risk": "med", "ai_fallback": "slowmo-hero-moment", "human_instructions": "Shoot the move toward the reveal at 60 fps or more and ramp from fast to slow on the frame where the result appears.", "ai_prompt": "Close-up, fast handheld push-in that slows sharply as {result} comes into view, {light}.", "evidence": ["Stuppy-2024", "TT-AdsHelp"]},
    {"id": "lens-cover-transition", "name": "Lens-cover wipe", "scale": "CU", "angle": "eye-level", "move": "handheld", "duration_s": [0.3, 1.0], "purposes": ["transition"], "best_beats": ["PAYOFF", "EVIDENCE BEAT", "STORY BEAT"], "visual_types": [], "vibes": ["playful-comedic", "hype-energy", "before-after-reveal"], "needs": ["hands"], "ai_risk": "med", "ai_fallback": "whip-pan-transition", "human_instructions": "Cover the lens with your palm at the end of one clip and uncover it at the start of the next, cutting on the dark frame.", "ai_prompt": "Close-up, a palm moves toward the lens until the frame goes dark, {light}.", "evidence": ["Meta-creators"]},
    {"id": "vo-over-hands-broll", "name": "Voice-over on hands B-roll", "scale": "CU", "angle": "high", "move": "handheld", "duration_s": [1.0, 3.0], "purposes": ["b-roll", "demo"], "best_beats": ["EDUCATION BEAT", "TEACHING BEAT", "STORY BEAT", "IMPERFECTION BEAT"], "visual_types": [], "vibes": ["raw-ugc", "asmr-satisfying", "cozy-calm", "expert-trust"], "needs": ["hands", "product"], "ai_risk": "med", "ai_fallback": "product-operating-cu", "human_instructions": "Film your hands handling the product loosely for about 10 s per clip; the talking-head audio runs on top.", "ai_prompt": "Close-up, high angle, handheld: relaxed hands rest on and gently touch {product} on {setting}, no speech, {light}.", "evidence": ["Influee-2026", "Emplifi-2026"]}
  ]
}
```

### 5.2 SHOT_RULES

Two kinds of numbers appear below. Cadence bands are anchored on Dost & Huang 2026 (p16–p84 = 1.9–5.2 cuts/10 s, max 8.2) and Xiao 2024 (inverted U); the per-vibe split is our inference [A]. Hard constraints each cite a source. Cuts are counted as shot boundaries, punch-in jump cuts included.

```json
{
  "SHOT_RULES": {
    "cadence": {
      "raw-ugc":             {"avg_shot_s": [2.0, 3.5], "cuts_per_10s": [2.9, 5.0], "max_static_s": 3.5},
      "clean-aesthetic":     {"avg_shot_s": [2.0, 3.5], "cuts_per_10s": [2.9, 5.0], "max_static_s": 3.0},
      "hype-energy":         {"avg_shot_s": [1.25, 2.0], "cuts_per_10s": [5.0, 8.0], "max_static_s": 2.0},
      "cozy-calm":           {"avg_shot_s": [3.0, 5.0], "cuts_per_10s": [2.0, 3.3], "max_static_s": 3.5},
      "expert-trust":        {"avg_shot_s": [2.5, 4.0], "cuts_per_10s": [2.5, 4.0], "max_static_s": 3.5},
      "playful-comedic":     {"avg_shot_s": [1.25, 2.5], "cuts_per_10s": [4.0, 8.0], "max_static_s": 2.5},
      "cinematic-premium":   {"avg_shot_s": [2.0, 4.0], "cuts_per_10s": [2.5, 5.0], "max_static_s": 2.5},
      "asmr-satisfying":     {"avg_shot_s": [2.5, 5.0], "cuts_per_10s": [2.0, 4.0], "max_static_s": 3.5},
      "story-vlog":          {"avg_shot_s": [2.0, 3.5], "cuts_per_10s": [2.9, 5.0], "max_static_s": 3.0},
      "before-after-reveal": {"avg_shot_s": [1.5, 3.0], "cuts_per_10s": [3.3, 6.7], "max_static_s": 3.0}
    },
    "cadence_global": {
      "video_cuts_per_10s_hard": [1.9, 8.2],
      "opening_0_3s_cuts": [1, 2],
      "min_shot_length_stdev_s": 0.4,
      "sources": ["Dost-Huang-2026", "Xiao-2024", "TT-CreativeCodes", "Emplifi-2026"]
    },
    "hard": {
      "frame0": {
        "window_s": [0.0, 0.5],
        "product_concepts": "frame-0 shot needs 'product', or its visual_type is result-reveal or before-after-split",
        "no_product_concepts": "frame 0 shows the subject, problem or day counter",
        "banned_ids_at_frame0": ["talking-head-mcu", "jump-cut-punch-in", "mws-cta-to-camera", "confession-handheld-cu", "count-off-teaching-ms", "green-screen-explainer"],
        "overlay_max_words": 3,
        "alternate_openings_differ_in": "visual_type AND shot id",
        "sources": ["virality §1", "Hilton-2026", "ABCD", "virality §4"]
      },
      "human_presence": {
        "face_or_hands_by_s": 3.0,
        "min_on_screen_s": 1.0,
        "face_by_s_if_human_presenter": 3.0,
        "face_required_tiktok_shop": true,
        "face_only_share_0_5s_max": {"utilitarian": 0.5, "hedonic": 1.0, "neutral": 0.7},
        "sources": ["virality §1", "Emplifi-2026", "Hilton-2026", "TT-Shop-2026", "ABCD"]
      },
      "scale_rotation": {
        "max_consecutive_same_scale": 2,
        "max_consecutive_talking_head": 2,
        "min_distinct_scales_per_15s": 3,
        "sources": ["RULES-D47", "Ling-2021", "LOreal-2026"]
      },
      "loop_ending": {
        "required_if_duration_le_s": 15,
        "rule": "last shot is loop-return-frame (inherits frame 0's scale, angle and subject) or repeats frame 0's shot id; the last spoken line may run into the first",
        "bonus_if_duration_gt_s": 15,
        "sources": ["Emplifi-2026", "YT-Shorts-deck-2026", "Omni-docs"]
      },
      "safe_zone": {
        "see": "virality §2 (all-platform box x 120-888, y 288-1248 on 1080x1920)",
        "eyes_y_px": [560, 760],
        "product_hero_box_px": {"x": [240, 840], "y": [640, 1248]},
        "grade": "A (derived)"
      },
      "product_visibility_share_min": {
        "demo": 0.6, "review": 0.5, "transformation": 0.4, "pov-vlog": 0.4, "talking-head": 0.3,
        "no_product_concepts": 0.0,
        "sources": ["TT-CreativeCodes", "ABCD", "VidMob-2025"]
      },
      "demo_beat_min_angles": 2,
      "before_after": {
        "same_setup_id": true, "same_scale_and_angle": true, "min_hold_each_s": 1.5,
        "time_marker_required": true, "filters_and_beauty_mode": "off",
        "ai_generated_states_allowed": false,
        "sources": ["ASDS", "virality §3", "virality §6"]
      },
      "d48_compatibility": {
        "static_max_s": 3.5,
        "gate_move_keywords": ["push-in", "push in", "pan", "tilt", "dolly", "handheld", "tracking", "move"],
        "render_phrase_for_move_id": {"pull-out": "dolly out", "orbit": "tracking arc (orbit)", "speed-ramp": "handheld push-in, speed-ramped", "whip-pan": "whip pan", "static": "split into sub-shots of 3.5 s or less"},
        "sources": ["gate-D48"]
      },
      "tiktok_shop_lane": {
        "min_continuous_live_action_s": 3.0,
        "live_action_must_show": ["face", "product", "camera movement", "real-world setting"],
        "max_still_or_loop_segment_s": 1.0,
        "banned": ["product-page screenshots", "slideshows of stills", "AI voice"],
        "footage": "stabilised (tripod or in-hand stabiliser)",
        "on_screen_text": "in sync with speech",
        "sources": ["TT-Shop-2026", "virality §3"]
      }
    },
    "talking_head_ids": ["talking-head-mcu", "talking-head-product-in-hand", "selfie-walk-talk", "mws-cta-to-camera", "jump-cut-punch-in", "confession-handheld-cu", "count-off-teaching-ms", "green-screen-explainer", "day-counter-selfie"],
    "ai": {
      "models": {
        "gemini-omni-flash-1.1": {"clip_s": [3, 10], "extend_to_s": 40, "ratio_9_16": true, "refs": "images + up to 3 video refs of 3 s or less", "notes": "multi-shot by default; no negative-prompt param"},
        "veo-3.1":               {"clip_s": [4, 8], "allowed_s": [4, 6, 8], "extend_to_s": 148, "ratio_9_16": true, "refs": "up to 3 asset images (8 s only)", "notes": "first+last frame; audio always on; 24 fps"},
        "kling-3.0":             {"clip_s": [3, 15], "ratio_9_16": true, "refs": "reference video or multiple images", "notes": "storyboard per-shot size/angle/move"},
        "seedance-2.0":          {"clip_s": [4, 15], "ratio_9_16": true, "refs": "up to 9 images, 3 videos, 3 audio", "notes": "native 480p/720p"},
        "wan-3.0":               {"clip_s": [2, 30], "ratio_9_16": true, "refs": "multimodal", "notes": "hosted preview API"},
        "luma-ray3.14":          {"clip_s": [5, 10], "extend_to_s": 30, "ratio_9_16": "UNVERIFIED (Reframe on Ray 3.2)", "refs": "none on 3.14", "notes": "loop mode; no native audio"},
        "runway-gen-4.5":        {"clip_s": "5 or 10 (Gen-4; Gen-4.5 UNVERIFIED)", "ratio_9_16": "UNVERIFIED", "refs": "Gen-4 references", "notes": "Aleph 2.0 edits up to 30 s"},
        "sora-2":                {"retired": "2026-09-24"}
      },
      "one_shot_per_prompt": true,
      "generate_length_rule": "shortest allowed clip length at least shot duration + 1.0 s of handles; trim in the edit",
      "native_aspect": "9:16 (never crop 16:9)",
      "prompt_order": ["cinematography: scale, angle, one move", "subject: locked persona or product text", "one action in beats", "setting", "light + 3-5 palette anchors", "style: vertical phone footage", "audio: SFX/ambience; dialogue after a colon"],
      "prompt_suffix": "Single continuous shot, no scene cuts. One camera move only. No on-screen text, captions, logos or watermarks.",
      "quotes_in_prompts": false,
      "model_rendered_text": false,
      "dialogue_max_words_per_clip": {"4s": 10, "8s": 20},
      "inserts_without_persona": "shots whose needs lack 'face' must not include the persona description; add 'hands only, face out of frame' when hands appear",
      "persona_consistency": "same 1-3 reference stills in every shot + identical description text + same seed; never re-describe the face when a reference is loaded",
      "product_consistency": "real product photos (front, side, back, detail); image-to-video from the real packshot for hero, label and end-card shots; slow moves only over labels",
      "hands": "large-object grasps only, contact 2 s or less; no finger-level manipulation, counting, typing or writing",
      "physics": "no drops, throws, snap-fits, stacking or fast motion; slow pours and foam are med risk",
      "proof": "AI shots never serve as evidence: EVIDENCE BEAT, matched before/after, stress tests and timestamps use real footage, or become text cards",
      "presenter_ai_substitution": "replace ai_risk=high with ai_fallback (follow the chain to med or low); at most 2 consecutive med shots; low-risk shots at least 30% of runtime",
      "risk_rubric": {"factors": ["hand-object contact", "readable text or numbers", "rigid or fast physics", "multi-object continuity", "lip-synced speech over 2 lines", "proof claim"], "low": 0, "med": 1, "high": "2+ or any proof claim"},
      "loop": "pass the frame-0 still as first and last frame (Omni sources syntax, Veo first+last frame) or use Luma loop",
      "qa": "run a vision-model check on every clip for hands, labels, identity and extra cuts before assembly",
      "sources": ["Omni-docs", "Veo-docs", "Veo-guide", "Google-best-practices", "Google-prompt-guide", "Sora-guide", "Sora-shutdown", "Kling-3", "Seedance-2", "Wan-3", "Luma-Ray3.14", "Runway-Gen-4.5", "ABot-2026", "PhysicsIQ", "T2V-text-2025", "Meta-Muse", "virality §6"]
    }
  }
}
```

### 5.3 FORMAT_RECIPES

**How a beat's shots are chosen:**
1. Start from `default`.
2. Apply the `formats` entry for the chosen format.
3. Apply the `concepts` entry for the concept (`product` adds no changes).

**What each entry holds.** `shots` is the ordered sub-shot list for one beat window, trimmed from the end when the window is short. `alt` holds substitutes, used in order.

**Checks after assembly:**
- `SHOT_RULES.hard.scale_rotation` must hold. If it fails, rotate in the beat's first `alt` that fixes it.
- With `presenter=ai`, apply `ai_fallback`.

**Grade.** The recipes combine §2–§4 and are graded [A] as a set.

```json
{
  "FORMAT_RECIPES": {
    "resolution": ["default", "formats[format]", "concepts[concept]"],
    "assembly": [
      "1. concatenate each beat's shots in beat order; trim from the end of a beat's list when its window is shorter than the sum of min durations",
      "2. presenter=ai: replace ai_risk=high ids by following ai_fallback until med/low",
      "3. if a shot repeats the previous id, or breaks max_consecutive_same_scale / max_consecutive_talking_head, take the beat's first alt (ai_risk != high when presenter=ai) that fixes it",
      "4. presenter=ai and format=transformation: require brand-supplied real before/after footage, else route the script to demo",
      "5. apply SHOT_RULES.hard (frame0, human_presence, loop_ending, product share) and log any rule still failing"
    ],
    "default": {
      "VISUAL TRIGGER":     {"shots": ["hook-hands-mid-action"], "alt": ["result-first-reveal", "problem-state-open", "pov-hands-first-use", "macro-texture-ecu"]},
      "VERBAL HOOK + LOCK": {"shots": ["talking-head-mcu"], "alt": ["talking-head-product-in-hand", "jump-cut-punch-in", "selfie-walk-talk"]},
      "IMPERFECTION BEAT":  {"shots": ["vo-over-hands-broll", "confession-handheld-cu"], "alt": ["talking-head-mcu", "toss-aside-cutaway"]},
      "REJECTION HISTORY":  {"shots": ["rejection-lineup", "talking-head-mcu"], "alt": ["comparison-side-by-side", "toss-aside-cutaway", "jump-cut-punch-in"]},
      "EDUCATION BEAT":     {"shots": ["macro-texture-ecu", "vo-over-hands-broll", "reaction-cutaway-3q", "feature-callout-hero"], "alt": ["label-detail-ecu", "lifestyle-context-ws", "prop-explainer-cu", "text-card-over-motion"]},
      "TEACHING BEAT":      {"shots": ["insert-object-detail", "talking-head-mcu", "text-card-over-motion"], "alt": ["jump-cut-punch-in", "count-off-teaching-ms", "green-screen-explainer", "prop-explainer-cu"]},
      "STORY BEAT":         {"shots": ["insert-object-detail", "selfie-walk-talk", "reaction-cutaway-3q"], "alt": ["talking-head-mcu", "establishing-ws", "pov-walk-in", "whip-pan-transition"]},
      "DEMO BEAT":          {"shots": ["over-shoulder-demo", "product-operating-cu", "reaction-cutaway-3q"], "alt": ["pov-hands-first-use", "overhead-hands-demo", "pour-dispense-cu", "step-insert-cu", "flat-lay-reveal", "timelapse-process"]},
      "EVIDENCE BEAT":      {"shots": ["matched-before", "matched-after", "reaction-cutaway-3q"], "alt": ["split-before-after", "timestamp-proof-insert", "comparison-side-by-side", "stress-test-action"]},
      "RITUAL BEAT":        {"shots": ["pov-walk-in", "ritual-step-wide", "pour-dispense-cu"], "alt": ["macro-texture-ecu", "timelapse-process", "slowmo-hero-moment"]},
      "PAYOFF":             {"shots": ["talking-head-product-in-hand"], "alt": ["low-angle-hero-payoff", "result-first-reveal", "hero-static-push-in", "speed-ramp-reveal"]},
      "COMMENT BAIT":       {"shots": ["mws-cta-to-camera"], "alt": ["comment-typing-insert", "talking-head-mcu"]},
      "CTA":                {"shots": ["loop-return-frame"], "alt": ["end-card-hero", "hero-static-push-in", "text-card-over-motion"]}
    },
    "formats": {
      "demo": {
        "VISUAL TRIGGER":     {"shots": ["hook-hands-mid-action"], "alt": ["product-operating-cu", "result-first-reveal", "problem-state-open"]},
        "VERBAL HOOK + LOCK": {"shots": ["talking-head-product-in-hand"], "alt": ["talking-head-mcu", "jump-cut-punch-in"]},
        "EDUCATION BEAT":     {"shots": ["macro-texture-ecu", "feature-callout-hero", "vo-over-hands-broll", "reaction-cutaway-3q"], "alt": ["label-detail-ecu", "flat-lay-reveal", "lifestyle-context-ws"]},
        "DEMO BEAT":          {"shots": ["over-shoulder-demo", "product-operating-cu", "pov-hands-first-use", "reaction-cutaway-3q"], "alt": ["overhead-hands-demo", "pour-dispense-cu", "step-insert-cu", "slowmo-hero-moment", "flat-lay-reveal", "timelapse-process"]},
        "EVIDENCE BEAT":      {"shots": ["comparison-side-by-side", "timestamp-proof-insert"], "alt": ["matched-before", "matched-after", "stress-test-action"]},
        "PAYOFF":             {"shots": ["result-first-reveal", "talking-head-product-in-hand"], "alt": ["speed-ramp-reveal", "low-angle-hero-payoff", "hero-static-push-in"]},
        "COMMENT BAIT":       {"shots": ["mws-cta-to-camera"], "alt": ["comment-typing-insert"]},
        "CTA":                {"shots": ["loop-return-frame"], "alt": ["end-card-hero", "hand-enters-pickup"]}
      },
      "review": {
        "VISUAL TRIGGER":     {"shots": ["hook-hands-mid-action"], "alt": ["comparison-side-by-side", "face-reaction-product", "result-first-reveal"]},
        "VERBAL HOOK + LOCK": {"shots": ["talking-head-product-in-hand"], "alt": ["talking-head-mcu", "jump-cut-punch-in"]},
        "IMPERFECTION BEAT":  {"shots": ["vo-over-hands-broll", "confession-handheld-cu"], "alt": ["toss-aside-cutaway", "talking-head-mcu"]},
        "REJECTION HISTORY":  {"shots": ["rejection-lineup", "jump-cut-punch-in"], "alt": ["comparison-side-by-side", "toss-aside-cutaway"]},
        "EDUCATION BEAT":     {"shots": ["macro-texture-ecu", "turn-in-hand-light", "reaction-cutaway-3q"], "alt": ["label-detail-ecu", "feature-callout-hero", "vo-over-hands-broll"]},
        "DEMO BEAT":          {"shots": ["pov-hands-first-use", "product-operating-cu", "reaction-cutaway-3q"], "alt": ["over-shoulder-demo", "overhead-hands-demo", "pour-dispense-cu", "slowmo-hero-moment", "flat-lay-reveal"]},
        "EVIDENCE BEAT":      {"shots": ["matched-before", "matched-after", "timestamp-proof-insert"], "alt": ["comparison-side-by-side", "split-before-after", "stress-test-action"]},
        "PAYOFF":             {"shots": ["hero-static-push-in", "talking-head-product-in-hand"], "alt": ["low-angle-hero-payoff", "result-first-reveal"]},
        "COMMENT BAIT":       {"shots": ["mws-cta-to-camera"], "alt": ["comment-typing-insert"]},
        "CTA":                {"shots": ["end-card-hero"], "alt": ["loop-return-frame", "hand-enters-pickup"]}
      },
      "transformation": {
        "VISUAL TRIGGER":     {"shots": ["split-before-after"], "alt": ["result-first-reveal", "problem-state-open", "match-cut-transform"]},
        "VERBAL HOOK + LOCK": {"shots": ["talking-head-mcu"], "alt": ["jump-cut-punch-in", "face-reaction-product"]},
        "STORY BEAT":         {"shots": ["matched-before", "insert-object-detail", "talking-head-mcu"], "alt": ["selfie-walk-talk", "day-counter-selfie"]},
        "DEMO BEAT":          {"shots": ["pov-hands-first-use", "pour-dispense-cu", "timelapse-process"], "alt": ["overhead-hands-demo", "product-operating-cu"]},
        "EVIDENCE BEAT":      {"shots": ["matched-before", "match-cut-transform", "matched-after"], "alt": ["split-before-after", "timestamp-proof-insert", "reaction-cutaway-3q", "timelapse-process"]},
        "PAYOFF":             {"shots": ["matched-after", "reaction-cutaway-3q"], "alt": ["speed-ramp-reveal", "low-angle-hero-payoff", "result-first-reveal", "face-reaction-product"]},
        "COMMENT BAIT":       {"shots": ["mws-cta-to-camera"], "alt": ["comment-typing-insert"]},
        "CTA":                {"shots": ["loop-return-frame"], "alt": ["split-before-after", "end-card-hero"]}
      },
      "talking-head": {
        "VISUAL TRIGGER":     {"shots": ["text-card-over-motion"], "alt": ["problem-state-open", "hook-hands-mid-action", "face-reaction-product"]},
        "VERBAL HOOK + LOCK": {"shots": ["talking-head-mcu"], "alt": ["green-screen-explainer", "selfie-walk-talk"]},
        "TEACHING BEAT":      {"shots": ["insert-object-detail", "talking-head-mcu", "jump-cut-punch-in", "problem-state-open"], "alt": ["count-off-teaching-ms", "green-screen-explainer", "prop-explainer-cu", "text-card-over-motion"]},
        "EDUCATION BEAT":     {"shots": ["green-screen-explainer", "insert-object-detail", "reaction-cutaway-3q"], "alt": ["prop-explainer-cu", "vo-over-hands-broll", "macro-texture-ecu"]},
        "STORY BEAT":         {"shots": ["insert-object-detail", "talking-head-mcu", "profile-look-cutaway"], "alt": ["selfie-walk-talk", "establishing-ws"]},
        "REJECTION HISTORY":  {"shots": ["rejection-lineup", "talking-head-mcu"], "alt": ["jump-cut-punch-in", "toss-aside-cutaway"]},
        "PAYOFF":             {"shots": ["text-card-over-motion", "jump-cut-punch-in"], "alt": ["talking-head-product-in-hand", "hero-static-push-in"]},
        "COMMENT BAIT":       {"shots": ["mws-cta-to-camera"], "alt": ["comment-typing-insert", "talking-head-mcu"]},
        "CTA":                {"shots": ["end-card-hero"], "alt": ["loop-return-frame", "text-card-over-motion"]}
      },
      "pov-vlog": {
        "VISUAL TRIGGER":     {"shots": ["pov-hands-first-use"], "alt": ["day-counter-selfie", "problem-state-open", "pov-walk-in"]},
        "VERBAL HOOK + LOCK": {"shots": ["selfie-walk-talk"], "alt": ["talking-head-mcu", "day-counter-selfie"]},
        "STORY BEAT":         {"shots": ["insert-object-detail", "selfie-walk-talk", "reaction-cutaway-3q"], "alt": ["pov-walk-in", "establishing-ws", "whip-pan-transition", "mirror-selfie"]},
        "RITUAL BEAT":        {"shots": ["pov-walk-in", "ritual-step-wide", "pour-dispense-cu"], "alt": ["macro-texture-ecu", "timelapse-process", "mirror-selfie"]},
        "DEMO BEAT":          {"shots": ["pov-hands-first-use", "product-operating-cu"], "alt": ["over-shoulder-demo", "mirror-selfie", "pour-dispense-cu", "ritual-step-wide", "slowmo-hero-moment"]},
        "PAYOFF":             {"shots": ["result-first-reveal", "day-counter-selfie"], "alt": ["talking-head-product-in-hand", "timelapse-process", "speed-ramp-reveal"]},
        "COMMENT BAIT":       {"shots": ["comment-typing-insert"], "alt": ["mws-cta-to-camera", "selfie-walk-talk"]},
        "CTA":                {"shots": ["loop-return-frame"], "alt": ["pov-walk-in", "end-card-hero"]}
      }
    },
    "concepts": {
      "product": {},
      "showcase": {
        "VISUAL TRIGGER":     {"shots": ["product-operating-cu"], "alt": ["slowmo-hero-moment", "macro-texture-ecu", "hook-hands-mid-action"]},
        "EDUCATION BEAT":     {"shots": ["product-hero-orbit", "macro-texture-ecu", "lifestyle-context-ws"], "alt": ["feature-callout-hero", "flat-lay-reveal"]},
        "DEMO BEAT":          {"shots": ["pov-hands-first-use", "over-shoulder-demo", "slowmo-hero-moment"], "alt": ["product-operating-cu", "pour-dispense-cu", "flat-lay-reveal"]},
        "PAYOFF":             {"shots": ["speed-ramp-reveal", "face-reaction-product"], "alt": ["hero-static-push-in", "product-hero-orbit", "result-first-reveal"]},
        "COMMENT BAIT":       {"shots": ["mws-cta-to-camera"], "alt": ["comment-typing-insert"]},
        "CTA":                {"shots": ["loop-return-frame"], "alt": ["end-card-hero"]}
      },
      "challenge": {
        "VISUAL TRIGGER":     {"shots": ["problem-state-open"], "alt": ["day-counter-selfie", "insert-object-detail", "text-card-over-motion"]},
        "VERBAL HOOK + LOCK": {"shots": ["day-counter-selfie"], "alt": ["talking-head-mcu", "selfie-walk-talk"]},
        "STORY BEAT":         {"shots": ["insert-object-detail", "selfie-walk-talk", "establishing-ws"], "alt": ["reaction-cutaway-3q", "pov-walk-in", "mirror-selfie", "whip-pan-transition"]},
        "RITUAL BEAT":        {"shots": ["pov-walk-in", "ritual-step-wide"], "alt": ["timelapse-process", "insert-object-detail"]},
        "EVIDENCE BEAT":      {"shots": ["timestamp-proof-insert", "matched-before", "matched-after"], "alt": ["day-counter-selfie"]},
        "PAYOFF":             {"shots": ["reaction-cutaway-3q", "day-counter-selfie"], "alt": ["matched-after", "text-card-over-motion"]},
        "COMMENT BAIT":       {"shots": ["comment-typing-insert"], "alt": ["talking-head-mcu"]},
        "CTA":                {"shots": ["loop-return-frame"], "alt": ["text-card-over-motion", "day-counter-selfie"]}
      },
      "routine": {
        "VISUAL TRIGGER":     {"shots": ["pour-dispense-cu"], "alt": ["macro-texture-ecu", "pov-hands-first-use", "day-counter-selfie"]},
        "VERBAL HOOK + LOCK": {"shots": ["selfie-walk-talk"], "alt": ["talking-head-mcu"]},
        "RITUAL BEAT":        {"shots": ["establishing-ws", "pov-walk-in", "ritual-step-wide", "pour-dispense-cu", "macro-texture-ecu"], "alt": ["timelapse-process", "slowmo-hero-moment", "mirror-selfie"]},
        "STORY BEAT":         {"shots": ["insert-object-detail", "profile-look-cutaway"], "alt": ["selfie-walk-talk"]},
        "PAYOFF":             {"shots": ["result-first-reveal", "reaction-cutaway-3q"], "alt": ["timelapse-process", "day-counter-selfie"]},
        "CTA":                {"shots": ["loop-return-frame"], "alt": ["lifestyle-context-ws", "text-card-over-motion"]}
      },
      "advice": {
        "VISUAL TRIGGER":     {"shots": ["text-card-over-motion"], "alt": ["problem-state-open", "insert-object-detail"]},
        "VERBAL HOOK + LOCK": {"shots": ["talking-head-mcu"], "alt": ["green-screen-explainer", "jump-cut-punch-in"]},
        "TEACHING BEAT":      {"shots": ["insert-object-detail", "talking-head-mcu", "jump-cut-punch-in", "problem-state-open"], "alt": ["green-screen-explainer", "count-off-teaching-ms", "prop-explainer-cu", "text-card-over-motion"]},
        "EDUCATION BEAT":     {"shots": ["green-screen-explainer", "insert-object-detail"], "alt": ["prop-explainer-cu", "screen-insert"]},
        "EVIDENCE BEAT":      {"shots": ["screen-insert", "reaction-cutaway-3q"], "alt": ["green-screen-explainer", "prop-explainer-cu"]},
        "PAYOFF":             {"shots": ["text-card-over-motion", "jump-cut-punch-in"], "alt": ["reaction-cutaway-3q"]},
        "COMMENT BAIT":       {"shots": ["talking-head-mcu"], "alt": ["comment-typing-insert"]},
        "CTA":                {"shots": ["insert-object-detail"], "alt": ["text-card-over-motion", "loop-return-frame"]}
      }
    }
  }
}
```

### 5.4 SHOOT_PLAN_RULES

- **Human lane:** a setup is one phone position, light, location, wardrobe and product state. Setups are shot in the order given, not in story order.
- **AI lane:** a render group is one reference set, setting, light and seed.

Sources: Influee (B-roll first, coverage), ASDS (matched positions), Meta and TikTok Shop (light, stabilisation), Apple (AE/AF lock), and batching practice [A].

```json
{
  "SHOOT_PLAN_RULES": {
    "setup_key": ["location", "light_preset", "phone_support", "lens", "wardrobe", "product_state"],
    "group_rule": "shots with the same setup_key form one setup; inside a setup shoot wide to tight (WS, MWS, MS, MCU, CU, ECU) so the phone moves in one direction",
    "setup_order": [
      {"step": 1, "name": "pristine product", "ids": ["unboxing-mid-open", "flat-lay-reveal", "hero-static-push-in", "product-hero-orbit", "label-detail-ecu", "macro-texture-ecu", "end-card-hero", "feature-callout-hero", "text-card-over-motion"], "why": "packaging and product are untouched only once"},
      {"step": 2, "name": "BEFORE states", "ids": ["matched-before", "problem-state-open", "insert-object-detail"], "why": "tape the phone spot now; the AFTER reuses it"},
      {"step": 3, "name": "hands and demo", "ids": ["hook-hands-mid-action", "pov-hands-first-use", "over-shoulder-demo", "overhead-hands-demo", "product-operating-cu", "step-insert-cu", "pour-dispense-cu", "slowmo-hero-moment", "turn-in-hand-light", "hand-enters-pickup", "stress-test-action", "vo-over-hands-broll", "timelapse-process"]},
      {"step": 4, "name": "A-roll talking head", "ids": ["talking-head-mcu", "talking-head-product-in-hand", "confession-handheld-cu", "count-off-teaching-ms", "green-screen-explainer", "mws-cta-to-camera", "face-reaction-product", "reaction-cutaway-3q", "profile-look-cutaway", "low-angle-hero-payoff", "prop-explainer-cu"], "why": "record the whole script top to bottom, then the cutaways at the same light"},
      {"step": 5, "name": "AFTER states", "ids": ["matched-after", "result-first-reveal", "timestamp-proof-insert"], "why": "same taped spot, lens, light and time of day as step 2"},
      {"step": 6, "name": "location and movement", "ids": ["establishing-ws", "lifestyle-context-ws", "pov-walk-in", "selfie-walk-talk", "ritual-step-wide", "mirror-selfie", "day-counter-selfie"]},
      {"step": 7, "name": "screens", "ids": ["screen-insert", "comment-typing-insert"], "why": "screen-record after posting a draft; notifications off"},
      {"step": 8, "name": "transitions and pick-ups", "ids": ["whip-pan-transition", "lens-cover-transition", "speed-ramp-reveal", "match-cut-transform", "toss-aside-cutaway", "rejection-lineup", "comparison-side-by-side", "loop-return-frame"], "why": "loop-return-frame is shot right after frame 0 when possible, at the same setup"}
    ],
    "edit_only_ids": ["split-before-after", "jump-cut-punch-in"],
    "a_roll": {"takes_min": 2, "record_full_script_per_take": true, "resolution": "4K 30 fps", "punch_in_headroom": 1.5, "phone_height": "eye level, arm's length, on a stand"},
    "b_roll": {"roll_s_per_clip": [5, 10], "angles_per_action": 2, "clips_per_30s_video": [12, 20], "clips_for_ad_variant_library": [20, 30], "record_live_sound": true, "one_insert_per_vo_line_over_2s": true},
    "min_coverage_product_concepts": {"product close-ups (hero-static-push-in, turn-in-hand-light)": 2, "hands in use (pov-hands-first-use, vo-over-hands-broll)": 2, "texture (macro-texture-ecu)": 1, "result (result-first-reveal or matched-after)": 1, "flat lay (flat-lay-reveal)": 1, "wide context (lifestyle-context-ws)": 1},
    "camera_settings": {"lock": "AE/AF lock on the subject at every setup", "stabilisation": "on; handheld moves stay smooth (TikTok Shop)", "lens": "1x main; macro mode or 2x for ECU; no digital zoom past 2x", "fps": {"a_roll": 30, "motion": 60, "slow_motion": [120, 240], "slow_process": "phone Time-lapse mode"}, "filters_and_beauty_mode": "off"},
    "light_presets": {
      "window-key-45": {"use": "talking heads, reactions", "how": "face a window at about 45 degrees; overhead lights off; no direct sun", "vibes": ["raw-ugc", "expert-trust", "story-vlog"]},
      "window-plus-bounce": {"use": "product in hand, payoff", "how": "window key plus a white card or foam board on the shadow side", "vibes": ["clean-aesthetic", "expert-trust"]},
      "soft-overhead": {"use": "flat lays, overhead demos", "how": "diffused daylight or a lamp through white fabric; keep the phone's shadow out of frame", "vibes": ["clean-aesthetic", "asmr-satisfying"]},
      "side-raking": {"use": "macro, texture, foam, fabric", "how": "one low side light so texture casts small shadows; dark background", "vibes": ["asmr-satisfying", "cinematic-premium"]},
      "warm-practical": {"use": "cozy routines", "how": "a warm lamp as key, daylight blocked so colour temperatures do not mix", "vibes": ["cozy-calm", "story-vlog"]},
      "ring-light-front": {"use": "fast talking-head batches", "how": "only when no glossy product or glasses are in frame (ring reflections)", "vibes": ["hype-energy", "playful-comedic"]}
    },
    "before_after_protocol": ["tape the phone or stand position and note height, lens and zoom", "same light preset and time of day; flash off", "same background and framing; subject in the same pose and distance", "clock, date card or phone clock in frame", "no filters or beauty mode; the same edit grade on both clips", "hold each state 1.5 s or more; show the AFTER from the same spot before any closer shot"],
    "props_checklist_rules": [
      "every shot needing 'product' adds the product; add a second unit if the shot list has stress-test-action or a messy demo",
      "unboxing-mid-open adds a sealed box; film step 1 before opening anything",
      "comparison-side-by-side and rejection-lineup add the alternatives with brand marks taped over or turned away",
      "pour-dispense-cu, product-operating-cu and slowmo-hero-moment add the consumable (milk, water, cream) and a wipe cloth",
      "matched-before, matched-after and timestamp-proof-insert add a clock or date card and floor or table tape",
      "shots needing 'screen' add a second phone or screen recorder, a clean home screen and notifications off; never a product-page screenshot for TikTok Shop",
      "shots needing 'location' list the location and time of day; shots needing 'face' list the wardrobe (one outfit per shoot day; change outfits per day only for day-counter stories)",
      "kit, always: phone stand or tripod, white card, lens cloth, tape; lazy Susan if product-hero-orbit is used; overhead mount if overhead shots are used"
    ],
    "broll_checklist_rules": [
      "each VO line longer than 2 s gets an insert showing its noun (insert-object-detail or a product close-up)",
      "each demo step gets two angles (e.g. pov-hands-first-use + over-shoulder-demo)",
      "record live sound on every B-roll clip; it plays under the voice",
      "shoot one spare hero push-in and one spare reaction per setup for the variant cuts"
    ],
    "ai_render_plan": {
      "order": ["approve persona reference sheet (1-3 stills) and product reference photos", "render low-risk image-to-video shots first (hero, flat lay, macro, lifestyle, inserts)", "render presenter shots with identical persona text + same seed", "apply ai_fallback swaps and re-render any clip that fails QA", "assemble; add all text, captions and cards in the edit"],
      "render_group_key": ["reference_set", "setting", "light_preset", "seed"],
      "retry_limit_per_shot": 3,
      "on_repeated_failure": "swap to ai_fallback, then to text-card-over-motion"
    }
  }
}
```

### 5.5 Proposed gate/rubric rules

Each rule has a threshold and a source. **S-** rules are hard gate-2 failures; **R-** rules are rubric scores.

```json
{
  "PROPOSED_RULES": [
    {"id": "S-F0-PRODUCT", "check": "shot 1 (0-0.5 s) has a non-empty visual_types; product concepts: its needs include 'product' or its visual_type is result-reveal/before-after-split; never a talking_head_id", "threshold": "fail otherwise", "grade": "S/M", "source": ["virality §1", "Hilton-2026", "ABCD"]},
    {"id": "S-HUMAN-3S", "check": "a shot needing face or hands covers at least 1.0 s within 0-3.0 s; human presenter or TikTok Shop lane: a face shot within 0-3.0 s", "threshold": "1.0 s by 3.0 s", "grade": "S/P", "source": ["virality §1", "Emplifi-2026", "TT-Shop-2026"]},
    {"id": "S-SCALE-RUN", "check": "no 3 consecutive shots share a SHOT_SCALES id (extends D47 from talking heads to all shots); no 3 consecutive talking_head_ids", "threshold": "run of 2 or fewer", "grade": "M/A", "source": ["RULES-D47", "Ling-2021"]},
    {"id": "R-CADENCE", "check": "cuts per 10 s inside the vibe band of SHOT_RULES.cadence; hard fail outside 1.9-8.2 averaged over the video", "threshold": "band ±0.5 = full points; outside 1.9-8.2 = fail", "grade": "M", "source": ["Dost-Huang-2026", "Xiao-2024"]},
    {"id": "R-PRODUCT-SHARE", "check": "share of runtime in shots needing 'product' (product concepts)", "threshold": "demo 0.6 or more; review 0.5; transformation/pov-vlog 0.4; talking-head 0.3", "grade": "M/A", "source": ["TT-CreativeCodes", "ABCD", "VidMob-2025"]},
    {"id": "S-BA-MATCH", "check": "matched-before/matched-after pairs share setup id, scale and angle, hold at least 1.5 s each and carry a time marker; presenter=ai may not use generated before/after, stress-test or timestamp shots", "threshold": "all conditions", "grade": "S/P", "source": ["ASDS", "virality §3", "virality §6"]},
    {"id": "R-LOOP", "check": "duration of 15 s or less: last shot is loop-return-frame or repeats frame 0's scale+angle+subject", "threshold": "required at 15 s or less; +bonus above 15 s", "grade": "M", "source": ["Emplifi-2026", "YT-Shorts-deck-2026"]},
    {"id": "S-AI-RISK", "check": "presenter=ai: no ai_risk=high shot; at most 2 consecutive med shots; every model prompt ends with SHOT_RULES.ai.prompt_suffix and contains no double quotes and no 'render exactly' text; product-only inserts carry no persona description", "threshold": "0 high; 2 med in a row at most", "grade": "S/P", "source": ["Runway-Gen-4.5", "ABot-2026", "Google-best-practices", "Omni-docs", "T2V-text-2025"]},
    {"id": "S-SHOP-DYNAMIC", "check": "TikTok Shop lane: at least 3.0 s of continuous live action with face + product + camera move in a real setting; no still or loop segment over 1.0 s; no screen-insert showing a product page", "threshold": "3.0 s; 1.0 s", "grade": "P", "source": ["TT-Shop-2026"]},
    {"id": "S-D48-PHRASE", "check": "any shot over 3.5 s uses a move in {push-in, pan, tilt, handheld, tracking, dolly, whip-pan} and its camera line contains a gate-2 D48 keyword (pull-out, orbit and speed-ramp must be rendered as 'dolly out', 'tracking arc', 'handheld push-in')", "threshold": "3.5 s", "grade": "P (internal gate)", "source": ["gate-D48"]}
  ]
}
```

### 5.6 Proposed vocabulary additions

These are additions only; nothing is renamed, per the vocab contract.

```json
{
  "PROPOSED_VOCAB_ADDITIONS": {
    "VISUAL_TYPES": {
      "stress-test": "the product mid-torture-test (drop, spill, stretch), outcome not yet shown",
      "screen-proof": "a real phone screen, reading or receipt as the opening proof",
      "timelapse-process": "a slow process compressed into seconds, result forming"
    },
    "SHOT_ANGLES": ["selfie", "mirror"],
    "CAMERA_MOVES": ["punch-in", "rack-focus"],
    "SHOT_PURPOSES": ["loop"],
    "TRANSITIONS": ["hard-cut", "jump-cut", "match-cut", "whip-pan", "lens-cover", "speed-ramp", "l-cut"],
    "AI_RISK": ["low", "med", "high"],
    "SHOT_NEEDS": ["face", "hands", "product", "screen", "location", "props"],
    "LIGHT_PRESETS": ["window-key-45", "window-plus-bounce", "soft-overhead", "side-raking", "warm-practical", "ring-light-front"],
    "notes": {
      "punch-in": "an edit-time crop (jump-cut-punch-in), distinct from a physical push-in; gate-2 D48 does not count it as a move",
      "selfie": "front camera at arm's length; today it is modelled as eye-level",
      "whip-pan": "stays in CAMERA_MOVES and is also listed under TRANSITIONS"
    }
  }
}
```

Content was rephrased for compliance with licensing restrictions.
