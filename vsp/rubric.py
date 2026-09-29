"""Deterministic quality rubric for a finished script (0-100).

Independent of the gates: the gates are pass/fail contracts; the rubric grades
how good a script is, using the RULES.md doctrine plus the 2025-2026 research
in /research (hook length and specificity, payoff placement, muted-viewer
readability, claims and AI-testimonial compliance, hashtag hygiene...).

Design (Rubrics-as-Rewards style):
  * every check is binary and atomic, with a tier and weight
      E = essential (3), I = important (2), O = optional (1)
  * pitfalls subtract points (slop phrases, meta leaks, repeated sentences)
  * AUDIT checks are held out of the selection score used by best-of-N, so the
    eval harness can detect a selector that games the rubric (winners should
    not score worse on audit checks than random passing candidates).

score(script) -> {"score", "selection_score", "audit_score", "checks",
                  "pitfalls", "flags"}
"""
import re

from vsp import lexicon as L
from vsp.lexicon import (ABSOLUTE, AI_FIRST_PERSON, FALLBACK_HOOK,  # noqa: F401
                         GENERIC_BAIT, GENERIC_TAGS, LABEL_WORDS, LINK_GROUPS,
                         MAX_HASHTAGS, META_LEAK, PRICE, SLOP, SOCIAL_PROOF,
                         VAGUE_HOOK, WORD_RE, overlay_is_clean)

T_RE = re.compile(r"(\d+(?:\.\d+)?)")

STOP = set("""a an the for with my of and in on to that just make sense things
thing days day every why your you how i stopped quit deleted ditched dropped
gave up tried did unfollowed this these it its is are be was were buying
make me script about video reel under best new mini portable set""".split())


def _items(s):
    return list(s.get("hook_stack") or []) + list(s.get("beats") or [])


def _win(item):
    m = T_RE.findall(item.get("t") or "")
    return (float(m[0]), float(m[1])) if len(m) >= 2 else (None, None)


def _words(text):
    return WORD_RE.findall(text or "")


def _norm(text):
    return " ".join(w.lower().strip(".'’") for w in _words(text))


def _stem(w):
    w = w.lower().strip(".'’")
    for suf in ("es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _wps(delivery):
    d = (delivery or "").lower()
    return 2.5 if any(k in d for k in ("slow down", "unhurried",
                                        "never rushed")) else 3.0


def hook_line(s):
    for h in s.get("hook_stack") or []:
        if h.get("dialogue"):
            return h["dialogue"]
    for b in s.get("beats") or []:
        if "HOOK" in (b.get("type") or "") and b.get("dialogue"):
            return b["dialogue"]
    return ""


def frame0_overlay(s):
    hs = s.get("hook_stack") or []
    if hs and hs[0].get("on_screen"):
        return hs[0]["on_screen"]
    for b in s.get("beats") or []:
        if b.get("type") == "VISUAL TRIGGER":
            return b.get("on_screen") or ""
    return ""


def prompt_anchors(prompt):
    toks = [_stem(w) for w in _words(prompt)]
    return {t for t in toks if len(t) >= 3 and t not in STOP
            and not t.replace(".", "").isdigit()}


def viewer_text(s, include_caption=True):
    parts = []
    for it in _items(s):
        for k in ("dialogue", "rehook", "on_screen"):
            if it.get(k):
                parts.append(str(it[k]))
    if include_caption and s.get("caption"):
        parts.append(s["caption"])
    return "\n".join(parts)


def spoken_text(s):
    return "\n".join(str(it.get(k)) for it in _items(s)
                     for k in ("dialogue", "rehook") if it.get(k))


# --------------------------------------------------------------- checks
def _c_hook_len(s, ctx):
    h = hook_line(s)
    n = len(_words(h))
    return (0 < n <= 8), f"{n} words: {h!r}"


def _c_hook_specific(s, ctx):
    h = hook_line(s).strip()
    if not h:
        return False, "no verbal hook"
    if FALLBACK_HOOK.match(h):
        return False, f"generic fallback hook: {h!r}"
    if VAGUE_HOOK.search(h):
        return False, f"vague hook: {h!r}"
    toks = {_stem(w) for w in _words(h)}
    anchored = bool(toks & ctx["anchors"]) or bool(re.search(r"\d", h)) \
        or bool(re.search(r"\b(?:I|my|I'm|I've)\b", h))
    return anchored, "anchored" if anchored else f"no concrete anchor: {h!r}"


def _c_timeline(s, ctx):
    dur = float(s.get("duration_s") or 30)
    wins = []
    for b in s.get("beats") or []:
        a, e = _win(b)
        if a is None:
            return False, f"beat without window: {b.get('type')}"
        wins.append((a, e, b))
    if not wins:
        return False, "no beats"
    probs = []
    for i in range(len(wins)):
        for j in range(i + 1, len(wins)):
            ov = min(wins[i][1], wins[j][1]) - max(wins[i][0], wins[j][0])
            if ov > 0.1:
                probs.append("overlap")
    ordered = sorted(wins, key=lambda w: (w[0], w[1]))
    for (a1, e1, _), (a2, e2, _) in zip(ordered, ordered[1:]):
        if a2 - e1 > 0.5:
            probs.append("gap")
    if max(e for _, e, _ in wins) > dur + 0.05:
        probs.append("overrun")
    for a, e, b in wins:
        dlg = b.get("dialogue") or ""
        if dlg and len(dlg.split()) / _wps(b.get("delivery")) > (e - a) * 1.15:
            probs.append(f"speech>window:{b.get('type')}")
    return (not probs), ", ".join(sorted(set(probs))) or "clean"


def _c_payoff_place(s, ctx):
    dur = float(s.get("duration_s") or 30)
    for b in s.get("beats") or []:
        if b.get("type") == "PAYOFF":
            a, _ = _win(b)
            if a is None:
                return False, "PAYOFF without window"
            frac = a / dur
            return 0.68 <= frac <= 0.88, f"payoff starts at {frac:.0%}"
    return False, "no PAYOFF beat"


def _c_claims(s, ctx):
    prompt = s.get("prompt") or ""
    txt = viewer_text(s)
    bad = []
    supplied = {re.sub(r"[^\d.]", "", p).rstrip(".").rstrip("0").rstrip(".")
                for p in PRICE.findall(prompt)}
    for p in PRICE.findall(txt):
        key = re.sub(r"[^\d.]", "", p).rstrip(".").rstrip("0").rstrip(".")
        if key not in supplied:
            bad.append(f"price {p!r}")
    for rx in SOCIAL_PROOF:
        m = rx.search(txt)
        if m and not rx.search(prompt):
            bad.append(f"social proof {m.group(0)!r}")
    return (not bad), "; ".join(bad) or "no invented claims"


def _c_ai_first_person(s, ctx):
    if s.get("presenter") != "ai":
        return None, "n/a (human presenter)"
    txt = viewer_text(s)
    for rx in AI_FIRST_PERSON:
        m = rx.search(txt)
        if m:
            return False, f"AI persona claims lived experience: {m.group(0)!r}"
    return True, "curator-framed"


def _c_leaks(s, ctx):
    txt = viewer_text(s)
    probs = []
    if "{" in txt or "}" in txt:
        probs.append("raw template slot")
    if re.search(r"\b(?:None|null|undefined)\b", txt):
        probs.append("null leak")
    m = re.search(r"\b([A-Za-z]+) \1\b", txt, re.I)
    if m and m.group(1).lower() not in ("that", "had", "very", "no"):
        probs.append(f"doubled word {m.group(0)!r}")
    m = re.search(r"[.!?] +[a-z]", txt)
    if m:
        probs.append(f"lowercase after sentence end {m.group(0)!r}")
    return (not probs), "; ".join(probs) or "clean"


def _c_frame0(s, ctx):
    ov = frame0_overlay(s).strip()
    if not ov:
        return False, "no frame-0 overlay"
    ok, why = overlay_is_clean(ov, hook_line(s))
    return ok, f"{why}: {ov!r}"


def _c_onscreen(s, ctx):
    probs = []
    hook_end = max([_win(h)[1] or 0.0 for h in s.get("hook_stack") or []]
                   + [3.0])
    for it in _items(s):
        os_txt = (it.get("on_screen") or "").strip()
        if not os_txt:
            continue
        n = len(os_txt.split())
        a, e = _win(it)
        if it.get("type") == "VISUAL TRIGGER" and a is not None:
            e = max(e, hook_end)  # the frame-0 card holds through the hook
        if n > 12:
            probs.append(f"{n} words on {it.get('type')}")
        elif len(os_txt) > 70:
            probs.append(f"{len(os_txt)} chars on {it.get('type')}")
        elif a is not None and e > a and len(os_txt) / (e - a) > 20:
            probs.append(f"{len(os_txt) / (e - a):.0f} cps on {it.get('type')}")
    return (not probs), "; ".join(probs) or "readable"


def _c_rehooks(s, ctx):
    rh = [_norm(b.get("rehook")) for b in s.get("beats") or [] if b.get("rehook")]
    if float(s.get("duration_s") or 30) > 15 and not rh:
        return False, "no re-hooks"
    dup = len(rh) - len(set(rh))
    return dup == 0, f"{len(rh)} re-hooks, {dup} repeated"


def _c_single_cta(s, ctx):
    low = (spoken_text(s) + "\n" + (s.get("caption") or "")).lower()
    hit = [g[0] for g in LINK_GROUPS if any(p in low for p in g)]
    return len(hit) <= 1, f"destinations: {hit or 'none'}"


def _c_speech_rate(s, ctx):
    words, secs = 0, 0.0
    for it in _items(s):
        a, e = _win(it)
        n = len(_words(it.get("dialogue"))) + len(_words(it.get("rehook")))
        if n and a is not None and e > a:
            words += n
            secs += e - a
    if not secs:
        return False, "no timed speech"
    wps = words / secs
    return 2.0 <= wps <= 3.3, f"{wps * 60:.0f} wpm"


def _c_hashtags(s, ctx):
    tags = [t.lower() for t in re.findall(r"#(\w+)", s.get("caption") or "")]
    if not 1 <= len(tags) <= MAX_HASHTAGS:
        return False, f"{len(tags)} hashtags"
    if all(t in GENERIC_TAGS for t in tags):
        return False, f"generic-only tags {tags}"
    return True, f"{len(tags)} tags"


def _c_keyword_echo(s, ctx):
    kws = re.findall(r"\bcomment\s+([A-Z][A-Z0-9]{1,})\b", spoken_text(s))
    if not kws:
        return None, "n/a (no comment keyword)"
    cap = s.get("caption") or ""
    return kws[0] in cap, f"keyword {kws[0]}"


def _c_product_early(s, ctx):
    toks = {_stem(w) for w in _words(hook_line(s) + " " + frame0_overlay(s))}
    ok = bool(toks & ctx["anchors"])
    return ok, "named in hook/overlay" if ok else "prompt noun absent from hook"


def _c_comment_bait(s, ctx):
    for b in s.get("beats") or []:
        if b.get("type") == "COMMENT BAIT":
            d = b.get("dialogue") or ""
            ok = bool(re.search(r"\bcomment\s+[A-Z]{2,}", d)) or "?" in d
            return ok, d[:60]
    return False, "no COMMENT BAIT beat"


def _c_generic_bait(s, ctx):
    m = GENERIC_BAIT.search(viewer_text(s))
    return (m is None), (f"engagement bait {m.group(0)!r}" if m else "none")


def _c_absolute(s, ctx):
    m = ABSOLUTE.search(viewer_text(s))
    return (m is None), (f"absolute claim {m.group(0)!r}" if m else "none")


def _c_ai_disclosure(s, ctx):
    if s.get("presenter") != "ai":
        return None, "n/a (human presenter)"
    disc = str(s.get("disclosure") or "")
    cap = s.get("caption") or ""
    ok = bool(re.search(r"\bAI\b", disc)) and bool(re.search(r"\bAI\b", cap))
    return ok, "label + caption line" if ok else "AI disclosure missing"


def _c_part2(s, ctx):
    for b in s.get("beats") or []:
        if b.get("type") == "CTA" and re.search(r"\bpart (?:2|two)\b",
                                                b.get("dialogue") or "", re.I):
            if not s.get("series_plan"):
                return False, "promises an unplanned part 2"
    return True, "no dangling series promise"


# ---------------------------------------- pipeline v2.1 creative layer (R21+)
# Quality, not gates: an absent creative key FAILS its check (the gates are
# silent on absent keys; docs/CREATIVE-PLAN.md §0.2). Research tables are
# transcribed here independently of the builders' modules (evaluator-
# optimizer separation): hooks-deep-dive §1.4 ARCHETYPES priors, §2.6
# VISUAL_HOOKS, §3.6 VARIANT_POLICY, §4.1 HOOK_SCORE_FEATURES;
# shots-cinematography §5.2 SHOT_RULES.cadence.

ARCHETYPE_PRIOR = {  # (prior, ai_safe) — hooks-deep-dive §1.4 [A]
    "curiosity-gap": (0.55, True), "bold-claim": (0.55, True),
    "negative-command": (0.6, True), "proof-first": (0.65, True),
    "transformation": (0.7, True), "story-time": (0.35, False),
    "contrarian-reframe": (0.5, True), "identity-reveal": (0.45, "partial"),
    "problem-agitate": (0.6, True), "question": (0.4, True),
    "comparison": (0.65, True), "pov": (0.5, True), "newness": (0.65, True),
    "confession": (0.6, False), "price-anchor": (0.7, True),
    "listicle": (0.55, True), "challenge": (0.55, "partial"),
    "day-counter": (0.55, "partial"), "showcase": (0.85, True)}
VISUAL_HOOK_PRIOR = {  # (prior, best archetypes) — hooks-deep-dive §2.6 [M/A]
    "product-in-action": (0.85, ("showcase", "bold-claim", "negative-command",
                                 "curiosity-gap", "newness")),
    "result-reveal": (0.8, ("showcase", "transformation", "bold-claim", "proof-first")),
    "before-after-split": (0.7, ("transformation", "comparison", "day-counter")),
    "problem-state": (0.6, ("problem-agitate", "negative-command", "question",
                            "pov", "challenge")),
    "pov-hands": (0.6, ("pov", "showcase", "listicle")),
    "face-reaction": (0.6, ("confession", "story-time", "identity-reveal",
                            "problem-agitate")),
    "text-first": (0.55, ("question", "listicle", "proof-first",
                          "contrarian-reframe", "price-anchor", "identity-reveal")),
    "unboxing": (0.75, ("newness", "showcase", "price-anchor")),
    "comparison": (0.65, ("comparison", "price-anchor", "contrarian-reframe", "question")),
    "day-counter": (0.5, ("day-counter", "challenge", "transformation")),
    "satisfying-macro": (0.6, ("showcase", "curiosity-gap", "bold-claim"))}
PAYOFF_COMPAT = {  # VARIANT_POLICY.diversity.payoff_compat (D35)
    "verdict": ("question", "curiosity-gap", "comparison", "price-anchor",
                "showcase", "proof-first", "contrarian-reframe",
                "identity-reveal", "confession", "story-time"),
    "measurable-demo": ("showcase", "bold-claim", "negative-command",
                        "problem-agitate", "curiosity-gap", "comparison",
                        "proof-first", "pov", "newness"),
    "transformation": ("transformation", "day-counter", "bold-claim",
                       "problem-agitate", "showcase", "pov"),
    "list": ("listicle", "showcase", "curiosity-gap", "negative-command", "newness"),
    "streak": ("challenge", "day-counter", "story-time", "confession",
               "question", "transformation")}
VIBE_CADENCE = {  # SHOT_RULES.cadence: (avg_shot_s band, max_static_s) [A]
    "raw-ugc": ((2.0, 3.5), 3.5), "clean-aesthetic": ((2.0, 3.5), 3.0),
    "hype-energy": ((1.25, 2.0), 2.0), "cozy-calm": ((3.0, 5.0), 3.5),
    "expert-trust": ((2.5, 4.0), 3.5), "playful-comedic": ((1.25, 2.5), 2.5),
    "cinematic-premium": ((2.0, 4.0), 2.5), "asmr-satisfying": ((2.5, 5.0), 3.5),
    "story-vlog": ((2.0, 3.5), 3.0), "before-after-reveal": ((1.5, 3.0), 3.0)}
HOOK_PRIMARY_MIN, HOOK_ALT_MIN = 60, 50      # HOOK-08 (uncalibrated) [A]
VARIANT_MAX_JACCARD = 0.2                    # VARIANT_POLICY.diversity
KEYWORD_BY_S, CAPTION_KEYWORD_CHARS = 3.0, 60  # DISC-01 / DISC-03
AI_TOGGLES = {"tiktok": "is_aigc", "instagram": "is_ai_generated",
              "youtube_shorts": "containsSyntheticMedia"}
PLATFORM_FIELDS = {"tiktok": ("caption", "hashtags"),
                   "instagram": ("caption", "hashtags"),
                   "youtube_shorts": ("title", "description")}

NEG_WORDS = ("stop", "don't", "dont", "skip", "quit", "mistake", "wrong", "weak",
             "ruin", "fail", "flaw", "tired", "wasted", "lost")
NUM_RE = re.compile(r"\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b",
                    re.I)
RHETORICAL = re.compile(r"have you ever|did you know|guess what", re.I)
OPEN_LOOP = re.compile(r"here'?s (?:why|what|the)|what changed|which wins|verdict|"
                       r"check this|before you", re.I)
FILLER = re.compile(r"^(?:hey|hi|hello|okay|ok|alright|welcome)\b|^so,|"
                    r"in today.?s video|let me tell you|have you ever wondered", re.I)
HYPE = re.compile(r"\b(?:amazing|insane|crazy|unreal|mind-?blowing|obsessed|"
                  r"game.?changer|life.?changing)\b", re.I)
PAYOFF_ANSWER = re.compile(r"\b(?:verdict|result|results|answer|yes|no|worth|"
                           r"winner|wins|held|lasted)\b", re.I)
WE_RE = re.compile(r"\b(?:we|our|us)\b", re.I)
FEATURE_WEIGHTS = (  # (id, weight, sign) — HOOK_SCORE_FEATURES §4.1
    ("length_band", 0.06, 1), ("payload_first3", 0.09, 1),
    ("keyword_early", 0.07, 1), ("concrete_specific", 0.07, 1),
    ("negativity", 0.05, 1), ("first_person_human", 0.02, 1),
    ("second_person_selfref", 0.02, 1), ("question_form", 0.03, 1),
    ("open_loop_paired", 0.10, 1), ("novelty", 0.08, 1),
    ("readability", 0.02, 1), ("overlay_alignment", 0.06, 1),
    ("visual_type_strength", 0.08, 1), ("archetype_prior", 0.06, 1),
    ("we_pronoun", 0.02, -1), ("filler_greeting", 0.05, -1),
    ("vague_hype", 0.05, -1), ("clickbait_marker", 0.04, -1),
    ("fake_urgency", 0.03, -1))
BONUS_SUM = 0.81


def _syllables(w):
    w = re.sub(r"[^a-z]", "", w.lower())
    if not w:
        return 0
    n = len(re.findall(r"[aeiouy]+", w))
    if w.endswith("e") and not w.endswith(("le", "ee")) and n > 1:
        n -= 1
    return max(1, n)


def _tri(text, drop=()):
    w = [x for x in L.keyword_tokens(text) if x not in drop]
    return {tuple(w[i:i + 3]) for i in range(len(w) - 2)} or ({tuple(w)} if w else set())


def _jac(a, b, drop=()):
    A, B = _tri(a, drop), _tri(b, drop)
    return len(A & B) / len(A | B) if A and B else 0.0


def script_keyword(s):
    """The discovery primary keyword, else '' (R24 needs the real one)."""
    d = s.get("discovery")
    kw = d.get("primary_keyword") if isinstance(d, dict) else None
    return kw.strip() if isinstance(kw, str) else ""


def _product_tokens(s, kw=""):
    toks = {w for w in L.keyword_tokens(s.get("prompt") or "")
            if len(w) >= 3 and w not in L.KEYWORD_STOP and w not in STOP}
    return toks | {w for w in L.keyword_tokens(kw) if w not in L.KEYWORD_STOP}


def _payoff_text(s):
    return " ".join(str(b.get(k) or "") for b in s.get("beats") or []
                    if "PAYOFF" in str(b.get("type") or "").upper()
                    for k in ("dialogue", "on_screen"))


def hook_score(verbal, overlay, visual_type, archetype, s, others=()):
    """Independent HOOK_SCORE_FEATURES scorer (hooks-deep-dive §4.1) ->
    (score 0-100, {feature: x}, [top reasons]). Detectors are this module's
    own; `others` are the script's other openings (novelty is a within-script
    proxy: no shipped-hook history exists in a single-script rubric)."""
    h = (verbal or "").strip()
    toks = L.norm(h).split()
    n = len(L.words(h))
    kw = script_keyword(s)
    prod = _product_tokens(s, kw)
    ktoks = L.keyword_tokens(h)
    prompt = s.get("prompt") or ""
    f = {}
    f["length_band"] = 1.0 if 4 <= n <= 8 else 0.6 if n == 3 else 0.0
    first3 = set(L.keyword_tokens(" ".join(toks[:3])))
    nxt = set(L.keyword_tokens(" ".join(toks[3:5])))
    f["payload_first3"] = 1.0 if (first3 & prod or re.search(r"\d", " ".join(toks[:3]))) \
        else 0.5 if nxt & prod else 0.0
    head = (L.keyword_tokens(kw)
            or [w for w in L.keyword_tokens(prompt) if w in prod] or [""])[-1]
    if kw:
        f["keyword_early"] = 1.0 if L.keyword_in(h, kw, loose=True) else 0.0
    else:
        f["keyword_early"] = 1.0 if head and head in ktoks else 0.0
    f["concrete_specific"] = min(1.0, 0.5 * bool(NUM_RE.search(h))
                                 + 0.5 * bool(set(ktoks) & prod))
    neg = sum(1 for w in toks if w.replace("’", "'").startswith(NEG_WORDS))
    f["negativity"] = {0: 0.0, 1: 1.0, 2: 0.8}.get(neg, 0.4)
    f["first_person_human"] = 1.0 if s.get("presenter") == "human" and \
        re.search(r"\b(?:I|my|me)\b", h) else 0.0
    f["second_person_selfref"] = 1.0 if re.search(r"\byour?\b", h, re.I) and (
        h.endswith("?") or re.match(r"if you\b", h, re.I)) else 0.0
    if "?" in h:
        f["question_form"] = 1.0 if ((kw and L.keyword_in(h, kw, loose=True))
                                     or set(ktoks) & prod or NUM_RE.search(h)) \
            and not RHETORICAL.search(h) else -1.0
    else:
        f["question_form"] = 0.0
    loop = "?" in h or bool(OPEN_LOOP.search(h))
    pay = _payoff_text(s)
    content = {w for w in ktoks if len(w) >= 4 and w not in STOP}
    paid = bool(content & set(L.keyword_tokens(pay))) or (
        "?" in h and bool(PAYOFF_ANSWER.search(pay)))
    f["open_loop_paired"] = (1.0 if paid else -1.0) if loop else 0.3
    drop = set(L.keyword_tokens(kw)) | prod
    sims = [_jac(h, o, drop) for o in others if o]
    same3 = any(L.norm(o).split()[:3] == toks[:3] for o in others if o)
    f["novelty"] = 0.0 if same3 else 1.0 - max(sims or [0.0])
    plain = [w for w in ktoks if w not in prod]
    syl = sum(_syllables(w) for w in plain) / max(1, len(plain))
    f["readability"] = 1.0 if syl <= 1.6 and h.count(",") <= 1 else 0.0
    ov = (overlay or "").strip()
    if not ov:
        f["overlay_alignment"] = 0.0
    else:
        ok, why = overlay_is_clean(ov, h)
        has_head = bool(head) and head in L.keyword_tokens(ov)
        f["overlay_alignment"] = 0.0 if not ok else 1.0 if has_head else \
            0.8 if why in ("label pair", "label form") else 0.6
    vp, best = VISUAL_HOOK_PRIOR.get(visual_type or "", (0.0, ()))
    f["visual_type_strength"] = vp * (1.0 if archetype in best else 0.6)
    ap, safe = ARCHETYPE_PRIOR.get(archetype or "", (0.0, True))
    req_ok = not ((archetype == "price-anchor" and not L.price_in(prompt))
                  or (archetype == "proof-first" and not L.proof_in(prompt)))
    ai_ok = s.get("presenter") != "ai" or safe is not False
    f["archetype_prior"] = ap if req_ok and ai_ok else 0.0
    f["we_pronoun"] = 1.0 if WE_RE.search(h) else 0.0
    f["filler_greeting"] = 1.0 if FILLER.search(h) else 0.0
    f["vague_hype"] = 1.0 if (SLOP.search(h) or VAGUE_HOOK.search(h)
                              or HYPE.search(h)) else 0.0
    f["clickbait_marker"] = 1.0 if L.clickbait_hits(h + "\n" + ov) else 0.0
    f["fake_urgency"] = 1.0 if L.offer_urgency_hits(h + "\n" + ov, prompt) else 0.0
    raw = sum(w * sign * f[k] for k, w, sign in FEATURE_WEIGHTS)
    score = round(100 * max(0.0, min(1.0, raw / BONUS_SUM)))
    pts = sorted(((100 * w * sign * f[k] / BONUS_SUM, k) for k, w, sign
                  in FEATURE_WEIGHTS if f[k]), key=lambda x: -abs(x[0]))
    return score, f, [f"{k} {p:+.0f}" for p, k in pts[:3]]


def _variants(s):
    hv = s.get("hook_variants")
    if not isinstance(hv, list):
        return None
    return [v for v in hv if isinstance(v, dict)]


def _c_direction(s, ctx):
    from vsp import creative_vocab as CV
    from vsp import rules as RL
    d = s.get("direction")
    if not isinstance(d, dict):
        return False, "no direction"
    probs = []
    miss = [k for k in ("vibe", "tone", "pacing", "energy_curve", "music", "voice")
            if not d.get(k)]
    if miss:
        probs.append(f"missing {miss}")
    errs = RL.check_d156(s, None, RL.build_ctx(s))
    if errs:
        probs.append(f"{len(errs)} D156 problem(s)")
    vibe = d.get("vibe")
    pac = d.get("pacing") if isinstance(d.get("pacing"), dict) else {}
    band = VIBE_CADENCE.get(vibe)
    avg = pac.get("avg_shot_s")
    if band and isinstance(avg, list) and len(avg) == 2 and all(
            isinstance(x, (int, float)) for x in avg):
        if avg[1] < band[0][0] or avg[0] > band[0][1]:
            probs.append(f"avg_shot_s {avg} outside the {vibe} band {list(band[0])}")
        ms = pac.get("max_static_s")
        if isinstance(ms, (int, float)) and ms > band[1]:
            probs.append(f"max_static_s {ms} > {vibe} {band[1]}")
    tone = d.get("tone") if isinstance(d.get("tone"), dict) else {}
    if tone.get("allowed") and tone.get("voice") not in tone["allowed"]:
        probs.append("tone.voice not in tone.allowed")
    if s.get("presenter") == "ai" and vibe == "story-vlog":
        probs.append("story-vlog vibe on an AI presenter (VTM9)")
    if vibe and vibe not in CV.VIBES:
        probs.append(f"unknown vibe {vibe!r}")
    return (not probs), "; ".join(probs) or f"{vibe}, coherent"


def _c_variants(s, ctx):
    vs = _variants(s)
    if vs is None:
        return False, "no hook_variants"
    n = len(vs)
    probs = []
    if not 3 <= n <= 5:
        probs.append(f"{n} variants")
    vt = [v.get("visual_type") for v in vs]
    arcs = [v.get("archetype") for v in vs]
    f3 = [tuple(L.norm(v.get("verbal") or "").split()[:3]) for v in vs]
    ovs = [L.norm(v.get("overlay") or "") for v in vs if (v.get("overlay") or "").strip()]
    if len(set(vt)) < n:
        probs.append("repeated visual_type")
    if len(set(arcs)) < min(3, n):
        probs.append(f"{len(set(arcs))} archetypes")
    if len(set(f3)) < n:
        probs.append("repeated first three words")
    if len(set(ovs)) < len(ovs):
        probs.append("repeated overlay")
    return (not probs), "; ".join(probs) or f"{n} variants, {len(set(arcs))} archetypes"


def _c_hook_strength(s, ctx):
    vs = _variants(s)
    if not vs:
        return False, "no hook_variants"
    verbals = [v.get("verbal") or "" for v in vs]
    scores = []
    for i, v in enumerate(vs):
        sc, _, why = hook_score(v.get("verbal"), v.get("overlay"),
                                v.get("visual_type"), v.get("archetype"), s,
                                others=verbals[:i] + verbals[i + 1:])
        scores.append((v.get("id") or str(i), sc, why))
    prim = next((x for v, x in zip(vs, scores) if v.get("is_primary")), scores[0])
    alts = [x for x in scores if x is not prim]
    ok = prim[1] >= HOOK_PRIMARY_MIN and all(x[1] >= HOOK_ALT_MIN for x in alts)
    return ok, (f"primary {prim[0]} {prim[1]} ({', '.join(prim[2])}); alternates "
                + ", ".join(f"{x[0]} {x[1]}" for x in alts))


def keyword_placement(s):
    """D161 -> (pass, detail): the discovery primary keyword is spoken or on
    screen by 3.0 s (DISC-01/02: exact or all content lemmas), sits in the
    first 60 chars of caption line 1 (DISC-03), and one caption hashtag is
    the compact keyword (DISC-04)."""
    kw = script_keyword(s)
    if not kw:
        return False, "no discovery primary keyword"
    early = []
    for it in s.get("hook_stack") or []:
        early += [it.get("dialogue"), it.get("on_screen")]
    for b in s.get("beats") or []:
        a, e = _win(b)
        if a is not None and a < KEYWORD_BY_S - 1e-9:
            if e is not None and e <= KEYWORD_BY_S + 0.05:
                early.append(b.get("dialogue"))
            early.append(b.get("on_screen"))
    spoken = any(L.keyword_in(str(t or ""), kw, loose=True) for t in early)
    cap = s.get("caption") or ""
    line1 = next((ln.strip() for ln in cap.splitlines() if ln.strip()), "")
    in_cap = L.keyword_in(line1[:CAPTION_KEYWORD_CHARS], kw)
    ck = L.compact_tag(kw)
    tag = any(L.compact_tag(t) == ck for t in re.findall(r"#\w+", cap))
    miss = [m for m, ok in (("by 3.0 s", spoken), ("caption line 1 [:60]", in_cap),
                            ("hashtag #" + ck, tag)) if not ok]
    return (not miss), (f"{kw!r} missing: {', '.join(miss)}" if miss
                        else f"{kw!r} placed")


def _c_keyword_placement(s, ctx):
    return keyword_placement(s)


def _c_discovery_complete(s, ctx):
    from vsp import rules as RL
    d = s.get("discovery")
    if not isinstance(d, dict):
        return False, "no discovery"
    probs = []
    if not script_keyword(s):
        probs.append("no primary_keyword")
    plats = d.get("platforms") if isinstance(d.get("platforms"), dict) else {}
    for p, fields in PLATFORM_FIELDS.items():
        e = plats.get(p)
        if not isinstance(e, dict):
            probs.append(f"no {p}")
            continue
        miss = [k for k in fields if not e.get(k)]
        if miss:
            probs.append(f"{p} lacks {miss}")
        if s.get("presenter") == "ai":
            tog = e.get("toggles") if isinstance(e.get("toggles"), dict) else {}
            if tog.get(AI_TOGGLES[p]) is not True:
                probs.append(f"{p} {AI_TOGGLES[p]} not true")
    cov = d.get("cover") if isinstance(d.get("cover"), dict) else {}
    if not (str(cov.get("text") or "").strip() and len(str(cov.get("text")).split()) <= 5
            and isinstance(cov.get("frame_s"), (int, float))):
        probs.append("cover frame/text")
    errs = RL.check_d155(s, None, RL.build_ctx(s))
    if errs:
        probs.append(f"{len(errs)} D155 problem(s)")
    return (not probs), "; ".join(probs) or "3 platforms + cover"


def payoff_types(s):
    """The payoff types a script can pay (union of format, prompt and PAYOFF
    signals) — this rubric's own mapping onto VARIANT_POLICY payoff types."""
    fmt = s.get("format")
    types = set({"demo": ("measurable-demo",), "review": ("verdict",),
                 "transformation": ("transformation",),
                 "talking-head": ("verdict",),
                 "pov-vlog": ("verdict", "transformation")}.get(fmt, ("verdict",)))
    p = (s.get("prompt") or "").lower()
    pay = _payoff_text(s).lower()
    if re.search(r"\bthings\b|\bitems\b|\bessentials\b|\bmust[- ]haves?\b|"
                 r"\b\d+ (?:things|products|picks|items|tools)\b", p):
        types.add("list")
    if re.search(r"\b\d+ days?\b|\bday \d+\b|\bstopped\b|\bquit\b|\bwithout\b|"
                 r"\bchallenge\b|\bstreak\b|\broutine\b", p):
        types.add("streak")
    if re.search(r"\bbefore\b|\bafter\b|\bday \d+\b", pay):
        types.add("transformation")
    if re.search(r"\bverdict\b|\bworth it\b", pay):
        types.add("verdict")
    if re.search(r"\btest\b|\bresult\b|\bheld\b|\d", pay):
        types.add("measurable-demo")
    return types


def _c_payoff_compat(s, ctx):
    vs = _variants(s)
    if not vs:
        return False, "no hook_variants"
    types = payoff_types(s)
    ok_arcs = {a for t in types for a in PAYOFF_COMPAT[t]}
    bad = [f"{v.get('id')}:{v.get('archetype')}" for v in vs
           if v.get("archetype") not in ok_arcs]
    return (not bad), (f"unpaid archetypes {bad} for {sorted(types)}" if bad
                       else f"all paid by {sorted(types)}")


def _c_variant_jaccard(s, ctx):
    vs = _variants(s)
    if not vs:
        return False, "no hook_variants"
    drop = set(L.keyword_tokens(script_keyword(s))) | _product_tokens(s)
    worst = (0.0, "")
    for i in range(len(vs)):
        for j in range(i + 1, len(vs)):
            jv = _jac(vs[i].get("verbal") or "", vs[j].get("verbal") or "", drop)
            if jv > worst[0]:
                worst = (jv, f"{vs[i].get('id')}/{vs[j].get('id')}")
    return worst[0] <= VARIANT_MAX_JACCARD, (f"max trigram Jaccard {worst[0]:.2f}"
                                             + (f" ({worst[1]})" if worst[1] else ""))


def _c_clickbait(s, ctx):
    texts = [hook_line(s), frame0_overlay(s),
             next((ln for ln in (s.get("caption") or "").splitlines() if ln.strip()), "")]
    for v in _variants(s) or []:
        texts += [v.get("verbal"), v.get("overlay"), v.get("caption_line")]
    hits = [h for t in texts for h in L.clickbait_hits(str(t or ""))
            if h[1] == "error"]
    return (not hits), (f"clickbait {hits[0][0]} {hits[0][2]!r}" if hits else "none")


# (id, title, tier, weight, audit_only, fn)
CHECKS = [
    ("R01", "verbal hook <= 8 words", "E", 3, False, _c_hook_len),
    ("R02", "hook is specific (no fallback/vague)", "E", 3, False, _c_hook_specific),
    ("R03", "timeline performable (no gap/overlap/overrun/overflow)", "E", 3, False, _c_timeline),
    ("R04", "payoff lands 68-88% through", "I", 2, False, _c_payoff_place),
    ("R05", "no invented prices / social proof", "E", 3, False, _c_claims),
    ("R06", "AI persona makes no lived-experience claims", "E", 3, False, _c_ai_first_person),
    ("R07", "no template leaks / broken casing", "E", 3, False, _c_leaks),
    ("R08", "frame-0 overlay is a clean <=3-word phrase", "I", 2, False, _c_frame0),
    ("R09", "on-screen text readable (<=12 words, <=20 cps)", "I", 2, False, _c_onscreen),
    ("R10", "re-hooks present and never repeated", "I", 2, False, _c_rehooks),
    ("R11", "one link destination", "I", 2, False, _c_single_cta),
    ("R12", "speech rate 120-198 wpm", "O", 1, True, _c_speech_rate),
    ("R13", "1-5 hashtags, not generic-only", "I", 2, False, _c_hashtags),
    ("R14", "caption echoes the comment keyword", "O", 1, False, _c_keyword_echo),
    ("R15", "product/concept named in hook or overlay", "I", 2, True, _c_product_early),
    ("R16", "AI disclosure (label + caption line)", "E", 3, False, _c_ai_disclosure),
    ("R17", "comment bait is specific", "O", 1, True, _c_comment_bait),
    ("R18", "no generic engagement bait", "I", 2, False, _c_generic_bait),
    ("R19", "no absolute / guarantee claims", "I", 2, False, _c_absolute),
    ("R20", "no unplanned part-2 promise", "O", 1, False, _c_part2),
    # ---- pipeline v2.1 creative layer (RULES.md §68) — absent key = FAIL
    ("R21", "creative direction present and coherent (D156-clean, vibe cadence band, tone)", "I", 2, False, _c_direction),
    ("R22", ">= 3 hook variants, diverse (visual types, archetypes, first 3 words, overlays)", "I", 2, False, _c_variants),
    ("R23", "primary hook strength >= 60, alternates >= 50 (independent HOOK_SCORE_FEATURES scorer)", "I", 2, True, _c_hook_strength),
    ("R24", "D161 keyword placement: by 3.0 s, caption line-1 first 60 chars, one hashtag", "I", 2, False, _c_keyword_placement),
    ("R25", "discovery packaging complete (3 platforms, cover, AI toggles, D155-clean)", "I", 2, False, _c_discovery_complete),
    ("R26", "variant archetypes paid by the script's payoff (VARIANT_POLICY, D35)", "O", 1, True, _c_payoff_compat),
    ("R27", "variant openings not near-duplicates (trigram Jaccard <= 0.2)", "O", 1, True, _c_variant_jaccard),
    ("R28", "openings free of clickbait markers (RISKY_PHRASES CB-01..03)", "I", 2, True, _c_clickbait),
]

PITFALLS = [
    ("P1", "meta/rule leak in viewer text", lambda s: META_LEAK.search(viewer_text(s))),
    ("P2", "slop phrase", lambda s: SLOP.search(viewer_text(s))),
    ("P3", "same sentence twice", lambda s: _dup_sentence(s)),
]
PITFALL_COST = 4
AUDIT_PITFALLS = {"P2"}
LEGACY_IDS = frozenset(f"R{i:02d}" for i in range(1, 21))
RUBRIC_VERSION = "R01-R28 (pipeline v2.1)"


def _dup_sentence(s):
    seen = set()
    for it in _items(s):
        for sent in re.split(r"(?<=[.!?])\s+", it.get("dialogue") or ""):
            n = _norm(sent)
            if len(n.split()) >= 3:
                if n in seen:
                    return n
                seen.add(n)
    return None


def score(script):
    ctx = {"anchors": prompt_anchors(script.get("prompt") or "")}
    checks = []
    for cid, title, tier, w, audit, fn in CHECKS:
        try:
            ok, detail = fn(script, ctx)
        except Exception as e:  # a rubric bug must never kill a run
            ok, detail = False, f"check error: {e!r}"
        checks.append({"id": cid, "title": title, "tier": tier, "weight": w,
                       "audit": audit, "pass": ok, "detail": detail})
    pits = []
    for pid, title, fn in PITFALLS:
        m = fn(script)
        if m:
            hit = m.group(0) if hasattr(m, "group") else str(m)
            pits.append({"id": pid, "title": title, "hit": hit,
                         "audit": pid in AUDIT_PITFALLS})

    def _agg(sel):
        num = sum(c["weight"] for c in checks if sel(c) and c["pass"])
        den = sum(c["weight"] for c in checks if sel(c) and c["pass"] is not None)
        return 100.0 * num / den if den else 0.0

    sel_pen = PITFALL_COST * sum(1 for p in pits if not p["audit"])
    all_pen = PITFALL_COST * len(pits)
    selection = max(0.0, _agg(lambda c: not c["audit"]) - sel_pen)
    audit = _agg(lambda c: c["audit"])
    overall = max(0.0, _agg(lambda c: True) - all_pen)
    # the v2.0 scale (R01-R20 + pitfalls): comparable with result files
    # scored before the v2.1 checks existed (scorecard 'shippable' uses it)
    legacy = max(0.0, _agg(lambda c: c["id"] in LEGACY_IDS) - all_pen)
    flags = sorted({c["id"] for c in checks if c["pass"] is False
                    and c["id"] in ("R05", "R06", "R16", "R18", "R19")})
    return {"score": round(overall, 1), "selection_score": round(selection, 1),
            "audit_score": round(audit, 1), "checks": checks,
            "pitfalls": pits, "compliance_flags": flags,
            "legacy_score": round(legacy, 1), "version": RUBRIC_VERSION}


def summary_line(result):
    failed = [c["id"] for c in result["checks"] if c["pass"] is False]
    pits = [p["id"] for p in result["pitfalls"]]
    return (f"rubric {result['score']:.0f}/100 (selection "
            f"{result['selection_score']:.0f}, audit {result['audit_score']:.0f})"
            + (f" — failed {', '.join(failed)}" if failed else "")
            + (f" — pitfalls {', '.join(pits)}" if pits else ""))


if __name__ == "__main__":
    import json
    import sys
    res = score(json.load(open(sys.argv[1])))
    print(summary_line(res))
    for c in res["checks"]:
        mark = {True: "PASS", False: "FAIL", None: "n/a "}[c["pass"]]
        print(f"  {mark} {c['id']} {c['title']}: {c['detail']}")
    for p in res["pitfalls"]:
        print(f"  PIT  {p['id']} {p['title']}: {p['hit']!r}")
