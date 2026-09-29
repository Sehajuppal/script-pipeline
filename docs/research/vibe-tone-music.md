# Vibe, Tone, Pacing & Music — Creative Direction Research (2026-09-29)

> Status: complete (2026-09-29). Feeds `vsp/direction.py` (the CREATIVE DIRECTION block). Vocabulary: `vsp/creative_vocab.py` (VIBES, TONES, CAMERA_MOVES).

Grading: **[P]** platform/legal rule · **[S]** strong (peer-reviewed / large-sample) · **[M]** moderate (platform-published study, vendor data, single study) · **[A]** anecdotal (practitioner blogs, creator lore). **UNVERIFIED** = could not confirm from a primary source.

## 0. TL;DR
1. **One vibe per bundle.** Every bundle now gets the same STYLE paragraph. The evidence does not support "lo-fi always wins"; it supports native grammar plus aesthetic appeal (§2.1).
2. **Sound is on.** Over 80% of Reels plays are sound-on, and speech plus music works best. Drop the "85% muted" lines but keep captions (§2.3).
3. **Get energy from the picture.** Visual variety raises engagement linearly, while vocal arousal and speech rate are inverted-U. Keep VO at 150–190 wpm; calm vibes use fewer words and a SLOW_KEY (§1, §2.2).
4. **Include one showmanship device per script.** Pure salesmanship costs brand memory, and dull ads convert worse (§2.2).
5. **Licensing comes first.** Product videos are commercial on every account type: TikTok uses the CML, Meta the Sound Collection, YouTube the Audio Library. Add music at upload; no AI music on TikTok commercial content (§3, §5.5).
6. **AI personas carry a trust tax.** Use one calm, realism-matched voice, a clear label and utilitarian products. Story-vlog stays human-only (§4).

## 1. What the pipeline emits today (gap analysis)

I checked three current bundles (`/projects/wt/scratch-research/{electric-milk-frother,silk-pillowcase,sugar-21}`): an AI tools demo, a human beauty review and a human food pov-vlog challenge.

| Problem | Evidence in the bundles | Fix in this report |
|---|---|---|
| One STYLE paragraph for every product | All three `## STYLE` blocks repeat "Imperfection welcome… polish kills trust", hard cuts, "bold sans… max 3 words per card" and one audio line; only the set/light sentence changes | A `vibe` id picks a whole profile (§5.1) |
| Music has no brief | "neutral upbeat background music bed… ducked under speech" everywhere, with no mood, BPM, ducking level, SFX or **licence lane**. "Upbeat" also clashes with the lamp-lit pillowcase bedroom | `music` block + `MUSIC_LICENSING` (§3, §5.5) |
| Niche note mis-routed | The frother is niche `tools`, yet it got the food note ("shoot the food, not the cook"). | Genre notes come from the vibe + niche, not from keywords |
| "Polish kills trust" is asserted for everyone | This contradicts RULES §5 (backgrounds work through fit), C6 (the polished grammar is the AI lane) and the "raw always beats polished" entry on the Killed list. | Lo-fi vs polished becomes a per-vibe choice (§2.1) |
| Delivery ignores the vibe | Beat deliveries are fixed strings: hook "Brisk, confident", education "Unhurried, warm", demo "Energetic, pitch-varied", payoff "Slow down…", CTA "Brisk 160–180 wpm". A cozy pillowcase review and a hype gadget demo get the same curve. | `ENERGY_CURVE` per vibe + `TONE_PROFILES` (§5.3–5.4) |
| Contradictory voice line for AI | The AI frother bundle's Do NOT says "No robotic TTS — human voice only" beside an AI persona that needs a synthetic (disclosed) voice. | `presenter_notes.ai` + §4 |
| Stale muted-viewing claim | Hook directions still say "85% watch sound-off". short-form-virality.md already flags this as outdated. | Treat sound as on by default, but keep the video readable when muted (§2.3) |

**Gate compatibility.** `vsp/gates.py` D43 fails a beat when words ÷ wps(delivery) > window × 1.15. wps is 3.0 by default and 2.5 when the delivery contains "slow down", "unhurried" or "never rushed". Two consequences for every profile below:

1. Speech rate stays between 150 and 190 wpm, and 200 is a hard ceiling. A calm feel comes from **fewer words and longer pauses**, not from slower articulation.
2. A vibe whose band dips below 160 wpm must put a slow keyword in its delivery strings, so the gate sizes windows at 2.5 w/s.

## 2. Production-style evidence

short-form-virality.md already covers Meta's 1.2M-ad findings, "88% say sound is vital", Google's +20% music/VO lift, Xiao et al. 2024, BBC's 160–180 wpm, Netflix's 20 cps and the safe zones. This section adds only what changes **by vibe**.

### 2.1 Lo-fi / native vs polished
- **Platforms ask for native, not ugly.**
  - TikTok wants a DIY, not-overly-polished look with real people and trends ([TikTok Ads Help](https://ads.tiktok.com/help/article/creative-best-practices?lang=en)). [P/S]
  - Meta × Toluna tested 100 Reels ads on 65 variables across 4 markets (Dec 2025). Everyday-people scenes were 1.5× and emojis 2.5× more likely to reach the top 20% for purchase intent ([PPC Land](https://ppc.land/meta-and-toluna-study-finds-emojis-lift-reels-purchase-intent-2-5x/)). [M, correlational]
  - System1 × TikTok covered 887 ads, 84,788 users and 358 lift studies. Creator-led ads got 39% more attention but only half the brand recognition, so native style needs early branding ([System1](https://system1group.com/creative-effectiveness-tiktok)). [M]
- **Polish is not the enemy.**
  - Professional-quality brand images raised engagement on both Twitter and Instagram ([Li & Xie, JMR 2020](https://journals.sagepub.com/doi/abs/10.1177/0022243719881113)). [S, stills]
  - In a preregistered experiment (N=1,200), aesthetic appeal raised credibility while production quality had no effect ([arXiv 2605.26309](https://arxiv.org/abs/2605.26309)). [S stills / M video]
- **Rule.** Every vibe combines native grammar (people, phone framing, stickers, emoji) with clean composition and good light. Deliberate roughness belongs only in `raw-ugc` and `story-vlog` (C6). Delete "polish kills trust".

### 2.2 Energy & pacing
- **Speech rate is curvilinear.** Faster speech first raises perceived confidence, then the gain flattens or reverses ([J. Nonverbal Behavior 2024](https://pablobrinol.com/wp-content/uploads/2025/03/2024-JNB-vocal-speed-and-processing.pdf)). A meta-analysis found persuasion peaks at moderate rates ([meta-analysis](https://index.distantreader.org/stacks/journals-ojs/csm/csm-1783.pdf)). [S] This supports 150–190 wpm and B11 (slow down for strong claims).
- **Raise energy visually.** Auditory arousal had an inverted-U effect on engagement, while visual variation had a linear one ([JTAER 2025](https://www.mdpi.com/0718-1876/20/2/69/xml)). [M] Add angles, inserts and cuts, not a louder or faster voice.
- **Fast cuts sell but cost memory.** System1 counts fast-cut scenes, split screens, on-screen words, facts and CTAs as *Salesmanship*: +88% conversion lift, but brand awareness lift drops. *Showmanship* lifted both (+50% conversion for the top quartile). Its devices are story, characters, spontaneous expressions, a hummable tune, and a pause or soft voice. Dull ads converted 27% worse ([System1](https://system1group.com/creative-effectiveness-tiktok)). [M] Every script gets one showmanship device.
- **Cut rates in §5.1 are calibrations** [A], anchored on Xiao's inverted-U, D48's 3.5 s cap and B5.

### 2.3 Sound: VO + music, sound-on share
- **Sound is on.** Meta reports over 80% of Instagram Reels plays are sound-on. Speech plus music made brand ads 2.0× likelier to be top-20% for brand interest ([PPC Land](https://ppc.land/meta-and-toluna-study-finds-emojis-lift-reels-purchase-intent-2-5x/)). [M] TikTok calls itself a full-sound environment ([TikTok](https://ads.tiktok.com/business/en/blog/evolution-of-sound-volume-1)). [S] Replace the "85% muted" lines and keep captions for the muted minority.
- **Liked voices and music.** Ad viewers preferred quieter, clearer voices (higher harmonics-to-noise ratio), and faster music went with positive affect ([J. Travel Research 2023](https://journals.sagepub.com/doi/10.1177/00472875231185882); [2024](https://www.researchgate.net/publication/383263453_I_like_the_sound_of_that_understanding_the_effectiveness_of_audio_in_ads)). VO with hedonic products raised emotional response ([ECR 2024](https://link.springer.com/article/10.1007/s10660-024-09902-w)). [M]
- **Mix.** Duck music 8–12 dB under speech and keep SFX above the bed ([CapCut](https://www.capcut.com/create/audio-ducking-for-clear-dialogue-in-video); [Krotos](https://krotos.studio/blog/how-to-balance-music-and-sound-effects)). [A] No platform publishes a loudness target; treat −14 to −16 LUFS and −1 dBTP as reference only (**UNVERIFIED**, [APU](https://apu.software/youtube-audio-loudness-target/)).

### 2.4 Tempo / BPM and arousal
- **Tempo moves arousal; mode moves mood** ([Husain et al. 2002](https://online.ucpress.edu/mp/article-abstract/20/2/151/62120)). [S] Energy maps to BPM, and valence maps to mode and timbre.
- **Music shapes product perception once noticed.** Fast tempo made sneakers seem faster, and a trombone timbre made a laptop seem sturdier ([Tran & Getz 2023](https://online.ucpress.edu/mp/article-abstract/41/1/59/197099/Attention-Required-for-Advertisement-Pitch-Tempo)). Lower pitch implies a bigger product ([Lowe & Haws, JMR 2017](https://journals.sagepub.com/doi/10.1509/jmr.14.0300)). [S/M]
- **BPM bands** (calm 60–85, mid 88–110, hype 118–140) are editor convention. [A]

### 2.5 Music–brand/product congruence
- **Fit matters.** Music congruent with the ad raises ad evaluation and purchase intention ([North et al.](https://www.researchgate.net/publication/247732761_The_effect_of_musical_fit_on_consumers'_memory); [2020](https://www.researchgate.net/publication/340037344_The_Influence_of_Different_Levels_of_Musical_Fit_on_the_Efficiency_of_Audio-Visual_Advertising)). [S older / M]
- **AI voice–product fit.** Tuning an AI voice's vocal-tract length to a product's gender coding raised CTR and cut CPC in a field test ([J. Interactive Marketing 2023](https://journals.sagepub.com/doi/10.1177/10949968231194905)). [S]
- **Implication.** Choose mood by vibe × fit: steady beds for utilitarian products, warm sensory ones for hedonic, and product sound for `asmr-satisfying`. "Neutral upbeat" fits only hype-energy.

### 2.6 Voice tone: warm vs dominant, similarity
RULES B18 (warm-affiliative default) and §5/B14 (similarity over beauty) still hold. New evidence refines them:
- **Warm does not mean flat.** Persuaders naturally get louder and vary their volume, which signals confidence ([Van Zant & Berger, JPSP 2020](https://pubmed.ncbi.nlm.nih.gov/31192632/)). Falling intonation conveys confidence and helps strong arguments ([Vaughan-Johnston et al., PSPB 2024](https://journals.sagepub.com/doi/full/10.1177/01461672241262180)). [S] End proof lines on a falling contour, with no uptalk.
- **Soft sell wins.**
  - French Gen Z rated soft-sell voices higher on both warmth and competence ([Desmarais & Vignolles 2023](https://link.springer.com/chapter/10.1007/978-3-658-40429-1_22)). [M] The per-country results of the 2025 cross-cultural follow-up are **UNVERIFIED** ([JCIRA 2025](https://researchcommons.waikato.ac.nz/bitstreams/49108226-5238-48fb-bef9-81a990b632b9/download)).
  - Calm reads beat energetic ones, **even for synthesized voices** ([Frontiers 2023](https://www.frontiersin.org/journals/communication/articles/10.3389/fcomm.2023.1089577/full)). [M]
  - Higher pitch reads warmer and lower pitch more competent ([Perception 2022](https://journals.sagepub.com/doi/10.1177/03010066221135472)). [M]
- **Voices.** More distinct voices raised attention and persuasion across 11k+ videos ([JMR 2023](https://journals.sagepub.com/doi/10.1177/00222437221134115)). [S] Multiple AI voices, however, were harder to process ([EMAC 2023](https://proceedings.emac-online.org/pdfs/A2023-113984.pdf)). [M] Human videos may add a witness voice (C4); AI personas keep one voice.

### 2.7 Humor
- **Humor has a credibility cost.** It raises ad liking, attention, affect and purchase intention but **lowers source credibility** ([Eisend, JAMS 2009](https://link.springer.com/article/10.1007/s11747-008-0096-y)), and it can distract from the brand ([Eisend 2011](http://www.communicationcache.com/uploads/1/0/8/8/10887248/how_humor_in_advertising_works-_a_meta-analytic_test_of_alternative_models.pdf)). [S] On TikTok, influencer humor raised effectiveness through hedonic experience ([Barta et al. 2023](https://zaguan.unizar.es/record/121367/files/texto_completo.pdf)). [S]
- **Rule.** `playful-comedic` is for low-risk and hedonic products. The product causes the joke, and proof, price and guarantee lines are never jokes. It is vetoed for finance and health claims.

### 2.8 ASMR / satisfying
- **Evidence.** Auditory ASMR raised voice credibility, sensory gratification, transportation and endorser liking ([2025](https://scispace.com/papers/testing-mechanisms-in-asmr-persuasion-advertising-consumers-kecgyjw4tu2f)). [M] Visual triggers and rubbing or crunching sounds drove engagement ([EMAC 2025](https://proceedings.emac-online.org/pdfs/A2025-125653.pdf)). [M/A] RULES §3 already allows a whisper register for self-care products.
- **Gate fit.** Use few words and let real product sound carry the video; captions carry the meaning. Speech still has to fit the 2.5 w/s gate.

### 2.9 Lighting, color, grade (weak evidence; grade honestly)
- **Color.** Colorfulness effects vary by category ([Li & Xie 2020](https://journals.sagepub.com/doi/abs/10.1177/0022243719881113)). [S] Brighter, more saturated photos drew more responses ([2020](https://www.researchgate.net/publication/340209205_Coloring_the_destination_The_role_of_color_psychology_on_Instagram)). [A/M]
- **Grade.** In a System1 regrade of 7 ads (n=2,100), a story-congruent warm or cool grade added up to +0.4 stars: warm for upbeat stories, cool for tense ones. A cool-to-warm shift at the emotional turn added +0.7 ([System1 2026](https://system1group.com/blog/colour-grading-is-not-just-a-finishing-touch)). [A: small vendor test]
- **Hard constraints** [P]:
  - **Never change grade or light between BEFORE and AFTER.** TikTok bans misleading before/after, and FTC substantiation applies (virality §3); grade shifts are for narrative beats only.
  - No red in finance price graphics (B16).
  - YouTube treats color and lighting filters as minor edits that need no AI disclosure ([YouTube](https://support.google.com/youtube/answer/14328491?hl=en)).

### 2.10 Text styling & readability
- **BBC guidance for 9:16.** Lines up to 90% of frame width (about 25 characters), up to 3 lines, line height 3.9–4.5% of frame height (≈75–86 px). White on black and system sans fonts ([BBC](https://www.bbc.co.uk/accessibility/forproducts/guides/subtitles/)). [S]
- **Case.** Sentences read faster in lowercase or sentence case ([Perea et al.](https://www.uv.es/mperea/lowercaseUPPERCASE_reading.pdf)). Uppercase helps at small sizes ([Arditi & Cho 2007](https://www.researchgate.net/publication/6164530_Letter_case_and_text_legibility_in_normal_and_low_vision)). [S] ALL CAPS only for labels of ≤3 words.
- **Contrast.** At least 4.5:1, or 3:1 for large bold text ([WCAG 2.2](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)). [P] Over motion, use a plate or a 2–4 px outline, in semibold or bold weight. [A]
- **Emoji.** Emoji correlated with 2.5× purchase intent in DR ads (Toluna). [M] Use at most one per card and **never in frame-0 text**, which carries the search keyword (discovery-seo.md).

## 3. Music licensing lanes (2025–2026)

Every bundle we make promotes a product, so **every lane is commercial**, even on a personal or creator account. The platforms' general music libraries are licensed only for personal, non-commercial use.

### 3.1 TikTok
- **The general "Sounds" library is personal and non-commercial only** [P]. Brand use of it needs separate rights. The **Commercial Music Library (CML)** serves any commercial user, individuals included. Music uses up to about 1 min are generally allowed, commercial users may not use another user's original sound, and no library music may be used in LIVE ([Music Terms, Jan 2026](https://www.tiktok.com/legal/page/global/music-terms-us/en)).
- **Business accounts use the CML for everything commercial**: organic posts (including duets and stitches), ads and branded content ([Ads Help](https://ads.tiktok.com/help/article/commercial-music-library?lang=en)). [P]
- **CML terms** [P] ([CML Terms](https://www.tiktok.com/legal/page/global/commercial-music-library-user-terms/en)):
  - The CML is the *only* commercial music on TikTok, and it is licensed **for TikTok only**.
  - Obey each track's "Usable Placements"; Premium tracks may carry a fee.
  - Tracks whose rights lapse can be muted.
- **Promote** needs original or commercial sounds ([TikTok](https://ads.tiktok.com/help/article/about-tiktok-advertising-policies-for-promote)). [P] The Spark Ads help page states no music rule of its own ([Spark Ads](https://ads.tiktok.com/help/article/spark-ads)), so brief Spark Ads as CML or cleared audio (**UNVERIFIED** wording).
- **TikTok Shop** (Academy quality rules, 23 May 2026, via [PPC Land](https://ppc.land/tiktok-shops-quality-rules-ban-ai-voices-and-still-images-from-lives/)) [P]:
  - TikTok-library music only, with no suggestive tracks.
  - Use a microphone in a quiet room and **stabilized** footage.
  - Keep text synced with speech.
  - No AI voices in LIVE. Press extends the ban to shoppable videos ([PYMNTS](https://www.pymnts.com/commerce/ecommerce/2026/tiktok-shop-bans-ai-voices-from-livestreams/)); that is **UNVERIFIED**, so treat it as banned.

### 3.2 Instagram / Facebook (Meta)
- **Account type** [M]. Business accounts are limited to the royalty-free **Meta Sound Collection**. Personal and creator accounts see the licensed catalog, which does not cover branded use ([SRIPLAW via TechTimes](https://www.techtimes.com/articles/321387/20260723/instagram-replace-audio-lets-you-swap-music-old-posts-without-losing-likes.htm)). Meta keeps licence terms confidential, so the exact matrix is **UNVERIFIED**.
- **Sound Collection** can be used in Facebook and Instagram videos "without any limits", but only on Meta platforms ([Instagram](https://about.instagram.com/blog/announcements/updates-and-guidelines-for-including-music-in-video/)). [P]
- **Ads.**
  - Reels with copyrighted music cannot be boosted ([Instagram for Business](https://business.instagram.com/blog/boost-instagram-reels/)). [P]
  - Ads Manager offers a royalty-free catalog ([DMN 2022](https://www.digitalmusicnews.com/2022/10/05/meta-free-songs-catalog-advertisers-2022/)). [M]
  - Paid creator content reportedly must run as Partnership Ads in 2026, with AI disclosure extended to commercial ads ([ContentGrip](https://www.contentgrip.com/meta-branded-content-rules-update/)). [M, **UNVERIFIED**]
- **Replace Audio** (21 Jul 2026) swaps the music on a published post and keeps its engagement ([TechTimes](https://www.techtimes.com/articles/321387/20260723/instagram-replace-audio-lets-you-swap-music-old-posts-without-losing-likes.htm)). [M] Coverage of Reels is **UNVERIFIED**.

### 3.3 YouTube Shorts
- **Shorts Audio Library (label music).** Most songs run up to **90 s** in a 3-min Short; some are capped at 60 or 30 s ([YouTube](https://support.google.com/youtube/answer/15424877?hl=en); [eligibility](https://support.google.com/youtube/answer/13486873?hl=en)). The licence is personal and non-commercial, so commercial or branded Shorts **may fail to upload** with it. Use the **YouTube Audio Library** instead: green artwork and the YouTube logo, no Content ID claims ([upload errors](https://support.google.com/youtube/answer/10383400?hl=en-GB)). [P]
- **24 Sep 2026.** New 1–3-min Shorts with a Content ID claim are **no longer auto-blocked** and may stay playable; you remove the content or dispute to monetize (same source). [P] Playable is not licensed, so this opens no commercial lane.
- **Audio Library details.** Tracks are copyright-safe and monetizable; CC tracks need attribution ([Audio Library](https://support.google.com/youtube/answer/3376882?hl=en)). Use off YouTube is **UNVERIFIED**. [P]
- **Shorts ads.** Any music not from the Audio Library must be rights-cleared ([Google Ads](https://support.google.com/google-ads/answer/16041383?hl=en)). [P]

### 3.4 Original audio
- **Your own recordings are the safest cross-platform choice.** That means the VO, room tone, product sounds, and music you commissioned or own [P]. On TikTok, uploading original audio as a commercial user certifies you hold the rights (Music Terms).
- **Never reuse another creator's "original audio" in commercial content**, on any platform [P on TikTok; A elsewhere]. To ride a trend, copy its **format or beat timing** with a licensed track. [A]
- **Naming.** Renaming original audio for search is covered in discovery-seo.md.

### 3.5 AI-generated music
- **Copyright** [P]. Purely prompt-generated music is not copyrightable in the US ([USCO, Jan 2025](https://www.copyright.gov/newsnet/2025/1060.html)). *Thaler* cert was denied on 2 Mar 2026 ([Baker Donelson](https://www.bakerdonelson.com/supreme-court-denies-certiorari-in-thaler-v-perlmutter-ai-cannot-be-an-author-under-the-copyright-act)). You may use such music, but you can't own it exclusively.
- **Tools** [P, vendor terms]:
  - **Suno** (from 3 Sep 2026) grants commercial rights only for **paid-plan downloads** ([Suno](https://blog.suno.com/blog/suno-updates-tos)). Its v6 models are licensed with WMG, BMG and Believe, and Germany's GEMA won an infringement ruling against it ([TNW](https://thenextweb.com/news/suno-v6-warner-bmg-believe-licensed-models)). [M]
  - **Udio** is a walled garden with no export ([MBW](https://www.musicbusinessworldwide.com/udio-taps-content-security-buydrm-to-secure-its-ai-music-walled-garden/)), so it can't supply a soundtrack.
- **Labels** [P]:
  - **YouTube** requires "AI use = Yes" for AI-generated music; the label does not reduce reach ([YouTube](https://support.google.com/youtube/answer/14328491?hl=en)).
  - **TikTok ads** need the AIGC disclaimer for AI audio ([TikTok Ads](https://ads.tiktok.com/help/article/about-ad-disclaimers-in-tiktok-ads-manager)).
  - **TikTok's Music Terms** require disclosure, ban imitated real voices, and say AI music videos **should not be used for endorsements** (ambiguous scope; the conservative reading is no AI music in TikTok commercial content).
  - **Meta** requires disclosure of realistic synthetic audio ([Meta](https://about.fb.com/news/2024/04/metas-approach-to-labeling-ai-generated-content-and-manipulated-media/)).

### 3.6 What the bundle must instruct
1. **No music in the master.** Deliver `master` (VO + SFX + room tone) plus a guide mix. Music is added **at upload, per platform**, because the CML and Sound Collection are platform-locked.
2. **Lane lookup.** Pick the library from platform × account × lane (§5.5) and give 3 search queries (mood, genre, BPM). Never name a commercial song.
3. **Trending songs** only if they are in the CML or Sound Collection. Otherwise copy the trend's structure with a licensed bed.
4. **Clip length:** ≤60 s on TikTok, ≤90 s on Shorts (check the per-track cap).
5. **AI music** only for Meta and YouTube organic, with a paid-plan receipt, no imitated artist, and AI toggles on. Never on TikTok commercial content or Shop.
6. **Licence log** in the manifest: `{platform, account_type, lane, library, track_id, date, placements}`.

## 4. Voice & tone: AI persona vs human presenter

**Evidence**
- **AI pays a trust tax.**
  - A meta-analysis finds virtual influencers offer more novelty but less credibility than humans, and credibility matters more over time ([JAMS 2026](https://link.springer.com/article/10.1007/s11747-026-01186-w)). [S]
  - In implicit tests (n=1,300), human voices beat matched AI voices by +23% on trust and +24% on brand attraction. Priming "this is AI" cut trust 27%, even for human voices, and listeners guessed at chance ([Studio Resonate 2025](https://www.contentgrip.com/studio-resonate-ai-voice-study/)). [M]
  - AI voices matched human voices on attention and purchase intent, but believed-human voices felt more relatable ([WPP Media 2025](https://www.wppmedia.com/news/ai-voices-audio-ads)). [M]
  - In a field test, an AI avatar got +25% plays but −38% clicks ([JTAER 2026](https://www.mdpi.com/0718-1876/21/10/337)). [M]
  - Human livestream hosts won on trust through intimacy, especially under hedonic motives ([Frontiers 2026](https://www.frontiersin.org/articles/10.3389/fpsyg.2026.1797803)). [M] This matches F32 and B15.
- **Disclosure: clear, not loud.** Prominent VI disclosure lowered credibility more than subtle disclosure ([UvA](https://pure.uva.nl/ws/files/246518004/Disclosing_the_virtual_nature_of_virtual_influencers.pdf)). [M/S] The law still demands a conspicuous label (virality §6), so keep RULES §4's small, integrated frame-0 label. Tone cannot remove this cost; product fit is the lever.
- **Uncanny voices.** A face–voice realism mismatch reads as eerie ([Mitchell et al. 2011](https://pubmed.ncbi.nlm.nih.gov/23145223/)). [S] Uncanniness comes from deviating from typical human voices, and good synthetic voices escape it ([CHB Reports 2024](https://www.researchgate.net/publication/380669432_Deviation_from_typical_organic_voices_best_explains_a_vocal_uncanny_valley)). [M] Match voice realism to render realism, the audio counterpart of F133.
- **Synthetic prosody.**
  - Calm reads beat energetic ones (§2.6).
  - AI-anchor pitch variability has an inverted-U relation to engagement ([JTAER 2026](https://www.mdpi.com/0718-1876/21/8/273)). [M]
  - Slowing specific words aided comprehension, whereas global slowing only *seemed* clearer ([arXiv 2603.30032](https://arxiv.org/abs/2603.30032)). [M] Stress names and numbers; don't slow the whole track.
- **Stories need humans.** Human narrators out-persuade AI ones ([IJHCI 2024](https://www.tandfonline.com/doi/pdf/10.1080/10447318.2023.2288734)). [M] This supports D137.

**Rules for the bundle**

| | AI persona (`presenter=ai`) | Human (`presenter=human`) |
|---|---|---|
| Voice source | One locked, licensed, consented synthetic voice per persona; never a clone of a real person without written consent (Muse AUP bans unconsented cloning and passing outputs off as human; agent-runtime.md B8) | The creator's own voice; a second voice (witness or friend) is allowed |
| Replace the bundle line "No robotic TTS — human voice only" with | "Natural-prosody synthetic voice, disclosed; no robotic cadence; never claims to be human" | "Real voice, recorded on the day; no TTS, no voice changer" |
| Tones allowed | warm, confident, calm, expert, deadpan, playful (light). Excited and empathetic are restricted: excited only on reveal lines, empathetic only in third person | all 8 |
| Tones blocked | empathetic *confession*, excited *testimonial* (FTC 465: no experience claims) | none, but keep dominant/pressuring delivery out (B18) |
| Pace control | Set the TTS rate so output lands at 155–175 wpm. Put pauses in text (commas, em-dashes) or SSML `<break time="300ms"/>` at beat seams (matches `timing.PAUSE=0.3`). Stress keywords; end claims on a falling contour | Natural pace; 1–2 disfluencies allowed (B20); no scripted laughs (F142) |
| Lanes | Utilitarian or high-complexity products; **not** the TikTok Shop lane (AI voices banned in LIVE, reportedly in shoppable videos); ads need the AIGC disclaimer | Every lane, including Shop |
| QA | Run Muse Voice Transcribe in `ENDPOINTING` mode on the render: wpm per turn = words ÷ (endMs − startMs) × 60,000. Fail if any turn is above 200 wpm; warn below 140 (agent-runtime.md B3/C3; per-turn only, no word timestamps). Muse has **no TTS endpoint**, so voices come from an external engine (**UNVERIFIED** which) | Same transcript check; also flag any turn above 200 wpm |

## 5. Deliverables (JSON)

**Conventions**
- `energy` runs 1–5. wpm is the rendered rate. `vo_ducking_db` is the music gain reduction under VO.
- Text boxes use 1080×1920 coordinates inside the safe box x 120–888, y 288–1248.
- Frame-0 text is ≤3 words, UPPER, with no emoji.
- `movement` uses `CAMERA_MOVES` ids. Shots over 3.5 s need a D48 keyword (push-in, pan, tilt, dolly, handheld, tracking).

**Added fields** (optional): `pacing.gate_wps`, `pacing.delivery_key` (the SLOW_KEY for spoken beats, "" if brisk), `tone.{default, allowed}`, and `transitions` ids (§5.7).

### 5.1 VIBE_PROFILES
```json
{
  "raw-ugc": {
    "description": "Lo-fi phone footage, handheld, natural light, talking to a friend. Native grammar in a real room with candid delivery.",
    "energy": 3,
    "pacing": {"target_wpm": [160, 180], "avg_shot_s": [2.0, 3.5], "cuts_per_10s": [3, 5], "pattern_interrupt_s": 5, "gate_wps": 3.0, "delivery_key": ""},
    "music": {"moods": ["light", "warm", "unobtrusive"], "bpm": [88, 110], "genres": ["lo-fi hip-hop", "acoustic pop", "bedroom pop"], "vo_ducking_db": -12, "sfx": ["room tone", "real product sounds", "phone-mic ambience"]},
    "look": {"lighting": "window daylight or room practicals; uneven light is fine as long as the face reads", "palette_names": ["warm white", "denim", "sand", "sage"], "palette_hex": ["#F5F0E6", "#4A6FA5", "#D8C3A5", "#A3B18A"], "grade": "phone default, slightly warm white balance; no LUT, no crushed contrast", "set": "a real lived-in room (kitchen counter, car, bathroom, desk), tidied but real", "wardrobe": "everyday casual, solid colours, no visible logos"},
    "camera": {"style": "selfie or handheld phone at eye level, one-take feel", "lens": "phone main camera (~24-26 mm equiv.) or selfie camera (~23 mm)", "movement": ["handheld", "push-in", "static"]},
    "text_style": {"case": "sentence", "weight": "bold", "max_words_per_card": 5, "placement": "upper-centre band y 288-700, never over the face"},
    "transitions": ["jump-cut", "hard-cut", "punch-in"],
    "tone": {"default": "warm", "allowed": ["warm", "confident", "excited", "playful", "empathetic", "deadpan"]},
    "do": ["open mid-action with hands on the product", "keep one visible imperfection (RULES C1/C6)", "talk to one person, not an audience", "show the product more than once (Meta x Toluna 2.7x)"],
    "dont": ["no studio light or seamless backdrop", "no stock-footage inserts", "no trending song outside the licensed library", "no shaky footage in the TikTok Shop lane (stabilise)"],
    "best_niches": ["gadgets", "automotive", "home", "food", "fitness", "commentary", "default"],
    "best_formats": ["talking-head", "review", "demo"],
    "presenter_notes": {"ai": "Not recommended: DEFAULT_VIBE swaps it to clean-aesthetic. Candid grammar is the human lane (C6), and faked shake on an AI render adds detectable-flaw eeriness (F133).", "human": "Default human lane. Add at least 2 candid cues: handheld micro-shake, uneven natural light, a mid-sentence punch-in (C6)."},
    "evidence": ["tiktok-cbp", "meta-toluna-2025", "system1-tiktok", "rules-C6", "xiao-2024"]
  },
  "clean-aesthetic": {
    "description": "Minimal set, soft even light, neutral palette, calm confidence. Polished but not glossy; the product is the only focal point.",
    "energy": 2,
    "pacing": {"target_wpm": [150, 170], "avg_shot_s": [2.5, 3.5], "cuts_per_10s": [3, 4], "pattern_interrupt_s": 6, "gate_wps": 2.5, "delivery_key": "never rushed"},
    "music": {"moods": ["calm", "airy", "confident"], "bpm": [85, 105], "genres": ["minimal electronic", "soft house", "neo-soul instrumental"], "vo_ducking_db": -12, "sfx": ["soft whoosh on text", "subtle clicks", "clean product foley"]},
    "look": {"lighting": "large soft key (window or diffused softbox), low contrast, no hard shadows", "palette_names": ["off-white", "greige", "sage", "oat"], "palette_hex": ["#FAF9F6", "#CFC8BE", "#A3B18A", "#E6DCC8"], "grade": "clean, neutral-warm white balance, low saturation, slightly lifted blacks", "set": "minimal surface with 1-3 props and negative space, in the product's colour family (B19)", "wardrobe": "neutral knit or linen, no patterns, no logos"},
    "camera": {"style": "tripod or gimbal, symmetrical framing, product centred", "lens": "35-50 mm equiv. plus macro inserts", "movement": ["static", "push-in", "pan"]},
    "text_style": {"case": "sentence", "weight": "semibold", "max_words_per_card": 4, "placement": "lower-middle band y 700-1248 with generous margins"},
    "transitions": ["hard-cut", "match-cut", "l-cut"],
    "tone": {"default": "calm", "allowed": ["calm", "confident", "warm", "expert"]},
    "do": ["one idea per shot", "leave negative space for text", "one macro texture insert", "keep the voice warm and volume-varied, not flat (Van Zant & Berger)"],
    "dont": ["no clutter or busy patterns", "no heavy LUT or teal-orange", "no risers or hype SFX", "no more than one emoji on screen"],
    "best_niches": ["beauty", "home", "wellness", "gadgets"],
    "best_formats": ["demo", "review", "talking-head"],
    "presenter_notes": {"ai": "Preferred AI lane: clean framing hides render flaws. Lock the persona's face and set from video 1 (RULES §4).", "human": "Suits creators with an aesthetic account style. Keep one candid moment so it does not read as a TV ad."},
    "evidence": ["visual-matters-2026", "li-xie-2020", "calm-tts-2023", "rules-C6", "rules-B19"]
  },
  "hype-energy": {
    "description": "Fast cuts, bold text, upbeat music, high-energy delivery. A selling tool: strong for gadgets and quick wins, but it costs brand memory when it is all salesmanship.",
    "energy": 5,
    "pacing": {"target_wpm": [170, 190], "avg_shot_s": [1.2, 2.0], "cuts_per_10s": [5, 8], "pattern_interrupt_s": 3, "gate_wps": 3.0, "delivery_key": ""},
    "music": {"moods": ["upbeat", "driving", "bold"], "bpm": [118, 140], "genres": ["pop-EDM", "electro-pop", "trap-pop instrumental"], "vo_ducking_db": -8, "sfx": ["riser into the payoff", "impact hit on the reveal", "whoosh on cuts", "pop on text"]},
    "look": {"lighting": "bright high-key and punchy; one coloured accent light allowed", "palette_names": ["electric blue", "hot pink", "acid lime", "black"], "palette_hex": ["#2F6BFF", "#FF3EA5", "#C6FF00", "#111111"], "grade": "high contrast, saturated, crisp", "set": "clean backdrop or bold colour wall, product in hand", "wardrobe": "bold solid colour that contrasts with the backdrop"},
    "camera": {"style": "dynamic: fast angle changes, product close to the lens", "lens": "wide 16-24 mm equiv. plus macro", "movement": ["whip-pan", "speed-ramp", "push-in", "orbit", "handheld"]},
    "text_style": {"case": "upper", "weight": "extra-bold", "max_words_per_card": 3, "placement": "upper-centre band y 288-700, pops on the beat"},
    "transitions": ["whip-pan", "speed-ramp", "punch-in", "hard-cut"],
    "tone": {"default": "excited", "allowed": ["excited", "confident", "playful"]},
    "do": ["cut on the beat", "add one showmanship device: a character, story turn or hummable hook (System1)", "make the payoff the single loudest moment", "slow the VO on the proof line (B11)"],
    "dont": ["no more than 8 cuts per 10 s (Xiao inverted-U)", "no wall-to-wall hype: dip the energy once before the payoff (A6)", "no finance or health claims in this vibe", "no VO above 190 wpm"],
    "best_niches": ["gadgets", "fitness", "automotive", "tools"],
    "best_formats": ["demo", "transformation"],
    "presenter_notes": {"ai": "Utilitarian gadgets only. Keep the synthetic voice calm-confident rather than shouty: energetic synthetic reads were rated worse (Frontiers 2023).", "human": "Get energy from movement and cuts, not shouting. Loud-then-soft volume variation reads as confidence (Van Zant & Berger 2020)."},
    "evidence": ["system1-tiktok", "xiao-2024", "jtaer-2025-arousal", "husain-2002", "rules-A6", "rules-B11"]
  },
  "cozy-calm": {
    "description": "Warm low light, slow pacing, soft voice, low-tempo music bed. Comfort and ritual; sells feeling and texture.",
    "energy": 2,
    "pacing": {"target_wpm": [150, 160], "avg_shot_s": [3.0, 4.5], "cuts_per_10s": [2, 3], "pattern_interrupt_s": 7, "gate_wps": 2.5, "delivery_key": "unhurried"},
    "music": {"moods": ["warm", "soft", "nostalgic"], "bpm": [60, 85], "genres": ["lo-fi chill", "soft acoustic guitar", "ambient piano"], "vo_ducking_db": -12, "sfx": ["fabric rustle", "mug set down", "kettle or steam", "low rain ambience"]},
    "look": {"lighting": "warm practicals (bedside lamp, string lights, candle-look) at 2700-3200 K with soft fall-off", "palette_names": ["honey", "terracotta", "cream", "cocoa"], "palette_hex": ["#E3A857", "#C8664B", "#F3E9DC", "#6B4F3F"], "grade": "warm, soft contrast, gentle grain; natural skin", "set": "bed, sofa, blanket, mug, window at dusk", "wardrobe": "soft knits or loungewear in muted tones"},
    "camera": {"style": "close and intimate, slow reveals", "lens": "35-50 mm equiv., shallow depth of field", "movement": ["static", "push-in", "tilt"]},
    "text_style": {"case": "lower", "weight": "medium", "max_words_per_card": 5, "placement": "lower-middle band y 900-1248 on a soft plate"},
    "transitions": ["dissolve", "l-cut", "match-cut"],
    "tone": {"default": "calm", "allowed": ["calm", "warm", "empathetic"]},
    "do": ["use fewer words and longer pauses rather than slower speech", "every shot over 3.5 s names push-in or tilt (D48)", "let one real sound breathe (steam, fabric)", "keep the tone warm-affiliative (B18)"],
    "dont": ["no risers, impact hits or whip-pans", "no bright overhead light", "no speech below 150 wpm (gate floor)", "no urgency or scarcity language (A3)"],
    "best_niches": ["home", "wellness", "beauty", "food"],
    "best_formats": ["pov-vlog", "review", "talking-head"],
    "presenter_notes": {"ai": "Hedonic lane, so a human is preferred (F32). If AI, keep it product-led, with hands and objects rather than the face.", "human": "Best in the human lane. A whisper-soft register is allowed for self-care products (RULES §3, d=0.38) if every word stays intelligible."},
    "evidence": ["husain-2002", "calm-tts-2023", "jtr-2023-voice", "rules-B18", "rules-F32"]
  },
  "expert-trust": {
    "description": "Steady medium shots, clear labels, measured authoritative delivery. Evidence first; the presenter explains how and why.",
    "energy": 3,
    "pacing": {"target_wpm": [150, 170], "avg_shot_s": [2.5, 3.5], "cuts_per_10s": [3, 4], "pattern_interrupt_s": 6, "gate_wps": 2.5, "delivery_key": "never rushed"},
    "music": {"moods": ["steady", "focused", "neutral"], "bpm": [80, 100], "genres": ["ambient electronic", "light piano", "minimal pulse"], "vo_ducking_db": -14, "sfx": ["subtle tick on labels", "real tool or product sounds"]},
    "look": {"lighting": "neutral 5000-5600 K key plus fill; even face light; no hard shadows", "palette_names": ["navy", "white", "slate", "teal accent"], "palette_hex": ["#1F2A44", "#FFFFFF", "#6B7A8F", "#1A9E8F"], "grade": "neutral, true-to-life skin, moderate contrast", "set": "clean workbench, desk or counter with real tools; labels and readouts legible", "wardrobe": "plain crew or collared top, solid colour, no logos"},
    "camera": {"style": "tripod at eye level; MCU/MS on the presenter, ECU inserts on proof", "lens": "35-50 mm equiv.; macro for readouts", "movement": ["static", "push-in", "pan"]},
    "text_style": {"case": "sentence", "weight": "semibold", "max_words_per_card": 6, "placement": "lower label bar y 900-1248; numbers set large"},
    "transitions": ["hard-cut", "match-cut", "j-cut"],
    "tone": {"default": "expert", "allowed": ["expert", "confident", "calm", "warm"]},
    "do": ["state strong facts plainly (B1)", "end claims on a falling contour (Vaughan-Johnston 2024)", "show the measurement, not just the verdict", "use a medium shot for price or guarantee lines (§5)"],
    "dont": ["no jokes on proof lines (humour lowers source credibility, Eisend 2009)", "no red in finance price graphics (B16)", "no extreme close-up of the face on high-trust claims", "no 'I tested it' from an AI persona (FTC 465)"],
    "best_niches": ["tools", "finance", "education", "wellness", "automotive"],
    "best_formats": ["demo", "review", "talking-head"],
    "presenter_notes": {"ai": "Strong AI lane for utilitarian or high-complexity products (B15): the persona explains the mechanism and never claims personal experience.", "human": "Mention credentials only if they are real. Similarity still beats status (§5), so keep it conversational."},
    "evidence": ["vj-2024-intonation", "vanzant-berger-2020", "eisend-2009", "rules-B1", "rules-B15", "rules-B16"]
  },
  "playful-comedic": {
    "description": "Quick punchlines, reaction shots, meme timing. The product causes the joke; entertainment carries memory and conversion.",
    "energy": 4,
    "pacing": {"target_wpm": [165, 185], "avg_shot_s": [1.5, 2.5], "cuts_per_10s": [4, 7], "pattern_interrupt_s": 3, "gate_wps": 3.0, "delivery_key": ""},
    "music": {"moods": ["quirky", "bouncy", "cheeky"], "bpm": [100, 128], "genres": ["comedic pizzicato or ukulele", "funk-lite", "chiptune accents"], "vo_ducking_db": -10, "sfx": ["record scratch", "a beat of silence before the punchline", "cartoon boing (max 1)", "crowd reaction"]},
    "look": {"lighting": "bright, even, flat-ish practical light", "palette_names": ["sunny yellow", "coral", "sky blue", "white"], "palette_hex": ["#FFD23F", "#FF6B6B", "#4CC9F0", "#FFFFFF"], "grade": "bright and saturated", "set": "a real home or workplace with the props the gag needs", "wardrobe": "casual and colourful; a character costume is allowed"},
    "camera": {"style": "reaction coverage (MCU plus wide), POV skits", "lens": "24-35 mm equiv.", "movement": ["static", "whip-pan", "push-in", "handheld"]},
    "text_style": {"case": "sentence", "weight": "bold", "max_words_per_card": 6, "placement": "meme caption at the top band y 288-600"},
    "transitions": ["hard-cut", "punch-in", "whip-pan"],
    "tone": {"default": "playful", "allowed": ["playful", "deadpan", "excited", "warm"]},
    "do": ["make the product cause the punchline", "hold 0.4-0.6 s of silence before the payoff line", "include a reaction face (RULES C4)", "escalate across 3 beats (C2)"],
    "dont": ["no jokes on price, guarantee or proof lines", "never in finance or health-claim scripts", "no punching down or stereotypes", "no scripted laughter (F142)"],
    "best_niches": ["pets", "home", "food", "gadgets", "commentary"],
    "best_formats": ["pov-vlog", "demo", "talking-head"],
    "presenter_notes": {"ai": "Deadpan only, because a flat AI affect reads as intentional. Never an AI 'confession' gag (D137).", "human": "Best in the human lane. Overlapping two-person dialogue is the scriptable stand-in for real chemistry (RULES §9 killed list)."},
    "evidence": ["eisend-2009", "barta-2023", "system1-tiktok", "rules-C2", "rules-C4"]
  },
  "cinematic-premium": {
    "description": "Macro and slow motion, dramatic light, product as hero. VO is sparse; music and light do the persuading.",
    "energy": 3,
    "pacing": {"target_wpm": [150, 160], "avg_shot_s": [2.0, 4.0], "cuts_per_10s": [3, 5], "pattern_interrupt_s": 5, "gate_wps": 2.5, "delivery_key": "unhurried"},
    "music": {"moods": ["dramatic", "elegant", "anticipatory"], "bpm": [70, 100], "genres": ["cinematic ambient", "hybrid orchestral", "premium deep house"], "vo_ducking_db": -8, "sfx": ["sub drop on the reveal", "swells", "hyper-detailed product foley"]},
    "look": {"lighting": "low-key: hard side or back light, rim light, controlled reflections, dark backdrop", "palette_names": ["onyx", "champagne gold", "deep emerald", "smoke"], "palette_hex": ["#0B0B0C", "#C9A96E", "#0F5132", "#8A8D91"], "grade": "rich contrast, deep blacks, filmic highlight roll-off; a cool-to-warm shift on narrative beats only (System1 2026)", "set": "seamless dark sweep; stone, marble or wet surface", "wardrobe": "hands only, or black or neutral sleeves"},
    "camera": {"style": "macro plus slow motion with a motion-control feel", "lens": "macro (~100 mm equiv.) plus 50-85 mm", "movement": ["dolly", "orbit", "push-in", "speed-ramp", "tracking"]},
    "text_style": {"case": "upper", "weight": "medium", "max_words_per_card": 3, "placement": "centre of the safe box, one card at a time, wide letter-spacing"},
    "transitions": ["match-cut", "speed-ramp", "dissolve"],
    "tone": {"default": "confident", "allowed": ["confident", "calm", "expert"]},
    "do": ["speak the product name at the visual transient (A4)", "one hero reveal, at the payoff", "show the brand in context, never a bare logo (System1: bare logo -30% awareness lift)", "keep VO under ~40% of runtime"],
    "dont": ["no hard sell or discount shouting", "no stock clichés (splashes unrelated to the product)", "no grade shift across before/after evidence", "no more than 3 words per card"],
    "best_niches": ["beauty", "gadgets", "home", "automotive", "outdoors"],
    "best_formats": ["demo", "transformation"],
    "presenter_notes": {"ai": "Good AI lane when the persona is mostly off-screen (VO plus hands). The render must be flawless (F133).", "human": "The human appears as VO or hands. Keep one human-scale shot so it does not read as a TV spot."},
    "evidence": ["system1-grade-2026", "system1-tiktok", "li-xie-2020", "lowe-haws-2017", "rules-A4", "rules-F133"]
  },
  "asmr-satisfying": {
    "description": "Close-up textures and real product sound, with little or no music. The sound is the soundtrack; words are sparse and captioned.",
    "energy": 2,
    "pacing": {"target_wpm": [150, 160], "avg_shot_s": [2.5, 4.5], "cuts_per_10s": [2, 4], "pattern_interrupt_s": 6, "gate_wps": 2.5, "delivery_key": "unhurried"},
    "music": {"moods": ["none", "ambient"], "bpm": [60, 75], "genres": ["none (product sound)", "optional ambient pad"], "vo_ducking_db": -18, "sfx": ["close-mic product sounds: click, pour, peel, crinkle, snap, fizz", "no added foley the product cannot make"]},
    "look": {"lighting": "soft top or side light for texture; high-CRI, flicker-free", "palette_names": ["mint", "blush", "lilac", "clean white"], "palette_hex": ["#BDE0C8", "#F4C2C2", "#C8B6E2", "#FFFFFF"], "grade": "clean, slightly saturated, crisp micro-detail", "set": "a tidy surface: organiser, restock or cleaning scene in close-up", "wardrobe": "hands only; neat nails; no jewellery that clinks"},
    "camera": {"style": "overhead or POV close-up, locked off or slow drift", "lens": "macro; 50 mm equiv.", "movement": ["static", "push-in", "tilt"]},
    "text_style": {"case": "lower", "weight": "medium", "max_words_per_card": 4, "placement": "top band y 288-500, away from the action"},
    "transitions": ["match-cut", "hard-cut", "none"],
    "tone": {"default": "calm", "allowed": ["calm", "warm"]},
    "do": ["record real sound close-mic in a quiet room (TikTok Shop audio rule)", "complete the satisfying action on screen as the payoff", "caption the one key claim", "keep speech under ~40% of runtime"],
    "dont": ["no music over the key sound", "no whisper so slow it falls below the 2.5 w/s gate", "no fake or exaggerated foley that misrepresents the product", "no fast cuts that break the action"],
    "best_niches": ["home", "food", "beauty", "automotive", "pets"],
    "best_formats": ["demo", "transformation"],
    "presenter_notes": {"ai": "Good AI lane (hands and product, little face). Disclose if the hands are AI-rendered.", "human": "Human hands. A whisper VO is allowed for self-care products (RULES §3)."},
    "evidence": ["asmr-2025", "emac-2025-asmr", "rules-S3-whisper", "tiktok-shop-2026"]
  },
  "story-vlog": {
    "description": "Selfie and walk-and-talk diary in the present tense, with day markers. The viewer lives the streak or the day alongside the presenter.",
    "energy": 3,
    "pacing": {"target_wpm": [160, 180], "avg_shot_s": [1.5, 3.0], "cuts_per_10s": [3, 6], "pattern_interrupt_s": 5, "gate_wps": 3.0, "delivery_key": ""},
    "music": {"moods": ["optimistic", "personal", "light"], "bpm": [90, 115], "genres": ["indie pop", "acoustic", "lo-fi"], "vo_ducking_db": -12, "sfx": ["location ambience", "day-marker swoosh", "real moments (door, steps, pour)"]},
    "look": {"lighting": "available light across locations; daylight and golden hour welcome", "palette_names": ["daylight neutral", "sky", "leaf green", "warm skin"], "palette_hex": ["#EDE6DB", "#87CEEB", "#6A994E", "#E0AC69"], "grade": "natural with light warmth, consistent across days", "set": "several real locations plus one anchor spot revisited every day", "wardrobe": "a different outfit each day (a day cue), same hair and face"},
    "camera": {"style": "selfie-stick or handheld walk-and-talk with POV inserts", "lens": "wide 16-24 mm equiv. (selfie)", "movement": ["handheld", "tracking", "pan"]},
    "text_style": {"case": "sentence", "weight": "bold", "max_words_per_card": 5, "placement": "day marker top-left of the safe box (x 120-500, y 288-420); captions mid-frame"},
    "transitions": ["jump-cut", "match-cut", "hard-cut"],
    "tone": {"default": "warm", "allowed": ["warm", "excited", "empathetic", "playful", "calm"]},
    "do": ["present tense, first person (human only)", "put day markers on screen", "include one setback beat (C1)", "let the product cause a story turn (B8)"],
    "dont": ["no AI presenter (story formats are human-only, D137)", "no 'results' without showing the middle (B9)", "no health or weight-loss outcome claims", "no grade that shifts from day to day"],
    "best_niches": ["food", "fitness", "wellness", "beauty", "outdoors", "education"],
    "best_formats": ["pov-vlog"],
    "presenter_notes": {"ai": "Not allowed: DEFAULT_VIBE swaps it to clean-aesthetic. Story-time and confession are human-only (D137), and human narrators out-persuade AI ones on narrative (IJHCI 2024).", "human": "Default for challenge and routine concepts. Conversational co-experience delivery (F45)."},
    "evidence": ["rules-D137", "ijhci-2024", "rules-B8", "rules-B9", "rules-C1"]
  },
  "before-after-reveal": {
    "description": "Transformation first, with matched framing; the gap is the star. Show the after, rewind to how, then show the middle.",
    "energy": 4,
    "pacing": {"target_wpm": [160, 180], "avg_shot_s": [1.5, 3.0], "cuts_per_10s": [3, 6], "pattern_interrupt_s": 4, "gate_wps": 3.0, "delivery_key": ""},
    "music": {"moods": ["build", "release"], "bpm": [95, 125], "genres": ["pop build with a drop at the reveal", "cinematic riser into a beat"], "vo_ducking_db": -10, "sfx": ["riser into the reveal", "whoosh on the split wipe", "shutter click on the after frame"]},
    "look": {"lighting": "IDENTICAL setup for before and after: same position, time of day and white balance", "palette_names": ["neutral grey", "clean white", "charcoal"], "palette_hex": ["#A0A0A0", "#FFFFFF", "#333333"], "grade": "one grade for both halves; no change in grade, exposure or filter between them", "set": "locked-off framing on the same marks; the after is shot from the same angle", "wardrobe": "identical in both halves unless the wardrobe is the product"},
    "camera": {"style": "tripod-locked matched framing; split-screen", "lens": "same focal length for both halves", "movement": ["static", "whip-pan", "push-in"]},
    "text_style": {"case": "upper", "weight": "extra-bold", "max_words_per_card": 3, "placement": "BEFORE/AFTER labels at the top of each half, y 288-420"},
    "transitions": ["split-wipe", "match-cut", "whip-pan"],
    "tone": {"default": "confident", "allowed": ["confident", "excited", "warm", "expert"]},
    "do": ["show the after in frame 0 (RULES §6)", "script 1-2 middle progression beats (B9)", "keep the gap visible at thumbnail size", "label the time span (DAY 1 to DAY 7)"],
    "dont": ["no lighting, grade or angle change that fakes the result (TikTok ad policy; FTC)", "no unsupported transformation claims (TikTok Shop)", "no weight-loss before/after", "no beauty filter on either half"],
    "best_niches": ["home", "beauty", "automotive", "fitness", "pets", "outdoors"],
    "best_formats": ["transformation", "demo", "review"],
    "presenter_notes": {"ai": "Allowed for product transformations (cleaning, organising). The AI never claims its own body or skin changed.", "human": "Best for personal transformations. Disclose the time span and keep lighting identical."},
    "evidence": ["rules-S6", "rules-B9", "tiktok-ad-policy", "tiktok-shop-2026", "system1-grade-2026"]
  }
}
```
### 5.2 DEFAULT_VIBE
**Resolution order:**
1. Base vibe: the first matching `concept_rules` entry, else `format_niche[format][niche]`, else `format_default`, else `global_default`.
2. `prompt_cues`: first match, listed formats only.
3. `pack_pattern`: only while the vibe is still `raw-ugc`.
4. Swaps: `fit`, then `duration`, then `presenter`.
5. `niche_veto`.

Steps 4 (presenter) and 5 are hard constraints; the rest are defaults. The `examples` list is a test vector.

```json
{
  "global_default": "raw-ugc",
  "concept_rules": [
    {"concept": "showcase", "niche": ["home", "beauty"], "vibe": "clean-aesthetic"},
    {"concept": "showcase", "vibe": "raw-ugc"},
    {"concept": "challenge", "format": ["transformation"], "vibe": "before-after-reveal"},
    {"concept": "challenge", "vibe": "story-vlog"},
    {"concept": "routine", "vibe": "story-vlog"},
    {"concept": "advice", "niche": ["finance", "education", "tools", "wellness"], "vibe": "expert-trust"},
    {"concept": "advice", "vibe": "raw-ugc"}
  ],
  "format_niche": {
    "demo": {"gadgets": "hype-energy", "tools": "expert-trust", "beauty": "clean-aesthetic", "wellness": "clean-aesthetic", "automotive": "raw-ugc", "pets": "playful-comedic", "home": "clean-aesthetic", "outdoors": "raw-ugc", "fitness": "hype-energy", "food": "asmr-satisfying", "finance": "expert-trust", "education": "expert-trust", "commentary": "raw-ugc", "default": "raw-ugc"},
    "talking-head": {"gadgets": "raw-ugc", "tools": "expert-trust", "beauty": "raw-ugc", "wellness": "clean-aesthetic", "automotive": "raw-ugc", "pets": "playful-comedic", "home": "raw-ugc", "outdoors": "raw-ugc", "fitness": "raw-ugc", "food": "raw-ugc", "finance": "expert-trust", "education": "expert-trust", "commentary": "raw-ugc", "default": "raw-ugc"},
    "pov-vlog": {"gadgets": "story-vlog", "tools": "story-vlog", "beauty": "story-vlog", "wellness": "cozy-calm", "automotive": "story-vlog", "pets": "story-vlog", "home": "cozy-calm", "outdoors": "story-vlog", "fitness": "story-vlog", "food": "story-vlog", "finance": "story-vlog", "education": "story-vlog", "commentary": "raw-ugc", "default": "story-vlog"},
    "transformation": {"gadgets": "before-after-reveal", "tools": "before-after-reveal", "beauty": "before-after-reveal", "wellness": "before-after-reveal", "automotive": "before-after-reveal", "pets": "before-after-reveal", "home": "before-after-reveal", "outdoors": "before-after-reveal", "fitness": "before-after-reveal", "food": "before-after-reveal", "finance": "expert-trust", "education": "expert-trust", "commentary": "raw-ugc", "default": "before-after-reveal"},
    "review": {"gadgets": "raw-ugc", "tools": "expert-trust", "beauty": "raw-ugc", "wellness": "raw-ugc", "automotive": "raw-ugc", "pets": "raw-ugc", "home": "raw-ugc", "outdoors": "raw-ugc", "fitness": "raw-ugc", "food": "raw-ugc", "finance": "expert-trust", "education": "expert-trust", "commentary": "raw-ugc", "default": "raw-ugc"}
  },
  "format_default": {"demo": "raw-ugc", "talking-head": "raw-ugc", "pov-vlog": "story-vlog", "transformation": "before-after-reveal", "review": "raw-ugc"},
  "prompt_cues": [
    {"pattern": "\\b(asmr|satisfying|restock(ing)?|organi[sz]ing|cleaning|detailing)\\b", "formats": ["demo", "transformation"], "vibe": "asmr-satisfying"},
    {"pattern": "\\b(sleep|pillow(case)?|blanket|candle|bath|tea|cozy|bedtime|wind[- ]down|night routine)\\b", "formats": ["review", "talking-head", "pov-vlog", "demo"], "vibe": "cozy-calm"},
    {"pattern": "\\b(luxury|premium|perfume|fragrance|watch|jewel(le)?ry)\\b", "formats": ["demo", "review"], "vibe": "cinematic-premium"},
    {"pattern": "\\b(prank|skit|funny|me when)\\b", "formats": ["pov-vlog", "demo", "talking-head"], "vibe": "playful-comedic"}
  ],
  "pack_pattern": {
    "apply_if": "current vibe == 'raw-ugc' AND the pattern is the research pack's top pattern with share >= 0.25",
    "map": {"b-roll-captions": "clean-aesthetic", "talking-head-ugc": "raw-ugc", "caption-driven-skit": "playful-comedic", "before-after": "before-after-reveal", "lifestyle-diary": "cozy-calm", "day-in-life": "story-vlog", "meme-overlay": "playful-comedic", "cinematic-manifesto": "cinematic-premium"}
  },
  "fit": {
    "utilitarian": {"swap": {"cozy-calm": "clean-aesthetic"}, "music_bias": "steady, clean beds; no sentimental or nostalgic moods"},
    "hedonic": {"swap": {"expert-trust": "clean-aesthetic", "hype-energy": "raw-ugc"}, "music_bias": "warm, sensory beds; product sound up"},
    "neutral": {"swap": {}, "music_bias": "the vibe's defaults"}
  },
  "duration": [
    {"max_s": 15, "swap": {"cozy-calm": "clean-aesthetic", "story-vlog": "raw-ugc"}, "pacing": "use the upper half of target_wpm; pattern_interrupt_s = min(profile, 3)"},
    {"min_s": 16, "max_s": 45, "swap": {}, "pacing": "profile defaults"},
    {"min_s": 46, "swap": {"hype-energy": "raw-ugc"}, "pacing": "at least two energy dips (A6); pattern_interrupt_s = min(profile, 6)"}
  ],
  "presenter": {
    "ai": {"swap": {"raw-ugc": "clean-aesthetic", "story-vlog": "clean-aesthetic"}, "constraints": ["default tone is one of warm, confident, calm, expert, deadpan, playful", "excited and empathetic only in restricted form: excited on reveal lines, empathetic in third person, never as testimonial or confession", "a vibe whose default tone is excited switches to confident", "playful-comedic forces tone = deadpan", "no TikTok Shop lane", "fit = hedonic keeps the vibe but raises fit_warning (F32)"]},
    "human": {"swap": {}, "constraints": ["raw-ugc and story-vlog carry at least 2 candid cues (C6)"]}
  },
  "niche_veto": {
    "finance": {"never": ["playful-comedic", "hype-energy", "cozy-calm"], "fallback": "expert-trust"},
    "education": {"never": ["hype-energy"], "fallback": "expert-trust"},
    "wellness": {"never": ["hype-energy"], "fallback": "clean-aesthetic"}
  },
  "examples": [
    {"prompt": "electric milk frother", "concept": "product", "format": "demo", "niche": "tools", "fit": "utilitarian", "presenter": "ai", "duration_s": 30, "expected": "expert-trust"},
    {"prompt": "silk pillowcase", "concept": "product", "format": "review", "niche": "beauty", "fit": "neutral", "presenter": "human", "duration_s": 30, "expected": "cozy-calm"},
    {"prompt": "I quit sugar for 21 days", "concept": "challenge", "format": "pov-vlog", "niche": "food", "fit": "hedonic", "presenter": "human", "duration_s": 30, "expected": "story-vlog"},
    {"prompt": "my 5AM routine before work", "concept": "routine", "format": "pov-vlog", "niche": "wellness", "fit": "neutral", "presenter": "ai", "duration_s": 30, "expected": "clean-aesthetic"}
  ]
}
```

### 5.3 TONE_PROFILES
`wpm` is the target band. `delivery_key` is the SLOW_KEY to append to the delivery string, or "" for brisk.

```json
{
  "warm": {
    "description": "Friendly, affiliative, agreement-rich; a friend recommending something. The default tone (RULES B18).",
    "when_to_use": ["default for human UGC", "education and trust beats", "CTA (positive end valence, A3)"],
    "delivery_notes": "Smile in the voice with moderate pitch variation. Vary volume slightly (confidence cue) and end claims on a falling contour.",
    "wpm": [155, 175], "delivery_key": "",
    "phrasing_tips": ["contractions and 'I' / 'you'", "about 8 words per sentence", "agreement tags ('right?', 'same.') at most once", "no hedging on the proof line"],
    "ai_notes": "Safe default for AI personas. Avoid over-bright, high pitch, and keep one consistent voice (RULES §3)."
  },
  "confident": {
    "description": "Assured and direct without dominance; certainty comes from specifics.",
    "when_to_use": ["verbal hook", "payoff and verdict", "comparison beats"],
    "delivery_notes": "Slightly louder, with deliberate volume variation (Van Zant & Berger 2020). Falling intonation at the end of claims (Vaughan-Johnston 2024). Slow down on the strongest line (B11).",
    "wpm": [160, 180], "delivery_key": "",
    "phrasing_tips": ["short declaratives", "a concrete number or test in the line", "no 'kind of', 'maybe', 'honestly'", "one command at most, never stacked (B18)"],
    "ai_notes": "Allowed. Keep it calm-confident rather than salesy; a synthetic hard-sell read is disliked (Frontiers 2023)."
  },
  "excited": {
    "description": "High-arousal enthusiasm reserved for genuine reveals.",
    "when_to_use": ["hype-energy demo beats", "the reveal moment", "newness hooks"],
    "delivery_notes": "Wider pitch range and faster pace, but peaks only at the payoff. Drop to warm right after it (A1 post-peak buffer).",
    "wpm": [170, 190], "delivery_key": "",
    "phrasing_tips": ["at most one exclamation per 10 s", "sensory verbs over superlatives", "never '#1', 'best ever', 'guaranteed' (TikTok policy)"],
    "ai_notes": "Use sparingly. Energetic synthetic reads were rated worse than calm ones. Never an excited testimonial: an AI cannot claim use or experience (FTC 465)."
  },
  "calm": {
    "description": "Low-arousal, reassuring, spacious.",
    "when_to_use": ["cozy-calm and asmr-satisfying", "clean-aesthetic narration", "ritual beats"],
    "delivery_notes": "Softer intensity and clear articulation (quieter, clearer voices were preferred, JTR 2023). Pause about 0.3-0.5 s between sentences. Cut words instead of slowing below 150 wpm.",
    "wpm": [150, 160], "delivery_key": "unhurried",
    "phrasing_tips": ["fewer, shorter sentences", "sensory and texture words", "no urgency or scarcity"],
    "ai_notes": "The best-performing style for synthetic voices (Frontiers 2023). Keep pitch variation moderate, not monotone (JTAER 2026 inverted-U)."
  },
  "deadpan": {
    "description": "Flat, understated delivery where the visual contradicts the words; comedy through restraint.",
    "when_to_use": ["playful-comedic with an AI persona", "imperfection beats played for laughs", "contrarian hooks"],
    "delivery_notes": "Narrow pitch range with crisp timing. Hold 0.4-0.6 s of silence before the punchline; never laugh at your own line (F142).",
    "wpm": [155, 175], "delivery_key": "",
    "phrasing_tips": ["literal statements the footage undercuts", "understatement ('it's fine.')", "keep proof lines straight"],
    "ai_notes": "Well suited to AI: flat affect reads as intentional rather than uncanny."
  },
  "expert": {
    "description": "Measured authority that explains mechanism and evidence.",
    "when_to_use": ["expert-trust vibe", "education, teaching and evidence beats", "finance, education and tools niches"],
    "delivery_notes": "Measured pace, falling intonation, stress on numbers and units. Pause before the key figure; slow targeted words, not the whole line (arXiv 2603.30032).",
    "wpm": [150, 170], "delivery_key": "never rushed",
    "phrasing_tips": ["'Here's why:' followed by the mechanism", "units and test conditions", "name the source (borrowed authority, RULES §1)", "one caveat, then the refutation (B7)"],
    "ai_notes": "A strong AI lane for utilitarian and high-complexity products (B15). Explain; never claim personal testing."
  },
  "playful": {
    "description": "Teasing, light and bouncy; invites the viewer into the joke.",
    "when_to_use": ["playful-comedic", "comment-bait beats", "pets, home and food"],
    "delivery_notes": "Bouncy pitch and a smile in the voice, with quick back-and-forth rhythm and callbacks.",
    "wpm": [165, 185], "delivery_key": "",
    "phrasing_tips": ["rhetorical questions", "obviously non-literal exaggeration", "a callback to the hook at the CTA"],
    "ai_notes": "Light touch only. Humour costs source credibility (Eisend 2009), so keep the product claim outside the joke."
  },
  "empathetic": {
    "description": "Validating and gentle; names the viewer's frustration without shaming.",
    "when_to_use": ["problem-state and imperfection beats", "rejection history", "wellness and sensitive niches"],
    "delivery_notes": "Softer and a little lower in pitch, slowing on the pain point, then lifting into the solution (gain frame, A3).",
    "wpm": [150, 165], "delivery_key": "unhurried",
    "phrasing_tips": ["'if you've ever…'", "validate, then pivot", "no fear appeals or body shaming", "no guilt in the close"],
    "ai_notes": "No 'I've been there' from an AI persona (FTC 465: no experience claims). Use 'a lot of people…' and let a human carry confession beats (D137)."
  }
}
```

### 5.4 ENERGY_CURVE
`base` implements RULES A6: the hook opens curious, energy dips on trust beats, rises through the demo, peaks at the payoff, and resolves positively at the CTA. Energy drives **music intensity, cut rate and visual transients**, not speech rate: a payoff at energy 5 is still spoken with "Slow down" (B11).

```json
{
  "scale": {"1": "still: bed barely audible, locked shot", "2": "low: soft bed, slow moves", "3": "medium: conversational, normal cut rate", "4": "high: music forward, faster cuts, pitch-varied VO", "5": "peak: single transient (reveal, drop or hit), then a 0.8 s low-information buffer (A1)"},
  "base": {"VISUAL TRIGGER": 4, "VERBAL HOOK + LOCK": 4, "IMPERFECTION BEAT": 2, "REJECTION HISTORY": 2, "EDUCATION BEAT": 2, "TEACHING BEAT": 3, "STORY BEAT": 3, "DEMO BEAT": 4, "EVIDENCE BEAT": 3, "RITUAL BEAT": 2, "PAYOFF": 5, "COMMENT BAIT": 3, "CTA": 3},
  "by_vibe": {
    "raw-ugc":             {"VISUAL TRIGGER": 4, "VERBAL HOOK + LOCK": 4, "IMPERFECTION BEAT": 2, "REJECTION HISTORY": 2, "EDUCATION BEAT": 2, "TEACHING BEAT": 3, "STORY BEAT": 3, "DEMO BEAT": 4, "EVIDENCE BEAT": 3, "RITUAL BEAT": 2, "PAYOFF": 5, "COMMENT BAIT": 3, "CTA": 3},
    "clean-aesthetic":     {"VISUAL TRIGGER": 3, "VERBAL HOOK + LOCK": 3, "IMPERFECTION BEAT": 2, "REJECTION HISTORY": 2, "EDUCATION BEAT": 2, "TEACHING BEAT": 3, "STORY BEAT": 3, "DEMO BEAT": 3, "EVIDENCE BEAT": 3, "RITUAL BEAT": 2, "PAYOFF": 4, "COMMENT BAIT": 3, "CTA": 3},
    "hype-energy":         {"VISUAL TRIGGER": 4, "VERBAL HOOK + LOCK": 4, "IMPERFECTION BEAT": 3, "REJECTION HISTORY": 3, "EDUCATION BEAT": 3, "TEACHING BEAT": 3, "STORY BEAT": 3, "DEMO BEAT": 4, "EVIDENCE BEAT": 3, "RITUAL BEAT": 3, "PAYOFF": 5, "COMMENT BAIT": 4, "CTA": 4},
    "cozy-calm":           {"VISUAL TRIGGER": 3, "VERBAL HOOK + LOCK": 3, "IMPERFECTION BEAT": 2, "REJECTION HISTORY": 2, "EDUCATION BEAT": 2, "TEACHING BEAT": 2, "STORY BEAT": 2, "DEMO BEAT": 3, "EVIDENCE BEAT": 2, "RITUAL BEAT": 1, "PAYOFF": 4, "COMMENT BAIT": 2, "CTA": 2},
    "expert-trust":        {"VISUAL TRIGGER": 3, "VERBAL HOOK + LOCK": 3, "IMPERFECTION BEAT": 2, "REJECTION HISTORY": 2, "EDUCATION BEAT": 2, "TEACHING BEAT": 3, "STORY BEAT": 2, "DEMO BEAT": 3, "EVIDENCE BEAT": 3, "RITUAL BEAT": 2, "PAYOFF": 4, "COMMENT BAIT": 3, "CTA": 3},
    "playful-comedic":     {"VISUAL TRIGGER": 4, "VERBAL HOOK + LOCK": 4, "IMPERFECTION BEAT": 3, "REJECTION HISTORY": 2, "EDUCATION BEAT": 2, "TEACHING BEAT": 3, "STORY BEAT": 4, "DEMO BEAT": 4, "EVIDENCE BEAT": 3, "RITUAL BEAT": 2, "PAYOFF": 5, "COMMENT BAIT": 4, "CTA": 3},
    "cinematic-premium":   {"VISUAL TRIGGER": 4, "VERBAL HOOK + LOCK": 3, "IMPERFECTION BEAT": 2, "REJECTION HISTORY": 2, "EDUCATION BEAT": 2, "TEACHING BEAT": 2, "STORY BEAT": 3, "DEMO BEAT": 4, "EVIDENCE BEAT": 3, "RITUAL BEAT": 2, "PAYOFF": 5, "COMMENT BAIT": 2, "CTA": 3},
    "asmr-satisfying":     {"VISUAL TRIGGER": 3, "VERBAL HOOK + LOCK": 3, "IMPERFECTION BEAT": 2, "REJECTION HISTORY": 1, "EDUCATION BEAT": 2, "TEACHING BEAT": 2, "STORY BEAT": 2, "DEMO BEAT": 3, "EVIDENCE BEAT": 2, "RITUAL BEAT": 2, "PAYOFF": 4, "COMMENT BAIT": 2, "CTA": 2},
    "story-vlog":          {"VISUAL TRIGGER": 4, "VERBAL HOOK + LOCK": 4, "IMPERFECTION BEAT": 2, "REJECTION HISTORY": 2, "EDUCATION BEAT": 2, "TEACHING BEAT": 3, "STORY BEAT": 3, "DEMO BEAT": 3, "EVIDENCE BEAT": 3, "RITUAL BEAT": 2, "PAYOFF": 5, "COMMENT BAIT": 3, "CTA": 3},
    "before-after-reveal": {"VISUAL TRIGGER": 4, "VERBAL HOOK + LOCK": 4, "IMPERFECTION BEAT": 2, "REJECTION HISTORY": 2, "EDUCATION BEAT": 2, "TEACHING BEAT": 3, "STORY BEAT": 3, "DEMO BEAT": 4, "EVIDENCE BEAT": 3, "RITUAL BEAT": 2, "PAYOFF": 5, "COMMENT BAIT": 3, "CTA": 3}
  },
  "vo_rule_by_energy": {"1": "delivery carries the vibe's SLOW_KEY (or 'unhurried')", "2": "delivery carries the vibe's SLOW_KEY (or 'unhurried')", "3": "vibe delivery_key", "4": "brisk, pitch-varied (unless the vibe's gate_wps is 2.5)", "5": "'Slow down. Let the result land.' on the claim (B11); energy comes from picture and music"},
  "rules": [
    "exactly one beat reaches the curve's maximum, and it is the PAYOFF (a single peak, A6/A7)",
    "at least one beat before the DEMO or PAYOFF sits at least 1 below the hook (the dip, A6)",
    "CTA energy is at least 2, at most the PAYOFF energy, and gain-framed (A3)",
    "the beats actually in the script use at least 3 distinct energy levels, so the curve is never flat (indifference is the enemy: dull ads convert 27% worse, System1)",
    "after any energy-5 beat, no payload (price, name, link) for 0.8 s (A1)",
    "keep BPM fixed within a track; express energy through stems, ducking depth and cuts, and change track only at the PAYOFF"
  ]
}
```
### 5.5 MUSIC_LICENSING
Every cell assumes **commercial** content, because the pipeline only makes product videos. On TikTok, which has only personal and business accounts, `creator` means a personal account doing brand or affiliate work.

```json
{
  "principles": [
    "music is added at upload, per platform; the render master carries VO + SFX + room tone only",
    "CML is TikTok-only and Meta Sound Collection is Meta-only; one master needs per-platform music or a third-party licence that names every platform plus paid media",
    "never reuse another creator's original audio in commercial content",
    "log {platform, account_type, lane, library, track_id, date, placements} in the manifest"
  ],
  "matrix": {
    "tiktok": {
      "personal": {
        "organic": {"library": "Commercial Music Library (Commercial Sounds)", "also_ok": ["original audio you recorded or own", "third-party track licensed for TikTok commercial use (keep proof)"], "never": ["general Sounds library (personal, non-commercial only)", "another user's original sound"], "max_music_s": 60, "flags": ["commercial content disclosure toggle"], "sources": ["tiktok-music-terms-2026", "tiktok-cml-terms"]},
        "shop": {"library": "Commercial Music Library", "also_ok": ["original audio you own"], "never": ["general Sounds library", "another user's original sound", "sexually suggestive tracks", "AI-generated music (Music Terms endorsement clause)", "AI voice as presenter"], "max_music_s": 60, "flags": ["commercial content disclosure toggle", "microphone, quiet room, stabilised footage"], "sources": ["tiktok-shop-2026", "tiktok-music-terms-2026"]},
        "ads": {"library": "Commercial Music Library, respecting each track's Usable Placements (Premium tracks may carry a fee)", "also_ok": ["original audio", "track licensed with paid-media rights"], "never": ["general Sounds library (Promote rejects it)", "another user's original sound"], "max_music_s": 60, "flags": ["AI-generated content disclaimer if any audio is AI", "Spark authorization"], "sources": ["tiktok-promote-policy", "tiktok-cml-terms", "tiktok-ad-disclaimers"]}
      },
      "creator": {
        "organic": {"library": "Commercial Music Library (Commercial Sounds)", "also_ok": ["original audio you recorded or own"], "never": ["general Sounds library for brand, affiliate or gifted posts", "another user's original sound"], "max_music_s": 60, "flags": ["commercial content disclosure toggle (Branded content)"], "sources": ["tiktok-music-terms-2026", "tiktok-cml-terms"]},
        "shop": {"library": "Commercial Music Library", "also_ok": ["original audio you own"], "never": ["general Sounds library", "another user's original sound", "AI-generated music", "AI voice as presenter"], "max_music_s": 60, "flags": ["commercial content disclosure toggle", "microphone, quiet room, stabilised footage"], "sources": ["tiktok-shop-2026", "tiktok-music-terms-2026"]},
        "ads": {"library": "Commercial Music Library (Usable Placements checked)", "also_ok": ["original audio", "track licensed with paid-media rights"], "never": ["general Sounds library", "another user's original sound"], "max_music_s": 60, "flags": ["AI-generated content disclaimer if any audio is AI", "Spark authorization code from the creator"], "sources": ["tiktok-promote-policy", "tiktok-cml-terms", "tiktok-ad-disclaimers"]}
      },
      "business": {
        "organic": {"library": "Commercial Music Library only", "also_ok": ["original audio you own"], "never": ["general Sounds library (not available for commercial use)", "another user's original sound", "cross-posting the CML track to Reels or Shorts"], "max_music_s": 60, "flags": [], "sources": ["tiktok-cml-help", "tiktok-cml-terms"]},
        "shop": {"library": "Commercial Music Library", "also_ok": ["original audio you own"], "never": ["general Sounds library", "another user's original sound", "AI-generated music", "AI voice as presenter"], "max_music_s": 60, "flags": ["microphone, quiet room, stabilised footage"], "sources": ["tiktok-shop-2026", "tiktok-cml-help"]},
        "ads": {"library": "Commercial Music Library via Creative Center (Usable Placements; Premium fee)", "also_ok": ["track licensed with paid-media rights", "original audio"], "never": ["general Sounds library", "another user's original sound"], "max_music_s": 60, "flags": ["AI-generated content disclaimer if any audio is AI"], "sources": ["tiktok-cml-terms", "tiktok-ad-disclaimers", "tiktok-promote-policy"]}
      }
    },
    "instagram": {
      "personal": {
        "organic": {"library": "Meta Sound Collection", "also_ok": ["original audio you own", "third-party track licensed for Instagram commercial use"], "never": ["in-app licensed songs in product-promoting posts (personal-use licence; detail UNVERIFIED)", "other creators' original audio"], "max_music_s": null, "flags": ["paid partnership label if a brand is involved", "AI info label for realistic AI audio or video"], "sources": ["ig-music-guidelines-2020", "meta-ai-labels"]},
        "shop": {"library": "Meta Sound Collection", "also_ok": ["original audio you own"], "never": ["in-app licensed songs", "other creators' original audio"], "max_music_s": null, "flags": ["paid partnership label for affiliate or gifted posts"], "sources": ["ig-music-guidelines-2020"]},
        "ads": {"library": "Meta Sound Collection or Ads Manager royalty-free music", "also_ok": ["track licensed with paid-media rights"], "never": ["copyrighted in-app music (makes the Reel ineligible for boosting)"], "max_music_s": null, "flags": ["AI disclosure at ad setup", "Partnership Ads format for creator content (UNVERIFIED primary)"], "sources": ["ig-boost-2022", "meta-reels-ads-music-2022", "contentgrip-2026"]}
      },
      "creator": {
        "organic": {"library": "Meta Sound Collection", "also_ok": ["original audio you own", "third-party track licensed for Instagram commercial use"], "never": ["in-app licensed songs in branded or affiliate Reels", "other creators' original audio"], "max_music_s": null, "flags": ["paid partnership label", "AI info label for realistic AI audio or video"], "sources": ["ig-music-guidelines-2020", "meta-ai-labels"]},
        "shop": {"library": "Meta Sound Collection", "also_ok": ["original audio you own"], "never": ["in-app licensed songs", "other creators' original audio"], "max_music_s": null, "flags": ["paid partnership label"], "sources": ["ig-music-guidelines-2020"]},
        "ads": {"library": "Meta Sound Collection or Ads Manager royalty-free music", "also_ok": ["track licensed with paid-media rights"], "never": ["copyrighted in-app music"], "max_music_s": null, "flags": ["Partnership Ads (UNVERIFIED primary)", "AI disclosure at ad setup"], "sources": ["ig-boost-2022", "contentgrip-2026"]}
      },
      "business": {
        "organic": {"library": "Meta Sound Collection (the business-account library)", "also_ok": ["original audio you own", "third-party track licensed for Instagram commercial use"], "never": ["in-app licensed songs", "other creators' original audio"], "max_music_s": null, "flags": ["AI info label for realistic AI audio or video"], "sources": ["sriplaw-techtimes-2026", "ig-music-guidelines-2020"]},
        "shop": {"library": "Meta Sound Collection", "also_ok": ["original audio you own"], "never": ["in-app licensed songs", "other creators' original audio"], "max_music_s": null, "flags": [], "sources": ["sriplaw-techtimes-2026"]},
        "ads": {"library": "Ads Manager royalty-free music or Meta Sound Collection", "also_ok": ["track licensed with paid-media rights"], "never": ["copyrighted in-app music"], "max_music_s": null, "flags": ["AI disclosure at ad setup"], "sources": ["meta-reels-ads-music-2022", "ig-boost-2022"]}
      }
    },
    "youtube_shorts": {
      "personal": {
        "organic": {"library": "YouTube Audio Library (green artwork + YouTube logo; filter 'Attribution not required' or add the CC credit)", "also_ok": ["original audio you own", "track cleared for commercial use on YouTube"], "never": ["Shorts Audio Library label music in commercial or branded Shorts (personal, non-commercial licence; upload errors)"], "max_music_s": null, "flags": ["paid promotion toggle if sponsored", "AI use = Yes if the music or voice is AI"], "sources": ["yt-upload-errors", "yt-audio-library", "yt-ai-disclosure"]},
        "shop": {"library": "YouTube Audio Library", "also_ok": ["original audio you own"], "never": ["Shorts Audio Library label music"], "max_music_s": null, "flags": ["paid product placement toggle", "AI use = Yes if AI"], "sources": ["yt-upload-errors", "yt-audio-library"]},
        "ads": {"library": "YouTube Audio Library or fully cleared licensed music", "also_ok": ["original audio"], "never": ["Shorts Audio Library label music", "relying on the 24 Sep 2026 'playable despite claim' change"], "max_music_s": null, "flags": ["AI use = Yes if AI"], "sources": ["gads-shorts-faq", "yt-3min-shorts"]}
      },
      "creator": {
        "organic": {"library": "YouTube Audio Library", "also_ok": ["original audio you own", "track cleared for commercial use on YouTube"], "never": ["Shorts Audio Library label music in branded Shorts"], "max_music_s": null, "flags": ["paid promotion toggle", "AI use = Yes if AI"], "sources": ["yt-upload-errors", "yt-audio-library", "yt-ai-disclosure"]},
        "shop": {"library": "YouTube Audio Library", "also_ok": ["original audio you own"], "never": ["Shorts Audio Library label music"], "max_music_s": null, "flags": ["paid product placement toggle"], "sources": ["yt-upload-errors"]},
        "ads": {"library": "YouTube Audio Library or fully cleared licensed music", "also_ok": ["original audio"], "never": ["Shorts Audio Library label music"], "max_music_s": null, "flags": ["AI use = Yes if AI"], "sources": ["gads-shorts-faq"]}
      },
      "business": {
        "organic": {"library": "YouTube Audio Library", "also_ok": ["original audio you own", "track cleared for commercial use on YouTube"], "never": ["Shorts Audio Library label music (commercial channel)"], "max_music_s": null, "flags": ["AI use = Yes if AI"], "sources": ["yt-upload-errors", "yt-audio-library"]},
        "shop": {"library": "YouTube Audio Library", "also_ok": ["original audio you own"], "never": ["Shorts Audio Library label music"], "max_music_s": null, "flags": ["paid product placement toggle"], "sources": ["yt-upload-errors"]},
        "ads": {"library": "YouTube Audio Library or fully cleared licensed music", "also_ok": ["original audio"], "never": ["Shorts Audio Library label music"], "max_music_s": null, "flags": ["AI use = Yes if AI"], "sources": ["gads-shorts-faq"]}
      }
    }
  },
  "caps": {"tiktok_general_music_s": 60, "yt_shorts_audio_library_s": {"default": 90, "some_tracks": [60, 30]}, "yt_content_id_1_to_3_min_from": "2026-09-24"},
  "ai_music": {
    "allowed_on": ["instagram organic (AI info label)", "youtube_shorts organic (AI use = Yes)"],
    "blocked_on": ["tiktok any commercial lane (Music Terms: AI music videos should not be used for endorsements)", "tiktok shop", "any ad unless the AI disclaimer is set and the licence covers paid media"],
    "requirements": ["generated on a paid plan with commercial rights, download receipt logged (Suno: paid-plan downloads only since 2026-09-03)", "no imitation of a real artist or voice", "no export-locked tools (Udio walled garden)", "expect no copyright ownership of pure AI output (USCO 2025; Thaler cert denied 2026-03-02)"]
  }
}
```

### 5.6 Proposed rubric / gate rules
```json
[
  {"id": "VTM1", "name": "vibe_speech_rate", "check": "If vibe.pacing.gate_wps == 2.5 or beat energy <= 2, every spoken beat's delivery contains a SLOW_KEY. The rendered per-turn wpm (Muse Voice Transcribe ENDPOINTING) lies within vibe.target_wpm +/- 10.", "threshold": "fail: any turn > 200 wpm, or a slow-vibe beat without a SLOW_KEY; warn: outside target +/- 10", "source": ["vsp/gates.py D43 + lexicon SLOW_KEYS", "BBC R&D 160-180 wpm", "Vaughan-Johnston 2024 JNB (curvilinear)", "agent-runtime.md B3"]},
  {"id": "VTM2", "name": "energy_curve_shape", "check": "Compute ENERGY_CURVE.by_vibe over the script's beats.", "threshold": "fail: the maximum is not a single beat at PAYOFF, CTA is outside [2, PAYOFF], or fewer than 3 distinct levels; warn: no beat before PAYOFF sits at least 1 below the hook (fix by adding an EDUCATION or EVIDENCE beat)", "source": ["RULES A1/A3/A6", "System1 x TikTok (dull ads -27% conversion)"]},
  {"id": "VTM3", "name": "music_lane_valid", "check": "direction.music.library is in MUSIC_LICENSING[platform][account][lane].library or also_ok. The music block names no song titles or artists. The licence-log keys are present.", "threshold": "fail on any mismatch or a named commercial song", "source": ["TikTok Music Terms 2026", "CML User Terms", "YouTube upload-errors page", "Instagram boost eligibility"]},
  {"id": "VTM4", "name": "music_not_baked", "check": "The render brief asks for a music-free master plus a guide mix; the final music is added at upload.", "threshold": "fail if the brief tells the video agent to add a final commercial track", "source": ["CML User Terms (TikTok-only use)", "Instagram: Sound Collection for Facebook and Instagram videos"]},
  {"id": "VTM5", "name": "ai_audio_disclosure", "check": "AI music or AI voice sets the platform flags: YouTube AI use = Yes, TikTok ads AIGC disclaimer, Meta AI info. There is no AI music in TikTok commercial or Shop lanes, and presenter=ai is never in the TikTok Shop lane.", "threshold": "fail if any flag is missing or a blocked lane is used", "source": ["YouTube GenAI disclosure", "TikTok ad disclaimers", "TikTok Music Terms s.6", "TikTok Shop Academy 2026-05-23"]},
  {"id": "VTM6", "name": "music_vibe_congruence", "check": "music.bpm is within vibe.bpm +/- 10 and music.moods overlaps vibe.moods. Hedonic fit gets no 'steady/neutral' bed; utilitarian fit gets no 'nostalgic' bed. asmr-satisfying ducks music at least 18 dB under the product sound, or uses no music.", "threshold": "warn on mismatch; fail if the legacy 'neutral upbeat' bed ships with cozy-calm, asmr-satisfying or cinematic-premium", "source": ["Husain et al. 2002", "musical-fit literature", "J. Interactive Marketing 2023 (voice-product congruence)"]},
  {"id": "VTM7", "name": "text_legibility", "check": "Frame-0 text is at most 3 words, UPPER, no emoji. Other cards have at most vibe.max_words_per_card words, and cards over 3 words use sentence or lower case. Contrast is at least 4.5:1 (3:1 for large bold). Line height is at least 75 px, at most 25 chars per line and 3 lines, and at most 1 emoji per card.", "threshold": "fail: frame-0 or contrast violations; warn: the rest", "source": ["BBC subtitle guidelines (9:16)", "WCAG 2.2 SC 1.4.3", "Perea et al. (case)", "Meta x Toluna (emoji)"]},
  {"id": "VTM8", "name": "before_after_lock", "check": "Every BEFORE/AFTER pair shares identical lighting, grade, lens, angle and white-balance tokens, with no filter on either half.", "threshold": "fail on any differing token", "source": ["TikTok ad policy: misleading before/after", "FTC substantiation (virality s.3/s.6)", "System1 2026 (grade shifts change emotion)"]},
  {"id": "VTM9", "name": "presenter_voice_lane", "check": "For presenter=ai, the voice spec says 'synthetic' and 'disclosed', the bundle never says 'human voice only', the tone is not an excited testimonial or empathetic confession, and the vibe is not story-vlog.", "threshold": "fail on any breach", "source": ["Muse AUP (agent-runtime.md B8)", "FTC 16 CFR 465", "RULES D137", "IJHCI 2024"]},
  {"id": "VTM10", "name": "showmanship_device", "check": "Scripts that are hype-energy or salesmanship-heavy (split-screen, facts and CTA together) contain at least 1 showmanship device: a story turn, a character, a reaction face, a hummable hook, a soft voice or pause, or an out-of-the-ordinary moment.", "threshold": "warn if none", "source": ["System1 x TikTok 2025-26 (showmanship +50% conversion lift, salesmanship -50% brand awareness lift)"]}
]
```

### 5.7 Proposed vocabulary additions
These ids are **not** in `creative_vocab.py`. They are proposals; the profiles above already use the `TRANSITIONS` ids.

```json
{
  "VIBES": {
    "tutorial-screen": "screen-record or whiteboard explainer for apps, finance and education; the cursor and numbers are the stars",
    "retro-nostalgic": "Y2K, VHS or film-grain look with period-style music; trend lane, hedonic products"
  },
  "TONES": {
    "hushed": "whisper/ASMR register for self-care (RULES §3 whisper-flow); 150-160 wpm, delivery_key 'unhurried'",
    "curious": "investigative, question-led delivery for curiosity-gap hooks; 160-175 wpm"
  },
  "TRANSITIONS": ["hard-cut", "jump-cut", "match-cut", "whip-pan", "speed-ramp", "j-cut", "l-cut", "punch-in", "dissolve", "split-wipe", "none"],
  "MUSIC_LIBRARIES": ["tiktok-cml", "meta-sound-collection", "meta-ads-music", "yt-audio-library", "yt-shorts-audio-library", "original-owned", "licensed-third-party", "ai-generated-paid-plan"],
  "ACCOUNT_TYPES": ["personal", "creator", "business"],
  "LANES": ["organic", "shop", "ads"]
}
```

## 6. Sources

Links appear inline throughout. The `evidence` and `sources` keys used in the JSON blocks resolve as follows. `rules-*` keys point to RULES.md sections, and `xiao-2024` points to short-form-virality.md §2.

```json
{
  "tiktok-cbp": "https://ads.tiktok.com/help/article/creative-best-practices?lang=en",
  "meta-toluna-2025": "https://ppc.land/meta-and-toluna-study-finds-emojis-lift-reels-purchase-intent-2-5x/",
  "system1-tiktok": "https://system1group.com/creative-effectiveness-tiktok",
  "system1-grade-2026": "https://system1group.com/blog/colour-grading-is-not-just-a-finishing-touch",
  "li-xie-2020": "https://journals.sagepub.com/doi/abs/10.1177/0022243719881113",
  "visual-matters-2026": "https://arxiv.org/abs/2605.26309",
  "xiao-2024": "https://www.emerald.com/insight/content/doi/10.1108/INTR-07-2023-0521/full/html",
  "jtaer-2025-arousal": "https://www.mdpi.com/0718-1876/20/2/69/xml",
  "husain-2002": "https://online.ucpress.edu/mp/article-abstract/20/2/151/62120",
  "lowe-haws-2017": "https://journals.sagepub.com/doi/10.1509/jmr.14.0300",
  "jtr-2023-voice": "https://journals.sagepub.com/doi/10.1177/00472875231185882",
  "calm-tts-2023": "https://www.frontiersin.org/journals/communication/articles/10.3389/fcomm.2023.1089577/full",
  "vanzant-berger-2020": "https://pubmed.ncbi.nlm.nih.gov/31192632/",
  "vj-2024-intonation": "https://journals.sagepub.com/doi/full/10.1177/01461672241262180",
  "eisend-2009": "https://link.springer.com/article/10.1007/s11747-008-0096-y",
  "barta-2023": "https://zaguan.unizar.es/record/121367/files/texto_completo.pdf",
  "asmr-2025": "https://scispace.com/papers/testing-mechanisms-in-asmr-persuasion-advertising-consumers-kecgyjw4tu2f",
  "emac-2025-asmr": "https://proceedings.emac-online.org/pdfs/A2025-125653.pdf",
  "ijhci-2024": "https://www.tandfonline.com/doi/pdf/10.1080/10447318.2023.2288734",
  "tiktok-ad-policy": "https://ads.tiktok.com/help/article/tiktok-ads-policy-misleading-and-false-content",
  "tiktok-shop-2026": "https://ppc.land/tiktok-shops-quality-rules-ban-ai-voices-and-still-images-from-lives/",
  "tiktok-music-terms-2026": "https://www.tiktok.com/legal/page/global/music-terms-us/en",
  "tiktok-cml-terms": "https://www.tiktok.com/legal/page/global/commercial-music-library-user-terms/en",
  "tiktok-cml-help": "https://ads.tiktok.com/help/article/commercial-music-library?lang=en",
  "tiktok-promote-policy": "https://ads.tiktok.com/help/article/about-tiktok-advertising-policies-for-promote",
  "tiktok-ad-disclaimers": "https://ads.tiktok.com/help/article/about-ad-disclaimers-in-tiktok-ads-manager",
  "ig-music-guidelines-2020": "https://about.instagram.com/blog/announcements/updates-and-guidelines-for-including-music-in-video/",
  "ig-boost-2022": "https://business.instagram.com/blog/boost-instagram-reels/",
  "meta-reels-ads-music-2022": "https://www.digitalmusicnews.com/2022/10/05/meta-free-songs-catalog-advertisers-2022/",
  "meta-ai-labels": "https://about.fb.com/news/2024/04/metas-approach-to-labeling-ai-generated-content-and-manipulated-media/",
  "sriplaw-techtimes-2026": "https://www.techtimes.com/articles/321387/20260723/instagram-replace-audio-lets-you-swap-music-old-posts-without-losing-likes.htm",
  "contentgrip-2026": "https://www.contentgrip.com/meta-branded-content-rules-update/",
  "yt-3min-shorts": "https://support.google.com/youtube/answer/15424877?hl=en",
  "yt-music-eligibility": "https://support.google.com/youtube/answer/13486873?hl=en",
  "yt-upload-errors": "https://support.google.com/youtube/answer/10383400?hl=en-GB",
  "yt-audio-library": "https://support.google.com/youtube/answer/3376882?hl=en",
  "yt-ai-disclosure": "https://support.google.com/youtube/answer/14328491?hl=en",
  "gads-shorts-faq": "https://support.google.com/google-ads/answer/16041383?hl=en"
}
```

**Still UNVERIFIED:**
- the exact Instagram music matrix by account type
- whether TikTok's AI-voice ban covers recorded shoppable videos
- a Spark-specific music rule
- off-YouTube use of standard Audio Library tracks
- Meta's 2026 mandatory Partnership Ads rule
- whether Replace Audio covers Reels
- per-country results in Desmarais et al. 2025
- which TTS engine the pipeline will use

Content was rephrased for compliance with licensing restrictions.
