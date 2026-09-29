"""Shared creative vocabulary (pipeline v2.1) — one set of ids for the
creative-direction (vsp.direction), hook (vsp.hooks), shot (vsp.shotplan /
make_shotlist) and discovery (vsp.discovery) modules and their evaluators.

Ids are stable contract values: scripts, shots.json, the rubric and the
feedback loop store them. Add ids; never rename or remove one.
"""

PLATFORMS = ("tiktok", "instagram", "youtube_shorts")

# Video vibe profiles (the overall feel). Parameters (pacing, music, look)
# live in vsp/direction.py; this is the id list + one-line meaning.
VIBES = {
    "raw-ugc": "lo-fi phone footage, handheld, natural light, talking to a friend",
    "clean-aesthetic": "minimal set, soft even light, neutral palette, calm confidence",
    "hype-energy": "fast cuts, bold text, upbeat music, high energy delivery",
    "cozy-calm": "warm low light, slow pacing, soft voice, low-tempo music bed",
    "expert-trust": "steady medium shots, clear labels, measured authoritative delivery",
    "playful-comedic": "quick punchlines, reaction shots, meme timing",
    "cinematic-premium": "macro and slow motion, dramatic light, product as hero",
    "asmr-satisfying": "close-up textures and real product sound, little or no music",
    "story-vlog": "selfie and walk-and-talk diary, present tense, day markers",
    "before-after-reveal": "transformation-first, matched framing, the gap is the star",
}

# Voice tone of the presenter / voiceover.
TONES = ("warm", "confident", "excited", "calm", "deadpan", "expert",
         "playful", "empathetic")

# Frame-0 visual hook types (what the first frame shows). Alternate openings
# (hook_variants) must differ in visual_type: Meta treats ads that share an
# opening as the same creative.
VISUAL_TYPES = {
    "product-in-action": "the product doing its job mid-motion, hands in frame",
    "result-reveal": "the end result shown first (the after-state)",
    "before-after-split": "split screen, before left, after right, matched framing",
    "problem-state": "the problem at its worst (mess, fail, frustration)",
    "pov-hands": "first-person POV, the viewer's hands using the product",
    "face-reaction": "the presenter's reaction with the product or result in frame",
    "text-first": "a bold text card over motion (built for muted viewers)",
    "unboxing": "package opening mid-action",
    "comparison": "side by side with the alternative",
    "day-counter": "a day-N marker over the streak or routine in progress",
    "satisfying-macro": "extreme close-up texture or sound moment",
}

# Hook archetypes. The first eight are viral_script_maker.HOOKS families;
# vsp.hooks may add maker families for the others. Flags: requires_price /
# requires_proof / requires_offer = only when the prompt supplies it (D37,
# D136, D158); human_only = never for an AI presenter (D137).
HOOK_ARCHETYPES = {
    "curiosity-gap": {},
    "bold-claim": {},
    "negative-command": {},
    "proof-first": {"requires_proof": True},
    "transformation": {},
    "story-time": {"human_only": True},
    "contrarian-reframe": {},
    "identity-reveal": {},
    "problem-agitate": {},
    "question": {},
    "comparison": {},
    "pov": {},
    "newness": {},
    "confession": {"human_only": True},
    "price-anchor": {"requires_price": True},
    "listicle": {},
    "challenge": {},
    "day-counter": {},
    "showcase": {},
}

SHOT_SCALES = ("ECU", "CU", "MCU", "MS", "MWS", "WS")
SHOT_ANGLES = ("eye-level", "high", "low", "overhead", "pov", "over-shoulder",
               "profile", "three-quarter", "split")
# Camera moves. Gate 2 (D48) only recognises these words in a shot's lines:
# push-in, push in, pan, tilt, dolly, handheld, tracking, move — a long shot
# must name one of them.
CAMERA_MOVES = ("static", "push-in", "pull-out", "pan", "tilt", "handheld",
                "tracking", "orbit", "whip-pan", "dolly", "speed-ramp")
SHOT_PURPOSES = ("hook", "context", "proof", "demo", "emotion", "payoff",
                 "cta", "b-roll", "transition", "reaction")

# Phrases that must never appear in NEW bundle sections (they trip legacy
# gate-2 checks or leak test data): D46 link groups, D36, D43, D151.
BUNDLE_FORBIDDEN = ("link in bio", "link list", "in your dms", "check your dms",
                    "tap the link", "same body", "D43 WARNING", "### Shot",
                    "FIXTURE")
