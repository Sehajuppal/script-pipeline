#!/usr/bin/env python3
"""make_shotlist.py — turn a viral_script_maker JSON into a shot list + Antigravity brief.

Standing rule (2026-09-27, user order): every script made for use ships as a
bundle — script JSON + shot list + Antigravity prompt. This generator makes
that automatic.

Usage:
    python3 make_shotlist.py script.json [--out bundle.md]

Reads the maker JSON, maps each beat to a shot (camera/framing/action/
on-screen text/VO/delivery), enforces the B4a keyword-CTA template
(follow -> keyword -> payload), and emits the Antigravity brief per the
standing template (DELIVERABLE block verbatim).

Pipeline v2 (2026-09-28) — the shot list is the timeline of record:
  * shots follow the script's windows exactly; only a missing window is
    sized from its words (no cascade drift from the old re-flow)
  * D48: every shot > 3.5 s is cut into sub-shots (4a/4b/...) or carries a
    camera move; D47: never 3 talking-head shots in a row (cutaways rotate in)
  * D64: identity / setting / style keyed by the maker's niches, product looks
    matched on word boundaries with a prompt-derived fallback, meta/rule notes
    stripped from every generation prompt, production notes lifted out of
    render-exactly on-screen text, voice spec from the persona/identity
  * D138: presenter=ai briefs always carry the frame-0 "AI persona" label
"""
import json, re, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vsp import config  # noqa: E402  (VSP_VIRAL_DB, read-only DB access)
from vsp import shotplan  # noqa: E402  (v2.1 shot recommender, CREATIVE-PLAN §1.4)

BEAT_SHOT_DIRECTION = {
    "VISUAL TRIGGER": "Frame-0 composition, static or micro push-in. High contrast, readable at a glance.",
    "VERBAL HOOK + LOCK": "Medium close-up, direct to camera, eye-level. Brisk and confident.",
    "IMPERFECTION BEAT": "Same framing, slightly looser — faint handheld feel. Candid, unpolished read.",
    "EDUCATION BEAT": "Product macro / B-roll over VO, or presenter with prop in hand. Unhurried, warm.",
    "DEMO BEAT": "Over-shoulder or mirror POV, mid-action framing. Presenter does the thing live, no fakes.",
    "EVIDENCE BEAT": "Timestamped split-screen / side-by-side. Same subject, same light. Slow — let the result land.",
    "PAYOFF": "Presenter to camera, product in hand. Slow push-in through the beat — the camera leans in as the proof lands. Slow down. No scripted laugh.",
    # D47 (v2): the closing third (payoff -> comment bait -> CTA) was one
    # scale; the bait now plays medium-wide, between the payoff's medium
    # close-up push-in and the CTA's close-up.
    "COMMENT BAIT": "Medium-wide: presenter CTA to camera, keyword text on screen.",
    "CTA": "Brisk close-up, clean end-card beat.",
    # v2 (D47/D48): beat types the maker emits that fell to the bare
    # "Presenter to camera." default (5 s static talking heads)
    "TEACHING BEAT": "Presenter to camera, mid-shot, one hand counting off the point. Unhurried, warm.",
    "STORY BEAT": "Presenter to camera, selfie framing, present tense — let the audience live the moment.",
    "RITUAL BEAT": "Wide on the routine step happening live, present tense, unhurried.",
    "REJECTION HISTORY": "Medium close-up to camera, the ones that failed lined up beside the presenter.",
}
DEFAULT_DIRECTION = "Presenter to camera."
# v2 (D64): concept prompts (challenge / routine / advice) have no product —
# "product in hand" / "product macro" were rendered for "why your hooks fail"
CONCEPT_SHOT_DIRECTION = {
    "EDUCATION BEAT": "Close-up B-roll of the subject over VO, or presenter with a prop in hand. Unhurried, warm.",
    "DEMO BEAT": "Over-shoulder POV, mid-action framing. The presenter does the thing live, no fakes.",
    "PAYOFF": "Presenter to camera, the result shown in frame. Slow push-in through the beat — the camera leans in as the proof lands. Slow down. No scripted laugh.",
}

DELIVERABLE = (
    "Render the FULL video as one long uncut master: everything you generated,\n"
    "no trims, no pre-cutting, no tightening. Deliver that long master as the\n"
    "deliverable. Marlowe cuts the 2-3 variants from it on the variant stage.\n"
    "If there is a voiceover, also send words.json (word-level timings).\n"
    "Captioning and variant cuts are Marlowe's stages \u2014 do not pre-apply them."
)

RENDER_SPEC = (
    "9:16 vertical, 1080x1920, 30fps, H.264 mp4. "
    "Files: <slug>-master.mp4 + <slug>-words.json (word-level timings as "
    '{"words": [{"word": str, "start": float_seconds, "end": float_seconds}], '
    '"duration_s": float}).'
)

DO_NOT = (
    "Do NOT burn in captions/subtitles (Marlowe's stage). No watermarks or logos. "
    "No stock-footage look \u2014 shoot it like real UGC. No robotic TTS \u2014 human voice only. "
    "No letterbox/pillarbox. No pre-cutting or tightening (see DELIVERABLE)."
)

NICHE_VIEWER = {
    "beauty": "women 18-34 into hair/makeup routines",
    "fitness": "adults 20-40 starting or restarting training",
    "pets": "pet owners 20-45",
    "kitchen": "home cooks 22-45",
    "tech": "gadget buyers 18-40",
    "fashion": "style-conscious 16-34",
    "wellness": "adults 22-45 fixing sleep and stress",
    "automotive": "drivers 20-45 who live in their car",
    "home": "renters and homeowners 22-40",
    "outdoors": "campers and hikers 20-45",
    "finance": "adults 20-40 getting their money together",
    "education": "learners and creators 16-35",
    "commentary": "creators and marketers 18-40",
}

# v2 (D64 niche-key alignment): the maker emits gadgets/tools/wellness/
# automotive/pets/home/outdoors/fitness/food/finance/education/commentary/
# default/beauty, while the brief maps were keyed tech/kitchen/fashion — every
# gadgets or food script fell to the generic identity/setting/style.
NICHE_ALIAS = {"gadgets": "tech", "food": "kitchen", "tools": "kitchen",
               "default": "generic", "": "generic"}

# D64 (2026-09-27): model-followable brief assets. The identity lock is the
# highest-leverage piece — without it the video model invents a new person per
# shot. One locked description per (presenter, niche); used VERBATIM in every
# shot prompt. Product/setting/style maps are concrete-visual, never brand
# claims (D37: no invented branding).
PRESENTER_IDENTITY = {
    ("human", "beauty"): "a woman in her late 20s with medium-length dark brown hair worn down, natural makeup, wearing a casual beige knit top",
    ("human", "fitness"): "a man in his early 30s with an athletic build and short dark hair, wearing a plain black t-shirt",
    ("human", "kitchen"): "a woman in her mid-30s with shoulder-length brown hair tied back, light makeup, wearing a plain sage-green t-shirt",
    ("human", "pets"): "a woman in her late 20s with a blonde ponytail and light makeup, wearing a plain white t-shirt",
    ("human", "tech"): "a man in his late 20s with short black hair and glasses, wearing a plain navy hoodie",
    ("human", "fashion"): "a woman in her mid-20s with long dark wavy hair, natural makeup, wearing a simple black top",
    ("human", "generic"): "a woman in her early 30s with shoulder-length brown hair, light makeup, wearing a plain white t-shirt",
    ("human", "automotive"): "a man in his early 30s with short brown hair and light stubble, wearing a plain olive crewneck",
    ("human", "outdoors"): "a woman in her early 30s with a low brown ponytail, no makeup look, wearing a plain rust-colored fleece",
    ("human", "wellness"): "a woman in her early 30s with shoulder-length light-brown hair worn down, minimal makeup, wearing a plain oatmeal sweater",
    ("ai", "beauty"): "a photorealistic AI woman in her mid-20s with long black hair, dewy natural makeup, wearing a soft pink cardigan",
    ("ai", "fitness"): "a photorealistic AI man in his early 30s, athletic build, short dark hair, wearing a plain gray athletic shirt",
    ("ai", "generic"): "a photorealistic AI woman in her late 20s with dark hair tied back, natural look, wearing a plain gray crewneck",
}
# v2 (D64): ordered word-boundary patterns — the old substring keys hijacked
# "clamp" -> lamp, "fancy" -> fan and gave car wax the hair-wax look. Each look
# fires only on the product it actually describes; everything else gets a
# prompt-derived description (product_description) instead of "the product".
PRODUCT_LOOK = [
    (r"\bhair[- ]?wax\b|\bwax stick\b|\bpomade\b",
     "a small twist-up solid hair-wax stick in a matte nude-beige tube about 10 cm long, cap on"),
    (r"\bsunrise\b[\w\s-]{0,24}\blamp\b",
     "a compact dome-shaped sunrise lamp in matte white about 15 cm wide, glowing warm"),
    (r"\bprojector\b",
     "a compact mini projector, matte dark-gray rounded box about 12 cm wide with a front lens"),
    (r"\bneck fan\b",
     "a small portable neck fan, matte white U-shaped band that sits around the neck"),
    (r"\bcar trash\b|\btrash can\b[\w\s-]{0,24}\bcar\b",
     "a small car trash can with a lid, matte black cylinder about 18 cm tall"),
    (r"\bmilk frother\b|\bfrother\b",
     "a handheld electric milk frother, slim matte-black wand about 20 cm long with a steel whisk head"),
]
PRODUCT_LOOK_GENERIC = "the product from the concept, plain and unbranded, true to its real-world shape and size"
NICHE_SETTING = {
    # niche -> (setting, light)
    "beauty": ("bathroom vanity with a large mirror", "soft natural window light from the left"),
    "fitness": ("a bright home gym corner", "bright daylight"),
    "kitchen": ("a clean modern kitchen counter", "bright daylight"),
    "pets": ("a cozy living room", "soft natural daylight"),
    "tech": ("a tidy modern desk setup", "soft daylight with a warm desk lamp glow"),
    "fashion": ("a bright bedroom with a full-length mirror", "soft natural window light"),
    "generic": ("a clean modern home interior", "soft natural daylight"),
    "wellness": ("a calm, tidy bedroom with a made bed", "soft warm bedside-lamp light"),
    "automotive": ("the interior of a clean modern car, parked", "soft natural daylight through the windshield"),
    "home": ("a bright, tidy apartment living space", "soft natural daylight"),
    "outdoors": ("an outdoor campsite clearing", "golden-hour daylight"),
    "finance": ("a tidy home-office desk", "soft daylight"),
    "education": ("a tidy study desk with a notebook and laptop", "soft daylight"),
    "commentary": ("a simple home-office corner with a plain wall behind", "soft key light from a window"),
}
# product words beat the niche (a desk lamp is shot on a desk, a sunrise lamp
# at the bedside, a tire inflator in the car) — first match wins
SETTING_BY_PRODUCT = [
    (r"\b(?:car|cars|truck|dashboard|headrest|trunk|tire|tires|vehicle)\b", "automotive"),
    (r"\bbird ?feeder\b|\bbird ?house\b", ("a backyard garden with the feeder on a post", "soft morning daylight")),
    (r"\b(?:dog|dogs|cat|cats|pet|pets|puppy|kitten)\b", "pets"),
    (r"\b(?:desk|laptop|keyboard|mouse|monitor|office|chair|earbuds?|headphones?|speaker|charger|cable|power bank)\b", "tech"),
    (r"\b(?:kitchen|knife|waffle|fryer|toaster|kettle|blender|cookware|frother|coffee|espresso|lunch|mealprep|recipe|snack|sugar)\b", "kitchen"),
    (r"\b(?:hair|skin|serum|makeup|lash|lashes|eyelash|eyelashes|lipstick|moisturizer|vanity)\b", "beauty"),
    (r"\b(?:camp|camping|tent|lantern|hike|hiking|outdoor|outdoors|backpack|flashlight|headlamp)\b", "outdoors"),
    (r"\b(?:gym|workout|yoga|bands?|dumbbells?|kettlebell|posture|treadmill)\b", "fitness"),
    (r"\b(?:bed|bedroom|sleep|pillow|pillowcase|noise|sunrise|alarm|morning|routine)\b", "wellness"),
    (r"\b(?:read|reading|book|books|pages)\b", ("a cozy reading nook by a window", "soft natural window light")),
    (r"\b(?:door|lock)\b", ("an apartment entryway with the door closed", "soft indoor light")),
    (r"\b(?:drill|toolbox|garage|workbench)\b", ("a tidy workbench in a bright garage", "bright daylight")),
]
NICHE_STYLE_NOTES = {
    "beauty": ["Maximum-contrast before/after is the genre's currency — make the transformation unmistakable.",
               "Motion toward the camera reads as confidence; stillness reads as ad."],
    "fitness": ["Sweat and effort are the proof — never shoot the workout looking fresh."],
    "kitchen": ["Steam, sizzle, and close-up texture carry the genre — shoot the food, not the cook."],
    "generic": ["Fast cold open, proof before pitch — the first frame hooks the eye and the first line hooks the ear (sound on; captions stay)."],
    "tech": ["Show the gadget doing its job in the first second — function is the hook, not the unboxing.",
             "Hands in frame make scale obvious; keep screens and LEDs readable, never blown out."],
    "wellness": ["Calm, uncluttered frames and soft light — trust beats energy in this niche."],
    "automotive": ["Shoot inside the real car in daylight — fit against the seats and dash is the proof."],
    "pets": ["The animal's reaction is the proof — keep the pet in frame at its own eye level."],
    "home": ["Each find in its real spot in the room — one clear before/after of the space."],
    "outdoors": ["Real outdoor light and texture — show it working in the field, not on a table."],
    "finance": ["Subject first, your face by 3 s, then fast — cut on every new point; on-screen labels carry the numbers alongside the voice."],
    "education": ["Subject first, your face by 3 s, then fast — cut on every new point; on-screen labels carry the numbers alongside the voice."],
    "commentary": ["Subject first, your face by 3 s, then fast — cut on every new point; on-screen labels carry the numbers alongside the voice."],
}
SHOT_CAMERA = {
    "VISUAL TRIGGER": "Camera: static frame with a micro push-in.",
    "VERBAL HOOK + LOCK": "Camera: medium close-up, eye-level, static.",
    "IMPERFECTION BEAT": "Camera: faint handheld feel, slightly loose framing.",
    "EDUCATION BEAT": "Camera: slow drift over the detail.",
    "DEMO BEAT": "Camera: over-shoulder, follows the action.",
    "EVIDENCE BEAT": "Camera: locked-off, identical framing.",
    "PAYOFF": "Camera: slow push-in through the beat.",
    "COMMENT BAIT": "Camera: medium-wide, slow push-in toward the presenter.",
    "CTA": "Camera: brisk close-up, static.",
    "REJECTION HISTORY": "Camera: medium close-up, static.",
    "TEACHING BEAT": "Camera: medium close-up, eye-level, static.",
    "STORY BEAT": "Camera: handheld selfie framing.",
    "RITUAL BEAT": "Camera: static wide, eye-level.",
}

# D48 (v2): long shots get a cut plan. (framing for the shot list, camera for
# the generation prompt); sub-shot a keeps the delivery + on-screen text, the
# last sub-shot keeps the spoken re-hook and any match-cut. The rotation
# alternates scales, so a split beat never contributes 3 talking heads (D47).
SUBSHOT_PLAN = {
    "EDUCATION BEAT": [
        ("Tight macro detail — product texture/label in frame", "Camera: slow drift over the detail."),
        ("Mid-action — hands + product doing the thing", "Camera: handheld, follows the hands."),
        ("Presenter cutaway — reaction/nod, keeps a human face in the edit", "Camera: medium shot, static."),
    ],
    "DEMO BEAT": [
        ("Over-shoulder POV — hands start the demo live, no fakes", "Camera: over-shoulder, follows the action."),
        ("Tight close-up — the product mid-action, the result forming", "Camera: slow push-in on the action."),
        ("Presenter cutaway — reaction as the result shows", "Camera: medium shot, static."),
    ],
    "EVIDENCE BEAT": [
        ("Split-screen — before left, after right, matched framing and light", "Camera: locked-off, identical framing on both sides."),
        ("Slow push-in on the after side", "Camera: slow push-in."),
        ("Detail close-up — the difference that proves it", "Camera: locked-off macro."),
    ],
    "TEACHING BEAT": [
        ("Presenter to camera, mid-shot — delivers the point", "Camera: medium close-up, eye-level, static."),
        ("Insert — the point shown up close: notes, a phone screen or the example", "Camera: slow push-in on the insert."),
        ("Reaction cutaway — presenter at a three-quarter angle", "Camera: medium shot, static."),
    ],
    "STORY BEAT": [
        ("Presenter to camera, selfie framing — tells the moment", "Camera: handheld selfie framing."),
        ("Insert — the moment itself: hands, object or place from the story", "Camera: handheld, follows the action."),
        ("Reaction cutaway — presenter's face at a three-quarter angle", "Camera: medium close-up, static."),
    ],
    "RITUAL BEAT": [
        ("Wide — the routine step happening live", "Camera: static wide, eye-level."),
        ("Close-up — hands doing the step", "Camera: handheld close-up, follows the hands."),
        ("Presenter cutaway — a quiet present-tense reaction", "Camera: medium shot, static."),
    ],
    "IMPERFECTION BEAT": [
        ("Presenter to camera, loose handheld framing — the confession, unpolished", "Camera: faint handheld feel, slightly loose framing."),
        ("Insert — close-up of the fumble or flaw the line admits", "Camera: handheld close-up."),
    ],
    "REJECTION HISTORY": [
        ("Presenter to camera, medium close-up — names the ones that failed", "Camera: medium close-up, eye-level, static."),
        ("Insert — slow pan across the rejected ones lined up on a table", "Camera: slow pan across the line-up."),
    ],
    "COMMENT BAIT": [
        ("Medium-wide: presenter CTA to camera, keyword text on screen", "Camera: slow push-in toward the presenter."),
        ("Phone close-up — the keyword typed into a comment", "Camera: static close-up on the phone screen."),
    ],
}
CONCEPT_SUBSHOT_PLAN = {
    "EDUCATION BEAT": [
        ("Close-up B-roll — the subject of the line in detail", "Camera: slow drift over the detail."),
        ("Mid-action — hands doing the thing", "Camera: handheld, follows the hands."),
        ("Presenter cutaway — reaction/nod, keeps a human face in the edit", "Camera: medium shot, static."),
    ],
    "DEMO BEAT": [
        ("Over-shoulder POV — the presenter starts it live, no fakes", "Camera: over-shoulder, follows the action."),
        ("Tight close-up — the moment it works", "Camera: slow push-in on the action."),
        ("Presenter cutaway — reaction as the result shows", "Camera: medium shot, static."),
    ],
}
GENERIC_SUBSHOTS = [
    ("Presenter medium shot — delivers the line", "Camera: medium shot, static."),
    ("Insert — close-up of the subject of the line", "Camera: slow push-in on the insert."),
    ("Reaction cutaway — presenter at a three-quarter angle", "Camera: medium shot, static."),
]
NEVER_SPLIT = {"VISUAL TRIGGER", "VERBAL HOOK + LOCK", "PAYOFF", "CTA"}
SPLIT_AT = {"IMPERFECTION BEAT": 5.0}     # it already moves (handheld)
MOVE_SENTENCE = {
    "VISUAL TRIGGER": "Micro push-in.",
    "VERBAL HOOK + LOCK": "Micro push-in through the line.",
    "CTA": "Slow push-in to the end card.",
}
# D47 (v2): deterministic cutaways that break a talking-head run
CUTAWAYS = [
    ("Cutaway: tight product close-up in hand — the voice continues over it", "Camera: slow push-in on the product."),
    ("Cutaway: hands mid-action with the product, over-shoulder angle", "Camera: handheld, follows the hands."),
    ("Cutaway: reaction — presenter at a three-quarter angle, eyes off-lens", "Camera: medium shot, static."),
]
ALT_FRAMING = {   # beat-native alternates (a different scale, same job)
    "COMMENT BAIT": ("Phone close-up — the keyword typed into a comment, the presenter's voice over it",
                     "Camera: static close-up on the phone screen."),
    "PAYOFF": ("Low-angle hero shot — the result held toward the lens, presenter at a three-quarter angle",
               "Camera: slow push-in through the beat."),
    "VERBAL HOOK + LOCK": ("Medium-wide at a three-quarter angle, eye-level, subject in hand",
                           "Camera: static."),
}
CUTAWAYS_NO_PRODUCT = [
    ("Cutaway: close-up insert of what the line is about — notes, phone screen or object", "Camera: slow push-in on the insert."),
    ("Cutaway: hands mid-action, over-shoulder angle", "Camera: handheld, follows the hands."),
    ("Cutaway: reaction — presenter at a three-quarter angle, eyes off-lens", "Camera: medium shot, static."),
]
# the gate's own D48 move vocabulary (vsp/gates.py gate2, substring match)
MOVE_KW = ("push-in", "push in", "pan", "tilt", "dolly", "handheld", "tracking", "move")
STATIC_MAX = 3.5          # D48 threshold (gate: duration > 3.5 s)
SLOW_KEYS = ("slow down", "unhurried", "never rushed")

# v2 (D64): meta notes and rule ids never reach a generation prompt — the
# maker's direction/delivery strings carry rulebook breadcrumbs ("Works muted
# (85% watch sound-off).", "(D73 charter hook stack)", "(F138)", "playbook")
# that the video model would try to render or obey literally.
_META_ID = (r"(?:\b[DFEQG]\d{1,3}[a-z]?\b|\u00a7|(?i:\bplaybook\b|\bdossier\b|"
            r"\bcharter\b|\bsound-off\b|\b\d+%\s*watch\b))")
_META_ID_RE = re.compile(_META_ID)
_META_PAREN = re.compile(r"\s*\((?=[^()]*" + _META_ID + r")[^()]*\)")
_META_SENT = re.compile(r"(?i)^works muted\b|\bverbal hook\s*(?:\u2264|<=?)\s*\d+\s*words\b|"
                        r"\bwatch sound-off\b|\bmuted viewers?\b.*\bplaybook\b")
_PROD_WORDS = re.compile(
    r"(?i)split[- ]?screen|timestamp|b-?roll|overlay|\bcut\b|zoom|\bpan\b|push[- ]?in|"
    r"slow[- ]?mo|freeze|graphic|\bshot\b|camera|\bframe\b|\bvo\b|on[- ]?screen|"
    r"caption|\blabel\b|arrow|circle|highlight|side[- ]by[- ]side")
_PAREN_ANY = re.compile(r"\s*(?:\(([^()]{1,120})\)|\[([^\[\]]{1,120})\])")


def _tidy(text):
    t = re.sub(r"\s+", " ", text or "").strip()
    t = re.sub(r"\s+([.,!?;:])", r"\1", t)
    t = re.sub(r"([.!?])[.,;:]+", r"\1", t)
    return t.strip(" ,;")


def clean_meta(text):
    """Strip rulebook breadcrumbs from a direction/delivery string: rule-id
    parentheticals ("(F138)", "(D73 charter hook stack)") and meta sentences
    ("Works muted.", "Verbal hook <=8 words total."). Never returns ''
    for non-empty input that had real content."""
    raw = re.sub(r"\s+", " ", text or "").strip()
    if not raw:
        return ""
    t = _META_PAREN.sub("", raw)
    sents = re.split(r"(?<=[.!?])\s+", t.strip())
    keep = [x for x in sents if x.strip() and not _META_SENT.search(x)]
    out = _tidy(" ".join(keep))
    return out if out else _tidy(t)


def split_on_screen(text):
    """Render-exactly on-screen text -> (display text, production notes).
    '(split-screen, timestamped)' is a staging note, never display copy (D122
    class): it is lifted into the shot's visual prompt instead. Rule-id notes
    are dropped."""
    notes = []

    def sub(m):
        inner = (m.group(1) or m.group(2) or "").strip()
        if _META_ID_RE.search(inner):
            return ""
        if _PROD_WORDS.search(inner):
            notes.append(inner)
            return ""
        return m.group(0)
    display = _tidy(_PAREN_ANY.sub(sub, re.sub(r"\s+", " ", text or "")))
    return display, notes


def _flat(text):
    """Block lines must stay single-line (the gate parses '- ' lines)."""
    return re.sub(r"\s*\n\s*", " ", (text or "").strip())


def shot_visual_prompt(sh, identity, product_desc, setting, light):
    """D64: one self-contained visual prompt per shot — no cross-shot references."""
    beat = sh["beat"].replace(" (cont.)", "")
    detail = re.sub(r"\s*\(VO continues\)", "", sh.get("direction", "")).strip()
    detail = clean_meta(detail).rstrip(".")
    # D64: strip cross-shot references the model cannot resolve ("same framing"
    # points at a shot it never saw — each prompt must stand alone)
    detail = re.sub(r"(?i)^same framing,\s*", "", detail)
    detail = detail[:1].upper() + detail[1:] if detail else "The presenter in the scene"
    camera = sh.get("camera") or SHOT_CAMERA.get(beat, "Camera: static.")
    staging = "; ".join(sh.get("staging") or [])
    extra = f" Staging: {staging}." if staging else ""
    if product_desc and re.search(r"(?i)\b(?:product|hands?|items?|props?|object|finds?)\b",
                                  detail):
        label = "Props in frame" if product_desc.startswith("only the everyday props") \
            else "Product in frame"
        extra += f" {label}: {product_desc}."
    return (f"{identity}. {detail}.{extra} Setting: {setting}. Light: {light}. {camera} "
            f"Photorealistic, 9:16 vertical. Any on-screen text is bold sans, high contrast.")


def niche_references(niche, k=3, db_path=None):
    """Top-k reels by likes in this niche: url + one-line why. Anchors the quality bar.

    Read-only (VSP_VIRAL_DB or ~/workspace/viral-research/viral.db): a missing
    DB returns [] and is never created as an empty file (pre-2.0 the bare
    sqlite3.connect() could create a 0-byte viral.db that then crashed
    research_bridge --refresh)."""
    db = None
    try:
        db = config.connect_ro(db_path)
        if db is None:
            return []
        rows = db.execute(
            "SELECT url, username, like_count, substr(notes,1,110) FROM reels "
            "WHERE niche LIKE ? AND url IS NOT NULL AND url != '' "
            "ORDER BY like_count DESC LIMIT ?", ("%"+niche+"%", k)).fetchall()
        if not rows:
            # fallback: niche absent from the DB (e.g. gadgets) — anchor on the
            # top reels overall rather than shipping unanchored
            rows = db.execute(
                "SELECT url, username, like_count, substr(notes,1,110) FROM reels "
                "WHERE url IS NOT NULL AND url != '' "
                "ORDER BY like_count DESC LIMIT ?", (k,)).fetchall()
        return [f"- {url} (@{user}, {likes or 0:,} likes) \u2014 {(notes or '').strip()}"
                for url, user, likes, notes in rows]
    except Exception:
        return []
    finally:
        if db is not None:
            db.close()


def parse_t(t):
    m = re.findall(r"(\d+(?:\.\d+)?)", t or "")
    return (float(m[0]), float(m[1])) if len(m) >= 2 else (0.0, 0.0)


def _window(t):
    """Valid script window -> (s, e); missing/degenerate -> (None, None)."""
    m = re.findall(r"(\d+(?:\.\d+)?)", t or "")
    if len(m) < 2:
        return None, None
    s, e = float(m[0]), float(m[1])
    return (s, e) if e > s else (None, None)


def _wps(delivery):
    return 2.5 if any(k in (delivery or "").lower() for k in SLOW_KEYS) else 3.0


def _fits(text, seconds, delivery):
    """The gate's D43 formula: words / wps <= window * 1.15."""
    return len((text or "").split()) / _wps(delivery) <= seconds * 1.15


def _gate_dur(s, e):
    """Duration exactly as gate 2 computes it from the rendered heading."""
    return float(f"{e:.1f}") - float(f"{s:.1f}")


def _b4a(dialogue, window, delivery):
    """B4a: the keyword CTA opens with the follow ask. Runs BEFORE sizing and
    picks the longest prefix that still fits an exact window (the old
    post-sizing rewrite added 9 words to a sized window -> D43 WARNING)."""
    kw = re.search(r"[Cc]omment\s+([A-Z][A-Z0-9]*)", dialogue)
    kw = kw.group(1) if kw else "LINK"
    for prefix in (f"Hit follow, comment {kw}, and I\u2019ll send it to you. ",
                   f"Hit follow, comment {kw}. ", "Hit follow \u2014 "):
        cand = prefix + dialogue
        if window is None or _fits(cand, window[1] - window[0], delivery):
            return cand
    return dialogue


def _order(items):
    """Windowed items by start (stable on document order); a windowless item
    goes right after its document-order predecessor (first if it has none).
    items: (doc_index, kind, item, s, e) tuples."""
    out = sorted([x for x in items if x[3] is not None], key=lambda x: (x[3], x[0]))
    for x in [x for x in items if x[3] is None]:
        pos = next((k + 1 for k, y in enumerate(out) if y[0] == x[0] - 1), 0)
        out.insert(pos, x)
    return out


def _block_lines(sh):
    """The '- ' lines render_bundle emits under '### Shot ...' (gate 2 parses
    exactly these for D47/D48). v2.1: '- Shot type:' (and, for AI-presenter
    proof shots, '- REAL FOOTAGE REQUIRED:') right after '- Camera:' — one
    renderer (vsp.shotplan.block_lines) so the planner checks exactly what
    the gate reads."""
    return shotplan.block_lines(sh)


def _talking_head(sh):
    """Gate 2's D47 predicate on this shot's block."""
    return "to camera" in "\n".join(_block_lines(sh)).lower().split("on-screen")[0]


def _has_move(sh):
    """Gate 2's D48 predicate (move keyword anywhere in the block)."""
    body = "\n".join(_block_lines(sh)).lower()
    return any(k in body for k in MOVE_KW)


def _camera_moves(sh):
    """Semantic check on the framing line only — "company" in the dialogue
    satisfies the gate's substring test but is not a camera move."""
    return any(k in sh["direction"].lower() for k in MOVE_KW)


def _is_sub(sh):
    return bool(re.search(r"[a-z]$", str(sh["n"])))


def _add_move(sh):
    if not _camera_moves(sh):
        mv = MOVE_SENTENCE.get(sh["beat"].replace(" (cont.)", ""),
                               "Slow push-in through the beat.")
        sh["direction"] = _tidy(sh["direction"].rstrip(".") + ". " + mv)
        sh["camera"] = "Camera: " + mv[0].lower() + mv[1:]


SUBSHOT_TARGET_S = 2.5    # cut every ~2.5 s (sub-shots stay <= ~3.1 s)


def _split(sh, product=True):
    """D48: cut a long shot into sub-shots with rotating framings."""
    dur = sh["e"] - sh["s"]
    beat = sh["beat"]
    plan = (None if product else CONCEPT_SUBSHOT_PLAN.get(beat)) or \
        SUBSHOT_PLAN.get(beat, GENERIC_SUBSHOTS)
    k = min(26, max(2, round(dur / SUBSHOT_TARGET_S)))
    step = dur / k
    out = []
    for i in range(k):
        ss, se = sh["s"] + i * step, sh["s"] + (i + 1) * step
        if i == k - 1:
            se = sh["e"]
        framing, camera = plan[i % len(plan)]
        first, last = i == 0, i == k - 1
        if first and sh.get("explicit"):
            framing = sh["direction"]        # the maker's own staging leads
        out.append({
            "n": f"{sh['n']}{chr(97 + i)}", "group": sh["n"], "item": sh.get("item"),
            "t": f"{ss:.1f}\u2013{se:.1f}s", "s": round(ss, 3), "e": round(se, 3),
            "beat": beat + (" (cont.)" if i else ""),
            "direction": framing + ("" if first else " (VO continues)"),
            "camera": camera, "explicit": bool(first and sh.get("explicit")),
            "on_screen": sh["on_screen"] if first else "",
            "staging": sh["staging"] if first else [],
            "dialogue": sh["dialogue"] if first else "",
            "delivery": sh["delivery"] if first else "",
            "rehook": sh["rehook"] if last else "",
            "match_cut": sh["match_cut"] if last else "",
        })
    return out


def _is_product_concept(d):
    """Product framing applies to products and showcase roundups (the finds
    are products); challenges / routines / advice have no product."""
    return _concept(d.get("prompt") or "") in ("product", "showcase")


def _reframe(sh, k, product):
    """D47: swap a talking-head framing for a different scale (a beat-native
    alternate, else a rotating cutaway); keeps the shot's other staging
    sentences, including its camera move."""
    beat = sh["beat"].replace(" (cont.)", "")
    framing, camera = ALT_FRAMING.get(beat) or \
        (CUTAWAYS if product else CUTAWAYS_NO_PRODUCT)[k % 3]
    rest = [x for x in re.split(r"(?<=[.!?])\s+", sh["direction"])
            if x and "to camera" not in x.lower() and "(vo continues)" not in x.lower()]
    tail = " (VO continues)" if "(VO continues)" in sh["direction"] else ""
    sh["direction"] = _tidy(" ".join([framing + "."] + rest)) + tail
    sh["camera"] = camera


def _rotate(shots, product):
    """D47: never 3 consecutive talking-head shots (gate 2's predicate) —
    the third is reframed; if its own lines say 'to camera' (dialogue), the
    second, then the first. Deterministic: cutaways rotate by a counter."""
    k = 0
    run = 0
    for i, sh in enumerate(shots):
        if not _talking_head(sh):
            run = 0
            continue
        run += 1
        if run < 3:
            continue
        for j in (i, i - 1, i - 2):
            cand = shots[j]
            saved = (cand["direction"], cand["camera"])
            _reframe(cand, k, product)
            k += 1
            if not _is_sub(cand) and _gate_dur(cand["s"], cand["e"]) > STATIC_MAX:
                _add_move(cand)
            if not _talking_head(cand):
                break
            cand["direction"], cand["camera"] = saved
        run = 0
        for j in range(i, -1, -1):
            if not _talking_head(shots[j]):
                break
            run += 1
    return shots


def build_shots(d):
    """Script dict -> (shots, vo_lines). Pure: no I/O (the shot library is a
    cached read-only table).

    v2.1: the legacy timeline below (_base_shots) is re-cut and typed by
    vsp.shotplan.plan — every shot carries a SHOT_LIBRARY shot_type with a
    reason plus scale/angle/move/purpose/energy/needs/ai_risk/ai_fallback/
    real_footage/setup/broll/sfx (CREATIVE-PLAN §1.4)."""
    shots, vo_lines = _base_shots(d)
    prompt = d.get("prompt") or ""
    shots = shotplan.plan(d, shots, ctx={"concept": _concept(prompt),
                                         "product_short": product_phrase(prompt)})
    return shots, vo_lines


def _base_shots(d):
    """Script dict -> (legacy shots, vo_lines): the v2.0 timeline of record.

    Timeline of record (v2): a valid script window is used exactly; only an
    item without one is sized from its words at the cursor (and pushes the
    items it would overlap). Each shot dict: n, group, t, s, e, beat,
    direction (shot-list framing), camera (generation camera line), on_screen
    (display text), staging (notes lifted out of on_screen), dialogue,
    delivery (display, meta-stripped), rehook, match_cut."""
    items = []
    for h in d.get("hook_stack", []) or []:
        if isinstance(h, dict):
            items.append(("HOOK", h))
    for b in d.get("beats", []) or []:
        if isinstance(b, dict):
            items.append(("BEAT", b))
    rows = [(i, kind, it) + _window(it.get("t", "")) for i, (kind, it) in enumerate(items)]
    product = _is_product_concept(d)
    shots, vo_lines, cursor, shift = [], [], 0.0, 0.0
    for idx, kind, it, s, e in _order(rows):
        btype = str(it.get("type") or "")
        dialogue = _flat(it.get("dialogue", ""))
        delivery_raw = _flat(it.get("delivery", ""))
        rehook = _flat(it.get("rehook", ""))
        if s is not None:
            s, e = s + shift, e + shift
            if cursor - s > 0.11:
                # overlap beyond D55's 0.1 s tolerance — only possible after a
                # sized (windowless) item or on malformed input: push this and
                # every later window by the same amount (no silent overlap)
                delta = cursor - s
                shift += delta
                s, e = s + delta, e + delta
        # B4a enforcement BEFORE sizing: keyword CTA must open with the follow ask
        if btype == "COMMENT BAIT" and dialogue and "follow" not in dialogue.lower():
            dialogue = _b4a(dialogue, (s, e) if s is not None else None, delivery_raw)
        if s is None:
            # only a missing window is sized (a fixed 0.5s default crams e.g.
            # "Look at this." into an unperformable window)
            s = cursor
            words = len(dialogue.split()) + len(rehook.split())
            e = s + max(0.5, words / _wps(delivery_raw) + 0.3 if words else 0.5)
        cursor = max(cursor, e)
        if dialogue:
            # D43: dialogue-time fit sanity check — brisk ~2.5 wps, slow ~2.0 wps
            wps = _wps(delivery_raw)
            need = len(dialogue.split()) / wps
            have = e - s
            flag = f"  <-- D43 WARNING: ~{need:.1f}s of speech in a {have:.1f}s window" if need > have * 1.15 else ""
            vo_lines.append(f"[{s:.1f}-{e:.1f}s] {dialogue}{flag}")
        if rehook:
            # D44: re-hooks are spoken transitions — they belong in the transcript
            vo_lines.append(f"[{e:.1f}s] (spoken transition) {rehook}")
        on_screen, staging = split_on_screen(it.get("on_screen", ""))
        explicit = bool(it.get("shot_direction") or it.get("direction"))
        direction = it.get("shot_direction") or it.get("direction") or \
            (None if product else CONCEPT_SHOT_DIRECTION.get(btype)) or \
            BEAT_SHOT_DIRECTION.get(btype, DEFAULT_DIRECTION)
        n = len(shots) + 1
        shots.append({
            "n": n, "group": n, "item": idx, "t": f"{s:.1f}\u2013{e:.1f}s",
            "s": round(s, 3), "e": round(e, 3),
            "beat": btype, "direction": clean_meta(_flat(direction)) or DEFAULT_DIRECTION,
            "camera": SHOT_CAMERA.get(btype, "Camera: static."), "explicit": explicit,
            "on_screen": on_screen, "staging": staging, "dialogue": dialogue,
            "delivery": clean_meta(delivery_raw), "rehook": rehook,
            "match_cut": _flat(it.get("match_cut", "")),
        })

    # D48: every shot > 3.5 s is cut into sub-shots or carries a camera move
    final_shots = []
    for sh in shots:
        dur = _gate_dur(sh["s"], sh["e"])
        if dur > STATIC_MAX and sh["beat"] not in NEVER_SPLIT \
                and dur > SPLIT_AT.get(sh["beat"], STATIC_MAX):
            final_shots.extend(_split(sh, product))
        else:
            if dur > STATIC_MAX:
                _add_move(sh)
            final_shots.append(sh)
    # D47: scale rotation — never 3 consecutive talking-head shots
    shots = _rotate(final_shots, product)
    return shots, vo_lines


# ------------------------------------------------------------ brief assets
def _niche_keys(niche):
    n = (niche or "").strip().lower()
    return [k for k in (n, NICHE_ALIAS.get(n)) if k]


def presenter_identity(d):
    """Locked identity: the persona entry wins for AI (ONE face across every
    video); otherwise (presenter, niche) -> (presenter, alias) ->
    (presenter, generic). v2: an AI presenter without a persona entry used to
    fall back to the HUMAN generic identity."""
    presenter = d.get("presenter") or "human"
    persona = d.get("persona") or {}
    if presenter == "ai" and persona.get("identity"):
        return persona["identity"]
    for key in _niche_keys(d.get("niche")):
        if (presenter, key) in PRESENTER_IDENTITY:
            return PRESENTER_IDENTITY[(presenter, key)]
    return PRESENTER_IDENTITY.get((presenter, "generic"),
                                  PRESENTER_IDENTITY[("human", "generic")])


_PRICE_RE = re.compile(r"[$\u20ac\u00a3]\s?\d[\d,]*(?:\.\d+)?|\b\d[\d,]*(?:\.\d+)?\s?"
                       r"(?:dollars|bucks|usd|euros?|pounds)\b", re.I)


def product_phrase(prompt):
    """The product noun phrase of a prompt: no price (D37), braces, article."""
    p = re.sub(r"[{}]", "", prompt or "")
    p = _PRICE_RE.sub("", p)
    p = re.sub(r"\s+", " ", p).strip(" .,!?-")
    p = re.sub(r"(?i)^(?:a|an|the)\s+", "", p)
    return p.strip()


def _concept(prompt):
    low = (prompt or "").strip().lower()
    if re.match(r"(?:\d+\s+)?(?:things|stuff|items|finds)\s+in\s+my\b", low):
        return "showcase"
    if re.match(r"i\s+(?:stopped|quit|deleted|gave up|ditched|dropped|tried|did|"
                r"read|went|unfollowed|cut|skipped|woke)\b", low):
        return "challenge"
    if re.search(r"\broutine\b", low):
        return "routine"
    if re.match(r"(?:why|how|what|stop|never|the\s+\d+)\b", low):
        return "advice"
    return "product"


def product_description(d):
    """D64 product block: a known look on a word-boundary match, else a
    description derived from the prompt itself (never a price or a claim)."""
    phrase = product_phrase(d.get("prompt") or "")
    low = phrase.lower()
    for pat, look in PRODUCT_LOOK:
        if re.search(pat, low):
            return look
    concept = _concept(d.get("prompt") or "")
    if not phrase:
        return PRODUCT_LOOK_GENERIC
    if concept == "showcase":
        m = re.search(r"\bin\s+my\s+([a-z][a-z ]*?)\s+(?:that|which|i)\b", low)
        where = m.group(1) if m else "space"
        return (f"the everyday {where} finds featured in the video — each one plain and "
                f"unbranded, true to its real-world shape, size and materials")
    if concept in ("challenge", "routine", "advice"):
        return (f"only the everyday props this concept needs (\u201c{phrase}\u201d) — "
                f"plain, unbranded, real-world objects")
    return (f"the {phrase} exactly as named — plain and unbranded, with its real-world "
            f"shape, size, materials and colors; no invented features")


def niche_setting(d):
    low = product_phrase(d.get("prompt") or "").lower()
    for pat, val in SETTING_BY_PRODUCT:
        if re.search(pat, low):
            return NICHE_SETTING[val] if isinstance(val, str) else val
    for key in _niche_keys(d.get("niche")):
        if key in NICHE_SETTING:
            return NICHE_SETTING[key]
    return NICHE_SETTING["generic"]


def niche_style_notes(d):
    for key in _niche_keys(d.get("niche")):
        if key in NICHE_STYLE_NOTES:
            return NICHE_STYLE_NOTES[key]
    return NICHE_STYLE_NOTES["generic"]


def _gender(identity):
    if re.search(r"(?i)\b(?:woman|female|girl|lady)\b", identity or ""):
        return "Female"
    if re.search(r"(?i)\b(?:man|male|guy)\b", identity or ""):
        return "Male"
    return None


def _pronoun(identity):
    g = _gender(identity)
    return {"Female": "her", "Male": "him"}.get(g, "them")


def slugify(prompt):
    return re.sub(r"[^a-z0-9]+", "-", (prompt or "x").lower()).strip("-") or "x"


def _shot_label(shots, beat):
    grp = [sh for sh in shots if sh["beat"].replace(" (cont.)", "") == beat]
    if not grp:
        return None
    first = grp[0]
    same = [sh for sh in grp if sh.get("group") == first.get("group")]
    if len(same) > 1:
        return f"{first.get('group')} ({same[0]['n']}\u2013{same[-1]['n']})"
    return str(first["n"])


def _hook_shots_label(d, shots):
    hook_end = max([_window(h.get("t", ""))[1] or 0.0
                    for h in d.get("hook_stack") or []] + [0.0]) or 3.0
    hs = [sh for sh in shots if sh["s"] < hook_end - 1e-6] or shots[:2]
    if not hs:
        return None
    if len(hs) == 1:
        return f"Shot {hs[0]['n']}"
    return f"Shots {hs[0]['n']}\u2013{hs[-1]['n']}"


def render_bundle(d, shots, vo_lines, refs=None):
    """Script + shots -> bundle markdown (shot list + Antigravity brief).
    `refs` defaults to niche_references(d["niche"]). DELIVERABLE verbatim."""
    # D64: model-followable brief assets — computed once, reused verbatim.
    # Persona-loop x pipeline (2026-09-28): the script's locked persona identity
    # wins over the per-niche map — ONE face across every video (Q2/F10: drift
    # triggers eerie rejection; F9: same-face repetition builds liking).
    _persona = d.get("persona") or {}
    presenter_identity_txt = presenter_identity(d)
    product_desc = product_description(d)
    setting_desc, light_desc = niche_setting(d)
    style_notes = niche_style_notes(d)
    slug = slugify(d.get("prompt"))
    is_ai = d.get("presenter") == "ai"
    # v2.1: prompt assets for the shot recommender's D160-clean prompts, and
    # the sibling creative modules (absent module or key = section omitted)
    _prompt = d.get("prompt") or ""
    A = shotplan.prompt_assets(d, presenter_identity_txt, product_desc, setting_desc, light_desc,
                               ctx={"concept": _concept(_prompt),
                                    "product_short": product_phrase(_prompt)})
    _dir = d.get("direction") if isinstance(d.get("direction"), dict) else None
    _disc = d.get("discovery") if isinstance(d.get("discovery"), dict) else None
    _dir_mod = _optional("vsp.direction") if _dir else None
    _disc_mod = _optional("vsp.discovery") if _disc else None

    L = []
    L.append(f"# Production bundle — {d.get('prompt')}")
    L.append(f"niche: {d.get('niche')} | presenter: {d.get('presenter')} | format: {d.get('format')} | "
             f"duration: {d.get('duration_s')}s | hook family: {d.get('hook_family')}")
    L.append("")
    L.append("## Shot list")
    for sh in shots:
        L.append(f"### Shot {sh['n']} ({sh['t']}) — {sh['beat']}")
        L.extend(_block_lines(sh))
        L.append("")
    L.append("## Antigravity brief")
    L.append("")
    # D64 (2026-09-27, user verdict: "the video model did not follow the script
    # because it was too bad of a prompt"): the old brief was a production
    # document, not a generatable prompt — no identity lock (the model invented
    # a new person every shot), cross-shot references it cannot resolve ("same
    # framing"), workflow instructions mixed with generation instructions, and
    # asks it cannot fulfill (watch reference URLs, pick trending sounds, emit
    # words.json from audio it didn't synthesize). The brief is now structured
    # as MODEL PROMPTS FIRST: a locked presenter identity repeated verbatim in
    # every shot, one self-contained visual prompt per shot (subject + action +
    # setting + light + camera — no cross-references), a concrete product block,
    # a negative prompt, and the voiceover isolated as a separate audio track.
    # Everything the pipeline does (not the model) lives under WORKFLOW.
    L.append("> HOW TO READ THIS BRIEF: the SHOT PROMPTS are your generation")
    L.append("> instructions — one self-contained prompt per shot. The VOICEOVER is")
    L.append("> a separate audio track, never on-screen text. Everything under")
    L.append("> WORKFLOW is for the production pipeline, not for generation.")
    L.append("")
    L.append("## PRESENTER — identity lock")
    L.append(f"{presenter_identity_txt} — use this exact description in every shot "
             "prompt that shows the presenter's face. Same person, same hair, same outfit in ALL shots. "
             "Never redesign the presenter between shots. Hands-only shots carry a short hands "
             "reference instead, and product-only shots carry no presenter text.")
    L.append("")
    if is_ai:
        # D138 (2026-09-28): the frame-0 disclosure label is carried by EVERY
        # presenter=ai brief — it no longer depends on a persona entry.
        L.append("## AI DISCLOSURE — frame-0 label (required)")
        L.append("On-screen small \"AI persona\" label from FRAME 0, top safe zone, minimum 2 "
                 "seconds, separate from hook text. Disclosure costs nothing on reach and "
                 "omission costs trust (dossier Q7/F130).")
        L.append("")
        # Persona-loop x pipeline (2026-09-28): fidelity rules distilled from the
        # AI-persona persuasion dossier — the video model must not "improve" her.
        _pname = (_persona.get("name") or "The AI persona")
        _pro = _pronoun(presenter_identity_txt)
        L.append(f"## PERSONA — fidelity rules (do not redesign {_pro})")
        L.append(f"- {_pname} is a recurring character. Render the identity above EXACTLY in every shot of THIS video that shows {_pro} and keep {_pro} recognizably identical across videos in the series — face, hair, outfit, age. Identity drift reads as fake and triggers rejection (dossier Q2/F10).")
        L.append("- Neutral, non-sexualized presentation — natural look, modest plain clothing as described. Sexualized styling damages brand attitude and purchase intent (dossier Q1/F6).")
        L.append(f"- Casting is neutral by design: attractiveness has no direct effect on purchase intent — credibility and product fit do the work (dossier Q1/F2). Do not beautify, glam up, or youth-shift {_pro} beyond the description.")
        L.append("- On-screen small \"AI persona\" label from FRAME 0, top safe zone, minimum 2 seconds, separate from hook text. Disclosure costs nothing on reach and omission costs trust (dossier Q7/F130).")
        L.append("- Funnel note: AI personas convert indirectly — this video's job is loyal-core building (follow, community, familiarity), not hard-sell. Keep the CTA warm, never pressuring (dossier Q10/F56, F49).")
        L.append("")
    L.append("## PRODUCT")
    L.append(f"{product_desc}. Match this exactly in every shot it appears in. "
             "Do not invent logos, brand names, or label text — plain unbranded packaging.")
    L.append("")
    L.append("## SHOT PROMPTS (self-contained — generate each shot from its own prompt only)")
    for sh in shots:
        L.append(f"#### Prompt — Shot {sh['n']} ({sh['t']})")
        # v2.1 (D160): [scale, angle, move]: subject, one action, setting,
        # light, vertical phone footage, one continuous shot, no in-frame text;
        # the identity lock only where the face is in frame
        _vp = shotplan.visual_prompt(sh, A) or \
            shot_visual_prompt(sh, presenter_identity_txt, product_desc, setting_desc, light_desc)
        L.append(f"VISUAL PROMPT: {_vp}")
        if sh["on_screen"]:
            L.append(shotplan.overlay_line(sh["on_screen"]))
        if sh["dialogue"]:
            L.append("AUDIO (voiceover for this shot — audio only, never on-screen text): "
                     + shotplan.says(A["name"], sh["dialogue"]))
            if sh["delivery"]:
                L.append(f"DELIVERY: {sh['delivery']}")
        else:
            L.append("AUDIO: no dialogue — visuals only (voiceover continues from previous shot if mid-sentence).")
        if sh["rehook"]:
            L.append("SPOKEN TRANSITION into next shot (audio only): " + shotplan.says(A["name"], sh["rehook"]))
        if sh["match_cut"]:
            L.append(f"EDIT NOTE: {sh['match_cut']}")
        L.append("")
    _alt = shotplan.alt_openings_md(d, A, shots)
    if _alt:
        L.extend(_safe_section(_alt, d).split("\n"))
        L.append("")
    L.extend(_safe_section(shotplan.shoot_plan_md(d, shots, A), d).split("\n"))
    L.append("")
    L.append("## VOICEOVER — separate audio track")
    L.append("AUDIO ONLY. Do not render any of these words as on-screen text, captions, "
             "or graphics. This is the spoken track laid over the shots above.")
    L.extend(vo_lines)
    L.append("")
    # v2: the voice follows the locked persona voice / the identity's gender
    # (it hard-coded "Female voice" even for male identities)
    _voice = (_persona.get("voice") or "").strip() if is_ai else ""
    _g = _gender(presenter_identity_txt)
    _cast = (f"{_voice.rstrip('.')} (locked persona voice — the same voice in every video)"
             if _voice else "cast a conversational human read — like a real person talking "
             "to a friend, never an ad read")
    if is_ai:
        # v2.1: an AI persona speaks with a disclosed synthetic voice — never
        # "human voice only" (research §1), never claimed to be a real person
        _cast = (re.sub(r"(?i)\bhuman read\b", "read", _cast) + " — a natural-prosody synthetic "
                 "voice, disclosed as AI, never robotic and never presented as a real person")
    _who = (f"{_g} voice, matching the presenter identity above" if _g
            else "Voice matching the presenter identity above")
    _tone = (" — never pressuring" if "warm" in _voice.lower()
             else " — warm and confident, never pressuring")
    _vs = _call(_dir_mod, "voice_spec", _dir)
    if _vs:
        _vs = _safe_section(_vs, d).replace("\n", " ").strip()
    if _vs:
        L.append(_vs if _vs.startswith("Voice spec:") else f"Voice spec: {_vs}")
    else:
        L.append(f"Voice spec: {_cast}. {_who}{_tone}. "
                 "Vary pace naturally: unhurried on trust "
                 "beats, brisk 160–180 wpm on the CTA. Light natural imperfections welcome "
                 "(breath, pace shifts, emphasis). Never monotone, never a polished commercial "
                 "delivery. No scripted laughs/sighs.")
    L.append("")
    L.append("## STYLE")
    _lane = "AI" if is_ai else str(d.get("presenter", "human")).capitalize()
    _sp = _call(_dir_mod, "style_paragraph", _dir)
    if _sp:
        _sp = _safe_section(_sp, d).replace("\n", " ").strip()
    if _sp:
        L.append(_sp)
    else:
        L.append(f"{_lane} UGC {d.get('format')}, {d.get('niche')} niche. 9:16 vertical. "
             f"{setting_desc[:1].upper() + setting_desc[1:]}. {light_desc[:1].upper() + light_desc[1:]}. "
             f"Imperfection welcome (flaws in the BEFORE, faint handheld in candid beats) — "
             f"polish kills trust in this format. "
             f"Transitions: hard cuts by default; match-cut on transformation beats. "
             f"On-screen graphic text (labels like BEFORE/AFTER, TEST 1): bold sans, high contrast, max 3 words per card. "
             f"Safe zones: keep graphic text and key action clear of the top 250px, bottom 320px (IG UI overlays), and the right rail. "
             f"Product accuracy: match the PRODUCT block above exactly — no invented branding. "
             f"Audio: voiceover clean and forward; neutral upbeat background music bed low underneath, ducked under speech.")
    for sn in style_notes:
        L.append(f"- {sn}")
    L.append("")
    _cd = _call(_dir_mod, "render_md", _dir)
    if _cd:
        L.extend(_safe_section(_cd, d, "## CREATIVE DIRECTION — vibe & tone").split("\n"))
        L.append("")
    L.append("## NEGATIVE PROMPT — never render")
    L.append("Warped faces, extra fingers or limbs, melted hands, garbled / misspelled / merged "
             "text, watermarks or logos, burned-in captions or subtitles, letterbox or pillarbox bars, "
             "plastic CGI skin, stock-photo stiffness. Never render text, captions, labels or cards "
             "in-frame — every word on screen is added in the edit.")
    L.append("")
    L.append("## Reference reels (human review — the quality bar)")
    L.append("The style notes above are distilled from these; the URLs are for human review, "
             "not for the model.")
    if refs is None:
        refs = niche_references(d.get("niche", ""))
    L.extend(refs if refs else ["- (no references found for this niche)"])
    L.append("")
    L.append("## Render spec")
    L.append(RENDER_SPEC.replace("<slug>", slug))
    L.append("")
    L.append("## Do NOT")
    L.append(DO_NOT + " Do NOT render voiceover words as on-screen text." + (AI_VOICE_NOTE if is_ai else ""))
    L.append("")
    L.append("## Fallbacks")
    # v2: fallback shot numbers come from the actual shots (was "Shot 8")
    fb = ["If any shot can't be rendered as specified, use the simpler version — never silently drop the beat."]
    _bait = _shot_label(shots, "COMMENT BAIT")
    if _bait:
        fb.append(f"Shot {_bait} fallback: presenter holds phone showing a DM notification close-up, points at it. "
                  "If on-screen phone/UI text renders garbled, use the fallback with the notification visible but no readable text required.")
    fb.append("Any product-macro fallback: clean product hero on a neutral surface, slow push-in.")
    if is_ai:
        _chain = [f"Shot {sh['n']} → {sh['ai_fallback']}" for sh in shots
                  if sh.get("ai_fallback") and not sh.get("real_footage")]
        if _chain:
            fb.append("AI retries: up to 3 attempts per shot, then swap to its fallback shot type ("
                      + "; ".join(_chain) + "), then to text-card-over-motion.")
    L.append(" ".join(fb))
    L.append("")
    L.append("## WORKFLOW (production pipeline — not generation instructions)")
    L.append("Send a draft for review before the final render.")
    L.append("")
    _open = _hook_shots_label(d, shots) or "Shots 1\u20132"
    L.append(f"Variant note: the cold-open cut uses {_open} as its opening — keep them self-contained. "
             "(Marlowe's variant stage.)")
    L.append("")
    L.append("## DELIVERABLE (standing)")
    L.append(DELIVERABLE)
    L.append("")
    L.append("words.json: if your pipeline synthesizes the voiceover, export word-level timings as "
             f"{slug}-words.json; otherwise omit it — Marlowe's caption stage aligns separately.")
    L.append("")
    _pd = _call(_disc_mod, "render_md", _disc, d)
    if _pd:
        L.extend(_safe_section(_pd, d, "## POSTING & DISCOVERY").split("\n"))
        L.append("")
    L.append("## Caption + hashtags (post as-is)")
    L.append(d.get("caption", ""))
    return "\n".join(L)


AI_VOICE_NOTE = (" AI presenter: the voice is the persona's disclosed, natural-prosody synthetic "
                 "voice — human-sounding, never a robotic TTS read, never presented as a real person.")


def _optional(modname):
    """A sibling creative module (vsp.direction / vsp.discovery) or None."""
    mod = sys.modules.get(modname)
    if mod is not None:
        return mod
    try:
        import importlib
        import importlib.util
        if importlib.util.find_spec(modname) is None:
            return None
        return importlib.import_module(modname)
    except Exception:  # noqa: BLE001 — an unimportable module = section omitted
        return None


def _call(mod, fn, *args):
    f = getattr(mod, fn, None) if mod is not None else None
    if not callable(f):
        return None
    try:
        out = f(*args)
    except Exception:  # noqa: BLE001 — a failing renderer omits its section
        return None
    return out if isinstance(out, str) and out.strip() else None


def _safe_section(md, d, heading=None):
    """New bundle sections never carry a creative_vocab.BUNDLE_FORBIDDEN
    phrase ('### Shot', 'same body', 'D43 WARNING', 'FIXTURE') or a D46
    link group the script caption doesn't already use."""
    from vsp import creative_vocab as V
    allowed = V.link_groups_in(d.get("caption", ""))
    out = []
    for line in (md or "").strip("\n").split("\n"):
        if "same body" in line.lower() or any(p in line for p in V.BUNDLE_FORBIDDEN):
            continue
        if V.link_groups_in(line) - allowed:
            continue
        out.append(line)
    if heading:
        out = [x for x in out if x.strip() != heading]
        while out and not out[0].strip():
            out.pop(0)
        if out and out[0].startswith("## "):
            out.pop(0)                    # a foreign heading: ours is the contract
        out = [heading] + out
    return "\n".join(out)


def build_bundle(d, refs=None):
    """Script dict -> (bundle_text, shots, vo_lines)."""
    shots, vo_lines = build_shots(d)
    return render_bundle(d, shots, vo_lines, refs), shots, vo_lines


def main():
    args = [x for x in sys.argv[1:]]
    out = None
    if "--out" in args:                      # documented form: --out bundle.md
        i = args.index("--out")
        out = args[i + 1] if i + 1 < len(args) else None
        del args[i:i + 2]
    if not args:
        print("usage: make_shotlist.py script.json [bundle.md | --out bundle.md]",
              file=sys.stderr)
        sys.exit(2)
    src = args[0]
    if out is None and len(args) > 1:
        out = args[1]
    with open(src, encoding="utf-8") as f:
        d = json.load(f)
    bundle, shots, _ = build_bundle(d)
    slug = re.sub(r"[^a-z0-9]+", "-", d.get("prompt", "script").lower()).strip("-")
    out = out or os.path.join(config.outputs_dir(), f"{slug}-bundle.md")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(bundle)
    print(f"wrote {out} ({len(shots)} shots)")
    print("=" * 60)
    print(bundle)

if __name__ == "__main__":
    main()
