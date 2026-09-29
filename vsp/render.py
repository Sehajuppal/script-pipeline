"""vsp/render.py — render hand-off for the Antigravity agent (pipeline v2.2,
WS-RENDER): per run, a Gemini Omni shot plan (render.json), a Cartesia Sonic
voice plan (voice_plan.json) and a short human summary (render.md).

    build_render(script, shots, slug=None, script_sha=None, voice_lane=None,
                 ai_broll=False, consent_ref=None) -> dict      render.json
    omni_prompt(shot, ctx) -> str          one §6.2 prompt string per shot
    build_voice_plan(script, shots=None, voice_lane=None, consent_ref=None,
                     voice_id=None) -> dict                     voice_plan.json
    check_render(r, script) -> [problem]   contract, lanes, prompt hygiene
    check_voice_plan(vp, script) -> [problem]
    render_md(r, vp) -> str                "## RENDER HANDOFF — Gemini Omni + Cartesia"
    build_all(script, shots, **kw) -> (render, voice_plan)
    write(outdir, script, shots, **kw) -> [file names]
        kw: slug, script_sha, voice_lane, ai_broll, consent_ref, voice_id
    selfcheck() -> (ok, lines)

    python3 -m vsp.render selfcheck | build <outdir> | check <outdir> | show <outdir>

`shots` is the in-process list from make_shotlist.build_shots, the shots.json
dict or its list, or None (built here); all give byte-identical output.
script_sha defaults to script_sha256(script), the sha256 of script.json as
pipeline stage 4 writes it. Contract tables: docs/ws-render-notes.md.

Sources: docs/research/video-generation-omni.md §6 + OMNI_CAPS and
docs/research/voice-cartesia.md §7 + CARTESIA_CAPS. The rules pack that
consumes these files is antigravity/ (AGENTS.md, rules, skills + scripts);
selfcheck() dry-runs its scripts.

Lanes. presenter=ai: presenter_mode "ai", voice lane "ai_persona", every
disclosure on; Omni renders presenter shots from the identity lock and a
synthetic presenter sheet, while real_footage (proof) shots stay "real"
(filmed, never generated). presenter=human: presenter_mode "human", voice
lane "real_voice" by default; every face or hands shot is "real"; faceless
product shots are "real" unless ai_broll=True (then "ai", and the AI
toggles go on). The creator_clone voice lane needs a consent_ref.
Edit-only shot types are "edit"; the loop-return frame is "reuse" of shot 1
(an Omni call from the frame-0 still only when shot 1 itself is generated).

Pure and deterministic: no I/O besides the cached shot library, no RNG, no
set iteration in outputs; stdlib only, py3.9+.
"""
import base64
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(_HERE)
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from vsp import lexicon as LX    # noqa: E402
from vsp import shotplan as SP   # noqa: E402
from vsp import timing as TM     # noqa: E402

SCHEMA_VERSION = 1
HEADING = "## RENDER HANDOFF \u2014 Gemini Omni + Cartesia"
DASH, NDASH = "\u2014", "\u2013"
PACK_DIR = os.path.join(REPO, "antigravity")
FILES = ("render.json", "voice_plan.json", "render.md")

# ----------------------------------------------------------- Gemini Omni
# OMNI_CAPS (research §6.10); prices are per output second
OMNI_MODEL = "gemini-omni-1.1-flash"
OMNI_FALLBACK = "veo-3.1-fast-generate-preview"
OMNI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
OMNI_PER_S = {"360p": 0.034, "720p": 0.101, "1080p": 0.152, "4k": 0.304}
CLIP_MIN, CLIP_MAX, LIPSYNC_CLIP_MAX = 3, 10, 7
LIPSYNC_LINE_MAX_S = 6.0
SOURCE_FPS = 24
WINDOW_IN_S = 0.5
MASTER = {"width": 1080, "height": 1920, "fps": 30,
          "conform": "duplicate frames 24\u219230; never optical-flow interpolation"}
PASSES = {"draft": {"resolution": "360p", "max_attempts": 3, "delivery": "inline",
                    "store": True},
          "final": {"resolution": "1080p", "max_attempts": 2, "delivery": "uri",
                    "store": True}}
EDIT_TURNS_MAX = 2
MAX_IMAGES = 10
MODES = ("ai", "real", "edit", "reuse")
TASKS = ("text_to_video", "image_to_video", "reference_to_video")
NATIVE_AUDIO = ("keep_ambience", "drop")
# D162: render hand-off lane integrity (presenter <-> voice lane <-> disclosure;
# a human-lane person is never synthesised; a clone needs consent_ref)
LANES = ("ai_persona", "creator_clone", "real_voice")
LIPSYNC_METHODS = ("native-then-lipsync-pass", "creator-take-then-lipsync-pass")
UGC_VIBES = ("raw-ugc", "story-vlog", "hype-energy", "playful-comedic",
             "before-after-reveal")
SYNC_TOLERANCE_MS = {"lead": 45, "lag": 125}          # ITU-R BT.1359-1
TAGS = ("<FIRST_FRAME>", "<LAST_FRAME>")
PLATFORM_TOGGLES = (("tiktok", "is_aigc"), ("instagram", "is_ai_generated"),
                    ("youtube_shorts", "containsSyntheticMedia"))

# -------------------------------------------------------------- Cartesia
# CARTESIA_CAPS (research §8); house ranges from §7.1/§7.2
ENGINE = {"provider": "cartesia", "base_url": "https://api.cartesia.ai",
          "api_version": "2026-08-14", "endpoint": "/tts/sse", "mode": "line",
          "model_id": "sonic-3.6-2026-08-27", "locale": "en-US",
          "normalization": "auto", "pronunciation_dict_id": None,
          "add_timestamps": True,
          "output_format": {"container": "raw", "encoding": "pcm_s16le",
                            "sample_rate": 48000}}
EMOTIONS = (
    "neutral", "happy", "excited", "enthusiastic", "elated", "euphoric", "triumphant",
    "amazed", "surprised", "flirtatious", "curious", "content", "peaceful", "serene",
    "calm", "grateful", "affectionate", "trust", "sympathetic", "anticipation",
    "mysterious", "angry", "mad", "outraged", "frustrated", "agitated", "threatened",
    "disgusted", "contempt", "envious", "sarcastic", "ironic", "sad", "dejected",
    "melancholic", "disappointed", "hurt", "guilty", "bored", "tired", "rejected",
    "nostalgic", "wistful", "apologetic", "hesitant", "insecure", "confused",
    "resigned", "anxious", "panicked", "alarmed", "scared", "proud", "confident",
    "distant", "skeptical", "contemplative", "determined")
PRIMARY_EMOTIONS = ("neutral", "calm", "angry", "content", "sad", "scared")
EMOTIVE_VOICES = {"Leo": "0834f3df-e650-4766-a20c-5a93a43aa6e3",
                  "Jace": "6776173b-fd72-460d-89b3-d85812ee518d",
                  "Kyle": "c961b81c-a935-4c17-bfb3-ba2239de8c2f",
                  "Gavin": "f4a3a8e4-694c-4c45-9ca0-27caf97901b5",
                  "Maya": "cbaf8084-f009-4838-a096-07ee2e6612b1",
                  "Tessa": "6ccbfb76-1fc6-48f7-b71d-91ac6298247b",
                  "Dana": "cc00e582-ed66-4004-8336-0175b85c85f6",
                  "Marian": "26403c37-80c1-4a1a-8692-540551ca2ae5"}
SPEED_API, VOLUME_API = (0.6, 1.5), (0.5, 2.0)
SPEED_HOUSE, VOLUME_HOUSE = (0.9, 1.15), (0.9, 1.2)
WPM_AT_1 = 175            # §3.5: keep voices that read 165-185 wpm at speed 1.0
WPM_WARN, WPM_FAIL, WPM_CAP = 190, 200, 190
ANCHOR_S = 0.10
GAP_S, GAP_PRE_PAYOFF_S, GAP_POST_PAYOFF_S = 0.3, 0.5, 0.4
# §7.2: tone -> (band wpm, emotion, fallback, speed start, volume)
TONES = {"warm": ((155, 175), "content", None, 1.0, 1.0),
         "confident": ((160, 180), "confident", "neutral", 1.0, 1.05),
         "excited": ((170, 190), "excited", "happy", 1.05, 1.1),
         "calm": ((150, 160), "calm", "peaceful", 1.0, 0.9),
         "deadpan": ((155, 175), "neutral", None, 1.0, 1.0),
         "expert": ((150, 170), "confident", "neutral", 1.0, 1.0),
         "playful": ((165, 185), "happy", "curious", 1.05, 1.0),
         "empathetic": ((150, 165), "sympathetic", "calm", 1.0, 0.95),
         "curious": ((160, 180), "curious", "anticipation", 1.0, 1.0),
         "serious": ((150, 170), "neutral", "determined", 1.0, 1.0)}
ENERGY_VOLUME = {1: 0.9, 2: 0.9, 3: 1.0, 4: 1.05, 5: 1.15}
INLINE_TAG_RE = re.compile(r"<(?:speed ratio=\"[\d.]+\"|volume ratio=\"[\d.]+\"|"
                           r"emotion value=\"[a-z]+\"|break time=\"\d+(?:ms|s)\")\s*/>|"
                           r"</?spell>")
INITIALISMS = {"LED", "USB", "UV", "TV", "AI", "DIY", "SPF", "PSA", "POV", "FAQ",
               "ASMR", "HDMI", "GPS", "LCD", "OLED", "RGB", "USA", "UK", "EU", "NYC",
               "BPA", "PVC", "CBD", "HD", "SUV", "DM", "DMS", "ID", "OK", "PM", "AM",
               "ADHD", "HIIT", "EMS", "RFID", "NFC", "MP3", "4K", "3D", "USB-C"}

# ------------------------------------------------------------ vocabulary
# Prompt-side camera words (shotplan.MOVE_WORDS without the bracketed forms)
MOVE_PROMPT = dict(SP.MOVE_WORDS, orbit="slow tracking arc",
                   **{"speed-ramp": "fast handheld push-in that slows sharply",
                      "pull-out": "slow dolly out"})
# Present-tense action per shot type, already in motion at the first frame.
# kind decides the subject: face -> identity lock, hands -> hands reference,
# product -> product text, place -> the setting, scene -> the problem,
# still -> the first-frame image (image-to-video: motion only).
ACTIONS = {
    "hook-hands-mid-action": ("hands", "already mid-motion using {p}, the product filling the lower two-thirds of the frame"),
    "result-first-reveal": ("product", "at the frame edge beside {result}, already in view"),
    "problem-state-open": ("scene", "at its worst, untidied"),
    "pov-hands-first-use": ("hands", "use {p} with one simple motion, already moving"),
    "face-reaction-product": ("face", "reacts with raised eyebrows to {p} held in the lower third of the frame, no speech"),
    "text-card-over-motion": ("product", "resting on a clean surface, clear empty space in the upper-middle frame"),
    "unboxing-mid-open": ("hands", "lift the lid of a plain unbranded box that is already half-open, {p} half out"),
    "comparison-side-by-side": ("product", "sitting beside a plain unbranded alternative of the same kind, the camera travelling from the alternative to it"),
    "day-counter-selfie": ("face", "holds the phone at arm's length and glances at the lens, no speech"),
    "macro-texture-ecu": ("product", "its surface texture filling the frame, shallow depth of field, macro lens"),
    "label-detail-ecu": ("still", "the real label in the first frame, the camera tilting slowly down it, letters unchanged, no other motion"),
    "talking-head-mcu": ("face", "speaks to the lens"),
    "talking-head-product-in-hand": ("face", "holds {p} at chin height, front toward the camera, and speaks to the lens"),
    "selfie-walk-talk": ("face", "walks slowly toward the camera holding the phone at arm's length and talks to the lens"),
    "mws-cta-to-camera": ("face", "stands beside {p} and speaks to camera"),
    "reaction-cutaway-3q": ("face", "looks down at {subject} and nods slightly, eyes off-lens, no speech"),
    "profile-look-cutaway": ("face", "studies {p} side-on, no speech"),
    "over-shoulder-demo": ("hands", "use {p} with one simple motion, already moving"),
    "overhead-hands-demo": ("hands", "enter from the bottom edge and perform one step with {p}"),
    "product-operating-cu": ("product", "its working end already doing its job in real use, hands out of frame"),
    "feature-callout-hero": ("still", "the product in the first frame, the camera easing toward its key feature, no other motion"),
    "timelapse-process": ("product", "the slow process it works on unfolding over the shot as a time-lapse"),
    "slowmo-hero-moment": ("product", "the key moment of use in slow motion, fine motion detail visible"),
    "pour-dispense-cu": ("product", "the contents pouring slowly from it into a cup"),
    "hand-enters-pickup": ("hands", "enter from the bottom edge and lift {p} with an easy grip"),
    "product-hero-orbit": ("product", "resting on a clean surface as the camera arcs slowly around it"),
    "hero-static-push-in": ("still", "the product in the first frame on a clean surface, the camera easing in, no other motion"),
    "flat-lay-reveal": ("still", "the flat lay in the first frame, the camera easing in overhead, every object staying still"),
    "lifestyle-context-ws": ("product", "in place where it really lives, the camera sliding slowly past"),
    "establishing-ws": ("place", "in the morning, the camera panning slowly across the room"),
    "rejection-lineup": ("product", "at the end of a row of plain unbranded {category} items, the camera panning along the row toward it"),
    "prop-explainer-cu": ("hands", "hold the prop for the point steady toward the lens"),
    "insert-object-detail": ("object", "in detail, the camera easing toward it"),
    "green-screen-explainer": ("face", "speaks to camera in front of a plain backdrop"),
    "pov-walk-in": ("place", "seen first-person, walking in toward the spot where it happens"),
    "ritual-step-wide": ("face", "does the routine step live, no speech"),
    "low-angle-hero-payoff": ("face", "holds {result} toward the lens, face in the upper third, no speech"),
    "end-card-hero": ("still", "the product in the first frame with clear empty space above it, the camera easing in, no other motion"),
    "loop-return-frame": ("still", "the opening composition in the first frame, the camera easing back and settling on it"),
    "whip-pan-transition": ("place", "a fast whip pan landing on {subject}, motion blur"),
    "speed-ramp-reveal": ("product", "the finished result coming into view as the push-in slows sharply"),
    "lens-cover-transition": ("hands", "move a palm toward the lens until the frame goes dark"),
    "vo-over-hands-broll": ("hands", "rest on and gently touch {p}, no speech"),
}
# a to-camera type with no line under it keeps its mouth closed
QUIET = {"talking-head-mcu": "looks into the lens, listening, no speech",
         "talking-head-product-in-hand": "holds {p} at chin height, front toward the camera, looking into the lens, no speech",
         "selfie-walk-talk": "walks slowly toward the camera holding the phone at arm's length, smiling at the lens, no speech",
         "mws-cta-to-camera": "stands beside {p}, looking into the lens, no speech",
         "green-screen-explainer": "stands in front of a plain backdrop, looking into the lens, no speech"}
# a plain backdrop replaces the set (the real image is composited later)
NO_SETTING = ("green-screen-explainer",)
# first-frame photo per image-to-video type (all real photos)
STILL_REF = {"label-detail-ecu": "label_photo", "flat-lay-reveal": "flatlay_photo"}
# named light sources (§5 realism cue): a location-bound light first (car,
# golden hour, outdoors), then the vibe's look (its practicals are the niche's
# own lamp), then the niche light
PLACE_LIGHTS = ((r"windshield", "soft daylight through the windshield"),
                (r"golden[- ]hour", "low golden-hour sun"))
PRACTICALS = ((r"bedside[- ]lamp", "a warm bedside lamp"), (r"desk lamp", "a warm desk lamp"))
LOOK_LIGHTS = ((r"ring[- ]light", "a ring light in front"), (r"string lights", "warm string lights"),
               (r"candle", "warm candle-like lamps"), (r"window", "soft window light from one side"),
               (r"softbox", "a large soft key from one side"),
               (r"rim light|back light|hard side", "a hard side light"),
               (r"side light", "a soft side light"),
               (r"daylight|available light", "soft natural daylight"))
NICHE_LIGHTS = PRACTICALS + ((r"window", "soft window light from one side"),
                             (r"bright daylight", "bright daylight from a window"),
                             (r"daylight", "soft natural daylight"),
                             (r"indoor light", "a warm ceiling light"))
_OUTDOOR = re.compile(r"(?i)\b(?:garden|campsite|outdoors?|backyard|park|street|beach|trail|"
                      r"balcony|clearing|patio)\b")
DEFAULT_LIGHT = "soft window light from one side"
_EDIT_SFX = re.compile(r"(?i)whoosh|riser|\bpop\b|swipe|thump|click|ticking bed")
_QUOTE = re.compile("[\"\u201c\u201d\u201e\u201f\u00ab\u00bb\u2018\u201a\u201b]")
_BAD_APOS = re.compile(r"(?<![A-Za-z])'|'(?![A-Za-z])")
_META = re.compile(r"(?i)\bplaybook\b|\bdossier\b|\bcharter\b|\brubric\b|render exactly|"
                   r"\u00a7|\bgate[ -]?\d\b|\bpalette\b|#[0-9a-f]{6}\b|negative prompt|"
                   r"warped faces|plastic cgi skin|stock-photo stiffness")
_RULE_ID = re.compile(r"\b(?:[DF]\d{1,3}[a-c]?|B4a|[ABCEGQR]\d{1,2})\b")
_BRACKETS = re.compile(r"\s*(?:\([^()]*\)|\[[^\[\]]*\])")


# ------------------------------------------------------------------ text
def _flat(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _clean(text, meta=False):
    """Prompt-safe text: no bracketed stage directions or quote marks
    (contractions keep a straight apostrophe). meta=True also strips rule
    ids and rulebook words (the maker's delivery notes carry them)."""
    t = _BRACKETS.sub("", _flat(text))
    t = t.replace("\u2019", "'")
    t = _QUOTE.sub("", t)
    t = _BAD_APOS.sub("", t)
    if meta:
        t = _RULE_ID.sub("", t)
        t = re.sub(r"(?i)\b(?:playbook|dossier|charter|rubric)\b", "", t)
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s+([.,;:!?])", r"\1", t)
    t = re.sub(r"([.,;:])(?:\s*[.,;:])+", r"\1", t)
    return t.strip(" ,;")


def _sentence(text):
    t = _clean(text).rstrip(" ,;:")
    return (t[:1].upper() + t[1:] + ("" if t.endswith((".", "!", "?")) else ".")) if t else ""


def _cap(t):
    return t[:1].upper() + t[1:] if t else t


def _beat(sh):
    return str(sh.get("beat") or "").replace(" (cont.)", "")


def _ms():
    """make_shotlist (repo root), imported lazily."""
    import importlib
    return importlib.import_module("make_shotlist")


def _lib(tid):
    return SP.data()["BY_ID"].get(tid) or {}


def _sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False)
                          .encode("utf-8")).hexdigest()


def script_sha256(script):
    """sha256 of script.json exactly as pipeline stage 4 writes it
    (json.dump indent=1, ensure_ascii=False, no trailing newline)."""
    return hashlib.sha256(json.dumps(script, indent=1, ensure_ascii=False)
                          .encode("utf-8")).hexdigest()


def _slug(script, shots, slug):
    if slug:
        return str(slug)
    if isinstance(shots, dict) and shots.get("slug"):
        return str(shots["slug"])
    return _ms().slugify(script.get("prompt"))


def _direction(script):
    d = script.get("direction")
    return d if isinstance(d, dict) else {}


def _gender(identity):
    if re.search(r"(?i)\b(?:woman|female|girl|lady)\b", identity or ""):
        return "feminine"
    if re.search(r"(?i)\b(?:man|male|guy)\b", identity or ""):
        return "masculine"
    return None


def _age(identity):
    m = re.search(r"(?i)\bin (?:his|her|their) ((?:early|mid|late)[- ]?\d0s)\b", identity or "")
    return m.group(1) if m else None


# ------------------------------------------------------------ shot rows
def _times(sh):
    """The shot list's own rounded times (the bundle headings = shots.json)."""
    for a, b in (("s", "e"), ("start_s", "end_s")):
        if sh.get(a) is not None and sh.get(b) is not None:
            try:
                return float(f"{float(sh[a]):.1f}"), float(f"{float(sh[b]):.1f}")
            except (TypeError, ValueError):
                pass
    m = re.findall(r"(\d+(?:\.\d+)?)", str(sh.get("t") or ""))
    if len(m) >= 2:
        return float(f"{float(m[0]):.1f}"), float(f"{float(m[1]):.1f}")
    return 0.0, 0.0


def _rows(script, shots):
    """shots.json dict | shot list (in-process s/e or shots.json start_s/end_s)
    | None (built here) -> shot dicts with rounded s/e."""
    if shots is None:
        shots, _ = _ms().build_shots(script)
    if isinstance(shots, dict):
        shots = shots.get("shots") or []
    out = []
    for sh in shots or []:
        if isinstance(sh, dict):
            row = dict(sh)
            row["s"], row["e"] = _times(sh)
            out.append(row)
    return out


def _groups(rows):
    """Beat groups (sub-shots merged) in timeline order."""
    out, idx = [], {}
    for sh in rows:
        key = str(sh.get("group", sh.get("n")))
        if key not in idx:
            idx[key] = len(out)
            out.append({"g": key, "beat": _beat(sh), "s": sh["s"], "e": sh["e"],
                        "dialogue": "", "delivery": "", "rehook": "", "shots": []})
        grp = out[idx[key]]
        grp["s"], grp["e"] = min(grp["s"], sh["s"]), max(grp["e"], sh["e"])
        grp["shots"].append(str(sh.get("n")))
        if sh.get("dialogue") and not grp["dialogue"]:
            grp["dialogue"] = _flat(sh["dialogue"])
            grp["delivery"] = _flat(sh.get("delivery"))
        if sh.get("rehook"):
            grp["rehook"] = _flat(sh["rehook"])
    return sorted(out, key=lambda x: (x["s"], x["e"]))


# -------------------------------------------------------------- context
def _named_light(look_lighting, niche_light, setting=""):
    """One named light source for every prompt of the run."""
    look, niche = look_lighting or "", niche_light or ""
    for pat, name in PLACE_LIGHTS:
        if re.search(pat, niche, re.I):
            return name
    if _OUTDOOR.search(setting or ""):
        return "soft natural daylight"
    if re.search(r"(?i)practical", look):
        for pat, name in PRACTICALS:
            if re.search(pat, niche, re.I):
                return name
    for table, text in ((LOOK_LIGHTS, look), (NICHE_LIGHTS, niche)):
        for pat, name in table:
            if re.search(pat, text, re.I):
                return name
    return DEFAULT_LIGHT


def _product_text(ms, script, is_product):
    """The product block as a prompt subject (no quotes, no meta)."""
    if not is_product:
        return None
    desc = ms.product_description(script)
    if ms._concept(script.get("prompt") or "") == "showcase":
        m = re.match(r"(?i)the (.+?) featured in the video", desc)
        what = m.group(1) if m else "finds"
        return (f"one of the {what} featured in the video, plain and unbranded, true to its "
                "real-world shape, size and materials")
    m = re.match(r"(?i)the (.+?) exactly as named\b", desc)
    if m:
        return (f"the {m.group(1)}, plain and unbranded, with its real-world shape, "
                f"size, materials and colours")
    return _clean(re.sub(r"\s+\u2014\s+", ", ", desc))


def _np(phrase):
    """A maker subject as a noun phrase: no ', ... at its worst' tail, and an
    article when it has none ('coffee cup mid-pour' -> 'the coffee cup ...')."""
    t = re.sub(r",[^,]*\bat its worst\b.*$", "", _clean(phrase)).strip(" ,")
    t = re.sub(r"\s*\bat its worst\b", "", t).strip(" ,") or _clean(phrase)
    if not re.match(r"(?i)(?:a|an|the|my|your|this|these|those|every|each|one|\d)\b", t):
        t = "the " + t
    return t


def context(script, voice_lane=None, ai_broll=False):
    """Everything omni_prompt needs, computed once per run."""
    ms = _ms()
    prompt = script.get("prompt") or ""
    concept = ms._concept(prompt)
    short = ms.product_phrase(prompt)
    c = SP.build_ctx(script, None, {"concept": concept, "product_short": short})
    identity = ms.presenter_identity(script)
    setting, niche_light = ms.niche_setting(script)
    d = _direction(script)
    look = d.get("look") if isinstance(d.get("look"), dict) else {}
    m = re.search(r"(?i)\bwearing (?:a |an )?(.+)$", identity or "")
    outfit = m.group(1).strip(" .") if m else ""
    is_product = c["concept"] in ("product", "showcase")
    tone = ((d.get("tone") or {}).get("voice") if isinstance(d.get("tone"), dict)
            else None) or "warm"
    g = _gender(identity)
    return {
        "lane": c["lane"], "concept": c["concept"], "is_product": is_product,
        "vibe": c["vibe"], "identity": _clean(identity),
        "hands": (f"the presenter's hands, the sleeve of the {outfit} just in frame"
                  if outfit else "the presenter's hands"),
        "product": _product_text(ms, script, is_product),
        "p": _np(c["subject"]), "subject": _np(c["subject"]),
        "result": _clean(c["result"]), "problem": _np(c["problem"]),
        "category": _clean(short or "product"),
        "setting": _clean(setting),
        "light": _named_light(look.get("lighting"), niche_light, setting),
        # F133 / vsp.direction: no faked handheld shake on an AI-persona
        # render (detectable synthetic flaws drive eeriness); faceless AI
        # B-roll in a human creator's video may match the phone footage
        "shake": c["vibe"] in UGC_VIBES and c["lane"] != "ai",
        "voice_tpl": ("in {a} {tone}, conversational "
                      f"{({'feminine': 'female', 'masculine': 'male'}).get(g, 'natural')} voice"),
        "tone": tone,
        "ai_broll": bool(ai_broll), "voice_lane": voice_lane, "outfit": outfit,
        "gender": g, "age": _age(identity),
    }


# ----------------------------------------------------------- the prompt
def _cine(shot):
    s = SP.SCALE_WORDS.get(shot.get("scale"), "medium shot")
    a = SP.ANGLE_WORDS.get(shot.get("angle"), "eye level")
    mv = MOVE_PROMPT.get(shot.get("move"), "static camera")
    return f"{_cap(s)}, {a}, {mv}"


def _images(inputs):
    """ref id -> image number (1-based, order of first appearance)."""
    out = {}
    for it in inputs or []:
        if it.get("ref") not in out:
            out[it["ref"]] = len(out) + 1
    return out


def _header(inputs, images):
    src = " ".join(f"{it['tag']}@Image{images[it['ref']]}" for it in inputs or []
                   if it.get("tag") in TAGS)
    ref = " ".join(f"{it['tag']}@Image{images[it['ref']]}" for it in inputs or []
                   if str(it.get("tag", "")).startswith("<IMAGE_REF_"))
    return " ".join(x for x in ((f"[# Sources {src}]" if src else ""),
                                (f"[# References {ref}]" if ref else "")) if x)


def _tag_of(inputs, ref):
    for it in inputs or []:
        if it.get("ref") == ref and str(it.get("tag", "")).startswith("<IMAGE_REF_"):
            return " " + it["tag"]
    return ""


def _sound(sfx, lipsync):
    """The ambience Omni should generate under the VO (edit SFX stay out)."""
    s = _clean(sfx)
    if lipsync or not s or _EDIT_SFX.search(s):
        return "quiet room tone"
    s = re.sub(r"(?i)clean voice,?\s*", "", s)
    s = re.sub(r"(?i)\s*under the voice", "", s)
    s = re.sub(r"(?i)^live sound$", "live room sound", s.strip(" ,"))
    s = re.sub(r"(?i)\bframe 0\b", "the first frame", s)
    return s.strip(" ,") or "quiet room tone"


def _negatives(needs, tid, lipsync):
    face, hands = "face" in needs, "hands" in needs
    prod = bool({"product", "props"} & set(needs))
    out = []
    if lipsync:
        out.append("One speaker only.")
    if face:
        out.append("No face morphing.")
    if hands:
        out.append("Five natural fingers on each hand, no fused fingers.")
    if tid == "label-detail-ecu":
        out.append("No invented or changed label text.")
    elif prod:
        out.append("No invented logo or label text.")
    if not face and hands:
        out.append("No face in frame.")
    elif not face and not hands and prod:
        out.append("No hands or people in frame.")
    elif not face and not hands:
        out += ["No people in frame.", "No readable signs or labels."]
    if face:
        out.append("No extra people in frame.")
    seen = []
    for x in out:
        if x not in seen:
            seen.append(x)
    return seen[:4]


def _closing(inputs, images, needs):
    """One closing sentence per input image stating its role."""
    tags = {}
    for it in inputs or []:
        tags.setdefault(it["ref"], []).append(it["tag"])
    out = []
    for ref, k in sorted(images.items(), key=lambda x: x[1]):
        t = tags.get(ref) or []
        if "<FIRST_FRAME>" in t and "<LAST_FRAME>" in t:
            out.append(f"Use Image{k} as the first frame and the last frame.")
        elif "<FIRST_FRAME>" in t:
            out.append(f"Use Image{k} as the starting frame" +
                       ("; keep the real product and label exactly as photographed."
                        if ref != "frame0" else "."))
        elif ref == "presenter_sheet" and "face" in needs:
            out.append(f"Use Image{k} as the presenter reference: the same face, hair "
                       "and outfit, not a literal first frame.")
        elif ref == "presenter_sheet":
            out.append(f"Use Image{k} only as the reference for skin tone and the sleeve, "
                       "keep the face out of frame, not a literal first frame.")
        elif ref == "set_plate":
            out.append(f"Use Image{k} as the set reference for the room and its light, "
                       "not a literal first frame.")
        elif ref == "product_front":
            out.append(f"Use Image{k} as the product reference: the same shape, colour, "
                       "size and finish, not a literal first frame.")
        else:
            out.append(f"Use Image{k} as another product reference angle, not a "
                       "literal first frame.")
    return out


def _voice_desc(ctx, tone=None):
    tone = tone or ctx.get("tone") or "warm"
    return ctx["voice_tpl"].format(a="an" if tone[:1] in "aeiou" else "a", tone=tone)


def _action(tid, shot, ctx):
    """(kind, action text) for the shot type; slots filled, prompt-safe."""
    kind, act = ACTIONS.get(tid) or ("product" if ctx.get("product") else "place",
                                     "in view, the camera easing in")
    lip = (shot.get("lipsync") or {}).get("required")
    if tid in QUIET and not lip:
        act = QUIET[tid]
    vals = {"p": ctx["p"], "result": ctx["result"], "subject": ctx["subject"],
            "category": ctx["category"]}
    if kind in ("product", "object") and not ctx.get("product"):
        kind = "object"
    return kind, _clean(act.format(**vals))


def omni_prompt(shot, ctx):
    """The research §6.2 template, one string: [sources/references header]
    {scale}, {angle}, {one move}: {subject} {one action, already in motion}
    in {setting}, lit by {named light}. Vertical 9:16 smartphone footage
    [, handheld with natural micro-shake]. Single continuous shot, no scene
    cuts. Sound: {ambience}. {No dialogue, no voiceover. | The presenter,
    <voice>, says: <line>. Delivery: <delivery>.} No music. No on-screen
    text, captions, subtitles, logos or watermarks. {2-4 negatives}.
    {one closing sentence per input image}."""
    tid = shot.get("shot_type") or ""
    inputs = shot.get("inputs") or []
    images = _images(inputs)
    needs = list(shot.get("needs") or [])
    lip = shot.get("lipsync") or {}
    kind, act = _action(tid, shot, ctx)
    i2v = shot.get("task") == "image_to_video"
    first = any(it.get("tag") == "<FIRST_FRAME>" and it.get("ref") == "frame0"
                for it in inputs)
    if kind == "still":
        subject, joiner = "", ""
    elif i2v and first:
        subject = {"face": "the presenter in the first frame",
                   "hands": "the presenter's hands in the first frame"}.get(
            kind, f"{ctx['p']} in the first frame")
        joiner = " " if kind in ("face", "hands") else ", "
    elif kind == "face":
        subject, joiner = ctx["identity"] + _tag_of(inputs, "presenter_sheet"), " "
    elif kind == "hands":
        subject, joiner = ctx["hands"], ", "
    elif kind == "product":
        subject, joiner = ctx["product"] + _tag_of(inputs, "product_front"), ", "
    elif kind == "object":
        subject, joiner = ctx["subject"], ", "
    elif kind == "scene":
        subject, joiner = ctx["problem"], " "
    else:
        subject, joiner = ctx["setting"], ", "
    body = f"{_cine(shot)}: {subject}{joiner}{act}" if subject else f"{_cine(shot)}: {act}"
    if not i2v:
        if kind == "place" or tid in NO_SETTING:
            body += f", lit by {ctx['light']}"
        else:
            prep = "at" if re.search(r"\b(?:counter|desk|vanity|workbench|table)\b",
                                     ctx["setting"]) else "in"
            body += f"{',' if ',' in act else ''} {prep} {ctx['setting']}, lit by {ctx['light']}"
    parts = [_sentence(body)]
    shake = ctx.get("shake") and shot.get("move") != "static"
    parts.append("Vertical 9:16 smartphone footage" +
                 (", handheld with natural micro-shake." if shake else "."))
    parts.append("Single continuous shot, no scene cuts.")
    parts.append(_sentence("Sound: " + _sound(shot.get("sfx"), lip.get("required"))))
    if lip.get("required") and shot.get("dialogue"):
        line = _clean(shot["dialogue"]).rstrip(" ,;:")
        if not line.endswith((".", "!", "?")):
            line += "."
        deliv = _clean(lip.get("delivery") or "natural and conversational",
                       meta=True).rstrip(".")
        voice = _voice_desc(ctx, lip.get("tone"))
        parts.append(f"The presenter, {voice}, says: {line} "
                     f"Delivery: {deliv[:1].lower() + deliv[1:]}.")
    else:
        parts.append("No dialogue, no voiceover.")
    parts.append("No music.")
    parts.append("No on-screen text, captions, subtitles, logos or watermarks.")
    parts += _negatives(needs, tid, lip.get("required"))
    parts += _closing(inputs, images, needs)
    hdr = _header(inputs, images)
    text = " ".join(p for p in ([hdr] if hdr else []) + parts if p)
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------- lanes
def _lane(script, voice_lane, consent_ref):
    """-> (presenter "ai"|"human", voice lane). Raises ValueError on a lane
    the presenter cannot use or a clone without a consent record."""
    presenter = "ai" if script.get("presenter") == "ai" else "human"
    lane = voice_lane or ("ai_persona" if presenter == "ai" else "real_voice")
    if lane not in LANES:
        raise ValueError(f"unknown voice_lane {lane!r} (one of {', '.join(LANES)})")
    if lane == "creator_clone" and not str(consent_ref or "").strip():
        raise ValueError("voice_lane 'creator_clone' needs consent_ref: the id of the "
                         "creator's signed consent record for this voice clone")
    if presenter == "ai" and lane != "ai_persona":
        raise ValueError("presenter=ai speaks only in the ai_persona lane (a disclosed, "
                         "licensed synthetic voice)")
    if presenter == "human" and lane == "ai_persona":
        raise ValueError("ai_persona is the AI-presenter lane; a human presenter uses "
                         "real_voice or creator_clone")
    return presenter, lane


# ----------------------------------------------------------- transcripts
_WORD = re.compile(r"[A-Za-z0-9]+(?:['\u2019][A-Za-z]+)?")
_EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2190-\u21FF\u2B00-\u2BFF"
                    "\u27F0-\u27FF\u2900-\u297F\uFE0F\u200D\u00B7\u2022\u2192]")
_FIRST_PERSON = re.compile(r"\bI\b|\bI['\u2019](?:m|ve|d|ll)\b|\b[Mm](?:e|y|ine|yself)\b")
_SERIOUS = re.compile(r"(?i)[$\u20ac\u00a3]\s?\d|\d\s?%|\bpercent\b|\bguarantee\w*|"
                      r"\bwarrant\w*|\brefund\w*|\bprice\w*|\bcosts?\b")


def comment_word(script):
    """The CTA keyword (discovery.comment_word, else 'comment WORD' in the copy)."""
    disc = script.get("discovery") if isinstance(script.get("discovery"), dict) else {}
    if disc.get("comment_word"):
        return str(disc["comment_word"]).strip()
    for it in list(script.get("beats") or []) + list(script.get("hook_stack") or []):
        m = re.search(r"\b[Cc]omment\s+([A-Z][A-Z0-9]+)\b",
                      str((it or {}).get("dialogue") or "") if isinstance(it, dict) else "")
        if m:
            return m.group(1)
    return None


def transcript_of(display, keyword=None):
    """§7.4 hygiene: the Cartesia transcript for a caption line (display
    stays the caption text). Lower-cases the comment keyword and other
    ALL-CAPS words (initialisms such as LED stay), strips emoji, arrows,
    '·', hashtags, parentheses and bracketed directions, writes ranges with
    'to', keeps the maker's punctuation and ends on . ? or !."""
    t = _flat(display)
    t = re.sub(r"\[[^\[\]]*\]", " ", t)
    t = re.sub(r"#\w+", " ", t)
    t = _EMOJI.sub(" ", t)
    t = t.replace("(", " ").replace(")", " ")
    t = re.sub(r"\$(\d+(?:\.\d+)?)\s*[-\u2013\u2014]\s*\$?(\d+(?:\.\d+)?)", r"\1 to \2 dollars", t)
    t = re.sub(r"(\d+(?:\.\d+)?)\s*[-\u2013]\s*(\d+(?:\.\d+)?)", r"\1 to \2", t)
    kw = str(keyword or "").strip().upper()

    def caps(m):
        w = m.group(0)
        if w == kw and w not in INITIALISMS:
            return w.lower()
        if w in INITIALISMS or len(w) <= 2 or not re.search(r"[AEIOUY]", w):
            return w
        return w.lower()
    t = re.sub(r"\b[A-Z][A-Z0-9-]*[A-Z0-9]\b", caps, t)
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s+([.,;:!?])", r"\1", t)
    t = re.sub(r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), t)
    if t and not t.endswith((".", "?", "!")):
        t = t.rstrip(" ,;:\u2014-") + "."
    return t


def strip_tags(text):
    return re.sub(r"\s+", " ", INLINE_TAG_RE.sub(" ", str(text or ""))).strip()


def speech_words(text):
    """Word list for display/transcript equality (case and punctuation
    ignored; the same normalisation-safe rewrites applied to both)."""
    return [w.lower().replace("\u2019", "'") for w in _WORD.findall(transcript_of(strip_tags(text)))]


# ------------------------------------------------------------ voice lines
def _curve_at(curve, grp, used):
    """(energy, floor wpm) of the direction energy_curve row for a group."""
    best = None
    for k, row in enumerate(curve):
        if row.get("type") != grp["beat"] or k in used:
            continue
        s, _ = TM.parse_window(row.get("t"))
        dist = abs((s if s is not None else 0.0) - grp["s"])
        if best is None or dist < best[0]:
            best = (dist, k)
    floor = 60.0 * TM.wps(grp["delivery"])
    if best is None:
        return 3, floor
    used.add(best[1])
    row = curve[best[1]]
    try:
        energy = int(row.get("energy") or 3)
    except (TypeError, ValueError):
        energy = 3
    return max(1, min(5, energy)), float(row.get("wpm") or floor)


def _vibe_allows_excited(vibe):
    try:
        from vsp import direction as DR
        prof = (DR.data().get("VIBE_PROFILES") or {}).get(vibe) or {}
        return "excited" in ((prof.get("tone") or {}).get("allowed") or [])
    except Exception:  # noqa: BLE001 — direction data is optional here
        return False


def _tone_for(ln, base, allowed, excited_ok, post_peak, is_ai):
    beat, role, text = ln["beat"], ln["role"], ln["display"]
    if _SERIOUS.search(text):
        want = "serious"
    elif beat == "PAYOFF" and role == "dialogue":
        want = "excited" if excited_ok else "confident"
    elif post_peak:
        want = "warm"
    elif role == "rehook":
        want = "curious"
    elif beat == "VERBAL HOOK + LOCK":
        want = "confident"
    elif beat == "COMMENT BAIT":
        want = "playful"
    elif beat in ("EDUCATION BEAT", "TEACHING BEAT", "EVIDENCE BEAT"):
        want = "expert"
    elif beat == "IMPERFECTION BEAT" and not is_ai:
        want = "empathetic"
    else:
        want = base
    ok = set(allowed) | {base, "curious", "serious"}
    if want == "excited" and excited_ok:
        ok.add("excited")
    return want if want in ok else base


def _target_wpm(floor, tone, delivery):
    if any(k in (delivery or "").lower() for k in LX.SLOW_KEYS):
        return int(round(floor))
    lo, hi = TONES[tone][0]
    return int(round(min(WPM_CAP, max(floor, (lo + hi) / 2.0))))


def speed_for(target, calibration=None):
    """Cartesia speed for a target wpm: the voice's calibration (speed ->
    measured wpm) interpolated, else WPM_AT_1 x speed; clamped to the house
    range 0.9-1.15 and snapped to 1.0 within +/-0.05."""
    pts = sorted((float(k), float(v)) for k, v in (calibration or {}).items()
                 if v not in (None, "") and float(v) > 0)
    if len(pts) < 2:
        pts = [(0.9, 0.9 * WPM_AT_1), (1.2, 1.2 * WPM_AT_1)]
    sp = None
    for (s0, w0), (s1, w1) in zip(pts, pts[1:]):
        if w0 <= target <= w1 and w1 > w0:
            sp = s0 + (s1 - s0) * (target - w0) / (w1 - w0)
            break
    if sp is None:
        (s0, w0), (s1, w1) = (pts[0], pts[1]) if target < pts[0][1] else (pts[-2], pts[-1])
        sp = s0 + (s1 - s0) * (target - w0) / (w1 - w0) if w1 != w0 else 1.0
    sp = min(SPEED_HOUSE[1], max(SPEED_HOUSE[0], sp))
    return 1.0 if abs(sp - 1.0) <= 0.05 + 1e-9 else round(sp, 2)


def _voice_lines(script, rows):
    """Spoken lines (dialogue, then rehook, per beat group) in timeline order
    with tone, energy, wpm and the placement estimated at the target wpm."""
    d = _direction(script)
    curve = [x for x in (d.get("energy_curve") or []) if isinstance(x, dict)]
    tone_d = d.get("tone") if isinstance(d.get("tone"), dict) else {}
    base = tone_d.get("voice") if tone_d.get("voice") in TONES else "warm"
    allowed = [t for t in (tone_d.get("allowed") or []) if t in TONES]
    excited_ok = "excited" in allowed or base == "excited" or \
        _vibe_allows_excited(d.get("vibe"))
    hi = (d.get("pacing") or {}).get("target_wpm") if isinstance(d.get("pacing"), dict) else None
    try:
        pace_hi = float(hi[1]) if isinstance(hi, (list, tuple)) and len(hi) >= 2 else WPM_CAP
    except (TypeError, ValueError):
        pace_hi = WPM_CAP
    kw = comment_word(script)
    is_ai = script.get("presenter") == "ai"
    lines, used = [], set()
    for grp in _groups(rows):
        energy, floor = _curve_at(curve, grp, used)
        for role in ("dialogue", "rehook"):
            if grp[role]:
                lines.append({"role": role, "beat": grp["beat"], "g": grp["g"],
                              "window": [grp["s"], grp["e"]], "energy": energy,
                              "floor": floor, "delivery": grp["delivery"],
                              "display": grp[role], "shots": list(grp["shots"])})
    peak = None
    for i, ln in enumerate(lines):
        ln["id"] = f"L{i + 1}"
        if peak is None and ln["beat"] == "PAYOFF" and ln["role"] == "dialogue":
            peak = i
    for i, ln in enumerate(lines):
        post = peak is not None and i == peak + 1
        ln["post_peak"] = post
        ln["tone"] = _tone_for(ln, base, allowed, excited_ok, post, is_ai)
        ln["transcript"] = transcript_of(ln["display"], kw)
        tgt = _target_wpm(ln["floor"], ln["tone"], ln["delivery"])
        ln["wpm"] = {"floor": int(round(ln["floor"])), "target": tgt,
                     "max": int(round(max(tgt, min(WPM_CAP, pace_hi))))}
        n = len(_WORD.findall(ln["transcript"]))
        ln["speech_s"] = round(n / float(tgt) * 60.0, 2) if tgt else 0.0
        s, e = ln["window"]
        if ln["role"] == "dialogue":
            ln["start"] = round(s + ANCHOR_S, 2)
            ln["end"] = round(ln["start"] + ln["speech_s"], 2)
        else:
            ln["end"] = round(e - ANCHOR_S, 2)
            ln["start"] = round(ln["end"] - ln["speech_s"], 2)
    for i, ln in enumerate(lines):
        s, e = ln["window"]
        flags = []
        over = max(ln["end"] - e, s - ln["start"], 0.0)
        if over > 1e-6:
            flags.append(f"about {over:.2f} s past its window at {ln['wpm']['target']} wpm "
                         "(estimate): place it by words.json and let it spill into the next "
                         "lead-in only if that line has slack; else trim words, never "
                         "time-stretch")
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        if nxt is not None and nxt["g"] == ln["g"]:
            gap = nxt["start"] - ln["end"]
            if gap < GAP_S - 1e-6:
                what = (f"overlaps {nxt['id']} by {-gap:.2f} s" if gap < 0 else
                        f"leaves only {gap:.2f} s before {nxt['id']}")
                flags.append(f"{what} at the target wpm (want a {GAP_S:g} s gap): the "
                             "measured take decides; trim words if they still collide")
        ln["fits"] = not flags
        if flags:
            ln["flags"] = flags
    return lines


def _spoken_part(ln, s):
    """What the presenter says natively in a to-camera take that starts at s:
    the whole line when it starts in the shot, else the words still to come
    (uniform word timing). -> (tokens, seconds)."""
    toks = ln["transcript"].split()
    if not toks:
        return [], 0.0
    if ln["start"] >= s - 1e-6:
        return toks, ln["speech_s"]
    step = (ln["end"] - ln["start"]) / len(toks)
    part = [t for k, t in enumerate(toks) if ln["start"] + (k + 0.5) * step >= s - 1e-6]
    return part, round(ln["speech_s"] * len(part) / len(toks), 2)


# ------------------------------------------------------------ routing
_NO_LIP = {"required": False, "line_id": None, "audio_in_s": None, "audio_out_s": None,
           "method": None}


def _ceil(x):
    return int(math.ceil(round(x, 3) - 1e-9))


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _gen_mode(tm):
    return not str(tm or "").startswith(("Not generated", "Edit-only"))


def _mode(sh, L, needs, ctx):
    """-> (mode, real_footage_why)."""
    tid = sh.get("shot_type") or ""
    tm = L.get("ai_prompt") or ""
    if tid == "loop-return-frame":
        return "reuse", None
    if sh.get("real_footage"):
        return "real", (sh.get("real_footage_why") or
                        "proof shot: only real footage can show the real result")
    if not L:
        return "real", "no shot type in the shot list: film it"
    if tm.startswith("Edit-only"):
        return "edit", None
    if tm.startswith("Not generated"):
        why = re.sub(r"(?i)^not generated:\s*", "", tm).rstrip(".")
        return "real", f"not generatable: {why}"
    if ctx["lane"] == "ai":
        return "ai", None
    if {"face", "hands"} & set(needs):
        return "real", "human presenter: the creator films every shot with a face or hands"
    if ctx["ai_broll"]:
        return "ai", None
    return "real", "human lane without AI B-roll: film this product shot for real"


def _mk_inputs(sources, refs):
    out = [{"tag": t, "ref": r} for t, r in sources]
    out += [{"tag": f"<IMAGE_REF_{k}>", "ref": r} for k, r in enumerate(refs)]
    return out


def _route(tid, L, needs, ctx, scale, first=False, reuse=False):
    """-> (task, inputs) for a generated shot."""
    face, hands = "face" in needs, "hands" in needs
    prod = ctx["is_product"] and bool({"product", "props"} & set(needs))
    person = ["presenter_sheet"] if ctx["lane"] == "ai" and (face or hands) else []
    if reuse:
        return "image_to_video", _mk_inputs(
            [("<FIRST_FRAME>", "frame0"), ("<LAST_FRAME>", "frame0")],
            ["product_front"] if prod else [])
    if first:
        return "image_to_video", _mk_inputs(
            [("<FIRST_FRAME>", "frame0")], person + (["product_front"] if prod else []))
    if str(L.get("ai_prompt") or "").startswith("Image-to-video"):
        return "image_to_video", _mk_inputs(
            [("<FIRST_FRAME>", STILL_REF.get(tid, "product_hero"))], [])
    refs = list(person)
    if prod:
        refs.append("product_front")
        if not (face or hands):
            refs.append("product_side")
    if refs and (face or "location" in needs or scale in ("MS", "MWS", "WS")):
        refs.append("set_plate")
    if refs:
        return "reference_to_video", _mk_inputs([], refs)
    return "text_to_video", []


def _lipsync(sh, tid, lines, mode, ctx, planned):
    """-> (lipsync dict, spoken text or None, note or None)."""
    capable = "{name} says" in (_lib(tid).get("ai_prompt") or "")
    if not capable or mode not in ("ai", "real"):
        return dict(_NO_LIP), None, None
    s, e = sh["s"], sh["e"]
    hits = [(ln, max(ln["start"], s), min(ln["end"], e)) for ln in lines
            if min(ln["end"], e) - max(ln["start"], s) > 0.25]
    if not hits:
        return dict(_NO_LIP), None, None
    seg_in = min(a for _, a, _ in hits)
    seg_out = max(b for _, _, b in hits)
    words, seg = [], 0.0
    for ln, _, _ in hits:
        part, secs = _spoken_part(ln, s)
        words += part
        seg += secs
    text = " ".join(words).strip()
    info = {"required": False, "line_id": hits[0][0]["id"], "audio_in_s": round(seg_in, 2),
            "audio_out_s": round(seg_out, 2), "method": None,
            "clip_in_s": round(WINDOW_IN_S + seg_in - s, 2)}
    if len(hits) > 1:
        info["line_ids"] = [h[0]["id"] for h in hits]
    note = None
    if mode == "ai":
        if text and seg <= LIPSYNC_LINE_MAX_S + 1e-9 and \
                planned + WINDOW_IN_S <= LIPSYNC_CLIP_MAX + 1e-9:
            info.update(required=True, method="native-then-lipsync-pass")
        else:
            note = (f"{info['line_id']} runs {seg:.1f} s over a to-camera take (lip-sync "
                    f"limit {LIPSYNC_LINE_MAX_S:g} s): split the line or use the ai_fallback")
    elif ctx.get("voice_lane") == "creator_clone" and text:
        info.update(required=True, method="creator-take-then-lipsync-pass")
    if info["required"]:
        info["speech_s"] = round(seg, 2)
        info["tone"] = hits[0][0]["tone"]
        info["delivery"] = _clean(hits[0][0]["delivery"], meta=True) or None
        return info, text, note
    return info, None, note


def _fallback_type(tid, ctx):
    """First generatable ai_fallback down the chain (never a proof type, never
    a face or hands type in the human lane), else text-card-over-motion."""
    seen, nxt = {tid}, _lib(tid).get("ai_fallback")
    while nxt and nxt not in seen:
        seen.add(nxt)
        L = _lib(nxt)
        ok = bool(L) and _gen_mode(L.get("ai_prompt")) and nxt not in SP.PROOF_ALWAYS \
            and nxt != "loop-return-frame"
        if ok and ctx["lane"] != "ai" and {"face", "hands"} & set(L.get("needs") or []):
            ok = False
        if ok:
            return nxt
        nxt = L.get("ai_fallback")
    return "text-card-over-motion" if tid != "text-card-over-motion" else "hero-static-push-in"


def _fallback(shot, row, ctx, lines, planned):
    fb = _fallback_type(shot["shot_type"], ctx)
    L = _lib(fb)
    needs = list(L.get("needs") or [])
    fshot = {"n": shot["n"], "shot_type": fb, "scale": L.get("scale"), "angle": L.get("angle"),
             "move": L.get("move"), "needs": needs, "sfx": SP.SFX.get(fb) or shot.get("sfx"),
             "lipsync": dict(_NO_LIP), "dialogue": None}
    if planned > TM.STATIC_CAP and fshot["move"] == "static":
        fshot["move"] = "push-in"
    lip, text, _ = _lipsync(row, fb, lines, "ai", ctx, planned)
    if lip["required"]:
        fshot["lipsync"], fshot["dialogue"] = lip, text
    fshot["task"], fshot["inputs"] = _route(fb, L, needs, ctx, fshot["scale"])
    gen = (_clamp(_ceil(max(lip["speech_s"], planned) + 1.0), CLIP_MIN, LIPSYNC_CLIP_MAX)
           if lip["required"]
           else _clamp(_ceil(planned + 1.0), CLIP_MIN, CLIP_MAX))
    return {"shot_type": fb, "task": fshot["task"], "gen_duration_s": gen,
            "prompt": omni_prompt(fshot, ctx), "inputs": fshot["inputs"]}


def _qa_ids(mode, needs, lip_required, tid):
    if mode == "edit":
        return ["safe_box"]
    base = ["aspect", "letterbox", "duration", "audio_stream"]
    if mode == "real":
        return base + (["no_text"] if tid != "label-detail-ecu" else []) + ["safe_box"]
    out = base + ["fps", "scene_cuts", "dup_frames"]
    out += ["no_text"] if tid != "label-detail-ecu" else []
    out += ["morphing"]
    if "face" in needs:
        out.append("identity")
    if "hands" in needs:
        out.append("hands")
    if {"product", "props"} & set(needs):
        out.append("product")
    out += ["lipsync_offset"] if lip_required else ["no_speech"]
    return out + ["no_music", "safe_box"]


def _instructions(L, needs, ctx, mode):
    hi = _clean(L.get("human_instructions") or "Film it on a phone at the planned framing.")
    if ctx["lane"] == "ai" and mode == "real" and "hands" in needs and ctx.get("outfit"):
        hi += f" Wear the {ctx['outfit']} so the sleeves match the presenter."
    return hi


def _shot(i, sh, ctx, lines, prior):
    tid = sh.get("shot_type") or ""
    L = _lib(tid)
    needs = list(sh.get("needs") or L.get("needs") or [])
    planned = round(sh["e"] - sh["s"], 2)
    mode, why = _mode(sh, L, needs, ctx)
    generated = mode == "ai"
    notes = []
    if mode == "reuse":
        generated = bool(prior) and prior[0]["mode"] == "ai"
        why = None if generated else "the loop reuses shot 1's real frame-0 footage"
    if ctx["lane"] == "ai" and mode == "real" and "face" in needs:
        notes.append("a synthetic presenter's face cannot be filmed: use the ai_fallback")
    lip, spoken, note = _lipsync(sh, tid, lines, mode, ctx, planned)
    if note:
        notes.append(note)
    if not generated and "clip_in_s" in lip:
        lip["clip_in_s"] = None
    out = {"n": str(sh.get("n")), "window": [sh["s"], sh["e"]], "planned_s": planned,
           "beat": _beat(sh) + (" (cont.)" if "(cont.)" in str(sh.get("beat")) else ""),
           "shot_type": tid, "scale": sh.get("scale"), "angle": sh.get("angle"),
           "move": sh.get("move"), "purpose": sh.get("purpose"), "needs": needs,
           "real_footage": bool(sh.get("real_footage")), "mode": mode}
    if mode == "reuse":
        out["reuse_of"] = prior[0]["n"] if prior else None
    task, inputs, gen, w_in, w_out = None, [], None, None, None
    if generated:
        task, inputs = _route(tid, L, needs, ctx, sh.get("scale"), first=(i == 0),
                              reuse=(mode == "reuse"))
        if lip["required"]:
            gen = _clamp(_ceil(max(lip["speech_s"], planned) + 1.0), CLIP_MIN,
                         LIPSYNC_CLIP_MAX)
        else:
            gen = _clamp(_ceil(planned + 1.0), CLIP_MIN, CLIP_MAX)
        w_in, w_out = WINDOW_IN_S, round(WINDOW_IN_S + planned, 2)
    out.update({"task": task, "gen_duration_s": gen, "window_in_s": w_in,
                "window_out_s": w_out, "prompt": None, "inputs": inputs,
                "dialogue": spoken if lip["required"] else None, "lipsync": lip,
                "native_audio": "drop" if lip["required"] else "keep_ambience",
                "overlay_text": _flat(sh.get("on_screen")) or None,
                "sfx": _flat(sh.get("sfx")) or None,
                "qa": _qa_ids("ai" if generated else ("edit" if mode == "edit" else "real"),
                              needs, lip["required"], tid),
                "ai_fallback": None, "human_instructions": None,
                "real_footage_why": why if mode in ("real", "reuse") else None})
    if generated:
        out["prompt"] = omni_prompt(out, ctx)
        out["ai_fallback"] = _fallback(out, sh, ctx, lines, planned)
    else:
        out["human_instructions"] = _instructions(L, needs, ctx, mode)
        if notes and ctx["lane"] == "ai" and mode == "real":
            out["ai_fallback"] = _fallback(out, sh, ctx, lines, planned)
    if notes:
        out["notes"] = notes
    return out


# ------------------------------------------------------------ refs & docs
def _ref(ref_id, ctx, first_shot):
    """One reference-pack entry: where it comes from and how to make it."""
    setting, light = ctx["setting"], ctx["light"]
    real_photo = ("a real photo (never an AI-made product image: logos, labels and "
                  "details get invented)")
    if ref_id == "presenter_sheet":
        return {"kind": "presenter", "synthetic": True, "source": "image model, generated first",
                "how": ("Generate before any video call: a photorealistic reference sheet of the "
                        "synthetic adult presenter (front and three-quarter head-and-shoulders "
                        "views plus one full-length pose, neutral expression, plain light-grey "
                        "background). A fictional adult only: never a real, recognisable or "
                        "under-18 person and never a photo of a real person. Reuse the same "
                        "sheet in every call."),
                "prompt": (f"Photorealistic character reference sheet of a fictional adult: "
                           f"{ctx['identity']}. Front view and three-quarter view, head and "
                           "shoulders, plus one full-length standing pose, neutral relaxed "
                           "expression, plain light-grey background, soft even light, natural "
                           "skin texture, no beauty filter. The person must not resemble any "
                           "real or famous person. No text, no logos.")}
    if ref_id in ("product_front", "product_side"):
        view = "Front" if ref_id == "product_front" else "Three-quarter"
        return {"kind": "product", "synthetic": False, "source": real_photo,
                "how": (f"{view} view of the real product, sharp, even light, plain background, "
                        "the whole product in frame, no hands, real packaging only.")}
    if ref_id == "product_hero":
        return {"kind": "product", "synthetic": False, "source": real_photo,
                "how": (f"The real product in the set ({setting}) as a 9:16 three-quarter "
                        f"close-up on a clean surface, lit by {light}: the first frame of the "
                        "image-to-video hero shots.")}
    if ref_id == "label_photo":
        return {"kind": "product", "synthetic": False, "source": real_photo,
                "how": "A sharp, straight-on 9:16 photo of the real label or spec plate, every line readable."}
    if ref_id == "flatlay_photo":
        return {"kind": "product", "synthetic": False, "source": real_photo,
                "how": "A real 9:16 top-down photo of the product and everything it comes with, laid out in a grid."}
    if ref_id == "set_plate":
        synth = ctx["lane"] == "ai"
        out = {"kind": "set", "synthetic": synth,
               "source": "image model or a photo of the set" if synth else "a photo of the real set",
               "how": (f"An empty 9:16 plate of the set: {setting}, lit by {light}; lived-in, "
                       "no people, no readable text or screens.")}
        if synth:
            out["prompt"] = (f"Photorealistic vertical 9:16 phone photo of {setting}, lit by "
                             f"{light}, lived-in and tidy, no people, no readable text, no logos.")
        return out
    # frame0: the opening still for image-to-video (and the loop's first/last frame)
    needs = set(first_shot.get("needs") or [])
    person = bool({"face", "hands"} & needs)
    synth = (person and ctx["lane"] == "ai") or not ctx["is_product"]
    cine = _cine(first_shot)
    still = ", ".join(cine.split(", ")[:2]).lower()
    kind, act = _action(first_shot.get("shot_type") or "", first_shot, ctx)
    subj = {"hands": ctx["hands"], "face": ctx["identity"]}.get(kind) or \
        (ctx["product"] or ctx["subject"])
    out = {"kind": "frame0", "synthetic": synth,
           "source": ("image model from presenter_sheet and the product photos" if synth and person
                      else "image model" if synth else "a real photo in the set (preferred) or an "
                      "image model from product_front and set_plate"),
           "how": (f"The exact opening frame of shot {first_shot.get('n')} ({cine.lower()}), "
                   "already mid-action, 9:16. Shot 1 animates it and the loop ends on it, so "
                   "keep it sharp and well lit; never invent a logo, label or text.")}
    out["prompt"] = _sentence(f"Photorealistic vertical 9:16 phone photo, {still}: "
                              f"{subj}, {act}, in {setting}, lit by {light}") + \
        " The product exactly as in the product photos. No text, no logos."
    return out


def _refs(shots, ctx):
    order, used, req = [], {}, {}
    for sh in shots:
        for src, ins in (("", sh.get("inputs") or []),
                         ("fallback:", ((sh.get("ai_fallback") or {}).get("inputs") or []))):
            for it in ins:
                r = it["ref"]
                if r not in used:
                    order.append(r)
                    used[r] = []
                tag = src + sh["n"]
                if tag not in used[r]:
                    used[r].append(tag)
                req[r] = req.get(r, False) or not src
    first = shots[0] if shots else {}
    out = []
    for r in order:
        e = {"id": r, "path": f"refs/{r}.png"}
        e.update(_ref(r, ctx, first))
        e["required"] = req[r]
        e["used_by"] = used[r]
        out.append(e)
    return out


QA_GATE = (
    {"id": "aspect", "stage": "probe", "check": "display aspect 9:16 within 1% (0.5625)",
     "threshold": {"ratio": 0.5625, "tolerance": 0.01}, "on_fail": "regenerate"},
    {"id": "fps", "stage": "probe", "check": "Omni clips 24 fps; the master 30 fps",
     "threshold": {"clip_fps": 24, "master_fps": 30, "tolerance": 0.5}, "on_fail": "regenerate"},
    {"id": "duration", "stage": "probe", "check": "clip duration >= window_out_s",
     "threshold": {"min_s": "window_out_s"}, "on_fail": "regenerate"},
    {"id": "audio_stream", "stage": "probe", "check": "an audio stream is present",
     "threshold": {"streams": 1}, "on_fail": "regenerate"},
    {"id": "letterbox", "stage": "probe", "check": "no letterbox or pillarbox bars (ffmpeg cropdetect)",
     "threshold": {"max_bar_px": 8}, "on_fail": "regenerate"},
    {"id": "scene_cuts", "stage": "probe", "check": "zero scene cuts inside a single-shot clip",
     "threshold": {"scene_score": 0.4, "max_cuts": 0}, "on_fail": "regenerate"},
    {"id": "dup_frames", "stage": "probe", "check": "duplicate-frame ratio (the 8-12 fps wobble)",
     "threshold": {"max_ratio": 0.2}, "on_fail": "regenerate"},
    {"id": "no_text", "stage": "judge", "check": "no legible text, captions, logos or watermarks "
     "(real-label shots excepted)", "threshold": {"text_regions": 0}, "on_fail": "edit turn, then regenerate"},
    {"id": "identity", "stage": "judge", "check": "the same presenter as the reference sheet: "
     "face, hair, glasses, outfit", "threshold": {"judge_score_min": 4}, "on_fail": "regenerate"},
    {"id": "product", "stage": "judge", "check": "the product matches its photos: shape, colour, "
     "size; no invented logo or label text", "threshold": {"judge_score_min": 4},
     "on_fail": "edit turn, then regenerate"},
    {"id": "hands", "stage": "judge", "check": "five fingers per hand, no fusion, plausible contact "
     "(checked at final resolution)", "threshold": {"judge_score_min": 4}, "on_fail": "fallback"},
    {"id": "morphing", "stage": "judge", "check": "no morphing, melting or detaching parts; objects "
     "stay the same object", "threshold": {"judge_score_min": 4}, "on_fail": "regenerate"},
    {"id": "no_speech", "stage": "audio", "check": "B-roll: no speech (voice-activity detection) "
     "and no music", "threshold": {"speech_s_max": 0.3}, "on_fail": "drop native audio or regenerate"},
    {"id": "no_music", "stage": "audio", "check": "no music in the clip or the master",
     "threshold": {"music": False}, "on_fail": "drop native audio"},
    {"id": "lipsync_offset", "stage": "audio", "check": "lip-sync offset inside the ITU window "
     "after the lip-sync pass", "threshold": {"lead_ms_max": 45, "lag_ms_max": 125},
     "on_fail": "re-run the lip-sync pass"},
    {"id": "safe_box", "stage": "judge", "check": "key action inside x120-888, y288-1248 of "
     "1080x1920", "threshold": {"x": [120, 888], "y": [288, 1248]}, "on_fail": "regenerate"},
    {"id": "log", "stage": "log", "check": "model id, seed, interaction id, cost and verdict "
     "logged per attempt", "threshold": {"file": "render_log.jsonl"}, "on_fail": "fix the log"},
)
QA_IDS = tuple(q["id"] for q in QA_GATE)
_SK = ".agents/skills"


def _workflow(slug, lane, generated, lipsync, real):
    job = f"jobs/{slug}"
    tts = lane in ("ai_persona", "creator_clone")
    steps = [
        ("validate", f"python3 {_SK}/omni-render/scripts/omni_render.py --job {job} --validate", True),
        ("references", "build refs/ from render.json refs[]: presenter sheet first (AI lane, "
         "synthetic adult), real product photos, set plate, frame-0 still", generated > 0),
        ("voice", f"python3 {_SK}/cartesia-voice/scripts/cartesia_vo.py --job {job} -> "
         f"vo/{slug}-vo.wav + {slug}-words.json", tts),
        ("draft", f"python3 {_SK}/omni-render/scripts/omni_render.py --job {job} --pass draft; "
         "then a contact sheet + 360p draft cut as an artifact for human review", generated > 0),
        ("fix", "per failing shot: <= 3 draft attempts; --edit for local fixes (<= 2 turns), "
         "else re-render, then --use-fallback; never drop a beat", generated > 0),
        ("final", f"python3 {_SK}/omni-render/scripts/omni_render.py --job {job} --pass final "
         "(1080p, same inputs and seed)", generated > 0),
        ("lipsync", "lipsync-pass skill on every lipsync.required shot (Cartesia segment by "
         "words.json, +45/-125 ms)", lipsync > 0),
        ("assemble", f"python3 {_SK}/assemble-master/scripts/assemble.py --job {job} "
         f"-> {slug}-master.mp4 (24->30 by frame duplication, -14 LUFS / -1 dBTP, no music)",
         tts or generated > 0),
        ("qa", f"python3 {_SK}/qa-judge/scripts/qa_probe.py --job {job} --pass final "
         "+ the Gemini judge on stills", generated > 0 or tts),
        ("report", "write render_report.json (per shot: attempts, verdicts, cost, files)", True),
        ("deliver", f"{slug}-master.mp4 + {slug}-words.json + clips/ + render_report.json; "
         f"list the {real} shot(s) to film", True),
    ]
    return [{"step": k + 1, "id": sid, "do": do} if on else
            {"step": k + 1, "id": sid, "do": do, "skip": True}
            for k, (sid, do, on) in enumerate(steps)]


def _toggle_on(presenter, lane, ai_visuals, platform):
    if presenter == "ai" or ai_visuals:
        return True
    return lane == "creator_clone" and platform != "youtube_shorts"


def _caption_line(script, presenter, lane, ai_visuals):
    if presenter == "ai":
        m = re.search(r"caption line \"([^\"]+)\"", str(script.get("disclosure") or ""))
        if m:
            return m.group(1)
        for ln in str(script.get("caption") or "").splitlines():
            if LX.has_ai_disclosure_line(ln):
                return ln.strip()
        return "made with an AI persona"
    if ai_visuals:
        return "Some shots in this video are AI-generated."
    if lane == "creator_clone":
        return "Voiceover made with an AI clone of my own voice."
    return None


def _disclosure(script, presenter, lane, generated):
    disc = script.get("discovery") if isinstance(script.get("discovery"), dict) else {}
    plats = disc.get("platforms") if isinstance(disc.get("platforms"), dict) else {}
    ai_visuals = generated > 0
    toggles, notes = {}, []
    for plat, key in PLATFORM_TOGGLES:
        cur = ((plats.get(plat) or {}).get("toggles") or {}) if isinstance(plats.get(plat), dict) else {}
        t = dict(cur) if isinstance(cur, dict) else {}
        want = _toggle_on(presenter, lane, ai_visuals, plat)
        if key in t and bool(t[key]) != want:
            notes.append(f"{plat}: posting.md says {key}={str(bool(t[key])).lower()}; "
                         f"this render needs {key}={str(want).lower()}")
        t[key] = want
        toggles[plat] = t
    ai_gen = presenter == "ai" or ai_visuals or lane == "creator_clone"
    line = _caption_line(script, presenter, lane, ai_visuals)
    if ai_visuals:
        notes += ["SynthID is embedded in every Omni clip: never try to remove it",
                  "check the master with a C2PA reader; re-encoding usually drops the "
                  "manifest, so the platform toggles are the label of record"]
    if presenter == "ai":
        notes.append("paid ads reaching New York need the conspicuous synthetic-performer "
                     "disclosure; the AI persona is never shown as a real person")
    if ai_gen:
        notes.append("never claim or imply that the footage or the voice is human-made")
    return {"ai_generated": ai_gen, "synthid": ai_visuals, "c2pa_check": ai_visuals,
            "platform_toggles": toggles, "caption_line": line,
            "frame0_label": "AI persona" if presenter == "ai" else None,
            "tiktok_shop": presenter != "ai" and lane == "real_voice" and not ai_visuals,
            "notes": notes}


# --------------------------------------------------------- build_render
def build_render(script, shots, slug=None, script_sha=None, voice_lane=None,
                 ai_broll=False, consent_ref=None):
    """render.json for one run (research §6.9 + WS-RENDER fields)."""
    presenter, lane = _lane(script, voice_lane, consent_ref)
    rows = _rows(script, shots)
    ctx = context(script, lane, ai_broll)
    lines = _voice_lines(script, rows)
    slug = _slug(script, shots, slug)
    sha = str(script_sha or script_sha256(script)).lower()
    out_shots = []
    for i, sh in enumerate(rows):
        out_shots.append(_shot(i, sh, ctx, lines, out_shots))
    gen = [s for s in out_shots if s["gen_duration_s"]]
    gen_s = sum(s["gen_duration_s"] for s in gen)
    lips = [s for s in out_shots if s["lipsync"]["required"]]
    draft = round(gen_s * OMNI_PER_S[PASSES["draft"]["resolution"]], 2)
    final = round(gen_s * OMNI_PER_S[PASSES["final"]["resolution"]], 2)
    tts = lane in ("ai_persona", "creator_clone")
    has_vo = bool(lines)
    words = f"{slug}-words.json" if tts and has_vo else None
    vo_file = f"{slug}-vo.wav" if has_vo else None
    counts = {m: sum(1 for s in out_shots if s["mode"] == m) for m in MODES}
    counts.update({"shots": len(out_shots), "generated": len(gen), "generated_s": gen_s,
                   "lipsync": len(lips)})
    lipsync_s = round(sum(s["planned_s"] for s in lips), 2)
    return {
        "schema_version": SCHEMA_VERSION, "slug": slug, "sha8": sha[:8],
        "prompt": script.get("prompt"), "duration_s": script.get("duration_s"),
        "presenter_mode": presenter, "voice_lane": lane,
        "consent_ref": str(consent_ref).strip() if consent_ref else None,
        "ai_broll": bool(ai_broll) if presenter == "human" else False,
        "model": {"id": OMNI_MODEL, "api": "gemini", "endpoint": OMNI_ENDPOINT,
                  "auth_header": "x-goog-api-key", "fallback": OMNI_FALLBACK},
        "format": {"aspect_ratio": "9:16", "source_fps": SOURCE_FPS, "master": dict(MASTER)},
        "passes": {"draft": dict(PASSES["draft"]), "final": dict(PASSES["final"]),
                   "edit_turns_max": EDIT_TURNS_MAX},
        "budget_usd": {"generated_s": gen_s,
                       "per_s": {"draft": OMNI_PER_S["360p"], "final": OMNI_PER_S["1080p"]},
                       "draft": draft, "final": final, "estimate": round(draft + final, 2),
                       "cap": round(draft * PASSES["draft"]["max_attempts"] +
                                    final * PASSES["final"]["max_attempts"], 2),
                       "lipsync_max": round(lipsync_s * 0.133, 2),
                       "note": "Omni output seconds; image inputs (1,120 tokens each) and "
                               "Cartesia credits (about 1 per character) are extra"},
        "seed": (int(sha[:8], 16) % 2147483647) if gen else None,
        "identity": {"presenter_text": ctx["identity"], "synthetic": presenter == "ai",
                     "hands_text": ctx["hands"], "product_text": ctx["product"],
                     "setting": ctx["setting"], "light": ctx["light"],
                     "voice": _voice_desc(ctx)},
        "refs": _refs(out_shots, ctx),
        "audio": {"vo_source": ("cartesia" if tts else "creator") if has_vo else "none",
                  "vo_file": vo_file, "words_json": words, "music": False,
                  "ambience": [{"n": s["n"], "sound": _sound(s["sfx"], s["lipsync"]["required"]),
                                "native_audio": s["native_audio"]} for s in out_shots],
                  "mix": {"integrated_lufs": -14, "true_peak_dbtp": -1, "ambience_db": -12,
                          "music_duck_db": -8},
                  "sync_tolerance_ms": dict(SYNC_TOLERANCE_MS)},
        "counts": counts,
        "shots": out_shots,
        "disclosure": _disclosure(script, presenter, lane, len(gen)),
        "deliverables": {"master": f"{slug}-master.mp4", "words": words, "vo": vo_file,
                         "clips_dir": "clips/", "report": "render_report.json"},
        "qa_gate": [dict(q) for q in QA_GATE],
        "workflow": _workflow(slug, lane, len(gen), len(lips), counts["real"]),
        "trend": None,
    }


# ------------------------------------------------------ build_voice_plan
def _voice_block(lane, ctx, voice_id, consent_ref, lines):
    emotive = lane == "ai_persona" and (not voice_id or voice_id in EMOTIVE_VOICES.values())
    g = ctx.get("gender")
    v = {"id": voice_id or None,
         "source": {"ai_persona": "library", "creator_clone": "ivc",
                    "real_voice": "creator"}[lane],
         "emotive": emotive, "gender": g, "age": ctx.get("age"),
         "style": "conversational, like telling a friend; never an announcer or ad read",
         "consent_ref": str(consent_ref).strip() if consent_ref else None,
         "calibration_wpm": {"0.9": None, "1.0": None, "1.1": None, "1.2": None},
         "speed_basis": f"uncalibrated: assumes {WPM_AT_1} wpm at speed 1.0 until "
                        "cartesia_vo.py --calibrate measures the voice"}
    if lane == "real_voice":
        v.update({"style": "the creator's own voice, recorded on the day; no TTS, no voice "
                  "changer", "calibration_wpm": None, "speed_basis": None, "emotive": False})
        return v
    if not voice_id:
        ids = {ln["beat"]: ln["id"] for ln in reversed(lines) if ln["role"] == "dialogue"}
        aud = [x for x in (ids.get("VERBAL HOOK + LOCK"), ids.get("PAYOFF"),
                           ids.get("CTA") or ids.get("COMMENT BAIT")) if x]
        if lane == "creator_clone":
            v["selection"] = {"how": "the creator's own instant clone (POST /voices/clone, "
                              "10-60 s of a relaxed telling-a-friend read); record the "
                              "voice id with the consent record"}
        else:
            q = "&".join(x for x in ("language=en", f"gender={g}" if g else "",
                                     "q=conversational", "expand[]=preview_file_url") if x)
            v["selection"] = {
                "query": f"GET https://api.cartesia.ai/voices?{q}",
                "then": ["q=casual", "q=friendly", "q=natural"],
                "reject_if_description_has": ["narrator", "announcer", "trailer",
                                              "commercial", "radio"],
                "match": "the presenter's apparent age and gender (identity lock) and a "
                         "US accent (locale en-US)",
                "emotive_shortlist": dict(EMOTIVE_VOICES),
                "emotive_note": "the voices Cartesia lists as most emotive; confirm gender "
                                "and age on GET /voices/{id} before auditioning",
                "audition_lines": aud or [ln["id"] for ln in lines[:3]],
                "accept_wpm_at_1_0": [165, 185], "takes_per_line": 3,
                "lock": "one voice per persona for life; set CARTESIA_VOICE_ID or --voice-id"}
    return v


def _plan_line(ln, lane, emotive, calib=None):
    out = {"id": ln["id"], "beat": ln["beat"], "role": ln["role"], "window": ln["window"],
           "anchor": "start" if ln["role"] == "dialogue" else "end",
           "place_s": [ln["start"], ln["end"]], "display": ln["display"],
           "transcript": ln["transcript"], "tone": ln["tone"], "energy": ln["energy"],
           "wpm": ln["wpm"], "speech_s_est": ln["speech_s"],
           "delivery": _clean(ln["delivery"], meta=True) or None,
           "shots": ln["shots"], "fits": ln["fits"]}
    if ln.get("flags"):
        out["flags"] = list(ln["flags"])
    if lane != "real_voice":
        gc = {"speed": speed_for(ln["wpm"]["target"], calib)}
        vol = 1.0 if ln["post_peak"] else ENERGY_VOLUME.get(ln["energy"], 1.0)
        if vol > 1.05 and ln["beat"] != "PAYOFF":
            vol = 1.05
        gc["volume"] = _clamp(vol, VOLUME_HOUSE[0], VOLUME_HOUSE[1])
        if emotive:
            emo = TONES[ln["tone"]][1]
            if ln["tone"] == "excited" and ln["beat"] != "PAYOFF":
                emo = "enthusiastic"
            gc["emotion"] = emo
            fb = TONES[ln["tone"]][2]
            if fb:
                out["emotion_fallback"] = fb
        out["generation_config"] = gc
    return out


def build_voice_plan(script, shots=None, voice_lane=None, consent_ref=None, voice_id=None):
    """voice_plan.json for one run (voice research §7.1): one entry per
    spoken dialogue and rehook, timeline order. real_voice is a read guide
    (engine null, no generation_config, no words.json)."""
    presenter, lane = _lane(script, voice_lane, consent_ref)
    rows = _rows(script, shots)
    ctx = context(script, lane)
    lines = _voice_lines(script, rows)
    slug = _slug(script, shots, None)
    voice = _voice_block(lane, ctx, voice_id, consent_ref, lines)
    real = lane == "real_voice"
    plan = []
    for i, ln in enumerate(lines):
        pl = _plan_line(ln, lane, voice["emotive"])
        pl["gap_before_s"] = 0.0 if i == 0 else (
            GAP_PRE_PAYOFF_S if ln["beat"] == "PAYOFF" and ln["role"] == "dialogue" else GAP_S)
        pl["gap_after_s"] = 0.0 if i == len(lines) - 1 else (
            GAP_POST_PAYOFF_S if ln["beat"] == "PAYOFF" and ln["role"] == "dialogue" else GAP_S)
        pl["first_person_claim"] = bool(_FIRST_PERSON.search(ln["display"]))
        if lane == "creator_clone":
            pl["creator_approved"] = False
        plan.append(pl)
    chars = sum(len(p["transcript"]) for p in plan)
    disc = {"ai_persona": {"tiktok_is_aigc": True, "instagram_ai_label": True,
                           "youtube_ai_use": True, "caption_line_required": True,
                           "frame0_label": "AI persona", "ny_synthetic_performer": True,
                           "tiktok_shop": False},
            "creator_clone": {"tiktok_is_aigc": True, "instagram_ai_label": True,
                              "youtube_ai_use": "if_visuals_ai",
                              "caption_line_required": True, "tiktok_shop": False},
            "real_voice": {"tiktok_is_aigc": "set_by_visuals",
                           "instagram_ai_label": "set_by_visuals",
                           "youtube_ai_use": "set_by_visuals",
                           "caption_line_required": False, "tiktok_shop": True}}[lane]
    room = re.sub(r"(?i)^(?:a|an|the)\s+", "", ctx["setting"]).split(",")[0].strip()
    return {
        "schema_version": SCHEMA_VERSION, "run": slug, "slug": slug,
        "prompt": script.get("prompt"), "duration_s": script.get("duration_s"),
        "presenter": presenter, "lane": lane, "read_guide": real,
        "engine": None if real else dict(ENGINE, output_format=dict(ENGINE["output_format"])),
        "voice": voice,
        "disclosure": disc,
        "mix": {"integrated_lufs": -14, "true_peak_dbtp": -1, "music_duck_db": -8,
                "music_in_master": False, "room_tone": room,
                "clip_gain_db": "+1 to +2 on the payoff, 0 elsewhere",
                "sample_rate": 48000, "channels": 1},
        "timing": {"anchor_offset_s": ANCHOR_S, "min_gap_s": GAP_S,
                   "gap_before_payoff_s": GAP_PRE_PAYOFF_S,
                   "gap_after_payoff_s": GAP_POST_PAYOFF_S, "trim_head_ms": 40,
                   "trim_tail_ms": 80, "breaks_at_seams": False},
        "qa": {"wpm_fail_above": WPM_FAIL, "wpm_warn_above": WPM_WARN,
               "wpm_warn_below_floor_by": 10, "speed_house": list(SPEED_HOUSE),
               "volume_house": list(VOLUME_HOUSE)},
        "lines": plan,
        "outputs": {"audio": f"{slug}-vo.wav", "words": None if real else f"{slug}-words.json",
                    "line_dir": "vo/"},
        "cost": None if real else {"credits_per_char": 1, "chars": chars,
                                   "credits_per_take": chars},
    }


# --------------------------------------------------------------- checks
TOP_KEYS = ("schema_version", "slug", "sha8", "prompt", "duration_s", "presenter_mode",
            "voice_lane", "consent_ref", "ai_broll", "model", "format", "passes",
            "budget_usd", "seed", "identity", "refs", "audio", "counts", "shots",
            "disclosure", "deliverables", "qa_gate", "workflow", "trend")
SHOT_KEYS = ("n", "window", "planned_s", "beat", "shot_type", "scale", "angle", "move",
             "purpose", "needs", "real_footage", "mode", "task", "gen_duration_s",
             "window_in_s", "window_out_s", "prompt", "inputs", "dialogue", "lipsync",
             "native_audio", "overlay_text", "sfx", "qa", "ai_fallback",
             "human_instructions", "real_footage_why")
PROMPT_MUST = ("Vertical 9:16 smartphone footage", "Single continuous shot, no scene cuts.",
               "Sound: ", "No music.",
               "No on-screen text, captions, subtitles, logos or watermarks.")
NEGATIVE_SET = ("One speaker only.", "No face morphing.",
                "Five natural fingers on each hand, no fused fingers.",
                "No invented logo or label text.", "No invented or changed label text.",
                "No face in frame.", "No hands or people in frame.", "No people in frame.",
                "No readable signs or labels.", "No extra people in frame.")
_HDR_RE = re.compile(r"^((?:\[# (?:Sources|References)(?: <[A-Z_0-9]+>@Image\d+)+\] ?)+)")


def prompt_problems(prompt, allowed_ids=(), lipsync=False):
    """Hygiene of one Omni prompt string -> [problem]."""
    p = str(prompt or "")
    out = []
    if not p.strip():
        return ["empty prompt"]
    m = _HDR_RE.match(p)
    body = p[m.end():] if m else p
    if _QUOTE.search(p) or "\u2019" in p or _BAD_APOS.search(p):
        out.append("quote character in the prompt")
    if _META.search(p):
        out.append(f"meta or forbidden wording: {_META.search(p).group(0)!r}")
    ids = sorted(set(_RULE_ID.findall(body)) - set(allowed_ids))
    if ids:
        out.append(f"rule id in the prompt: {', '.join(ids)}")
    if re.search(r"[\[\]()]", body):
        out.append("bracketed text outside the sources/references header")
    for must in PROMPT_MUST:
        if must not in body:
            out.append(f"missing {must.strip()!r}")
    if lipsync:
        if " says: " not in body or "No dialogue" in body:
            out.append("lip-sync prompt without a 'says:' line")
    elif " says:" in body or "No dialogue, no voiceover." not in body:
        out.append("B-roll prompt carries dialogue (needs 'No dialogue, no voiceover.')")
    n_neg = sum(1 for x in NEGATIVE_SET if x in body)
    if not 2 <= n_neg <= 4:
        out.append(f"{n_neg} shot-specific negatives (want 2-4)")
    for k in sorted(set(re.findall(r"@Image(\d+)", p))):
        if f"Use Image{k} " not in body:
            out.append(f"no closing sentence for Image{k}")
    return out


def _inputs_problems(inputs, task, ref_ids):
    out = []
    tags = [it.get("tag") for it in inputs or []]
    for it in inputs or []:
        t = str(it.get("tag") or "")
        if t not in TAGS and not re.match(r"^<IMAGE_REF_\d+>$", t):
            out.append(f"bad input tag {t!r}")
        if it.get("ref") not in ref_ids:
            out.append(f"input ref {it.get('ref')!r} not in refs[]")
    if "<LAST_FRAME>" in tags and "<FIRST_FRAME>" not in tags:
        out.append("<LAST_FRAME> without <FIRST_FRAME>")
    refs = [t for t in tags if str(t).startswith("<IMAGE_REF_")]
    if refs != [f"<IMAGE_REF_{k}>" for k in range(len(refs))]:
        out.append("IMAGE_REF tags not numbered from 0")
    if len({it.get("ref") for it in inputs or []}) > MAX_IMAGES:
        out.append(f"more than {MAX_IMAGES} images")
    if task == "image_to_video" and "<FIRST_FRAME>" not in tags:
        out.append("image_to_video without a <FIRST_FRAME>")
    if task == "reference_to_video" and (not refs or "<FIRST_FRAME>" in tags):
        out.append("reference_to_video needs references and no first frame")
    if task == "text_to_video" and inputs:
        out.append("text_to_video with image inputs")
    return out


def _check_shot(sh, r, lane_h, ref_ids, allowed):
    P = []
    n = sh.get("n")
    for k in SHOT_KEYS:
        if k not in sh:
            P.append(f"shot {n}: missing {k}")
    if P:
        return P
    mode, task, gen = sh["mode"], sh["task"], sh["gen_duration_s"]
    if mode not in MODES:
        return [f"shot {n}: mode {mode!r}"]
    generated = gen is not None
    if generated != (mode == "ai" or (mode == "reuse" and task is not None)):
        P.append(f"shot {n}: generation does not match mode {mode}")
    lip = sh["lipsync"] or {}
    if not isinstance(lip, dict) or "required" not in lip:
        return P + [f"shot {n}: bad lipsync"]
    if generated:
        if task not in TASKS:
            P.append(f"shot {n}: task {task!r}")
        if not isinstance(gen, int) or isinstance(gen, bool) or not CLIP_MIN <= gen <= CLIP_MAX:
            P.append(f"shot {n}: gen_duration_s {gen!r} is not an integer 3-10")
        elif lip["required"] and gen > LIPSYNC_CLIP_MAX:
            P.append(f"shot {n}: lip-sync clip {gen} s > {LIPSYNC_CLIP_MAX} s")
        if sh["window_in_s"] != WINDOW_IN_S or \
                abs((sh["window_out_s"] or 0) - (WINDOW_IN_S + sh["planned_s"])) > 0.011:
            P.append(f"shot {n}: window_in/out {sh['window_in_s']}/{sh['window_out_s']}")
        elif isinstance(gen, int) and gen + 1e-9 < sh["window_out_s"]:
            P.append(f"shot {n}: clip {gen} s shorter than window_out_s {sh['window_out_s']}")
        P += [f"shot {n}: {x}" for x in prompt_problems(sh["prompt"], allowed, lip["required"])]
        P += [f"shot {n}: {x}" for x in _inputs_problems(sh["inputs"], task, ref_ids)]
        fb = sh["ai_fallback"]
        if not isinstance(fb, dict) or not fb.get("shot_type") or not fb.get("prompt"):
            P.append(f"shot {n}: ai_fallback needs shot_type and prompt")
        else:
            fl = _lib(fb["shot_type"])
            if fb["shot_type"] in SP.PROOF_ALWAYS or not _gen_mode(fl.get("ai_prompt")):
                P.append(f"shot {n}: fallback {fb['shot_type']} is not generatable")
            if lane_h and {"face", "hands"} & set(fl.get("needs") or []):
                P.append(f"shot {n}: human-lane fallback {fb['shot_type']} shows a face or hands")
            P += [f"shot {n} fallback: {x}" for x in
                  prompt_problems(fb["prompt"], allowed, " says: " in fb["prompt"])]
            P += [f"shot {n} fallback: {x}" for x in
                  _inputs_problems(fb.get("inputs"), fb.get("task"), ref_ids)]
    else:
        if task is not None or sh["prompt"] or sh["inputs"]:
            P.append(f"shot {n}: a {mode} shot carries a task, prompt or inputs")
        if not sh["human_instructions"]:
            P.append(f"shot {n}: {mode} shot without human_instructions")
    if lip["required"]:
        seg = float(lip.get("speech_s") or 0.0)
        if not sh["dialogue"]:
            P.append(f"shot {n}: lip-sync shot without dialogue")
        if seg > LIPSYNC_LINE_MAX_S + 1e-9:
            P.append(f"shot {n}: lip-sync line {seg:.1f} s > {LIPSYNC_LINE_MAX_S:g} s")
        if lip.get("method") not in LIPSYNC_METHODS:
            P.append(f"shot {n}: lip-sync method {lip.get('method')!r}")
        if sh["native_audio"] != "drop":
            P.append(f"shot {n}: lip-synced shot keeps Omni audio")
    elif sh["dialogue"]:
        P.append(f"shot {n}: dialogue without a planned lip-sync")
    if sh["native_audio"] not in NATIVE_AUDIO:
        P.append(f"shot {n}: native_audio {sh['native_audio']!r}")
    bad = [q for q in sh["qa"] or [] if q not in QA_IDS]
    if bad:
        P.append(f"shot {n}: unknown qa ids {bad}")
    if lane_h and mode == "ai" and {"face", "hands"} & set(sh["needs"] or []):
        P.append(f"shot {n}: human lane renders a face or hands shot with AI")
    if lane_h and mode == "ai" and not r.get("ai_broll"):
        P.append(f"shot {n}: human lane AI shot without ai_broll")
    return P


def check_render(r, script):
    """Contract and hygiene problems in a render.json dict -> [problem]."""
    if not isinstance(r, dict):
        return ["render.json is not an object"]
    P = [f"missing field {k}" for k in TOP_KEYS if k not in r]
    if P:
        return P
    presenter = "ai" if script.get("presenter") == "ai" else "human"
    lane_h = presenter == "human"
    if r["schema_version"] != SCHEMA_VERSION:
        P.append(f"schema_version {r['schema_version']!r}")
    if r["presenter_mode"] != presenter:
        P.append(f"presenter_mode {r['presenter_mode']!r} != script presenter {presenter}")
    lane = r["voice_lane"]
    if lane not in LANES:
        P.append(f"voice_lane {lane!r}")
    if (presenter == "ai") != (lane == "ai_persona"):
        P.append(f"voice lane {lane} does not fit presenter {presenter}")
    if lane == "creator_clone" and not r["consent_ref"]:
        P.append("creator_clone without consent_ref")
    if (r["model"] or {}).get("id") != OMNI_MODEL:
        P.append("model id is not " + OMNI_MODEL)
    f = r["format"] or {}
    if f.get("aspect_ratio") != "9:16" or f.get("source_fps") != SOURCE_FPS or \
            (f.get("master") or {}).get("fps") != MASTER["fps"]:
        P.append("format must be 9:16, 24 fps source, 30 fps master")
    ps = r["passes"] or {}
    if (ps.get("draft") or {}).get("resolution") != "360p" or \
            (ps.get("final") or {}).get("resolution") != "1080p":
        P.append("passes must be draft 360p / final 1080p")
    slug = r["slug"]
    tts = lane in ("ai_persona", "creator_clone")
    dl = r["deliverables"] or {}
    if dl.get("master") != f"{slug}-master.mp4":
        P.append("deliverables.master must be <slug>-master.mp4")
    words = r["audio"].get("words_json")
    if tts and r["audio"].get("vo_file") and words != f"{slug}-words.json":
        P.append("audio.words_json must be <slug>-words.json (render spec)")
    if not tts and words:
        P.append("real_voice lane exports no words.json (the caption stage aligns)")
    if r["audio"].get("music") is not False:
        P.append("music must stay out of the master")
    shots = r["shots"] or []
    if not shots:
        return P + ["no shots"]
    ref_ids = [x.get("id") for x in r["refs"] or []]
    if len(ref_ids) != len(set(ref_ids)):
        P.append("duplicate ref ids")
    for x in r["refs"] or []:
        if x.get("kind") == "product" and x.get("synthetic"):
            P.append(f"ref {x.get('id')}: product photos must be real")
        if x.get("kind") == "presenter" and (lane_h or not x.get("synthetic")):
            P.append(f"ref {x.get('id')}: presenter sheets are synthetic and AI-lane only")
    idt = r["identity"] or {}
    allowed = set(_RULE_ID.findall(" ".join(str(idt.get(k) or "") for k in
                                            ("presenter_text", "product_text", "setting")) +
                                   " " + str(script.get("prompt") or "")))
    for sh in shots:
        P += _check_shot(sh, r, lane_h, ref_ids, allowed)
        if sh.get("real_footage") and sh.get("mode") not in ("real", "reuse"):
            P.append(f"shot {sh.get('n')}: real_footage shot is mode {sh.get('mode')}")
    s0 = shots[0]
    if s0.get("mode") == "ai" and (s0.get("task") != "image_to_video" or not any(
            it.get("ref") == "frame0" and it.get("tag") == "<FIRST_FRAME>"
            for it in s0.get("inputs") or [])):
        P.append("frame-0 shot is not image_to_video from the frame-0 still")
    for sh in shots:
        if sh.get("mode") != "reuse":
            continue
        if sh.get("reuse_of") != s0.get("n"):
            P.append(f"shot {sh.get('n')}: reuse_of {sh.get('reuse_of')!r} is not shot 1")
        if (s0.get("mode") == "ai") != (sh.get("task") is not None):
            P.append(f"shot {sh.get('n')}: the loop is generated only when shot 1 is")
        if sh.get("task") and [it.get("tag") for it in sh["inputs"][:2]] != list(TAGS):
            P.append(f"shot {sh.get('n')}: the loop needs the frame-0 still as first and last frame")
        if s0.get("mode") in ("real", "edit") and not sh.get("real_footage_why"):
            P.append(f"shot {sh.get('n')}: reuse of real footage needs real_footage_why")
    dur = float(r.get("duration_s") or 0)
    prev = 0.0
    for sh in shots:
        w = sh.get("window") or [0, 0]
        if abs(w[0] - prev) > 0.051:
            P.append(f"shot {sh.get('n')}: window {w} does not start at {prev:.1f}")
        if w[1] <= w[0]:
            P.append(f"shot {sh.get('n')}: empty window {w}")
        prev = w[1]
    if abs(prev - dur) > 0.051:
        P.append(f"windows end at {prev:.1f}, not duration_s {dur:g}")
    gen = [s for s in shots if s.get("gen_duration_s")]
    gen_s = sum(s["gen_duration_s"] for s in gen)
    b = r["budget_usd"] or {}
    want_d = round(gen_s * OMNI_PER_S["360p"], 2)
    want_f = round(gen_s * OMNI_PER_S["1080p"], 2)
    if b.get("generated_s") != gen_s or b.get("draft") != want_d or b.get("final") != want_f \
            or b.get("estimate") != round(want_d + want_f, 2):
        P.append("budget_usd does not match the generated seconds")
    if (r["seed"] is None) != (not gen) or (gen and not isinstance(r["seed"], int)):
        P.append("seed must be an int when anything is generated, else null")
    P += _disclosure_problems(r, presenter, lane, len(gen))
    c = r["counts"] or {}
    if c.get("shots") != len(shots) or c.get("generated") != len(gen):
        P.append("counts do not match the shots")
    return P


def _disclosure_problems(r, presenter, lane, n_gen):
    d = r.get("disclosure") or {}
    P = []
    tg = d.get("platform_toggles") or {}
    for plat, key in PLATFORM_TOGGLES:
        want = _toggle_on(presenter, lane, n_gen > 0, plat)
        if (tg.get(plat) or {}).get(key) is not want:
            P.append(f"disclosure: {plat} {key} must be {str(want).lower()}")
    ai_gen = presenter == "ai" or n_gen > 0 or lane == "creator_clone"
    if d.get("ai_generated") is not ai_gen:
        P.append(f"disclosure.ai_generated must be {str(ai_gen).lower()}")
    if d.get("synthid") is not (n_gen > 0):
        P.append("disclosure.synthid must follow the Omni shots")
    line = d.get("caption_line")
    if ai_gen and not (line and LX.has_ai_disclosure_line(line)):
        P.append("AI content needs a D138 caption disclosure line")
    if presenter == "ai" and d.get("frame0_label") != "AI persona":
        P.append("AI persona needs the frame-0 'AI persona' label (edit overlay)")
    return P


def check_voice_plan(vp, script):
    """Contract problems in a voice_plan.json dict -> [problem]."""
    if not isinstance(vp, dict):
        return ["voice_plan.json is not an object"]
    P = [f"missing field {k}" for k in ("schema_version", "lane", "engine", "voice", "lines",
                                        "outputs", "disclosure", "mix") if k not in vp]
    if P:
        return P
    presenter = "ai" if script.get("presenter") == "ai" else "human"
    lane = vp["lane"]
    if lane not in LANES:
        return [f"lane {lane!r}"]
    if (presenter == "ai") != (lane == "ai_persona"):
        P.append(f"lane {lane} does not fit presenter {presenter}")
    real = lane == "real_voice"
    eng = vp["engine"]
    if real:
        if eng is not None:
            P.append("real_voice is a read guide: engine must be null")
        if vp["outputs"].get("words"):
            P.append("real_voice exports no words.json")
    else:
        if not isinstance(eng, dict):
            return P + ["engine missing"]
        if eng.get("model_id") != ENGINE["model_id"] or eng.get("endpoint") != "/tts/sse":
            P.append("engine must be sonic-3.6-2026-08-27 on /tts/sse")
        if eng.get("output_format") != ENGINE["output_format"]:
            P.append("engine.output_format must be raw pcm_s16le 48000")
        if bool(eng.get("locale")) == bool(eng.get("language")):
            P.append("set locale or language, never both")
        if eng.get("mode") not in ("line", "take") or eng.get("add_timestamps") is not True:
            P.append("engine mode line|take with add_timestamps true")
        if vp["outputs"].get("words") != f"{vp.get('slug')}-words.json":
            P.append("outputs.words must be <slug>-words.json")
    voice = vp["voice"] or {}
    if lane == "creator_clone" and not str(voice.get("consent_ref") or "").strip():
        P.append("creator_clone voice without consent_ref")
    emotive = bool(voice.get("emotive"))
    lines = vp["lines"] or []
    dur = float(vp.get("duration_s") or script.get("duration_s") or 0)
    prev = -1.0
    for k, ln in enumerate(lines):
        lid = ln.get("id")
        if lid != f"L{k + 1}":
            P.append(f"line {k + 1}: id {lid!r}")
        if ln.get("role") not in ("dialogue", "rehook") or \
                ln.get("anchor") != ("start" if ln.get("role") == "dialogue" else "end"):
            P.append(f"{lid}: role/anchor {ln.get('role')}/{ln.get('anchor')}")
        w = ln.get("window") or [0, 0]
        if w[0] < -1e-6 or w[1] > dur + 0.051 or w[1] <= w[0]:
            P.append(f"{lid}: window {w}")
        if w[0] + 1e-6 < prev:
            P.append(f"{lid}: out of timeline order")
        prev = w[0]
        tr = str(ln.get("transcript") or "")
        if speech_words(ln.get("display")) != speech_words(tr):
            P.append(f"{lid}: display and transcript differ in words")
        if re.search(r"\[[^\]]*\]", tr):
            P.append(f"{lid}: nonverbal or bracket tag in the transcript")
        if re.search(r"[<>]", strip_tags(tr)):
            P.append(f"{lid}: a tag other than speed/volume/emotion/break/spell")
        if lane == "ai_persona":
            m = LX.first_match(LX.AI_FIRST_PERSON, strip_tags(tr))
            if m:
                P.append(f"{lid}: D137 lived-experience claim {m.group(0)!r} in an AI voice")
        if lane == "creator_clone" and ln.get("first_person_claim") and \
                not ln.get("creator_approved"):
            P.append(f"{lid}: first-person claim needs creator approval")
        wpm = ln.get("wpm") or {}
        try:
            ok = float(wpm["floor"]) <= float(wpm["target"]) <= float(wpm["max"]) <= WPM_FAIL \
                and float(wpm["target"]) <= WPM_CAP
        except (KeyError, TypeError, ValueError):
            ok = False
        if not ok:
            P.append(f"{lid}: wpm {wpm}")
        if not ln.get("fits") and not ln.get("flags"):
            P.append(f"{lid}: overruns its window at the target wpm without a flag")
        gc = ln.get("generation_config")
        if real:
            if gc is not None:
                P.append(f"{lid}: real_voice line carries generation_config")
            continue
        if not isinstance(gc, dict):
            P.append(f"{lid}: generation_config missing")
            continue
        sp, vol = gc.get("speed"), gc.get("volume")
        if not (isinstance(sp, (int, float)) and SPEED_HOUSE[0] <= sp <= SPEED_HOUSE[1]):
            P.append(f"{lid}: speed {sp!r} outside {SPEED_HOUSE}")
        if not (isinstance(vol, (int, float)) and VOLUME_HOUSE[0] <= vol <= VOLUME_HOUSE[1]):
            P.append(f"{lid}: volume {vol!r} outside {VOLUME_HOUSE}")
        if "emotion" in gc and (not emotive or gc["emotion"] not in EMOTIONS):
            P.append(f"{lid}: emotion {gc['emotion']!r} (enum, Emotive voices only)")
    return P


# ------------------------------------------------------------ render_md
def render_md(r, vp):
    """A short human summary of the hand-off (render.md)."""
    c = r.get("counts") or {}
    b = r.get("budget_usd") or {}
    d = r.get("disclosure") or {}
    shots = r.get("shots") or []
    on = [f"{p} {k}" for p, k in PLATFORM_TOGGLES
          if ((d.get("platform_toggles") or {}).get(p) or {}).get(k)]
    L = [HEADING, ""]
    L.append(f"- **Run:** `{r.get('slug')}` · {r.get('duration_s')} s · presenter "
             f"{r.get('presenter_mode')} · voice lane {r.get('voice_lane')}"
             + (f" (consent {r['consent_ref']})" if r.get("consent_ref") else "")
             + (" · AI B-roll on" if r.get("ai_broll") else "") + f" · sha8 {r.get('sha8')}")
    L.append(f"- **Shots:** {c.get('shots')} — ai {c.get('ai')}, real {c.get('real')}, edit "
             f"{c.get('edit')}, reuse {c.get('reuse')}; {c.get('generated')} Omni clips = "
             f"{c.get('generated_s')} s generated at 24 fps (master 1080x1920, 30 fps by "
             "frame duplication)")
    L.append(f"- **Budget (Omni {OMNI_MODEL}):** draft ${b.get('draft', 0):.2f} at 360p · "
             f"final ${b.get('final', 0):.2f} at 1080p · estimate ${b.get('estimate', 0):.2f} · "
             f"cap ${b.get('cap', 0):.2f} with every retry"
             + (f" · lip-sync up to ${b['lipsync_max']:.2f}" if b.get("lipsync_max") else ""))
    L.append("- **Disclosure:** " + ("AI-generated: " + ", ".join(on) + " on" if on else
                                     "no AI toggles (nothing synthetic)")
             + (f"; caption line: {d['caption_line']}" if d.get("caption_line") else "")
             + ("; frame-0 'AI persona' label in the edit" if d.get("frame0_label") else ""))
    v = vp.get("voice") or {}
    if vp.get("read_guide"):
        L.append(f"- **Voice:** the creator's real voice (read guide, {len(vp.get('lines') or [])} "
                 "lines with windows and wpm); no TTS, no words.json")
    else:
        eng = vp.get("engine") or {}
        who = v.get("id") or (f"to pick: {'emotive ' if v.get('emotive') else ''}library voice"
                              f"{', ' + v['gender'] if v.get('gender') else ''}"
                              f"{', ' + v['age'] if v.get('age') else ''}")
        L.append(f"- **Voice:** Cartesia {eng.get('model_id')} ({eng.get('endpoint')}, "
                 f"{eng.get('mode')} mode, 48 kHz) · {len(vp.get('lines') or [])} lines · "
                 f"voice {who}" + (" · emotion tags on" if v.get("emotive") else ""))
    lips = [f"{s['n']} ({s['lipsync'].get('line_id')})" for s in shots
            if (s.get("lipsync") or {}).get("required")]
    L.append("- **Lip-sync:** " + (", ".join(lips) + " — Omni says the line, then the "
                                   "lip-sync pass on the Cartesia segment" if lips else "none"))
    film = [s for s in shots if s.get("mode") == "real" or
            (s.get("mode") == "reuse" and not s.get("task"))]
    if film:
        why = {}
        for s in film:
            why.setdefault(s.get("real_footage_why") or "real footage", []).append(s["n"])
        L.append(f"- **Film for real ({len(film)}):** " + "; ".join(
            f"{', '.join(ns)}: {w}" for w, ns in why.items()))
    refs = r.get("refs") or []
    if refs:
        L.append("- **References:** " + ", ".join(
            f"{x['id']} ({'synthetic' if x.get('synthetic') else 'real'}"
            f"{'' if x.get('required') else ', fallback only'})" for x in refs))
    flags = [ln["id"] for ln in vp.get("lines") or [] if ln.get("flags")]
    if flags:
        L.append(f"- **Timing flags:** {', '.join(flags)} may overrun at the target wpm; "
                 "place by words.json")
    L += ["", "| shot | window | mode | task | clip | notes |", "|---|---|---|---|---|---|"]
    for s in shots:
        w = s.get("window") or [0, 0]
        note = []
        if (s.get("lipsync") or {}).get("required"):
            note.append(f"lip-sync {s['lipsync'].get('line_id')}")
        if s.get("overlay_text"):
            note.append("overlay in edit")
        if s.get("mode") == "reuse":
            note.append(f"loop of {s.get('reuse_of')}")
        task = s.get("task") or DASH
        clip = f"{s['gen_duration_s']} s" if s.get("gen_duration_s") else DASH
        extra = ("; " + "; ".join(note)) if note else ""
        L.append(f"| {s.get('n')} | {w[0]:.1f}{NDASH}{w[1]:.1f} | {s.get('mode')} | {task} | "
                 f"{clip} | {s.get('shot_type')}{extra} |")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- write
_RENDER_KW = ("slug", "script_sha", "voice_lane", "ai_broll", "consent_ref")
_VOICE_KW = ("voice_lane", "consent_ref", "voice_id")


def _dumps(obj):
    return json.dumps(obj, indent=1, ensure_ascii=False) + "\n"


def _reslug(vp, slug):
    vp["run"] = vp["slug"] = slug
    vp["outputs"]["audio"] = f"{slug}-vo.wav"
    if vp["outputs"].get("words"):
        vp["outputs"]["words"] = f"{slug}-words.json"
    return vp


def build_all(script, shots, **kw):
    """-> (render dict, voice plan dict) with one set of keyword options."""
    bad = sorted(set(kw) - set(_RENDER_KW) - set(_VOICE_KW))
    if bad:
        raise TypeError(f"unknown option(s): {', '.join(bad)}")
    r = build_render(script, shots, **{k: kw[k] for k in _RENDER_KW if k in kw})
    vp = build_voice_plan(script, shots, **{k: kw[k] for k in _VOICE_KW if k in kw})
    if vp["slug"] != r["slug"]:
        _reslug(vp, r["slug"])
    return r, vp


def write(outdir, script, shots, **kw):
    """Write render.json, voice_plan.json and render.md into outdir.
    kw: slug, script_sha, voice_lane, ai_broll, consent_ref, voice_id.
    -> the file names written."""
    r, vp = build_all(script, shots, **kw)
    os.makedirs(outdir, exist_ok=True)
    texts = {"render.json": _dumps(r), "voice_plan.json": _dumps(vp),
             "render.md": render_md(r, vp)}
    for name in FILES:
        with open(os.path.join(outdir, name), "w", encoding="utf-8") as f:
            f.write(texts[name])
    return list(FILES)


# ------------------------------------------------------------ selfcheck
SC_FORMATS = ("demo", "talking-head", "pov-vlog", "transformation", "review")
SC_PRESENTERS = ("human", "ai")
SC_BUDGET_S = 30.0
PACK_SCRIPTS = {"omni": "omni-render/scripts/omni_render.py",
                "voice": "cartesia-voice/scripts/cartesia_vo.py",
                "qa": "qa-judge/scripts/qa_probe.py",
                "assemble": "assemble-master/scripts/assemble.py"}
_PNG_1PX = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMI"
            "QAAAABJRU5ErkJggg==")
_OMNI_BODY_KEYS = {"model", "input", "response_format", "generation_config", "store",
                   "previous_interaction_id", "background"}
_TTS_BODY_KEYS = {"model_id", "transcript", "voice", "output_format", "language", "locale",
                  "generation_config", "add_timestamps", "normalization",
                  "pronunciation_dict_id"}
_HASH_CODE = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
import viral_script_maker as m
import make_shotlist as ms
from vsp import render as R
out = []
for pr in json.loads(sys.argv[2]):
    for f in R.SC_FORMATS:
        for p in R.SC_PRESENTERS:
            s = json.loads(json.dumps(m.generate(pr, presenter=p, fmt=f, duration=30, seed=1)))
            shots, _ = ms.build_shots(s)
            out.append(list(R.build_all(s, shots)))
print("@@DIGEST@@" + R._sha(out))
"""


def _golden():
    with open(os.path.join(REPO, "evals", "golden.jsonl"), encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip() and not ln.lstrip().startswith("//")]


def _gen(maker, prompt, presenter, fmt, duration):
    s = json.loads(json.dumps(maker.generate(prompt, presenter=presenter, fmt=fmt,
                                             duration=duration, seed=1)))
    shots, vo = _ms().build_shots(s)
    return s, shots, vo


def _unit_checks():
    """Synthetic checks: hygiene, speed, prompt screens, lane errors."""
    errs = []
    for disp, kw, want in (
            ("Follow, comment LAMP for the link list.", "LAMP",
             "Follow, comment lamp for the link list."),
            ("The LED lamp was $10-15 \U0001F447 #lamp", None, "The LED lamp was 10 to 15 dollars."),
            ("WAIT (really) it works \u2192 every time \u00b7 promise", None,
             "Wait really it works every time promise."),
            ("POV: day 7, 160\u2013180 wpm", None, "POV: day 7, 160 to 180 wpm.")):
        got = transcript_of(disp, kw)
        if got != want:
            errs.append(f"transcript_of({disp!r}) = {got!r}, want {want!r}")
        if speech_words(disp) != speech_words(got):
            errs.append(f"speech_words differ for {disp!r}")
    if speech_words("Comment LAMP now") == speech_words("Comment lamp later"):
        errs.append("speech_words misses a changed word")
    for tgt, cal, want in ((175, None, 1.0), (150, None, 0.9), (200, None, 1.14),
                           (150, {"0.9": 140, "1.0": 150, "1.1": 165, "1.2": 180}, 1.0)):
        if speed_for(tgt, cal) != want:
            errs.append(f"speed_for({tgt}, {cal}) = {speed_for(tgt, cal)}, want {want}")
    good = ("Close-up, eye level, slow push-in: the lamp, glowing, in a bedroom, lit by a warm "
            "bedside lamp. Vertical 9:16 smartphone footage. Single continuous shot, no scene "
            "cuts. Sound: quiet room tone. No dialogue, no voiceover. No music. No on-screen "
            "text, captions, subtitles, logos or watermarks. No invented logo or label text. "
            "No hands or people in frame.")
    if prompt_problems(good):
        errs.append(f"clean prompt flagged: {prompt_problems(good)}")
    for bad in (good.replace("quiet room tone", "a \"loud\" room"),
                good + " Render exactly the label.", good + " Palette #2F6BFF.",
                good + " Rule D123 applies.", good.replace("No dialogue, no voiceover.",
                                                           "The presenter says: hi."),
                good.replace(" No invented logo or label text.", ""),
                good.replace("Single continuous shot, no scene cuts. ", "")):
        if not prompt_problems(bad):
            errs.append(f"prompt screen missed: {bad[-60:]!r}")
    base = {"prompt": "LED sunrise alarm lamp", "presenter": "human", "duration_s": 30,
            "hook_stack": [], "beats": []}
    for fn in (lambda: build_render(base, [], voice_lane="creator_clone"),
               lambda: build_voice_plan(base, [], voice_lane="creator_clone"),
               lambda: build_render(dict(base, presenter="ai"), [], voice_lane="real_voice"),
               lambda: build_render(base, [], voice_lane="ai_persona"),
               lambda: build_voice_plan(base, [], voice_lane="robot")):
        try:
            fn()
            errs.append("an invalid voice lane did not raise ValueError")
        except ValueError:
            pass
    return errs


def _assertions(key, s, r, vp, stats):
    """The lane rules the matrix must hold (counted into stats)."""
    errs = []
    shots = r["shots"]
    s0 = shots[0]
    if s0["mode"] == "ai":
        stats["frame0_i2v"] += 1
        if s0["task"] != "image_to_video" or s0["inputs"][0] != {"tag": "<FIRST_FRAME>",
                                                                 "ref": "frame0"}:
            errs.append(f"{key}: frame-0 shot is not image_to_video from frame0")
    for sh in shots:
        if sh["shot_type"] == "loop-return-frame":
            stats["loops"] += 1
            if sh["mode"] != "reuse" or sh.get("reuse_of") != s0["n"]:
                errs.append(f"{key}: loop {sh['n']} is not a reuse of shot 1")
            if (s0["mode"] == "ai") != bool(sh["task"]):
                errs.append(f"{key}: loop generation does not follow shot 1")
            stats["loops_generated"] += bool(sh["task"])
        if r["presenter_mode"] == "ai" and sh["real_footage"]:
            stats["ai_real_footage"] += 1
            if sh["mode"] not in ("real", "reuse") or (sh["mode"] == "reuse" and sh["task"]):
                errs.append(f"{key}: real_footage shot {sh['n']} is {sh['mode']}")
    if r["presenter_mode"] == "human" and r["counts"]["ai"]:
        errs.append(f"{key}: human lane without ai_broll has {r['counts']['ai']} ai shots")
    if (vp["engine"] is None) != (r["voice_lane"] == "real_voice"):
        errs.append(f"{key}: voice plan engine does not follow the lane")
    stats["lipsync"] += r["counts"]["lipsync"]
    return errs


def _omni_shape(o, r):
    errs = []
    b = o.get("body") or {}
    if o.get("method") != "POST" or o.get("url") != OMNI_ENDPOINT or \
            "x-goog-api-key" not in (o.get("headers") or {}):
        errs.append("request line/header")
    if set(b) - _OMNI_BODY_KEYS:
        errs.append(f"unknown body keys {sorted(set(b) - _OMNI_BODY_KEYS)}")
    if b.get("model") != OMNI_MODEL or b.get("store") is not True:
        errs.append("model/store")
    rf = b.get("response_format") or {}
    if rf.get("type") != "video" or rf.get("aspect_ratio") != "9:16" or \
            rf.get("resolution") not in ("360p", "1080p") or \
            rf.get("delivery") not in ("inline", "uri"):
        errs.append(f"response_format {rf}")
    task = ((b.get("generation_config") or {}).get("video_config") or {}).get("task")
    if b.get("previous_interaction_id"):
        if task != "edit" or not isinstance(b.get("input"), list):
            errs.append("edit turn shape")
        return errs
    if not re.match(r"^(?:[3-9]|10)s$", str(rf.get("duration"))) or task not in TASKS:
        errs.append(f"duration {rf.get('duration')!r} / task {task!r}")
    ins = b.get("input") or []
    if not ins or ins[-1].get("type") != "text" or not ins[-1].get("text"):
        errs.append("the prompt text must close the input list")
    for it in ins[:-1]:
        if it.get("type") != "image" or it.get("mime_type") not in ("image/png", "image/jpeg",
                                                                   "image/webp"):
            errs.append(f"image item {it.get('type')}/{it.get('mime_type')}")
            continue
        try:
            base64.b64decode(it.get("data") or "", validate=True)
        except (ValueError, TypeError):
            errs.append("image data is not base64")
    seed = (b.get("generation_config") or {}).get("seed")
    if seed is not None and seed != r.get("seed"):
        errs.append("seed differs from render.json")
    return errs


def _tts_shape(o):
    errs = []
    b = o.get("body") or {}
    h = o.get("headers") or {}
    if o.get("url") != ENGINE["base_url"] + ENGINE["endpoint"] or \
            not str(h.get("Authorization", "")).startswith("Bearer ") or \
            h.get("Cartesia-Version") != ENGINE["api_version"]:
        errs.append("request line/headers")
    if set(b) - _TTS_BODY_KEYS:
        errs.append(f"unknown body keys {sorted(set(b) - _TTS_BODY_KEYS)}")
    if b.get("model_id") != ENGINE["model_id"] or not b.get("transcript") or \
            not isinstance(b.get("voice"), str) or b.get("add_timestamps") is not True or \
            b.get("output_format") != ENGINE["output_format"] or \
            ("locale" in b) == ("language" in b):
        errs.append("body fields")
    gc = b.get("generation_config") or {}
    if "speed" in gc and not SPEED_API[0] <= gc["speed"] <= SPEED_API[1]:
        errs.append(f"speed {gc['speed']}")
    if "volume" in gc and not VOLUME_API[0] <= gc["volume"] <= VOLUME_API[1]:
        errs.append(f"volume {gc['volume']}")
    if "emotion" in gc and gc["emotion"] not in EMOTIONS:
        errs.append(f"emotion {gc['emotion']}")
    return errs


def _load_script(key):
    """Import a pack script in-process (no __pycache__ left in the pack)."""
    import importlib.util
    path = os.path.join(PACK_DIR, ".agents", "skills", PACK_SCRIPTS[key])
    spec = importlib.util.spec_from_file_location(f"_pack_{key}", path)
    mod = importlib.util.module_from_spec(spec)
    saved, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = saved
    return mod


def _stub_runs(job, r):
    """In-process runs of the Omni and Cartesia scripts with the network
    stubbed: files, render_log.jsonl, seed retry, words.json, the VO track."""
    import contextlib
    import io
    import struct
    errs = []
    om = _load_script("omni")
    calls = []

    def fake_http(method, url, key, body=None, timeout=0, raw=False):
        calls.append(json.loads(json.dumps(body)) if body else None)
        gc = (body or {}).get("generation_config") or {}
        if "seed" in gc and len(calls) == 1:
            raise om.ApiError(400, "Invalid argument: seed is not supported")
        if len(calls) == 2:
            raise om.ApiError(429, "RESOURCE_EXHAUSTED")
        return {"id": "v1_stub", "status": "completed", "steps": [
            {"type": "model_output", "content": [
                {"type": "video", "mime_type": "video/mp4",
                 "data": base64.b64encode(b"stub-mp4").decode("ascii")}]}]}
    om.http = fake_http
    om.BACKOFF_S = (0,)
    n = r["shots"][0]["n"]
    old = os.environ.get("GEMINI_API_KEY")
    os.environ["GEMINI_API_KEY"] = "stub"
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = om.main(["--job", job, "--shot", n])
            rc2 = om.main(["--job", job, "--shot", n])
    finally:
        if old is None:
            os.environ.pop("GEMINI_API_KEY", None)
        else:
            os.environ["GEMINI_API_KEY"] = old
    log = om.read_log(job)
    clip = os.path.join(job, "clips", f"shot-{n}-draft-a1.mp4")
    if rc != 0 or rc2 != 0 or len(log) != 1 or not os.path.isfile(clip):
        errs.append(f"omni stub run: rc {rc}/{rc2}, {len(log)} log lines")
    elif not (log[0].get("seed_dropped") and log[0].get("interaction_id") == "v1_stub" and
              len(calls) == 3 and "seed" not in calls[2]["generation_config"]):
        errs.append("omni stub run: seed retry or 429 backoff did not happen")
    cv = _load_script("voice")

    def fake_tts(vp, body, key):
        words = body["transcript"].split()
        rate = int(body["output_format"]["sample_rate"])
        n_s = int((0.2 + len(words) / 3.2) * rate)
        pcm = struct.pack("<%dh" % n_s, *([1200, -1200] * (n_s // 2) + [0] * (n_s % 2)))
        return pcm, [{"words": words, "start": [0.12 + i / 3.2 for i in range(len(words))],
                      "end": [0.12 + (i + 0.85) / 3.2 for i in range(len(words))]}]
    cv.tts = fake_tts
    os.environ["CARTESIA_API_KEY"] = os.environ.get("CARTESIA_API_KEY") or "stub"
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = cv.main(["--job", job, "--voice-id", "stub-voice"])
    finally:
        if os.environ.get("CARTESIA_API_KEY") == "stub":
            os.environ.pop("CARTESIA_API_KEY", None)
    try:
        with open(os.path.join(job, r["audio"]["words_json"]), encoding="utf-8") as f:
            wj = json.load(f)
        ws = wj["words"]
        ok = rc in (0, 1) and ws and all(0 <= w["start"] <= w["end"] <= wj["duration_s"] + 1.0
                                         for w in ws) and \
            all(a["end"] <= b["start"] + 1e-9 for a, b in zip(ws, ws[1:])) and \
            os.path.isfile(os.path.join(job, "vo", r["audio"]["vo_file"]))
        if not ok:
            errs.append("cartesia stub run: words.json or the VO track is wrong")
    except (OSError, ValueError, KeyError, TypeError) as e:
        errs.append(f"cartesia stub run: {e}")
    return errs


def _pack_checks(maker):
    """--help, dry runs and stubbed runs of the four pack scripts."""
    errs, notes = [], []
    tmp = tempfile.mkdtemp(prefix="vsp-render-")
    env = {k: v for k, v in os.environ.items()
           if k not in ("GEMINI_API_KEY", "CARTESIA_API_KEY", "CARTESIA_VOICE_ID")}
    path = {k: os.path.join(PACK_DIR, ".agents", "skills", v) for k, v in PACK_SCRIPTS.items()}

    def run(key, *args):
        return subprocess.run([sys.executable, path[key]] + [str(a) for a in args],
                              capture_output=True, text=True, timeout=120, cwd=tmp, env=env)

    def jlines(p):
        return [json.loads(x) for x in p.stdout.splitlines() if x.startswith("{")]
    try:
        for key in PACK_SCRIPTS:
            if not os.path.isfile(path[key]):
                return [f"pack script missing: {PACK_SCRIPTS[key]}"], notes
            p = run(key, "--help")
            if p.returncode != 0 or "usage" not in p.stdout:
                errs.append(f"{key} --help exit {p.returncode}")
        s, shots, _ = _gen(maker, "LED sunrise alarm lamp", "ai", "demo", 30)
        job = os.path.join(tmp, "ai")
        write(job, s, shots)
        with open(os.path.join(job, "render.json"), encoding="utf-8") as f:
            r = json.load(f)
        os.makedirs(os.path.join(job, "refs"))
        for x in r["refs"]:
            with open(os.path.join(job, "refs", x["id"] + ".png"), "wb") as f:
                f.write(base64.b64decode(_PNG_1PX))
        p = run("omni", "--job", job, "--validate", "--dry-run")
        if p.returncode != 0 or "validate: ok" not in p.stdout:
            errs.append(f"omni --validate exit {p.returncode}: {p.stdout[-300:]}")
        p = run("omni", "--job", job, "--dry-run", "--full")
        reqs = jlines(p)
        gen = [sh for sh in r["shots"] if sh["gen_duration_s"]]
        if p.returncode != 0 or len(reqs) != len(gen):
            errs.append(f"omni draft dry run: exit {p.returncode}, {len(reqs)}/{len(gen)} requests")
        for o in reqs:
            sh = next(x for x in gen if x["n"] == o["shot"])
            e = _omni_shape(o, r)
            if o["body"]["input"][-1]["text"] != sh["prompt"] or \
                    o["body"]["response_format"]["duration"] != f"{sh['gen_duration_s']}s":
                e.append("prompt/duration differ from render.json")
            errs += [f"omni request shot {o['shot']}: {x}" for x in e]
        lip = next((sh["n"] for sh in gen if sh["lipsync"]["required"]), gen[0]["n"])
        for extra, want in ((["--pass", "final", "--shot", lip], ("1080p", "uri")),
                            (["--shot", gen[1]["n"], "--use-fallback"], ("360p", "inline")),
                            (["--shot", gen[1]["n"], "--edit", "Warmer glow"], ("360p", "inline"))):
            p = run("omni", "--job", job, "--dry-run", "--full", *extra)
            got = jlines(p)
            rf = (got[0]["body"].get("response_format") or {}) if got else {}
            if p.returncode != 0 or len(got) != 1 or (rf.get("resolution"), rf.get("delivery")) != want:
                errs.append(f"omni dry run {extra[:2]}: exit {p.returncode}")
            else:
                errs += [f"omni {extra[0]} {extra[-1]}: {x}" for x in _omni_shape(got[0], r)]
        real = next((sh["n"] for sh in r["shots"] if sh["mode"] == "real"), None)
        if real and run("omni", "--job", job, "--dry-run", "--shot", real).returncode != 2:
            errs.append("omni does not refuse a mode real shot")
        p = run("voice", "--job", job, "--dry-run")
        reqs = jlines(p)
        with open(os.path.join(job, "voice_plan.json"), encoding="utf-8") as f:
            vp = json.load(f)
        if p.returncode != 0 or len(reqs) != len(vp["lines"]):
            errs.append(f"cartesia dry run: exit {p.returncode}, {len(reqs)} requests")
        for o in reqs:
            errs += [f"cartesia request {o.get('line')}: {x}" for x in _tts_shape(o)]
        p = run("voice", "--job", job, "--dry-run", "--calibrate")
        cal = jlines(p)
        if p.returncode != 0 or len(cal) != 12 or any(
                o["body"].get("generation_config") != {"speed": float(o["calibrate_speed"])}
                for o in cal):
            errs.append(f"cartesia --calibrate dry run: exit {p.returncode}, {len(cal)} requests")
        p = run("qa", "--job", job, "--judge-prompt", "--shot", gen[0]["n"])
        if p.returncode != 0 or "Answer with JSON only" not in p.stdout:
            errs.append(f"qa --judge-prompt exit {p.returncode}")
        tools = bool(shutil_which("ffmpeg") and shutil_which("ffprobe"))
        if not tools:
            p = run("qa", "--job", job, "--pass", "draft")
            if p.returncode != 3 or "skipped" not in p.stdout:
                errs.append(f"qa without ffmpeg: exit {p.returncode} (want 3, skipped)")
        p = run("assemble", "--job", job, "--dry-run")
        txt = p.stdout
        if p.returncode != 0 or "fps=30" not in txt or "crop=1080:1920" not in txt or \
                "loudnorm=I=-14:TP=-1" not in txt or "minterpolate" in txt or "pad=" in txt or \
                txt.count(" -an -vf ") != len(r["shots"]):
            errs.append(f"assemble dry run: exit {p.returncode}")
        s2, shots2, _ = _gen(maker, "LED sunrise alarm lamp", "human", "demo", 30)
        job2 = os.path.join(tmp, "human")
        write(job2, s2, shots2)
        p = run("voice", "--job", job2, "--dry-run")
        if p.returncode != 3 or "REAL VOICE" not in p.stdout:
            errs.append(f"cartesia does not refuse real_voice (exit {p.returncode})")
        if run("omni", "--job", job2, "--validate", "--dry-run").returncode != 0:
            errs.append("omni --validate fails on a human-lane job")
        errs += _stub_runs(job, r)
        notes.append(f"pack: 4 scripts --help; omni {len(gen)} draft requests + final/fallback/"
                     f"edit shapes; cartesia {len(vp['lines'])} + 12 calibration requests; qa "
                     f"judge prompt{'' if tools else ' + skipped exit 3'}; assemble dry run; "
                     "real_voice refused; stubbed Omni (seed retry, 429 backoff) and Cartesia "
                     "(placed VO + words.json)")
    except (OSError, ValueError, KeyError, IndexError, StopIteration,
            subprocess.SubprocessError) as e:
        errs.append(f"pack checks crashed: {type(e).__name__}: {e}")
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    return errs, notes


def shutil_which(name):
    import shutil
    return shutil.which(name)


def selfcheck():
    """Hermetic: the golden matrix (x 5 formats x 2 presenters, seed 1, 30 s;
    15 and 60 s for a subset), lane assertions, determinism (in-process, the
    shots.json route and PYTHONHASHSEED 0/4242 children), unit checks and the
    pack scripts (dry runs + stubbed runs). Writes only temp dirs. -> (ok, lines)."""
    t0 = time.time()
    saved = os.environ.get("VSP_NO_PRIORS")
    os.environ["VSP_NO_PRIORS"] = "1"
    try:
        return _selfcheck(t0)
    finally:
        if saved is None:
            os.environ.pop("VSP_NO_PRIORS", None)
        else:
            os.environ["VSP_NO_PRIORS"] = saved


def _selfcheck(t0):
    import importlib
    maker = importlib.import_module("viral_script_maker")
    from vsp import exporters
    lines, fails = [], []
    unit = _unit_checks()
    fails += [f"unit: {e}" for e in unit]
    lines.append("unit: transcript hygiene, speed interpolation, prompt screens, lane "
                 f"errors: {'ok' if not unit else 'FAIL'}")
    golden = _golden()
    subset = [golden[0]["prompt"], golden[1]["prompt"], golden[-3]["prompt"]]
    env = dict(os.environ)
    kids = {}
    for hs in ("0", "4242"):
        kids[hs] = subprocess.Popen([sys.executable, "-c", _HASH_CODE, REPO, json.dumps(subset)],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                    cwd=REPO, env=dict(env, PYTHONHASHSEED=hs))
    stats = {k: 0 for k in ("frame0_i2v", "loops", "loops_generated", "ai_real_footage",
                            "lipsync", "broll_ai", "clone")}
    runs = 0
    sub_digest = []
    jobs = [(g["prompt"], g["id"], 30) for g in golden] + \
        [(g["prompt"], g["id"], d) for d in (15, 60) for g in golden[:4]]
    for prompt, gid, dur in jobs:
        for fmt in SC_FORMATS:
            for pr in SC_PRESENTERS:
                key = f"{gid}|{fmt}|{pr}|{dur}"
                try:
                    s, shots, vo = _gen(maker, prompt, pr, fmt, dur)
                    r, vp = build_all(s, shots)
                    runs += 1
                    probs = check_render(r, s) + check_voice_plan(vp, s)
                    fails += [f"{key}: {p}" for p in probs[:3]]
                    fails += _assertions(key, s, r, vp, stats)
                    r2, vp2 = build_all(s, exporters.shots_json(s, shots, vo))
                    if _sha([r, vp]) != _sha([r2, vp2]):
                        fails.append(f"{key}: the shots.json route differs from in-process")
                    if dur == 30 and prompt in subset:
                        sub_digest.append([r, vp])
                    if pr == "human" and dur == 30:
                        rb = build_render(s, shots, ai_broll=True)
                        fails += [f"{key} ai_broll: {p}" for p in check_render(rb, s)[:3]]
                        stats["broll_ai"] += rb["counts"]["ai"]
                        if rb["counts"]["ai"] and not rb["disclosure"]["ai_generated"]:
                            fails.append(f"{key}: ai_broll without the AI disclosure")
                        if gid == golden[0]["id"]:
                            rc = build_render(s, shots, voice_lane="creator_clone",
                                              consent_ref="consent-001")
                            vc = build_voice_plan(s, shots, voice_lane="creator_clone",
                                                  consent_ref="consent-001")
                            fails += [f"{key} clone: {p}" for p in check_render(rc, s)[:3]]
                            left = [p for p in check_voice_plan(vc, s)
                                    if "creator approval" not in p]
                            for ln in vc["lines"]:
                                ln["creator_approved"] = True
                            left += check_voice_plan(vc, s)
                            fails += [f"{key} clone: {p}" for p in left[:3]]
                            stats["clone"] += 1
                except Exception as e:  # noqa: BLE001 — a crash is a failure line
                    fails.append(f"{key}: crash {type(e).__name__}: {e}")
    if _sha(sub_digest) != _sha([list(build_all(*_gen(maker, p, pr, f, 30)[:2]))
                                 for p in subset for f in SC_FORMATS for pr in SC_PRESENTERS]):
        fails.append("determinism: a second in-process build differs")
    lines.append(f"matrix: {runs} scripts ({len(golden)} golden x {len(SC_FORMATS)} formats x "
                 f"{len(SC_PRESENTERS)} presenters at 30 s + 4 prompts at 15/60 s); "
                 "check_render + check_voice_plan clean; the shots.json route is identical")
    lines.append(f"lanes: frame-0 image_to_video {stats['frame0_i2v']}, loops {stats['loops']} "
                 f"(generated {stats['loops_generated']}), AI-lane real-footage shots "
                 f"{stats['ai_real_footage']} all real, lip-sync shots {stats['lipsync']}, human "
                 f"lane 0 ai shots (ai_broll: {stats['broll_ai']}), creator_clone "
                 f"{stats['clone']} + no-consent ValueError")
    for k, v in (("frame0_i2v", 1), ("loops_generated", 1), ("ai_real_footage", 1),
                 ("lipsync", 1), ("broll_ai", 1), ("clone", 1)):
        if stats[k] < v:
            fails.append(f"lanes: no {k} case in the matrix")
    want = _sha(sub_digest)
    for hs, p in kids.items():
        try:
            out, err = p.communicate(timeout=240)
        except subprocess.TimeoutExpired:
            p.kill()
            out, err = "", "timeout"
        got = out.rsplit("@@DIGEST@@", 1)[-1].strip()
        if got != want:
            fails.append(f"PYTHONHASHSEED={hs}: digest differs ({got[:12]} {err[-200:]})")
    lines.append(f"determinism: 2 in-process builds + PYTHONHASHSEED 0/4242 children identical "
                 f"({len(sub_digest)} scripts)")
    perrs, pnotes = _pack_checks(maker)
    fails += perrs
    lines += pnotes or ["pack: FAIL"]
    dt = time.time() - t0
    if dt > SC_BUDGET_S:
        fails.append(f"timing: {dt:.1f} s > {SC_BUDGET_S:g} s")
    lines += [f"FAIL {x}" for x in fails[:40]]
    if len(fails) > 40:
        lines.append(f"... {len(fails) - 40} more failures")
    lines.append(f"selfcheck {'ok' if not fails else 'FAILED'} in {dt:.1f}s "
                 f"({len(fails)} failures)")
    return not fails, lines


# ------------------------------------------------------------------ CLI
def read_outdir(outdir):
    """An existing run dir -> (script, shots.json dict or None, script sha256)."""
    with open(os.path.join(outdir, "script.json"), "rb") as f:
        raw = f.read()
    script = json.loads(raw.decode("utf-8"))
    shots = None
    sp = os.path.join(outdir, "shots.json")
    if os.path.isfile(sp):
        with open(sp, encoding="utf-8") as f:
            shots = json.load(f)
    return script, shots, hashlib.sha256(raw).hexdigest()


def _load(outdir, name):
    with open(os.path.join(outdir, name), encoding="utf-8") as f:
        return json.load(f)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="python3 -m vsp.render",
                                 description="render hand-off (render.json, voice_plan.json, "
                                             "render.md) for Gemini Omni + Cartesia")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("selfcheck", help="hermetic golden-matrix check (+ pack dry runs)")
    b = sub.add_parser("build", help="write the three files into an existing run dir "
                                     "(reads script.json + shots.json)")
    b.add_argument("outdir")
    b.add_argument("--voice-lane", choices=LANES, default=None)
    b.add_argument("--ai-broll", action="store_true",
                   help="human lane: render faceless product shots with Omni")
    b.add_argument("--consent-ref", default=None, help="consent record id (creator_clone)")
    b.add_argument("--voice-id", default=None, help="Cartesia voice id, if already chosen")
    c = sub.add_parser("check", help="check render.json + voice_plan.json in a run dir")
    c.add_argument("outdir")
    s = sub.add_parser("show", help="print render.md (built in memory if absent)")
    s.add_argument("outdir")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    if a.cmd == "selfcheck":
        ok, lines = selfcheck()
        print("\n".join(lines))
        return 0 if ok else 1
    if a.cmd == "build":
        script, shots, sha = read_outdir(a.outdir)
        try:
            names = write(a.outdir, script, shots, script_sha=sha, voice_lane=a.voice_lane,
                          ai_broll=a.ai_broll, consent_ref=a.consent_ref, voice_id=a.voice_id)
        except ValueError as e:
            print(f"render: {e}", file=sys.stderr)
            return 2
        probs = check_render(_load(a.outdir, "render.json"), script) + \
            check_voice_plan(_load(a.outdir, "voice_plan.json"), script)
        print("wrote " + ", ".join(os.path.join(a.outdir, n) for n in names))
        print("\n".join(probs) if probs else "check: clean")
        return 1 if probs else 0
    if a.cmd == "check":
        script, _, _ = read_outdir(a.outdir)
        probs = check_render(_load(a.outdir, "render.json"), script) + \
            check_voice_plan(_load(a.outdir, "voice_plan.json"), script)
        print("\n".join(probs) if probs else "check: clean")
        return 1 if probs else 0
    if a.cmd == "show":
        p = os.path.join(a.outdir, "render.md")
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                print(f.read(), end="")
        else:
            script, shots, sha = read_outdir(a.outdir)
            r, vp = build_all(script, shots, script_sha=sha)
            print(render_md(r, vp), end="")
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
