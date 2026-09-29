#!/usr/bin/env python3
"""
VIRAL SCRIPT MAKER — research-grounded short-form script generator.

Built by Marlowe (2026-09-27) for the user's Antigravity agent / video pipeline.
Feed it a basic prompt ("make a script about a $12 LED lamp") and it returns a
complete, shoot-ready viral script: hook stack, timestamped beats, re-hooks,
payoff contract, comment-bait closer, CTA, caption, and the research notes that
justify every choice.

Knowledge compiled from three research programs:
  1. Viral-content research DB — hooks-mastery-playbook (19 hook formulas,
     3-layer hook stack, payoff contracts, niche mapping; 349 dissected reels)
  2. UGC persuasion dossier — 942 lines, 66 VERIFIED findings on voice, social
     proof, authenticity, storytelling structures, body language, gender fit
  3. AI persona persuasion dossier — ~144 graded findings on persona-product
     fit, AI disclosure, engagement ladders, voice registers, parasocial bonds

Usage:
  python3 viral_script_maker.py "a $12 LED sunrise alarm lamp" --presenter ai --format demo
  python3 viral_script_maker.py "why your hooks fail" --presenter human --format talking-head --duration 45
  python3 viral_script_maker.py "prompt" --json > script.json   # machine-readable for the pipeline
"""
import argparse, json, os, random, re, sys, textwrap

_NO_RESEARCH = False
try:
    import research_bridge
    _PACK = research_bridge.load_pack()
except Exception:
    research_bridge = None
    _PACK = None

# ---------------------------------------------------------------- hook banks
# curiosity-gap and bold-claim together = ~41% of all viral hooks in the DB.
# Default to those two families unless the niche has a native family.
HOOKS = {
 "curiosity-gap": [
   'Nobody is talking about {flaw}.',
   'I tested {product} for {ndays} days. The result surprised me.',
   'There\'s one thing {product} does that nobody mentions.',
   'I almost didn\'t post this about {product}.',
   'The {category} industry doesn\'t want you to know this.',
   'Wait until you see what {product} does at the {moment}.',
 ],
 "bold-claim": [
   '{product} is the best {category} under ${price}.',
   'I replaced my {expensive} with {product}. No regrets.',
   '{product} just made every other {category} obsolete.',
   'Ninety seconds. That\'s all {product} needed to convince me.',
 ],
 "negative-command": [
   'Stop {mistake}.',
   'Stop buying {category} until you see this.',
   'You\'re using {product} wrong.',
 ],
 "proof-first": [
   'Here\'s the receipt: {proof}.',
   'Screenshot first, talking after: {proof}.',
   '{proof} — and it started with {product}.',
 ],
 "transformation": [
   'This is the after. Here\'s what it took.',
   '{before} → {after}. Same {timespan}.',
 ],
 "story-time": [
   'Story time: the {moment} {product} saved my {thing}.',
   'So I\'m {situation} when {product} does this —',
 ],
 "contrarian-reframe": [
   'Everyone does {common}. Here\'s why that\'s wrong.',
   '{common} is a waste of money. Do this instead.',
 ],
 "identity-reveal": [
   'I\'m a {identity}, and I was wrong about {product}.',
   'Full disclosure: I\'m {persona_note}. Here\'s my honest take.',
 ],
}
NICHE_KEYWORDS = {
 # D11 (judge loop, cycle 5): pet-family products get their own niche FIRST —
 # "pet hair remover roller" was misclassified as beauty by the "hair" keyword
 # and captioned #beautytok #skincare. Pets keywords use word-boundary match
 # (carpet -> pet false positive otherwise) and are checked BEFORE the loop.
 "pets": [r"\bpet\b", r"\bpets\b", r"\bdog\b", r"\bdogs\b", r"\bcat\b", r"\bcats\b",
          r"furbaby", r"\bpuppy\b", r"\bpuppies\b", r"\bkitty\b", r"\bkitten\b",
          r"litterbox", r"\bleash\b", r"furball",
          # D75 (judge loop, cycle 19): bird/animal-object products ("smart
          # bird feeder with camera") fell to niche=default (the D11-family
          # fall-through, ninth occurrence) — "bird"/"feeder" matched nothing.
          # Birding/wildlife products belong to the pets caption community.
          r"\bbird\b", r"\bbirds\b", r"\bfeeder\b", r"\bbirdhouse\b"],
 "gadgets": ["gadget","tech","lamp","alarm","charger","earbud","speaker","keyboard",
             "mouse","light","led","projector","drone","smartwatch","phone","desk","cable","fan",
             "laptop"],  # D110: +laptop (D11 class)
 "tools": ["tool","kitchen","clean","organize","organizer","knife","drill",
          "waffle","fryer","toaster","kettle","blender","cookware",
          "lunch", "mealprep"],  # D98, D110: +lunch/+mealprep (D11 class)
 "finance": ["finance","money","budget","invest","debt","credit","bank"],
 "fitness": ["fitness","workout","gym","protein","posture","exercise","yoga","run",
          # D24 (judge loop, cycle 9): "resistance bands set" fell to
          # niche=default → #viral #fyp #ugc (the D11/D14/D18/D20
          # fall-through bug, fifth occurrence). Equipment keywords now route.
          "resistance","band","dumbbell","kettlebell","treadmill",
          "pull-up","pullup","chin-up",
          # D38 (judge loop, cycle 12): "walking pad" fell to gadgets via
          # "desk" (seventh fall-through) — the compound is caught by the
          # D37 pre-check above; bare "walking"/"cardio"/"steps" route here.
          "walking","cardio","steps"],
 "beauty": ["beauty","skincare","makeup","serum","cream","hair",
             # D72 (judge loop, cycle 18): "magnetic eyelashes" fell to
             # niche=default -> #viral #fyp #ugc (the D11-family fall-through,
             # eighth occurrence). Lash products are beauty's core review
             # community (#beautytok #lashreview).
             "lash","lashes","eyelash","lipstick","moisturizer"],  # D107: +lipstick/+moisturizer (D11 class)
 # D14 (judge loop, cycle 6): ingestible/wellness products ("sleep gummies")
 # fell through to niche=default → generic #viral #fyp #ugc. Wellness is a
 # real caption community (#sleeptok #wellnesstok) and a trust-sensitive class.
 # D29 (judge loop, cycle 11): "portable white noise machine" fell through —
 # no wellness keyword matched "noise"/"sound" products (the D11/D14/D18/D20/
 # D24 fall-through bug, SIXTH occurrence). Sound-sleep keywords added.
 "wellness": ["sleep","gumm","melatonin","magnesium","supplement","vitamin",
              "hydrat","wellness","selfcare","self-care","relax",
              "anxiety","stress","meditat","cbd","probiotic",
              "noise","snore","lullab"],
 # D18 (judge loop, cycle 7): "car headrest hook" fell through to
 # niche=default → #viral #fyp #ugc. Automotive is a real caption community
 # (anatomy-automotive notes). Short tokens use word-boundary regexes like
 # pets (D11) to dodge substring hijacks ("car" ⊂ "cardboard"/"career").
 # D129 (gauntlet, cycle 17): trunk — "trunk organizer" fell to niche=tools
 # (thirteenth D11-family fall-through) and captioned #organization
 # #kitchentok on a car trunk organizer. In product names "trunk" is the
 # car sense essentially always ("swim trunks" is plural and never matches
 # the boundary); word-boundary regex per the D18 pattern.
 "automotive": [r"\bcar\b", r"\bcars\b", r"\bauto\b", r"\bvehicle\b",
               r"\btruck\b", r"\bdashboard\b", r"\bheadrest\b", r"\btire\b",
               r"\bengine\b", r"\bmotor\b", r"\bgarage\b", r"\bdriving\b",
               r"\btrunk\b"],
 # D20 (judge loop, cycle 8): home niche — "things in my apartment that just
 # make sense" fell through to niche=default (the challenge branch skipped
 # niche detection entirely). Room-tour/listicle content is a real caption
 # community (#homefinds #apartmenttherapy). Placed last in the loop so
 # gadget/tool keywords win on mixed prompts ("LED desk lamp" stays gadgets).
 "home": [r"\bhome\b", r"\bapartment\b", r"\bbedroom\b", r"\bliving ?room\b",
          r"\bcloset\b", r"\bbathroom\b", r"\bdecor\b"],
 "food": ["food","recipe","cook","snack","coffee","meal"],
 "education": ["learn","course","study","language","exam"],
 "commentary": ["news","politics","drama","tea"],
 # D134 (judge loop, cycle 35): OUTDOORS niche — "portable camping lantern"
 # fell through to niche=default → generic #viral #fyp #ugc (the
 # D11-family fall-through, fourteenth occurrence; "light"/"lamp" gadgets
 # keywords never match "lantern"/"camping"). Outdoor gear is a real
 # caption community (#campingtok). Placed LAST so gadget/tool keywords win
 # on mixed prompts ("LED camping lantern" stays gadgets via "led", per
 # the D20 ordering philosophy). Plain-substring-safe tokens (no
 # word-boundary regexes in this loop — see line ~789).
 "outdoors": ["camp","camping","tent","outdoor","hik","lantern","flashlight",
              "headlamp","backpack","firewood"],
}
NICHE_HOOK = {  # from the playbook's niche mapping
 "gadgets": "curiosity-gap", "tech": "curiosity-gap", "tools": "curiosity-gap",
 "pets": "transformation",  # D11: pet products demo a visible before/after
 "finance": "bold-claim", "money": "bold-claim", "fitness": "bold-claim",
 "beauty": "transformation", "food": "transformation", "makeover": "transformation",
 "comedy": "story-time", "commentary": "contrarian-reframe",
 "advice": "negative-command", "education": "negative-command",
 "lifestyle": "story-time", "vlog": "story-time",
 "home": "story-time",  # D20 (judge loop, cycle 8): room-tour/listicle grammar
 # D29 (judge loop, cycle 11): sleep/sound products demo on a named sleep
 # CLAIM, not curiosity — "Asleep in twenty minutes. Two nights in a row."
 "wellness": "bold-claim",
 # D134 (judge loop, cycle 35): outdoor-gear demos open on the object (like
 # gadgets) — mirrors gadgets' curiosity-gap so the niche fix changes only
 # tags/comment word, never the hook family.
 "outdoors": "curiosity-gap",
}

# D29 (judge loop, cycle 11): niche-gated extra hook templates — appended to
# the family's candidate list, so the min-word-count selection can prefer a
# niche-native hook without leaking it into other niches' families.
NICHE_HOOK_EXTRA = {
 "wellness": ["Asleep in twenty minutes. Two nights in a row."],
}
NICHE_AUTHORITY = {  # borrowed-authority name-drop per niche (Robins rule)
 "gadgets": "MKBHD", "tech": "MKBHD", "tools": "Hormozi",
 "finance": "Hormozi", "money": "Hormozi", "fitness": "Huberman",
 "beauty": "Hyram", "food": "Gordon Ramsay",
 # D29 (judge loop, cycle 11): wellness borrowed authority is Huberman's
 # sleep-science episodes — the vague "the best in the game said it best"
 # default fired on a white-noise machine, naming nobody (A2: evidence >
 # adjectives; an unnamed "best" is an adjective).
 "wellness": "Huberman",
}

REHOOKS = [  # D2 (judge loop, cycle 1+2): re-hooks are EVENT-SPECIFIC, never
 # generic. Every template must name the upcoming event via {action}; callers
 # always .format(action=...). Generic family ("here's where it gets
 # interesting" with no event) is banned — it scored 4/10 against refs.
 "But here's the part nobody shows you — {action}.",
 "Wait — it gets better: {action}.",
 "That's not even the best part: {action}.",
 "Here's where it gets interesting: {action}.",
 "Now watch what happens when I {action}.",
 "And then I noticed something weird — {action}.",
 "Okay, but why does it actually work? Watch {action}.",
 "One more thing before you decide — {action}.",
]
# D93 (pipeline v2): REHOOK PROMISE-UNIQUENESS past 30s. With 2–3 edu or
# demo beats every channel re-promised ONE event (edu_action / the demo
# test) under different frames, and 3+ challenge days repeated the same pin.
# Later beats promise their own next event (noun phrases: they render in
# every non-"when I" frame, D86).
_EDU_NEXT_TEASES = ["the {category} spec that actually matters",
                    "the setup, start to finish",
                    "the part the listing hides"]
_DEMO_NEXT_TEASES = ["round two, pushed harder",
                     "the stress test that ends it",
                     "the one detail nobody checks"]
_DEMO_LATER_RESULTS = ["same result, pushed harder", "still holding up"]
_CHALLENGE_REHOOK_PINS = ["Day 1 is where it almost fell apart.",
                          "Day {d}: the moment I almost quit.",
                          "Day {d}: the part nobody warns you about.",
                          "Day {d}: where it finally clicked."]

EDU_BEATS = [  # educational narrative beats (F103: educational > evaluative for personas)
 "Here's the problem {product} actually solves: {problem}.",
 # D143 drive-by: "Most {category} fail" rendered "Most car vacuum fail"
 # (and the D63 rewrite only caught one-word categories) — plural slot.
 "Most {category_s} fail because {flaw}. This one doesn't.",
 "The science is simple: {mechanism}.",
 "{authority} said it best — {authority_quote}.",
 "Three things to check before you buy any {category}: {check1}, {check2}, {check3}.",
]

DEMO_BEATS = [
 "Watch: {action}. See that? {result}.",
 "Test one: {test1}. {result1}.",
 "Test two: {test2}. {result2}.",
 "Compare it to {expensive}: {comparison}.",
 "The detail that sold me: {detail}.",
]

# D12 (judge loop, cycle 5): HUMAN IMPERFECTION BEAT. Human-presenter scripts
# were losing the "complex very human" axis — every reference in the human
# class (haleyybaylee, istanboss, vladigalagan) carries visible imperfection,
# and RULES.md E7 (admit the flaw first) had no maker code path. Templates
# always open with a confession or a visible fumble; slots force honesty.
# D23 (judge loop, cycle 9): pools are niche-scoped — cycle 9 caught
# "The last one clogged on day two" firing on a resistance bands set (bands
# snap/roll up, never clog). A fake confession burns the trust E7 buys.
# D143 (pipeline v2, D12 budget): the 3–5s imperfection beat carries <=12
# spoken words — the old 20–34-word confessions shipped in a fixed 2.0s
# window (~600 wpm). Same confessions, spoken length; {category} replaces
# {product} (a 4-word product name blew the budget on its own).
IMPERFECTION_BEATS = {
 "generic": [
  # D115 (gauntlet, cycle 12): RETIRED "my last {product} snapped in half on
  # the couch" — fired impossibly on three products (white noise machine,
  # waffle maker, portable door lock): a door lock doesn't snap, a speaker
  # doesn't live on a couch. Per D23/D32, an imperfection entry that fires
  # impossibly on 2+ categories leaves the generic pool — it was a
  # fake confession burning the E7 trust contract. Fail-neutral entries stay.
  "Honest start: I thought {this_category} {was} a scam. The last one died.",
  # D123 (gauntlet cycle 15): no markdown in spoken lines — the old template
  # shipped literal "*I*" emphasis markers; dialogue is read verbatim by the
  # presenter/VO engine, so markup is unperformable garbage, not emphasis.
  "Confession: I fumbled the first try. Left it in.",
  "Nobody's paying me. The first one I tried was garbage.",
 ],
 # D23: fitness lane — failure verbs true of workout equipment
 "fitness": [
  "Real talk: my last set of bands snapped mid-rep.",
  "Honest start: my last ones rolled up by day two.",
 ],
 # D32 (judge loop, cycle 11): wellness/sound lane — failure verbs true of
 # sleep-sound products. Cycle 11 caught the generic pool's "snapped in
 # half on the couch" firing on a WHITE NOISE MACHINE (maker self-violation
 # of D23's intent — a fake confession burns the E7 trust contract).
 "wellness": [
  "Real talk: my last sound machine died at 3AM. Twice.",
  "Honest start: the last one rattled and hissed all night.",
 ],
}

# D26 (judge loop, cycle 10): MECHANISM FAILURE MAP. Cycle 10 caught D19
# evasion — the maker retired "$20 beat the $160 name brand" but kept the
# price-surprise framing in the surprise/expected_flop slots ("the $20 one
# didn't cut a single corner") and in demo beats ("the $160 name-brand
# one"). A7 subversion now targets a category-specific FAILURE MECHANISM,
# never the price. Map keys are substrings matched against the category
# noun; values are (part, fail_verb, zero_outcome) triples rendering as
# "the {category}'s {part} to {fail_verb}" / "seven days, {zero_outcome}".
CATEGORY_MECHANISM_FAIL = {
 "mount": ("magnet", "give up on the first speed bump", "zero slips, zero wobble"),
 "roller": ("head", "jam on pet hair after two passes", "zero jams, one swipe clean"),
 "brace": ("straps", "dig into my shoulders by hour two", "no digging, wore it eight hours"),
 "lamp": ("bulb", "be a glorified nightlight", "actually filled the room"),
 "blender": ("motor", "choke on ice", "crushed ice, no stalling"),
 "gumm": ("dose", "be candy with a bedtime story", "asleep in twenty minutes, twice in a row"),
 "band": ("bands", "snap mid-rep like the last set", "a hundred reps, no snap"),
 "hook": ("hook", "snap on the first hard brake", "hard brakes, zero give"),
 # D29/D32 (judge loop, cycle 11): sleep-sound products — the failure
 # mechanism is the SPEAKER (crackle at volume), never the plastic shell.
 "noise": ("speaker", "crackle at high volume like every sound machine I've tried",
           "zero crackle, even at full blast"),
 # D95 (judge loop, cycle 23): vacuum failure mechanism — the motor choking
 # on debris, never the plastic shell. Seed 926's card degraded to
 # DEFAULT_MECHANISM_FAIL ("build ... fail the way cheap vacuums always
 # fail" / "no failure, no gimmicks") — negative-proof by construction.
 "vacuum": ("motor", "choke on sand like every cheap car vacuum",
            "sand gone, suction held all week"),
 # D116 (judge loop, cycle 29): stand failure mechanism — the hinge/joint
 # slips under laptop weight (angle collapses / wobble), never the flat
 # plate. Seed 936's VERDICT card degraded to DEFAULT_MECHANISM_FAIL on
 # "stand" — the same D95-class degrade: every unmapped category ships
 # negative-proof cards ("expected the build to fail ... but it never did
 # — seven days, no failure, no gimmicks").
 "stand": ("joint", "slip under a heavy laptop like every cheap stand",
           "angle held, zero wobble all week"),
 # D118 (judge loop, cycle 30): inflator failure mechanism — the pump motor
 # dies mid-job on cheap inflators (the script's own imperfection beat names
 # it: "the last one gave up on day two"), never the plastic shell. Seed
 # 937's VERDICT card degraded to DEFAULT_MECHANISM_FAIL on "inflator" and
 # the spoken payoff degraded to DEFAULT_PURPOSE_PROOF ("Test result:
 # before and after, side by side.") — the same D95/D116-class double
 # degrade cycle 29 caught on "stand". Inflator now joins all three proof
 # maps plus CATEGORY_WHO.
 "inflator": ("pump", "die mid-tire like every cheap inflator",
              "every tire at full pressure, still going"),
 # D128 (judge loop, cycle 33): built-in-cable power-bank category — the
 # cables' failure mode is fraying at the connector neck (seed 940's
 # VERDICT card degraded to DEFAULT_MECHANISM_FAIL on "cables" — the
 # D95/D116/D118 class, fourth occurrence). part="connector" keeps
 # expected_flop readable: "the cables' connector to fray...".
 "cables": ("connector", "fray at the neck like every cheap cable",
            "zero fraying, still clicking in tight"),
 # D133 (judge loop, cycle 35): camping-lantern category — cheap lanterns
 # die on the trail (LED dims out by night two), never the plastic shell.
 # Seed 947's VERDICT card degraded to DEFAULT_MECHANISM_FAIL on "lantern"
 # and the spoken payoff degraded to DEFAULT_PURPOSE_PROOF — the same
 # D95/D116/D118/D128-class double degrade, fifth occurrence.
 "lantern": ("LED", "dim out by night two like every cheap lantern",
             "full glow every night, zero dimming"),
}
DEFAULT_MECHANISM_FAIL = ("build", "fail the way cheap {category_s} always fail",
                          "no failure, no gimmicks")

# D27 (judge loop, cycle 10): REVIEW-FORMAT VERDICT WHO-FOR. A review's
# verdict always names who it's for (saves-driver); keys matched against
# the category noun like CATEGORY_MECHANISM_FAIL.
CATEGORY_WHO = {
 "mount": "anyone who drives with their phone as the co-pilot",
 "roller": "anyone losing the pet-hair war",
 "brace": "anyone at a desk all day",
 "lamp": "anyone who wakes up angry",
 "blender": "anyone blending on the go",
 "gumm": "anyone staring at the ceiling at 2AM",
 "band": "anyone training at home",
 "hook": "anyone with a backseat that eats bags",
 # D29 (judge loop, cycle 11): sleep-sound products — the buyer is awake at 3AM.
 "noise": "anyone staring at the ceiling at 3AM",
 # D72 (judge loop, cycle 18): lash buyers want the extension look without glue.
 "lash": "anyone who wants the lash look without the glue drama",
 # D118 (judge loop, cycle 30): inflator buyers are the stranded-with-a-soft-tire class.
 "inflator": "anyone who's been stranded on the shoulder with a soft tire",
 # D128 (judge loop, cycle 33): cables buyers are the dead-phone-no-cable class.
 "cables": "anyone who's shown up with a dead phone and no cable",
 # D133 (judge loop, cycle 35): lantern buyers are the dark-tent-dying-light class.
 "lantern": "anyone who's camped in the dark with a dying lantern",
}
DEFAULT_WHO = "anyone burned by cheap {category_s} before"

# D56 (judge loop, cycle 15 — CODE ENFORCEMENT of the cycle-14 rule; the rule
# was appended to RULES.md but never wired into the maker, and seed-815
# shipped the exact negative-proof pattern one cycle later). REVIEW PAYOFF =
# POSITIVE PROOF: the SPOKEN payoff line names the purpose fulfilled on
# camera — never just survival ("it never failed" is an absence, not a
# result). Keys matched against the category noun like CATEGORY_WHO. Kept
# ≤8 words so the spoken payoff fits the D43 3.9s window with the verdict.
CATEGORY_PURPOSE_PROOF = {
 "mount": "the phone didn't move the whole drive",
 "roller": "one swipe, fur gone",
 "brace": "I sat straighter without thinking",
 "lamp": "I woke up before the alarm",
 "blender": "the smoothie was actually smooth",
 "gumm": "asleep in twenty minutes, twice",
 "band": "a hundred reps, no rolling",
 "hook": "my bag rode through every turn",
 "noise": "the room went quiet, I slept",
 "lid": "the lid sealed shut every time",
 "projector": "movie night on my bedroom wall",
 "pad": "the steps happened, every day",
 "fan": "steady cool air through the whole commute",
 # D72 (judge loop, cycle 18): lash category — positive proof is the look
 # delivered, not durability ("looked like extensions through a full day
 # out" beats "didn't fall off").
 "lash": "looked like lash extensions through a full day out",
 # D95 (judge loop, cycle 23): vacuum category — positive proof is the debris
 # removed, not durability ("crumbs and sand off the seats" beats "seven
 # days of daily use"). Seed 926 degraded to DEFAULT_PURPOSE_PROOF because
 # no key matched — the same D56-class degrade cycle 18 (lash) and 19
 # (feeder) fixed per-category.
 "vacuum": "crumbs and sand off the seats, one pass",
 # D116 (judge loop, cycle 29): stand category — positive proof is the
 # posture outcome, not durability (seed 936's spoken payoff degraded to
 # the generic "before and after, side by side" because no key matched).
 "stand": "no more craning over the keyboard",
 # D118 (judge loop, cycle 30): inflator category — positive proof is the
 # delivered pressure, not durability (seed 937's spoken payoff degraded to
 # DEFAULT_PURPOSE_PROOF because no key matched).
 "inflator": "the tire back to full pressure",
 # D128 (judge loop, cycle 33): cables category — positive proof is the
 # differentiator delivered (the phone charged with nothing loose in the
 # bag), not durability (seed 940's spoken payoff degraded to
 # DEFAULT_PURPOSE_PROOF because no key matched). ≤8 words: "Verdict: BUY —
 # ..." totals 8 (D43).
 "cables": "phone charged with no extra cable",
 # D133 (judge loop, cycle 35): lantern category — positive proof is the
 # light delivered (the dark campsite lit), not durability (seed 947's
 # spoken payoff degraded to DEFAULT_PURPOSE_PROOF because no key matched).
 # 5 tokens so the full "Test result: ..." line totals 7, inside the D43
 # 3.9s window (cf. cycle 30's "Test result: the tire back to full
 # pressure." = 8).
 "lantern": "the whole campsite lit up",
}
# D95 (judge loop, cycle 23): the DEFAULT was negative-proof BY CONSTRUCTION
# ("seven days of daily use, on camera" = durability = absence of failure =
# the D56-banned class). Every unmapped category shipped a D56 violation in
# both demo and review payoffs, and the map can never cover all categories.
# The category-blind default is now result-evidence grammar (D25 family):
# it names the visible proof, not survival. D37-safe: no numbers invented.
# D58-repair (gauntlet, cycle 12): was "..., on camera" — a camera-location
# directive in the SPOKEN payoff ("Test result: before and after, side by
# side, on camera."), the D58 stage-direction class seed 811 shipped. The
# shot list owns the camera; VO names the proof.
DEFAULT_PURPOSE_PROOF = "before and after, side by side"

# D137 (pipeline v2): CURATOR PROOF. Five purpose-proof lines above are
# first-person lived experience ("I woke up before the alarm", "the room
# went quiet, I slept") and shipped verbatim in the AI lane ("Test result: I
# woke up before the alarm."). The AI presenter speaks the demonstrative /
# second-person form of the same result; the human lane is unchanged.
AI_PROOF_REWRITES = {
 "I sat straighter without thinking": "you sit straighter without thinking",
 "I woke up before the alarm": "the room is bright before the alarm",
 "my bag rode through every turn": "the bag rode through every turn",
 "the room went quiet, I slept": "the room goes quiet, all night",
 "movie night on my bedroom wall": "movie night on any bedroom wall",
}

# D142 (pipeline v2): SHORT PAYOFF CARDS. The payoff card carried the full
# expected_flop + surprise clauses ("TEST: white noise machine · expected the
# white noise machine's speaker to crackle at high volume like every sound
# machine I've tried, but it never did — seven days, ...", 24–34 words, D103)
# — unreadable at 20 chars/s and an AI first-person leak (D137). Each
# CATEGORY_MECHANISM_FAIL key gets a <=3-token flop and surprise so the card
# keeps D83's elements (label · short product · flop → surprise) in <=12
# tokens. Keys match the category noun like CATEGORY_MECHANISM_FAIL.
CATEGORY_CARD = {
 "mount": ("a slipping magnet", "zero slips"),
 "roller": ("jams on fur", "one-swipe clean"),
 "brace": ("digging straps", "no digging"),
 "lamp": ("a nightlight", "fills the room"),
 "blender": ("a choking motor", "crushed ice"),
 "gumm": ("bedtime candy", "asleep fast"),
 "band": ("snapped bands", "no snap"),
 "hook": ("a snapped hook", "zero give"),
 "noise": ("speaker crackle", "zero crackle"),
 "vacuum": ("a choking motor", "sand gone"),
 "stand": ("a wobbly joint", "zero wobble"),
 "inflator": ("a dead pump", "full pressure"),
 "cables": ("frayed cables", "zero fraying"),
 "lantern": ("a dim LED", "full glow"),
 "lash": ("falling lashes", "held all day"),
 "lid": ("a popping lid", "sealed shut"),
}
DEFAULT_CARD = ("a breakdown", "held all week")
# showcase roundups: the flop is the pretty-but-unshoppable tour, the
# surprise the almost-skipped find (never "cheapest", D141)
SHOWCASE_CARD = ("a pretty tour", "a sleeper hit")
# D27 on the short card: who-for in <=3 tokens (CATEGORY_WHO is a sentence)
CATEGORY_WHO_SHORT = {
 "mount": "daily drivers", "roller": "pet owners", "brace": "desk workers",
 "lamp": "alarm haters", "blender": "gym commuters", "gumm": "light sleepers",
 "band": "home trainers", "hook": "car commuters", "noise": "light sleepers",
 "lash": "no-glue lash fans", "inflator": "road trippers",
 "cables": "daily commuters", "lantern": "campers", "stand": "laptop workers",
 "vacuum": "car owners",
}

# D96 (judge loop, cycle 23): DEMO BEAT NAMES THE TEST (D41 extended to the
# beat itself). "Test 1: the side-by-side. Night-and-day difference." shipped
# verbatim on seeds 714 and 926 — the demo beat's {test}/{result} slot
# defaults were pure labels: no test object named, no measurable outcome,
# against the anna_louisa_at_home reference (one product, every surface
# named). Keys matched against the category noun like CATEGORY_PURPOSE_PROOF;
# fallback is category-grounded, never a label.
CATEGORY_DEMO_TEST = {
 "vacuum": ("crumbs and sand on the passenger seat", "gone in one pass"),
 # D118 (judge loop, cycle 30): inflator demo test — the low tire is the
 # category's one canonical test object (seed 937 shipped the D108 fallback
 # "the inflator doing its real job" on both the demo beat and the demo
 # rehook). Result is positive proof ("full pressure"), never survival.
 "inflator": ("a low tire", "full pressure in one go"),
 # D128 (judge loop, cycle 33): cables demo test — the one canonical test is
 # a dying phone charged by the built-in cable (seed 940 shipped the D108
 # fallback "the cables doing its real job" on the demo beat, the demo
 # rehook, AND the imperfection rehook — plus the D125 violation: no
 # observable named). D37-safe: no numbers invented.
 "cables": ("a dead phone", "charging again, no loose cable"),
 # D133 (judge loop, cycle 35): lantern demo test — the one canonical test
 # is the pitch-black campsite (seed 947 shipped the D108 fallback "the
 # lantern doing its real job" on the demo beat and the demo rehook — the
 # D125 violation: no observable named). D37-safe: no numbers invented.
 "lantern": ("a pitch-black campsite", "full glow in one click"),
}
# D117 (judge loop, cycle 29): flaw-hook demo detail. The review demo beat's
# "The detail that sold me" slot now names the mechanism part (the flaw the
# hook promised) when the category is mapped in CATEGORY_MECHANISM_FAIL.
def _d117_mech(ctx):
    part = next((v[0] for k, v in CATEGORY_MECHANISM_FAIL.items()
                 if k in ctx["category"]), None)
    if not part:
        return None
    return ("the %s, the part every cheap %s gets wrong"
            # D128 (judge loop, cycle 33): "every" takes the singular —
            # "every cheap cables gets wrong" (seed 940, once "cables" is
            # mapped) is an agreement error.
            % (part, singular(ctx["category"])))


# D128 (judge loop, cycle 33): PLURAL-AWARE D108 FALLBACK PRONOUN. The demo-test
# fallback hard-coded "its" — with a plural category ("cables", "bands") the
# spoken line shipped "the cables doing its real job" (seed 940), an
# agreement error across demo beat, demo rehook, and imperfection rehook.
# Plural categories (plural(noun) == noun) take "their".
def _pron(noun):
    return "their" if plural(noun) == noun.strip() else "its"


def _demo_test_for(ctx):
    # D108 (judge loop, cycle 27): the fallback was a LABEL ("the {category}
    # test, up close") — no test object, no measurable outcome — on every
    # unmapped product (only "vacuum" has a map key), a self-violation of
    # D96's "fallback is category-grounded, never a label" contract (seed 934
    # "heated electric lunch box" shipped "Test 1: the box test, up close").
    # The fallback is now event-shaped positive proof (D25/D95 family).
    # D58-repair (gauntlet, cycle 12): was "doing its real job, on camera" —
    # the D96 rehook and the demo dialogue are SPOKEN slots, and "on camera"
    # is a camera-location directive the presenter would voice as nonsense
    # (seed 811: "the lock doing its real job, on camera, round two" failed
    # D44). D108's fix created the channel; the fallback stays event-shaped
    # without the direction. The shot list owns the camera.
    # D128 (judge loop, cycle 33): plural-aware pronoun — see _pron.
    return ctx.get("demo_test",
                   (f"the {ctx['category']} doing {_pron(ctx['category'])} real job",
                    "visible before-and-after proof"))

# D76 (judge loop, cycle 19): COMPOUND-OBJECT AWARENESS. "smart bird feeder
# with camera" extracts category="camera" (the feature tail — the cycle-15
# "lid" precedent: the reviewed differentiator), but slots that must name the
# SHOPPABLE OBJECT fire on the object: who-for, purpose proof, and niche
# event defaults (a bird feeder must not inherit the pet-hair "fur-covered
# couch" edu action, nor the camera buyer's "burned by cheap cameras"
# who-for). Keys are word-boundary regexes matched against the FULL product
# string and are checked BEFORE the category-substring/niche defaults; a
# standalone feature product ("camera") never matches and keeps its own
# behavior. New compound products add one entry here instead of new code.
COMPOUND_OBJECT_SLOTS = {
    r"\bfeeder\b": {
        "who_for": "anyone who wants backyard birds up close",
        "purpose_proof": "birds on camera every single morning",
        "edu_action": ("hang it where the morning birds actually land "
                       "and let the camera roll"),
        # D76b: the pets demo_action default was hardcoded to the cycle-5
        # roller ("hold the roller up after one full swipe") — a bird feeder
        # review voicing that is a D23-class niche-pool leak.
        "demo_action": "the morning the first bird showed up on the feed",
    },
}

# D28 (judge loop, cycle 10): REVIEW-FORMAT REJECTION HISTORY. A reviewer's
# credibility comes from named rejections, not from testing one item. The
# reviewer names N items tried and how they failed — failure verbs are
# category-scoped like D23 (a mount slides/fails in turns; it never
# "clogs"). Niche pool wins; generic is fallback.
# D143 (pipeline v2): rejection lines are spoken-length (<=~16 words; the old
# 24-word forms shipped in a fixed 2.0s window) and count-consistent — "I
# tried {n=2} ... Two went back, one went in the trash" listed THREE failures
# for two items.
REVIEW_REJECT_BEATS = {
 "generic": [
  "Full disclosure: I tried {n} {category_s} before this one. Not one lasted a week.",
  "Before this one, I tried {n} {category_s}. Broken, returned, or lying in the listing.",
 ],
 "automotive": [
  "Full disclosure: I tried {n} {category_s} first. They slid in turns or cooked in the sun.",
 ],
 "fitness": [
  "Full disclosure: I tried {n} {category_s} first. They snapped mid-rep or rolled up.",
 ],
}
# D137 (pipeline v2): an AI presenter never tried anything — the rejection
# history is CURATOR-framed (a shortlist it cut), never "I tried".
REVIEW_REJECT_BEATS_AI = {
 "generic": [
  "Full disclosure: {n} other {category_s} made the shortlist. Each one got cut.",
  "The shortlist had {n} other {category_s}. Broken, returned, or lying in the listing.",
 ],
 "automotive": [
  "Full disclosure: {n} other {category_s} made the shortlist. They slide in turns or cook in the sun.",
 ],
 "fitness": [
  "Full disclosure: {n} other {category_s} made the shortlist. They snap mid-rep or roll up.",
 ],
}

COMMENT_BAIT = [  # deliberate disagreement / fill-in-blank (952-comment example)
 "Rank these: {opt1}, {opt2}, {opt3} — fight in the comments.",
 "Agree or disagree: {hottake}?",
 "The one {category} I'd never buy again is ___. Yours?",
 "Unpopular opinion: {hottake}. Change my mind.",
 # B4a (judge loop, cycle 15): the keyword CTA is follow-FIRST — "hit follow,
 # comment [KEYWORD], and I'll send you [PAYLOAD]", in that order. The follow
 # is the price of the payload; a keyword CTA without it is a funnel with the
 # gate left open (seed-701, seed-714, seed-815 all shipped it follow-less).
 # D88 (judge loop, cycle 21): this template is drawn into the fixed 2.7s
 # comment-bait window on every product/showcase/story run — the old 16-word
 # form was ~355 wpm, unperformable (D87 budget: 2.7s -> <=9 words). Follow-
 # first + keyword + payload, 9 words.
 # D114 (gauntlet, cycle 12): the D88-certified form was 10 TOKENS, not 9 —
 # gate1's D43 tokenizer is whitespace-split, so the em dash counts as a
 # spoken token (D54) and seed 811 shipped 3.3s of speech in the 2.7s window.
 # Fixed-window slots carry no em dashes, ever: "," keeps the 9-token budget.
 "Hit follow, comment {cta_word}, the link list is yours.",
]

# D34 (judge loop, cycle 11): comment word is the NICHE noun the viewer
# wants ("SLEEP"/"CHILI"/"FIND"), never a generic container noun ("MACHINE"/
# "DEVICE"). julianna_claire's comment words (PINK, CHILI, OFFICE, FIND —
# 172–5433 comments) are always niche nouns, never the literal product
# category. Cycle 11 fired "Comment MACHINE" — a generic tail noun is
# comment-bait poison. Niche override wins; fallback is category uppercased.
NICHE_COMMENT_WORD = {
 "wellness": "SLEEP", "home": "FIND", "pets": "PET",
 "fitness": "SET", "automotive": "CAR", "beauty": "GLOW",
 # D134 (judge loop, cycle 35): outdoors niche noun — the camper's desire,
 # not the product category (D34 class; juliana-class desire-noun grammar).
 "outdoors": "CAMP",
}

CTAS = [
 "Link's in my bio — {urgency}.",
 "I put the link in bio. Thank me later.",
 # D89 (judge loop, cycle 21): the old "Follow for the part 2 — I'm testing
 # {next}." was 12 words in the fixed 1.8s CTA window (D87 budget: <=6 words,
 # ~400 wpm unperformable) and carried the "the part 2" article bug. Short,
 # serialized, 6-word max with {next}.
 # D114 (gauntlet, cycle 12): same dash-tokenization class as the D88 bait —
 # the certified 6-word form was 7 tokens ("Follow — part 2: {next}.") and
 # seed 811 shipped 2.3s in the 1.8s window. Comma, not dash.
 "Follow, part 2: {next}.",
 "Save this before you forget. Link in bio.",
]

CAPTION_TAGS = {
 "gadgets": ["#gadgets", "#techfinds", "#amazonfinds"],
 "tech": ["#tech", "#techtok"],
 "pets": ["#petowner", "#furbaby", "#petsoftiktok"],  # D11 (judge loop, cycle 5)
 "wellness": ["#sleeptok", "#wellnesstok", "#selfcare"],  # D14 (judge loop, cycle 6)
 "automotive": ["#cartok", "#carhacks", "#caraccessories"],  # D18 (judge loop, cycle 7)
 "home": ["#homefinds", "#apartmenttherapy", "#amazonfinds"],  # D20 (judge loop, cycle 8)
 # D91 (judge loop, cycle 22): "things in my kitchen that just make sense"
 # resolved niche=tools (via the "kitchen" keyword) but CAPTION_TAGS had no
 # tools entry — ninth D11-family fall-through, generic #viral #fyp #ugc on
 # a kitchen video against the juliana_claire kitchen class. The tools
 # niche (kitchen/clean/organize/knife/drill) captions on organization +
 # kitchen communities; #amazonfinds is the juliana-class universal.
 "tools": ["#organization", "#kitchentok", "#amazonfinds"],
 "finance": ["#moneytok", "#personalfinance"],
 "fitness": ["#fitnesstips", "#gymtok"],
 "beauty": ["#beautytok", "#skincare"],
 "food": ["#foodtok", "#recipe"],
 "challenge": ["#30daychallenge", "#digitaldetox", "#selfimprovement"],
# D47 (judge loop, cycle 13): routine caption community — the ashtonhall
# day-counter class captions on #morningroutine / #5amclub, not #viral.
# (Beauty GRWM keeps the beauty tags via the build_caption branch.)
 "routine": ["#morningroutine", "#5amclub", "#selfimprovement"],
 # D134 (judge loop, cycle 35): outdoors caption community — the camping-gear
 # class captions on #campingtok, not #viral.
 "outdoors": ["#campingtok", "#outdoors", "#campinggear"],
 "default": ["#viral", "#fyp", "#ugc"],
}

# --------------------------------------------------------------- personas
PERSONA_DISCLOSURE = (
  'Disclosure (G6/Q7): on-screen small "AI persona" label from FRAME 0, '
  'separate element from hook text, top safe zone, min 2s + caption line '
  '"made with an AI persona". Never a banner; omission punished worse than '
  'disclosure (third-party exposure trust cliff).'
)
HUMAN_NOTE = (
  'Borrowed authority allowed (name-drop a known figure in-niche). '
  'Delivery: confident-dynamism, never pressuring (UGC Q4 composite).'
)
UTILITARIAN_HINTS = {"gadget","tech","tool","software","lamp","charger","app","earbud",
  "speaker","keyboard","mouse","projector","cable","fan","humidifier","vacuum","mop",
  "kitchen","clean","organize","sleep","alarm","led","phone","desk","car","home",
  "waffle","fryer","toaster","kettle","blender","cookware"}  # D98 appliance nouns
HEDONIC_HINTS = {"perfume","luxury","makeup","fashion","dress","watch","jewelry",
  "resort","spa","wine","experience","romantic"}

# ------------------------------------------------------- parsing & assembly
# D71 (judge loop, cycle 18): NOUN INFLECTION HELPERS. Templates appended "s"
# blindly to {category} (7 sites) and "'s" (expected_flop) — "magnetic
# eyelashes" shipped "eyelashess" (rejection beat, who-for) and "eyelashes's"
# (payoff card), and "every {category}" shipped "every eyelashes gets wrong".
# Plural never double-adds to an s-terminal noun; singular strips one terminal
# s (ies -> y); possessive uses ' for s-terminals. (Known edge: singular
# s-terminal nouns like "glass" keep the s in plural — no current category
# hits it; prefer the map over silent wrongness if one appears.)
def plural(noun):
    n = noun.strip()
    if n.endswith("s"):
        return n
    if re.search(r"(s|x|z|ch|sh)$", n.lower()):
        return n + "es"
    return n + "s"

def singular(noun):
    n = noun.strip()
    if n.lower().endswith("ies"):
        return n[:-3] + "y"
    if n.endswith("s") and not n.endswith("ss") and len(n) > 3:
        return n[:-1]
    return n

def possessive(noun):
    n = noun.strip()
    return n + "'" if n.endswith("s") else n + "'s"

def parse_prompt(prompt):
    p = prompt.strip()
    m = re.search(r'\$(\d+(?:\.\d+)?)', p)
    # D37 (judge loop, cycle 12): PRICE IS NULLABLE. The old default "20"
    # fabricated a price the prompt never named — "under-desk walking pad"
    # rendered "at $20" in the payoff and "it's under twenty bucks" in the
    # CTA (FTC deceptive-claim risk). When the prompt names no price, every
    # price-bearing template degrades (gated like D26's {expensive} filter):
    # payoff drops "at $X", the "under $X" hook is filtered out, the
    # expensive-slot guards fall back to non-price phrasing, and the CTA
    # loses its price claim.
    price = m.group(1) if m else None
    low0 = p.lower()
    # D8/D9 (judge loop, cycle 4): CONCEPT-CLASS ROUTING + SLOT HYGIENE.
    # "I stopped doomscrolling for 30 days" is a SELF-CHALLENGE, not a
    # product — the old (about|for|on) regex parsed "for 30 days" into
    # product="30 days" and routed it through demo grammar ("the days test
    # the box never shows", link-list CTA, expected-flop-inversion surprise
    # (D19). Classify FIRST; slots are derived from the concept class.
    # D112 (judge loop, cycle 28): "I unfollowed 500 accounts for 30 days"
    # (story mode, abstinence challenge per rotation) re-ran the D8/D66
    # routing bug — "unfollowed" matched NO verb class (ch: stopped/quit/
    # gave up/tried/did; act: activity verbs; vice: deleted/ditched/dropped),
    # so is_challenge stayed False and the title fell to product grammar:
    # product="30 days", "Nobody mentions the days flaw", demo tests, link-list
    # CTA, #viral #fyp #ugc. "Unfollowed" is quitting-verb-shaped — abstinence
    # of a feed source, same class as "stopped doomscrolling" (D8) — so it
    # joins the ch alternation, routing to abstinence grammar.
    ch = re.search(r"\bi\s+(stopped|quit|gave up|tried|did|unfollowed)\s+([a-z0-9,]+(?:\s+(?!for\b)[a-z0-9,]+){0,2})(?:\s+for\s+(\d+)\s*days?)?", low0)
    # D66 (judge loop, cycle 17): PRACTICE-CHALLENGE + VICE-ABSTINENCE
    # detection. "I cooked every meal at home for 30 days" is a self-
    # challenge no D8 verb can catch ("cooked" isn't a quitting verb), so it
    # fell to product grammar and re-ran the exact cycle-4 bug: product="30
    # days", "the days test the box never shows", link-list CTA for a story
    # with nothing to link, durability payoff, #viral #fyp #ugc.
    # Triangulation (D20): PRACTICE = I + activity-verb + BEHAVIOR object
    # (carries a behavior quantifier: every/all/each/daily/no/without/at
    # home — never a bare SKU noun) + "for N days". "I tested car headrest
    # hook for 7 days" stays product: "tested" isn't an activity verb and
    # the object is a SKU. VICE-ABSTINENCE = deleted/ditched/dropped + a
    # vice noun ("deleted Instagram for 30 days") — abstinence-shaped.
    act = re.search(
        r"\bi\s+(cooked|ran|walked|meditated|woke|read|wrote|lifted|trained|"
        r"saved|drank|fasted|journaled|studied|stretched|cleaned|danced|"
        r"swam|biked|unplugged|ate)\s+"
        r"([a-z0-9,]+(?:\s+(?!for\b)[a-z0-9,]+){0,3})\s+for\s+(\d+)\s*days?",
        low0)
    act_behav = bool(act) and bool(re.search(
        r"\b(every|all|each|daily|no|without|at home|a day|per day)\b",
        act.group(2)))
    _VICE_NOUNS = ("instagram", "tiktok", "doomscrolling", "phone", "sugar",
                   "coffee", "alcohol", "takeout", "smoking", "snacking",
                   "soda", "netflix", "youtube", "delivery",
                   # D130 (judge loop, cycle 34): "I deleted all social media
                   # apps for 30 days" matched the vice verb regex but flunked
                   # the noun gate — "social media"/"apps" weren't nouns, so
                   # vice stayed None and the prompt fell to product grammar
                   # (the exact D66-class bug). The umbrella noun for the
                   # screen vice is "social media"; platform nouns join too.
                   "social media", "apps", "facebook", "twitter", "snapchat",
                   "reddit", "threads")
    _vice = re.search(
        r"\bi\s+(deleted|ditched|dropped)\s+([a-z ]+?)\s+for\s+(\d+)\s*days?",
        low0)
    vice = (_vice if _vice and any(v in _vice.group(2) for v in _VICE_NOUNS)
            else None)
    # D20 (judge loop, cycle 8): CHALLENGE-TRIGGER TRIANGULATION. The old
    # line fired challenge mode on ANY "\bthings in my\b" — so "things in my
    # apartment that just make sense" (a product-showcase listicle) got
    # doomscrolling journey grammar with "the habit" placeholders
    # ("Thirty days with no the habit"). Challenge now needs a SECOND
    # signal: the verb regex, "N days", or "no X for". Bare "things in my X"
    # is a SHOWCASE (product-roundup listicle) — the julianna_claire class.
    things_in_my = re.search(r"\bthings in my\s+([a-z ]+?)(?:\s+that\s|\s+which\s|\s*$)", low0)
    is_challenge = (bool(ch) or act_behav or bool(vice) or
        (bool(things_in_my) and not bool(ch) and not act_behav and
         bool(re.search(r"\b\d+\s*days?\b|\bno\s+\w+(?:\s+\w+)?\s+for\b", low0))))
    if is_challenge:
        # D21 (judge loop, cycle 8): NO BARE PLACEHOLDER SLOTS. The old code
        # defaulted challenge_noun to "the habit" and rendered it literally
        # ("no the habit"). If the verb regex missed, derive the noun from
        # the "things in my X" phrase before falling back to a generic.
        if act_behav:
            # D67: PRACTICE challenge — the presenter BUILDS a streak, never
            # breaks one. Noun is the gerund of the activity verb + object
            # ("cooking every meal at home"), never "stopping {noun}".
            verbed, obj = act.group(1), act.group(2).strip()
            span_n = act.group(3)
            noun = f"{_PRACTICE_GERUND[verbed]} {obj}"
            challenge_type = "practice"
        elif vice:
            # D130 (judge loop, cycle 34): strip the leading
            # quantifier/determiner from vice nouns — "I deleted ALL social
            # media apps" rendered the hook "I quit all social media apps
            # for 30 days." = 9 words (D73 starve, D113 bypass) and the
            # frame-0 "ALL SOCIAL MEDIA" (D109 drops the payoff noun "apps").
            # "social media apps" is clean for the hook budget, the overlay,
            # and the caption noun (D34).
            noun = re.sub(r"^(all|every|the|my|these)\s+", "",
                          vice.group(2).strip())
            span_n = vice.group(3)
            challenge_type = "abstinence"
        elif ch:
            noun = ch.group(2).strip()
            span_n = ch.group(3) if ch.group(3) else "30"
            challenge_type = "abstinence"
        elif things_in_my and things_in_my.group(1).strip():
            noun = things_in_my.group(1).strip().split(" and ")[0]
            span_n = "30"
            challenge_type = "abstinence"
        else:
            noun, span_n = "a habit worth breaking", "30"
            challenge_type = "abstinence"
        span = f"{span_n} days"
        if challenge_type == "practice":
            # D67: practice slots are STREAK-shaped (D53 grammar: practices
            # fail at relapse, never at a product) — the abstinence slots
            # (withdrawal, screen time, "quiet evenings") are wrong here.
            product = f"{noun} for {span}"
            expected_flop = "I'd be back to my old routine by day 4"
            measured_claim = (f"Day 1 vs Day {span_n} — the streak, "
                              "logged on camera")
            # D105 (judge loop, cycle 26): the old surprise read "the hardest
            # day wasn't day 1 — and the quiet payoff beat the streak
            # itself" — a content-free tail naming no actual delta (3rd
            # cycle of the WATCHED item, seed 929: a journaling challenge
            # whose promised payoff was the streak restated). The card's
            # surprise slot must name a concrete delta; the practice branch
            # ties it to the template's own expected_flop relapse (day 4).
            surprise = ("the hardest day wasn't day 1 — it was day 4, "
                        "and I showed up anyway")
            # D68 (D62-split, judge loop, cycle 17 — closes the cycle-16 OPEN
            # item on the story/challenge payoff): spoken ≤11 tokens
            # (D43: 3.9s payoff window); the card carries noun + subversion
            # for the 85% watching muted.
            measured_short = f"the streak held, all {span_n} days"
            # D101 (judge loop, cycle 24): D68's stated constraint is "no
            # em-dash — it counts as a spoken token"; measured_short shipped
            # with one ("the streak held — all 30 days", seed 927). Comma
            # form: 9 tokens, same budget, D68-literal.
            verdict_card = (f"DAY 1 vs DAY {span_n}: {noun} — logged on "
                            f"camera · expected {expected_flop} · {surprise}")
        else:
            # D120: noun-class abstinence slots (see above). The old branch
            # hard-coded doomscrolling slots for every noun.
            acls = _abstinence_class(noun)
            aslots = _ABSTINENCE_SLOTS[acls]
            product = f"stopping {noun} for {span}"
            expected_flop = aslots["expected_flop"]
            measured_claim = aslots["measured_claim"]
            surprise = aslots["surprise"]
            measured_short = aslots["measured_short"]
            verdict_card = (f"{aslots['verdict_label']} — screen-recorded "
                            f"· expected {expected_flop} · {surprise}")
        ctx0 = {"concept": "challenge", "challenge_noun": noun, "span": span, "span_n": span_n,
                "challenge_type": challenge_type,
                "abstinence_class": (acls if challenge_type == "abstinence" else None),
                "product": product,
                "price": price, "niche": "default", "fit": "hedonic",
                "category": "challenge",
                "expected_flop": expected_flop,
                "measured_claim": measured_claim,
                "measured_short": measured_short,
                "verdict_card": verdict_card,
                "surprise": surprise}
        low = ctx0["product"].lower()
        niche = "default"
        for nk, kws in NICHE_KEYWORDS.items():
            if any(kw in low for kw in kws):
                niche = nk; break
        ctx0["niche"] = niche
        return ctx0
    # D22 (judge loop, cycle 8): SHOWCASE/LISTICLE CONCEPT CLASS. "Things in
    # my apartment that just make sense" is a product-roundup, not a challenge
    # or a single-SKU demo. Grammar = one shoppable item per beat, E2 price
    # reframe ("most $30 & under"), per-item micro-proof, ONE comment-word CTA
    # naming the category (julianna_claire: 1280–5433 comments, D1 class).
    # category="find" keeps every downstream template grammatical ("most
    # finds are overpriced", "Comment FIND — link list").
    if bool(things_in_my) and not is_challenge:
        domain = things_in_my.group(1).strip() or "space"
        ctx1 = {"concept": "showcase", "domain": domain,
                "product": f"these {domain} finds",
                "price": price, "niche": "default", "fit": "utilitarian",
                "category": "find",
                # D81 (judge loop, cycle 20): the expected_flop was apartment-
                # DNA — "another aesthetic room tour" shipped on the car
                # showcase too (seed 923). Domain-scoped so non-home
                # roundups don't inherit the apartment visual language.
                "expected_flop": (f"another aesthetic {domain} tour "
                                  "with nothing actually shoppable"),
                # D36: price may be None (no price in prompt) — never render
                # "under $None" on the showcase roundups.
                "measured_claim": ((f"every item under ${price}, all linked "
                                    "in one list") if price
                                   else "every item linked in one list"),
                # D84 (judge loop, cycle 20): "the cheapest item" is a price-ordered
                # claim — with price=None (no prices named anywhere) it is a
                # D37-class fabrication: cheapest relative to what? The
                # no-price surprise names the overlooked item instead — the
                # same underdog angle, with no price order to defend.
                "surprise": ((f"the cheapest item — under ${price} — is the one "
                              "everyone keeps asking about") if price
                             else ("the one I almost skipped is the one "
                                   "everyone keeps asking about"))}
        # D20 (judge loop, cycle 8): regex pre-check for the home niche — its
        # keywords are word-boundary regexes (like pets/automotive, D11/D18),
        # which the plain substring loop below can never match.
        # D80 (judge loop, cycle 20): the showcase branch checked ONLY the home
        # regex — the pets (D11) and automotive (D18) word-boundary pre-checks
        # never ran here, so "things in my car that just make sense" fell to
        # niche=default (tenth D11-family fall-through): wrong caption tags,
        # comment word FALLBACK "FIND" instead of NICHE_COMMENT_WORD
        # ["automotive"]="CAR", and the placeholder borrowed-authority. Parity
        # with the main product branch: pets, then automotive, then home, then
        # the substring loop (pets/automotive/home excluded there as before).
        low = f"{p} {domain}".lower()
        if any(re.search(rx, low) for rx in NICHE_KEYWORDS["pets"]):
            niche = "pets"
        elif any(re.search(rx, low) for rx in NICHE_KEYWORDS["automotive"]):
            niche = "automotive"
        else:
            niche = ("home" if any(re.search(rx, low)
                                   for rx in NICHE_KEYWORDS["home"])
                     else "default")
        if niche == "default":
            for nk, kws in NICHE_KEYWORDS.items():
                if nk in ("pets", "automotive", "home"):
                    continue
                if any(kw in low for kw in kws):
                    niche = nk; break
        ctx1["niche"] = niche
        return ctx1
    # D47 (judge loop, cycle 13): ROUTINE/DAILY-VLOG CONCEPT CLASS. "my 5AM
    # routine before work" is a PERSONAL ROUTINE — a vlog concept, not a
    # product. The old code fell through to product concept → "hands on 5AM
    # routine before work", category="work", a durability payoff on a routine
    # contract, a link-list CTA for a story with nothing to link, and
    # #viral #fyp #ugc. Routines are their own genre (ashtonhall day-counter
    # series: Day 315 / Day 2,335; "Day 14 with the Hall's" 9.06M likes,
    # 49.2K comments): timestamped ritual acts, one relapse confession
    # (human texture — routines fail at the ALARM, never at a product), a
    # behavior-metric payoff (B1: end on behavior, never views), wake-time
    # fill-in comment bait, and a next-day-check-in CTA (serialization is
    # native to routines — D7's payoff/tease separation applies, but the
    # tease is the genre's fuel). No product demo, no link list, no price —
    # price stays None (D37).
    is_routine = bool(re.search(
        r"\broutine\b|\bgrwm\b|\bget ready with me\b|"
        r"\bday in (my|the) life\b|\bmorning reset\b|\bwind[- ]?down\b",
        low0))
    if is_routine:
        tm = re.search(r"\b(\d{1,2})\s?(am|pm)\b", low0)
        routine_time = (f"{tm.group(1)}{tm.group(2).upper()}" if tm
                        else "night" if "night" in low0 else "morning")
        label = p.strip().rstrip(".")
        # GRWM/get-ready content lives in the beauty caption community;
        # everything else routine-shaped routes wellness.
        niche = ("beauty" if any(re.search(rx, low0) for rx in
                 (r"\bgrwm\b", r"\bget ready with me\b", r"\bmakeup\b",
                  r"\bskincare\b", r"\bbeauty\b")) else "wellness")
        ctx2 = {"concept": "routine", "routine_time": routine_time,
                "routine_label": label, "streak": "14",
                "product": label, "price": None, "niche": niche,
                "fit": "neutral", "category": "routine",
                "expected_flop": "burnout by Wednesday",
                "measured_claim": "fourteen mornings, zero snooze",
                "surprise": "the quiet mornings won"}
        return ctx2
    # D13-fix (judge loop, cycle 6): concept routing is tri-state, not a
    # format mapping. Advice prompts ("why your hooks fail") are NOT products —
    # hard-mapping talking-head to advice (or product) both break the other
    # class. Detect advice markers on the raw prompt; challenge still first.
    is_advice = bool(re.search(
        r"^(why|how|what no one|the truth about|the secret)\b|"
        r"\bmistakes?\b|\bsigns?\b|\bthings to (stop|avoid|never)\b|"
        r"\bfail\b|\bfails\b|\bsecrets?\b|\btips\b|\bhacks\b", low0)) \
        and not re.search(r"\$\d", p)
    if is_advice:
        topic = re.sub(r"^(make (me )?a (script|video) (about|for|on)\s*)", "",
                       p.strip(), flags=re.I).strip()
        low = topic.lower()
        niche = "default"
        for nk, kws in NICHE_KEYWORDS.items():
            if any(kw in low for kw in kws):
                niche = nk; break
        toks = [t for t in re.findall(r"[a-zA-Z]+", low)
                if t not in {"a","an","the","my","for","with","and","of","to","your","about","why","how"}]
        # D15 note: advice "category" is the topic's HEAD noun (first keyword),
        # not the tail — "why your hooks fail" → HOOKS, not "fail".
        return {"concept": "advice", "product": topic, "price": price,
                "niche": niche, "fit": "neutral",
                "category": toks[0] if toks else "videos"}
    # D77 (judge loop, cycle 19): the preposition strip needs word boundaries —
    # "birdhouse with motion camera" matched the "on" inside "motion" and
    # parsed product="camera" (the cycle-4/13 (about|for|on) bug class, new
    # variant: preposition-as-substring). "before work" and "motion" are not
    # prepositions.
    m2 = re.search(r'(?:\babout\b|\bfor\b|\bon\b)\s+(?:a|an|the|my)?\s*(.+)', p, re.I)
    product = (m2.group(1).strip().rstrip('.') if m2 else p).strip()
    product = re.sub(r'^(make (me )?a (script|video) (about|for|on)\s*)', '', product, flags=re.I)
    product = re.sub(r'^(a|an|the|my)\s+', '', product, flags=re.I)
    product = re.sub(r'\$\d+(?:\.\d+)?\s*', '', product).strip()  # price lives in its own slot
    low = product.lower()
    niche = "default"
    # D11: pets pre-check uses word-boundary regex (see NICHE_KEYWORDS) and
    # wins over substring matching — beauty's "hair" must never claim pet-hair.
    # D18 (judge loop, cycle 7): same pattern for automotive — "car" as a raw
    # substring would hijack "career"/"scar"/"cardboard", so regex pre-check.
    if any(re.search(rx, low) for rx in NICHE_KEYWORDS["pets"]):
        niche = "pets"
    elif any(re.search(rx, low) for rx in NICHE_KEYWORDS["automotive"]):
        niche = "automotive"
    # D38 (judge loop, cycle 12): fitness-equipment pre-check — "under-desk
    # walking pad" fell to niche=gadgets (seventh niche fall-through, D24's
    # intent) because gadgets' "desk" won the substring loop before fitness
    # ever ran. Compound equipment names win via regex pre-check, same as
    # D11/D18; word-boundary so "desk" alone still routes gadgets.
    elif re.search(r"\b(walking pad|treadmill|pull-?up|chin-?up|kettlebell|"
                   r"dumbbell|resistance band|yoga mat|step machine|"
                   r"elliptical)\b", low):
        niche = "fitness"
    # D119 (gauntlet, cycle 14): battery-bank compound pre-check — "solar
    # power bank" matched finance's bare substring "bank" (the D11-family
    # substring hijack, twelfth occurrence) and captioned
    # #moneytok #personalfinance on a gadget. A power bank is never a
    # finance product; the compound wins via regex pre-check, same as D38.
    elif re.search(r"\b(power bank|battery bank|power station)\b", low):
        niche = "gadgets"
    else:
        for nk, kws in NICHE_KEYWORDS.items():
            if nk in ("pets", "automotive"):
                continue
            if any(kw in low for kw in kws):
                niche = nk; break
    fit = "utilitarian" if any(h in low for h in UTILITARIAN_HINTS) else \
          "hedonic" if any(h in low for h in HEDONIC_HINTS) else "neutral"
    # category = content noun of the product name ("sunrise alarm lamp" -> "lamp")
    # D30 (judge loop, cycle 11): when the tail token is a generic container
    # noun ("machine"/"device"/"gadget"/"tool"/"item"/"kit"/"set"), keep the
    # descriptive head — "portable white noise machine" -> "white noise
    # machine". The bare tail produced a fake industry ("the machine
    # industry"), a meaningless comment word ("Comment MACHINE"), and weak
    # templates downstream. Up to 3 trailing tokens.
    stop = {"a","an","the","my","for","with","and","of","12","20","30"}
    toks = [t for t in re.findall(r"[a-zA-Z]+", product.lower()) if t not in stop]
    GENERIC_TAIL = {"machine","device","gadget","tool","item","thing","kit",
                    "set","system","unit","product"}
    if len(toks) >= 2 and toks[-1] in GENERIC_TAIL:
        category = " ".join(toks[-3:])
    else:
        category = toks[-1] if toks else "product"
    # D26 (judge loop, cycle 10): closes the D19 evasion. The maker retired
    # the "$20 beat the $160 name brand" line but kept the price-surprise
    # framing in two other channels: the surprise slot ("the $20 one didn't
    # cut a single corner") and the expected_flop slot ("a $20 mount to cut
    # corners"). Price-surprise is now banned from A7 subversion entirely:
    # the subverted expectation is a category-specific FAILURE MECHANISM
    # (the magnet gives up on speed bumps), never the price. Price only
    # re-enters when the prompt names a competitor to compare against
    # (named_competitor), which also gates the "{expensive}" demo/hook
    # templates below.
    # D31 (judge loop, cycle 11): NO RAW SLOT LEAK (extends D21). The old
    # code formatted only tuple index 0 — index 1 kept a raw {category}
    # placeholder that rendered LITERALLY in the payoff ("fail the way cheap
    # {category_s} always fail"). Every element is formatted now.
    mech = next(
        (v for k, v in CATEGORY_MECHANISM_FAIL.items() if k in category),
        tuple(e.format(category=category, category_s=plural(category))
              for e in DEFAULT_MECHANISM_FAIL))
    part, fail_verb, zeroed = mech
    # D76 (judge loop, cycle 19): compound-object slot override — matched on
    # the full product string BEFORE the category-substring lookups below.
    compound_slots = next(
        (v for k, v in COMPOUND_OBJECT_SLOTS.items()
         if re.search(k, product, re.I)), None)
    # D96 (judge loop, cycle 23): the demo test event, computed once — the
    # demo beat, the imperfection-beat rehook, and the demo_action default
    # all name the SAME concrete test (promise -> show -> payoff).
    # D108 (judge loop, cycle 27): the old fallback was the label "the
    # {category} test, up close" — see _demo_test_for. Event-shaped
    # positive-proof fallback instead (D25/D95 family).
    _dt_pair = next(
        (v for k, v in CATEGORY_DEMO_TEST.items() if k in category),
        # D58-repair (gauntlet, cycle 12): was "doing its real job, on camera"
        # — same spoken-slot violation as _demo_test_for's fallback (D44 on
        # seed 811). Event-shaped, no camera direction.
        # D128 (judge loop, cycle 33): plural-aware pronoun — see _pron.
        (f"the {category} doing {_pron(category)} real job",
         "visible before-and-after proof"))
    return {"concept": "product", "product": product, "price": price, "niche": niche,
            "fit": fit, "category": category, "named_competitor": None,
            # A7 + D5 (judge loop cycle 2): payoff must subvert a NAMED expectation
            # and the contract must name the same MEASURABLE in hook and payoff.
            # "the one thing Xs are supposed to do" is banned as contract language.
            "expected_flop": f"the {possessive(category)} {part} to {fail_verb}",
            "measured_claim": (f"seven days using it daily: the {category} test "
                                # D118 drive-by (judge loop, cycle 30): was the
                                # baked-in "the box never shows" from the cycle-27
                                # lunch-box fix — category-blind now.
                                f"nobody ever shows — measured, on camera"),
            "surprise": (f"it never did — seven days, {zeroed}"),
            # D27 (judge loop, cycle 10): review-format verdict who-for — the
            # verdict always names the buyer, not just BUY/SKIP.
            # D76 (judge loop, cycle 19): compound-object who-for wins over the
            # category lookup — a feeder review's buyer is a birder, not a
            # camera shopper.
            "who_for": (compound_slots["who_for"]
                        if compound_slots and "who_for" in compound_slots
                        else next(
                            (v for k, v in CATEGORY_WHO.items() if k in category),
                            DEFAULT_WHO.format(category=category,
                                             category_s=plural(category)))),
            # D56 (judge loop, cycle 15): positive-proof clause for review
            # payoffs — the purpose fulfilled, spoken at the payoff beat.
            # D76 (judge loop, cycle 19): compound-object proof wins — the proof
            # names what the object delivered ("birds on camera"), not the
            # feature's survival.
            "purpose_proof": (compound_slots["purpose_proof"]
                              if compound_slots and "purpose_proof" in compound_slots
                              else next(
                                  (v for k, v in CATEGORY_PURPOSE_PROOF.items()
                                   if k in category),
                                  DEFAULT_PURPOSE_PROOF)),
            # D11 (judge loop, cycle 5): the two hardcoded rehook {action} slots
            # ("I dim the room" / "I flip it over") defeated D2's event-specific
            # contract on every non-lamp product. Pets niche gets real events.
            # D13-fix (judge loop, cycle 6): action strings are verb phrases with
            # NO leading "I" — the deck template "when I {action}" rendered
            # "when I I dim the room". Defaults are category-aware so every
            # niche gets an event-shaped action, not just pets.
            # D58 (judge loop, cycle 15, extends D44): SPOKEN-SLOT SCREEN. The old
            # default injected a camera command ("show X on camera") into a
            # SPOKEN action slot — a stage direction the presenter would voice
            # as nonsense. Spoken defaults use presenter actions only; camera
            # grammar lives in the shot list, never in VO.
            # D76 (judge loop, cycle 19): compound-object edu action wins over the
            # niche default — a bird feeder must not inherit the pet-hair
            # "fur-covered couch" event.
            # D82 (judge loop, cycle 20): D58 closed the camera-command-in-spoken-
            # slot class for the DEMO channel ("zoom in on the detail..." →
            # presenter-neutral default), but the EDU channel kept performer
            # imperatives in BOTH defaults: the beat-level fallback "show the
            # {category} up close on camera" (which the showcase branch hits on
            # EVERY run — its early return skips the parse-time dict) and the
            # parse-time "hold the {category} up where you can see every
            # edge". Both render inside spoken re-hooks ("But here's the part
            # nobody shows you — show the find up close on camera." on
            # seed 923): the presenter would say the camera move out loud —
            # D58's exact violation, edu channel. Presenter-neutral events;
            # the shot list owns camera moves.
            "edu_action": (compound_slots["edu_action"]
                           if compound_slots and "edu_action" in compound_slots
                           else ("the fur-covered couch, start to finish, "
                                 "one take"
                                 if niche == "pets"
                                 else f"the {category}, edge to edge, no cuts")),
            # D41 (judge loop, cycle 12): the parse-time default echoed the demo
            # beat's own action verbatim ("I put it through the real-world
            # test" / "put the pad through the real-world test, live") — a
            # re-hook that restates the beat burns its retention job. The
            # default is now a FORWARD event (new loop), never the beat's.
            # D58 (judge loop, cycle 15): "zoom in on the detail..." was a camera
            # command in a spoken slot — the presenter would say "zoom in" out
            # loud. The default is now a presenter-neutral event; the shot list
            # decides the camera move.
            # D76b (judge loop, cycle 19): compound-object demo action wins —
            # the pets default was hardcoded to the roller.
            # D96 (judge loop, cycle 23): the non-pets default was the
            # category-blind meta-generic "the detail the box never shows, up
            # close" — a D15-class self-violation (re-hook defaults must be
            # category-aware events per D2). The default is now the demo test
            # event itself, so the re-hook promises the beat's actual test.
            "demo_action": (compound_slots["demo_action"]
                            if compound_slots and "demo_action" in compound_slots
                            else ("hold the roller up after one full swipe"
                                  if niche == "pets"
                                  else _dt_pair[0])),
            "demo_test": _dt_pair}

def overlay_truncate(s, max_words=3):
    # hook playbook §4: frame-0 on-screen text ≤3 words, works muted
    # D17 (judge loop, cycle 7): naive words[:3] sliced mid-phrase — "I tested
    # car headrest hook for 7 days" rendered "I TESTED CAR". Strip leading
    # pronoun-verb boilerplate ("I tested"/"I tried"/"I stopped"...) so the
    # truncation lands on a phrase boundary and names the product/concept.
    # D47 (judge loop, cycle 13): day-counter hooks open with "Day N of my X"
    # ("Day 14 of my 5AM routine" truncated to "DAY 14 OF") — strip the
    # day-counter prefix too so the overlay names the concept ("5AM ROUTINE").
    words = s.strip().split()
    stripped = re.sub(
        r"^(i|we|you)\s+(tested|tried|stopped|quit|started|bought|built|"
        r"fixed|used|using|reviewed|review|gave\s+up)\s+"
        r"(the|a|an|my|this|these|that)?\s*"
        r"|^(this|these|here'?s)\s+(is|are)\s+(the|a|an|my)?\s*"
        r"|^(day|week|month)\s+\d+\s+(of\s+)?(the|a|an|my|this)?\s*",
        "", s.strip(), flags=re.I)
    if stripped.strip():
        words = stripped.strip().split()
    # D17b (judge loop, cycle 15): leading-strip fixed the front, but
    # truncation can dangle a function word at the END — "Nobody mentions the
    # lid flaw" rendered "NOBODY MENTIONS THE". Strip trailing articles /
    # prepositions / conjunctions so the overlay never ends mid-phrase.
    out = words[:max_words]
    while len(out) > 1 and out[-1].lower() in (
            "the", "a", "an", "of", "to", "for", "on", "in", "at", "by",
            "with", "and", "or", "but", "my", "your", "his", "her", "its",
            "their", "this", "that", "these", "those", "is", "are", "as"):
        out = out[:-1]
    # D109 (judge loop, cycle 27): the truncation can land mid-phrase and the
    # D17b trailing strip then drops the hook's payoff noun — "Nobody mentions
    # the box flaw" (seed 934) rendered "NOBODY MENTIONS", an overlay naming
    # nothing. When the strip freed slots, refill from the sentence TAIL: the
    # final content word sits in the payoff-noun position in flaw/bold-claim
    # hooks ("... the box flaw" -> "NOBODY MENTIONS FLAW").
    func_words = ("the", "a", "an", "of", "to", "for", "on", "in", "at", "by",
                  "with", "and", "or", "but", "my", "your", "his", "her",
                  "its", "their", "this", "that", "these", "those", "is",
                  "are", "as")
    if len(out) < max_words and len(out) < len(words[:max_words]):
        tail = next((w for w in reversed(words)
                     if w.lower() not in func_words), None)
        if tail and tail.lower() not in (w.lower() for w in out):
            out = out + [tail]
    return " ".join(out).upper()

def word_truncate(s, n=30):
    s = s.strip()
    if len(s) <= n: return s.upper()
    cut = s[:n].rsplit(" ", 1)[0]
    return (cut if cut else s[:n]).upper()

# D63 (2026-09-27, user verdict: "the script sounded like a robot"): SPOKEN-VOICE
# PASS. Dialogue is scored as SPOKEN, not written. The banks are written in
# explainer/copywriter voice ("The science is simple:", "The wax coats each
# flyaway") — a TTS read of ad copy sounds like an ad, i.e. a robot. This pass
# rewrites final dialogue/rehook strings into first-person spoken voice:
# contractions enforced, third-person product-description openers flipped to
# first person, textbook framings replaced with spoken ones. Applied in
# generate() so GATE 1's D43 word-budget checks the final spoken strings.
# Idempotent: no pattern matches its own output, so re-application is safe.
VOICE_REWRITES = [
    # textbook/explainer framings -> spoken framings
    (re.compile(r"\bThe science is simple:"), "Here's why it actually works:"),
    (re.compile(r"Three things to check before you buy any ([\w ]+?):"),
     r"Three things I check before buying any \1:"),
    # D63 (pipeline v2): multi-word categories ("Most resistance bands set
    # fail because") slipped past the one-word pattern ungrammatical.
    (re.compile(r"\bMost (?!of these\b)[\w'-]+(?: [\w'-]+){0,3} fail because"),
     r"Most of these fail because"),
    (re.compile(r"Here's the problem (.+?) actually solves:"),
     r"Here's what \1 actually fixes:"),
    # third-person product-description openers -> first person ("The wax coats
    # each flyaway" is copy; "It coats each flyaway" is a person talking)
    (re.compile(r"\bThe (?:wax|cream|serum|oil|gel|stick|product|formula|mask|spray) "
                r"(coats|covers|lasts|feels|works|dries|sets|lays|kills|fixes) "),
     r"It \1 "),
]
# D63 (pipeline v2): an auxiliary never contracts at the END of a sentence or
# clause — "Here it is." / "That's what it is." / "Here you are." are English,
# "Here it's." is not. _CLAUSE_END guards the positive contractions.
_CLAUSE_END = r"(?![ \t]*(?:[.,;:!?)\u2014\u2013]|$))"
VOICE_CONTRACTIONS = [
    (re.compile(r"\bit is\b" + _CLAUSE_END), "it's"),
    (re.compile(r"\bthat is\b" + _CLAUSE_END), "that's"),
    (re.compile(r"\bI am\b" + _CLAUSE_END), "I'm"), (re.compile(r"\bdo not\b"), "don't"),
    (re.compile(r"\bcannot\b"), "can't"), (re.compile(r"\bwill not\b"), "won't"),
    (re.compile(r"\byou are\b" + _CLAUSE_END), "you're"),
    (re.compile(r"\bwe are\b" + _CLAUSE_END), "we're"),
    (re.compile(r"\bthey are\b" + _CLAUSE_END), "they're"), (re.compile(r"\bdid not\b"), "didn't"),
    (re.compile(r"\bwas not\b"), "wasn't"), (re.compile(r"\bwere not\b"), "weren't"),
    (re.compile(r"\bhave not\b"), "haven't"), (re.compile(r"\bhas not\b"), "hasn't"),
    (re.compile(r"\bwould not\b"), "wouldn't"), (re.compile(r"\bcould not\b"), "couldn't"),
    (re.compile(r"\bshould not\b"), "shouldn't"), (re.compile(r"\bis not\b"), "isn't"),
    (re.compile(r"\bare not\b"), "aren't"),
]

def humanize_dialogue(s):
    """D63: rewrite a dialogue/rehook string into spoken voice. Idempotent."""
    if not s:
        return s
    for pat, rep in VOICE_REWRITES:
        s = pat.sub(rep, s)
    for pat, rep in VOICE_CONTRACTIONS:
        # case-preserving contraction: "That is" -> "That's", "it is" -> "it's"
        def _rep(m, rep=rep):
            t = m.group(0)
            return rep[0].upper() + rep[1:] if t[0].isupper() else rep
        s = re.sub(pat.pattern, _rep, s, flags=re.IGNORECASE)
    return s

class RehookDeck:  # no repeated re-hook inside one script
    def __init__(self, rng, ai=False):
        self.rng = rng; self.deck = []
        # D137 (pipeline v2): the AI lane never deals a first-person frame
        # ("And then I noticed something weird — ...": 237/990 AI runs).
        self.templates = [r for r in REHOOKS if not (ai and _ai_claims(r))]
    def draw(self, no_when_i=False):
        # D86 (judge loop, cycle 20): the "when I {action}" template needs a
        # verb-phrase action; the D58/D82 presenter-neutral defaults are noun
        # phrases ("the detail the box never shows, up close") — drawing it
        # rendered "Now watch what happens when I the detail..." on seed 923
        # (D69-class grammar break, verified). Callers whose action is a
        # neutral default exclude that one template; the other seven still
        # vary (D2), and no template repeats within a script.
        if not self.deck:
            self.deck = self.templates[:]; self.rng.shuffle(self.deck)
        if not no_when_i:
            return self.deck.pop()
        for i, tmpl in enumerate(self.deck):
            if "when I {action}" not in tmpl:
                return self.deck.pop(i)
        return self.deck.pop()

class Bank:  # draw unique lines from any template bank
    def __init__(self, rng, items):
        self.rng = rng; self.items = items; self.deck = []
    def draw(self):
        if not self.deck:
            self.deck = self.items[:]; self.rng.shuffle(self.deck)
        return self.deck.pop()

ADVICE_BEATS = [  # talking-head / advice mode (Robins-style breakdowns)
 "The number-one mistake: {mistake}. Everyone does it.",
 "Here's the fix — {fix}. Takes thirty seconds.",
 "{authority} figured this out years ago: {authority_quote}.",
 "I audited fifty {topic_noun} videos. Same pattern every time: {pattern}.",
 "The algorithm rewards {reward}. Most people optimize for {wrong}.",
 "Two things separate videos that pop from videos that die: {thing1} and {thing2}.",
]

STORY_BEATS = [  # pov-vlog mode: episodic, participatory
 "Day {n} of {quest}: {event}.",
 "Nobody believed {claim}. Then {turn}.",
 "The plan was {plan}. Reality had other ideas.",
 "POV: you're {situation} and {twist}.",
]

# D143 (pipeline v2): BANK VARIANTS. Long bank lines carry shorter spoken
# forms with the SAME slots and the same claim; _fit_timeline swaps in the
# longest form that fits the duration budget before it ever trims (and a trim
# only cuts at a sentence/clause boundary — never mid-clause). Keys are the
# raw templates; every form is rendered with the template's own slots.
BEAT_SHORT_FORMS = {
 # EDU_BEATS
 "Here's the problem {product} actually solves: {problem}.":
     ["Here's what it fixes: {problem}."],
 "Most {category_s} fail because {flaw}. This one doesn't.":
     ["Most {category_s} fail at daily use. This one doesn't."],
 "The science is simple: {mechanism}.": ["{mechanism}."],
 "{authority} said it best — {authority_quote}.":
     ["{authority}'s rule: {authority_quote}."],
 "Three things to check before you buy any {category}: {check1}, {check2}, {check3}.":
     ["Three checks: build, setup time, no gimmicks."],
 # DEMO_BEATS
 "Watch: {action}. See that? {result}.": ["Watch: {action}. {result}.", "Watch: {action}."],
 "The detail that sold me: {detail}.": ["The detail: {detail}."],
 # IMPERFECTION_BEATS (human only — D12 <=12 words, 3–5s)
 "Honest start: I thought {this_category} {was} a scam. The last one died.":
     ["Honest start: I thought {this_category} {was} a scam.",
      "Honest start: I doubted {this_category}."],
 "Confession: I fumbled the first try. Left it in.": ["Confession: I fumbled the first try."],
 "Nobody's paying me. The first one I tried was garbage.":
     ["The first one I tried was garbage."],
 "Real talk: my last set of bands snapped mid-rep.": ["My last bands snapped mid-rep."],
 "Honest start: my last ones rolled up by day two.": ["My last ones rolled up by day two."],
 "Real talk: my last sound machine died at 3AM. Twice.":
     ["Real talk: my last sound machine died at 3AM.", "My last one died at 3AM."],
 "Honest start: the last one rattled and hissed all night.": ["The last one rattled all night."],
 # REVIEW_REJECT_BEATS / REVIEW_REJECT_BEATS_AI
 "Full disclosure: I tried {n} {category_s} before this one. Not one lasted a week.":
     ["I tried {n} {category_s} first. Not one lasted a week."],
 "Before this one, I tried {n} {category_s}. Broken, returned, or lying in the listing.":
     ["Before this one, I tried {n} {category_s}."],
 "Full disclosure: I tried {n} {category_s} first. They slid in turns or cooked in the sun.":
     ["I tried {n} {category_s} first. They slid or cooked."],
 "Full disclosure: I tried {n} {category_s} first. They snapped mid-rep or rolled up.":
     ["I tried {n} {category_s} first. They snapped or rolled."],
 "Full disclosure: {n} other {category_s} made the shortlist. Each one got cut.":
     ["{n} other {category_s} made the shortlist. All cut."],
 "The shortlist had {n} other {category_s}. Broken, returned, or lying in the listing.":
     ["The shortlist had {n} other {category_s}."],
 "Full disclosure: {n} other {category_s} made the shortlist. They slide in turns or cook in the sun.":
     ["{n} other {category_s} made the shortlist. They slide or cook."],
 "Full disclosure: {n} other {category_s} made the shortlist. They snap mid-rep or roll up.":
     ["{n} other {category_s} made the shortlist. They snap or roll."],
 # ADVICE_BEATS
 "The number-one mistake: {mistake}. Everyone does it.": ["The number-one mistake: {mistake}."],
 "Here's the fix — {fix}. Takes thirty seconds.": ["The fix: {fix}."],
 "{authority} figured this out years ago: {authority_quote}.": ["The rule: {authority_quote}."],
 "I audited fifty {topic_noun} videos. Same pattern every time: {pattern}.":
     ["Same pattern every time: {pattern}."],
 "The algorithm rewards {reward}. Most people optimize for {wrong}.":
     ["The algorithm rewards {reward}, not {wrong}."],
 "Two things separate videos that pop from videos that die: {thing1} and {thing2}.":
     ["Two things matter: {thing1} and {thing2}."],
}

# D8 (judge loop, cycle 4): journey grammar for SELF-CHALLENGE concepts.
# Product-slot templates ("Day N of {product} testing", "the {category} test
# the box never shows") are BANNED here — challenge beats name days,
# withdrawal, and the measurable behavior, never a box or a price.
CHALLENGE_BEATS = [
 "Day {n} of no {noun}: {event}.",
 "{n} days in — {event}.",
 "The withdrawal hit on day {n}: {event}.",
 "I almost relapsed on day {n}. {event}.",
]
# D120 (judge loop, cycle 31): ABSTINENCE NOUN CLASSES. The abstinence branch's
# slots were doomscrolling-shaped for EVERY noun — measured_claim "screen time
# from 6h14m down to 47 minutes", the six CHALLENGE_EVENTS all phone/scroll
# content, expected_flop "I'd cave by day 3 and scroll harder than before",
# and the "My screen time was {before} a day" hook candidate. Seed 938's
# quit-COFFEE challenge rendered phone-grabbing events and a screen-time
# payoff — content-nonsensical (the cycle-28 WATCHED item, now systematic on
# a second noun). The noun resolves into a vice class; every abstinence slot
# (payoff, flop, surprise, verdict card, events, screen-time hook) renders
# class-native. Keyword match order matters: "drinking coffee" must hit
# caffeine before alcohol's bare "drinking"; bare "drinking" is alcohol.
# Default = screen (back-compat with the doomscrolling-class nouns the
# branch was written for).
_ABSTINENCE_CLASS_KWS = (
    ("caffeine", ("coffee", "espresso", "soda", "energy drink", "caffeinated")),
    ("sugar", ("sugar", "snacking", "candy", "sweets", "junk food")),
    ("alcohol", ("alcohol", "drinking", "beer", "wine", "smoking")),
    ("screen", ("doomscrolling", "phone", "instagram", "tiktok", "youtube",
                "netflix", "accounts", "screen",
                # D130 (judge loop, cycle 34): umbrella + platform nouns map
                # to the screen class explicitly (the old fallback returned
                # "screen" anyway — this is routing made legible, not new
                # behavior).
                "social media", "apps", "facebook", "twitter", "snapchat",
                "reddit", "threads")),
)
_ABSTINENCE_SLOTS = {
    "screen": {
        "expected_flop": "I'd cave by day 3 and scroll harder than before",
        "measured_claim": ("screen time from 6h14m a day down to 47 minutes "
                           "— screen-recorded, on camera"),
        "measured_short": "6h14m down to 47 minutes",
        "surprise": ("the hardest part was the first 48 hours — and the "
                     "quietest evenings ended up being the win"),
        "verdict_label": "SCREEN TIME: 6h14m → 47min",
        # D142: <=3-token card surprise; D89: the CTA's one-word swap noun
        "card_surprise": "calm evenings", "swap": "scroll",
        "events": "CHALLENGE_EVENTS",
        "frame0": "screen-time graph",
    },
    "caffeine": {
        "expected_flop": "I'd cave by day 3 and mainline espresso again",
        "measured_claim": ("sleep quality up and the 3pm crash gone — "
                           "logged on camera"),
        "measured_short": "deeper sleep, no 3pm crash",
        "surprise": ("the headaches only lasted 4 days — and my afternoons "
                     "got quieter, not louder"),
        "verdict_label": "SLEEP + ENERGY: crash gone",
        "card_surprise": "headaches: 4 days", "swap": "coffee",
        "frame0": "coffee cup mid-pour",
        "events": [
            "the 3pm headache I tried to bargain with",
            "I caught myself reaching for the coffee maker on autopilot",
            "the morning ritual that felt wrong without the cup",
            "replacing the ritual with a walk, and the walk won",
            "the money I stopped spending on lattes — I counted it",
        ],
    },
    "sugar": {
        "expected_flop": "I'd cave by day 3 and raid the snack drawer",
        "measured_claim": ("no 4pm energy crashes and cravings gone by "
                           "week 2 — logged on camera"),
        "measured_short": "no crashes, cravings gone week 2",
        "surprise": ("the cravings only lasted 5 days — and food started "
                     "tasting louder"),
        "verdict_label": "ENERGY: crashes gone",
        "card_surprise": "cravings: 5 days", "swap": "sugar",
        "frame0": "open snack drawer",
        "events": [
            "the evening craving I tried to negotiate with",
            "I caught myself opening the snack drawer on autopilot",
            "the 4pm slump that used to need sugar",
            "replacing the drawer raid with a walk, and the walk won",
            "the boredom hunger I was scared of — it came, then it passed",
        ],
    },
    "alcohol": {
        "expected_flop": "I'd cave by day 3 and pour a drink",
        "measured_claim": ("sleep deepened and I saved what I used to "
                           "spend — logged on camera"),
        "measured_short": "deeper sleep, money back in pocket",
        "surprise": ("week 2 sleep was the thing I didn't expect — and my "
                     "mornings got easier"),
        "verdict_label": "SLEEP + WALLET: both up",
        "card_surprise": "week-2 sleep", "swap": "nightcap",
        "frame0": "full drink on the bar",
        "events": [
            "the Friday night I almost poured one",
            "the social itch — everyone drinking around me",
            "the wind-down ritual I had to rebuild",
            "replacing the nightcap with a walk, and the walk won",
            "the money I wasn't spending — I counted it",
        ],
    },
}
def _abstinence_class(noun):
    low = noun.lower()
    for cls, kws in _ABSTINENCE_CLASS_KWS:
        if any(k in low for k in kws):
            return cls
    return "screen"
def _abstinence_events(cls):
    ev = _ABSTINENCE_SLOTS[cls]["events"]
    return CHALLENGE_EVENTS if ev == "CHALLENGE_EVENTS" else ev
CHALLENGE_EVENTS = [
 "the phantom-scroll itch",
 "I caught myself reaching for a phone that wasn't in the room",
 "the evening boredom I was scared of — it came, then it passed",
 "the relapse I almost filmed but didn't",
 "replacing the scroll with a walk, and the walk won",
 "the hour I used to lose to the feed — I got it back",
]
# D137 (pipeline v2): the AI lane's form of the event lines that match
# lexicon.AI_FIRST_PERSON ("I tried", "I used") — same beat, curator voice.
AI_EVENT_REWRITES = {
 "the hour I used to lose to the feed — I got it back":
     "the hour the feed used to eat — it comes back",
 "the 3pm headache I tried to bargain with": "the 3pm headache that tries to bargain",
 "the evening craving I tried to negotiate with": "the evening craving that tries to negotiate",
}
CHALLENGE_HOOKS = [  # ≤8-word first sentence enforced at pick_hook
 "I stopped {noun} for {span}. Here's what actually happened.",
 "Thirty days with no {noun}. The quiet won.",
 "My screen time was {before} a day. Then I quit {noun}.",
 # D113 (judge loop, cycle 28): D73's total-word filter (correct) starved the
 # challenge branch — all three templates above exceed 8 TOTAL words for any
 # multi-word noun ("Thirty days with no 500 accounts. The quiet won." = 9),
 # so the fallback fired and rendered "Nobody mentions the challenge flaw"
 # (seed 935) — the bare category word as content, a D9 slot-hygiene
 # violation. This candidate names the abstinence + span in ≤8 words total
 # for nouns up to 2 words ("I quit 500 accounts for 30 days." = 7).
 "I quit {noun} for {span}.",
]

# D67 (judge loop, cycle 17): PRACTICE-CHALLENGE journey grammar. The D8
# abstinence grammar ("Day {n} of no {noun}", withdrawal events, screen-time
# payoff) is wrong for practice challenges ("I cooked every meal at home
# for 30 days") — the presenter BUILDS a streak, never breaks one. Stakes
# are the streak (D53 grammar: practices fail at relapse, never at a
# product), not withdrawal from a vice. The hook is PINNED (D52 doctrine:
# streak genres pin the hook to the day-count; the payoff names the same
# count — D35 contract pairing). First sentence ≤8 words counted on the
# RENDERED string (D61): "Day {span_n} of {gerund} {≤4 obj tokens}." is
# ≤8 by construction (Day, count, of, gerund + ≤4 tokens).
_PRACTICE_GERUND = {
 "cooked": "cooking", "ran": "running", "walked": "walking",
 "meditated": "meditating", "woke": "waking", "read": "reading",
 "wrote": "writing", "lifted": "lifting", "trained": "training",
 "saved": "saving", "drank": "drinking", "fasted": "fasting",
 "journaled": "journaling", "studied": "studying",
 "stretched": "stretching", "cleaned": "cleaning", "danced": "dancing",
 "swam": "swimming", "biked": "biking", "unplugged": "unplugging",
 "ate": "eating",
}
PRACTICE_CHALLENGE_BEATS = [
 "Day {n} of {noun}: {event}.",
 "{n} days in — {event}.",
 "I almost quit on day {n}. {event}.",
 # D99 (judge loop, cycle 24): the old template read "The {span} wall hit"
 # with span="30 days" — "The 30 days wall hit on day 2" shipped
 # ungrammatical (D69/D61-class; seed 927). The wall lands ON day {n}:
 # hyphenated compound adjective, span_n slot.
 "The {span_n}-day wall hit on day {n}: {event}.",
]
PRACTICE_CHALLENGE_EVENTS = [
 "the old habit knocking at 11pm — I didn't answer",
 # D104 (judge loop, cycle 25): the old event read "the day-four wall
 # everyone warned about" — a baked-in day number that combined with
 # templates carrying a DIFFERENT day ("1 day in — the day-four wall...",
 # "I almost quit on day 2. The day-four wall...", seeds 928/933),
 # violating the maker's own day-counter consistency intent (D47 pinned
 # day-counter, D102 frame-0 day matches hook, D69/D61 grammar class).
 # Day-number content lives ONLY in beat templates; event banks carry
 # day-agnostic content. Replacement keeps the wall concept's human
 # texture without a date: any template day stays coherent.
 "the sloppy session that still counted",
 "the attempt I ruined and finished anyway",
 "the shortcut that saved the streak",
 "the small win nobody clapped for",
 "the almost-quit moment I didn't film",
]
PRACTICE_CHALLENGE_HOOK = "Day {span_n} of {noun}. Here's what changed."

# D22 (judge loop, cycle 8): listicle/showcase hooks for the "things in my X
# that just make sense" class (julianna_claire product-roundup grammar:
# negative-command/listicle, price-anchored, "POV: your X is missing these").
# ≤8-word first sentences; {domain} = the "things in my X" domain.
# D47 (judge loop, cycle 13): routine hooks for the "my 5AM routine before
# work" class. The day-counter hook is PINNED (not drawn) — the genre's
# contract is the streak, and the hook must name the same day-count the
# payoff delivers (D35 contract pairing). {time} = extracted clock label,
# {streak} = day count. ≤8-word first sentence like every other family.
ROUTINE_HOOKS = [
 "I wake up at {time}. Every single day.",
 "My alarm goes off at {time}. No snooze.",
 "POV: it's {time} and you're already winning.",
 "I stopped sleeping in. It rewired everything.",
]
ROUTINE_HOOK_PINNED = "Day {streak} of my {time} routine. Here's what changed."

SHOWCASE_HOOKS = [
 "Things in my {domain} that just make sense.",
 "POV: your {domain} is missing these.",
 "Every {domain} needs at least one of these.",
]

# D42 (judge loop, cycle 12): DETERMINER RULE helper — spoken dialogue never
# uses a bare product noun. "the" (neutral) beats "this" (avoids "this about
# this X" collisions in templates like "I almost didn't post this about
# {product}").
_DET_OPENERS = ("the ", "a ", "an ", "this ", "that ", "these ", "those ",
                "my ", "your ", "his ", "her ", "its ", "our ", "their ")
def _det(noun):
    return noun if noun.lower().startswith(_DET_OPENERS) else f"the {noun}"

def _render_hook_line(ctx, rng, line, auth):
    slots = {
        # D42 (judge loop, cycle 12): DETERMINER RULE — spoken dialogue never
        # uses a bare product noun ("I tested under-desk walking pad" fired
        # ungrammatical; the cycle-10 queued hygiene note, now live). Bare
        # product names in dialogue get "the" unless they already open with a
        # determiner/demonstrative/possessive.
        "product": _det(ctx["product"]), "price": ctx["price"],
        "category": ctx["category"], "ndays": ctx.get("ndays") or rng.choice([3, 7, 14, 30]),
        # D36: price may be None — guard the int() (belts-and-braces behind
        # D26's named-competitor gate; the {expensive} hook dies above anyway).
        # pipeline v2 crash fix: int("12.99") raised ValueError on every
        # decimal-price prompt (baseline: 30/990 runs crashed) — float first.
        "expensive": (f"my ${round(float(ctx['price'])*8)} {ctx['category']}"
                      if ctx.get("price") else f"a premium {ctx['category']}"),
        "flaw": f"the {ctx['category']} flaw everyone ignores",
        "moment": "3AM test", "proof": f"{rng.choice(['4.9★','12,000+ orders','sold out twice'])}",
        "before": "chaos mornings", "after": "wake up calm",
        # D47 (judge loop, cycle 13): routine slots — {time} (extracted clock
        # label, e.g. "5AM"), {label} (full routine label), {streak} (day
        # count). All default-safe; only populated for concept=routine.
        "time": ctx.get("routine_time", "5AM"),
        "label": ctx.get("routine_label", "the routine"),
        "streak": ctx.get("streak", "14"),
        "timespan": "one week", "mistake": f"buying {ctx['category']} on looks alone",
        "common": f"overpaying for {ctx['category']}",
        "identity": "skeptic", "persona_note": "an AI, so I test everything twice",
        "situation": "half asleep at 6AM",
        "thing": "morning routine",
        # D8 challenge slots (only populated for concept=challenge; inert otherwise)
        "noun": ctx.get("challenge_noun", ctx["category"]),
        "span": ctx.get("span", "30 days"),
        # D67 (judge loop, cycle 17): practice-challenge pinned hook names
        # the day-count — needs the raw count, not the "30 days" string.
        "span_n": ctx.get("span_n", "30"),
        # D22 (judge loop, cycle 8): showcase {domain} slot for listicle hooks.
        "domain": ctx.get("domain", ctx["category"]),
        "before": "6 hours",
    }
    if auth:
        slots.setdefault("authority", auth)
    # pipeline v2 crash fix: the old double .format() re-parsed rendered text,
    # so a literal "{...}" in the prompt raised KeyError (baseline: 30/990
    # runs). generate() strips braces from the prompt (D31); a single pass
    # with the full slot dict renders every template.
    return line.format(**slots)

def _screen_pin(rendered):
    # D73 (judge loop, cycle 18): the D47/D67 pinned hooks bypass the
    # pick_hook draw — "Day 14 of my 5AM routine. Here's what changed." (9w)
    # and "Day 30 of cooking every meal at home. Here's what changed." (11w)
    # shipped over the charter's verbal ≤8-words budget in a 2.5s window.
    # The pin's first sentence carries the day-counter contract by
    # construction (≤8w); the "Here's what changed" coda is dropped when the
    # total exceeds budget.
    if len(rendered.split()) <= 8:
        return rendered
    return rendered.split(".")[0].strip() + "."

def pick_hook(ctx, rng):
    # D6 (judge loop, cycle 3): hook-stack budget enforced at the gate — the
    # verbal hook's FIRST SENTENCE must be ≤8 words (playbook §1). Draw up to
    # 6 candidates; take the shortest first sentence; never emit >8 words.
    fam = NICHE_HOOK.get(ctx["niche"], "curiosity-gap")
    if _PACK and not _NO_RESEARCH:  # research bridge: live niche rankings override static map
        live = (_PACK.get("niche_hooks") or {}).get(ctx["niche"])
        if live and live[0]["category"] in HOOKS:
            fam = live[0]["category"]
    auth = NICHE_AUTHORITY.get(ctx["niche"])
    # D47 (judge loop, cycle 13): routine hooks are PINNED, not drawn — the
    # genre's contract is the streak, and the hook must name the same
    # day-count the payoff delivers (D35 pairing). No draw means no chance of
    # emitting "I wake up at 5AM" while the payoff says "Day 14".
    if ctx.get("concept") == "routine":
        return "day-counter", _screen_pin(_render_hook_line(ctx, rng, ROUTINE_HOOK_PINNED, auth))
    # D67 (judge loop, cycle 17): practice-challenge hooks are PINNED like
    # D52's routine pin — a drawn hook can name a different contract than
    # the payoff delivers ("I stopped X" grammar on a streak the presenter
    # is building). The pin names the day-count the payoff verdicts (D35).
    if ctx.get("challenge_type") == "practice":
        return "day-counter", _screen_pin(_render_hook_line(ctx, rng, PRACTICE_CHALLENGE_HOOK, auth))
    candidates = []
    # D8: challenge concepts never draw product-comparison hook lines —
    # "I tested {product} for {ndays}" is banned here (it produced
    # "I tested 30 days for 30 days"). D22 (judge loop, cycle 8): showcase
    # concepts draw listicle hooks ("POV: your apartment is missing these"),
    # never the SKU-demo family.
    lines = CHALLENGE_HOOKS if ctx.get("concept") == "challenge" else \
            SHOWCASE_HOOKS if ctx.get("concept") == "showcase" else HOOKS[fam]
    # D120 (judge loop, cycle 31): the screen-time hook candidate ("My screen
    # time was {before} a day. Then I quit {noun}.") is doomscrolling-shaped —
    # it shipped on the quit-coffee seed (938) behind the D73 word filter.
    # Fire it only on screen-class abstinence nouns.
    if (ctx.get("concept") == "challenge" and
            ctx.get("challenge_type") == "abstinence" and
            (ctx.get("abstinence_class") or "screen") != "screen"):
        lines = [l for l in lines if "screen time" not in l.lower()] or lines
    # D29 (judge loop, cycle 11): niche-gated extra hooks join the family's
    # candidates — the wellness sleep-claim beats the family on word count.
    lines = lines + NICHE_HOOK_EXTRA.get(ctx.get("niche"), [])
    # D26 (judge loop, cycle 10): the "{expensive}" name-brand comparison
    # ("I replaced my $160 name-brand mount") is retired unless the prompt
    # names a competitor — an unverified price-vs-brand claim burned D19's
    # trust contract across cycles 5/6/7 and evaded it via hooks in cycle 10.
    if not ctx.get("named_competitor"):
        lines = [l for l in lines if "{expensive}" not in l] or lines
    # D37 (judge loop, cycle 12): price-bearing hooks ("the best {category}
    # under ${price}") die when the prompt named no price — same gate as
    # D26's {expensive} filter (never render "under $None").
    if not ctx.get("price"):
        lines = [l for l in lines if "{price}" not in l] or lines
    # D35 (judge loop, cycle 11): HOOK-PAYOFF CONTRACT PAIRING (extends D5).
    # The industry-secret hook promises a SECRET the demo/review payoff never
    # reveals — cycle 11 fired "The machine industry doesn't want you to know
    # this" + a durability payoff (secret → mechanism = broken contract).
    # Demo/review formats can't deliver a named secret, so the template is
    # gated out of those formats entirely.
    if ctx.get("fmt") in ("demo", "review"):
        lines = [l for l in lines if "industry" not in l] or lines
    # D130 (judge loop, cycle 34): CHALLENGE hook pre-filter by the D73
    # total-word budget BEFORE the draw. Three of the four CHALLENGE_HOOKS
    # templates are multi-sentence and can NEVER pass the ≤8-total filter
    # for multi-word nouns — only the D113 candidate ("I quit {noun} for
    # {span}.") is budget-feasible there, so it won on a lucky draw. Seed
    # 946 drew six losers and shipped the D113 fallback "Nobody mentions
    # no social media apps." Drawing only from budget-feasible lines makes
    # the hook deterministic-by-construction; the fallback stays as
    # belt-and-suspenders. (Challenge renders are rng-free — noun/span —
    # so pre-rendering costs no draw state.)
    if ctx.get("concept") == "challenge":
        feasible = [l for l in lines
                    if (lambda r: len(r.split('.')[0].split()) <= 8
                        and len(r.split()) <= 8)
                    (_render_hook_line(ctx, rng, l, auth))]
        lines = feasible or lines
    for _ in range(6):
        line = rng.choice(lines)
        rendered = _render_hook_line(ctx, rng, line, auth)
        first = rendered.split('.')[0].split()
        candidates.append((len(first), len(rendered.split()), rendered))    # D61 (judge loop, cycle 15): HARD cap — "take the shortest" still emitted
    # 9+ words whenever every draw was over budget (cycle 15: a 5-word {flaw}
    # slot turned a 4-word template into a 9-word hook while the output printed
    # "First sentence ≤8 words"). Filter to ≤8 first; guaranteed-short
    # fallback last, verified against the same budget it enforces.
    # D73 (judge loop, cycle 18, extends D61 + D54): the D61 cap only checked
    # the FIRST SENTENCE, but the viewer hears the WHOLE hook line in the
    # 0.5–3.0s window (2.5s × 1.15 × 3 = 8.6 words D43 budget) and the loop
    # charter scores "verbal ≤8 words" on the full verbal hook. Seed-921
    # shipped "I tested the magnetic eyelashes for 7 days. The result
    # surprised me." — 8-word first sentence, 12 words total, in a 2.5s
    # window (~290 wpm, unperformable per F86). Filter candidates on total
    # words too.
    ok = [c for c in candidates if c[0] <= 8 and c[1] <= 8]
    if ok:
        return fam, min(ok, key=lambda c: (c[0], c[1]))[2]
    # D113 (judge loop, cycle 28): the generic fallback renders the bare
    # category word as content — on the challenge branch that's "Nobody
    # mentions the challenge flaw." (seed 935), a D9 slot-hygiene violation
    # ("challenge flaw" names nothing). Challenge concepts get a
    # noun-carrying fallback; the same ≤8-word budget guards it.
    if ctx.get("concept") == "challenge":
        fb = f"Nobody mentions no {ctx.get('challenge_noun', ctx['category'])}."
    else:
        fb = f"Nobody mentions the {ctx['category']} flaw."
    if len(fb.split()) <= 8:
        return fam, fb
    return fam, "Nobody mentions it."

def build_beats(ctx, duration, rng, fmt, presenter="ai"):
    D = duration
    beats = []
    deck = RehookDeck(rng, ai=(presenter == "ai"))   # D137
    # D85 (judge loop, cycle 20): the borrowed-authority template "{authority}
    # said it best — {authority_quote}." fired for niches with NO mapped
    # authority — the placeholder "the best in the game said it best — design
    # the environment, not the willpower." shipped on a car-finds video (seed
    # 923). D29 already ruled that an unnamed "best" is an adjective (A2);
    # the template now joins the draw only for niches with a NAMED authority —
    # same filter mechanics as D26's {expensive} gate on the demo bank.
    edu_bank = Bank(rng, EDU_BEATS if NICHE_AUTHORITY.get(ctx.get("niche"))
                    else [t for t in EDU_BEATS if "{authority}" not in t])
    demo_bank = Bank(rng, [t for t in DEMO_BEATS
                           # D26 (judge loop, cycle 10): same gate as hooks —
                           # "Compare it to {expensive}" dies without a named
                           # competitor (D19's trust contract).
                           if "{expensive}" not in t or ctx.get("named_competitor")])
    advice_bank = Bank(rng, ADVICE_BEATS)
    story_bank = Bank(rng, STORY_BEATS)
    def t(x): return round(x, 1)
    # D143: initialised up front (replaces the locals().get() hack) — every
    # branch that pins a payoff card sets it. *_alts are the spoken variants
    # (longest first) the timeline budget may swap in; series_next is the
    # CTA's promised next episode (D146).
    payoff_on_screen = None
    payoff_alts = bait_alts = cta_alts = None
    series_next = None
    # D13 (judge loop, cycle 6): FORMAT ≠ CONTENT MODE, v2. Concept routing is
    # tri-state: product prompts get product beats, advice topics get advice
    # beats, challenges get journey grammar — regardless of camera format
    # (talking-head is a framing choice, not a content mode).
    concept = ctx.get("concept", "product")
    # D47 (judge loop, cycle 13): routine is its own content mode — neither
    # product-demo nor story grammar applies.
    # D13 (pipeline v2): the last clause routed CHALLENGE concepts in demo/
    # review/transformation formats into PRODUCT grammar — "Verdict: BUY —
    # deeper sleep, no 3pm crash.", "for anyone burned by cheap challenges",
    # "Test result: ... logged on camera." (D44), and "comment CHALLENGE"
    # while the caption asks for DAY1. Journey grammar now fires for every
    # challenge regardless of camera format, as the D13 doctrine states.
    mode = "product" if concept in ("product", "showcase") else \
           "advice" if concept == "advice" else \
           "routine" if concept == "routine" else \
           "story" if concept == "challenge" else \
           "product" if fmt in ("demo", "review", "transformation") else "story"
    # 3-layer hook stack: visual 0-0.5s, verbal 0.5-1.5s, lock by 3s
    # D35 (judge loop, cycle 11): pick_hook gates the industry-secret hook
    # out of demo/review formats — it needs the format in ctx.
    ctx["fmt"] = fmt
    # D40 (judge loop, cycle 12): the transformation payoff names the same
    # day-count the hook drew ("DAY 1 vs DAY N") — pre-draw once into ctx so
    # hook and payoff stay consistent; _render_hook_line reads it back.
    if fmt == "transformation":
        ctx["ndays"] = rng.choice([3, 7, 14, 30])
    fam, hookline = pick_hook(ctx, rng)
    # D33 (judge loop, cycle 11): AUDIO-PRODUCT DEMO GRAMMAR. Sound products
    # are AUDIO-LED — the reference class (josh.harmon "Ratatouille Sounds",
    # 409K likes, 1,030 comments) lets the product's actual sound be heard
    # through the mic; "watch" is the wrong verb for a white-noise machine.
    is_audio = any(k in ctx["category"]
                   for k in ("noise", "sound", "speaker", "audio", "headphone"))
    # D81 (judge loop, cycle 20): the showcase frame-0 was apartment DNA —
    # "room-tour tracking shot" rendered on a CAR video, and "price tag
    # visible on screen" shipped with price=None: a price-bearing visual
    # direction with no price (D37 evasion channel — D37 filtered price-bearing
    # HOOKS but never the visual-direction channel, same class as D26's
    # closure of D19). Domain-scoped framing; the price-tag clause renders
    # only when the prompt named a price (never invented, D37).
    price_tag = (", price tag visible on screen" if ctx.get("price") else "")
    vis = (f"Frame 0: tracking shot through the {ctx.get('domain', 'space')} "
           f"— first find in hand{price_tag}, on-screen text already up. "
           if ctx.get("concept") == "showcase" else
           # D25 (judge loop, cycle 9): transformation opens on the PROOF, not
           # the product — before/after split-screen (linnlowes split-screen,
           # ownbyfemme showcase) with a day-stamp; narrated-only
           # transformation loses the genre's visual contract.
           # D135 (gauntlet cycle 19): frame-0 must name the SAME day-count the
           # hook drew (ctx["ndays"], D40) — "TODAY right" contradicted the
           # hook contract ("DAY 1 vs DAY 30") and the payoff card.
           f"Frame 0: BEFORE/AFTER split-screen — DAY 1 left, "
           f"DAY {ctx.get('ndays', 7)} right, "
           f"{ctx['product']} in frame, on-screen text already up. "
           if fmt == "transformation" and mode == "product" else
           f"Frame 0 MID-ACTION: hands on {ctx['product']}, object in motion. "
           # D33: audio products open with the volume-up cue — 85% watch
           # muted EXCEPT when the product IS sound; the cue converts.
           f"{'On-screen: TURN YOUR VOLUME UP. ' if is_audio else ''}"
           if mode == "product" else
           # D8: challenge story opens on the measurable problem artifact
           # (screen-time graph), not a mid-gesture — the problem is the hook.
           # D67 (judge loop, cycle 17): practice challenges open on DAY 1
           # of the streak in progress — there is no "problem state" for a
           # streak the presenter is building.
           # D98 (judge loop, cycle 24): but the verbal hook reports
           # Day {span_n} ("Day 30 of reading 10 pages every day") — frame-0
           # showing "Day 1" contradicts the hook (ashtonhall names the same
           # day in hook and visual: "Day 14 with the Hall's", 9.06M likes).
           # Frame-0 now shows the REPORTED day in progress, matching the
           # hook's day-counter.
           (f"Frame 0: Day {ctx.get('span_n', '30')} of the streak full-frame — "
            f"{ctx.get('challenge_noun','the streak')} in progress, "
            f"day-counter on screen, on-screen text already up. "
            if ctx.get("challenge_type") == "practice" else
            # D120 (judge loop, cycle 31): frame-0 problem artifact is
            # noun-class native (coffee-maker for caffeine, not a
            # screen-time graph).
            f"Frame 0: the problem state full-frame — "
            f"{_ABSTINENCE_SLOTS[(ctx.get('abstinence_class') or 'screen')]['frame0']}, "
            f"{ctx.get('challenge_noun','the habit')} at its worst, on-screen text up. "
            if ctx.get("concept") == "challenge" else
            # D47 (judge loop, cycle 13): routines open on the ALARM CLOCK /
            # phone screen — the time is the spectacle, and 5AM on a glowing
            # screen works muted. Creator mid-action getting up.
            f"Frame 0: alarm clock / phone screen full-frame — "
            f"{ctx.get('routine_time','5AM')} lit up on screen, creator mid-action "
            f"getting up, on-screen text already up. "
            if ctx.get("concept") == "routine" else
            "Frame 0 MID-ACTION: creator mid-gesture, text overlay already up. "))
    beats.append({"t": "0.0–0.5s", "type": "VISUAL TRIGGER",
        "direction": vis + "No logos, no static intro. Works muted (85% watch sound-off).",
        "on_screen": overlay_truncate(hookline.split('.')[0])})
    beats.append({"t": "0.5–3.0s", "type": "VERBAL HOOK + LOCK",
        "dialogue": hookline,
        # D143/D94: "~{t(D*0.78)}s" is a placeholder — _fit_timeline re-times
        # the "delivered at ~Xs" literal to the laid-out PAYOFF start.
        # D13 (pipeline v2): concept contracts first — a routine or
        # challenge in review/transformation format was promised a product
        # verdict or a DAY 1 vs DAY N split its journey grammar never shows.
        "payoff_contract": (
                            # D47 (judge loop, cycle 13): a routine's contract
                            # is the STREAK result — what the routine changed,
                            # named in the pinned day-counter hook.
                            f"Viewer is promised the Day {ctx.get('streak', '14')} "
                            f"result — what {ctx.get('routine_label', 'the routine')} "
                            f"changed — delivered at ~{t(D*0.78)}s — never frontloaded."
                            if ctx.get("concept") == "routine" else
                            # D8/D68: a challenge's contract is the Day-N verdict.
                            f"Viewer is promised the Day {ctx.get('span_n', '30')} "
                            f"verdict — delivered at ~{t(D*0.78)}s — never frontloaded."
                            if ctx.get("concept") == "challenge" else
                            # D27 (judge loop, cycle 10): a review's contract is a verdict
                            # question ("worth it or skip"), not a surprise tease.
                            f"Viewer is promised a verdict — worth it or skip "
                            f"— delivered at ~{t(D*0.78)}s — never frontloaded."
                            if fmt == "review" and mode == "product" else
                            # D39: transformation contract = the dated
                            # before/after result, named in the hook.
                            f"Viewer is promised the DAY 1 vs DAY "
                            f"{ctx.get('ndays', 7)} transformation result — "
                            f"delivered at ~{t(D*0.78)}s — never frontloaded."
                            if fmt == "transformation" and mode == "product" else
                            f"Viewer is promised a specific payoff, delivered at "
                            f"~{t(D*0.78)}s — never frontloaded."),
        "delivery": "Brisk, confident. Verbal hook ≤8 words total (D73 charter hook stack)."})
    auth = NICHE_AUTHORITY.get(ctx["niche"], "the best in the game")
    if mode == "product":
        # D12 (judge loop, cycle 5): human-presenter scripts open with an
        # IMPERFECTION BEAT (3–5s) — visible flaw first per RULES.md E7. The
        # reference human class wins on authenticity; polished reads as an ad.
        if presenter == "human":
            # D23 (judge loop, cycle 9): imperfection pool is niche-scoped —
            # cycle 9 caught a category-wrong failure verb ("clogged" on bands)
            # burning the E7 trust contract. Niche pool wins; generic is fallback.
            imp_pool = IMPERFECTION_BEATS.get(
                ctx.get("niche"), IMPERFECTION_BEATS["generic"])
            imperf_bank = Bank(rng, imp_pool)
            imp_t = imperf_bank.draw()
            # D143 drive-by: number agreement ("I thought this eyelashes was
            # a scam" shipped) — plural categories take these/were.
            _pl = bool(re.search(r"[^s]s$", ctx["category"]))
            imp_slots = dict(product=ctx["product"], category=ctx["category"],
                             this_category=("these " if _pl else "this ") + ctx["category"],
                             was="were" if _pl else "was")
            # D143: no fixed window — _fit_timeline sizes it from its words;
            # _alts are the bank's shorter spoken forms (never a mid-clause cut).
            beats.append({"type": "IMPERFECTION BEAT",
                "dialogue": imp_t.format(**imp_slots),
                "_alts": _bank_variants(imp_t, imp_slots),
                "delivery": "Candid, unpolished — the flaw first (E7, D12). "
                            "No cover-up, no polished read.",
                # D96 (judge loop, cycle 23): the old "here's what I tested"
                # was a meta-generic promise with no event (D2). The rehook
                # now names the demo test event — the loop the demo beat
                # closes two beats later.
                # D143: "Okay — with that out of the way:" was 7 tokens of
                # filler in a 3–5s beat (D12); the event is the payload.
                "rehook": f"Now the test: {_demo_test_for(ctx)[0]}.",
                # if every demo beat is budgeted out (15s transformation) the
                # promise must still be answered by what follows (D45)
                "_rh_needs": "DEMO BEAT",
                "_rh_fallback": ("Now the proof: day 1 vs day "
                                 f"{ctx.get('ndays', 7)}."
                                 if fmt == "transformation" else "")})
        # D28 (judge loop, cycle 10): REVIEW-FORMAT REJECTION HISTORY. A
        # reviewer's credibility comes from named rejections, not from
        # testing one item — the reviewer names N items tried and how they
        # failed (failure verbs category-scoped like D23). Fires for both
        # presenters; the human presenter keeps its D12 beat above this one.
        if fmt == "review" and mode == "product":
            # D137: the AI lane draws the curator-framed pool.
            _rej_src = REVIEW_REJECT_BEATS_AI if presenter == "ai" else REVIEW_REJECT_BEATS
            rej_pool = _rej_src.get(ctx.get("niche"), _rej_src["generic"])
            rej_t = rng.choice(rej_pool)
            rej_slots = dict(product=ctx["product"], category=ctx["category"],
                             category_s=plural(ctx["category"]),
                             n=rng.choice([2, 3, 4]))
            beats.append({"type": "REJECTION HISTORY",
                "dialogue": rej_t.format(**rej_slots),
                "_alts": _bank_variants(rej_t, rej_slots),
                # D143: optional under a ~35s body (dropped before any
                # essential line is trimmed), last-resort droppable above.
                "_drop": _DROP_OPTIONAL + 10 if D - 3.0 < 35 else 10,
                "delivery": "Candid reviewer register — the credibility beat (D28).",
                # D41 (judge loop, cycle 15): the old re-hook ("Here's the one
                # that survived.") restated the beat's own closing line
                # ("This is the one that survived.") — shipped twice despite
                # the D57 gate design. Re-hooks open the NEXT beat, never echo
                # the current one.
                "rehook": "Here's why this one survived."})
        # education beats (F103: educational > evaluative sales pitch for personas)
        n_edu = max(1, int(D // 18))
        for i in range(n_edu):
            edu_t = edu_bank.draw()
            edu_slots = dict(
                product=ctx["product"], category=ctx["category"],
                # D143 drive-by: "Most {category} fail" rendered "Most car
                # vacuum fail" — the bank line takes the plural now.
                category_s=plural(ctx["category"]),
                problem=f"the thing every {singular(ctx['category'])} gets wrong",
                flaw="they optimize for the spec sheet, not real daily use",
                mechanism="it removes the friction between you and the result",
                authority=auth,
                authority_quote="design the environment, not the willpower",
                check1="build quality that survives daily use",
                check2="setup under five minutes",
                check3="does the core job without gimmicks")
            beats.append({"type": "EDUCATION BEAT",
                "dialogue": edu_t.format(**edu_slots),
                "_alts": _bank_variants(edu_t, edu_slots),
                # D143: extra edu beats are optional (dropped first, later
                # ones before earlier ones); the first is a last resort.
                "_drop": _DROP_OPTIONAL + 20 + i if i else 20,
                "delivery": "Unhurried, warm — trust-building register (F138).",
                # D15 (judge loop, cycle 6, extended cycle 8): re-hook defaults are
                # category-aware — "I dim the room" on a pet roller or "I flip
                # it over" on a room-tour listicle defeats D2's event contract.
                # D82 (judge loop, cycle 20): the beat-level fallback carried the
                # same D58-class camera command ("show the {category} up close
                # on camera") the parse-time default had. Presenter-neutral.
                # D86: neutral-default actions are noun phrases — exclude the
                # verb-phrase-only "when I" template (pets/compound verb-phrase
                # actions lose that one template; never ungrammatical).
                # D93 (pipeline v2): at 45–60s every edu beat re-promised the
                # same edu_action; later edu beats promise their own event.
                "rehook": deck.draw(no_when_i=True).format(action=(ctx.get(
                    "edu_action",
                    f"the {ctx['category']} detail the box never shows, up close")
                    if i == 0 else _EDU_NEXT_TEASES[(i - 1) % len(_EDU_NEXT_TEASES)].format(
                        category=ctx["category"])))})
        # demo beats
        n_demo = max(1, int(D // 16))
        for i in range(n_demo):
            # D96 (judge loop, cycle 23): the beat's test slots draw the demo
            # test event — never the old label defaults ("the side-by-side" /
            # "night-and-day difference" / "I put it through the real-world
            # test", the last one D41-banned phrasing as beat content too).
            _dt, _dr = _demo_test_for(ctx)
            # D111-implementation (gauntlet, cycle 12): "round two" dangles on
            # single-test scripts — seed 811 shipped "the lock doing its real
            # job, on camera, round two" with no round one. A script numbers
            # tests only if it numbers at least two; the slot is neutralized
            # when there is a single demo beat.
            demo_t = demo_bank.draw()
            # D143 (P3 at 45–60s): three of the four demo templates end on
            # the same {result} sentence, so 2–3 demo beats repeated it
            # verbatim; later rounds report their own outcome.
            if i:
                _dr = _DEMO_LATER_RESULTS[(i - 1) % len(_DEMO_LATER_RESULTS)]
            demo_slots = dict(
                product=ctx["product"], action=_dt,
                result=_dr,
                test1=_dt, result1=_dr,
                # D90/D111 (pipeline v2): "round two" only on a beat that IS
                # round two — the index-numbered "Test 1: ..., round two." shipped.
                test2=(f"{_dt}, round two" if n_demo > 1 and i >= 1 else _dt),
                result2=_dr,
                # D36: price may be None (int(None) crashes); the {expensive}
                # demo template is gated on named_competitor (D26) anyway.
                expensive=(f"the ${round(float(ctx['price'])*8)} name-brand one"
                           if ctx.get("price") else "the premium name-brand one"),
                comparison="same job, a fraction of the price",
                # D117 (judge loop, cycle 29): the flaw hook ("Nobody mentions
                # the {category} flaw.") promises a flaw revelation the demo
                # beat never instantiated — seed 936 shipped "The detail that
                # sold me: finished details, not cost-cut." (the cycle-27
                # WATCHED item, now systematic: the viewer was promised a flaw
                # and shown a generic compliment). When the category is mapped
                # in CATEGORY_MECHANISM_FAIL, the detail names the mechanism
                # part — the flaw gets a name where the hook promised one.
                # "The detail that sold me: the details are finished"
                # stuttered (cycle 12) — the slot value must complete the
                # template's singular "detail", not repeat it.
                detail=(_d117_mech(ctx) if _d117_mech(ctx)
                        else "finished details, not cost-cut"))

            def _demo_line(s, i=i):
                # D90 (judge loop, cycle 21): "Test one:"/"Test two:" ordinals were
                # template-fixed but the draw is index-unaware — seed 924's single
                # demo beat said "Test two" while on_screen said "TEST 1" (D65's
                # de-overlap pass indexes by i). The ordinal now comes from the
                # beat index so spoken and on-screen numbering always agree.
                # D111-implementation (gauntlet, cycle 12): a single-test script
                # numbers nothing - seed 811's lone demo beat shipped "Test 1"
                # with no "Test 2" and failed the D111 gate. Strip the ordinal
                # when there is only one demo beat.
                if n_demo == 1:
                    s = re.sub(r"^Test (one|two):\s*", "", s)
                    # the stripped test text starts lowercase ("the lock doing
                    # its real job.") - sentence-case the beat open.
                    s = s[:1].upper() + s[1:] if s else s
                else:
                    s = re.sub(r"^Test (one|two):", f"Test {i+1}:", s)
                # D90b: pool result strings start lowercase ("zero friction after
                # a week of use") and render after a period as "...test. zero
                # friction" — sentence-case the draw at the same site.
                # D90b (pipeline v2): also after "? " and "! " — "See that?
                # visible before-and-after proof." shipped lowercase.
                return re.sub(r"(?<=[.?!] )([a-z])",
                              lambda m: m.group(1).upper(), s)
            demo_alts = [_demo_line(v) for v in _bank_variants(demo_t, demo_slots)]
            demo = demo_alts[0]
            # D33 (judge loop, cycle 11): audio products get one audio-led
            # demo beat — the first demo is always "listen", never "watch".
            # The sound the mic will actually hear is NAMED, not gestured at.
            if is_audio and i == 0:
                demo = (f"Turn your volume up — listen: this {ctx['category']} "
                        f"fills the whole room. Hear that? No crackle, no hiss.")
                demo_alts = [demo, f"Volume up: this {ctx['category']} fills "
                                   f"the room. No crackle.",
                             "Volume up. Hear that? No crackle."]
            # D41 (pipeline v2): ctx["demo_action"] IS the demo test (D96), so
            # the re-hook re-promised the beat it closes ("Here's where it gets
            # interesting: the resistance bands set doing its real job." after
            # "Watch: the resistance bands set doing its real job."). An
            # echoing action is replaced by the NEXT event: the next test, the
            # dated split-screen, or the verdict/result the payoff delivers.
            _post_demo = (f"the day-{ctx.get('ndays', 7)} split-screen"
                          if fmt == "transformation" else
                          "the verdict" if fmt == "review" else
                          "the one everyone keeps asking about"
                          if ctx.get("concept") == "showcase" else
                          "the week-one result")
            _rh_t = deck.draw(no_when_i=True)
            _rh_action = ctx.get(
                "demo_action",
                ((f"every {ctx['category']}, side by side — and the one "
                  "everyone keeps asking about")
                 if (ctx.get("concept") == "showcase"
                     and "the box never shows" in ctx.get(
                         "edu_action",
                         f"the {ctx['category']} detail the box never "
                         "shows, up close"))
                 else "the detail the box never shows, up close"))
            # D93: the default action IS the demo test — even when this beat's
            # line doesn't voice it, the imperfection re-hook already promised
            # it, so the demo channel opens the next loop instead; later demo
            # beats never re-promise the first one's event either.
            _echo = _echoes(_rh_action, demo) or _rh_action == _dt or i > 0
            if _echo:
                _rh_action = (_DEMO_NEXT_TEASES[i % len(_DEMO_NEXT_TEASES)]
                              if i < n_demo - 1 else _post_demo)
            beats.append({"type": "DEMO BEAT",
                "dialogue": demo,
                "_alts": demo_alts,
                # D143: extra demo beats are optional; the first is essential
                # except in transformation, where the dated EVIDENCE beat is
                # the genre contract (D25) and the demo is a last resort.
                "_drop": (_DROP_OPTIONAL + 10 + i if i else
                          15 if fmt == "transformation" else None),
                # when a later demo beat is budgeted out, this one becomes the
                # last demo and its re-hook must promise what now follows
                "_rh_last": (_rh_t.format(action=_post_demo)
                             if _echo and i < n_demo - 1 else None),
                # D111 (gauntlet, cycle 12): display-only "TEST 1" counts as
                # dangling numbering — single-test scripts carry bare "TEST".
                "on_screen": ("TEST" if n_demo == 1 else "TEST " + str(i+1)),
                "delivery": "Energetic, pitch-varied (F85). Mid-action framing.",
                # D15 (judge loop, cycle 6, extended cycle 8): category-aware default
                # ("I flip it over" on non-flippable products defeats D2).
                # D41 (judge loop, cycle 12): the re-hook must open a NEW
                # loop, never restate the beat — cycle 12's demo dialogue
                # ("I put it through the real-world test") was echoed
                # verbatim by its own re-hook, burning the loop's retention job.
                # (Parse-time default now carries this; this fallback matches.)
                # D82 (judge loop, cycle 20): the beat-level fallback carried the
                # pre-D58 camera command verbatim ("zoom in on the detail the
                # box never shows") — D58 fixed only the parse-time default,
                # and the showcase branch's early return skips parse-time, so
                # this fallback fired on seed 923: "Now watch what happens
                # when I zoom in on the detail..." — the presenter saying the
                # camera move out loud. Presenter-neutral, mirroring D58.
                # D86: see the edu rehook above — same verb-phrase-template
                # exclusion for the demo channel's neutral default.
                # D93 (judge loop, cycle 22): REHOOK PROMISE-UNIQUENESS ACROSS
                # BEATS. D41 banned echoing the current beat; seed 925 echoed
                # ACROSS beats — the edu fallback ("the {category} detail the
                # box never shows, up close") and the demo fallback ("the
                # detail the box never shows, up close") resolve to the same
                # promise on showcase runs, spending both open loops on one
                # event (the nick.digiovanni reference withholds the payoff
                # with ONE sustained loop, not two copies). When the
                # demo-channel fallback would re-promise the edu channel's
                # box-detail close-up on a roundup, it opens a distinct loop
                # instead: the side-by-side plus the crowd-favorite find
                # (the payoff card's own surprise, held back).
                "rehook": _rh_t.format(action=_rh_action)})
        # D25 (judge loop, cycle 9): TRANSFORMATION EVIDENCE GRAMMAR — the
        # genre's contract is dated visual proof, never narration-only
        # transformation. Every transformation script pins an evidence beat
        # with split-screen before/after + day-stamp overlays (linnlowes
        # split-screen, jellydevote dated doc, ownbyfemme showcase: before/
        # after proof beats all other fitness content for shares+saves).
        if fmt == "transformation":
            # D39 (judge loop, cycle 12): AI-CURATED TRANSFORMATION. An AI
            # persona has no body — "Same body, same light ... that's
            # {product}, every day" claimed the persona's OWN transformation
            # (cycle 12, under-desk walking pad). The reference class's proof
            # engine (gauthamramkarthik 280K likes, ownbyfemme 39K/850
            # comments) is real-human bodies. In the AI lane the evidence beat
            # is CURATOR-FRAMED: the split-screen documents someone else's
            # logged journey; the persona analyzes, never embodies.
            # D36 (pipeline v2 — RULES D36): "Same body, same light" shipped
            # on hair wax, door locks and lunch bags (gate 2: 'same body' on a
            # non-body transformation). The line names the REAL subject
            # ("same hair, same light"), "same angle" when the prompt names
            # none; "body" only when the prompt is about a body.
            _subj = _d36_subject(ctx.get("_prompt") or ctx.get("product", ""))
            _nd = ctx.get('ndays', 7)
            ev_dialogue = (f"Same {_subj}, same light — DAY 1 on the left, "
                           f"today on the right. That's not a filter; that's "
                           f"{_det(ctx['product'])}, every day.") \
                if presenter == "human" else \
                (f"Their Day 1, their Day {_nd} — one creator's "
                 f"full log with {_det(ctx['product'])}. Same {_subj}, same "
                 f"light — the split doesn't lie.")
            # D143: shorter spoken forms of the same proof for tight budgets
            ev_alts = ([ev_dialogue,
                        f"Same {_subj}, same light: day 1 on the left, day {_nd} on the right.",
                        f"Same {_subj}, same light. Day 1 left, day {_nd} right."]
                       if presenter == "human" else
                       [ev_dialogue,
                        f"Their day 1, their day {_nd}: same {_subj}, same light.",
                        f"Their day 1 vs day {_nd}. Same {_subj}, same light."])
            beats.append({"type": "EVIDENCE BEAT",
                "dialogue": ev_dialogue,
                "_alts": ev_alts,
                # D122 (gauntlet cycle 15): on_screen is render-exactly overlay
                # copy (make_shotlist renders it verbatim as "ON-SCREEN TEXT
                # (render exactly, ...)") — the old template burned the
                # staging note "(split-screen, timestamped)" into the card.
                # D135 (gauntlet cycle 19): the evidence card must name the same
                # day-count the hook drew (ctx["ndays"], D40) — the hardcoded
                # "DAY 1 | TODAY" contradicted the hook contract
                # ("DAY 1 vs DAY {nd}") and the payoff card
                # (f"DAY 1 | DAY {nd}"). Template is the sole source.
                "on_screen": f"DAY 1 | DAY {ctx.get('ndays', 7)}",
                "delivery": "Slow down. Let the result land — proof shots are "
                            "never rushed. No scripted laugh (F142).",
                # The deck's "Watch {action}" template rendered "Watch zoom in
                # on the pad" (cycle 12) — ungrammatical. The evidence re-hook
                # is pinned to a grammatical template instead of the deck.
                # D93 (pipeline v2): the pin WAS the deck's REHOOKS[6] frame
                # ("Okay, but why does it actually work? Watch ...") — a
                # near-duplicate whenever the deck also dealt that template.
                # Its own frame now, still answered by the payoff (D45).
                "rehook": "Now the close-up that settles it."})
        # D5 (judge loop cycle 2): payoff must name the SAME specific measurable
        # as the hook contract — no "the one thing Xs are supposed to do".
        # D27 (judge loop, cycle 10): REVIEW-FORMAT VERDICT GRAMMAR. A review's
        # contract is an explicit verdict, never just surprise — the reference
        # review class (brookemonk visual-verdict, nick.digiovanni keep/drop)
        # closes on BUY / SKIP / WHO-FOR. BUY always names who_for (saves-
        # driver); the payoff pins an on-screen VERDICT card.
        payoff_on_screen = None
        # D137: the AI lane speaks the curator form of a first-person proof
        # ("I woke up before the alarm" -> "the room is bright before the alarm").
        _proof = _spoken_proof(ctx, presenter)
        _sp = _short_product(ctx)
        if fmt == "review":
            # D56 (judge loop, cycle 15): POSITIVE PROOF IS SPOKEN. The old
            # template shipped durability-only negative proof
            # ("I expected the build to fail... but it never did") — an
            # absence, not a result; seed-815 violated the cycle-14 rule
            # because it was never coded. The spoken line (D43: ≤11 tokens in
            # the 3.9s payoff window) names the purpose fulfilled — desire
            # needs voice. The who-for + durability subversion ride the
            # on-screen VERDICT card — information rides text (85% muted).
            # pipeline v2 crash fix: challenge/showcase/routine/advice ctx has
            # no purpose_proof/who_for (KeyError on every review × non-product
            # run, baseline 36/990) — concept-safe fallbacks.
            # D143: spoken variants, longest first (D62: <=11 tokens).
            payoff_alts = [f"Verdict: BUY — {_proof}.",
                           f"Verdict: BUY. {_cap(_proof)}.",
                           f"BUY. {_cap(_proof)}.", "Verdict: BUY."]
            # D142 (pipeline v2): the old card was the full who-for sentence
            # + "expected <flop clause>, but <surprise clause>" — 24–34 words
            # (D103) at ~40 chars/s. The short card keeps D27/D56/D83's
            # elements — label, who-for, flop → surprise — in <=12 tokens.
            _who = _card_who(ctx)
            _flop, _surp = _card_flop(ctx)
            payoff_on_screen = _pick_card(
                ([f"VERDICT: BUY for {_who} · expected {_flop} → {_surp}",
                  f"VERDICT: BUY for {_who} · {_flop} → {_surp}"] if _who else []) +
                [f"VERDICT: BUY · expected {_flop} → {_surp}",
                 f"VERDICT: BUY · {_flop} → {_surp}", f"VERDICT: BUY · {_surp}"])
        elif fmt == "transformation":
            # D40 (judge loop, cycle 12): TRANSFORMATION PAYOFF = TRANSFORMATION
            # RESULT. Cycle 12's payoff delivered durability A7-subversion
            # ("the pad's build to fail") on an evidence contract — a D35
            # contract-pairing violation (the D25 evidence beat promises a
            # dated before/after; the payoff must name that result). The
            # subverted expectation is category-true abandonment, never
            # durability, never price (D26/D36).
            nd = ctx.get("ndays", 7)
            # D143/D62 (pipeline v2): the old spoken payoff was ~35 tokens
            # ("So here's the payoff I promised: DAY 1 vs DAY 7 — 7 days of
            # ..., one result on screen. I expected this to be a very
            # expensive clothes rack by day 4, but the log never missed a
            # day.") — the clothes-rack flop was walking-pad copy on every
            # product. Spoken names the dated result; the abandonment
            # subversion (D40) rides the card.
            payoff_alts = [f"Day 1 vs day {nd}: that's the {nd}-day difference.",
                           f"Day 1 vs day {nd}: the difference.", f"Day 1 vs day {nd}."]
            # D120: no "(split-screen)" staging note in render-exactly overlay
            # copy (see evidence beat). D142/D83: label + flop → surprise.
            payoff_on_screen = f"DAY 1 | DAY {nd} · expected skips → {nd}/{nd} days"
        else:
            # D62 (judge loop, cycle 16 — extends D43/D56): DEMO PAYOFF SPLIT
            # CONTRACT. Cycle 14's 53-word review payoff was unperformable;
            # cycle 15 fixed review but the demo branch kept the old
            # template — seed-916 shipped the same 53 words in 3.9s
            # (~815 wpm, D43 self-violation in demo format) and negative
            # proof only ("no failure, no gimmicks", D56 recurrence).
            # The spoken line (D43: <=11 tokens in the 3.9s payoff window)
            # now names the measured result — the purpose fulfilled — while
            # the product + test label + named flop + subversion ride the
            # on-screen MEASURED card (85% watch muted). Showcase/listicle
            # concepts (D22) carry no purpose_proof — their measured result
            # IS the measured_claim ("every item linked in one list").
            # D83 (judge loop, cycle 20): the card restated the spoken payoff
            # verbatim — "Test result: every item linked in one list." spoken,
            # then "TEST: these car finds — every item linked in one list · ..."
            # on screen (~35 words on seed 923, against the playbook §4
            # overlay discipline; the cycle-3 flagged open item). The card
            # carries only what the spoken line doesn't: TEST label + product
            # + flop + surprise — mirroring D56's VERDICT card, which shares
            # only the headline with the spoken line.
            # D92 (judge loop, cycle 22): closes the cycle-21 OPEN item —
            # "Test result:"/TEST-label payoff framing on showcase roundups.
            # A roundup runs no experiment ("Test 1: the daily-use test" is
            # template filler, not a described test; the payoff names no
            # test outcome) — the TEST label is demo grammar leaking into
            # listicles, against the juliana_claire reference class, which
            # never frames a roundup as a test. Showcase concepts LIST, they
            # don't test: spoken names the full list (D62 ≤11 tokens, D35
            # contract pairing intact), the card keeps the D83 de-overlap
            # shape under a LIST label. Demo/product formats keep TEST.
            # D142 (pipeline v2): the cards below were "TEST: {product} ·
            # expected {expected_flop}, but {surprise}" — 24–34 words at up to
            # ~40 chars/s. Short card, same D83 elements (label, short
            # product, flop → surprise), <=12 tokens, never the spoken line.
            _flop, _surp = _card_flop(ctx)
            if ctx.get("concept") == "showcase":
                _claim = ctx.get("measured_claim") or "every item in one list"
                payoff_alts = [f"That's the full roundup — {_claim}.",
                               f"Full roundup: {_claim}.", "That's the full roundup."]
                payoff_on_screen = _pick_card(
                    [f"FULL LIST: {_sp} · expected {_flop} → {_surp}",
                     f"FULL LIST · expected {_flop} → {_surp}",
                     f"FULL LIST: {_sp} · {_surp}"])
            else:
                payoff_alts = [f"Test result: {_proof}.", f"Result: {_proof}."]
                payoff_on_screen = _pick_card(
                    [f"TEST: {_sp} · expected {_flop} → {_surp}",
                     f"TEST · expected {_flop} → {_surp}",
                     f"TEST: {_sp} · {_flop} → {_surp}", f"TEST: {_sp} · {_surp}"])
        payoff_alts = _cap_tokens(payoff_alts, 11)   # D62/D68 spoken budget
        payoff = payoff_alts[0]
        # D1 (judge loop cycle 1): comment-word CTA engine — product-mode comment
        # bait is ALWAYS the comment-word template, never a random draw (random
        # draw let "follow for part 2" win, which D1 replaced).
        _cw = _cta_word(ctx)  # D107: beauty sub-category scoped
        bait = COMMENT_BAIT[4].format(
            opt1=f"budget {ctx['category']}", opt2=f"premium {ctx['category']}",
            opt3="going without",
            hottake=f"most {ctx['category']}s are overpriced for what they actually do",
            category=ctx["category"],
            # D34 (judge loop, cycle 11): comment word = niche noun ("SLEEP"),
            # never the generic container noun ("MACHINE").
            cta_word=_cw)
        # D143: shorter follow-first forms (B4a order kept, D88 <=9 tokens)
        bait_alts = [bait, f"Follow, comment {_cw} for the link list.",
                     f"Follow, comment {_cw} for the list.", f"Follow, comment {_cw}."]
        # D36: the old hardcoded "it's under twenty bucks" was a fabricated
        # price claim when the prompt named no price — the urgency degrades
        # to a non-price close when price is None.
        # D46 (judge loop, cycle 15 — code enforcement): ONE LINK CTA. The
        # comment-bait beat already runs the keyword → DM-list funnel; a
        # bio-link CTA in the same video is a second competing payload.
        # Product-mode CTAs are filtered to non-link closes (follow + next
        # test) — the funnel ends on the keyword, never splits.
        # D89 (judge loop, cycle 21): {next} is concept-aware — showcase
        # category is "find", so the product-mode "the find head-to-head"
        # shipped meaningless on roundups (seed 924). Product promises the
        # rematch episode; showcase promises more finds. D89c: {next} is
        # hard-capped at 3 words — multi-word categories ("resistance bands
        # set") blew the old template to 8 words in the fixed 1.8s CTA
        # window (D87 -> <=6w total).
        # D97 (judge loop, cycle 23): "the rematch" fired UNCONDITIONALLY on
        # every non-showcase product CTA — but a rematch continues a
        # comparison narrative the video only establishes when it names a
        # competitor (D26's named_competitor gate; the {expensive} demo/hook
        # templates). Seed 926 ran a single-vacuum test and still promised
        # "part 2: the rematch" — a dangling serial, the demo-side twin of
        # the cycle-21 "head-to-head on roundups" class. {next} must match
        # the video's own test structure: comparison -> rematch, review ->
        # the long-term check-in, single-test demo -> the escalated test.
        _next = (f"more {ctx.get('domain', 'space')} finds"
                 if ctx.get("concept") == "showcase"
                 else "the rematch" if ctx.get("named_competitor")
                 else "the long-term test" if fmt == "review"
                 else "the torture test")
        if len(_next.split()) > 3:
            _next = ("more finds" if ctx.get("concept") == "showcase"
                     else "the rematch")
        cta = rng.choice(
            [c for c in CTAS if "bio" not in c]).format(
            urgency=(f"it's under {ctx['price']} bucks" if ctx.get("price")
                     else "this one's going in my bio"),
            next=_next)
        cta_alts = [cta, f"Part 2: {_next}.", "Follow for part 2."]   # D143 (D89 <=6 tokens)
        # D146: the part-2 promise is planned — generate() writes it into
        # script["series_plan"].
        series_next = _next
    elif mode == "advice":
        n_adv = max(2, int(D // 14))
        # D44 (pipeline v2): the re-hook action was the camera command "show
        # the analytics" — spoken in every advice re-hook ("...: show the
        # analytics."). Presenter-neutral noun-phrase events instead (D58/
        # D86: no "when I" frame), one per beat so no promise repeats (D93).
        _adv_actions = ["the analytics from a real account",
                        "the retention graph that proves it",
                        "the one-line fix, live"]
        for i in range(n_adv):
            adv_t = advice_bank.draw()
            adv_slots = dict(
                mistake="leading with your logo instead of the payoff",
                fix="state the viewer's reward in the first sentence",
                authority=auth,
                authority_quote="borrow trust, then earn your own",
                # D143 drive-by: {topic_noun} was the whole prompt ("I audited
                # fifty why your hooks fail videos").
                topic_noun=singular(ctx["category"]),
                pattern="the hook promises, the video never delivers",
                reward="watch time", wrong="likes",
                thing1="a payoff contract", thing2="a re-hook every 8 seconds")
            beats.append({"type": "TEACHING BEAT",
                "dialogue": adv_t.format(**adv_slots),
                "_alts": _bank_variants(adv_t, adv_slots),
                # D143: teaching beats past the second are optional; the
                # second is a last resort, the first is essential.
                "_drop": (_DROP_OPTIONAL + 20 + i if i >= 2 else
                          20 if i == 1 else None),
                "delivery": "Unhurried, warm — then punch the re-hook (F138 + Robins).",
                "rehook": deck.draw(no_when_i=True).format(
                    action=_adv_actions[i % len(_adv_actions)])})
        # D62-class (pipeline v2): the old advice payoff was ~20 tokens and
        # rendered the whole prompt as its subject ("... and why your hooks
        # fail stops being luck."). Spoken <=11 tokens; the three parts of
        # the fix ride the card (information rides text, 85% muted).
        payoff_alts = ["The payoff: fix the first 3 seconds. Luck stops mattering.",
                       "Fix the first 3 seconds. Luck stops mattering.",
                       "Fix the first 3 seconds."]
        payoff = payoff_alts[0]
        payoff_on_screen = "FIRST 3 SECONDS: trigger · hook · contract"
        # D15 (judge loop, cycle 6): D10 MODE-AWARE CTA. The advice branch drew the
        # link-list comment-word template — advice topics have nothing to link
        # (same mode-blind class as cycle 4's challenge fix). Advice CTA content
        # is a guide/checklist, never a link list.
        # D16 (judge loop, cycle 6): advice CTA content is a guide/checklist,
        # never a link list. B4a (judge loop, cycle 15): follow-first order
        # applies here too — the follow is the price of the payload.
        # D88/D89 (pipeline v2): the bait was 14 tokens and the CTA 13 — both
        # unperformable in their windows. Same payloads, spoken length.
        _cw = ctx['category'].upper()
        bait_alts = [f"Hit follow, comment {_cw} for the free checklist.",
                     f"Follow, comment {_cw} for the checklist.",
                     f"Follow, comment {_cw}."]
        bait = bait_alts[0]
        cta_alts = ["Follow, tomorrow: a live account audit.",
                    "Tomorrow: a live account audit.", "Tomorrow: a live audit."]
        cta = cta_alts[0]
        series_next = "a live account audit"   # D146
    elif mode == "routine":
        # D47 (judge loop, cycle 13): ROUTINE GRAMMAR. A personal routine is
        # not a product and not a challenge — the reference grammar is
        # ashtonhall's day-counter series (Day 315, Day 2,335; "Day 14 with
        # the Hall's" 9.06M likes, 49.2K comments): timestamped ritual acts,
        # ONE relapse confession (human texture — routines fail at the
        # alarm, never at a product; D12/E7 for routines), a behavior-metric
        # payoff (B1), wake-time comment bait (B4a follow-gated keyword CTA),
        # and a next-day check-in CTA (serialization is native here).
        # D43 DIALOGUE-TIME FIT: every line is budgeted at ~3 wps (2.5 for the
        # slow payoff) against its own window — the hair-wax audit proved
        # unperformable scripts ship silently otherwise. D44: dialogue is
        # spoken — no stage directions ("show the X", "on camera").
        t_label = ctx["routine_time"]
        # D143: each act carries a shorter spoken form (unhurried delivery
        # = 2.5 wps, so three full acts + re-hooks overran a 30s body).
        # D137: "cold water on my face" is a lived-experience claim in the
        # AI lane — the curator form drops the "my".
        _face = "on my face" if presenter == "human" else "to the face"
        acts = [
            (f"{t_label}: alarm off, feet on the floor before my brain wakes up.",
             [f"{t_label}: alarm off, feet on the floor."],
             f"{t_label.upper()} FIRST WIN",
             "That's the first win. Here's the second."),
            (f"Twenty minutes later — cold water {_face}. No phone for the first hour.",
             ["Cold water, then no phone for the first hour.",
              "No phone for the first hour."],
             "NO PHONE, FIRST HOUR",
             "Here's the one nobody talks about."),
            ("One hour later — I'm at my desk before the city wakes up.",
             ["At my desk before the city wakes up."],
             "BEAT THE CITY",
             "And here's what fourteen mornings did."),
        ]
        if presenter == "human":
            # Routine imperfection = relapse honesty, not product failure.
            # D43: 2.5s window → ≤7 words at conversational pace.
            imp = rng.choice([
                f"Day {ctx['streak']}: I slept straight through it.",
                "Tuesday I snoozed an hour. Almost quit."])
            beats.append({"type": "IMPERFECTION BEAT",
                "dialogue": imp,
                "delivery": "Candid, unpolished — relapse first (E7, D12).",
                "rehook": f"{t_label} — here's how it actually starts."})
        # D143: ritual windows are content-sized by _fit_timeline (the old
        # fixed 5.5s/5.5s/5.0s windows ignored the words). The first act is
        # essential; the middle act goes before the last (whose re-hook
        # tees up the payoff) when even the short forms cannot fit.
        for i, (dlg, short, card, rh) in enumerate(acts):
            beats.append({"type": "RITUAL BEAT",
                "dialogue": dlg,
                "_alts": [dlg] + short,
                "_drop": (None, 22, 21)[i],
                "on_screen": card,
                "delivery": "Present-tense, unhurried — let them co-live it (F45 ritual).",
                "rehook": rh})
        # Payoff (shared 3.9s slow window → ≤11 tokens at 2.5 wps): streak
        # result named in the pinned hook, same measurable, subverted
        # expectation (A7/D35). No em-dash — it counts as a spoken token.
        payoff = (f"Day {ctx['streak']}: {ctx['measured_claim']}. "
                  f"Expected {ctx['expected_flop']}.")
        payoff_alts = [payoff, f"Day {ctx['streak']}: {ctx['measured_claim']}."]  # D143
        # B4a (beauty audit): follow-before-keyword CTA; the payload is the
        # routine checklist (D46: no link list, no bio link — one funnel).
        # Shared 2.7s bait window → ≤9 words.
        bait = (f"Follow, then comment ROUTINE for the {t_label} checklist.")
        cta = f"Tomorrow: Day {int(ctx['streak']) + 1}. Same time."
        # D143 short forms; D146: the next-day check-in is a planned episode
        bait_alts = [bait, "Follow, then comment ROUTINE for the checklist.",
                     "Follow, comment ROUTINE."]
        cta_alts = [cta, f"Tomorrow: Day {int(ctx['streak']) + 1}."]
        series_next = f"Day {int(ctx['streak']) + 1}"
    else:  # story / pov-vlog
        if ctx.get("concept") == "challenge":
            # D8/D10 (judge loop, cycle 4): JOURNEY GRAMMAR for self-challenge
            # concepts. Product story grammar assumed a testable SKU ("Day N
            # of {product} testing", "the {category} test the box never
            # shows", link-list CTA) — every slot broke on a challenge.
            # Journey grammar: day-counter streak framing (ashtonhall:
            # 9.06M likes), withdrawal/relapse beats (human texture C1),
            # in-session measurable payoff (D5/D7, behavior metric), D1
            # comment-word bait with MODE-AWARE content (join-the-count, never
            # a link list — there is nothing to link). Serialized day-counters
            # tease tomorrow's episode only after today's payoff resolves.
            noun, span, span_n = ctx["challenge_noun"], ctx["span"], ctx["span_n"]
            n_st = max(2, int(D // 14))
            # D67 (judge loop, cycle 17): practice challenges get practice
            # journey grammar — the abstinence beats ("Day {n} of no {noun}",
            # withdrawal events) are wrong for a streak the presenter is
            # BUILDING, not breaking. Practice stakes = the streak (D53).
            if ctx.get("challenge_type") == "practice":
                _beat_src, _event_src = PRACTICE_CHALLENGE_BEATS, PRACTICE_CHALLENGE_EVENTS
                # D99: the wall template needs span_n (hyphenated "30-day"),
                # not span ("30 days").
                _beat_kw = {"noun": noun, "span": span, "span_n": span_n}
            else:
                # D120: abstinence events are noun-class native (caffeine
                # challenges get coffee-maker events, not phone-grabbing).
                _beat_src, _event_src = (CHALLENGE_BEATS,
                    _abstinence_events(ctx.get("abstinence_class") or "screen"))
                _beat_kw = {"noun": noun}
            ch_bank = Bank(rng, _beat_src)
            # D100 (judge loop, cycle 24): events were drawn with bare
            # rng.choice per beat — "the shortcut that saved the streak"
            # fired in two consecutive beats (seed 927), one open loop spent
            # twice (D93-class, cycle-22 G2, now generalized to the challenge
            # branch). Bank draws unique events per script.
            ev_bank = Bank(rng, _event_src)
            for i in range(n_st):
                _ev = ev_bank.draw()
                if presenter == "ai":
                    # D137: curator form of a first-person event ("the 3pm
                    # headache I tried to bargain with" -> "... that tries to
                    # bargain") — the AI lane never claims it lived the day.
                    _ev = AI_EVENT_REWRITES.get(_ev, _ev)
                st = ch_bank.draw().format(
                    n=i+1, event=_ev, **_beat_kw
                ).replace("1 days in", "1 day in")
                # D69: sentence-case the event after a period — the event
                # bank is lowercase by design ("the old habit..."), and the
                # templates put it after ". " ("I almost quit on day 2.
                # the old habit..." shipped lowercase — a spoken-voice bug).
                st = re.sub(r"([.!?]) ([a-z])",
                            lambda m: f"{m.group(1)} {m.group(2).upper()}", st)
                # D69: challenge re-hooks are PINNED, not drawn from the
                # generic deck — no single {action} fits both "when I
                # {action}" and "Watch {action}" frames ("Now watch what
                # happens when I day 1 — the moment I almost quit."
                # shipped). Both pins are spoken-safe (D44), event-specific
                # (D2), and answered by the next beat (D45).
                # D93 (pipeline v2): 3+ day beats (45s+) repeated "Day N: the
                # moment I almost quit." — each day gets its own pinned promise.
                rh = _CHALLENGE_REHOOK_PINS[min(i, len(_CHALLENGE_REHOOK_PINS) - 1)].format(d=i + 1)
                beats.append({"type": "STORY BEAT",
                    "dialogue": st,
                    # D143: the first day beat is essential, the second a
                    # last resort, any further ones optional.
                    "_drop": (None if i == 0 else 20 if i == 1
                              else _DROP_OPTIONAL + 20 + i),
                    "delivery": "Conversational, present-tense. Let the audience co-experience (F45 ritual).",
                    "rehook": rh})
            # D68 (D62-split, judge loop, cycle 17 — closes the cycle-16 OPEN
            # item): the old challenge payoff shipped ~53 words in the 3.9s
            # window (~815 wpm, D43 unperformable, seed 404). Spoken ≤11
            # tokens names the measured verdict; the card carries noun +
            # subversion for the 85% watching muted.
            payoff = f"Day {span_n} verdict: {ctx['measured_short']}."
            payoff_alts = [payoff, f"Day {span_n}: {ctx['measured_short']}."]  # D143
            # D142 (pipeline v2): ctx["verdict_card"] is the full label +
            # expected-flop sentence + surprise sentence (~30 tokens, ~45
            # chars/s). Short card: label · flop → surprise, <=12 tokens.
            if ctx.get("challenge_type") == "practice":
                payoff_on_screen = f"DAY {span_n} · expected a day-4 quit → showed up anyway"
            else:
                _as = _ABSTINENCE_SLOTS[ctx.get("abstinence_class") or "screen"]
                payoff_on_screen = _pick_card(
                    [f"{_as['verdict_label'].split(':')[0]} · expected a day-3 cave → {_as['card_surprise']}",
                     f"{_as['verdict_label'].split(':')[0]} · {_as['card_surprise']}"])
            # D70 (judge loop, cycle 17): the old challenge bait ("Comment DAY1
            # — start your own 30-day count on {noun}. I'll check in.") was
            # ~15 words in the 2.7s window (~330 wpm, D43 unperformable) and
            # never got the B4a follow-first sequence — cycles 14/15
            # enforced follow-first in product+advice branches only (a D6
            # every-format miss). Now 9 words, follow-first, join-the-count
            # (D10) intact; the noun detail lives in the caption echo (D59).
            bait = "Follow, then comment DAY1 — start your own count."
            bait_alts = [bait, "Follow, then comment DAY1 to start your count.",
                         "Follow, comment DAY1 to join.", "Follow, comment DAY1."]
            # D67: practice CTA teases the near-break, not "what I replaced
            # the {noun} with" — there is nothing being replaced.
            # D89b (judge loop, cycle 21): the old forms were 9-10 words in
            # the fixed 1.8s CTA window (D87 -> <=6w, ~300+ wpm,
            # unperformable). The D7 serialization promise and the D67
            # near-break tease survive at 6 words; noun detail lives in the
            # beats and caption.
            # D89 (pipeline v2): "my {noun} replacement" broke on multi-word
            # nouns ("Tomorrow: my buying coffee replacement. No lies." = 7
            # tokens, ungrammatical) — the vice class names the swap.
            if ctx.get("challenge_type") == "practice":
                series_next = "my near-break day"
            else:
                series_next = (f"my {_ABSTINENCE_SLOTS[ctx.get('abstinence_class') or 'screen']['swap']}"
                               f" replacement")
            cta = f"Tomorrow: {series_next}. No lies."
            cta_alts = [cta, f"Tomorrow: {series_next}."]
        else:
                # D6/D7 (judge loop, cycle 3): the story branch bypassed every enforcement
            # gate from cycles 1-2 (D1 comment-word, D2 event-specific re-hooks, D5
            # measurable payoff) and deferred the payoff to "tomorrow". Gates apply
            # to ALL format branches — a rule enforced in one template tree is a dead
            # rule. Payoff is delivered IN-SESSION; serialization gets its own NEW
            # contract, never a substitution for the current one.
            n_st = max(2, int(D // 14))
            for i in range(n_st):
                st = story_bank.draw().format(
                    n=i+1, quest=f"testing {ctx['product']}",
                    event="it did something I didn't expect",
                    claim=f"{ctx['product']} was just hype", turn="the numbers said otherwise",
                    plan="a quick unboxing", situation="unboxing it live",
                    twist="it does the one thing the listing never mentioned")
                # D6: {action} must name the SPECIFIC on-screen event, never a
                # meta-reference like "I show what happened next".
                rehook_action = (f"Day {i+1} of {ctx['product']} testing — "
                                 f"the {ctx['category']} test the box never shows")
                beats.append({"type": "STORY BEAT",
                    "dialogue": st,
                    "_drop": (None if i == 0 else 20 if i == 1
                              else _DROP_OPTIONAL + 20 + i),   # D143
                    "delivery": "Conversational, present-tense. Let the audience co-experience (F45 ritual).",
                    "rehook": deck.draw().format(action=rehook_action)})
            # D7: payoff delivered in-session at ~72-85%, names the same measurable
            # as the hook contract, subverts a named expectation (A7). No "the thing
            # I'll show you tomorrow" — deferral is a broken contract, not retention.
            # D62-class (pipeline v2): the old line was ~40 tokens ("Day 2
            # verdict on X: <measured_claim> — and here's what surprised me: I
            # expected <flop>, but <surprise>."). Spoken <=11 tokens names the
            # measured result; flop → surprise rides the card (D83).
            _proof = _spoken_proof(ctx, presenter)
            payoff_alts = _cap_tokens([f"Day {n_st} verdict: {_proof}.",
                                       f"Verdict: {_proof}."], 11)
            payoff = payoff_alts[0]
            _flop, _surp = _card_flop(ctx)
            payoff_on_screen = _pick_card(
                [f"DAY {n_st}: {_short_product(ctx)} · expected {_flop} → {_surp}",
                 f"DAY {n_st} · expected {_flop} → {_surp}", f"DAY {n_st} · {_surp}"])
            # D1 every-format gate: product-ish story formats get the comment-word
            # engine, never "comment what I test next".
            bait = COMMENT_BAIT[4].format(
                opt1=f"budget {ctx['category']}", opt2=f"premium {ctx['category']}",
                opt3="going without",
                hottake=f"most {ctx['category']}s are overpriced for what they actually do",
                category=ctx["category"],
                cta_word=ctx["category"].upper())
            _cw = ctx["category"].upper()
            bait_alts = [bait, f"Follow, comment {_cw} for the link list.",
                         f"Follow, comment {_cw}."]
            # D7 serialization clause: the next-episode tease is a NEW named promise,
            # made in the CTA beat — it never replaces the episode-N payoff.
            # D46/D89/D146 (pipeline v2): the old CTA re-ran the link-list
            # funnel the bait already owns (two payloads), was ~20 tokens,
            # and promised "frozen fruit in the {category}" on lamps and
            # locks. One serialized promise, <=6 tokens, planned.
            series_next = "the torture test"
            cta = f"Follow, part 2: {series_next}."
            cta_alts = [cta, f"Part 2: {series_next}.", "Follow for part 2."]
    # payoff delivery
    # D27 (judge loop, cycle 10): review scripts pin the verdict on screen.
    payoff_beat = {"type": "PAYOFF",
        "dialogue": payoff,
        # D143: spoken variants for the post-payoff budget (D7 band)
        "_alts": payoff_alts or [payoff],
        "delivery": "Slow down. Let the result land. No scripted laugh (F142)."}
    if payoff_on_screen:
        payoff_beat["on_screen"] = payoff_on_screen
        payoff_beat["_os_alts"] = _card_variants(payoff_on_screen)   # D142
    beats.append(payoff_beat)    # comment bait
    beats.append({"type": "COMMENT BAIT",
        "dialogue": bait,
        "_alts": bait_alts or [bait],
        "note": "Deliberate disagreement / fill-in-blank = comment engine (playbook §17)."})
    # CTA — late, never opening (playbook: 215/349 viral reels have no CTA; make yours explicit but last)
    beats.append({"type": "CTA",
        "dialogue": cta,
        "_alts": cta_alts or [cta],
        "delivery": "Brisk 160–180 wpm (F86)."})
    # D146: the promised next episode, for generate()'s series_plan
    ctx["_series_next"] = series_next
    # D143 (pipeline v2 — replaces the D65 de-overlap pass): TIMELINE FROM
    # CONTENT. The old fixed-fraction anchors (edu at edu_base, demo at D*0.38,
    # evidence at D*0.68, payoff D*0.72–0.85, bait D*0.85–0.94, CTA D*0.94–D,
    # a 2.0s imperfection window for 20–34 words) never looked at the words,
    # and D65 then shifted beats forward without re-timing the contract —
    # 687/990 runs failed D43, 627 D74, 279 D94, 270 D78. Body beats are now
    # appended in NARRATIVE ORDER with no window; _fit_timeline budgets the
    # copy, sizes every window from its own words (vsp.timing.layout: tiled
    # 3.0s→D, payoff inside the D7 72–85% band) and re-times the hook's
    # "delivered at ~Xs" contract to the real payoff start (D94).
    hook, body = _fit_timeline(beats[:2], beats[2:], D, presenter)
    return fam, hook + body


# ------------------------------------------------ D143 content budget helpers
_DROP_OPTIONAL = 30   # D143: a beat whose _drop rank is >= this is OPTIONAL
# D12/D88/D114/D89/D62/D68 doctrine budgets (gate tokens: whitespace split,
# an em dash counts) — the first variant inside the cap is the one that ships.
_TYPE_WORD_CAP = {"IMPERFECTION BEAT": 12, "COMMENT BAIT": 9, "CTA": 6, "PAYOFF": 11}
_CARD_TOKENS, _CARD_CHARS = 12, 66   # D142/D103 card budget (R09: <=70 chars)


def _gate_words(text):
    return len((text or "").split())


def _ai_claims(text):
    """D137: True if text matches a lexicon.AI_FIRST_PERSON pattern."""
    from vsp.lexicon import AI_FIRST_PERSON
    return any(rx.search(text or "") for rx in AI_FIRST_PERSON)


def _bank_variants(tmpl, slots):
    """D143: the bank line plus its BEAT_SHORT_FORMS, rendered with the same
    slots (longest first)."""
    return [tmpl.format(**slots)] + [s.format(**slots)
                                     for s in BEAT_SHORT_FORMS.get(tmpl, ())]


def _cap(s):
    return s[:1].upper() + s[1:] if s else s


def _cap_tokens(alts, n):
    """D62/D68: keep the variants inside the n-token spoken budget; if none
    fits, the longest boundary cut of the shortest one (never mid-clause)."""
    from vsp import timing
    ok = [a for a in alts if _gate_words(a) <= n]
    if ok:
        return ok
    cut = timing.fit_words(alts[-1], n)
    return [cut] if cut else [alts[-1]]


def _spoken_proof(ctx, presenter):
    """D56 positive proof, in the AI lane's curator voice (D137)."""
    p = (ctx.get("purpose_proof") or ctx.get("measured_short")
         or "it did the job")
    return AI_PROOF_REWRITES.get(p, p) if presenter == "ai" else p


def _short_product(ctx):
    """D142/D83: <=2-word product name for cards ("LED sunrise alarm lamp"
    -> "alarm lamp", "car trash can with lid" -> "trash can")."""
    p = re.sub(r"\s+with\s+.*$", "", ctx.get("product") or ctx.get("category", ""))
    p = re.sub(r"^(?:these|this|the|a|an|my)\s+", "", p.strip(), flags=re.I)
    w = p.split()
    if len(w) <= 2:
        return p
    if w[-1].lower() in ("set", "kit", "pack", "bundle"):
        w = w[:-1]
    tail = w[-2:]
    if len(tail) == 2 and (len(tail[0]) <= 1 or tail[0].lower().endswith("ing")):
        tail = tail[-1:]
    return " ".join(tail)


def _card_flop(ctx):
    """D142: (<=3-token flop, <=3-token surprise) for the payoff card."""
    if ctx.get("concept") == "showcase":
        return SHOWCASE_CARD
    cat = ctx.get("category", "")
    return next((v for k, v in CATEGORY_CARD.items() if k in cat), DEFAULT_CARD)


def _card_who(ctx):
    cat = ctx.get("category", "")
    return next((v for k, v in CATEGORY_WHO_SHORT.items() if k in cat), None)


def _pick_card(cands):
    """D142/D103: first candidate inside <=12 tokens ('·', '—', '→' count)
    and the char cap; else the shortest."""
    for c in cands:
        if _gate_words(c) <= _CARD_TOKENS and len(c) <= _CARD_CHARS:
            return c
    return min(cands, key=lambda c: (_gate_words(c), len(c)))


def _card_variants(card):
    """D142: shorter forms of a 'LABEL · ... · expected FLOP → SURPRISE' card
    for tight windows (a card needs len/20 s on screen) — longest first."""
    if not card:
        return []
    segs = [s.strip() for s in card.split(" · ")]
    out = [card, card.replace("expected ", "")]
    tail = segs[-1]
    if len(segs) > 1 and "→" in tail:
        out.append(f"{segs[0]} · {tail.split('→')[-1].strip()}")
    if len(segs) > 1:
        out.append(segs[0])
    uniq = []
    for c in out:
        if c and c not in uniq and _gate_words(c) <= _CARD_TOKENS:
            uniq.append(c)
    return sorted(uniq, key=lambda c: -len(c))


def _d36_subject(prompt):
    """RULES D36: the transformation's real subject — "body" only when the
    prompt is about a body, else vsp.repair's subject map ("hair", "skin",
    "room", ...), else the neutral "angle"."""
    if "body" in (prompt or "").lower():
        return "body"
    from vsp import repair
    return repair.d36_subject({"prompt": prompt or ""})


def _norm_words(text):
    return re.findall(r"[a-z0-9']+", (text or "").lower())


def _echoes(a, b):
    """D41: True if line a restates line b (contained, or >=half of a's
    word trigrams appear in b)."""
    na, nb = _norm_words(a), _norm_words(b)
    if not na or not nb:
        return False
    if " ".join(na) in " ".join(nb):
        return True
    ta = {tuple(na[i:i + 3]) for i in range(len(na) - 2)}
    tb = {tuple(nb[i:i + 3]) for i in range(len(nb) - 2)}
    return bool(ta) and len(ta & tb) / len(ta) >= 0.5


# D44: a spoken slot never ends on a camera location ("... — logged on
# camera.", "..., measured, on camera.") — the shot list owns the camera.
_CAMERA_TAIL = re.compile(r"(?:,|\s[\u2014\u2013])?\s*(?:(?:logged|measured|"
                          r"screen-recorded),?\s+)?on camera(?=[.,!?;]|$)")


def _spoken(s):
    """Final spoken form: D63 voice pass, D44 camera-tail scrub, D90b
    sentence casing (after '. ', '? ' and '! ') and a capital open."""
    if not s:
        return s
    s = _CAMERA_TAIL.sub("", humanize_dialogue(s))
    s = re.sub(r"(?<=[.?!] )([a-z])", lambda m: m.group(1).upper(), s)
    return _cap(s.strip())


def _fix_promises(body):
    """D45/D41 after a beat is budgeted out: a demo re-hook that promised the
    next test now promises what follows (_rh_last); a re-hook whose promised
    beat type is gone falls back (_rh_fallback, or nothing)."""
    for i, b in enumerate(body):
        # a budget-dropped re-hook is kept in _rh_orig for the restore pass —
        # fix whichever field holds it
        f = "_rh_orig" if b.get("_rh_dropped") else "rehook"
        nxt = body[i + 1].get("type") if i + 1 < len(body) else None
        if b.get("_rh_last") and nxt != b.get("type"):
            b[f] = b.pop("_rh_last")
        need = b.get("_rh_needs")
        if need and not any(x.get("type") == need for x in body[i + 1:]):
            b[f] = b.get("_rh_fallback") or ""
            b.pop("_rh_needs", None)
    # D111: a lone surviving demo beat numbers nothing ("TEST 1" with no
    # "TEST 2" once the second demo is budgeted out)
    demos = [b for b in body if b.get("type") == "DEMO BEAT"]
    if len(demos) == 1 and re.match(r"TEST \d+$", demos[0].get("on_screen") or ""):
        d = demos[0]
        d["on_screen"] = "TEST"
        strip = lambda s: _cap(re.sub(r"^Test \d+:\s*", "", s or ""))  # noqa: E731
        d["dialogue"] = strip(d.get("dialogue"))
        d["_alts"] = [strip(a) for a in d.get("_alts") or []]


def _fit_timeline(hook, body, duration, presenter="ai"):
    """D143: final spoken form -> content budget -> content-sized layout ->
    payoff contract re-timed. Returns (hook_stack, body_beats).

    Budget (vsp.timing.min_window per beat: dialogue + re-hook words at the
    delivery's gate rate + 0.3s, on-screen text at <=20 cps): the body must
    fit D-3.0s, and for the D7 band the pre-payoff beats must end by 0.85*D
    while PAYOFF+BAIT+CTA fit in 0.28*D (then the rubric's 68–88% band, then
    feasibility only). Reductions, gentlest first: shorter PAYOFF/BAIT/CTA
    variants (post region) · drop OPTIONAL beats (extra edu/demo, a rejection
    history under a ~35s body) · shorter bank variants · drop the costliest
    re-hook (one always stays past 15s) · trim a line at a sentence/clause
    boundary (vsp.timing.fit_words) · finally, for feasibility only, drop a
    last-resort beat. vsp.repair.retime is the fallback if still infeasible.
    """
    from vsp import timing
    D = float(duration)
    start = 3.0
    B = D - start
    ai = presenter == "ai"
    body = [dict(b) for b in body]
    # 1. final spoken form first: the gates measure what ships (D63 runs here
    #    and again in generate() — it is idempotent).
    for b in body:
        for k in ("rehook", "_rh_last", "_rh_fallback"):
            if b.get(k):
                b[k] = _spoken(b[k])
        alts = [_spoken(a) for a in [b.get("dialogue")] + list(b.get("_alts") or []) if a]
        uniq = []
        for a in alts:
            if a not in uniq:
                uniq.append(a)
        if ai:   # D137: never ship a variant that claims lived experience
            uniq = [a for a in uniq if not _ai_claims(a)] or uniq
            for k in ("rehook", "_rh_last", "_rh_fallback"):
                if b.get(k) and _ai_claims(b[k]):
                    b[k] = ""
        if b.get("type") == "PAYOFF":
            # D143: boundary cuts of the spoken payoff ("Test result: before
            # and after." from "..., side by side.") as last-resort variants
            # for sub-25s bands — never mid-clause (fit_words), >=4 tokens.
            for a in list(uniq):
                for n in range(_gate_words(a) - 1, 3, -1):
                    cut = timing.fit_words(a, n)
                    if cut and cut not in uniq and _gate_words(cut) >= 4:
                        uniq.append(cut)
        uniq.sort(key=lambda a: -_gate_words(a))       # stable: longest first
        cap = _TYPE_WORD_CAP.get(b.get("type"))
        if cap and uniq:
            inside = [a for a in uniq if _gate_words(a) <= cap]
            if not inside:
                cut = timing.fit_words(uniq[-1], cap)
                inside = [cut] if cut else uniq[-1:]
            uniq = inside
        if uniq:
            b["dialogue"], b["_alts"] = uniq[0], uniq
    # 2. D41/D93: a re-hook never restates its own beat or another re-hook
    seen = set()
    for b in body:
        rh = b.get("rehook")
        if not rh:
            continue
        key = " ".join(_norm_words(rh))
        if _echoes(rh, b.get("dialogue")) or key in seen:
            b["rehook"] = ""
            b["_rh_dropped"] = True
        seen.add(key)

    # 3. budget loop
    def pay_idx():
        return next((i for i, b in enumerate(body) if b.get("type") == "PAYOFF"),
                    len(body))

    def regions():
        m = [timing.min_window(b) for b in body]
        k = pay_idx()
        return sum(m[:k]), sum(m[k:]), m, k

    def next_alt(b):
        # the next shorter spoken variant — or card variant — that actually
        # shrinks the beat's minimum window (words are never spent for nothing)
        base = timing.min_window(b)
        cur = _gate_words(b.get("dialogue"))
        for a in b.get("_alts") or []:
            if _gate_words(a) < cur and \
                    timing.min_window(dict(b, dialogue=a)) < base - 1e-9:
                b["dialogue"] = a
                return True
        cur_os = len(b.get("on_screen") or "")
        for c in b.get("_os_alts") or []:
            if len(c) < cur_os and \
                    timing.min_window(dict(b, on_screen=c)) < base - 1e-9:
                b["on_screen"] = c
                return True
        return False

    rot = [0]

    def post_alt():   # CTA -> BAIT -> PAYOFF, one step each in turn
        k = pay_idx()
        order = [i for ty in ("CTA", "COMMENT BAIT", "PAYOFF")
                 for i in range(k, len(body)) if body[i].get("type") == ty]
        for j in range(len(order)):
            i = order[(rot[0] + j) % len(order)]
            if next_alt(body[i]):
                rot[0] = (rot[0] + j + 1) % len(order)
                return True
        return False

    def drop(lo, hi):
        k = pay_idx()
        c = [(b["_drop"], i) for i, b in enumerate(body[:k])
             if b.get("_drop") is not None and lo <= b["_drop"] < hi]
        if not c:
            return False
        del body[max(c)[1]]
        _fix_promises(body)
        return True

    def drop_cta():
        # sub-18s only, and only once every post-payoff variant is spent:
        # PAYOFF+BAIT+CTA cannot fit the 28% post-payoff band at their
        # floors (3 x 1.5s > 0.28*15s); the comment bait already carries the
        # follow ask (playbook: 215/349 viral reels ship no CTA) — D7 wins.
        i = next((j for j, b in enumerate(body) if b.get("type") == "CTA"), None)
        if i is None or sum(1 for b in body if b.get("type") != "CTA") < 3:
            return False
        del body[i]
        return True

    def pre_alt():
        _, _, m, k = regions()
        return any(next_alt(body[i]) for i in sorted(range(k), key=lambda i: -m[i]))

    def drop_rehook():
        _, _, m, k = regions()
        have = [i for i, b in enumerate(body) if b.get("rehook")]
        if D > 15 and len(have) <= 1:
            return False           # the rubric's "no re-hooks" floor past 15s
        c = [i for i in have if i < k]
        if not c:
            return False
        i = max(c, key=lambda i: (_gate_words(body[i]["rehook"])
                                  / timing.wps(body[i].get("delivery")), i))
        body[i]["_rh_orig"] = body[i]["rehook"]
        body[i]["rehook"] = ""
        body[i]["_rh_dropped"] = True
        return True

    def trim(post=False):   # sentence/clause boundary only (fit_words), >=3 words kept
        _, _, m, k = regions()
        for i in sorted(range(len(body) if post else k), key=lambda i: -m[i]):
            d = body[i].get("dialogue") or ""
            n = _gate_words(d)
            new = timing.fit_words(d, n - 1) if n > 4 else None
            if new and 3 <= _gate_words(new) < n:
                body[i]["dialogue"] = new
                return True
        return False

    levels = [(0.72, 0.85), (0.68, 0.88), None]
    lvl = 0
    for _ in range(500):
        pre, post, m, k = regions()
        band = levels[lvl]
        tot_over = pre + post > B + 1e-6
        if band is None:
            if not tot_over:
                break
            post_over, pre_over = False, True
        else:
            post_over = post > (1 - band[0]) * D + 1e-6
            pre_over = tot_over or pre > band[1] * D - start + 1e-6
            if not (post_over or pre_over):
                break
        if post_over and post_alt():
            continue
        if post_over and D < 18 and drop_cta():
            continue
        if pre_over:
            if drop(_DROP_OPTIONAL, 10 ** 6) or pre_alt() or drop_rehook() or trim():
                continue
            if band is None and (drop(0, _DROP_OPTIONAL) or trim(post=True)):
                continue
            if tot_over and post_alt():
                continue
        if band is None:
            break
        lvl += 1

    # 4. restore: the greedy reductions can over-cut (a short variant taken
    #    before a re-hook drop made it unnecessary) — give back, in narrative
    #    order, the longest line / card / re-hook the reached budget allows.
    def holds():
        pre, post, _, _ = regions()
        band = levels[lvl]
        return pre + post <= B + 1e-6 and (band is None or (
            post <= (1 - band[0]) * D + 1e-6 and
            pre <= band[1] * D - start + 1e-6))

    if holds():
        # with no band reached, a longer post-payoff line only moves the
        # payoff earlier — restore the pre-payoff beats only
        scope = body if levels[lvl] is not None else body[:pay_idx()]
        for field, alts_key in (("dialogue", "_alts"), ("on_screen", "_os_alts")):
            for b in scope:
                cur = b.get(field) or ""
                longer = [a for a in b.get(alts_key) or [] if len(a) > len(cur)
                          and (field == "on_screen" or _gate_words(a) > _gate_words(cur))]
                for a in longer:          # longest first
                    b[field] = a
                    if holds():
                        break
                    b[field] = cur
        for b in body:
            if b.get("_rh_orig") and not b.get("rehook"):
                b["rehook"] = b["_rh_orig"]
                if not holds():
                    b["rehook"] = ""
    # 5. ship only public keys; lay out; re-time the contract (D94)
    body = [{k: v for k, v in b.items() if not k.startswith("_") and
             not (k == "rehook" and not v)} for b in body]
    laid, info = timing.layout(body, D, start=start)
    hook = timing.retime_contract(hook, info["payoff_start"])
    if not info["feasible"]:
        # last resort (tiny durations): the proven trim loop — relayout,
        # boundary trims, re-hook drops, restore over-trims (vsp.repair)
        from vsp import repair
        s, _ = repair.retime({"duration_s": duration, "hook_stack": hook,
                              "beats": laid})
        hook, laid = s["hook_stack"], s["beats"]
    return hook, laid

def _bt(b):
    """Parse a beat's 't' window ('3.0–7.4s') -> (start, end). Module-level so the
    D65 de-overlap pass can sort beats without depending on pipeline.py."""
    m = re.findall(r"(\d+(?:\.\d+)?)", b.get("t", "") or "")
    return (float(m[0]), float(m[1])) if len(m) >= 2 else (None, None)

# D107 (gauntlet cycle 10): beauty sub-category tag hygiene. #skincare on a hair
# product is a within-niche mis-route (pipeline.py's MISMATCH list already
# flags ("skincare","hair") — the gate caught it, the maker ignored it). The
# tag map AND the comment word are scoped by sub-category: hair products get
# #hairtok + HAIR; skin keeps #skincare + GLOW; makeup gets #makeuptok.
_BEAUTY_SUBCAT_TAGS = {
    "hair":   (["#beautytok", "#hairtok"], "HAIR"),
    "skin":   (["#beautytok", "#skincare"], "GLOW"),
    "makeup": (["#beautytok", "#makeuptok"], "GLOW"),
}
def _beauty_subcat(ctx):
    low = (str(ctx.get("product", "")) + " " + str(ctx.get("category", ""))).lower()
    if re.search(r"\b(hair|shampoo|conditioner|straightener|curler|dryer|pomade|wax\s?stick)\b", low):
        return "hair"
    if re.search(r"\b(makeup|lipstick|foundation|mascara|eyelash|eyelashes|blush|eyeshadow|liner|concealer)\b", low):
        return "makeup"
    if re.search(r"\b(skin|serum|cream|moisturizer|cleanser|toner|acne|exfoliat)\b", low):
        return "skin"
    return None  # unclassifiable beauty keeps the legacy beauty tags/word

def _scoped_tags(ctx):
    if ctx.get("niche") == "beauty":
        sub = _beauty_subcat(ctx)
        if sub:
            return _BEAUTY_SUBCAT_TAGS[sub][0]
    return CAPTION_TAGS.get(ctx["niche"], CAPTION_TAGS["default"])

def _cta_word(ctx):
    # D107: beauty comment word is sub-category scoped ("comment HAIR" on hair
    # products, never "comment GLOW").
    if ctx.get("niche") == "beauty":
        sub = _beauty_subcat(ctx)
        if sub:
            return _BEAUTY_SUBCAT_TAGS[sub][1]
    return NICHE_COMMENT_WORD.get(ctx.get("niche"), ctx["category"].upper())

def build_caption(ctx, hookline, fmt, presenter):
    tags = _scoped_tags(ctx)
    # D10/E8: challenge captions name the method and carry the join-the-count
    # CTA — never a link list, never generic follow-bait.
    if ctx.get("concept") == "challenge":
        niche = ctx.get("niche", "default")
        # D121 (judge loop, cycle 31): ABSTINENCE CAPTIONS NEVER INHERIT THE
        # VICE NOUN'S NICHE. "stopped drinking coffee" matched food ("coffee")
        # and the D107 branch shipped #foodtok #recipe on a quit-coffee
        # challenge (seed 938) — a recipe community on an abstinence video,
        # the D11-family bleed (thirteenth occurrence). Only practice
        # challenges are genuinely content of the noun's niche (D67's
        # "cooked every meal at home" → #foodtok); abstinence captions on the
        # habit community. #digitaldetox stays gated to the screen class it
        # was written for (D106).
        if ctx.get("challenge_type") == "practice":
            if niche != "default":
                # D67 (judge loop, cycle 17): practice-food challenges route the
                # food caption community (#foodtok) — the challenge-only tag set
                # (#digitaldetox) mis-routes them (D11/D14/D18/D20/D24 class).
                tags = ["#30daychallenge"] + _scoped_tags(ctx)  # D107
            else:
                tags = ["#30daychallenge", "#selfimprovement"]  # D106
        else:
            tags = ["#30daychallenge"]
            if (ctx.get("abstinence_class") or "screen") == "screen":
                tags.append("#digitaldetox")  # D106: doomscrolling class only
            tags.append("#selfimprovement")
        method = f"The {ctx['span_n']}-Day {ctx['challenge_noun'].title()} Reset"
        lines = [hookline, "",
                 f"{method} — Day {ctx['span_n']} results.",
                 "", "Comment DAY1 to start your own count. 👇", ""]
    # D47 (judge loop, cycle 13): routine captions name the method (E8), ask
    # the wake-time fill-in (identity comment — the comment engine, §17), and
    # tag the routine community (#morningroutine/#5amclub), never #viral.
    elif ctx.get("concept") == "routine":
        tags = (CAPTION_TAGS["routine"] if ctx.get("niche") == "wellness"
                else CAPTION_TAGS.get(ctx["niche"], CAPTION_TAGS["default"]))
        method = (f"The {ctx['routine_time']} Rule" if ctx.get("niche") == "wellness"
                  else ctx["routine_label"].title())
        lines = [hookline, "",
                 f"{method} — Day {ctx['streak']} results.",
                 "", "What time do you get up? 👇", ""]
    # D13-fix (judge loop, cycle 6): caption content follows the CONCEPT class,
    # not the format — a talking-head product script gets the product caption
    # (was landing in the advice-caption branch: "Follow for the daily
    # breakdown" under a sleep-gummies ad).
    elif ctx.get("concept") in ("product", "showcase"):
        # D13-fix2 (judge loop, cycle 6): old line "POV: your {category} finally
        # does its job" broke agreement on plural categories ("your gummies
        # finally does"). Agreement-free phrasing.
        # D59 (judge loop, cycle 15 — code enforcement): the comment-word CTA
        # must echo in the caption, not live only in dialogue —
        # julianna_claire's captions carry the keyword + payload line on every
        # viral product reel (part of conversion happens at the caption, where
        # the spoken CTA is skimmed). Same keyword as the bait beat, or the
        # funnel splits.
        cta_word = _cta_word(ctx)  # D107: beauty sub-category scoped
        lines = [hookline, "",
                 f"POV: the {ctx['category']} that finally delivered.",
                 "", f"Comment {cta_word} for the full link list 👇", ""]
    else:
        lines = [hookline, "",
                 "Follow for the daily breakdown.", ""]
    if presenter == "ai":
        lines.append("made with an AI persona")
        lines.append("")
    lines.append(" ".join(tags))
    return "\n".join(lines)

def research_notes(ctx, presenter, fmt, fam):
    notes = []
    if _PACK and not _NO_RESEARCH:
        top3 = ", ".join(h["category"] for h in _PACK.get("top_hooks", [])[:3])
        pat3 = ", ".join(p["pattern"] for p in _PACK.get("top_patterns", [])[:3])
        # py3.9 compatibility (pipeline v2): same-quote nested f-strings are
        # PEP 701 (3.12+) syntax — they made the whole pipeline a SyntaxError
        # on 3.9-3.11. Single-quoted keys; .get() so a partial pack can't raise.
        notes.append(f"LIVE RESEARCH (pack {str(_PACK.get('generated_at', ''))[:10]}, "
                     f"{_PACK.get('reels_total', 0)} reels): "
                     f"top hook families now: {top3}; top patterns: {pat3}.")
        fresh = _PACK.get("fresh_hook_lines", [])[:3]
        for fr in fresh:
            notes.append(f"Fresh from the DB ({fr.get('account')}, {fr.get('niche')}): "
                         f"\"{fr.get('hook')}\"")
    notes += [
      f"Hook family '{fam}': curiosity-gap + bold-claim = ~41% of viral hooks (hooks playbook §2).",
      "3-layer hook stack: visual 0–0.5s / verbal ≤8 words 0.5–1.5s / lock by 3.0s (playbook §1).",
      "Payoff contract: specific reward named in hook, delivered ~78% through — never frontloaded (playbook §3).",
      "Re-hooks every beat: open loops keep retention past the 3–5s mark (Robins analysis).",
      "85% watch muted → frame-0 visual + ≤3-word on-screen text (playbook §4).",
      "Educational beats before evaluative pitch (F103, persona dossier: educational > evaluative for VIs).",
      "Pacing by objective: unhurried for trust beats, brisk 160–180 wpm for CTA (F86/F138/F139).",
      "No scripted laughs/sighs — volitional vocalizations read inauthentic (F142).",
    ]
    if presenter == "ai":
        notes += [
          f"Persona–product fit: '{ctx['fit']}' SKU. " +
          ("Utilitarian = congruent lane for AI personas (F32/F34)." if ctx["fit"]=="utilitarian"
           else "Hedonic = humans win here; AI persona is the wrong anchor (F32)." if ctx["fit"]=="hedonic"
           else "Fit unclear — test both anchors."),
          "Attractiveness is a top-of-funnel amplifier, not a conversion lever — don't over-invest in beauty (Q1).",
          "Frame-0 AI disclosure: small on-screen 'AI persona' label, separate from hook text, top safe zone (G6/FTC).",
          "Autonomy cue: persona 'decides' to test — perceived autonomy is the VI-specific bond driver (F143).",
          "Engagement ladder: comments → DMs → community; conversion lags engagement (Q9/F112).",
        ]
    else:
        notes += [
          "Borrowed authority: name-drop an in-niche known figure (Robins rule).",
          "Delivery: confident-dynamism, never pressuring/harsh (UGC Q4 composite).",
          "Similarity > beauty for presenter appeal (JTAER 2025).",
        ]
    if ctx["niche"] in ("gadgets","tech","tools"):
        notes.append("Format note: split-screen sub-$10 gadget demos are a top trend (viral-trends-watch 2026-09-27).")
    return notes

def _load_personas():
    # Persona-loop x pipeline: house AI-persona registry (personas.json). One
    # face across every video — Q2/F10: identity drift triggers eerie rejection,
    # F9: same-face repetition builds liking. Never edit a shipped entry.
    try:
        with open(os.path.join(os.path.dirname(__file__), "personas.json")) as f:
            return json.load(f)
    except Exception:
        return {}

def _resolve_persona(presenter, name):
    if presenter != "ai":
        return None
    reg = _load_personas()
    key = name or "maya"
    entry = reg.get(key, reg.get("maya"))
    if not entry or key.startswith("_"):
        return None
    return {"name": entry.get("name", key), "identity": entry["identity"],
            "voice": entry.get("voice", ""), "styling_rule": entry.get("styling_rule", "")}

def generate(prompt, presenter="ai", fmt="demo", duration=30, seed=None, use_research=True, persona=None):
    global _NO_RESEARCH
    _NO_RESEARCH = not use_research or _PACK is None
    rng = random.Random(seed)
    # D31 + pipeline v2 crash fix: template braces in the prompt ("a {limited}
    # edition bottle") are never product text — strip them before parsing so
    # no raw {slot} can reach a template or the viewer.
    ctx = parse_prompt(re.sub(r"\s+", " ", re.sub(r"[{}]", "", prompt)).strip())
    ctx["_prompt"] = prompt   # D36: the evidence line names the prompt's subject
    fam, beats = build_beats(ctx, duration, rng, fmt, presenter)
    # D63: spoken-voice pass over every spoken string before the script ships —
    # gates below measure the final spoken words, not the raw templates.
    for b in beats:
        if b.get("dialogue"):
            b["dialogue"] = humanize_dialogue(b["dialogue"])
        if b.get("rehook"):
            b["rehook"] = humanize_dialogue(b["rehook"])
    hookline = beats[1]["dialogue"]
    caption = build_caption(ctx, hookline, fmt, presenter)
    fit_warning = None
    if presenter == "ai" and ctx["fit"] == "hedonic":
        fit_warning = ("FIT WARNING (F32): hedonic SKU + AI persona = humans convert better. "
                       "Consider --presenter human, or reframe the product as functional.")
    script = {
        "prompt": prompt, "presenter": presenter, "format": fmt,
        "duration_s": duration, "niche": ctx["niche"], "fit": ctx["fit"],
        "hook_family": fam, "fit_warning": fit_warning,
        "persona": _resolve_persona(presenter, persona),
        "hook_stack": beats[0:2], "beats": beats[2:],
        "caption": caption,
        "research_notes": research_notes(ctx, presenter, fmt, fam),
        # D145: what actually rendered the hook (GEN-B's pick_hook sets it)
        "hook_source": ctx.get("hook_source") or "template",
    }
    # D146: a CTA that promises the next episode ("Follow, part 2: the
    # torture test." / "Tomorrow: Day 15.") ships its plan — an unplanned
    # series promise is a broken contract.
    cta_line = next((b.get("dialogue") or "" for b in script["beats"]
                     if b.get("type") == "CTA"), "")
    if ctx.get("_series_next") and re.search(r"\bpart (?:2|two)\b|\btomorrow\b",
                                             cta_line, re.I):
        script["series_plan"] = {"next": ctx["_series_next"], "cta": cta_line}
    if presenter == "ai":
        script["disclosure"] = PERSONA_DISCLOSURE
    else:
        script["delivery_note"] = HUMAN_NOTE
    return script

def render_text(s):
    L = []
    L.append("=" * 64)
    L.append(f"VIRAL SCRIPT — {s['format'].upper()} · {s['duration_s']}s · presenter: {s['presenter'].upper()}")
    L.append(f"Prompt: {s['prompt']}")
    L.append(f"Niche: {s['niche']} · Fit: {s['fit']} · Hook family: {s['hook_family']}")
    if s["fit_warning"]:
        L.append("!! " + s["fit_warning"])
    L.append("=" * 64)
    L.append("")
    L.append("--- HOOK STACK (first 3 seconds) ---")
    for b in s["hook_stack"]:
        L.append(f"[{b['t']}] {b['type']}")
        for k in ("direction", "dialogue", "on_screen", "payoff_contract", "delivery"):
            if k in b: L.append(f"  {k}: {b[k]}")
        L.append("")
    L.append("--- BEATS ---")
    for b in s["beats"]:
        L.append(f"[{b['t']}] {b['type']}")
        for k in ("dialogue", "direction", "on_screen", "delivery", "rehook", "note"):
            if k in b: L.append(f"  {k}: {b[k]}")
        L.append("")
    L.append("--- CAPTION ---")
    L.append(s["caption"])
    L.append("")
    if "disclosure" in s:
        L.append("--- DISCLOSURE ---"); L.append(s["disclosure"]); L.append("")
    if "delivery_note" in s:
        L.append("--- DELIVERY ---"); L.append(s["delivery_note"]); L.append("")
    L.append("--- RESEARCH NOTES (why each choice) ---")
    for n in s["research_notes"]:
        L.append("• " + n)
    return "\n".join(L)

def main():
    ap = argparse.ArgumentParser(description="Viral script maker — research-grounded short-form scripts from a basic prompt.")
    ap.add_argument("prompt", help='Basic prompt, e.g. "a $12 LED sunrise alarm lamp"')
    ap.add_argument("--presenter", choices=["ai", "human"], default="ai")
    ap.add_argument("--format", choices=["demo", "talking-head", "pov-vlog", "transformation", "review"], default="demo")
    ap.add_argument("--duration", type=int, default=30)
    ap.add_argument("--seed", type=int, default=None, help="Fixed seed for reproducible scripts")
    ap.add_argument("--json", action="store_true", help="Machine-readable output for the pipeline")
    ap.add_argument("--persona", default=None,
                    help="House AI persona from personas.json (default: maya for --presenter ai; ignored for human)")
    ap.add_argument("--no-research", action="store_true", help="Ignore the live research pack (frozen rulebook only)")
    a = ap.parse_args()
    s = generate(a.prompt, presenter=a.presenter, fmt=a.format, duration=a.duration, seed=a.seed,
                 use_research=not a.no_research, persona=a.persona)
    if a.json:
        print(json.dumps(s, indent=2, ensure_ascii=False))
    else:
        print(render_text(s))

if __name__ == "__main__":
    main()
