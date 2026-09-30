# Hooks deep-dive: archetypes, the hook stack, variants and an explainable hook score

Checked 2026-09-29. Builds on [short-form-virality.md](short-form-virality.md) (SFV §1, §4, §7) and [discovery-seo.md](discovery-seo.md) (keyword-in-hook, DISC-01/02, Trial Reels protocol) without restating them. All ids come from `vsp/creative_vocab.py`; proposed new ids are in §1.5 and §2.6.

Grades: **[P]** platform rule, policy or law · **[S]** strong (peer-reviewed, registered, or first-party at scale) · **[M]** moderate (large vendor dataset, method partly disclosed) · **[A]** anecdotal, practitioner or our own inference. **UNVERIFIED** = no primary source found.

## 0. Baseline and scope

| Script | Presenter | Family | Frame-0 overlay | Verbal hook | Note |
|---|---|---|---|---|---|
| electric-milk-frother | AI | negative-command | BUYING MILK FROTHERS | "Stop buying milk frothers on looks alone." (7w) | Strong: keyword by word 3, D144-clean. |
| silk-pillowcase | human | transformation | SILK PILLOWCASE | "The silk pillowcase after 7 days. Worth it?" (8w) | Question + day count; verdict payoff pairs (D35). |
| sugar-21 | human | challenge | SUGAR | "21 days without sugar." (4w) | Overlay too thin; no stakes word. |

Our template audit [A] (rendered with `milk frother` and 1–4-word slot fills, see §1.4) found:
- Only **33 of 49** current templates fit D73's 8 words. Contrarian-reframe fits **0/2**, identity-reveal 1/3 and story-time 2/4. Three of the eight families are therefore rarely or never drawable.
- At the template level, distinct-2 is 0.74. So the output distinct-2 of about 0.078 does not come from similar templates. It comes from a few surviving templates being drawn over and over with the same slot fills.
- 6 of 49 templates start with "I". For an AI presenter those are D137 hazards.

The fix is three things: families that fit D73 natively, 5+ templates for each of the 19 archetypes, and alternates that must change the archetype, the visual_type and the first three words (§3.4).

## 1. Archetype catalog

### 1.1 Measured evidence by tactic

- **Motion 2026 (Meta ads).** Sample: 578,750 creatives, 1 Sep 2025 – 1 Jan 2026. A tactic is listed only if 50+ accounts use it. Rankings use hit rate and are not ROAS-weighted ([Motion](https://motionapp.com/library/research/creative-benchmarks-2026/top-hook-tactics)). [M]
  - **Hit-rate rank (of 25), mapped to our ids:**

    | Our id | Motion tactic (rank) |
    |---|---|
    | newness | Newness (1), New Product Announcement (8), Product Announcement (24) |
    | price-anchor | Price Anchor (3) |
    | confession | Confession (9) |
    | curiosity-gap | Curiosity (11) |
    | bold-claim | Bold Claim (14), Shocking Statement (16) |
    | negative-command | Reverse Psychology (15), Warning (18) |
    | question / callout | If/Then (17), Direct Address (23) |
    | contrarian-reframe | Contrarian (20) |
    | pov | Relatability (21) |
    | comparison | Contrast (22) |
    | identity-reveal | Authority (25) |
    | proposed `offer` | Sale Announcement (2), Urgency (4), Announcement (5), Offer Only (6), FOMO (7), Exclusivity (10), Giveaway (12), Event Announcement (13) |

  - The 25 listed tactics hit 6–11%, against 4–8% tier averages. Wordplay (19th) has no id.
  - Motion's *promotional* cluster (a concrete reason to act now) is reliable; its *interrupt* cluster (Confession, Contrarian, Shocking, Reverse Psychology, Warning, Myth Busting, Bold Claim) wins less often but with higher variance. Motion warns that the Black Friday/Cyber Monday window inflates promotional tactics, while interrupt tactics should hold across seasons.
- **Motion visual formats** ([Motion](https://motionapp.com/library/research/creative-benchmarks-2026/top-visual-formats)) [M]: winner rates are Offer-First Banner 8.6%, Demo 8.1%, Testimonial 6.5%, Unboxing 9.8% and Celebrity 5.9%. The ordered list adds Before & After (6th), Split Screen (8th), Us vs Them (9th), Problem Agitation (15th) and POV (18th). It puts Unboxing 10th despite the table's top rate, so treat ranks as approximate.
- **OpusClip (organic TikTok)** [M]: 34,635 clips, Jan–Mar 2026, mean 7-day views per hook category, paid clips excluded.
  - Product/outcome showcase 6,037, about 2× Rare Event/Achievement at 2,983 ([OpusClip](https://www.opus.pro/research/how-to-go-viral-tiktok)).
  - Shock/Surprise 1,973 ([page](https://www.opus.pro/research/how-to-use-shock-surprise-hooks)); Direct Address/Intrigue/Question 1,768, below the TikTok median hook of 1,879 ([page](https://www.opus.pro/research/how-to-use-direct-address-intrigue-question-hooks); [benchmarks](https://www.opus.pro/research/engagement-benchmarks-tiktok)); "Visual Hooks" 632 ([page](https://www.opus.pro/research/how-to-use-visual-hooks)).
  - Caveats: means without variance, a proprietary taxonomy, and a 632 figure that contradicts OpusClip's own "2× the lowest" line.
  - Named underperformers: story-setup openers, greetings, "Okay so…" and "Have you ever wondered…" ([blog](https://www.opus.pro/blog/tiktok-hooks-that-go-viral-2026)) [A].
- **The first seconds (Meta).** [M]
  - Meta's Arun Srinivas (Sep 2026): under-25 average view time is below 2 s, and in reach campaigns the first 5 s of attention has 5× the impact of seconds 10–15 ([BW Marketing World](https://www.bwmarketingworld.com/article/reels-ads-deliver-24-higher-brand-lift-says-metas-arun-srinivas-545211)).
  - Older Facebook/Nielsen work: up to 47% of campaign value lands in the first 3 s ([Croud](https://croud.com/resources/how-to-grab-attention-in-five-seconds/)).
  - Fors Marsh research (reported by Facebook): feed content is recalled after 0.25 s ([Marketing Dive](https://www.marketingdive.com/news/facebook-why-mobile-video-ads-must-work-fast/446217/)).
- **TikTok Creative Codes** (SFV §1): product on screen early gives +65% brand affinity and +25% recall, and the proposition should land within 3–6 s [S]. Used here as evidence for showcase and product-in-action.
- **Buffer, Socialinsider, Metricool, Dash Hudson.** No hook-archetype data (searched 2026-09-29), only the baselines already in SFV §2. Instagram has no official skip-rate benchmark ([Metricool](https://metricool.com/instagram-reel-analytics/)). [M]

### 1.2 Academic evidence

- **Negativity.** In Upworthy A/B tests, each negative word raised CTR by 2.3% for an average-length headline, and positive words *lowered* it ([Robertson 2023](https://www.nature.com/articles/s41562-023-01538-4)). [S]
- **Pronouns, length, generality: [Gligorić 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC10038272/)** (registered report). [S]
  - Negative-emotion words: β 0.18. Positive words: not significant.
  - Longer headlines won (β 0.07). Readability: not significant.
  - Indefinite articles helped (β 0.12).
  - "I" (β 0.24) and third person (β 0.22) helped, "we" hurt (β −0.15), and "you" had no effect.
  - **Linguistic features picked the winning headline only 54% of the time, and under 60% even for the largest gaps** ([PLOS ONE](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0281682)). A text-only hook score is a weak ranker.
- **Sentence length.** About 8 words per sentence maximized engagement with social video ([Kim 2024](https://link.springer.com/article/10.1007/s10660-024-09926-2)). [M]
- **Information gap.** Curiosity rises when a specific, closable gap in knowledge becomes salient. The viewer needs enough context to know what is missing (Loewenstein, *Psychological Bulletin*, 1994). [S theory] So a gap needs a concrete noun ("the foam test") rather than "this".
- **Clickbait and questions: mixed to negative.** [M]
  - Question headlines drew more negative attitudes; forward references made no difference ([CME 2016](https://mediaengagement.org/research/clickbait-headlines/)).
  - Questions were mostly negative for interaction on 4,400 Facebook posts (half not significant), and lowered CTR in Kuiken 2017 ([Jung 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC9242456/)).
  - Self-referencing questions beat declaratives, with rhetorical questions last ([Lai & Farbrot 2014](https://www.researchgate.net/publication/271992279_What_makes_you_click_The_effect_of_question_headlines_on_readership_in_computer-mediated_communication)).
  - Forward references capture involuntary attention faster in an ERP study ([2022](https://www.researchgate.net/publication/366652381_Attention_Grabbing_through_Forward_Reference_An_ERP_Study_on_Clickbait_and_Top_News_Stories)). Clickbait did not change trust or learning ([Munger et al.](https://csmapnyu.org/research/academic-research/the-null-effects-of-clickbait-headlines-on-polarization-trust-and-learning)).
  - **Encodable conclusion:** a question is neutral at best. Allow it only when it is specific, answerable, and names the product or category.

### 1.3 Policy risk

- **Meta.** [P]
  - Facebook demotes clickbait links that withhold information, use sensational phrasing ("You won't believe…", "You'll never guess…") or lean on all caps and "!!!" ([Meta](https://transparency.meta.com/en-gb/features/approach-to-ranking/content-distribution-guidelines/clickbait-links)). Engagement bait and Instagram recommendation eligibility are covered in SFV §3 and D139.
  - Meta's Prohibited Commercial Practices policy covers deceptive pricing and unauthorized endorsements ([Meta](https://transparency.meta.com/policies/ad-standards/fraud-scams/unacceptable-business-practices)).
  - The Llama Acceptable Use Policy (AUP) bans spam, fake engagement and fake reviews, and presenting outputs as human-generated ([Llama 4 AUP](https://github.com/meta-llama/llama-models/blob/main/models/llama4/USE_POLICY.md)).
  - The phrase "manipulative techniques" does **not** appear in that AUP (UNVERIFIED as a Meta rule). The closest legal text is EU AI Act Art. 5(1)(a), which bans AI systems that use purposefully manipulative or deceptive techniques.
- **TikTok.** [P]
  - The ad policy (updated Apr 2026) bans promised or exaggerated results, absolute terms about time, region or brand, before/after comparisons without evidence, inconsistent price details, and visual tactics that manipulate engagement such as fake play or close buttons ([TikTok](https://ads.tiktok.com/help/article/tiktok-ads-policy-misleading-and-false-content)).
  - The 2026-H2 Community Guidelines keep reused or minimally edited content and extreme dieting/fitness content out of the For You feed (FYF), and ban fake engagement and fake reviews ([TikTok](https://www.tiktok.com/community-guidelines/en/fyf-standards)). The dieting rule matters for challenge hooks.
- **YouTube.** Since Dec 2024 (India first) it removes "egregious clickbait", meaning videos whose title or thumbnail promises something the video doesn't deliver ([Google](https://blog.google/intl/en-in/products/platforms/strengthening-enforcement-against-egregious-clickbait-on-youtube/)). [P] This is D35 as a platform rule.
- **FTC.** [P]
  - Its dark-pattern taxonomy lists false low-stock and high-demand messages, baseless countdown timers, false limited-time offers and fake discounts ([FTC 2022](https://www.ftc.gov/system/files/ftc_gov/pdf/P214800%20Dark%20Patterns%20Report%209.14.2022%20-%20FINAL.pdf)).
  - Objective claims need a reasonable basis ([FTC substantiation](https://www.ftc.gov/legal-library/browse/ftc-policy-statement-regarding-advertising-substantiation)).
  - A limit on how long "new" may be claimed (often cited as 6 months) is UNVERIFIED.

### 1.4 ARCHETYPES (json)

**How to read the block.**
- `prior` is our composite research prior (0–1) for organic product short-form. It is [A] and must be recalibrated (§4.2).
- `variance` follows Motion's clusters.
- `human_only` lists templates the maker must drop when presenter=ai (D137).
- Templates use only the allowed slots. `{price}` appears only in price-anchor and `{proof}` only in proof-first. `{price}` renders with its currency symbol ("$25"); the current maker writes `${price}`.

**Budget check.** All 115 templates were machine-checked: each renders to ≤8 words with the slot fills below. Longer fills must pass the existing D73 post-render filter.

```json
{"TEMPLATE_SLOT_BUDGET": {"product": "milk frother", "category": "milk frother", "category_pl": "milk frothers", "expensive": "espresso machine", "common": "the microwave method", "flaw": "weak foam", "mistake": "frothing cold milk", "moment": "morning rush", "ndays": "7", "timespan": "30 seconds", "before": "flat milk", "after": "silky foam", "identity": "home barista", "persona_note": "an AI persona", "price": "$25", "proof": "a 4.6 rating", "situation": "making morning lattes", "thing": "morning coffee"}}
```

```json
{
  "curiosity-gap": {
    "definition": "Names a specific unknown about the product that the payoff reveals on screen.",
    "mechanism": "Information-gap curiosity (Loewenstein 1994): a salient, closable gap motivates watching; forward reference speeds involuntary attention (ERP 2022).",
    "evidence": "Motion Curiosity 11th of 25 by hit rate [M]; OpusClip Direct Address/Intrigue/Question 1,768 mean views vs 1,879 TikTok median [M]; forward-reference headlines no worse than plain ones (CME 2016) [M]; vague withholding demoted by Meta, unpaid promises removed by YouTube [P].",
    "prior": 0.55, "variance": "med",
    "when": "demo, review, showcase: a concrete non-obvious detail is shown before 85% of runtime",
    "avoid_when": "payoff cannot name the hidden thing (D35); secret/industry framing; gap refers to 'this/it' with no noun",
    "risk": "medium: clickbait demotion if vague or unpaid",
    "ai_safe": true,
    "requires": ["a concrete detail the payoff shows (D35)"],
    "templates": [
      "The {product} detail worth checking first.",
      "Before you buy a {category}, check this.",
      "One {product} detail decides the verdict.",
      "What {ndays} days revealed about the {product}.",
      "Watch the {product} at the {moment}.",
      "Here's where {category_pl} hide the {flaw}."
    ],
    "human_only": []
  },
  "bold-claim": {
    "definition": "A specific, checkable performance claim the video proves in one take.",
    "mechanism": "Expectancy violation plus commitment: a falsifiable claim invites the viewer to verify it.",
    "evidence": "Motion Bold Claim 14th, Shocking Statement 16th; interrupt cluster, higher variance [M]; FTC requires a reasonable basis for objective claims; TikTok bans exaggerated results and absolutes (Apr 2026) [P].",
    "prior": 0.55, "variance": "high",
    "when": "demo formats with a measurable (time, count, before/after) captured on camera",
    "avoid_when": "superlatives (best, #1, only); health or efficacy; 'obsolete'; comparisons not filmed (D141)",
    "risk": "high: absolute or unsubstantiated claim class (D141)",
    "ai_safe": true,
    "requires": ["on-screen measurement or one-take demo proving the claim (D5)"],
    "templates": [
      "This {product} gets {after} in seconds.",
      "Under a minute: {before} to {after}.",
      "{product}, day {ndays}: still no {flaw}.",
      "{ndays} days, zero {flaw}: {product}.",
      "The {product} fixes {before}. Watch.",
      "{after} from a {category}, one take.",
      "My {expensive} lost to a {product}."
    ],
    "human_only": ["My {expensive} lost to a {product}."]
  },
  "negative-command": {
    "definition": "Tells the viewer to stop one specific mistake; the payoff shows the fix.",
    "mechanism": "Negativity bias and loss framing; the imperative interrupts passive scrolling.",
    "evidence": "Each negative word +2.3% CTR (Robertson 2023); negative-emotion words beta 0.18 (Gligoric 2023) [S]; Motion Reverse Psychology 15th, Warning 18th [M]; OpusClip calls imperatives the most divisive pattern [A].",
    "prior": 0.6, "variance": "med",
    "when": "advice, tools, kitchen, beauty: a real common mistake with a visible fix",
    "avoid_when": "no concrete mistake; shaming; health scares; 'stop scrolling' attention bait",
    "risk": "medium: sensational if the mistake is invented",
    "ai_safe": true,
    "requires": ["a real {mistake} and its fix on screen"],
    "templates": [
      "Stop {mistake}.",
      "Stop buying {category_pl} on looks alone.",
      "Don't buy a {category} before checking this.",
      "Skip this {category} mistake: {mistake}.",
      "Quit {mistake}. Do this instead.",
      "{product} owners: stop {mistake}."
    ],
    "human_only": []
  },
  "proof-first": {
    "definition": "Opens on sourced evidence (rating, measurement, result card) before any claim.",
    "mechanism": "Credibility heuristic: evidence first lowers skepticism for the rest of the video.",
    "evidence": "Motion Testimonial format 6.5% winner rate, Statistic format listed [M]; OpusClip specific-number pattern [A]; FTC 16 CFR 465 and D136 ban unsourced ratings and counts [P].",
    "prior": 0.65, "variance": "med",
    "when": "the prompt supplies proof with its source",
    "avoid_when": "proof not in the prompt (D136); AI presenter framing proof as personal experience (D137)",
    "risk": "high if unsourced: fabricated review signal",
    "ai_safe": true,
    "requires": ["proof in the prompt, attributed (D136)"],
    "templates": [
      "Proof first: {proof}.",
      "Start with the numbers: {proof}.",
      "{proof}. Now watch the {product}.",
      "{proof}. Here's what that means.",
      "The {product} scorecard: {proof}.",
      "Here's the receipt: {proof}."
    ],
    "human_only": []
  },
  "transformation": {
    "definition": "Before and after of the same object, with the product as the cause.",
    "mechanism": "Visual contrast and closure: the gap between the two states is the promise.",
    "evidence": "Motion Before & After 6th of 25 formats [M]; OpusClip showcase class includes before/after (6,037) [M]; TikTok bans misleading before/after and unsupported transformation claims [P].",
    "prior": 0.7, "variance": "med",
    "when": "honest matched-framing results on objects: cleaning, cooking, organizing, car care",
    "avoid_when": "body, skin, weight or health results; staged timelines; AI-generated results",
    "risk": "medium-high: misleading before/after is an ad-rejection class",
    "ai_safe": true,
    "requires": ["real matched before/after footage", "dates if multi-day"],
    "templates": [
      "{before} to {after}: the {product}.",
      "Day 1 vs day {ndays}: {product}.",
      "Same {thing}, {before} vs {after}.",
      "This is the after. Here's the before.",
      "The {product} after {ndays} days.",
      "{after} in {timespan}. Here's the before."
    ],
    "human_only": []
  },
  "story-time": {
    "definition": "Opens mid-story with the conflict already stated.",
    "mechanism": "Narrative transportation: an unresolved conflict pulls toward the resolution.",
    "evidence": "OpusClip: story-setup openers underperform [A/M]; Motion Storytelling only on the spend-use list [M]; first-person singular helps headlines (beta 0.24) [S].",
    "prior": 0.35, "variance": "high",
    "when": "human presenter; vlog, challenge, routine; conflict in the first line",
    "avoid_when": "AI presenter (D137); slow setup; the story is not true",
    "risk": "low policy, high performance risk",
    "ai_safe": false,
    "requires": ["presenter=human", "a true lived experience"],
    "templates": [
      "So I almost returned the {product}.",
      "Why I kept the {product}.",
      "Day {ndays} and I almost quit.",
      "So I'm {situation} when this happens.",
      "I didn't expect the {product} to win.",
      "Quick story about my {expensive}."
    ],
    "human_only": ["*"]
  },
  "contrarian-reframe": {
    "definition": "Rejects a common practice and promises a better one, shown on screen.",
    "mechanism": "Schema violation: viewers stay to resolve the contradiction.",
    "evidence": "Motion Contrarian 20th, Myth Busting on the spend list; interrupt cluster, high variance [M]; OpusClip lists the contrarian open and warns against crying wolf [A]; current templates fit D73 0/2.",
    "prior": 0.5, "variance": "high",
    "when": "advice or education with a widespread practice and a demonstrable alternative",
    "avoid_when": "strawman beliefs; health myths; value claims without a comparison",
    "risk": "medium: misleading if the alternative is not shown",
    "ai_safe": true,
    "requires": ["a real {common} practice", "the alternative shown"],
    "templates": [
      "{common} is overrated. Here's why.",
      "Unpopular opinion: skip {common}.",
      "{common} causes the {flaw}.",
      "Skip the {expensive}. Get {after} anyway.",
      "The {category} advice worth ignoring.",
      "{common}? Wrong fix. Try this."
    ],
    "human_only": []
  },
  "identity-reveal": {
    "definition": "Leads with who is speaking: a real credential or role, or the AI disclosure itself.",
    "mechanism": "Source credibility and in-group identity; disclosure pre-empts distrust.",
    "evidence": "Motion Authority 25th, Founder 20th and Expert Explained 25th formats [M]; OpusClip expert-explainer is the most common storyline (2,626 clips) [M]; 'I' helps headlines (beta 0.24) [S]; FTC bans fake testimonialists (16 CFR 465.2) [P].",
    "prior": 0.45, "variance": "med",
    "when": "human with a verified relevant identity; AI only as a disclosure-first opener",
    "avoid_when": "unverifiable credentials; AI claiming a human identity (D137; Llama AUP)",
    "risk": "high if the identity is fabricated",
    "ai_safe": "partial",
    "requires": ["identity from the prompt (human) or {persona_note} (AI)"],
    "templates": [
      "Full disclosure: I'm {persona_note}.",
      "AI host, real footage: the {product}.",
      "AI host here. Real {product} test.",
      "As a {identity}, I'd skip this.",
      "{identity} here. Honest {product} verdict.",
      "A {identity} tests the {product}."
    ],
    "human_only": ["As a {identity}, I'd skip this.", "{identity} here. Honest {product} verdict.", "A {identity} tests the {product}."]
  },
  "problem-agitate": {
    "definition": "Names the viewer's problem vividly before the product appears.",
    "mechanism": "Problem salience plus negativity; self-relevance holds the viewer for the fix.",
    "evidence": "Motion Problem Agitation format 15th [M]; negativity lifts CTR (Robertson; Gligoric) [S]; problem-to-solution is the standard explainer template (Jasper) [A].",
    "prior": 0.6, "variance": "med",
    "when": "utilitarian products with a visible, common frustration",
    "avoid_when": "medical conditions, body image, fear appeals; problem not shown",
    "risk": "medium: sensational if exaggerated",
    "ai_safe": true,
    "requires": ["the {flaw} visible in frame 0 (problem-state)"],
    "templates": [
      "{flaw} again? It's not your fault.",
      "Tired of {flaw} every {moment}?",
      "{flaw} ruins your {thing}. Here's why.",
      "Why {category_pl} give you {flaw}.",
      "{situation} and still getting {flaw}?",
      "The {flaw} problem, fixed in {timespan}."
    ],
    "human_only": []
  },
  "question": {
    "definition": "Asks the specific question a viewer would search; the payoff answers it explicitly.",
    "mechanism": "Self-reference and search intent; an answerable question sets up an expected answer.",
    "evidence": "Mixed [M]: self-referencing questions beat declaratives (Lai & Farbrot 2014); questions lowered CTR or attitudes (Kuiken 2017; CME 2016; Jung 2022); OpusClip question class below median; Motion If/Then 17th, Direct Address 23rd.",
    "prior": 0.4, "variance": "med",
    "when": "'worth it', 'X vs Y', 'does it work' intents; verdict payoffs; keyword first (DISC-01)",
    "avoid_when": "rhetorical or vague questions; questions answerable 'no' instantly; health questions",
    "risk": "low",
    "ai_safe": true,
    "requires": ["a payoff that answers the question in words and on screen"],
    "templates": [
      "Is the {product} actually worth it?",
      "{product}: buy or skip?",
      "Does the {product} fix {flaw}?",
      "Why does your {thing} get {flaw}?",
      "How long does {after} really take?",
      "{product} or {expensive}: which wins?"
    ],
    "human_only": []
  },
  "comparison": {
    "definition": "The product against its alternative on one filmed test.",
    "mechanism": "Contrast supports the decision; the winner is the payoff.",
    "evidence": "Motion Split Screen 8th, Us vs Them 9th formats; Contrast tactic 22nd [M]; TikTok allows comparative claims only with evidence [P].",
    "prior": 0.65, "variance": "med",
    "when": "a pricier, DIY or older alternative exists and both can be filmed",
    "avoid_when": "named competitor brands with claims; rigged setups",
    "risk": "medium: comparative claim needs evidence",
    "ai_safe": true,
    "requires": ["real footage of both on the same test"],
    "templates": [
      "{product} vs {expensive}: same {after}?",
      "{common} vs the {product}.",
      "Left: {before}. Right: {product}.",
      "Same {thing}, two methods. One wins.",
      "{expensive} or {product}? Side by side.",
      "One {category} test, two results."
    ],
    "human_only": []
  },
  "pov": {
    "definition": "Puts the viewer inside a concrete scenario with 'POV:'.",
    "mechanism": "Self-projection and relatability: second person without asking a question.",
    "evidence": "Motion POV format 18th, Relatability tactic 21st [M]; internal pack lists pov among top families [A]; RULES saturation note on repeated 'POV: your {domain}...' [A].",
    "prior": 0.5, "variance": "med",
    "when": "routines, lifestyle, relatable moments; pairs with pov-hands",
    "avoid_when": "POV as a bare label; the same POV frame across a series",
    "risk": "low",
    "ai_safe": true,
    "requires": ["the scenario is what the footage shows"],
    "templates": [
      "POV: your {thing} finally has {after}.",
      "POV: it's {moment} and {flaw} again.",
      "POV: you stopped {mistake}.",
      "POV: you finally tried a {category}.",
      "POV: {situation} with a {product}.",
      "POV: your {expensive} just got replaced."
    ],
    "human_only": []
  },
  "newness": {
    "definition": "Frames the product, version or use as new, or as a first look.",
    "mechanism": "Novelty seeking: 'new' signals information the viewer lacks.",
    "evidence": "Motion Newness 1st and New Product Announcement 8th by hit rate, inflated by the promo window [M].",
    "prior": 0.65, "variance": "low",
    "when": "the prompt states a launch, new version or new use; otherwise only 'first look' templates",
    "avoid_when": "product is not new; launch urgency that is not real",
    "risk": "medium: false newness claim",
    "ai_safe": true,
    "requires": ["a newness fact in the prompt for templates containing 'new'"],
    "templates": [
      "First look: the {product}.",
      "First look at the {product} in action.",
      "New {category} just dropped. First look.",
      "The new {product} changes the {moment}.",
      "New find: a {category} for {after}.",
      "{product}, new version: what changed?"
    ],
    "human_only": []
  },
  "confession": {
    "definition": "Admits a real mistake or bias before showing what changed.",
    "mechanism": "Vulnerability and the pratfall effect: admitted fault raises credibility.",
    "evidence": "Motion Confession 9th by hit rate and over-indexes on spend; interrupt cluster, high variance [M]; 'I' helps headlines (beta 0.24) [S].",
    "prior": 0.6, "variance": "high",
    "when": "human presenter; beauty, wellness, lifestyle, money; confession tied to the payoff",
    "avoid_when": "AI presenter (D137); invented confessions (FTC 465); health overshare",
    "risk": "medium: fake testimony if invented",
    "ai_safe": false,
    "requires": ["presenter=human", "a true confession"],
    "templates": [
      "Confession: I was {mistake} for years.",
      "I almost didn't post this {product} test.",
      "Honestly? I misjudged the {product}.",
      "I wasted money on {common}.",
      "Embarrassing, but I was {mistake}.",
      "I was wrong about the {product}."
    ],
    "human_only": ["*"]
  },
  "price-anchor": {
    "definition": "States the supplied price against a pricier alternative or an outcome.",
    "mechanism": "Anchoring and value contrast.",
    "evidence": "Motion Price Anchor 3rd by hit rate, 2nd by spend use [M]; FTC lists fake discounts as a dark pattern; TikTok bans inconsistent price details [P]; D37.",
    "prior": 0.7, "variance": "low",
    "when": "the prompt gives a price; dupes and value reviews",
    "avoid_when": "no price in the prompt (D37); was/now without a real prior price; 'cheapest'",
    "risk": "high if the price is invented or the discount fake",
    "ai_safe": true,
    "requires": ["price in the prompt (D37)"],
    "templates": [
      "{price} for {after}? Let's test it.",
      "This {product} is {price}. Worth it?",
      "{price} {product} vs the {expensive}.",
      "At {price}: the {product} verdict.",
      "What {price} gets you in a {category}.",
      "{price} {product}, {expensive} results?"
    ],
    "human_only": []
  },
  "listicle": {
    "definition": "Promises a counted set and delivers exactly that count.",
    "mechanism": "Structure and progress: a count sets a closable expectation.",
    "evidence": "Motion Listicle format 7th, Reasons Why on the spend list [M]; OpusClip specific-number pattern [A].",
    "prior": 0.55, "variance": "low",
    "when": "advice, checks, roundups and showcases (D92)",
    "avoid_when": "beats do not deliver the stated count; padding",
    "risk": "low",
    "ai_safe": true,
    "requires": ["beats deliver exactly the stated count", "'tested' templates need that many real products"],
    "templates": [
      "3 {category} checks before you buy.",
      "3 ways to get {after} faster.",
      "3 {category} mistakes behind {flaw}.",
      "{product}: 3 things the box skips.",
      "3 {category_pl} tested, 1 kept.",
      "2 {product} settings, 2 results."
    ],
    "human_only": []
  },
  "challenge": {
    "definition": "A time-boxed personal test stated as the hook: streak, quit, only-X.",
    "mechanism": "Stakes and completion curiosity: will it last?",
    "evidence": "OpusClip Rare Event/Achievement 2,983 mean views, 2nd named class [M]; D52 pins challenge hooks to the day count; TikTok keeps extreme dieting and fitness out of the FYF [P].",
    "prior": 0.55, "variance": "med",
    "when": "human creator; habits, food, fitness, digital detox; dated footage",
    "avoid_when": "dangerous or extreme diet challenges; AI presenter doing the challenge",
    "risk": "medium: FYF ineligibility or dangerous-acts policy",
    "ai_safe": "partial",
    "requires": ["presenter=human, or a licensed creator log narrated in curator framing (D39)"],
    "templates": [
      "{ndays} days of {situation}. Day 1.",
      "Day {ndays} of {situation}.",
      "I tried {situation} for {ndays} days.",
      "Can I last {ndays} days {situation}?",
      "One creator, {ndays} days of {situation}.",
      "{ndays} days, one rule: {situation}."
    ],
    "human_only": ["{ndays} days of {situation}. Day 1.", "Day {ndays} of {situation}.", "I tried {situation} for {ndays} days.", "Can I last {ndays} days {situation}?"]
  },
  "day-counter": {
    "definition": "Opens on a day-N marker from an ongoing, dated log.",
    "mechanism": "Progress cue plus accumulated proof: the number implies commitment.",
    "evidence": "D52 pinned day-counter hooks [A]; OpusClip Rare Event/Achievement 2,983 [M]; specific numbers imply measurement [A].",
    "prior": 0.55, "variance": "med",
    "when": "routines, challenges, long-term product tests with dated footage",
    "avoid_when": "no real log; hook day differs from payoff day (D5 drift)",
    "risk": "low-medium: D5 drift",
    "ai_safe": "partial",
    "requires": ["a dated log; hook day equals payoff day (D52)"],
    "templates": [
      "Day 1 vs day {ndays}.",
      "Day {ndays} of {ndays}: the verdict.",
      "{product} log, day {ndays}.",
      "Day {ndays}. The {flaw} is gone.",
      "Day {ndays}: {situation}, still going.",
      "Day {ndays} with the {product}."
    ],
    "human_only": ["Day {ndays}: {situation}, still going.", "Day {ndays} with the {product}."]
  },
  "showcase": {
    "definition": "Shows the product working, or the finished outcome, before any explanation.",
    "mechanism": "Immediate value preview: no setup stands between the viewer and the payoff image.",
    "evidence": "OpusClip Product/Outcome Showcase top class, 6,037 mean views [M]; product on screen early +65% brand affinity (Creative Codes, SFV) [S]; Motion Demo 8.1%, Unboxing 9.8% [M]; TikTok Shop wants the hook about the product [P].",
    "prior": 0.85, "variance": "low",
    "when": "any visually demonstrable product; roundups; room, car or desk showcases (D81)",
    "avoid_when": "static product shots (TikTok Shop non-interactive cap); nothing moves in frame 0",
    "risk": "low",
    "ai_safe": true,
    "requires": ["real footage of the product working"],
    "templates": [
      "This is the {product} in action.",
      "Watch the {product} make {after}.",
      "{after}, made by a {product}.",
      "The {product}, start to finish.",
      "Here's the {product} doing its job.",
      "{product} at the {moment}, no cuts."
    ],
    "human_only": []
  }
}
```

`"human_only": ["*"]` means every template.

### 1.5 Proposed archetype additions

New ids to add to `HOOK_ARCHETYPES` (never rename existing ones):
- **`offer`** (`requires_offer`, D158): Motion's promotional cluster (Sale Announcement, Urgency, Offer Only, FOMO, Exclusivity, Giveaway; all in the top 12) [M]. Valid only with a real offer and deadline from the prompt, since fake timers and limited-time claims are FTC dark patterns [P]. Needs new slots, e.g. "{offer} on the {product}, ends {deadline}."
- **`callout`**: an if/then self-reference such as "If you get {flaw}, try this." It covers Motion's If/Then (17th) and Lai & Farbrot's self-reference effect, as second person without a question [M].
- **`mechanism-reveal`**: a third-person how-it-works line such as "How the {product} makes {after}." It follows OpusClip's most common storyline (expert explainer), its 77.8% third-person share, and Gligorić's third-person β 0.22. AI-safe by construction [M].
- **`measured-number`**: a number produced on camera, such as "{measure}: the {product}, on camera." Because the number comes from the video, D136 is not triggered. Needs a `{measure}` slot [A].

Myth Busting stays inside contrarian-reframe; Reverse Psychology and Warning stay inside negative-command.

## 2. The hook stack

### 2.1 Visual hook (frame 0)

- **Lead with the thing, already moving.** Both 2026 datasets reward openings that show the product or outcome first: OpusClip's showcase class, and Motion's Demo (8.1%) and Unboxing (9.8%) formats [M]. With recall after 0.25 s and under-25 view time below 2 s, the object and its motion belong in the first 0.5 s [M]; the exact 0.5 s figure is a heuristic [A].
- **Faces.** A visible human lifts CTR, and faces predict views better than text sentiment (SFV §1, §7) [S/M]. For an AI presenter, a delighted reaction to a result implies use (D137), so keep AI expressions neutral and let the product carry frame 0.
- **Before/after and results** are strong (Motion's Before & After is 6th, Split Screen 8th) but must be real matched captures. A generated result is a fabricated claim under TikTok's misleading before/after rule [P], hence the high `ai_render_risk`.
- **Text-first** is the safest type to render, because the text is composited in post, never drawn by the model (D64 garbled-text risk). Motion's Headline format ranks 4th [M].

### 2.2 Text hook

- **Length: a ≤3-word key phrase, not a transcript** [S]. Printed text that duplicates narration hurts learning (16/16 tests, median d 0.86), but short redundant key phrases *improved* retention (d 0.47 and 0.70) ([Mayer & Johnson 2008](https://www.researchgate.net/publication/232540768_Revising_the_Redundancy_Principle_in_Multimedia_Learning); [Yue, Bjork & Bjork 2013](https://sites.lifesci.ucla.edu/psych-bjorklab/wp-content/uploads/sites/13/2016/07/YueBjorkBjork2013_redundancy.pdf)). D144's contiguous-phrase-or-label rule is the right design.
- **Meaning.** The overlay carries the keyword's head noun (DISC-02) and never adds a claim the voice doesn't make; TikTok Shop requires text that matches speech (SFV §3) [P].
- **Placement and duration.** Inside x 120–888, y 288–1248, clear of the caption band and the AI label (D138). On screen from 0.0 s until the spoken hook ends (≥3.0 s, D142), and never under max(0.83 s, characters ÷ 20).
- **Style.** Caps are fine; "!!!" and all-caps sentences are Meta clickbait signals [P, by analogy].

### 2.3 Verbal hook

- **Timing.** The first word starts by 0.3 s. At the gate's 3.0 words per second (`lexicon.WPS_BRISK`), word 3 ends at about 1.3 s, inside the under-2 s under-25 view time. **So the payload goes in words 1–3**: product or category, flaw, or number [M/A]. That also puts the keyword well before DISC-01's 3.0 s.
- **Length.** ≤8 words (D73), matching Kim's roughly 8 words per sentence [M]. Gligorić's longer-wins result comes from typed headlines; don't carry it over to timed speech [S, caveat].
- **Words** [S]. One concrete negative word (stop, mistake, weak, ruins, fail) helps; positive hype doesn't (Robertson). "I" helps but is human-only (D137); "you" is neutral; "we" hurts; third person helps. Concrete nouns and numbers make the gap closable (Loewenstein).

### 2.4 Audio hook

- **Sound from frame 0.** 73% of Kantar respondents said they'd stop and look at TikTok ads with audio ([TikTok/Kantar](https://ads.tiktok.com/business/en/blog/kantar-report-how-brands-are-making-noise-and-driving-impact-with-sound-on-tiktok)) [M, self-report]; music plus voice-over helps on Meta (SFV).
- **Real product sound as the cue.** ASMR or whispered audio raised ad recall across four experiments ([JAR 2022](https://www.journalofadvertisingresearch.com/content/early/2022/07/28/jar-2022-016)) [S]. Sound presence raised engagement, and voice-over with hedonic products raised emotion ([ECR 2024](https://link.springer.com/10.1007/s10660-024-09902-w)) [M]. This favors satisfying-macro and product-in-action openings with the frother's own whirr.
- **Music.** Custom music beat recognizable tracks on recall ([MediaScience via TikTok](https://ads.tiktok.com/business/vi/blog/roundup-how-to-use-power-of-sound-tiktok)) [M]; TikTok Shop allows library music only (SFV) [P].
- **"Music drop" and "silence break" openers**: no primary evidence (UNVERIFIED, [A]). Use them only as variant levers, never as defaults.

### 2.5 Alignment and best pairings

**One promise, four layers, and a timeline:**
1. At 0.0 s the overlay (≤3 words, containing the keyword) and the visual event are both present, with motion or a reveal by 0.5 s.
2. The voice starts by 0.3 s and names the noun by word 3.
3. The sound at frame 0 is the product's real sound, or voice over a bed.
4. The overlay stays until the spoken hook ends.

If any layer promises something the payoff doesn't deliver, the hook fails D35.

Pairings below are our inference from Motion's format and tactic lists [A]. No public archetype × format matrix exists.

| Archetype | Best visual_type (in order) |
|---|---|
| showcase | product-in-action, satisfying-macro, pov-hands |
| transformation / day-counter | before-after-split, result-reveal, day-counter |
| comparison / price-anchor | comparison, text-first, unboxing |
| problem-agitate / negative-command | problem-state, product-in-action, text-first |
| curiosity-gap / bold-claim | satisfying-macro, result-reveal, product-in-action |
| proof-first / question / listicle / contrarian-reframe | text-first, comparison |
| pov | pov-hands, problem-state |
| newness | unboxing, product-in-action |
| identity-reveal / confession / story-time (human) | face-reaction, problem-state |
| challenge | day-counter, problem-state |

### 2.6 VISUAL_HOOKS (json)

`prior` is a composite [A] used by the score's visual-type feature (§4).

```json
{
  "product-in-action": {
    "evidence": "Motion Demo format 8.1% winner rate, 2nd [M]; OpusClip showcase class top at 6,037 mean views [M]; product on screen early +65% affinity, +25% recall (Creative Codes) [S]; TikTok Shop wants >=3 s dynamic footage and a product-led hook [P].",
    "prior": 0.85,
    "best_archetypes": ["showcase", "bold-claim", "negative-command", "curiosity-gap", "newness"],
    "needs": "the product mid-task with hands in frame and visible motion by 0.5 s; the real product sound",
    "ai_render_risk": "medium: hand and finger artifacts, liquid physics, invented logos (D64 negative prompt)"
  },
  "result-reveal": {
    "evidence": "OpusClip: leading with the outcome is the top pattern [M]; Motion Before & After 6th [M]; TikTok bans results that give a false impression [P].",
    "prior": 0.8,
    "best_archetypes": ["showcase", "transformation", "bold-claim", "proof-first"],
    "needs": "a real captured result that the payoff re-shows in context",
    "ai_render_risk": "high: a generated result is a fabricated claim; use real capture only"
  },
  "before-after-split": {
    "evidence": "Motion Before & After 6th, Split Screen 8th [M]; TikTok ad policy restricts before/after without evidence; TikTok Shop bans unsupported transformations [P].",
    "prior": 0.7,
    "best_archetypes": ["transformation", "comparison", "day-counter"],
    "needs": "matched framing, light and angle; dated captures; label pair 'BEFORE | AFTER' (D144)",
    "ai_render_risk": "high: never generate either side; composite real footage"
  },
  "problem-state": {
    "evidence": "Motion Problem Agitation 15th [M]; negativity lifts clicks (Robertson 2023; Gligoric 2023) [S, text-to-visual inference].",
    "prior": 0.6,
    "best_archetypes": ["problem-agitate", "negative-command", "question", "pov", "challenge"],
    "needs": "the problem at its worst, honestly depicted; the product enters by about 3 s",
    "ai_render_risk": "low-medium: staged mess reads fine; avoid depicting injury or health symptoms"
  },
  "pov-hands": {
    "evidence": "Motion POV format 18th [M]; hands-on-product openers are practitioner consensus [A].",
    "prior": 0.6,
    "best_archetypes": ["pov", "showcase", "listicle"],
    "needs": "first-person angle, the viewer's hands using the product, motion by 0.5 s",
    "ai_render_risk": "medium-high: hands are the most common generation artifact"
  },
  "face-reaction": {
    "evidence": "Visible human +27% CTR (Meta, SFV) [S]; faces predict TikTok views better than text sentiment (163k videos, SFV section 7) [M]; Motion Testimonial 6.5% [M].",
    "prior": 0.6,
    "best_archetypes": ["confession", "story-time", "identity-reveal", "problem-agitate"],
    "needs": "presenter face with the product or result in the same frame; human presenter for emotional reactions",
    "ai_render_risk": "high: an AI face reacting to a result implies use (D137); keep AI expressions neutral and disclosed (D138)"
  },
  "text-first": {
    "evidence": "Motion Headline format 4th [M]; TikTok search ads recommend a keyword text hook [P]; text stickers +11 points (Meta, SFV) [S]; brief key-phrase labels aid retention (Mayer & Johnson 2008) [S].",
    "prior": 0.55,
    "best_archetypes": ["question", "listicle", "proof-first", "contrarian-reframe", "price-anchor", "identity-reveal"],
    "needs": "a <=3-word card over MOTION (never a static card, per TikTok Shop's non-interactive rule), keyword head noun included",
    "ai_render_risk": "low: composite the text in post, never ask the model to draw it"
  },
  "unboxing": {
    "evidence": "Motion Unboxing 9.8% winner rate, highest in its table, but only 2.1% of creatives [M].",
    "prior": 0.75,
    "best_archetypes": ["newness", "showcase", "price-anchor"],
    "needs": "a real package opened mid-action; packaging branding must be real, not invented (D37/D64)",
    "ai_render_risk": "medium: garbled packaging text and invented brands"
  },
  "comparison": {
    "evidence": "Motion Us vs Them 9th, Split Screen 8th, Contrast tactic 22nd [M]; TikTok allows comparative claims only with evidence [P].",
    "prior": 0.65,
    "best_archetypes": ["comparison", "price-anchor", "contrarian-reframe", "question"],
    "needs": "both items filmed on the same test, same framing; no named-competitor claims",
    "ai_render_risk": "medium: both sides must be real captures when the outcome is the claim"
  },
  "day-counter": {
    "evidence": "D52 pinned day-counter hooks [A]; OpusClip Rare Event/Achievement class 2,983 [M].",
    "prior": 0.5,
    "best_archetypes": ["day-counter", "challenge", "transformation"],
    "needs": "a 'DAY N' label over real footage from that day; the hook's N equals the payoff's N",
    "ai_render_risk": "low for the label; lived-experience risk if an AI presenter claims the streak (D137)"
  },
  "satisfying-macro": {
    "evidence": "ASMR audio raised ad recall across 4 experiments (JAR 2022) [S]; TikTok Creative Codes recommend 'clean and satisfying' edits [M].",
    "prior": 0.6,
    "best_archetypes": ["showcase", "curiosity-gap", "bold-claim"],
    "needs": "an extreme close-up texture with the real product sound; little or no music",
    "ai_render_risk": "medium: fluid and foam physics; the sound must be real or foley, not generated speech"
  }
}
```

**Proposed VISUAL_TYPES additions** (new ids):
- `talking-head`: face to camera, no reaction. It covers Motion's Founder and Expert Explained formats [M]. It needs a human, or a disclosed AI presenter.
- `offer-banner`: Motion's first-listed format (8.6%) [M]. It requires an offer (D158).
- `screen-recording`: Motion lists it 14th, and it suits apps [M]. TikTok Shop bans product-page screenshots [P].
- `pattern-interrupt`: an unexpected object or motion in frame 0 [A]. Fake UI elements such as play or close buttons are banned by TikTok ad policy [P].

## 3. Variants and testing

### 3.1 Meta: creative diversification and Andromeda

- **What agencies report.** Meta's engines treat ads with the same look or the same opening hook as one ad. Text-only swaps don't count as new creative (SFV §4, Marketing Brew). [M]
- **The new metric.** In August 2026 Ads Manager added a *Creative diversity* column that rates each ad set Low, Medium or High. It is labelled estimated and in development. Reported by [Search Engine Land](https://searchengineland.com/meta-ads-creative-diversity-485751), [Common Thread](https://commonthreadco.com/blogs/coachs-corner/metas-new-creative-diversity-score-is-live-in-ads-manager-what-ecommerce-brands-must-act-on-now) and [Billo](https://billo.app/blog/creative-diversity/). [M]
- **What Meta itself says about Andromeda.** The [engineering post](https://engineering.fb.com/2024/12/02/production-engineering/meta-andromeda-advantage-automation-next-gen-personalized-ads-retrieval-engine/) describes it as the retrieval stage, cutting tens of millions of candidate ads to a few thousand through a hierarchical index built for fast-growing GenAI creative volume. It reports +6% recall and +8% ads quality on selected segments. [S]
- **What Meta does not say.** The post says nothing about grouping similar ads. The "Entity ID" and "60%/40% similarity" thresholds are agency lore (UNVERIFIED).

### 3.2–3.3 TikTok, Trial Reels and Shorts

- **TikTok.** The 3–5 substantially different creatives per ad group are in SFV §4. TikTok Studio documents no organic 3-second metric (UNVERIFIED), so read the retention curve at 3 s.
- **Trial Reels** mechanics are in discovery-seo §3.
- **Instagram skip rate** is the share of views skipped within 3 s. It replaced view rate in August 2025 and is exposed as `reels_skip_rate` ([SMT](https://www.socialmediatoday.com/news/meta-announces-updates-for-the-instagram-marketing-api/807083/)) [S]. There is no official benchmark; trackers call under 30–40% healthy and over 50% a failing hook ([BabbleBoxx](https://www.babbleboxx.com/post/instagram-adds-reels-retention-skip-rate-what-influencer-marketers-should-do-next)) [A].
- **YouTube Shorts:** Studio's "Viewed vs. swiped away" is the equivalent ([YouTube Help](https://support.google.com/youtube/answer/12942217)) [P]. One creator's median across 226 Shorts was 50.6% ([note.com](https://note.com/shorts_data_lab/n/nf10c16ae0f1e?hl=en)) [A].

### 3.4 How many variants and what must differ

- **Count:** one primary plus 3–4 alternates, fitting TikTok's 3–5 and Symphony's 3.
- **Must differ:** `visual_type`, `archetype`, the first three words and the overlay, with trigram Jaccard ≤0.2 between any two openings (shared keyword tokens removed).
- **Stays fixed:** the payoff (D35, so an alternate may only use an archetype its payoff can pay), the keyword (DISC-01/02), the disclosure and the body from 3.0 s. Fixing everything after 3.0 s is what isolates the hook in a test.

### 3.5 Reading results

- **Metrics:** paid hook rate = 3 s plays ÷ impressions (benchmarks in SFV §1); Instagram hold = 1 − skip rate; Shorts viewed %.
- **Guardrail:** a winner may not lose more than 10% relative on average watch time or sends per reach. Winning the first 3 s and losing the watch is a broken promise (D35).
- **Statistics.** Organic delivery isn't randomized (audience, time and ranker differ between posts), so treat organic results as directional and replicate before updating priors.
  - Model each variant as Beta-Binomial with a weak prior centred on the account's rolling median (strength about 20 views).
  - Decide on P(best) and expected loss ([Stucchio/VWO](https://vwo.com/downloads/VWO_SmartStats_technical_whitepaper.pdf)) at pre-registered looks only. Peeking inflates false winners ([Evan Miller](https://www.evanmiller.org/how-not-to-run-an-ab-test.html)), and Bayesian rules are not immune ([Analytics-Toolkit](https://blog.analytics-toolkit.com/2017/bayesian-ab-testing-not-immune-to-optional-stopping-issues/)).
  - Our normal-approximation arithmetic (80% power, one-sided 95%, 30% base rate): a 5-point lift needs about 1,000 views per variant, a 10-point lift about 260.

### 3.6 VARIANT_POLICY (json)

```json
{
  "count": {"primary": 1, "alternates_min": 3, "alternates_max": 4, "total_max": 5,
            "source": "TikTok 3-5 creatives per ad group; Symphony 3 variants per run; Meta creative diversity rating"},
  "diversity": {
    "unique_fields": ["visual_type", "archetype", "first3_tokens", "on_screen"],
    "max_trigram_jaccard": 0.2,
    "jaccard_excludes": "primary keyword tokens and stopwords",
    "max_per_cluster": 2,
    "clusters": {
      "promotional": ["price-anchor", "newness"],
      "interrupt": ["negative-command", "bold-claim", "contrarian-reframe", "confession"],
      "evidence": ["showcase", "proof-first", "transformation", "comparison", "day-counter"],
      "inquiry": ["question", "curiosity-gap", "problem-agitate", "listicle"],
      "persona": ["pov", "story-time", "identity-reveal", "challenge"]
    },
    "shared_across_variants": ["payoff and payoff_contract (D35)", "primary keyword spoken and on screen by 3.0 s (DISC-01/02)", "disclosure (D138)", "all beats from 3.0 s"],
    "payoff_compat": {
      "verdict": ["question", "curiosity-gap", "comparison", "price-anchor", "showcase", "proof-first", "contrarian-reframe", "identity-reveal", "confession", "story-time"],
      "measurable-demo": ["showcase", "bold-claim", "negative-command", "problem-agitate", "curiosity-gap", "comparison", "proof-first", "pov", "newness"],
      "transformation": ["transformation", "day-counter", "bold-claim", "problem-agitate", "showcase", "pov"],
      "list": ["listicle", "showcase", "curiosity-gap", "negative-command", "newness"],
      "streak": ["challenge", "day-counter", "story-time", "confession", "question", "transformation"]
    },
    "presenter_filter": "presenter=ai drops ai_safe=false archetypes and every human_only template (D137)"
  },
  "testing_protocol": {
    "paid": "one ad per variant in one ad set/ad group, same budget, same audience, launched together; read daily, decide at day 3 or 7",
    "instagram_trial_reels": "post all variants as MANUAL trials the same day within a 2 h window; looks at 24, 48, 72 h; graduate the winner, never repost a loser as-is",
    "organic_other": "alternate the variants across comparable slots (same weekday and hour band); treat as directional only",
    "looks": "pre-registered only; no decisions between looks",
    "log": ["variant_id", "archetype", "visual_type", "hook_text", "on_screen", "platform", "trial", "posted_at", "impressions_or_views", "holds_3s"]
  },
  "metrics": {
    "primary": {"meta_paid": "3s video plays / impressions", "tiktok_paid": "2-second video views / impressions (TikTok reports 2 s and 6 s views; exact metric names UNVERIFIED)", "instagram": "1 - reels_skip_rate", "youtube_shorts": "viewed vs swiped away (% viewed)", "tiktok_organic": "retention at 3.0 s from the retention curve (manual)"},
    "guardrails": ["average watch time", "sends or shares per reach", "completion rate"],
    "guardrail_rule": "winner may not be worse than the primary by more than 10% relative on any guardrail"
  },
  "thresholds": {
    "hook_rate_paid": {"kill_below": {"meta": 0.15}, "median": {"meta": 0.28, "tiktok": 0.33, "youtube": 0.22}, "top_decile": {"meta": 0.45, "tiktok": 0.55, "youtube": 0.38}, "source": "SFV section 1 (Benly/Ryze via AdBeacon) [M]"},
    "instagram_skip_rate": {"healthy_below": 0.35, "failing_above": 0.5, "grade": "A (trackers; no official benchmark)"},
    "shorts_viewed_pct": {"reference_median": 0.506, "grade": "A (one creator, 226 Shorts)"}
  },
  "stats": {
    "model": "Beta-Binomial per variant: holds ~ Binomial(n, p), p ~ Beta(a0 + holds, b0 + n - holds)",
    "prior": "a0 = 20 * m, b0 = 20 * (1 - m), m = account's rolling median hold rate for the platform (fallback: platform median above)",
    "decision": "pick variant v when P(v is best) >= 0.95 AND expected loss of choosing v <= 0.01, evaluated by 20,000 Monte Carlo draws",
    "min_n_per_variant": 300,
    "power_guide": {"lift_5pp_at_30pct": 1000, "lift_10pp_at_30pct": 260, "note": "normal approximation, 80% power, one-sided 95%; derived here"},
    "futility": "at the last look, if no variant has P(best) >= 0.80, keep the primary and log 'no difference'",
    "early_kill": "drop a variant at any look when P(p < kill threshold) >= 0.90",
    "prior_update": "update archetype and visual priors only from paid tests or >= 2 replicated organic wins"
  }
}
```

## 4. Explainable hook score

The score ranks candidate openings *within one script*. It does not predict virality.

**Formula.**
- Each feature returns x in [0,1]. `open_loop_paired` and `question_form` are signed, in [−1,1].
- raw = Σ w·x over bonuses − Σ w·x over penalties.
- score = round(100 × clamp(raw ÷ 0.81, 0, 1)). The 0.81 is the sum of the bonus weights, and all weights sum to 1.
- The explanation is each feature's points, 100·w·x ÷ 0.81, sorted by size. Hard failures (§6) are gates, not score terms.

### 4.1 HOOK_SCORE_FEATURES (json)

```json
[
  {"id": "length_band", "description": "spoken hook length and time budget", "weight": 0.06, "direction": "+", "detector": "n = len(lexicon.words(hook)); x = 1 if 4<=n<=8 and 0.3 + n/3.0 <= 3.0 else 0.6 if n == 3 else 0", "evidence": "D73; Kim 2024 ~8 words per sentence [M]; SFV speech-rate rule [S]"},
  {"id": "payload_first3", "description": "product, category, flaw or a number within the first 3 words", "weight": 0.09, "direction": "+", "detector": "first 3 norm tokens intersect tokens of ctx product/category/category_pl/flaw/after or match \\d; x = 1, words 4-5 -> 0.5, else 0", "evidence": "Meta: under-25 view time < 2 s [M]; 0.25 s recall [M]; OpusClip lead-with-the-thing [M]"},
  {"id": "keyword_early", "description": "product or category spoken by 3.0 s (search and relevance)", "weight": 0.07, "direction": "+", "detector": "DISC-01 check on the hook cue; x in {0,1}", "evidence": "discovery-seo DISC-01 [P/M]; Creative Codes product early [S]"},
  {"id": "concrete_specific", "description": "a concrete noun from ctx slots and/or a number", "weight": 0.07, "direction": "+", "detector": "x = 0.5 per signal (number regex \\b\\d+\\b|one..ten; any ctx noun phrase present), max 1", "evidence": "Loewenstein 1994 closable gap [S]; OpusClip specific-number pattern [A]"},
  {"id": "negativity", "description": "one or two concrete negative words", "weight": 0.05, "direction": "+", "detector": "count NEG = {stop, don't, skip, quit, mistake, wrong, weak, ruins, fail, flaw, tired, wasted, lost}; x = 1 for 1, 0.8 for 2, 0.4 for >=3, 0 for none", "evidence": "Robertson 2023 +2.3% CTR per negative word [S]; Gligoric 2023 beta 0.18 [S]"},
  {"id": "first_person_human", "description": "'I/my/me' when presenter is human", "weight": 0.02, "direction": "+", "detector": "x = 1 if presenter == 'human' and re '\\b(I|my|me)\\b'; 0 for ai (D137 gate handles misuse)", "evidence": "Gligoric 2023 beta 0.24 for first-person singular [S]"},
  {"id": "second_person_selfref", "description": "'you/your' inside a question or callout", "weight": 0.02, "direction": "+", "detector": "x = 1 if re '\\byou(r)?\\b' and (hook ends with '?' or starts with 'if you')", "evidence": "Lai & Farbrot 2014 self-referencing questions [M]; 'you' alone n.s. (Gligoric) [S]"},
  {"id": "question_form", "description": "signed: specific answerable question vs rhetorical or vague", "weight": 0.03, "direction": "+/-", "detector": "if '?' in hook: x = +1 when it contains keyword or number and not re 'have you ever|did you know|guess what'; else -1; no '?' -> 0", "evidence": "CME 2016, Kuiken 2017, Jung 2022 negative; Lai & Farbrot 2014 positive [M]"},
  {"id": "open_loop_paired", "description": "signed: open loop whose promise the payoff pays", "weight": 0.10, "direction": "+/-", "detector": "loop = '?' or re 'here's (why|what|the)|what changed|which wins|verdict|check this|before you'; x = +1 if loop and payoff_contract names the same measurable (D5/D35), -1 if loop and no match, 0.3 if no loop", "evidence": "Loewenstein 1994 [S]; YouTube egregious-clickbait policy [P]; D35/D5"},
  {"id": "novelty", "description": "distance from recent hooks", "weight": 0.08, "direction": "+", "detector": "x = 1 - max trigram Jaccard vs last 50 shipped hooks in niche (keyword tokens removed); x = 0 if first3 tokens equal any of last 10", "evidence": "Meta same-opening = same ad [M]; Motion hook fatigue warning [M]; TikTok FYF unoriginal rule [P]; baseline distinct ratio 28%"},
  {"id": "readability", "description": "easy to hear once", "weight": 0.02, "direction": "+", "detector": "x = 1 if mean syllables/word <= 1.6 excluding ctx product tokens, and no clause nesting (<= 1 comma)", "evidence": "readability n.s. for headlines (Gligoric) [S]; BBC subtitle-rate research [S]: low weight"},
  {"id": "overlay_alignment", "description": "frame-0 overlay is a contiguous hook phrase or label carrying the keyword head noun", "weight": 0.06, "direction": "+", "detector": "lexicon.overlay_is_clean(ov, hook); x = 1 if clean and contains keyword head noun, 0.8 label form, 0.6 clean without keyword, 0 otherwise", "evidence": "Mayer & Johnson 2008 brief key phrases aid retention [S]; D144; DISC-02"},
  {"id": "visual_type_strength", "description": "frame-0 visual prior and fit to the archetype", "weight": 0.08, "direction": "+", "detector": "x = VISUAL_HOOKS[vt].prior * (1 if archetype in VISUAL_HOOKS[vt].best_archetypes else 0.6)", "evidence": "Motion 2026 formats [M]; OpusClip showcase [M]; Creative Codes [S]"},
  {"id": "archetype_prior", "description": "research prior for the archetype, zeroed if its requirements are unmet", "weight": 0.06, "direction": "+", "detector": "x = ARCHETYPES[a].prior if requires satisfied and (presenter == 'human' or ai_safe != false) else 0", "evidence": "Motion 2026 tactics [M]; OpusClip categories [M]; composite [A]"},
  {"id": "we_pronoun", "description": "'we/our/us' framing", "weight": 0.02, "direction": "-", "detector": "x = 1 if re '\\b(we|our|us)\\b'", "evidence": "Gligoric 2023 beta -0.15 [S]"},
  {"id": "filler_greeting", "description": "greeting or delay opener", "weight": 0.05, "direction": "-", "detector": "x = 1 if re '^(hey|hi|hello|okay|ok|alright|welcome)\\b|^so,|in today.?s video|let me tell you|have you ever wondered'", "evidence": "OpusClip underperformer list [A]; lexicon.SLOP"},
  {"id": "vague_hype", "description": "empty hype or positive superlatives", "weight": 0.05, "direction": "-", "detector": "x = 1 if lexicon.SLOP or lexicon.VAGUE_HOOK or re '\\b(amazing|insane|crazy|unreal|mind-?blowing|obsessed|game.?changer|life.?changing)\\b'", "evidence": "Robertson 2023: positive words lower CTR [S]; Meta sensational phrasing [P]"},
  {"id": "clickbait_marker", "description": "withholding or sensational clickbait phrasing", "weight": 0.04, "direction": "-", "detector": "x = 1 on any RISKY_PHRASES entry with class 'clickbait'; also '!!' or an all-caps sentence of 4+ words", "evidence": "Meta clickbait guidelines [P]; YouTube clickbait policy [P]; D35"},
  {"id": "fake_urgency", "description": "urgency or scarcity without a supplied offer and deadline", "weight": 0.03, "direction": "-", "detector": "x = 1 on RISKY_PHRASES class 'urgency' when prompt has no offer/deadline (D158)", "evidence": "FTC dark-pattern taxonomy [P]"}
]
```

### 4.2 Caveats and calibration

- **Ceiling.** Text features picked the better Upworthy headline only 54% of the time (Gligorić). An LLM coding 77 theory-based variables added little beyond account baselines (SFV §7). Expect a text-only score to rank barely better than chance until it is calibrated. It is still useful for removing weak or risky candidates.
- **Goodhart risk.** Every feature can be gamed: negativity everywhere, a number everywhere. That is why negativity is capped and novelty is weighted. Do not tune the weights on our own golden outputs, because that trains the maker to satisfy the scorer.
- **Calibration.**
  1. Log each variant's features with `platform`, impressions/views and 3 s holds (VARIANT_POLICY `log`).
  2. Fit a Beta-Binomial or logistic model of hold rate on the features. Include random effects for account × platform. Use shrinkage (ridge or horseshoe) toward the weights above as the prior.
  3. Evaluate on **within-script pairwise accuracy**, meaning variants that share a body. This is the same design as Upworthy's same-article tests.
  4. Replace the priors only after 200 or more pairs and a win over the prior weights on a time-split holdout.
  5. Then map score to expected skip-rate percentile with isotonic regression, and refit monthly.
  6. Track per-feature drift, because platform and season shifts are large (Motion's BFCM caveat).

## 5. RISKY_PHRASES (json)

These extend `lexicon.GENERIC_BAIT`, `ABSOLUTE`, `SLOP` and `VAGUE_HOOK`; they don't replace them.
- Use Python `re` with `re.I`, except the caps and punctuation rule (`CB-06`).
- `allow_if` names the prompt-consent path (the D37/D136/D141 allow-path).
- Meta demotes explicit requests for votes, shares, comments, tags, likes or reactions, with narrow exceptions such as missing-person appeals ([Meta](https://transparency.meta.com/features/approach-to-ranking/content-distribution-guidelines/engagement-bait/)) [P].

```json
[
  {"id": "CB-01", "class": "clickbait", "regex": "\\byou (won'?t|will never|wont) believe\\b|\\byou'?ll never guess\\b", "why": "sensational withholding phrase named by Meta", "source": "Meta clickbait-links guideline [P]", "severity": "error", "allow_if": null},
  {"id": "CB-02", "class": "clickbait", "regex": "\\bwhat happen(s|ed) next\\b|\\bwait (for it|till|until)\\b|\\b(watch|stay) (till|until|to) the end\\b", "why": "withholds the payoff to farm watch time", "source": "Meta clickbait-links guideline [P]; D35", "severity": "error", "allow_if": null},
  {"id": "CB-03", "class": "clickbait", "regex": "\\bsecret (to|behind)\\b|\\bthey don'?t want you to know\\b|\\bindustry (doesn'?t|does not) want\\b", "why": "promises a secret demo/review payoffs cannot reveal", "source": "D35; YouTube egregious-clickbait policy [P]", "severity": "error", "allow_if": "payoff names the secret"},
  {"id": "CB-04", "class": "clickbait", "regex": "\\b(shocking|jaw[- ]dropping|mind[- ]?blowing|this will shock you)\\b", "why": "sensationalism without information", "source": "Meta clickbait-links guideline [P]", "severity": "warn", "allow_if": null},
  {"id": "CB-05", "class": "clickbait", "regex": "\\b(nobody|no one) (is talking about|talks about|mentions|knows|tells you)\\b", "why": "unverifiable claim about others; baseline fallback frame", "source": "D144/R02 fallback history [A]", "severity": "warn", "allow_if": null},
  {"id": "CB-06", "class": "clickbait", "regex": "!{2,}|\\?!|\\b[A-Z]{2,}(?:\\s+[A-Z]{2,}){3,}\\b", "why": "excessive punctuation or an all-caps sentence (4+ words); case-sensitive", "source": "Meta clickbait-links guideline [P]", "severity": "warn", "allow_if": null},
  {"id": "CB-07", "class": "clickbait", "regex": "^\\s*stop scrolling\\b", "why": "attention bait that promises nothing", "source": "OpusClip imperative caveat [A]", "severity": "warn", "allow_if": null},
  {"id": "EB-01", "class": "engagement_bait", "regex": "\\bcomment (yes|below if|if you)\\b|\\btype (yes|1|a)\\b|\\bvote (yes|below)\\b|\\bcomment \\d for\\b", "why": "comment and vote baiting", "source": "Meta engagement-bait guideline [P]; D139", "severity": "error", "allow_if": "keyword-to-DM CTA naming a payload (B4a)"},
  {"id": "EB-02", "class": "engagement_bait", "regex": "\\b(share|send) (this|it) (with|to)\\b", "why": "share baiting; sends must be earned", "source": "Meta engagement-bait guideline [P]; D139", "severity": "error", "allow_if": null},
  {"id": "EB-03", "class": "engagement_bait", "regex": "\\btag (a friend|someone|your \\w+)\\b", "why": "tag baiting", "source": "Meta engagement-bait guideline [P]; D139", "severity": "error", "allow_if": null},
  {"id": "EB-04", "class": "engagement_bait", "regex": "\\b(like|react|heart) (this )?if\\b|\\bdouble[- ]tap\\b|\\bsmash (that|the) like\\b", "why": "react baiting", "source": "Meta engagement-bait guideline [P]; D139", "severity": "error", "allow_if": null},
  {"id": "UR-01", "class": "urgency", "regex": "\\bhurry\\b|\\bact (fast|now)\\b|\\blast chance\\b|\\bbefore it'?s gone\\b|\\bends (tonight|today|soon|at midnight)\\b|\\btoday only\\b|\\blimited[- ]time\\b|\\bwhile (supplies|stocks?) last\\b|\\bdon'?t miss (out|this deal)\\b", "why": "false limited-time pressure", "source": "FTC dark patterns: false limited time, baseless countdown [P]", "severity": "error", "allow_if": "offer and deadline in prompt (D158)"},
  {"id": "UR-02", "class": "scarcity", "regex": "\\bonly \\d+ left\\b|\\balmost (gone|sold out)\\b|\\bselling (out )?fast\\b|\\b(low|limited) stock\\b|\\bsold out\\b", "why": "false low-stock message", "source": "FTC dark patterns: false low stock [P]; D136", "severity": "error", "allow_if": "stock claim in prompt"},
  {"id": "UR-03", "class": "scarcity", "regex": "\\b\\d+[kKmM]? (people|others|shoppers) (are )?(viewing|watching|looking|buying)\\b|\\b(everyone|everybody) is (buying|getting)\\b", "why": "false high-demand or activity message", "source": "FTC dark patterns: false high demand/activity [P]; D136", "severity": "error", "allow_if": "sourced figure in prompt"},
  {"id": "UR-04", "class": "urgency", "regex": "\\b(was|regularly|reg\\.?) [$€£]?\\d[\\d.,]*\\b.{0,15}\\b(now|today) [$€£]?\\d|\\b\\d{1,2}% off\\b|\\bprice (goes|is going) up\\b|\\bwon'?t be this price\\b", "why": "fake discount or price-rise pressure", "source": "FTC dark patterns: false discount [P]; Meta deceptive pricing [P]; D37", "severity": "error", "allow_if": "offer in prompt"},
  {"id": "AB-01", "class": "absolute", "regex": "\\bbest\\b(\\s+\\w+){0,2}\\s+(in the world|on the market|on (amazon|tiktok)|there is)\\b|\\bworld'?s (best|first|most)\\b|\\bmost popular\\b", "why": "absolute terms about region, brand or time", "source": "TikTok ad policy, misleading claims (Apr 2026) [P]; D141", "severity": "error", "allow_if": "same claim in prompt"},
  {"id": "AB-02", "class": "absolute", "regex": "\\bobsolete\\b|\\bnothing (else )?compares\\b|\\bunbeatable\\b|\\bworks for everyone\\b|\\bnever fails\\b|\\b100 ?%\\b", "why": "unsubstantiable superlative or universal claim", "source": "TikTok ad policy [P]; FTC substantiation [P]; D141", "severity": "error", "allow_if": "same claim in prompt"},
  {"id": "AB-03", "class": "absolute", "regex": "\\b(instant|overnight) results\\b|\\bright away\\b|\\bin (one|1) (day|night) flat\\b", "why": "promised or exaggerated speed of effect", "source": "TikTok ad policy ('Get slim legs right away' example) [P]", "severity": "error", "allow_if": "measured on camera (bold-claim with timer)"},
  {"id": "AB-04", "class": "absolute", "regex": "\\b(cures?|heals?|clinically|doctor[- ]recommended|dermatologist[- ](approved|recommended)|fda[- ]approved)\\b|\\bmoney[- ]back\\b", "why": "health or authority claims needing substantiation", "source": "TikTok ad policy [P]; FTC health guidance [P]; D141", "severity": "error", "allow_if": "same claim in prompt"},
  {"id": "UI-01", "class": "fake_ui", "regex": "\\bfake (notification|play button|close button|low battery|incoming call|dm)\\b|\\b(notification|play button) (overlay|mock-?up)\\b", "why": "frame-0 visual that manipulates viewers into engaging", "source": "TikTok ad policy, non-functioning interactive elements [P]", "severity": "error", "allow_if": null}
]
```

## 6. Proposed gate and rubric rules

These are proposals. Ids are neutral (`HOOK-nn`) so they don't collide with D or R numbering.

```json
[
  {"id": "HOOK-01", "stage": "gate2", "severity": "warn->error", "rule": "script carries 3-4 hook_variants besides the primary; every pair differs in visual_type, archetype, first 3 tokens and on_screen; trigram Jaccard <= 0.2 with keyword tokens removed; <= 2 openings per cluster", "threshold": {"alternates": [3, 4], "max_jaccard": 0.2, "max_per_cluster": 2}, "source": "Meta same-opening guidance [M]; TikTok 3-5 creatives [S]; VARIANT_POLICY"},
  {"id": "HOOK-02", "stage": "gate1", "severity": "error", "rule": "every opening's archetype is in VARIANT_POLICY.payoff_compat[payoff_type] and all openings share one payoff_contract", "threshold": null, "source": "D35/D5; YouTube egregious-clickbait policy [P]"},
  {"id": "HOOK-03", "stage": "gate1", "severity": "error", "rule": "presenter=ai: no opening uses an archetype with ai_safe=false or a human_only template; lexicon.AI_FIRST_PERSON clean", "threshold": null, "source": "D137; FTC 16 CFR 465.2 [P]; Llama AUP [P]"},
  {"id": "HOOK-04", "stage": "gate1", "severity": "error", "rule": "archetype requirements met: price-anchor needs a prompt price (D37), proof-first a prompt proof (D136), 'new' templates a newness fact, offer an offer and deadline (D158)", "threshold": null, "source": "D37; D136; FTC dark patterns [P]"},
  {"id": "HOOK-05", "stage": "gate1", "severity": "error (warn for severity=warn entries)", "rule": "no RISKY_PHRASES hit in any opening's dialogue, on_screen or frame-0 direction unless allow_if holds", "threshold": {"max_hits": 0}, "source": "section 5"},
  {"id": "HOOK-06", "stage": "gate1", "severity": "warn", "rule": "payload (product/category/flaw/number) within the first 3 spoken words; first word starts <= 0.3 s; keyword spoken by 3.0 s (DISC-01)", "threshold": {"payload_by_word": 3, "first_word_s": 0.3, "keyword_by_s": 3.0}, "source": "Meta view-time statement [M]; SFV rule 2; DISC-01"},
  {"id": "HOOK-07", "stage": "gate1", "severity": "error", "rule": "each opening's overlay passes overlay_is_clean, holds the keyword head noun or a label pair, and stays on screen from 0.0 s to the end of the spoken hook (>= 3.0 s)", "threshold": {"max_words": 3, "min_display_s": 3.0}, "source": "D144; D142; DISC-02; Mayer & Johnson 2008 [S]"},
  {"id": "HOOK-08", "stage": "rubric", "severity": "soft", "rule": "primary = argmax hook_score among openings passing gates; primary >= 60, each alternate >= 50; store score and top-3 feature contributions in script.json", "threshold": {"primary_min": 60, "alternate_min": 50}, "source": "section 4 (uncalibrated) [A]"},
  {"id": "HOOK-09", "stage": "scorecard", "severity": "soft", "rule": "per 30-seed cell and per run: fallback hooks 0%; hook distinct ratio >= 0.60; distinct-2 >= 0.20; no first-3-token repeat within the last 10 hooks of a niche", "threshold": {"fallback": 0.0, "distinct_ratio": 0.6, "distinct2": 0.2}, "source": "baseline 28% / 0.078 (brief); Motion fatigue warning [M]"},
  {"id": "HOOK-10", "stage": "gate2", "severity": "warn", "rule": "the noun named in words 1-3 is visible in the frame-0 direction, and visual_type is in the archetype's best list or has prior >= 0.6", "threshold": {"min_visual_prior": 0.6}, "source": "section 2.5; VISUAL_HOOKS"}
]
```

**Worked example (milk frother, AI presenter, demo, no price or proof).** The table shows the primary and three alternates. Each overlay is a contiguous hook phrase or a label pair (D144), and each carries the keyword.

| Role | Archetype | visual_type | Overlay | Hook |
|---|---|---|---|---|
| Primary | showcase | product-in-action | MILK FROTHER | "Watch the milk frother make silky foam." |
| Alt 1 | negative-command | problem-state | MILK FROTHER OWNERS | "Milk frother owners: stop frothing cold milk." |
| Alt 2 | comparison | comparison | MILK FROTHER \| ESPRESSO MACHINE | "Milk frother vs espresso machine: same silky foam?" |
| Alt 3 | curiosity-gap | satisfying-macro | MILK FROTHER DETAIL | "One milk frother detail decides the verdict." |

- Price-anchor and proof-first are skipped (D37, D136), and every human_only template is dropped for the AI presenter.
- The openings span three clusters (evidence ×2, interrupt, inquiry), within the cap of two per cluster.
- All four share the measurable-demo payoff.

## 7. Sources

All sources are linked inline where they are used. Figures carried over from SFV and discovery-seo keep their original citations there.

Content was rephrased for compliance with licensing restrictions.
