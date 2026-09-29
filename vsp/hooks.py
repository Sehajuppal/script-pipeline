"""Hook variants (pipeline v2.1 creative layer, WS-HOOKS).

    variants(script, ctx=None, seed=None, maker=None) -> list | None
        script["hook_variants"] (docs/CREATIVE-PLAN.md §1.2): variant A is the
        script's own hook (VERBAL HOOK dialogue + VISUAL TRIGGER on_screen, its
        visual_type read from the real frame-0 direction); B..E are the best
        payoff-compatible alternates, rendered by the maker's own renderer,
        screened like the primary (D37/D136/D137/D139/D141/D158, D73, D144),
        chosen by maximal marginal relevance (score, then distinct visual type,
        archetype and first three words).
    score_hook(verbal, overlay, visual_type, script, ctx=None) -> (score, features, reasons)
        the explainable hook score (hooks-deep-dive §4: 19 weighted features,
        score = clamp(raw / 0.81, 0, 1)). It ranks openings WITHIN one script;
        it does not predict virality. Novelty is measured against the other
        variants of the same script (never global state), so it is
        deterministic.
    render_md(variants, script) -> str     hooks.md: variant table + protocol
    check_variants(variants, script, ctx=None) -> [problems]   the §1.2 rules
    selfcheck() -> (ok, lines)             hermetic, in-process

CLI:  python3 -m vsp.hooks selfcheck
      python3 -m vsp.hooks show "<prompt>" [--format F --presenter P --seed N]

Data: vsp/data/hooks.json (research tables verbatim + maker glue). Stdlib
only, Python >= 3.9, no network. Never consumes the maker's rng: the local rng
is random.Random(vsp.seeding.derive_seed(seed, "hooks")).
"""
import json
import os
import random
import re
import sys

from vsp import creative_vocab as CV
from vsp import lexicon as L
from vsp import seeding

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data",
                         "hooks.json")
SCHEMA_VERSION = 1
_DATA = {}


def data():
    """The parsed hooks.json (cached; read once per process)."""
    if not _DATA:
        with open(DATA_PATH, encoding="utf-8") as f:
            d = json.load(f)
        _DATA.update(d)
        _DATA["_risky"] = [
            dict(r, rx=re.compile(r["regex"], 0 if r["id"] == "CB-06" else re.I))
            for r in d["RISKY_PHRASES"]]
        # one-pass pre-check (the per-entry scan runs only on a hit)
        _DATA["_risky_any"] = (
            re.compile("|".join("(?:%s)" % r["regex"] for r in d["RISKY_PHRASES"]
                                if r["id"] != "CB-06"), re.I),
            re.compile("|".join("(?:%s)" % r["regex"] for r in d["RISKY_PHRASES"]
                                if r["id"] == "CB-06")))
        _DATA["_feat_w"] = {f["id"]: float(f["weight"])
                            for f in d["HOOK_SCORE_FEATURES"]}
        _DATA["_feat_dir"] = {f["id"]: f["direction"]
                              for f in d["HOOK_SCORE_FEATURES"]}
        _DATA["_bonus_sum"] = round(sum(
            float(f["weight"]) for f in d["HOOK_SCORE_FEATURES"]
            if f["direction"] != "-"), 6)
        compat = {k: list(v) for k, v in
                  d["VARIANT_POLICY"]["diversity"]["payoff_compat"].items()}
        compat.update(d["maker"]["payoff_compat_extra"])
        _DATA["_compat"] = compat
        clusters = {}
        for cl, arcs in d["VARIANT_POLICY"]["diversity"]["clusters"].items():
            for a in arcs:
                clusters[a] = cl
        _DATA["_cluster"] = clusters
    return _DATA


def payoff_compat():
    """{payoff type: [archetype ids]} (VARIANT_POLICY + the advice 'fix')."""
    return {k: list(v) for k, v in data()["_compat"].items()}


def cluster_of(archetype):
    return data()["_cluster"].get(archetype)


# ------------------------------------------------------------------ text
_STOP = frozenset("""a an the of to for on in at by with without from into and or
but is are was were be been it its this that these those your you my our their
his her i me we us so just then than as if at vs""".split())
_NUMWORDS = frozenset("one two three four five six seven eight nine ten".split())
_NUM_RX = re.compile(r"\b\d+(?:\.\d+)?\b|\b(?:one|two|three|four|five|six|seven|"
                     r"eight|nine|ten)\b", re.I)
_NEG = frozenset("""stop don't dont skip quit mistake mistakes wrong weak ruins ruin
ruined fail fails failed failing flaw flaws tired wasted lost""".split())
_LOOP = re.compile(r"here'?s (?:why|what|the)|what changed|which wins|verdict|"
                   r"check this|before you", re.I)
_RHETORICAL = re.compile(r"have you ever|did you know|guess what", re.I)
_FILLER = re.compile(r"^(?:hey|hi|hello|okay|ok|alright|welcome)\b|^so,|"
                     r"in today.?s video|let me tell you|have you ever wondered", re.I)
_HYPE = re.compile(r"\b(?:amazing|insane|crazy|unreal|mind-?blowing|obsessed|"
                   r"game.?changer|life.?changing)\b", re.I)
_WE = re.compile(r"\b(?:we|our|us)\b", re.I)
_FIRST_PERSON = re.compile(r"\bI(?:'m|'ve|'d|'ll|’m|’ve|’d|’ll)?\b|\b[Mm](?:y|e)\b")
# the maker's D137 first-person screen (viral_script_maker._HOOK_FIRST_PERSON)
_AI_PRONOUNS = re.compile(
    r"\bI(?:'m|'ve|'d|'ll|’m|’ve|’d|’ll)?\b|"
    r"\b(?:[Mm]e|[Mm]y|[Mm]ine|[Mm]yself|[Ww]e|[Oo]ur|[Uu]s)\b")
_YOU = re.compile(r"\byou(?:r)?\b", re.I)
_NEWNESS_PROMPT = re.compile(
    r"\b(?:new|newly|brand-new|just (?:launched|dropped|released)|launch(?:ed|ing)?|"
    r"release[ds]?|debut(?:s|ed)?|next-gen|gen \d|version \d|v\d|2\.0)\b", re.I)
_OFFER_PROMPT = re.compile(
    r"\b\d{1,2} ?% off\b|\b(?:sale|discount|coupon|promo(?:tion)?|deal|offer|"
    r"bogo|free shipping)\b", re.I)
_DEADLINE_PROMPT = re.compile(
    r"\b(?:ends?|until|through|thru|by|expires?|deadline|last day)\b.{0,20}"
    r"\b(?:\d|today|tonight|midnight|monday|tuesday|wednesday|thursday|friday|"
    r"saturday|sunday|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", re.I)


def _stem(w):
    w = w.lower().strip(".'’,:;!?")
    for suf in ("es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def toks(text):
    """Normalised tokens (vsp.lexicon.norm)."""
    return L.norm(text).split()


def first3(text):
    return " ".join(toks(text)[:3])


def _content_stems(text):
    return [_stem(t) for t in toks(text) if t not in _STOP and len(t) >= 2]


def _syllables(w):
    w = re.sub(r"[^a-z]", "", w.lower())
    if not w:
        return 0
    n = len(re.findall(r"[aeiouy]+", w))
    if w.endswith("e") and not w.endswith(("le", "ee", "ye")) and n > 1:
        n -= 1
    return max(1, n)


def trigrams(text, drop=()):
    t = [x for x in toks(text) if x not in _STOP and _stem(x) not in drop]
    if len(t) < 3:
        return {tuple(t)} if t else set()
    return {tuple(t[i:i + 3]) for i in range(len(t) - 2)}


def jaccard(a, b):
    u = a | b
    return len(a & b) / len(u) if u else 0.0


def a_an(text):
    """'a' -> 'an' before a vowel sound (letter-name acronyms like LED too)."""
    def fix(m):
        art, word = m.group(1), m.group(2)
        low = word.lower()
        vowel = low[:1] in "aeiou" and not re.match(r"(?:uni|use|usa|usb|eu|one|once)", low)
        if word.isupper() and len(word) > 1:
            vowel = word[0] in "AEFHILMNORSX"
        if low.startswith(("hour", "honest", "heir")):
            vowel = True
        if not vowel:
            return m.group(0)
        return ("An " if art == "A" else "an ") + word
    return re.sub(r"\b([Aa]) ([A-Za-z][\w'-]*)", fix, text)


# --------------------------------------------------------------- risky
def risky_hits(text, prompt="", classes=None, severity=None):
    """RISKY_PHRASES entries hit by `text` (hooks-deep-dive §5), minus the
    ones whose allow-path the prompt supplies: urgency/scarcity/offer need the
    offer (and deadline) in the prompt (D158); absolute and scarcity claims
    are allowed when the prompt makes the same claim. -> [entry ids]."""
    out = []
    t = text or ""
    any_ci, any_cs = data()["_risky_any"]
    if not (any_ci.search(t) or any_cs.search(t)):
        return out
    ptxt = prompt or ""
    offer = bool(_OFFER_PROMPT.search(ptxt))
    deadline = bool(_DEADLINE_PROMPT.search(ptxt))
    for r in data()["_risky"]:
        if classes and r["class"] not in classes:
            continue
        if severity and r["severity"] != severity:
            continue
        if not r["rx"].search(text or ""):
            continue
        if r["class"] == "urgency" and offer and (deadline or r["id"] == "UR-04"):
            continue          # D158 allow-path: the prompt supplies the offer
        if r["class"] in ("scarcity", "absolute") and r["rx"].search(ptxt):
            continue          # the prompt makes the same claim
        out.append(r["id"])
    return out


def prompt_has_offer(prompt):
    return bool(_OFFER_PROMPT.search(prompt or ""))


def prompt_has_newness(prompt):
    return bool(_NEWNESS_PROMPT.search(prompt or ""))


def screen_text(text, prompt, ai):
    """The §1.2 screens shared by verbal, overlay and caption_line. ->
    [problem strings] ([] = clean)."""
    t = text or ""
    p = prompt or ""
    out = []
    if "{" in t or "}" in t:
        out.append("raw slot brace")
    if L.PRICE.search(t) and not L.PRICE.search(p):
        out.append("D37 price not in the prompt")
    for rx in L.SOCIAL_PROOF:
        if rx.search(t) and not rx.search(p):
            out.append("D136 unsourced social proof")
            break
    if L.GENERIC_BAIT.search(t):
        out.append("D139 engagement bait")
    allowed = {m.group(0).lower() for m in L.ABSOLUTE.finditer(p)}
    for m in L.ABSOLUTE.finditer(t):
        if m.group(0).lower() not in allowed:
            out.append("D141 absolute claim")
            break
    if L.FALLBACK_HOOK.match(t.strip()) or L.VAGUE_HOOK.search(t) or L.SLOP.search(t):
        out.append("R02 vague/fallback/slop")
    hits = risky_hits(t, p, severity="error")
    if hits:
        out.append("D158/RISKY " + ",".join(hits))
    if ai:
        if L.first_match(L.AI_FIRST_PERSON, t):
            out.append("D137 AI lived experience")
        elif _AI_PRONOUNS.search(t):
            out.append("D137 AI first person")
    return out


# ------------------------------------------------------------ context
def _maker():
    m = sys.modules.get("viral_script_maker") or sys.modules.get("__main__")
    if m is not None and hasattr(m, "_render_hook_line"):
        return m
    try:
        import viral_script_maker as m  # noqa: F811
        return m
    except Exception:  # noqa: BLE001
        return None


def payoff_type(script=None, ctx=None):
    """verdict | measurable-demo | transformation | list | streak | fix — the
    payoff each (concept, format) branch of the maker's build_beats writes."""
    concept = (ctx or {}).get("concept") if ctx else None
    fmt = (ctx or {}).get("fmt") if ctx else None
    if script:
        fmt = fmt or script.get("format")
        if not concept:
            concept = _concept_of(script)
    table = data()["maker"]["payoff_by_concept"].get(concept or "product") or \
        data()["maker"]["payoff_by_concept"]["product"]
    return table.get(fmt or "", table["*"])


def _concept_of(script):
    fam = str(script.get("hook_family") or "")
    card = " ".join(str(b.get("on_screen") or "") for b in script.get("beats") or []
                    if isinstance(b, dict) and b.get("type") == "PAYOFF")
    if fam == "challenge" or re.search(r"\bstopping\b|\bfor \d+ days\b",
                                       str(script.get("prompt") or ""), re.I):
        return "challenge"
    if fam == "listicle" or "FULL LIST" in card:
        return "showcase"
    if "FIRST 3 SECONDS" in card:
        return "advice"
    if fam == "day-counter" and re.search(r"\broutine\b", str(script.get("prompt") or ""), re.I):
        return "routine"
    return "product"


def hook_info(script=None, ctx=None, maker=None):
    """Everything score_hook needs about the script, computed once."""
    ctx = ctx or {}
    script = script or {}
    maker = maker or _maker()
    presenter = str(ctx.get("presenter") or script.get("presenter") or "").strip().lower()
    prompt = str(ctx.get("prompt_text") or ctx.get("_prompt") or script.get("prompt") or "")
    concept = ctx.get("concept") or (_concept_of(script) if script else "product")
    kw, head, payload = keyword(ctx, maker)
    nums = set()
    for k in ("ndays", "span_n", "streak"):
        if ctx.get(k):
            nums.add(str(ctx[k]))
    pt = payoff_type(script, ctx) if (ctx or script) else "measurable-demo"
    if pt in ("measurable-demo", "verdict"):
        nums |= {"7", "seven"}
    if pt == "transformation":
        nums.add("1")
    if pt == "streak":
        nums |= {"1"}
    if pt == "fix":
        nums |= {"3", "three"}
    return {"presenter": presenter, "ai": presenter == "ai", "prompt": prompt,
            "concept": concept, "payoff": pt, "kw": kw, "head": head,
            "payload": payload, "nums": nums,
            "price": bool(ctx.get("price")) or bool(L.PRICE.search(prompt)),
            "proof": bool(ctx.get("proof")) or bool(L.first_match(L.SOCIAL_PROOF, prompt)),
            "newness": prompt_has_newness(prompt), "offer": prompt_has_offer(prompt)}


def keyword(ctx, maker=None):
    """(keyword content stems, head-noun stem, payload stems) for a ctx: the
    compound hook noun of a product (maker._hook_nouns), the challenge noun,
    the showcase domain + 'finds', the routine label, the advice category."""
    ctx = ctx or {}
    c = ctx.get("concept", "product")
    if c == "challenge":
        kwt = str(ctx.get("challenge_noun") or "")
        extra = []
    elif c == "showcase":
        kwt = f"{ctx.get('domain', '')} finds"
        extra = [str(ctx.get("domain") or "")]
    elif c == "routine":
        kwt = re.sub(r"(?i)^my\s+", "", str(ctx.get("routine_label") or ""))
        extra = [str(ctx.get("routine_time") or "")]
    elif c == "advice":
        kwt = str(ctx.get("category") or "")
        extra = [str(ctx.get("product") or "")]
    else:
        kwt = str(ctx.get("category") or ctx.get("product") or "")
        try:
            if maker is not None and ctx.get("product"):
                kwt = maker._hook_nouns(ctx)[0][1]
        except Exception:  # noqa: BLE001
            pass
        extra = [str(ctx.get("product") or ""), str(ctx.get("category") or "")]
    drop = {"day", "days", "every", "daily", "week", "weeks", "morning", "night"} \
        if c == "challenge" else set()
    kw = [s for s in _content_stems(kwt) if s not in drop and not s.isdigit()]
    head = kw[-1] if kw else ""
    payload = set(kw)
    for e in extra:
        payload |= {s for s in _content_stems(e) if not s.isdigit() and len(s) >= 3}
    return kw, head, payload


_PAYS = {
    "verdict": re.compile(r"\b(?:worth it|worth|verdict|buy or skip|or skip|keep or|"
                          r"kept|which wins|should you buy|buy it|honest|misjudged|"
                          r"wrong about)\b", re.I),
    "measurable-demo": re.compile(r"\b(?:check(?:ing)? this|check|before you|here'?s "
                                  r"(?:what|the|why)|test\w*|detail|watch|works?|"
                                  r"result|fail\w*|fix\w*|zero|revealed|job|action)\b", re.I),
    "transformation": re.compile(r"\b(?:after|before|day 1|day \d+|\d+ days|changed|"
                                 r"difference|vs)\b", re.I),
    "list": re.compile(r"\b(?:these|finds?|list|every|things|check this|here'?s what|"
                       r"asks? about|worth it)\b", re.I),
    "streak": re.compile(r"\b(?:day \d+|\d+ days|last|verdict|changed|streak|"
                         r"what happened|quit|without|no)\b", re.I),
    "fix": re.compile(r"\b(?:fix\w*|why|here'?s|mistakes?|explained|seconds|stop|"
                      r"fault)\b", re.I),
}


def pays(hook, info):
    """D5/D35: does the script's payoff pay this hook's promise? The loop
    must name what the payoff type delivers, and every number in the hook
    must be the payoff's own (day count, the 7-day test, the 3-second fix)."""
    pat = _PAYS.get(info["payoff"])
    if pat is None or not pat.search(hook):
        return False
    for m in _NUM_RX.finditer(hook):
        n = m.group(0).lower()
        if L.PRICE.search(hook) and n in re.sub(r"[^\d.]", " ", hook).split() and \
                re.search(r"[$€£]\s?" + re.escape(n), hook):
            continue          # the prompt's own price is not a measurable
        if n not in info["nums"]:
            return False
    return True


# ---------------------------------------------------------- score_hook
def _arch_ok(archetype, info):
    a = data()["ARCHETYPES"].get(archetype)
    if not a:
        return False
    if info["ai"] and a.get("ai_safe") is False:
        return False
    if archetype == "price-anchor" and not info["price"]:
        return False
    if archetype == "proof-first" and not info["proof"]:
        return False
    return True


def score_hook(verbal, overlay, visual_type, script, ctx=None, archetype=None,
               others=None, info=None):
    """-> (score 0-1, {feature id: x}, [reasons]) — hooks-deep-dive §4.1.
    `archetype` defaults to the matching variant's archetype in
    script["hook_variants"] (else the line's classified archetype);
    `others` (default: the other variants' verbals in script["hook_variants"])
    is what novelty is measured against. Deterministic."""
    d = data()
    info = info or hook_info(script, ctx)
    hook = " ".join(str(verbal or "").split())
    ov = " ".join(str(overlay or "").split())
    hv = [v for v in ((script or {}).get("hook_variants") or []) if isinstance(v, dict)]
    if archetype is None:
        archetype = next((v.get("archetype") for v in hv if v.get("verbal") == hook), None) \
            or classify(hook, payoff=info["payoff"])
    if others is None:
        others = [v.get("verbal") for v in hv if v.get("verbal") and v.get("verbal") != hook]
    t = toks(hook)
    stems = [_stem(x) for x in t]
    x = {}
    n = len(L.words(hook))
    x["length_band"] = 1.0 if 4 <= n <= 8 and 0.3 + n / 3.0 <= 3.0 else 0.6 if n == 3 else 0.0

    def payload_at(i):
        tok = t[i]
        return (stems[i] in info["payload"] and tok not in _STOP) or bool(
            re.match(r"\d", tok)) or tok in _NUMWORDS
    x["payload_first3"] = 1.0 if any(payload_at(i) for i in range(min(3, len(t)))) else \
        0.5 if any(payload_at(i) for i in range(3, min(5, len(t)))) else 0.0
    kw = info["kw"]
    x["keyword_early"] = 1.0 if kw and all(k in stems for k in kw) else 0.0
    has_num = bool(_NUM_RX.search(hook))
    has_noun = bool(info["head"]) and info["head"] in stems
    x["concrete_specific"] = min(1.0, 0.5 * has_num + 0.5 * has_noun)
    neg = sum(1 for tok in t if tok in _NEG)
    x["negativity"] = 1.0 if neg == 1 else 0.8 if neg == 2 else 0.4 if neg >= 3 else 0.0
    x["first_person_human"] = 1.0 if (not info["ai"] and info["presenter"] == "human"
                                       and _FIRST_PERSON.search(hook)) else 0.0
    q = hook.rstrip().endswith("?")
    x["second_person_selfref"] = 1.0 if _YOU.search(hook) and (
        q or re.match(r"(?i)\s*if you\b", hook)) else 0.0
    if "?" in hook:
        x["question_form"] = 1.0 if ((has_noun or has_num) and not _RHETORICAL.search(hook)) \
            else -1.0
    else:
        x["question_form"] = 0.0
    loop = "?" in hook or bool(_LOOP.search(hook))
    x["open_loop_paired"] = (1.0 if pays(hook, info) else -1.0) if loop else 0.3
    drop = set(kw)
    mine = trigrams(hook, drop)
    f3 = first3(hook)
    nov = 1.0
    for o in others or []:
        if first3(o) == f3:
            nov = 0.0
            break
        nov = min(nov, 1.0 - jaccard(mine, trigrams(o, drop)))
    x["novelty"] = round(nov, 4)
    plain = [w for w, s in zip(t, stems) if s not in info["payload"]] or t
    syl = sum(_syllables(w) for w in plain) / max(1, len(plain))
    x["readability"] = 1.0 if syl <= 1.6 and hook.count(",") <= 1 else 0.0
    if ov:
        ok, why = L.overlay_is_clean(ov, hook)
        ovs = {_stem(w) for w in toks(ov)}
        x["overlay_alignment"] = 0.0 if not ok else 1.0 if info["head"] and \
            info["head"] in ovs else 0.8 if "label" in why else 0.6
    else:
        x["overlay_alignment"] = 0.0
    vh = d["VISUAL_HOOKS"].get(visual_type or "")
    x["visual_type_strength"] = round(float(vh["prior"]) * (
        1.0 if archetype in vh["best_archetypes"] else 0.6), 4) if vh else 0.0
    arc = d["ARCHETYPES"].get(archetype or "")
    x["archetype_prior"] = float(arc["prior"]) if arc and _arch_ok(archetype, info) else 0.0
    x["we_pronoun"] = 1.0 if _WE.search(hook) else 0.0
    x["filler_greeting"] = 1.0 if _FILLER.search(hook.strip()) else 0.0
    x["vague_hype"] = 1.0 if (L.SLOP.search(hook) or L.VAGUE_HOOK.search(hook)
                              or _HYPE.search(hook)) else 0.0
    x["clickbait_marker"] = 1.0 if risky_hits(hook, "", classes=("clickbait",)) else 0.0
    x["fake_urgency"] = 1.0 if (not info["offer"] and risky_hits(
        hook, "", classes=("urgency", "scarcity"))) else 0.0
    w, dirn, bsum = d["_feat_w"], d["_feat_dir"], d["_bonus_sum"]
    raw = 0.0
    pts = []
    for f in d["HOOK_SCORE_FEATURES"]:
        fid = f["id"]
        sign = -1.0 if dirn[fid] == "-" else 1.0
        contrib = sign * w[fid] * x[fid]
        raw += contrib
        p = 100.0 * contrib / bsum
        if abs(p) >= 0.05:
            pts.append((p, fid))
    score = round(100 * max(0.0, min(1.0, raw / bsum))) / 100.0
    order = [f["id"] for f in d["HOOK_SCORE_FEATURES"]]
    pts.sort(key=lambda pf: (-abs(pf[0]), order.index(pf[1])))
    reasons = [f"{p:+.1f} {fid}: {_REASON.get(fid, fid)}" for p, fid in pts[:6]]
    feats = {f["id"]: round(float(x[f["id"]]), 4) for f in d["HOOK_SCORE_FEATURES"]}
    return score, feats, reasons


_REASON = {
    "length_band": "4-8 words, sayable inside the 3 s hook window",
    "payload_first3": "product, category or a number in the first words",
    "keyword_early": "keyword spoken by 3.0 s (search)",
    "concrete_specific": "concrete noun and/or number",
    "negativity": "one concrete negative word",
    "first_person_human": "first person, human presenter",
    "second_person_selfref": "self-referencing 'you' question",
    "question_form": "specific answerable question (negative when vague)",
    "open_loop_paired": "open loop the payoff pays (negative when unpaid)",
    "novelty": "differs from the other openings",
    "readability": "easy to hear once",
    "overlay_alignment": "frame-0 card is a hook phrase with the keyword",
    "visual_type_strength": "frame-0 visual prior and archetype fit",
    "archetype_prior": "research prior of the archetype",
    "we_pronoun": "'we/our' framing",
    "filler_greeting": "greeting or delay opener",
    "vague_hype": "empty hype",
    "clickbait_marker": "clickbait phrasing",
    "fake_urgency": "urgency or scarcity without an offer",
}


# ------------------------------------------------------------ frame 0
def frame0_visual_type(ctx):
    """The VISUAL_TYPES id of the frame 0 build_beats writes for this ctx
    (the VISUAL TRIGGER direction): the showcase tracking shot with the first
    find in hand and the product mid-action are product-in-action, the
    transformation split is before-after-split, a practice streak and a
    routine's lit clock open on their day marker, an abstinence challenge on
    the problem state, advice on a text card over the creator."""
    ctx = ctx or {}
    c = ctx.get("concept", "product")
    fmt = ctx.get("fmt")
    if c == "showcase":
        return "product-in-action"
    if c == "product":
        return "before-after-split" if fmt == "transformation" else "product-in-action"
    if c == "challenge":
        return "day-counter" if ctx.get("challenge_type") == "practice" else "problem-state"
    if c == "routine":
        return "day-counter"
    return "text-first"


_DIRECTION_VT = (
    (re.compile(r"BEFORE/AFTER split-screen|split[- ]screen", re.I), "before-after-split"),
    (re.compile(r"tracking shot through|MID-ACTION: hands on|hands on .+ in motion", re.I),
     "product-in-action"),
    (re.compile(r"of the streak full-frame|day-counter on screen", re.I), "day-counter"),
    (re.compile(r"alarm clock / phone screen", re.I), "day-counter"),
    (re.compile(r"problem state full-frame", re.I), "problem-state"),
    (re.compile(r"creator mid-gesture|text overlay already up", re.I), "text-first"),
)


def visual_type_of_direction(direction):
    """VISUAL_TYPES id described by a VISUAL TRIGGER direction text."""
    for rx, vt in _DIRECTION_VT:
        if rx.search(direction or ""):
            return vt
    return "product-in-action" if re.search(r"\bhands?\b", direction or "", re.I) \
        else "text-first"


# ------------------------------------------------------------ classify
_CLASSIFY = (
    (re.compile(r"^\s*pov\b", re.I), "pov"),
    (re.compile(r"^\s*(?:confession\b|honestly\?|i was wrong|i almost didn'?t|"
                r"embarrassing|i didn'?t think)", re.I), "confession"),
    (re.compile(r"^\s*(?:so i\b|story time|why i kept|i didn'?t expect|quick story)",
                re.I), "story-time"),
    (re.compile(r"^\s*(?:proof first|here'?s the receipt|start with the numbers)|"
                r"\bscorecard\b", re.I), "proof-first"),
    (re.compile(r"[$€£]\s?\d"), "price-anchor"),
    (re.compile(r"\bfirst look\b|\bnew\b", re.I), "newness"),
    (re.compile(r"^\s*(?:stop|don'?t|skip|quit)\b|\busing .* wrong\b|\bmistake\b",
                re.I), "negative-command"),
    (re.compile(r"\btired of\b|\bagain\?|\bkeep failing\b|\bruins\b|\bnot your fault\b",
                re.I), "problem-agitate"),
    (re.compile(r"\bday 1 vs day\b|\bbefore\b.*\bafter\b|\bthe after\b", re.I),
     "transformation"),
    (re.compile(r"\bvs\.?\b|\bside by side\b|\bwhich wins\b", re.I), "comparison"),
    (re.compile(r"^\s*day \d+\b|\blog, day\b", re.I), "day-counter"),
    (re.compile(r"\?\s*$"), "question"),
    (re.compile(r"^\s*\d+ \w+ (?:checks|ways|mistakes|things|finds|fixes)\b", re.I),
     "listicle"),
    (re.compile(r"\bin action\b|\bstart to finish\b|\bdoing (?:its|their) job\b|"
                r"^\s*watch\b|\bfinds\b", re.I), "showcase"),
    (re.compile(r"\bdays? (?:without|with no|of)\b|\bi (?:quit|stopped)\b", re.I),
     "challenge"),
    (re.compile(r"\bmost \w+(?: \w+)? fail\b|\bzero\b|\bno regrets\b", re.I),
     "bold-claim"),
)


def classify(line, family=None, payoff=None):
    """Best-effort archetype of a rendered hook line: the first matching
    form that the payoff type pays; the maker family when it is an archetype
    and compatible; else the first form, the family, or curiosity-gap."""
    compat = data()["_compat"].get(payoff or "", None)
    cands = [a for rx, a in _CLASSIFY if rx.search(line or "")]
    if family in CV.HOOK_ARCHETYPES:
        cands.append(family)
    cands.append("curiosity-gap")
    if compat:
        for a in cands:
            if a in compat:
                return a
    if family in CV.HOOK_ARCHETYPES:
        return family
    return cands[0]
