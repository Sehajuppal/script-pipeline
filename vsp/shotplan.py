"""vsp/shotplan.py — shot recommender (pipeline v2.1, docs/CREATIVE-PLAN.md §1.4).

    plan(script, shots, ctx=None) -> shots
        Re-cuts the beat groups make_shotlist.build_shots produced and gives
        every shot a named SHOT_LIBRARY type with a reason, plus the §1.4 keys:
        shot_type, scale, angle, move, purpose, energy, needs, ai_risk,
        ai_fallback, real_footage, setup, broll, sfx (extras: why,
        light_preset, ai_swapped_from, real_footage_why).
    block_lines(sh) -> ["- Camera: ...", "- Shot type: ...", ...]
        The exact '- ' lines of a '### Shot' block (gate 2 parses these).
    visual_prompt(sh, assets) / prompt_assets(...)
        D160-clean generation prompt per shot (Veo/Gemini structure).
    shoot_plan_md(script, shots, assets) -> "## SHOOT PLAN — setups, props, B-roll" section
    alt_openings_md(script, assets) -> "## ALTERNATE OPENINGS — variant cuts" section
    selfcheck() -> (ok, lines)   hermetic: golden x 5 formats x 2 presenters,
        gate 2, D157/D160 criteria, determinism, runtime, synthetic contracts.

Tables: vsp/data/shot_library.json (verbatim from
docs/research/shots-cinematography.md §5). Rules applied (SHOT_RULES.hard):
frame 0 shows the product/result (subject/problem for no-product concepts),
never a talking head; a human (face or hands) by 3.0 s, a face by 3.0 s for
human presenters and the TikTok Shop lane; never 3 consecutive shots at one
scale; >3.5 s unsplit shots carry a real camera move (D48); the last shot
returns to frame 0 when duration <= 15 s. presenter=ai: high-risk shots follow
ai_fallback to med/low, and proof shots (evidence, payoff results, demo
tests, before/after, measured or durable results) are REAL FOOTAGE — an
AI-rendered proof is fabricated evidence (research §4.5).

Deterministic (no RNG, no set iteration in outputs), stdlib only, py3.9+.
"""
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(_HERE, "data", "shot_library.json")
_CACHE = {}

# gate 2's D48 vocabulary (vsp/gates.py g2_d48_internal_cuts, substring match)
MOVE_KW = ("push-in", "push in", "pan", "tilt", "dolly", "handheld", "tracking", "move")
STATIC_MAX = 3.5
SUB_MIN_S, SUB_MAX_S = 1.2, 3.1          # direction pacing bounds for sub-shots
LEGACY_SUB_S = 2.5                       # make_shotlist.SUBSHOT_TARGET_S
SCALE_ORDER = ("WS", "MWS", "MS", "MCU", "CU", "ECU")   # wide -> tight
FORMATS = ("demo", "talking-head", "pov-vlog", "transformation", "review")

_TIKTOK_SHOP = re.compile(r"\btik ?tok[- ]?shop\b|\btt ?shop\b", re.I)  # = vsp.router


def data():
    """The transcribed research tables (cached) + BY_ID index."""
    d = _CACHE.get("data")
    if d is None:
        with open(DATA_PATH, encoding="utf-8") as f:
            d = json.load(f)
        d["BY_ID"] = {s["id"]: s for s in d["SHOT_LIBRARY"]}
        rules = d["SHOT_RULES"]
        d["TH_IDS"] = tuple(rules["talking_head_ids"])
        d["BANNED_F0"] = tuple(rules["hard"]["frame0"]["banned_ids_at_frame0"])
        step = {}
        for st in d["SHOOT_PLAN_RULES"]["setup_order"]:
            for i in st["ids"]:
                step.setdefault(i, st["step"])
        d["STEP"] = step
        _CACHE["data"] = d
    return d


def lib(tid):
    return data()["BY_ID"][tid]


# --------------------------------------------------------------- wording
SCALE_WORDS = {"ECU": "extreme close-up", "CU": "close-up", "MCU": "medium close-up",
               "MS": "medium shot", "MWS": "medium-wide shot", "WS": "wide shot"}
ANGLE_WORDS = {"eye-level": "eye level", "high": "slightly high angle", "low": "low angle",
               "overhead": "overhead", "pov": "first-person POV", "over-shoulder":
               "over the shoulder", "profile": "profile", "three-quarter": "three-quarter angle",
               "split": "split screen"}
# the phrase that names each move in a prompt / camera line; every moving id
# carries a gate-2 D48 keyword (SHOT_RULES.hard.d48_compatibility)
MOVE_WORDS = {"static": "static camera", "push-in": "slow push-in", "pull-out": "dolly out",
              "pan": "slow pan", "tilt": "slow tilt", "handheld": "handheld",
              "tracking": "tracking", "orbit": "tracking arc (orbit)", "whip-pan": "whip pan",
              "dolly": "slow dolly", "speed-ramp": "handheld push-in, speed-ramped"}

# Shot-list framing ("- Camera:" line) per type, written for a phone creator.
# Contract with gate 2: "to camera" appears exactly in the talking-head ids
# (D47 counts them honestly); a D48 move keyword appears exactly when the
# type moves; static framings use "locked-off" and no keyword substrings.
FRAMING = {
    "hook-hands-mid-action": "Frame-0 hands mid-action: close-up from slightly above, hands already using {p}, product filling the lower two-thirds, subtle push-in",
    "result-first-reveal": "Result first: close-up at eye level on the finished result of {p}, the product at the frame edge, slow push-in",
    "problem-state-open": "Problem at its worst: medium shot from above, handheld, {problem}, untidied",
    "split-before-after": "Split-screen BEFORE | AFTER built in the edit: two matched clips from one taped phone spot, same lens and light, locked-off",
    "pov-hands-first-use": "POV hands: first-person close-up, handheld, both hands use {p} with one simple motion",
    "face-reaction-product": "Reaction with {p} in frame: medium close-up at eye level, handheld, a genuine silent first reaction, product in the lower third",
    "text-card-over-motion": "Text-first card over motion: close-up, slow push-in on {p}; the 3-word card is added in the edit",
    "unboxing-mid-open": "Unboxing mid-open: top-down close-up, handheld, the box already half-open with {p} inside",
    "comparison-side-by-side": "Side by side with the alternative: medium shot, slow pan from an unbranded alternative to {p}, one surface, one light",
    "day-counter-selfie": "Day-N check-in to camera: front-camera medium close-up, handheld, same spot and time each day; the Day N marker is added in the edit",
    "macro-texture-ecu": "Macro texture: extreme close-up across {p}, very slow push-in, focus and exposure locked, real sound up close",
    "label-detail-ecu": "Label detail: extreme close-up at a three-quarter angle, slow tilt down the real label, each line held a full second",
    "talking-head-mcu": "Talking head to camera: medium close-up at eye level, locked-off on a stand, window light",
    "talking-head-product-in-hand": "To camera with {p} in hand: medium close-up, product at chin height facing the lens, slow push-in",
    "selfie-walk-talk": "Selfie walk-and-talk to camera: front camera at arm's length, tracking as you walk slowly, present tense",
    "mws-cta-to-camera": "Medium-wide CTA to camera: presenter beside {p}, slow push-in on the comment prompt; the keyword card is added in the edit",
    "reaction-cutaway-3q": "Reaction cutaway: medium close-up at a three-quarter angle, locked-off, a silent nod at {subject}, eyes off-lens",
    "profile-look-cutaway": "Profile look: medium close-up side-on, locked-off, the presenter studies {p}, window light on the far side of the face",
    "jump-cut-punch-in": "Jump-cut punch-in on the talking head to camera: an edit push-in (1.3x crop) on the key word, nothing extra to film",
    "confession-handheld-cu": "Candid confession to camera: handheld close-up, a little tighter than the talking head, one unrehearsed take",
    "over-shoulder-demo": "Over-shoulder demo: medium shot over the shoulder, handheld, hands do the real task with {p} start to finish",
    "overhead-hands-demo": "Top-down hands demo: medium shot from directly above, locked-off, hands enter from the bottom edge and do one step with {p}",
    "product-operating-cu": "Product doing its job: close-up from slightly above, slow push-in on the working end of {p}, hands out of frame",
    "step-insert-cu": "Step insert: tight close-up from above, locked-off, one press, twist or click on {p} with its real sound",
    "feature-callout-hero": "Feature call-out: close-up at a three-quarter angle, slow push-in toward the key feature of {p}; the circle or arrow is added in the edit",
    "timelapse-process": "Time-lapse: phone locked on a stand from above, the slow process with {p} compressed into seconds",
    "slowmo-hero-moment": "Slow-motion hero moment: close-up at eye level, handheld push-in, speed-ramped into 120 fps slow motion on the key moment with {p}",
    "pour-dispense-cu": "Pour close-up: from above, locked-off, one slow pour or pump from {p}, sound close to the mic",
    "hand-enters-pickup": "Hand enters and picks up: close-up at eye level, locked-off, {p} alone, then a hand enters from the bottom edge and lifts it",
    "turn-in-hand-light": "Turn in hand: close-up at eye level, locked-off, facing the window, {p} rotated slowly so the light travels across it",
    "product-hero-orbit": "Orbit: close-up at a three-quarter angle, tracking arc (orbit) around {p} on a lazy Susan or a slow half-circle",
    "hero-static-push-in": "Product hero: close-up at a three-quarter angle, slow push-in on {p} on a clean surface, side window light",
    "flat-lay-reveal": "Flat lay: top-down medium shot, slow push-in over {p} and everything it comes with, laid out in a grid",
    "lifestyle-context-ws": "In its real setting: medium-wide at eye level, slow dolly sideways past {p} where it actually lives",
    "establishing-ws": "Establishing wide: from the doorway at eye level, slow pan across the place to set the time and location",
    "matched-before": "Matched BEFORE: medium shot at eye level from a taped phone spot, locked-off, a clock or date card in frame, filters off",
    "matched-after": "Matched AFTER: the same taped spot, lens, light and framing as the BEFORE, locked-off, date visible",
    "match-cut-transform": "Match-cut transformation: a whip pan past the lens from the same taped spot, cut mid-motion from BEFORE to AFTER",
    "timestamp-proof-insert": "Timestamped proof insert: close-up from above, locked-off on the real reading (timer, scale or phone clock), held long enough to read",
    "screen-insert": "Phone-screen insert: first-person close-up, locked-off, a real screen recording with notifications off",
    "stress-test-action": "Stress test: medium shot from a low angle, handheld, the real test on {p}, outcome not yet shown",
    "rejection-lineup": "Rejection line-up: medium shot at eye level, slow pan along the unbranded ones that failed, ending on {p}",
    "toss-aside-cutaway": "Toss-aside cutaway: medium shot from above, whip pan as the failed one is set aside",
    "count-off-teaching-ms": "Count-off to camera: medium shot at eye level, slow push-in as one hand counts off the point",
    "prop-explainer-cu": "Prop explainer: close-up at eye level, slow push-in as a hand holds {prop} steady toward the lens",
    "insert-object-detail": "Insert: close-up from slightly above, slow push-in on {object}",
    "green-screen-explainer": "Green-screen explainer to camera: medium close-up at eye level, locked-off, the real image composited behind",
    "pov-walk-in": "POV walk-in: first-person tracking shot into the space, toward the spot where it happens",
    "ritual-step-wide": "Ritual step: medium-wide at a three-quarter angle, slow dolly as the presenter does the step live",
    "mirror-selfie": "Mirror selfie: medium shot at eye level in the mirror, handheld phone",
    "low-angle-hero-payoff": "Low-angle hero payoff: medium close-up from below, slow push-in as the presenter holds {result} toward the lens",
    "comment-typing-insert": "Comment-typing insert: first-person close-up of the phone, locked-off, the keyword typed into a comment (screen-recorded)",
    "end-card-hero": "End card: close-up at eye level, slow push-in on {p} with clear space above it for the card added in the edit",
    "loop-return-frame": "Loop return to frame 0: {frame0}; same scale and angle as the opening shot, a slow dolly out that settles on the opening composition",
    "whip-pan-transition": "Whip-pan transition: medium shot, a fast whip pan that lands on {subject}",
    "speed-ramp-reveal": "Speed-ramp reveal: close-up, handheld push-in, speed-ramped, fast then slowing sharply as {result} comes into view",
    "lens-cover-transition": "Lens-cover transition: handheld close-up, a palm comes toward the lens until the frame goes dark",
    "vo-over-hands-broll": "Hands B-roll under the voice: close-up from above, handheld, relaxed hands rest on and gently touch {p}",
}

# sound design per type (shots.json "sfx"); the voice track is separate
SFX = {
    "hook-hands-mid-action": "the product's real working sound from frame 0",
    "result-first-reveal": "soft room tone, then the product's real sound",
    "problem-state-open": "real room sound of the mess",
    "split-before-after": "a soft swipe as the split opens",
    "pov-hands-first-use": "the real handling and working sound, close to the mic",
    "unboxing-mid-open": "real tape and flap sounds",
    "comparison-side-by-side": "room tone",
    "macro-texture-ecu": "close-miked texture sound",
    "label-detail-ecu": "room tone",
    "over-shoulder-demo": "the real working sound of the task",
    "overhead-hands-demo": "the real working sound of each step",
    "product-operating-cu": "the product's real working sound, close-miked",
    "step-insert-cu": "the real press, twist or click",
    "timelapse-process": "a soft ticking bed",
    "slowmo-hero-moment": "a short riser into the slow motion, real sound under it",
    "pour-dispense-cu": "the pour, close to the mic",
    "hand-enters-pickup": "a soft pick-up sound",
    "stress-test-action": "the real test sound",
    "toss-aside-cutaway": "a whoosh on the cut",
    "whip-pan-transition": "a whoosh on the cut",
    "match-cut-transform": "a whoosh on the cut",
    "speed-ramp-reveal": "a riser into the reveal",
    "lens-cover-transition": "a soft thump as the frame goes dark",
    "screen-insert": "soft screen taps",
    "comment-typing-insert": "soft keyboard taps",
    "loop-return-frame": "a soft click on the cut back to frame 0",
    "end-card-hero": "a soft click on the end card",
    "text-card-over-motion": "a soft pop as the card lands",
    "establishing-ws": "real ambience of the place",
    "pov-walk-in": "real footsteps and ambience",
    "lifestyle-context-ws": "real ambience of the room",
    "ritual-step-wide": "real ambience of the routine",
}
SFX_FACE = "clean voice, quiet room tone"
SFX_DEFAULT = "live sound under the voice"

# light preset per type (SHOOT_PLAN_RULES.light_presets); face shots follow the vibe
LIGHT_BY_TYPE = {
    "macro-texture-ecu": "side-raking", "slowmo-hero-moment": "side-raking",
    "product-operating-cu": "side-raking", "label-detail-ecu": "side-raking",
    "product-hero-orbit": "side-raking", "pour-dispense-cu": "side-raking",
    "flat-lay-reveal": "soft-overhead", "overhead-hands-demo": "soft-overhead",
    "unboxing-mid-open": "soft-overhead", "step-insert-cu": "soft-overhead",
    "timelapse-process": "soft-overhead", "timestamp-proof-insert": "soft-overhead",
    "talking-head-product-in-hand": "window-plus-bounce", "low-angle-hero-payoff": "window-plus-bounce",
    "result-first-reveal": "window-plus-bounce", "hero-static-push-in": "window-plus-bounce",
    "end-card-hero": "window-plus-bounce", "feature-callout-hero": "window-plus-bounce",
    "turn-in-hand-light": "window-plus-bounce", "text-card-over-motion": "window-plus-bounce",
}
FACE_LIGHT_BY_VIBE = {"hype-energy": "ring-light-front", "playful-comedic": "ring-light-front",
                      "cozy-calm": "warm-practical", "clean-aesthetic": "window-plus-bounce"}
DEFAULT_VIBE = {"demo": "raw-ugc", "review": "raw-ugc", "transformation": "before-after-reveal",
                "talking-head": "expert-trust", "pov-vlog": "story-vlog"}

BEAT_PURPOSE = {
    "VISUAL TRIGGER": ("hook",),
    "VERBAL HOOK + LOCK": ("hook", "context", "emotion"),
    "IMPERFECTION BEAT": ("emotion", "b-roll", "context"),
    "REJECTION HISTORY": ("context", "proof", "emotion"),
    "EDUCATION BEAT": ("context", "b-roll", "proof", "demo"),
    "TEACHING BEAT": ("context", "demo", "b-roll"),
    "STORY BEAT": ("context", "emotion", "b-roll", "reaction"),
    "RITUAL BEAT": ("demo", "context", "b-roll"),
    "DEMO BEAT": ("demo", "proof", "reaction"),
    "EVIDENCE BEAT": ("proof", "reaction"),
    "PAYOFF": ("payoff", "proof", "reaction", "emotion"),
    "COMMENT BAIT": ("cta",),
    "CTA": ("cta", "transition"),
}
BEAT_FORCED_PURPOSE = {"VISUAL TRIGGER": "hook", "VERBAL HOOK + LOCK": "hook",
                       "COMMENT BAIT": "cta", "CTA": "cta"}
BEAT_ENERGY = {"VISUAL TRIGGER": 5, "VERBAL HOOK + LOCK": 4, "IMPERFECTION BEAT": 2,
               "REJECTION HISTORY": 3, "EDUCATION BEAT": 3, "TEACHING BEAT": 3,
               "STORY BEAT": 3, "RITUAL BEAT": 2, "DEMO BEAT": 4, "EVIDENCE BEAT": 4,
               "PAYOFF": 4, "COMMENT BAIT": 3, "CTA": 3}
VIBE_ENERGY = {"hype-energy": 1, "playful-comedic": 1, "cozy-calm": -1, "asmr-satisfying": -1}
GENERIC_RECIPE = {"shots": ["insert-object-detail", "talking-head-mcu", "reaction-cutaway-3q"],
                  "alt": ["hero-static-push-in", "vo-over-hands-broll", "text-card-over-motion",
                          "lifestyle-context-ws"]}
NEVER_CUT = ("VISUAL TRIGGER", "VERBAL HOOK + LOCK", "CTA")

# proof classes (research §4.5 / S-BA-MATCH): only real footage can prove
PROOF_ALWAYS = ("split-before-after", "matched-before", "matched-after", "match-cut-transform",
                "timestamp-proof-insert", "stress-test-action")
RESULT_TYPES = PROOF_ALWAYS + ("result-first-reveal", "speed-ramp-reveal", "low-angle-hero-payoff",
                               "timelapse-process", "comparison-side-by-side")
USE_TYPES = ("hook-hands-mid-action", "pov-hands-first-use", "over-shoulder-demo",
             "overhead-hands-demo", "product-operating-cu", "step-insert-cu", "pour-dispense-cu",
             "slowmo-hero-moment", "stress-test-action", "speed-ramp-reveal", "timelapse-process")
REACTION_TYPES = ("reaction-cutaway-3q", "face-reaction-product", "profile-look-cutaway")
DEMO_ANGLES = ("pov-hands-first-use", "over-shoulder-demo", "overhead-hands-demo",
               "product-operating-cu")
_TEST_RE = re.compile(
    r"(?i)\btest(?:s|ed|ing)?\b|\bproof\b|\bresults?\b|before[- ]and[- ]after|\bbefore\b[^.]{0,40}\bafter\b|"
    r"\bheld\b|\blasted\b|\bstill works\b|\bafter \d+|\bday \d+|\b\d+(?:\.\d+)?\s?(?:days?|weeks?|months?|hours?|"
    r"hrs?|minutes?|mins?|seconds?|%|x)\b|\bmeasur|\bverdict\b")
_BEFORE_AFTER_RE = re.compile(r"(?i)before[- ]and[- ]after|\bbefore\b[^.]{0,40}\bafter\b|side[- ]by[- ]side")


# ------------------------------------------------------ text -> type/move
_MOVE_TEXT = (
    (r"speed[- ]?ramp", "speed-ramp"), (r"whip[- ]?pan", "whip-pan"),
    (r"dolly out|pull[- ]?(?:out|back)", "pull-out"), (r"\borbit|tracking arc", "orbit"),
    (r"push[- ]?in|leans? in|punch[- ]?in", "push-in"), (r"\btracking\b", "tracking"),
    (r"\bdolly\b", "dolly"), (r"\bpan(?:s|ning)?\b", "pan"), (r"\btilt", "tilt"),
    (r"hand-?held|follows the (?:hands|action)", "handheld"),
    (r"\bstatic\b|locked[- ]off", "static"),
)
_MOVE_TEXT_RE = [(re.compile(p, re.I), m) for p, m in _MOVE_TEXT]


def move_in_text(text):
    """The camera move a framing/camera sentence names (None if none).
    'no static intro' is an instruction, not a move."""
    t = re.sub(r"(?i)\bno static \w+", "", text or "")
    for rx, m in _MOVE_TEXT_RE:
        if rx.search(t):
            return m
    return None


# explicit (maker/--script-json) framing -> nearest library type
_TEXT_TYPES = [(re.compile(p, re.I), t) for p, t in (
    (r"split[- ]?screen|before\s*/\s*after|before-after", "split-before-after"),
    (r"medium[- ]wide[^.]*to camera|to camera[^.]*medium[- ]wide", "mws-cta-to-camera"),
    (r"to camera[^.]*(?:in hand|holds?|holding)|(?:in hand|holds?|holding)[^.]*to camera",
     "talking-head-product-in-hand"),
    (r"walk[- ]and[- ]talk|selfie walk", "selfie-walk-talk"),
    (r"\bto camera\b|talking head|to the lens|direct address", "talking-head-mcu"),
    (r"problem state|at its worst", "problem-state-open"),
    (r"\bday\s+\d+\s+of\b|day[- ]counter", "pov-walk-in"),
    (r"alarm clock|phone screen|text overlay|text card", "text-card-over-motion"),
    (r"unbox", "unboxing-mid-open"),
    (r"slow[- ]?mo|slow motion", "slowmo-hero-moment"),
    (r"time[- ]?lapse", "timelapse-process"),
    (r"over[- ]?(?:the[- ])?shoulder", "over-shoulder-demo"),
    (r"overhead|top[- ]down", "overhead-hands-demo"),
    (r"\bpov\b|first[- ]person", "pov-hands-first-use"),
    (r"macro|texture", "macro-texture-ecu"),
    (r"\bpour|\bpump|dispens", "pour-dispense-cu"),
    (r"reaction|reacts|\bnods?\b", "reaction-cutaway-3q"),
    (r"end[- ]card", "end-card-hero"),
    (r"line[- ]?up|lined up", "rejection-lineup"),
    (r"\bhands?\b|mid-action|in motion|tracking shot", "hook-hands-mid-action"),
    (r"establishing|\bwide\b", "lifestyle-context-ws"),
    (r"\binsert\b|close[- ]up", "insert-object-detail"),
)]
_VT_TEXT = [(re.compile(p, re.I), v) for p, v in (
    (r"split[- ]?screen|before\s*/\s*after|before-after", "before-after-split"),
    (r"problem state|at its worst", "problem-state"),
    (r"\bday\s+\d+\s+of\b|day[- ]counter|\bstreak\b", "day-counter"),
    (r"alarm clock|phone screen|text overlay|text card|creator mid-gesture", "text-first"),
    (r"unbox", "unboxing"),
    (r"side[- ]by[- ]side|\bversus\b|\bvs\.?\s", "comparison"),
    (r"\bpov\b|first[- ]person", "pov-hands"),
    (r"reaction|reacts", "face-reaction"),
    (r"macro|texture|asmr", "satisfying-macro"),
    (r"\bresult\b|after-state|finished", "result-reveal"),
    (r"\bhands?\b|in hand|mid-action|in motion|tracking shot", "product-in-action"),
)]


def text_type(text, beat=""):
    for rx, t in _TEXT_TYPES:
        if rx.search(text or ""):
            return t
    return None


def visual_type_of(text):
    for rx, v in _VT_TEXT:
        if rx.search(text or ""):
            return v
    return None


# ------------------------------------------------------------- helpers
def _beat(sh):
    return (sh.get("beat") or "").replace(" (cont.)", "")


def _tidy(t):
    t = re.sub(r"\s+", " ", t or "").strip()
    t = re.sub(r"\s+([.,!?;:])", r"\1", t)
    return t.strip(" ,;")


def _dur(s, e):
    """Duration exactly as gate 2 reads it from the rendered heading."""
    return float(f"{e:.1f}") - float(f"{s:.1f}")


def recipe(fmt, concept, beat):
    """FORMAT_RECIPES resolution: default -> formats[format] -> concepts[concept]."""
    R = data()["FORMAT_RECIPES"]
    e = R["default"].get(beat)
    for layer in (R["formats"].get(fmt) or {}, R["concepts"].get(concept) or {}):
        if layer.get(beat):
            e = layer[beat]
    return e or GENERIC_RECIPE


def is_talking_head(tid):
    return tid in data()["TH_IDS"]


def effective(tid, lane, proof):
    """presenter=ai: a high-risk, non-proof type follows ai_fallback to med/low."""
    if lane != "ai" or proof:
        return tid
    seen = [tid]
    while lib(tid)["ai_risk"] == "high":
        nxt = lib(tid)["ai_fallback"]
        if not nxt or nxt in seen:
            break
        tid = nxt
        seen.append(tid)
    return tid


def subshot_target(script):
    """Sub-shot length: direction.pacing.avg_shot_s (midpoint, bounded to
    1.2-3.1 s) when the script carries a direction, else the legacy 2.5 s."""
    pacing = ((script.get("direction") or {}).get("pacing") or {}) \
        if isinstance(script.get("direction"), dict) else {}
    rng = pacing.get("avg_shot_s")
    try:
        if isinstance(rng, (list, tuple)) and len(rng) >= 2:
            v = (float(rng[0]) + float(rng[1])) / 2.0
        elif isinstance(rng, (int, float)):
            v = float(rng)
        else:
            return None
    except (TypeError, ValueError):
        return None
    return min(SUB_MAX_S, max(SUB_MIN_S, v))


def _n_cuts(beat, dur, target, recipe_len, legacy_split):
    """How many sub-shots a beat window gets."""
    if beat in NEVER_CUT:
        return 1
    if beat == "PAYOFF":
        # result -> face: the face comes back at the payoff as a reaction
        return 2 if dur >= 3.0 and recipe_len >= 2 else 1
    if beat == "IMPERFECTION BEAT" and dur >= 3.0 and dur <= 5.0:
        return 2          # the flaw shown on the product, then the face
    if target is None:                        # legacy cut plan (no direction)
        if dur > STATIC_MAX and legacy_split:
            return min(26, max(2, int(round(dur / LEGACY_SUB_S))))
        return 1
    k = int(round(dur / target))
    if dur > STATIC_MAX:
        k = max(k, 2)
    k = max(1, k)
    while k < 26 and dur / k > SUB_MAX_S:
        k += 1
    while k > 2 and dur / k < SUB_MIN_S:
        k -= 1
    if k == 2 and dur / k < SUB_MIN_S and dur <= STATIC_MAX:
        k = 1
    return min(26, k)


# ------------------------------------------------------------ context
def _identity_outfit(identity):
    m = re.search(r"(?i)\bwearing (?:a |an )?(.+)$", identity or "")
    return m.group(1).strip(" .") if m else ""


def _problem_clause(text):
    m = re.search(r"(?i)problem state full-frame\s*[\u2014-]\s*([^.]*?)(?:, on-screen|$|\.)", text or "")
    if not m:
        return ""
    return _tidy(m.group(1))


def build_ctx(script, shots=None, ctx=None):
    """Planning context: lane, concept, subject phrases, vibe, energy curve."""
    c = dict(ctx or {})
    if "concept" not in c or "product_short" not in c:
        ms = sys.modules.get("make_shotlist")
        if ms is None or not hasattr(ms, "_concept"):
            import importlib
            ms = importlib.import_module("make_shotlist")
        c.setdefault("concept", ms._concept(script.get("prompt") or ""))
        c.setdefault("product_short", ms.product_phrase(script.get("prompt") or ""))
    presenter = script.get("presenter") or "human"
    c["lane"] = "ai" if presenter == "ai" else "human"
    c["format"] = script.get("format") or ""
    c["shop"] = bool(_TIKTOK_SHOP.search(script.get("prompt") or ""))
    try:
        c["duration"] = float(script.get("duration_s") or 30)
    except (TypeError, ValueError):
        c["duration"] = 30.0
    direction = script.get("direction") if isinstance(script.get("direction"), dict) else None
    c["direction"] = direction
    vibe = (direction or {}).get("vibe")
    if not vibe:
        vibe = "cozy-calm" if c["concept"] == "routine" else DEFAULT_VIBE.get(c["format"], "raw-ugc")
    c["vibe"] = vibe
    c["product"] = c["concept"] in ("product", "showcase")
    vt_text = ""
    for it in script.get("hook_stack") or []:
        if isinstance(it, dict) and it.get("type") == "VISUAL TRIGGER":
            vt_text = it.get("direction") or it.get("shot_direction") or ""
    prob = _problem_clause(vt_text)
    ps = c.get("product_short") or ""
    if c["concept"] == "showcase":
        subj = "the first find"
    elif c["product"]:
        subj = f"the {ps}" if ps else "the product"
    else:
        subj = prob or {"challenge": "the habit's everyday object",
                        "routine": "the first step of the routine",
                        "advice": "the example the line is about"}.get(c["concept"],
                                                                       "the subject of the line")
    c["subject"] = subj
    c["problem"] = prob or (f"the problem {subj} fixes" if c["product"] else f"{subj}, at its worst")
    c["result"] = (f"the finished result of using {subj}" if c["product"]
                   else "the result the line describes")
    variants = script.get("hook_variants")
    prim = None
    if isinstance(variants, list):
        prim = next((v for v in variants if isinstance(v, dict) and v.get("is_primary")),
                    variants[0] if variants and isinstance(variants[0], dict) else None)
    c["primary_variant"] = prim
    curve = (direction or {}).get("energy_curve")
    c["energy_curve"] = curve if isinstance(curve, list) else None
    moves = ((direction or {}).get("camera") or {}).get("movement") if direction else None
    c["pref_moves"] = tuple(m for m in (moves or []) if isinstance(m, str))
    c["target"] = subshot_target(script)
    cad = data()["SHOT_RULES"]["cadence"].get(vibe) or {}
    c["max_static_s"] = float(cad.get("max_static_s") or STATIC_MAX)
    return c


def _fill(template, c, extra=None):
    vals = {"p": c["subject"], "problem": c["problem"], "result": c["result"],
            "subject": c["subject"] if c["product"] else "the result",
            "object": c["subject"], "prop": "the prop for the point", "frame0": "the opening frame"}
    if extra:
        vals.update(extra)
    return template.format(**vals)


# ------------------------------------------------------------ proof rules
def _group_text(g):
    return " ".join(x for x in (g.get("on_screen"), g.get("dialogue"), g.get("rehook")) if x)


def is_proof(tid, beat, g, c, first=False):
    """A shot that proves a result: only real footage can serve (§4.5)."""
    if tid in PROOF_ALWAYS:
        return True
    if first:
        return tid in ("result-first-reveal", "split-before-after")
    if beat == "EVIDENCE BEAT":
        return not (tid in REACTION_TYPES or is_talking_head(tid))
    if beat == "PAYOFF":
        return tid in RESULT_TYPES or tid in USE_TYPES
    if beat == "DEMO BEAT":
        return (tid in USE_TYPES or tid in RESULT_TYPES) and bool(g.get("test"))
    if tid == "screen-insert" and beat in ("EVIDENCE BEAT", "PAYOFF"):
        return True
    return False


def _proof_why(tid, beat, first):
    if tid in ("matched-before", "matched-after", "split-before-after", "match-cut-transform"):
        return "before/after is evidence; film both states from one taped phone spot"
    if tid == "timestamp-proof-insert":
        return "a real reading is evidence; film the real timer, scale or clock"
    if tid == "stress-test-action":
        return "a durability test is evidence; film the real test"
    if first:
        return "the opening shows the real result; film the real result"
    if beat == "DEMO BEAT":
        return "this is the test itself; film the real product doing it"
    if beat == "PAYOFF":
        return "the payoff result is evidence; film the real result"
    if beat == "EVIDENCE BEAT":
        return "evidence beat; only real footage can prove it"
    return "the line claims a measured result; film the real result"


# ------------------------------------------------------------- blocks
def shot_type_line(sh):
    if not sh.get("shot_type"):
        return None
    return (f"- Shot type: {sh['shot_type']} \u00b7 {sh['scale']} \u00b7 {sh['move']} \u00b7 "
            f"{sh['purpose']} \u00b7 energy {sh['energy']} \u00b7 AI risk {sh['ai_risk']}")


def real_footage_line(sh):
    why = sh.get("real_footage_why")
    return f"- REAL FOOTAGE REQUIRED: {why} \u2014 do not generate" if why else None


def block_lines(sh):
    """The '- ' lines under '### Shot ...' (gate 2 parses exactly these for
    D47/D48). The new lines sit right after '- Camera:'."""
    L = [f"- Camera: {sh['direction']}"]
    for extra in (shot_type_line(sh), real_footage_line(sh)):
        if extra:
            L.append(extra)
    if sh.get("on_screen"):
        L.append(f"- On-screen text: {sh['on_screen']}")
    if sh.get("dialogue"):
        L.append(f"- Dialogue/VO: \"{sh['dialogue']}\"")
    if sh.get("delivery"):
        L.append(f"- Delivery: {sh['delivery']}")
    if sh.get("rehook"):
        L.append(f"- Re-hook into next: \"{sh['rehook']}\"")
    if sh.get("match_cut"):
        L.append(f"- Match-cut: {sh['match_cut']}")
    return L


def gate_talking_head(sh):
    """Gate 2's D47 predicate on this shot's block."""
    return "to camera" in "\n".join(block_lines(sh)).lower().split("on-screen")[0]


def gate_has_move(sh):
    """Gate 2's D48 predicate (move keyword anywhere in the block)."""
    body = "\n".join(block_lines(sh)).lower()
    return any(k in body for k in MOVE_KW)


def is_sub(sh):
    return bool(re.search(r"[a-z]$", str(sh.get("n", ""))))


# ============================================================== planning
def _merge(shots):
    """build_shots output -> one base dict per beat group (sub-shots merged)."""
    groups = []
    for sh in shots:
        g = sh.get("group", sh.get("n"))
        if groups and groups[-1]["g"] == g:
            groups[-1]["parts"].append(sh)
        else:
            groups.append({"g": g, "parts": [sh]})
    out = []
    for grp in groups:
        first, last = grp["parts"][0], grp["parts"][-1]
        base = dict(first)
        base["s"], base["e"] = float(first["s"]), float(last["e"])
        base["beat"] = _beat(first)
        base["direction"] = _tidy(re.sub(r"\s*\(VO continues\)", "", first.get("direction") or ""))
        base["rehook"] = last.get("rehook") or ""
        base["match_cut"] = last.get("match_cut") or ""
        base["g"] = grp["g"]
        base["legacy_parts"] = len(grp["parts"])
        out.append(base)
    return out


def _cine(scale, angle, move):
    s = SCALE_WORDS.get(scale, "medium shot")
    return f"{s[:1].upper() + s[1:]}, {ANGLE_WORDS.get(angle, 'eye level')}, {MOVE_WORDS.get(move, 'static camera')}"


def _frame0_desc(text):
    t = re.sub(r"(?i)^frame[\s-]*0\b[^:]*:\s*", "", text or "")
    t = re.split(r"(?<=[.!?])\s+", t.strip())[0] if t.strip() else ""
    t = re.sub(r"(?i),?\s*(?:on-screen|text overlay|day-counter on)[^,.;]*", "", t)
    t = re.sub(r"(?i)\bto camera\b", "toward the lens", t)
    t = _tidy(t).rstrip(".")
    return t[:110].rstrip(" ,;") or "the opening frame"


def _safe_sentences(text):
    """Maker frame-0 sentences that survive a reframe (no people/hands)."""
    keep = []
    for x in re.split(r"(?<=[.!?])\s+", text or ""):
        if re.search(r"(?i)^no logos|no static intro", x):
            keep.append(x.strip())
    return " ".join(keep)


def _frame0_candidates(vt, rec, c):
    d = data()
    ids = []
    for t in list(rec.get("shots") or []) + list(rec.get("alt") or []):
        if vt in lib(t)["visual_types"] and t not in ids:
            ids.append(t)
    for s in d["SHOT_LIBRARY"]:
        if vt in s["visual_types"] and s["id"] not in ids:
            ids.append(s["id"])
    return [t for t in ids if t not in d["BANNED_F0"] and not is_talking_head(t)]


def _frame0_ok(tid, c):
    L = lib(tid)
    if not L["visual_types"] or is_talking_head(tid) or tid in data()["BANNED_F0"]:
        return False
    if c["product"]:
        return "product" in L["needs"] or bool(
            set(L["visual_types"]) & {"result-reveal", "before-after-split"})
    return True


def _pick_frame0(g, c):
    """-> (orig type, effective type, visual_type, why)."""
    rec = recipe(c["format"], c["concept"], "VISUAL TRIGGER")
    vocab_vt = ("product-in-action", "result-reveal", "before-after-split", "problem-state",
                "pov-hands", "face-reaction", "text-first", "unboxing", "comparison",
                "day-counter", "satisfying-macro")
    try:
        from vsp import creative_vocab as V
        vocab_vt = tuple(V.VISUAL_TYPES)
    except Exception:  # noqa: BLE001 — vocab is optional for planning
        pass
    prim = c.get("primary_variant") or {}
    vt, src = prim.get("visual_type"), "hook variant A"
    if vt not in vocab_vt:
        vt, src = visual_type_of(g.get("direction") if g.get("explicit") else ""), "the frame-0 direction"
    if vt not in vocab_vt:
        first = (rec.get("shots") or ["hook-hands-mid-action"])[0]
        vts = lib(first)["visual_types"] or ["product-in-action"]
        vt, src = vts[0], f"the {c['format'] or 'default'} recipe"
    cands = [t for t in _frame0_candidates(vt, rec, c) if _frame0_ok(t, c)]
    if not cands:
        cands = [t for t in list(rec.get("shots") or []) + list(rec.get("alt") or [])
                 + ["text-card-over-motion"] if _frame0_ok(t, c)]
    best = None
    for t in cands:
        pr = is_proof(t, "VISUAL TRIGGER", g, c, first=True)
        eff = effective(t, c["lane"], pr)
        if not _frame0_ok(eff, c):
            continue
        keeps = vt in lib(eff)["visual_types"]
        if c["lane"] == "ai" and lib(eff)["ai_risk"] == "high" and not pr:
            continue
        if c["lane"] == "ai" and pr and "face" in lib(eff)["needs"]:
            continue
        if keeps:
            best = (t, eff, pr)
            break
        if best is None:
            best = (t, eff, pr)
    if best is None:
        best = ("text-card-over-motion", "text-card-over-motion", False)
    t, eff, pr = best
    why = f"frame 0 = {vt} (from {src}): the product or result in the opening frame, never a talking head"
    if eff != t:
        why += f"; AI lane: {t} is high-risk, fallback {eff}"
    return t, eff, vt, pr, why


def _classify_explicit(text, beat, rec, first):
    t = text_type(text, beat)
    if t == "hook-hands-mid-action" and not first:
        t = next((x for x in list(rec.get("shots") or []) + list(rec.get("alt") or [])
                  if "hands" in lib(x)["needs"]), "pov-hands-first-use")
    if t == "pov-walk-in" and not first:
        t = "day-counter-selfie"
    return t


def _slots(groups, c):
    """Cut plan: per group a list of (s, e) sub-shot windows."""
    loop_needed = c["duration"] <= 15.0 + 1e-9 and len(groups) > 1
    plans = []
    for gi, g in enumerate(groups):
        dur = g["e"] - g["s"]
        rec = recipe(c["format"], c["concept"], g["beat"])
        k = 1 if gi == 0 else _n_cuts(g["beat"], _dur(g["s"], g["e"]), c["target"],
                                       len(rec.get("shots") or []), g["legacy_parts"] > 1)
        loop = False
        if loop_needed and gi == len(groups) - 1:
            loop = True
            if k == 1 and dur >= 2.0 - 1e-9:
                k = 2
        if k == 1:
            wins = [(g["s"], g["e"])]
        elif loop:
            L = min(1.2, max(0.6, round(dur * 0.4, 1)))
            head = dur - L
            step = head / (k - 1)
            wins = [(g["s"] + i * step, g["s"] + (i + 1) * step) for i in range(k - 1)]
            wins.append((g["s"] + head, g["e"]))
        else:
            step = dur / k
            wins = [(g["s"] + i * step, g["s"] + (i + 1) * step) for i in range(k)]
            wins[-1] = (wins[-1][0], g["e"])
        plans.append({"wins": wins, "loop": loop, "rec": rec})
    return plans


def _mk(g, i, k, win):
    """A shot dict for sub-shot i of k in group g (legacy field layout)."""
    s, e = win
    first, last = i == 0, i == k - 1
    n = g["g"] if k == 1 else f"{g['g']}{chr(97 + i)}"
    sh = {
        "n": n, "group": g["g"], "t": f"{s:.1f}\u2013{e:.1f}s",
        "s": round(s, 3), "e": round(e, 3),
        "beat": g["beat"] + ("" if first else " (cont.)"),
        "direction": g["direction"], "camera": g.get("camera") or "",
        "explicit": bool(first and g.get("explicit")),
        "on_screen": g.get("on_screen", "") if first else "",
        "staging": list(g.get("staging") or []) if first else [],
        "dialogue": g.get("dialogue", "") if first else "",
        "delivery": g.get("delivery", "") if first else "",
        "rehook": g.get("rehook", "") if last else "",
        "match_cut": g.get("match_cut", "") if last else "",
    }
    if "item" in g:
        sh["item"] = g["item"]
    return sh


def _framing(tid, sh, c, frame0_desc):
    txt = _fill(FRAMING[tid], c, {"frame0": frame0_desc})
    return txt


def _apply(sh, tid, move, c, frame0_desc, sub_i, explicit_text=None, first_shot=False):
    """Set the shot's framing/camera for type tid."""
    L = lib(tid)
    if explicit_text is not None:
        sh["direction"] = explicit_text
    else:
        txt = _framing(tid, sh, c, frame0_desc)
        if first_shot:
            txt = "Frame 0: " + txt[:1].lower() + txt[1:] if not txt.lower().startswith("frame") else txt
        if sub_i > 0:
            txt += " (VO continues)"
        sh["direction"] = txt
    sh["shot_type"] = tid
    sh["scale"], sh["angle"] = L["scale"], L["angle"]
    sh["move"] = move
    sh["camera"] = "Camera: " + _cine(L["scale"], L["angle"], move) + "."


def _th_if(sh, tid, move, c, frame0_desc, sub_i, explicit_text, first_shot):
    """Gate-2 D47 predicate for this shot if it took type tid."""
    saved = {k: sh.get(k) for k in ("direction", "shot_type", "scale", "angle", "move", "camera")}
    _apply(sh, tid, move, c, frame0_desc, sub_i, explicit_text, first_shot)
    sh.setdefault("purpose", "hook")
    sh.setdefault("energy", 3)
    sh.setdefault("ai_risk", "low")
    th = gate_talking_head(sh)
    for k, v in saved.items():
        if v is None:
            sh.pop(k, None)
        else:
            sh[k] = v
    return th


def _purpose(tid, beat, loop=False, proof=False, first=False):
    """SHOT_PURPOSES id: 'hook' at frame 0; 'proof' exactly for proof
    (real-footage) shots; otherwise the beat's first purpose the type serves."""
    if first:
        return "hook"
    if loop:
        return "cta" if beat in ("CTA", "COMMENT BAIT") else "transition"
    if proof:
        return "proof"
    if beat in BEAT_FORCED_PURPOSE:
        return BEAT_FORCED_PURPOSE[beat]
    P = [p for p in lib(tid)["purposes"] if p != "proof"]
    if tid in REACTION_TYPES and "reaction" in P:
        return "reaction"
    for p in BEAT_PURPOSE.get(beat, ()):
        if p in P:
            return p
    bp = [p for p in BEAT_PURPOSE.get(beat, ()) if p != "proof"]
    return bp[0] if bp else (P[0] if P else "context")


def _energy(g, c):
    curve = c.get("energy_curve")
    idx = g.get("item")
    if curve and isinstance(idx, int) and 0 <= idx < len(curve):
        try:
            v = int(round(float((curve[idx] or {}).get("energy"))))
            return min(5, max(1, v))
        except (TypeError, ValueError, AttributeError):
            pass
    v = BEAT_ENERGY.get(g["beat"], 3) + VIBE_ENERGY.get(c["vibe"], 0)
    return min(5, max(1, v))


def _light(tid, c):
    L = lib(tid)
    if tid in LIGHT_BY_TYPE:
        return LIGHT_BY_TYPE[tid]
    if "face" in L["needs"]:
        return FACE_LIGHT_BY_VIBE.get(c["vibe"], "window-key-45")
    if c["vibe"] == "cozy-calm":
        return "warm-practical"
    return "window-key-45"


def _choose(cands, st, ctx_slot, c):
    """Greedy pick: hard constraints first (same id twice, 3 same scales,
    3 talking heads, AI high risk), then reuse, recipe order, fit."""
    best = None
    seen = []
    for idx, t in enumerate(cands):
        if t in seen or t not in data()["BY_ID"]:
            continue
        seen.append(t)
        pr = is_proof(t, ctx_slot["beat"], ctx_slot["g"], c)
        eff = effective(t, c["lane"], pr)
        pr = pr or is_proof(eff, ctx_slot["beat"], ctx_slot["g"], c)
        L = lib(eff)
        move = L["move"]
        hard = 0
        prev = st["types"][-1:] if st["types"] else []
        if prev and prev[0] == eff:
            hard += 1
        sc = st["scales"][-2:]
        if len(sc) == 2 and sc[0] == sc[1] == L["scale"]:
            hard += 1
        nxt = ctx_slot.get("next_scale")
        if nxt and st["scales"][-1:] == [L["scale"]] and nxt == L["scale"]:
            hard += 1
        if nxt and nxt == L["scale"] and ctx_slot.get("next2_scale") == L["scale"]:
            hard += 1
        th = _th_if(ctx_slot["sh"], eff, move, c, st["frame0_desc"], ctx_slot["i"], None, False)
        if th and st["th"][-2:] == [True, True]:
            hard += 1
        if c["lane"] == "ai" and L["ai_risk"] == "high" and not pr:
            hard += 1
        if ctx_slot["unsplit_long"] and move == "static":
            hard += 1
        if eff == "matched-after" and not any(x in ("matched-before", "split-before-after")
                                              for x in st["types"]):
            hard += 1          # an AFTER needs its matched BEFORE (S-BA-MATCH)
        if c["lane"] == "ai" and pr and "face" in L["needs"]:
            hard += 1          # a proof shot must be filmed: the AI persona cannot be
        soft = 6.0 * st["used"].get(eff, 0) + idx
        lo, hi = L["duration_s"]
        dur = ctx_slot["dur"]
        if dur < lo - 0.3 or dur > hi + 0.3:
            soft += 1.5
        if c["lane"] == "ai" and L["ai_risk"] == "med" and st["risk"][-2:] == ["med", "med"]:
            soft += 1.0
        if move == "static" and dur > c["max_static_s"] + 1e-9:
            soft += 1.0
        if move in c["pref_moves"]:
            soft -= 0.5
        if ctx_slot.get("prefer_face") and "face" in L["needs"]:
            soft -= 8.0
        if c["vibe"] in L["vibes"]:
            soft -= 0.5
        key = (hard, soft, idx)
        if best is None or key < best[0]:
            best = (key, t, eff, pr, th)
    return best


def plan(script, shots, ctx=None):
    """Enrich (and re-cut) build_shots output with the §1.4 shot plan.
    Returns the new shot list; deterministic, no I/O besides the cached
    table load."""
    if not shots:
        return shots
    c = build_ctx(script, shots, ctx)
    groups = _merge(shots)
    for g in groups:
        g["test"] = bool(_TEST_RE.search(_group_text(g)))
    plans = _slots(groups, c)
    # before/after promised in the copy but no BEFORE in the plan (research §1)
    all_text = " ".join(_group_text(g) for g in groups)
    forced = {}
    if _BEFORE_AFTER_RE.search(all_text):
        has_ba = any(set(p["rec"].get("shots") or []) & {"matched-before", "split-before-after",
                                                          "match-cut-transform"}
                     and len(p["wins"]) >= 2 for p in plans[1:])
        if not has_ba:
            demo = next((j for j, g in enumerate(groups) if j and g["beat"] == "DEMO BEAT"
                         and not g.get("explicit") and not plans[j]["loop"]), None)
            if demo is not None:
                g = groups[demo]
                k = len(plans[demo]["wins"])
                dur = g["e"] - g["s"]
                if k < 3 and dur / (k + 1) >= 1.5:
                    step = dur / (k + 1)
                    plans[demo]["wins"] = [(g["s"] + i * step, g["s"] + (i + 1) * step)
                                           for i in range(k + 1)]
                    plans[demo]["wins"][-1] = (plans[demo]["wins"][-1][0], g["e"])
                if len(plans[demo]["wins"]) >= 2:
                    forced[(demo, 0)] = "matched-before"
            if not forced:
                for beat in ("EVIDENCE BEAT", "EDUCATION BEAT"):
                    gi = next((j for j, g in enumerate(groups) if j and g["beat"] == beat
                               and len(plans[j]["wins"]) >= 2 and not g.get("explicit")), None)
                    if gi is not None:
                        forced[(gi, 0)] = "matched-before"
                        break
            if forced:
                side = bool(re.search(r"(?i)side[- ]by[- ]side|split", all_text))
                for gi, g in enumerate(groups):
                    if g["beat"] == "PAYOFF" and not g.get("explicit"):
                        forced[(gi, 0)] = "split-before-after" if side else "matched-after"
                        break
    c["group_test"] = {g["g"]: g["test"] for g in groups}
    out = []
    st = {"types": [], "scales": [], "th": [], "risk": [], "used": {}, "frame0_desc": "the opening frame"}
    occ = {}
    frame0 = None
    for gi, g in enumerate(groups):
        p = plans[gi]
        k = len(p["wins"])
        rec = p["rec"]
        o = occ.get(g["beat"], 0)
        occ[g["beat"]] = o + 1
        energy = _energy(g, c)
        for i, win in enumerate(p["wins"]):
            sh = _mk(g, i, k, win)
            dur = _dur(sh["s"], sh["e"])
            first_shot = gi == 0 and i == 0
            loop_slot = p["loop"] and i == k - 1
            explicit_text = None
            why = ""
            if first_shot:
                t, eff, vt, pr, why = _pick_frame0(g, c)
                txt = g["direction"] if g.get("explicit") else None
                if txt is not None:
                    tt = text_type(txt, g["beat"])
                    reframe = (tt is not None and not _frame0_ok(tt, c)) or \
                        bool(re.search(r"(?i)creator mid-gesture|\bto camera\b|talking head", txt)) or \
                        (visual_type_of(txt) not in (None, vt) and vt not in lib(eff)["visual_types"]) or \
                        (visual_type_of(txt) not in (None, vt) and c.get("primary_variant"))
                    if eff != t:            # AI lane swap: the maker's hands leave the frame
                        m = re.search(r"(?i)hands on (.+?), object in motion", txt)
                        if m and eff == "product-operating-cu":
                            txt = txt[:m.start()] + (f"{m.group(1)} already running, working end in "
                                                     f"close-up, hands out of frame, object in motion") + txt[m.end():]
                        else:
                            reframe = True
                    if reframe:
                        base = _fill(FRAMING[eff], c)
                        prim = c.get("primary_variant") or {}
                        if prim.get("visual") and prim.get("visual_type") == vt and eff == t:
                            base = _tidy(re.sub(r"(?i)^frame[\s-]*0\b[^:]*:\s*", "",
                                                str(prim["visual"])).replace('"', ""))
                            base = re.sub(r"(?i)\bto camera\b", "toward the lens", base)
                        txt = _tidy("Frame 0: " + base[:1].lower() + base[1:] + ". " + _safe_sentences(g["direction"]))
                    explicit_text = txt
                move = lib(eff)["move"]
                if explicit_text is not None and eff == t:
                    move = move_in_text(explicit_text) or move_in_text(g.get("camera") or "") or move
                th = False
            elif loop_slot:
                f0 = out[0]
                t = eff = "loop-return-frame"
                pr = bool(f0.get("real_footage"))
                move = "pull-out"
                th = False
                why = "loop ending (duration <= 15 s): the last shot returns to frame 0's framing"
            elif (gi, i) in forced:
                t = eff = forced[(gi, i)]
                pr = True
                move = lib(eff)["move"]
                th = False
                why = "the copy promises a before/after: film a real matched BEFORE and AFTER"
            elif i == 0 and g.get("explicit"):
                t = _classify_explicit(g["direction"], g["beat"], rec, False) or \
                    (rec.get("shots") or GENERIC_RECIPE["shots"])[0]
                pr = is_proof(t, g["beat"], g, c)
                eff = effective(t, c["lane"], pr)
                if eff != t:
                    explicit_text = None
                    why = f"AI lane: {t} is high-risk, fallback {eff}"
                else:
                    explicit_text = g["direction"]
                    why = "the maker's own staging, typed"
                move = lib(eff)["move"]
                if explicit_text is not None:
                    move = move_in_text(explicit_text) or move_in_text(g.get("camera") or "") or move
                th = _th_if(sh, eff, move, c, st["frame0_desc"], i, explicit_text, False)
            else:
                shots_r = list(rec.get("shots") or [])
                base_c = shots_r[i:] + shots_r[:i] if shots_r else []
                cands = base_c + list(rec.get("alt") or []) + GENERIC_RECIPE["shots"] + GENERIC_RECIPE["alt"]
                if k == 1 and g["beat"] == "VERBAL HOOK + LOCK":
                    cands = [x for x in cands if "face" in lib(x)["needs"]] + cands
                # the face comes back at the payoff, as a reaction (research §2.2)
                prefer_face = g["beat"] == "PAYOFF" and i >= 1 and bool(out) and \
                    "face" not in out[-1]["needs"]
                nxt_scale = nxt2 = None
                if out and ((p["loop"] and i == k - 2) or
                            (gi == len(groups) - 2 and plans[-1]["loop"] and
                             len(plans[-1]["wins"]) == 1 and i == k - 1)):
                    nxt_scale = out[0]["scale"]
                slot = {"beat": g["beat"], "g": g, "sh": sh, "i": i, "dur": dur,
                        "unsplit_long": k == 1 and dur > STATIC_MAX, "next_scale": nxt_scale,
                        "next2_scale": nxt2, "prefer_face": prefer_face}
                _, t, eff, pr, th = _choose(cands, st, slot, c)
                move = lib(eff)["move"]
                idx = cands.index(t)
                if eff != t:
                    why = f"AI lane: {t} is high-risk, fallback {eff}"
                elif idx < len(base_c):
                    why = f"{c['format'] or 'default'}/{c['concept']} recipe for {g['beat']}"
                else:
                    why = (f"recipe alternate for {g['beat']}: keeps the scale rotation, "
                           f"fits {dur:.1f} s and avoids repeating a shot type")
            if k == 1 and dur > STATIC_MAX and move == "static":
                move = "push-in"              # D48: a long unsplit shot really moves
            _apply(sh, eff, move, c, st["frame0_desc"], i, explicit_text, first_shot and explicit_text is None)
            if eff == "loop-return-frame" and out:
                # the loop inherits frame 0's scale, angle and subject (and its footage)
                f0 = out[0]
                sh["scale"], sh["angle"] = f0["scale"], f0["angle"]
                sh["camera"] = "Camera: " + _cine(sh["scale"], sh["angle"], move) + "."
                if f0.get("real_footage"):
                    pr = True
                    loop_slot = True
            if k == 1 and dur > STATIC_MAX and not any(kw in sh["direction"].lower() for kw in MOVE_KW):
                sh["direction"] = _tidy(sh["direction"].rstrip(".") + ". " +
                                        MOVE_WORDS[move][:1].upper() + MOVE_WORDS[move][1:] + " through the shot.")
            sh["purpose"] = _purpose(eff, g["beat"], loop_slot, bool(pr), first_shot)
            sh["energy"] = energy
            L = lib(eff)
            sh["needs"] = list(L["needs"])
            sh["ai_risk"] = L["ai_risk"]
            sh["ai_fallback"] = L["ai_fallback"] if L["ai_fallback"] != eff else None
            sh["ai_swapped_from"] = t if t != eff else None
            sh["real_footage"] = bool(pr)
            sh["real_footage_why"] = None
            if pr and c["lane"] == "ai":
                sh["real_footage_why"] = ("the loop reuses the real frame-0 footage" if loop_slot
                                          else _proof_why(eff, g["beat"], first_shot))
            sh["why"] = why or "recipe"
            sh["light_preset"] = _light(eff, c)
            if first_shot:
                frame0 = sh
                st["frame0_desc"] = _frame0_desc(sh["direction"])
            out.append(sh)
            st["types"].append(eff)
            st["scales"].append(sh["scale"])
            st["th"].append(gate_talking_head(sh))
            st["risk"].append(sh["ai_risk"])
            st["used"][eff] = st["used"].get(eff, 0) + 1
    _repair(out, c)
    _human_by_3s(out, c)
    _setups(out, c)
    _coverage(out, c)
    return out


def _alts_for(sh, c):
    beat = _beat(sh)
    rec = recipe(c["format"], c["concept"], beat)
    return list(rec.get("shots") or []) + list(rec.get("alt") or []) + \
        GENERIC_RECIPE["shots"] + GENERIC_RECIPE["alt"]


def _retype(out, j, c, avoid_scale=None, need_face=False):
    """Swap shot j (non-explicit, not frame 0 / loop / forced proof) to the
    first alternate that keeps every neighbourhood rule."""
    sh = out[j]
    if j == 0 or sh.get("explicit") or sh["shot_type"] == "loop-return-frame" \
            or sh["why"].startswith("the copy promises"):
        return False
    beat = _beat(sh)
    dur = _dur(sh["s"], sh["e"])
    sub_i = 0 if not is_sub(sh) else ord(str(sh["n"])[-1]) - 97
    g = {"on_screen": sh.get("on_screen"), "dialogue": sh.get("dialogue"), "rehook": sh.get("rehook"),
         "test": bool((c.get("group_test") or {}).get(sh.get("group")))}
    f0 = _frame0_desc(out[0]["direction"])
    for t in _alts_for(sh, c):
        pr = is_proof(t, beat, g, c)
        eff = effective(t, c["lane"], pr)
        L = lib(eff)
        if c["lane"] == "ai" and L["ai_risk"] == "high" and not pr:
            continue
        if c["lane"] == "ai" and pr and "face" in L["needs"]:
            continue
        if eff == "matched-after" and not any(x["shot_type"] in ("matched-before", "split-before-after")
                                              for x in out[:j]):
            continue
        if eff == sh["shot_type"] or (avoid_scale and L["scale"] == avoid_scale):
            continue
        if need_face and "face" not in L["needs"]:
            continue
        if j > 0 and out[j - 1]["shot_type"] == eff or j + 1 < len(out) and out[j + 1]["shot_type"] == eff:
            continue
        move = L["move"]
        if not is_sub(sh) and dur > STATIC_MAX and move == "static":
            continue
        trial = dict(sh)
        _apply(trial, eff, move, c, f0, sub_i, None, False)
        scales = [x["scale"] for x in out]
        scales[j] = trial["scale"]
        if _scale_run(scales, j):
            continue
        ths = [gate_talking_head(x) for x in out]
        ths[j] = gate_talking_head(trial)
        if _th_run(ths, j):
            continue
        _apply(sh, eff, move, c, f0, sub_i, None, False)
        sh["purpose"] = _purpose(eff, beat, False, bool(pr))
        sh["needs"] = list(L["needs"])
        sh["ai_risk"] = L["ai_risk"]
        sh["ai_fallback"] = L["ai_fallback"] if L["ai_fallback"] != eff else None
        sh["ai_swapped_from"] = t if t != eff else None
        sh["real_footage"] = bool(pr)
        sh["real_footage_why"] = _proof_why(eff, beat, False) if pr and c["lane"] == "ai" else None
        sh["why"] = f"alternate for {beat} (rule repair)"
        sh["light_preset"] = _light(eff, c)
        return True
    return False


def _scale_run(scales, j):
    for a in range(max(0, j - 2), min(len(scales) - 2, j + 1)):
        if scales[a] == scales[a + 1] == scales[a + 2]:
            return True
    return False


def _th_run(ths, j):
    for a in range(max(0, j - 2), min(len(ths) - 2, j + 1)):
        if ths[a] and ths[a + 1] and ths[a + 2]:
            return True
    return False


def _repair(out, c):
    """Final guard: no 3 same-scale / 3 talking-head runs (D47 extended)."""
    for _ in range(3):
        changed = False
        for a in range(len(out) - 2):
            trio = out[a:a + 3]
            same_scale = trio[0]["scale"] == trio[1]["scale"] == trio[2]["scale"]
            ths = [gate_talking_head(x) for x in trio]
            if not (same_scale or all(ths)):
                continue
            for j in (a + 1, a + 2, a):
                if _retype(out, j, c, avoid_scale=trio[0]["scale"] if same_scale else None):
                    changed = True
                    break
        if not changed:
            break


def _human_by_3s(out, c):
    """A face or hands on screen >= 1.0 s within 0-3.0 s; a face for human
    presenters and the TikTok Shop lane."""
    def cover(pred):
        tot = 0.0
        for sh in out:
            if sh["s"] >= 3.0:
                break
            if pred(sh):
                tot += max(0.0, min(3.0, sh["e"]) - sh["s"])
        return tot
    need_face = c["lane"] == "human" or c["shop"]
    ok_h = cover(lambda x: bool(set(x["needs"]) & {"face", "hands"})) >= 1.0 - 1e-9
    ok_f = (not need_face) or cover(lambda x: "face" in x["needs"]) >= 1.0 - 1e-9
    if ok_h and ok_f:
        return
    for j, sh in enumerate(out[1:], 1):
        if sh["s"] >= 3.0 - 1e-9:
            break
        if _retype(out, j, c, need_face=True):
            return


BA_IDS = ("matched-before", "matched-after", "split-before-after", "match-cut-transform")


def _setup_key(sh, c):
    tid = sh["shot_type"]
    if tid in BA_IDS:
        # before/after pairs share one setup: the same taped phone spot,
        # lens and light (S-BA-MATCH); the AFTER is shot later from it
        return (0, "film", 2, "before-after") if c["lane"] == "ai" else (2, "before-after", "stand")
    step = data()["STEP"].get(tid, 8)
    if tid == "jump-cut-punch-in":
        step = 4
    if tid == "split-before-after":
        step = 2
    support = "overhead mount" if sh["angle"] == "overhead" else (
        "handheld" if sh["move"] in ("handheld", "tracking", "whip-pan", "speed-ramp") else "stand")
    if c["lane"] == "ai":
        if sh.get("real_footage"):
            return (0, "film", step, sh["light_preset"])
        refs = "persona" if "face" in sh["needs"] else ("hands" if "hands" in sh["needs"] else "product")
        order = {"product": 1, "hands": 2, "persona": 3}[refs]
        return (order, "render", refs, sh["light_preset"])
    return (step, sh["light_preset"], support)


def _setups(out, c):
    keys = []
    for j, sh in enumerate(out):
        if sh["shot_type"] == "loop-return-frame" and c["lane"] == "human":
            continue
        k = _setup_key(sh, c)
        if k not in keys:
            keys.append(k)
    order = sorted(range(len(keys)), key=lambda i: (keys[i][0], i))
    num = {keys[i]: n + 1 for n, i in enumerate(order)}
    for sh in out:
        if sh["shot_type"] == "loop-return-frame" and c["lane"] == "human":
            sh["setup"] = num[_setup_key(out[0], c)]
        else:
            sh["setup"] = num[_setup_key(sh, c)]


def _coverage(out, c):
    """Per-shot B-roll coverage ids + sound design."""
    sfx_dir = [x for x in (((c.get("direction") or {}).get("music") or {}).get("sfx") or [])
               if isinstance(x, str)] if c.get("direction") else []
    for j, sh in enumerate(out):
        tid = sh["shot_type"]
        cov = []
        if tid in DEMO_ANGLES or (sh["purpose"] == "demo" and "hands" in sh["needs"]):
            neigh = {out[x]["shot_type"] for x in (j - 1, j + 1) if 0 <= x < len(out)}
            alt = next((a for a in DEMO_ANGLES if a != tid and a not in neigh), None)
            if alt:
                cov.append(alt)
        elif "face" in sh["needs"] and sh.get("dialogue") and len(sh["dialogue"].split()) / 3.0 > 2.0:
            cov.append("hero-static-push-in" if c["product"] else "insert-object-detail")
        sh["broll"] = cov
        sfx = SFX.get(tid) or (SFX_FACE if "face" in sh["needs"] else SFX_DEFAULT)
        if sh["purpose"] == "transition" and sfx_dir:
            sfx = sfx_dir[j % len(sfx_dir)]
        sh["sfx"] = sfx


# ======================================================== brief rendering
class _Safe(dict):
    def __missing__(self, key):
        return "the subject"


def _clean_prompt(t):
    """D160: no quote characters (quoted dialogue makes models draw text),
    no 'render exactly'."""
    t = re.sub(r"[\"\u201c\u201d]", "", t or "")
    t = re.sub(r"(?i)render exactly", "match", t)
    return re.sub(r"\s+", " ", t).strip()


def prompt_assets(script, identity, product_desc, setting, light, ctx=None):
    """Everything visual_prompt / the sections need, computed once per bundle."""
    c = build_ctx(script, None, ctx)
    persona = script.get("persona") if isinstance(script.get("persona"), dict) else {}
    outfit = _identity_outfit(identity)
    look = ((c.get("direction") or {}).get("look") or {}) if c.get("direction") else {}
    palette = [p for p in (look.get("palette_names") or []) if isinstance(p, str)][:5]
    c.update({
        "identity": identity, "product_desc": product_desc, "setting": setting, "light": light,
        "name": (persona.get("name") or "").strip() or "The presenter",
        "outfit": outfit,
        "hands_ref": (f"the presenter's hands, the sleeve of the {outfit} just in frame"
                      if outfit else "the presenter's hands"),
        "palette": palette if len(palette) >= 3 else [],
        "category": c.get("product_short") or "product",
    })
    return c


def says(name, line):
    """D160 dialogue form: '<Name> says: <line>' — never quoted."""
    return f"{name} says: {_clean_prompt(line)}"


def visual_prompt(sh, A):
    """One self-contained generation prompt (research §4.3 structure):
    [scale, angle, move]: subject, one action, setting, light, vertical phone
    footage, single continuous shot, no on-screen text. The identity lock only
    in shots that show the face; hands-only shots get a short hands reference;
    product-only inserts carry no persona text."""
    tid = sh.get("shot_type")
    if not tid or tid not in data()["BY_ID"]:
        return None
    L = lib(tid)
    hi = L["human_instructions"]
    if A["lane"] == "ai" and sh.get("real_footage"):
        return _clean_prompt(
            "Not generated: REAL FOOTAGE slot. Hold a plain neutral placeholder frame for this "
            "shot's length; the filmed clip replaces it in the edit. Film it on a phone: " + hi)
    tm = L["ai_prompt"]
    note = ""
    if tid == "jump-cut-punch-in":
        tm = lib("talking-head-mcu")["ai_prompt"]
        note = " Keep headroom: the 1.3x punch-in crop is added in the edit."
    if tm.startswith(("Not generated", "Edit-only")):
        return _clean_prompt(f"Not generated (film it on a phone): {hi}")
    tm = re.sub(r"\s*\{name\} says: \{line\}\s*$", "", tm)
    subj = A["subject"]
    vals = _Safe({
        "product": subj, "persona": A["identity"], "setting": A["setting"], "light": A["light"],
        "result": "the finished result" if "{product}" in tm else A["result"],
        "material": subj, "sound": "its real working sound, close-miked",
        "alt": "alternative of the same kind", "category": A["category"], "problem": A["problem"],
        "object": subj, "process": f"the slow process {subj} works on",
        "fast_action": "the key moment of use", "liquid": "the contents", "vessel": "a cup or palm",
        "action": "doing its job", "medium": "real use", "feature": "key feature",
        "prop": "the prop for the point", "subject": subj, "spot": "the spot where it happens",
        "step": "the routine step", "time_of_day": "morning", "name": A["name"], "line": "",
    })
    body = tm.format_map(vals)
    # "in a kitchen counter" -> "at a kitchen counter"
    body = re.sub(r"\b(?:in|on) ((?:a|an|the) [^,.;]*?\b(?:counter|desk|vanity|workbench|table)\b)",
                  r"at \1", body)
    if not sh.get("dialogue") and re.search(r"speaks to (?:the lens|camera)", body):
        # the voiceover runs over this clip: no lip movement to sync
        body = re.sub(r"speaks to (?:the lens|camera)", "looks into the lens, listening, no speech", body)
        body = re.sub(r"\s*talking to the lens", ", no speech", body)
    if (sh.get("scale"), sh.get("angle"), sh.get("move")) != (L["scale"], L["angle"], L["move"]) \
            and ":" in body[:90] and not tm.startswith(("Image-to-video", "Use the frame-0")):
        body = _cine(sh["scale"], sh["angle"], sh["move"]) + ":" + body.split(":", 1)[1]
    parts = [body.rstrip(" .") + "." + note]
    needs = sh.get("needs") or L["needs"]
    if "face" not in needs and "hands" in needs:
        parts.append(f"Hands only, face out of frame: {A['hands_ref']}.")
    if "product" in needs or "props" in needs:
        parts.append(("Product: " if A["product"] else "Props: ") + A["product_desc"].rstrip(".") + ".")
    if "{setting}" not in tm:
        parts.append(f"Setting: {A['setting']}.")
    if "{light}" not in tm:
        parts.append(f"Light: {A['light']}.")
    if A.get("palette"):
        parts.append("Palette: " + ", ".join(A["palette"]) + ".")
    parts.append("Vertical 9:16 phone footage.")
    parts.append(data()["SHOT_RULES"]["ai"]["prompt_suffix"])
    if "sound design:" not in body:
        parts.append(f"Ambient sound: {sh.get('sfx') or SFX_DEFAULT}.")
    return _clean_prompt(" ".join(parts))


def overlay_line(text):
    return f"ON-SCREEN TEXT (edit overlay \u2014 add in the edit; never generate text in-frame): {text}"


def _clean_visual(text):
    t = re.sub(r"(?i)^frame[\s-]*0\b[^:]*:\s*", "", str(text or ""))
    keep = [x for x in re.split(r"(?<=[.!?;,])\s+", t)
            if x and not re.search(r"(?i)on-?screen|overlay|caption|\btext\b|label|logo", x)]
    t = _clean_prompt(" ".join(keep)).rstrip(" ,;.")
    t = re.sub(r"(?i)\bto camera\b", "toward the lens", t)
    return t[:160].rstrip(" ,;")


def alt_openings_md(script, A, shots=None):
    """## ALTERNATE OPENINGS — one ≤3 s clip per non-primary hook variant."""
    variants = script.get("hook_variants")
    if not isinstance(variants, list):
        return None
    alts = [v for v in variants if isinstance(v, dict) and not v.get("is_primary")]
    if not alts:
        return None
    opening = "Shots 1\u20132"
    if shots:
        hs = [sh for sh in shots if sh["s"] < 3.0 - 1e-6] or shots[:1]
        opening = (f"Shot {hs[0]['n']}" if len(hs) == 1 else f"Shots {hs[0]['n']}\u2013{hs[-1]['n']}")
    L = ["## ALTERNATE OPENINGS \u2014 variant cuts",
         "Render each alternate opening below as its own clip of 3 s or less, placed after the "
         "master's last shot \u2014 never inside the master's timeline. Same identity lock and "
         f"product block as the master. Each one replaces {opening} (0.0\u20133.0s) in its "
         "variant cut; the overlay is added in the edit."
         + (" Each carries the same frame-0 AI disclosure label as the master." if A["lane"] == "ai" else "")]
    for v in alts:
        vid = re.sub(r"[^A-Za-z0-9]", "", str(v.get("id") or "")) or "X"
        arch = str(v.get("archetype") or "unknown")
        vt = str(v.get("visual_type") or "unknown")
        c2 = dict(A)
        c2["primary_variant"] = v
        g0 = {"direction": "", "explicit": False, "on_screen": v.get("overlay") or "",
              "dialogue": v.get("verbal") or "", "rehook": "", "test": False}
        t, eff, vt2, pr, _why = _pick_frame0(g0, c2)
        Lb = lib(eff)
        sh = {"shot_type": eff, "scale": Lb["scale"], "angle": Lb["angle"], "move": Lb["move"],
              "needs": list(Lb["needs"]), "sfx": SFX.get(eff) or SFX_DEFAULT, "real_footage": bool(pr)}
        L.append("")
        L.append(f"#### Alt opening {vid} (0.0\u20133.0s) \u2014 {arch} / {vt}")
        L.append(f"OPENING SHOT: {eff} \u00b7 {Lb['scale']} \u00b7 {Lb['move']} \u00b7 AI risk {Lb['ai_risk']}")
        vp = visual_prompt(sh, c2)
        vis = _clean_visual(v.get("visual")) if eff == t and not (pr and A["lane"] == "ai") else ""
        if vis:
            vp = vp.replace(" Vertical 9:16", f" Opening: {vis}. Vertical 9:16", 1)
        L.append(f"VISUAL PROMPT: {vp}")
        if pr and A["lane"] == "ai":
            L.append(f"REAL FOOTAGE REQUIRED: {_proof_why(eff, 'VISUAL TRIGGER', True)} \u2014 do not generate")
        if v.get("overlay"):
            L.append(overlay_line(_clean_prompt(str(v["overlay"]))))
        if v.get("verbal"):
            L.append("AUDIO (voiceover \u2014 audio only, never on-screen text): "
                     + says(A["name"], str(v["verbal"])))
    return "\n".join(L)


def _setup_label(sh, A):
    if A["lane"] == "ai":
        if sh.get("real_footage"):
            return "FILM (real footage, hybrid lane)"
        refs = "persona reference sheet" if "face" in sh["needs"] else (
            "hands reference" if "hands" in sh["needs"] else "product reference photos")
        return f"RENDER (image or text to video, {refs}, same seed)"
    if sh["shot_type"] in BA_IDS:
        return "before/after spot (tape the phone position; the AFTER reuses it)"
    step = data()["STEP"].get(sh["shot_type"], 8)
    if sh["shot_type"] == "jump-cut-punch-in":
        step = 4
    names = {s["step"]: s["name"] for s in data()["SHOOT_PLAN_RULES"]["setup_order"]}
    support = "overhead mount" if sh["angle"] == "overhead" else (
        "handheld, stabilisation on" if sh["move"] in ("handheld", "tracking", "whip-pan", "speed-ramp")
        else "phone on a stand")
    return f"{names.get(step, 'pick-ups')} ({support})"


def shoot_plan_md(script, shots, A):
    """## SHOOT PLAN — setups in shooting order, props, B-roll, light, AE/AF."""
    ai = A["lane"] == "ai"
    SPR = data()["SHOOT_PLAN_RULES"]
    L = ["## SHOOT PLAN \u2014 setups, props, B-roll"]
    if ai:
        L.append("AI lane: shots are grouped into render groups (one reference set, setting, light "
                 "and seed). REAL FOOTAGE shots are filmed on a phone (hybrid lane) because an AI "
                 "render cannot prove a result; everything else is generated from its prompt.")
    else:
        L.append("Shoot by setup, not story order: a setup is one phone position, light, location, "
                 "wardrobe and product state. Inside a setup go wide to tight so the phone moves "
                 "one way. B-roll first, while the product is still pristine.")
    L.append("Lock exposure and focus on the subject at every setup (touch and hold for AE/AF "
             "lock). Stabilisation on; 1x main lens, macro mode or 2x for extreme close-ups, no "
             "digital zoom past 2x; filters and beauty mode off.")
    L.append("")
    L.append("Setups in order:")
    by = {}
    for j, sh in enumerate(shots):
        by.setdefault(sh.get("setup", 0), []).append((j, sh))
    for n in sorted(by):
        mem = sorted(by[n], key=lambda x: (SCALE_ORDER.index(x[1]["scale"])
                                            if x[1]["scale"] in SCALE_ORDER else 9, x[0]))
        first = mem[0][1]
        L.append(f"- Setup {n}: {_setup_label(first, A)} \u00b7 light {first.get('light_preset')}")
        for _, sh in mem:
            Lb = lib(sh["shot_type"])
            if ai and not sh.get("real_footage"):
                how = ("reuse the frame-0 still as the first and last frame" if sh["shot_type"] ==
                       "loop-return-frame" else "image-to-video from the real product photo"
                       if Lb["ai_prompt"].startswith("Image-to-video") else "generate from its prompt")
            else:
                how = Lb["human_instructions"]
            L.append(f"  - Shot {sh['n']} ({sh['t']}) {sh['shot_type']} ({sh['scale']}, "
                     f"{MOVE_WORDS.get(sh['move'], sh['move'])}): {how}")
    types = [sh["shot_type"] for sh in shots]
    needs = []
    for sh in shots:
        for x in sh.get("needs") or []:
            if x not in needs:
                needs.append(x)
    rf = [sh for sh in shots if sh.get("real_footage")]
    L.append("")
    L.append("Props checklist:")
    props = []
    messy = any(t in types for t in ("stress-test-action", "pour-dispense-cu", "product-operating-cu",
                                     "slowmo-hero-moment"))
    if "product" in needs or "props" in needs:
        props.append(("the product: " if A["product"] else "the props: ") + A["product_desc"].rstrip(".")
                     + ("; a second unit for the messy shots" if messy and A["product"] else ""))
    if ai:
        props.append("product reference photos (front, side, back, detail) and a 1-3 still persona "
                     "reference sheet, approved before any render")
    if "unboxing-mid-open" in types:
        props.append("a sealed box; film the pristine shots before opening anything")
    if any(t in types for t in ("comparison-side-by-side", "rejection-lineup")):
        props.append("the alternatives, brand marks taped over or turned away")
    if messy:
        props.append("the consumable it works on and a wipe cloth")
    if any(t in BA_IDS or t == "timestamp-proof-insert" for t in types):
        props.append("a clock or date card, and tape to mark the phone spot on the floor or table")
    if "screen" in needs:
        props.append("a second phone or screen recorder, a clean home screen, notifications off")
    if "location" in needs:
        props.append(f"location: {A['setting']}, same time of day for matched shots")
    if "face" in needs and not ai:
        props.append(f"wardrobe: {A['outfit'] or 'one outfit'}, one outfit for the whole shoot")
    kit = "kit: phone stand or tripod, white card, lens cloth, tape"
    if "product-hero-orbit" in types:
        kit += ", lazy Susan"
    if any(sh["angle"] == "overhead" for sh in shots):
        kit += ", overhead phone mount"
    props.append(kit)
    L.extend(f"- {p}" for p in props)
    L.append("")
    L.append("B-roll list:")
    br = []
    for sh in shots:
        for b in sh.get("broll") or []:
            what = ("a second angle of the same step" if b in DEMO_ANGLES
                    else "an insert showing what the line names")
            br.append(f"Shot {sh['n']}: {what} ({b})")
    L.extend(f"- {b}" for b in br)
    L.append("- record live sound on every B-roll clip; it plays under the voice")
    L.append("- one spare hero push-in and one spare reaction per setup for the variant cuts")
    L.append("")
    L.append("Lighting presets:")
    used = []
    for sh in shots:
        p = sh.get("light_preset")
        if p and p not in used:
            used.append(p)
    for p in used:
        lp = SPR["light_presets"].get(p) or {}
        L.append(f"- {p}: {lp.get('how', '')} ({lp.get('use', '')})")
    if rf and ai:
        L.append("")
        L.append("Real footage to film (never generated): " + ", ".join(
            f"Shot {sh['n']} {sh['shot_type']}" for sh in rf) + ".")
    if ai:
        plan_ = SPR["ai_render_plan"]
        L.append("Render order: " + "; ".join(f"{i + 1}. {x}" for i, x in enumerate(plan_["order"]))
                 + f". Retry each shot up to {plan_['retry_limit_per_shot']} times, then "
                 + plan_["on_repeated_failure"] + ".")
    if any(t in BA_IDS for t in types):
        L.append("Before/after protocol: " + "; ".join(SPR["before_after_protocol"]) + ".")
    return "\n".join(L)
