"""Shared lexicons: one definition for the gates (vsp/gates.py, vsp/rules.py),
the maker's self-checks and the rubric (vsp/rubric.py).

Sources are cited per pattern group; see docs/research/short-form-virality.md.
"""
import re

# Words spoken per second at the gate's own rate (pipeline.words_per_sec, D43)
WPS_BRISK, WPS_SLOW, SLACK = 3.0, 2.5, 1.15
SLOW_KEYS = ("slow down", "unhurried", "never rushed")

# D136 — unsourced social proof (FTC 16 CFR 465 fake-review rule; D37 class)
SOCIAL_PROOF = [
    re.compile(r"\d(?:\.\d)?\s?(?:★|stars?\b)", re.I),
    re.compile(r"\b\d[\d,.]*\s?[kKmM]?\+?\s*(?:orders|reviews|sold|customers|"
               r"buyers|people bought|five-star)\b", re.I),
    re.compile(r"\bsold out\b", re.I),
    re.compile(r"\bbest[- ]?seller\b", re.I),
]

# D37 — any currency amount (digits or spelled currency words)
PRICE = re.compile(r"(?:[$€£]\s?\d[\d,]*(?:\.\d+)?|\b\d[\d,]*(?:\.\d+)?\s?"
                   r"(?:dollars|bucks|usd|euros?|pounds)\b)", re.I)

# D137 — AI persona lived-experience claims (FTC 16 CFR 465.2: testimonials
# that misrepresent that the testimonialist exists or used the product)
AI_FIRST_PERSON = [
    re.compile(r"\bI (?:woke|slept|tried|used|bought|ordered|wore|felt|"
               r"noticed|lost|gained|returned|switched to|swear by|"
               r"can'?t live without|was skeptical)\b", re.I),
    re.compile(r"\bI'?ve (?:been using|used|tried|had|worn|bought|owned|"
               r"been wearing)\b", re.I),
    re.compile(r"\bI (?:use|wear|love) (?:it|this|mine)\b", re.I),
    re.compile(r"\bmy (?:skin|hair|face|back|neck|body|sleep|lashes|legs|"
               r"feet|mornings?|knees|shoulders)\b", re.I),
    re.compile(r"\b(?:changed|saved) my (?:life|mornings?|sleep|skin|back)\b",
               re.I),
]

# D138 — an AI disclosure LINE: "AI" plus a disclosure cue ("made with an AI
# persona", "AI-generated presenter", "created with AI"). A product name that
# merely contains "AI" ("AI voice recorder") is not a disclosure.
AI_WORD = re.compile(r"\bAI\b")
AI_DISCLOSURE_CUE = re.compile(
    r"\b(?:persona|generated|avatar|virtual|synthetic|character|creator|"
    r"presenter|host|influencer|digital human|made with|created with|"
    r"made by|created by|not a real|disclos\w*|label(?:led|ed)?)\b|"
    r"\b(?:by|with|using)\s+(?:an?\s+)?AI\b", re.I)


def has_ai_disclosure_line(text):
    """D138: some line of `text` names the AI with a disclosure cue."""
    return any(AI_WORD.search(ln) and AI_DISCLOSURE_CUE.search(ln)
               for ln in (text or "").splitlines())


# D139 — generic engagement bait (Meta engagement-bait guidelines; Instagram
# recommendation eligibility). The keyword->DM CTA (D1/B4a) is NOT bait.
GENERIC_BAIT = re.compile(
    r"\b(?:like if|tag a friend|tag someone|comment yes|type yes|"
    r"share this with|double tap|smash that|like and subscribe|"
    r"drop a (?:like|heart|🔥))\b", re.I)

# D141 — absolute / guarantee claims (TikTok ad policy: misleading and false
# content; TikTok Shop content policy 2026-05-22)
ABSOLUTE = re.compile(
    r"(?:\bguarantee(?:d|s)?\b|\bcures?\b|\bmiracle\b|#1\b|\bnumber one\b|"
    r"\bcheapest\b|\blowest price\b|\bbest\s+(?:\w+\s+)?ever\b|"
    r"\b100% (?:effective|proven|safe|natural)\b|\brisk[- ]free\b|"
    r"\bclinically proven\b)", re.I)

# D140 — hashtags that carry no niche signal
GENERIC_TAGS = {"fyp", "foryou", "foryoupage", "viral", "ugc", "trending",
                "explore", "reels", "tiktok", "fy", "xyzbca"}
MAX_HASHTAGS = 5   # Instagram cap since Dec 2025

# rubric-only: slop and meta leaks
SLOP = re.compile(
    r"\b(?:game[- ]changer|you won'?t believe|wait for it|hey guys|"
    r"in today'?s video|let'?s dive in|life[- ]changing|must[- ]have|"
    r"trust me)\b", re.I)
META_LEAK = re.compile(
    r"(?:\bD\d{1,3}[a-c]?\b|\bplaybook\b|\bF\d{2,3}\b|\(split-screen|"
    r"\b85%|sound-off|safe zone|timestamped\)|\bgate \d\b)", re.I)

# D144 / R02 — hooks
FALLBACK_HOOK = re.compile(
    r"^nobody mentions (the [\w\s'-]+ flaw|it|no [\w\s'-]+)\.?$", re.I)
VAGUE_HOOK = re.compile(
    r"you won'?t believe|wait for it|this is crazy|watch this|must see", re.I)
LABEL_WORDS = {"before", "after", "day", "test", "verdict", "wait", "volume",
               "list", "full", "vs", "today", "turn", "your", "up", "result"}

# D46 — link-payload phrases grouped by destination
LINK_GROUPS = [["link in bio"],
               ["link list", "in your dms", "check your dms"],
               ["tap the link"]]

# D146 — series promise
PART2 = re.compile(r"\bpart (?:2|two)\b", re.I)

WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’.-]*")


def words(text):
    return WORD_RE.findall(text or "")


def norm(text):
    return " ".join(w.lower().strip(".'’") for w in words(text))


def first_match(patterns, text):
    for rx in patterns:
        m = rx.search(text or "")
        if m:
            return m
    return None


def overlay_is_clean(overlay, hook):
    """D144: frame-0 overlay is a contiguous <=3-word phrase of the hook, or a
    label form ("BEFORE | AFTER", "DAY 1 | DAY 7", "TEST", ...)."""
    ov = (overlay or "").strip()
    if not ov:
        return True, "no overlay"
    # label pair "X | Y" (each side <= 2 words): "BEFORE | AFTER",
    # "DAY 1 | DAY 7" (D25/D135 transformation frame-0) — a split-screen
    # label, not a phrase, so it is exempt from the 3-word phrase count
    if "|" in ov:
        sides = [norm(x).split() for x in ov.split("|")]
        if len(sides) == 2 and all(1 <= len(x) <= 2 for x in sides):
            return True, "label pair"
        return False, "malformed label pair"
    w = norm(ov).split()
    if not 1 <= len(w) <= 3:
        return False, f"{len(w)} words"
    if ":" in ov or set(w) <= LABEL_WORDS | {"1", "3", "7", "14", "21", "30"}:
        return True, "label form"
    h = norm(hook).split()
    for i in range(len(h) - len(w) + 1):
        if h[i:i + len(w)] == w:
            return True, "contiguous hook phrase"
    return False, "not a contiguous phrase of the hook"
