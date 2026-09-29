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

# ------------------------------------------------ pipeline v2.1 (RULES §68)
# D158 — fake urgency, scarcity or offers. FTC dark-pattern taxonomy (2022:
# false limited-time offers, baseless countdowns, false low-stock and
# high-demand messages, fake discounts); Meta deceptive-pricing policy.
# Transcribed from docs/research/hooks-deep-dive.md §5 RISKY_PHRASES
# UR-01..UR-04 with two deliberate changes: "sold out" / "best-seller" stay
# with D136 (SOCIAL_PROOF — one claim, one rule id), and a bare "hurry"
# ("mornings in a hurry") is not urgency — only "hurry up/now/before" or
# "hurry," / "hurry!" are.
# (id, class, pattern); class decides the allow-path in offer_allowed().
OFFER_URGENCY_PATTERNS = (
    ("UR-01", "urgency",
     r"\bhurry(?: up| now| before)\b|\bhurry[,!]|\bact (?:fast|now)\b|"
     r"\blast chance\b|\bbefore (?:it'?s|they'?re) gone\b|"
     r"\b(?:sale|offer|deal|discount|promo(?:tion)?)s? (?:ends?|ending)\b|"
     r"\bends (?:tonight|today|tomorrow|soon|at midnight|in \d+)\b|"
     r"\btoday only\b|\bonly today\b|\blimited[- ]time\b|"
     r"\bwhile (?:supplies|stocks?) lasts?\b|\bdon'?t miss (?:out|this deal)\b|"
     r"\bflash sale\b|\b(?:24|48|72)[- ]hours? only\b|\bcountdown (?:is on|timer)\b"),
    ("UR-02", "scarcity",
     r"\bonly (?:\d+|a few|a handful) (?:left|remaining|in stock)\b|"
     r"\balmost (?:gone|sold out)\b|\bselling (?:out )?fast\b|\bselling out\b|"
     r"\b(?:low|limited) (?:stock|supply|quantities)\b|\bgoing fast\b|"
     r"\b(?:last|final) (?:few|\d+) (?:units?|pieces?|left)\b"),
    ("UR-03", "demand",
     r"\b\d[\d,.]*[kKmM]? (?:people|others|shoppers) (?:are )?"
     r"(?:viewing|watching|looking at|buying|shopping)\b|"
     r"\b(?:everyone|everybody) is (?:buying|getting)\b"),
    ("UR-04", "offer",
     r"\b(?:was|regularly|reg\.?) [$€£]?\d[\d.,]*\b.{0,15}\b(?:now|today) [$€£]?\d|"
     r"\b\d{1,3}\s?% off\b|\b\d{1,3} percent off\b|\bhalf off\b|"
     r"\bprice (?:goes|is going) up\b|\bwon'?t be this price\b|"
     r"\b(?:promo|discount|coupon) code\b|\buse (?:my |our |the )?code\b|"
     r"\bbogo\b|\bbuy one,? get one\b|\bfree shipping\b|\bon sale\b|"
     r"\bclearance sale\b|\bdeal of the (?:day|week)\b"),
)
OFFER_URGENCY = [re.compile(p, re.I) for _, _, p in OFFER_URGENCY_PATTERNS]
_OFFER_CLASSES = tuple(cls for _, cls, _ in OFFER_URGENCY_PATTERNS)

# the prompt supplies an offer / deadline (allow-path for urgency + offer
# classes) or a stock / demand figure (allow-path for scarcity + demand)
OFFER_CUE = re.compile(
    r"%\s*off\b|\b\d{1,3} percent off\b|\bhalf off\b|\bsale\b|\bdiscount\w*|"
    r"\bdeals?\b|\bcoupons?\b|\bpromo\w*|\bcode\b|\boffers?\b|\bbogo\b|"
    r"\bbuy one,? get one\b|\bfree shipping\b|\bclearance\b|\blimited[- ]time\b|"
    r"\btoday only\b|\bdeadline\b|\bexpires?\b|\bends? (?:on |at |by )?"
    r"(?:today|tonight|tomorrow|midnight|monday|tuesday|wednesday|thursday|"
    r"friday|saturday|sunday|\d)", re.I)
STOCK_CUE = re.compile(
    r"\bin stock\b|\bstock\b|\b\d+ (?:units?|pieces?|left)\b|"
    r"\blimited (?:run|supply|quantities|stock)\b|\bonly \d+\b|"
    r"\b\d[\d,.]*[kKmM]? (?:people|shoppers|buyers|customers)\b", re.I)


def offer_in(prompt, kind=None):
    """D158 allow-path: the prompt itself supplies the offer.

    kind=None / "offer" / "urgency": an offer or deadline cue (sale,
    discount, % off, code, free shipping, limited-time, ends …) or any
    OFFER_URGENCY phrase in the prompt. kind="scarcity" / "demand": a stock
    or demand figure (in stock, only 3, 12k shoppers …) or a scarcity/demand
    phrase in the prompt — a discount is not a stock claim."""
    p = prompt or ""
    if kind in ("scarcity", "demand"):
        return bool(STOCK_CUE.search(p)) or any(
            rx.search(p) for rx, cls in zip(OFFER_URGENCY, _OFFER_CLASSES)
            if cls in ("scarcity", "demand"))
    return bool(OFFER_CUE.search(p)) or any(rx.search(p) for rx in OFFER_URGENCY)


def offer_urgency_hits(text, prompt=""):
    """D158: [(id, class, matched text)] in `text` the prompt does not allow
    (first match per pattern, pattern order)."""
    out = []
    for rx, (pid, cls, _) in zip(OFFER_URGENCY, OFFER_URGENCY_PATTERNS):
        m = rx.search(text or "")
        if m and not offer_in(prompt, cls):
            out.append((pid, cls, m.group(0)))
    return out


# rubric — clickbait markers (Meta clickbait-links guideline: withholding and
# sensational phrasing, all caps, "!!"; YouTube egregious-clickbait policy).
# hooks-deep-dive.md §5 RISKY_PHRASES CB-01..CB-07; CB-06 is case-sensitive.
CLICKBAIT_PATTERNS = (
    ("CB-01", "error", r"\byou (?:won'?t|will never|wont) believe\b|"
                       r"\byou'?ll never guess\b", re.I),
    ("CB-02", "error", r"\bwhat happen(?:s|ed) next\b|\bwait (?:for it|till|until)\b|"
                       r"\b(?:watch|stay) (?:till|until|to) the end\b", re.I),
    ("CB-03", "error", r"\bsecret (?:to|behind)\b|\bthey don'?t want you to know\b|"
                       r"\bindustry (?:doesn'?t|does not) want\b", re.I),
    ("CB-04", "warn", r"\b(?:shocking|jaw[- ]dropping|mind[- ]?blowing|"
                      r"this will shock you)\b", re.I),
    ("CB-05", "warn", r"\b(?:nobody|no one) (?:is talking about|talks about|"
                      r"mentions|knows|tells you)\b", re.I),
    ("CB-06", "warn", r"!{2,}|\?!|\b[A-Z]{2,}(?:\s+[A-Z]{2,}){3,}\b", 0),
    ("CB-07", "warn", r"^\s*stop scrolling\b", re.I),
)
CLICKBAIT = [re.compile(p, f) for _, _, p, f in CLICKBAIT_PATTERNS]


def clickbait_hits(text):
    """[(id, severity, matched text)] — clickbait markers in `text`."""
    out = []
    for rx, (cid, sev, _, _) in zip(CLICKBAIT, CLICKBAIT_PATTERNS):
        m = rx.search(text or "")
        if m:
            out.append((cid, sev, m.group(0)))
    return out


def price_in(prompt):
    """D37 allow-path (requires_price archetypes): the prompt names a price."""
    return bool(PRICE.search(prompt or "") or re.search(r"\$\d", prompt or ""))


PROOF_CUE = re.compile(
    r"\b(?:rated|ratings?|reviews?|reviewed|stars?|tested by|lab[- ]tested|"
    r"certified|award\w*|clinical\w*|stud(?:y|ies)|dermatologist\w*|"
    r"proven)\b", re.I)


def proof_in(prompt):
    """D136 allow-path (requires_proof archetypes): the prompt supplies a
    proof claim (a SOCIAL_PROOF form, a rating, a review count, a test,
    a certification or a study)."""
    p = prompt or ""
    return bool(first_match(SOCIAL_PROOF, p) or PROOF_CUE.search(p))

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


KEYWORD_STOP = {"a", "an", "the", "for", "with", "of", "and", "in", "on", "to",
                "my", "your", "this", "that", "is", "it", "at", "by", "vs"}


def _kstem(w):
    w = w.lower().strip(".'’")
    for pos in ("'s", "’s"):
        if w.endswith(pos):
            w = w[:-2]
    if len(w) > 4 and w.endswith("es") and w[:-2].endswith(("sh", "ch", "x", "ss", "z")):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def keyword_tokens(text):
    """Plural/possessive-tolerant tokens; hyphens split words."""
    return [_kstem(w) for w in norm((text or "").replace("-", " ")).split()]


def keyword_in(text, keyword, loose=False):
    """D155/D161: the keyword occurs in `text` as a contiguous token run
    (case-, plural- and hyphen-insensitive). loose=True also accepts every
    content token of the keyword present anywhere in `text` (DISC-01 "exact
    or all content lemmas")."""
    k = keyword_tokens(keyword)
    t = keyword_tokens(text)
    if not k or not t:
        return False
    if any(t[i:i + len(k)] == k for i in range(len(t) - len(k) + 1)):
        return True
    if loose:
        content = [w for w in k if w not in KEYWORD_STOP]
        return bool(content) and all(w in t for w in content)
    return False


def compact_tag(text):
    """'#Milk-Frothers' / 'milk frother' -> 'milkfrother' (plural-tolerant)."""
    return "".join(keyword_tokens(re.sub(r"[#_]", " ", text or "")))


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
