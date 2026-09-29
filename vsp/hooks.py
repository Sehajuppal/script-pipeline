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


_MEMO_MAX = 50000
_SCREEN_MEMO = {}
_BASE_MEMO = {}
_OV_MEMO = {}


def _memo(table, key, fn):
    hit = table.get(key)
    if hit is None:
        if len(table) > _MEMO_MAX:
            table.clear()
        hit = table[key] = fn()
    return hit


def screen_text(text, prompt, ai):
    """The §1.2 screens shared by verbal, overlay and caption_line. ->
    [problem strings] ([] = clean). Pure; memoised."""
    return list(_memo(_SCREEN_MEMO, (text or "", prompt or "", bool(ai)),
                      lambda: tuple(_screen_text(text, prompt, ai))))


def _screen_text(text, prompt, ai):
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
    """The maker's concept for a script: its own parse of the prompt when the
    maker is importable, else what the payoff card and family show."""
    m = _maker()
    prompt = re.sub(r"\s+", " ", re.sub(r"[{}]", "", str(script.get("prompt") or ""))).strip()
    if m is not None and prompt:
        try:
            return m.parse_prompt(prompt).get("concept") or "product"
        except Exception:  # noqa: BLE001
            pass
    fam = str(script.get("hook_family") or "")
    card = " ".join(str(b.get("on_screen") or "") for b in script.get("beats") or []
                    if isinstance(b, dict) and b.get("type") == "PAYOFF")
    if fam == "challenge" or re.search(r"\bstopping\b|\bfor \d+ days\b",
                                       str(script.get("prompt") or ""), re.I):
        return "challenge"
    if "FIRST 3 SECONDS" in card:
        return "advice"
    if fam == "listicle" or "FULL LIST" in card:
        return "showcase"
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
                                  r"result|fail\w*|fix\w*|zero|revealed|job|action|"
                                  r"break\w*|broke\w*|week|held|showed)\b", re.I),
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
    x = dict(_memo(_BASE_MEMO, (hook, ov, _info_key(info)),
                   lambda: _base_features(hook, ov, info)))
    arc = d["ARCHETYPES"].get(archetype or "")
    x["archetype_prior"] = float(arc["prior"]) if arc and _arch_ok(archetype, info) else 0.0
    kw = info["kw"]
    drop = set(kw)
    f3 = first3(hook)
    nov = 1.0
    if others:
        mine = trigrams(hook, drop)
        for o in others:
            if first3(o) == f3:
                nov = 0.0
                break
            nov = min(nov, 1.0 - jaccard(mine, trigrams(o, drop)))
    x["novelty"] = round(nov, 4)
    vh = d["VISUAL_HOOKS"].get(visual_type or "")
    x["visual_type_strength"] = round(float(vh["prior"]) * (
        1.0 if archetype in vh["best_archetypes"] else 0.6), 4) if vh else 0.0
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


def _info_key(info):
    return (info["presenter"], info["payoff"], tuple(info["kw"]), info["head"],
            tuple(sorted(info["payload"])), tuple(sorted(info["nums"])), info["price"],
            info["proof"], info["newness"], info["offer"])


def _base_features(hook, ov, info):
    """Every feature but novelty, visual_type_strength and archetype_prior
    (those depend on the other variants, the frame-0 type and the
    archetype) — pure, memoised."""
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
    x["we_pronoun"] = 1.0 if _WE.search(hook) else 0.0
    x["filler_greeting"] = 1.0 if _FILLER.search(hook.strip()) else 0.0
    x["vague_hype"] = 1.0 if (L.SLOP.search(hook) or L.VAGUE_HOOK.search(hook)
                              or _HYPE.search(hook)) else 0.0
    x["clickbait_marker"] = 1.0 if risky_hits(hook, "", classes=("clickbait",)) else 0.0
    x["fake_urgency"] = 1.0 if (not info["offer"] and risky_hits(
        hook, "", classes=("urgency", "scarcity"))) else 0.0
    return x


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


# ------------------------------------------------------------ variants
IDS = "ABCDE"
MAX_VARIANTS = 5            # VARIANT_POLICY.count.total_max
MIN_VARIANTS = 3            # §1.2: 3-5 variants
MMR_LAMBDA = 0.7            # score first, then diversity (MMR)
MAX_JACCARD = 0.2           # VARIANT_POLICY.diversity.max_trigram_jaccard
MAX_PER_CLUSTER = 2         # VARIANT_POLICY.diversity.max_per_cluster
_AFTER_RX = re.compile(r"\bafter\b|\bbefore\b|\bday 1 vs day\b|\blater\b|\b\d+ days\b|"
                       r"\bday \d+\b|\bresult\b", re.I)
_DAYN_RX = re.compile(r"\bday (\d+)\b|\b(\d+) days\b", re.I)
_ALT_RX = re.compile(r"\bvs\.?\b|\bor\b|\bside by side\b|\btwo\b|\bwhich wins\b", re.I)
_MUTED_TAIL = re.compile(r"\s*Works muted \(85% watch sound-off\)\.?\s*$")


def variants(script, ctx=None, seed=None, maker=None):
    """script["hook_variants"] (docs/CREATIVE-PLAN.md §1.2) or None. Never
    raises: a script this cannot read (no hook stack, no maker) gets None."""
    try:
        return _variants(script, ctx, seed, maker)
    except Exception:  # noqa: BLE001 — the maker must never die on variants
        return None


def _hook_items(script):
    hs = [it for it in (script.get("hook_stack") or []) if isinstance(it, dict)]
    vt = next((it for it in hs if str(it.get("type", "")).upper() == "VISUAL TRIGGER"), None)
    vh = next((it for it in hs if "VERBAL HOOK" in str(it.get("type", "")).upper()
               and it.get("dialogue")), None)
    return vt, vh


def ctx_from_script(script, maker):
    """A parse context for a script without one (--script-json): the maker's
    parse of the prompt plus what the script itself states (format,
    presenter, the transformation day count)."""
    prompt = re.sub(r"\s+", " ", re.sub(r"[{}]", "", str(script.get("prompt") or ""))).strip()
    if not prompt:
        return None
    ctx = maker.parse_prompt(prompt)
    ctx["_prompt"] = script.get("prompt")
    ctx["fmt"] = script.get("format")
    ctx["presenter"] = script.get("presenter")
    blob = " ".join(str(it.get(k) or "") for it in (script.get("hook_stack") or [])
                    if isinstance(it, dict) for k in ("direction", "payoff_contract"))
    m = re.search(r"DAY 1 (?:vs|left, )\s*DAY (\d+)", blob, re.I)
    if ctx.get("fmt") == "transformation" and m:
        ctx["ndays"] = int(m.group(1))
    return ctx


def _group(concept):
    return "streak" if concept in ("challenge", "routine") else \
        "advice" if concept == "advice" else "product"


def _subject(ctx, maker):
    c = ctx.get("concept", "product")
    if c == "showcase":
        return f"the first {ctx.get('domain', 'space')} find"
    if c == "challenge":
        cn = _habit(ctx, maker)
        return (f"the streak of {cn}" if ctx.get("challenge_type") == "practice"
                else f"the streak without {cn}")
    if c == "routine":
        t = str(ctx.get("routine_time") or "")
        return f"the {t} routine" if t else "the routine"
    if c == "advice":
        return str(ctx.get("category") or "the topic")
    try:
        sp = maker._short_product(ctx)
    except Exception:  # noqa: BLE001
        sp = str(ctx.get("category") or "the product")
    return sp if re.match(r"(?i)(?:the|a|an|my|these|this)\b", sp) else f"the {sp}"


def _habit(ctx, maker):
    if ctx.get("concept") == "routine":
        return re.sub(r"(?i)^my\s+", "the ", str(ctx.get("routine_label") or "the routine"))
    cn = str(ctx.get("challenge_noun") or "the habit")
    try:
        cn = maker._proper(cn)
    except Exception:  # noqa: BLE001
        pass
    return cn


def _day_n(line, ctx):
    ns = [int(m.group(1) or m.group(2)) for m in _DAYN_RX.finditer(line or "")]
    if ns:
        return str(max(ns))
    for k in ("ndays", "span_n", "streak"):
        if ctx.get(k):
            return str(ctx[k])
    return "7"


def _visual_sentence(vt, ctx, maker, line, ai):
    m = data()["maker"]
    grp = _group(ctx.get("concept", "product"))
    table = m["visual_sentences"].get(grp) or m["visual_sentences"]["product"]
    tmpl = table.get(vt) or m["visual_sentences"]["product"].get(vt) or \
        "Frame 0: {subject} in motion from the first frame."
    out = tmpl.format(subject=_subject(ctx, maker), n=_day_n(line, ctx),
                      habit=_habit(ctx, maker))
    if ai and vt in m["ai_real_footage_visual_types"]:
        out += m["ai_visual_notes"]["real_footage"]
    elif ai and vt in ("product-in-action", "pov-hands", "satisfying-macro", "unboxing"):
        out += m["ai_visual_notes"]["render"]
    return out


def _audio(vt, ctx, ai):
    m = data()["maker"]
    cat = str(ctx.get("category") or "")
    if ctx.get("concept", "product") == "product" and any(
            k in cat for k in ("noise", "sound", "speaker", "audio", "headphone")):
        out = m["audio_product_cue"]
    else:
        out = m["audio_cues"].get(vt) or m["audio_cues"]["text-first"]
    return out + (m["ai_voice_cue"] if ai else "")


def _vt_options(arc, line, overlay, ctx, ai):
    """Frame-0 visual types that can honestly open this line, best first:
    the archetype's pairings (hooks-deep-dive §2.5), then any other type with
    prior >= 0.6 (HOOK-10); a label-pair card needs the split screen
    (D25/D135), a DAY-N marker needs the hook's own day count, a comparison
    frame needs an alternative the line names, face-reaction is human-only."""
    d = data()
    feas = d["maker"]["concept_visual_types"].get(ctx.get("concept", "product"),
                                                  d["maker"]["concept_visual_types"]["product"])
    if ctx.get("challenge_type") == "practice" or ctx.get("concept") == "routine":
        feas = [v for v in feas if v != "problem-state"]   # a streak being built
    if "|" in (overlay or ""):
        return ["before-after-split"] if "before-after-split" in feas else []
    order = list(d["PAIRINGS"].get(arc, []))
    rest = sorted((v for v in d["VISUAL_HOOKS"] if v not in order and
                   float(d["VISUAL_HOOKS"][v]["prior"]) >= 0.6),
                  key=lambda v: (-float(d["VISUAL_HOOKS"][v]["prior"]), v))
    out = []
    for vt in order + rest:
        if vt not in feas or (ai and vt in d["maker"]["ai_excluded_visual_types"]):
            continue
        if vt == "day-counter" and not _DAYN_RX.search(line):
            continue
        if vt == "before-after-split" and not (
                arc in ("transformation", "day-counter") and _AFTER_RX.search(line)):
            continue
        if vt == "comparison" and not _ALT_RX.search(line):
            continue
        if vt == "result-reveal" and not (_AFTER_RX.search(line) or arc in (
                "showcase", "bold-claim", "transformation", "proof-first", "curiosity-gap")):
            continue
        out.append(vt)
    return out


def _render_candidates(ctx, maker, seed, ai, payoff):
    """Every payoff-compatible template of the maker's own pool, rendered by
    the maker's renderer (local rng, the niche authority), screened exactly
    like the primary (maker._hook_template_ok / _hook_finish) plus §1.2."""
    rng = random.Random(seeding.derive_seed(seed, "hooks"))
    auth = getattr(maker, "NICHE_AUTHORITY", {}).get(ctx.get("niche"))
    pool = maker.hook_pool(ctx)
    focus = maker._hook_focus(ctx)
    levels = maker._hook_levels(ctx)
    prompt = str(ctx.get("prompt_text") or ctx.get("_prompt") or "")
    compat = set(data()["_compat"].get(payoff, ()))
    out, seen = [], set()
    for idx, (fam, line, req) in enumerate(pool):
        arc = maker._hook_template_ok(ctx, fam, line, req, ai, payoff, variant=True)
        if arc is None or arc not in compat:
            continue
        for lctx, pv, noun in levels:
            try:
                raw = maker._render_hook_line(lctx, rng, line, auth, pv, noun)
            except (KeyError, IndexError, ValueError):
                break
            res = maker._hook_finish(lctx, raw, ai, L, focus)
            if res == "stop":
                break
            if res == "next":
                continue
            r, _ov, anchored, ov_focus = res
            head = r.split(".")[0]
            ov = _memo(_OV_MEMO, (id(maker.overlay_truncate), head),
                       lambda: maker.overlay_truncate(head))
            if r in seen or not anchored or screen_text(r, prompt, ai) or \
                    not _card_has_content(ov):
                break
            seen.add(r)
            try:
                alts = [a for a in maker._template_archetypes(fam, line) if a in compat]
            except Exception:  # noqa: BLE001
                alts = []
            for a in [arc] + [a for a in alts if a != arc]:
                out.append({"family": fam, "archetype": a, "verbal": r, "overlay": ov,
                            "ov_focus": ov_focus, "template": line, "idx": idx})
            break
    return out


def _card_has_content(ov):
    """A card that names something: a label pair or a word of 3+ letters
    beyond function words ("AT" from "At $12.99: ..." is no card)."""
    if "|" in ov or ":" in ov:
        return True
    return any(len(w) >= 3 and w not in _STOP for w in toks(ov))


def _load_priors():
    try:
        from vsp import priors as P
        return P.load_priors()
    except Exception:  # noqa: BLE001
        return None


def _prior_means(pri, niche, arc, vt):
    """Learned tie-break only (docs/CREATIVE-PLAN.md §1.5): posterior means
    with n >= 3 (vsp.priors.mean_for), neutral 0.5 otherwise."""
    if not pri:
        return 0.5, 0.5
    try:
        from vsp import priors as P
        a = P.mean_for(pri, "archetype", niche, arc)
        v = P.mean_for(pri, "visual_type", niche, vt)
        return (0.5 if a is None else a), (0.5 if v is None else v)
    except Exception:  # noqa: BLE001
        return 0.5, 0.5


def _variants(script, ctx, seed, maker):
    if not isinstance(script, dict):
        return None
    vt_item, vh_item = _hook_items(script)
    if vt_item is None or vh_item is None:
        return None
    maker = maker or _maker()
    if maker is None or not hasattr(maker, "hook_pool"):
        return None
    if ctx is None:
        ctx = ctx_from_script(script, maker)
        if ctx is None:
            return None
    d = data()
    presenter = str(ctx.get("presenter") or script.get("presenter") or "").lower()
    ai = presenter == "ai"
    payoff = maker._hook_payoff(ctx)
    compat = d["_compat"].get(payoff, [])
    info = hook_info(script, ctx, maker)
    info["payoff"] = payoff
    verbal = " ".join(str(vh_item.get("dialogue") or "").split())
    overlay = str(vt_item.get("on_screen") or "")
    direction = str(vt_item.get("direction") or "")
    fam_a = str(script.get("hook_family") or "")
    arc_a = ctx.get("hook_archetype")
    if arc_a not in compat:
        arc_a = classify(verbal, fam_a, payoff)
    vt_a = visual_type_of_direction(direction)
    A = {"id": "A", "is_primary": True, "archetype": arc_a, "family": fam_a,
         "verbal": verbal, "overlay": overlay, "visual_type": vt_a,
         "visual": _MUTED_TAIL.sub("", " ".join(direction.split())) or
         _visual_sentence(vt_a, ctx, maker, verbal, ai),
         "audio": _audio(vt_a, ctx, ai), "caption_line": verbal}
    cands = [c for c in _render_candidates(ctx, maker, seed, ai, payoff)
             if c["verbal"] != verbal and first3(c["verbal"]) != first3(verbal)]
    # one feature pass per candidate; the visual type and novelty terms are
    # added per MMR round (score_hook is linear in both)
    w = d["_feat_w"]
    bsum = d["_bonus_sum"]
    for c in cands:
        _s, feats, _r = score_hook(c["verbal"], c["overlay"], None, script, ctx,
                                   archetype=c["archetype"], others=(), info=info)
        raw = 0.0
        for f in d["HOOK_SCORE_FEATURES"]:
            fid = f["id"]
            if fid in ("novelty", "visual_type_strength"):
                continue
            raw += (-1.0 if f["direction"] == "-" else 1.0) * w[fid] * feats[fid]
        c["raw0"] = raw
        c["paid"] = feats["open_loop_paired"] >= 0
        c["vts"] = _vt_options(c["archetype"], c["verbal"], c["overlay"], ctx, ai)
        c["pair"] = set(d["PAIRINGS"].get(c["archetype"], ()))
        c["tri"] = trigrams(c["verbal"], set(info["kw"]))
        c["f3"] = first3(c["verbal"])
    # D35/D5: an opening whose loop the payoff does not pay never ships
    cands = [c for c in cands if c["paid"] and c["vts"]]
    chosen = _select(A, cands, info, ctx)
    if len(chosen) < MIN_VARIANTS:
        return None
    out = []
    for i, c in enumerate(chosen):
        if i == 0:
            v = dict(A)
        else:
            v = {"id": IDS[i], "is_primary": False, "archetype": c["archetype"],
                 "family": c["family"], "verbal": c["verbal"], "overlay": c["overlay"],
                 "visual_type": c["vt"],
                 "visual": _visual_sentence(c["vt"], ctx, maker, c["verbal"], ai),
                 "audio": _audio(c["vt"], ctx, ai), "caption_line": c["verbal"]}
        out.append(v)
    for v in out:
        others = [o["verbal"] for o in out if o is not v]
        s, feats, reasons = score_hook(v["verbal"], v["overlay"], v["visual_type"], script,
                                       ctx, archetype=v["archetype"], others=others,
                                       info=info)
        v["score"], v["features"], v["reasons"] = s, feats, reasons
    return out


# selection levels, tried in order for every slot: (new archetype only, max
# trigram Jaccard, cluster cap, alternate floor). 0 = VARIANT_POLICY (a new
# archetype, Jaccard <= 0.2, <= 2 per cluster) at HOOK-08's alternate floor
# (score >= 0.50); 1 = an archetype may repeat while >= 3 stay distinct
# (§1.2); 2 = near-miss wording / weaker lines, only to reach 4 openings
# (VARIANT_POLICY: 3 alternates)
ALT_MIN_SCORE = 0.50
_LEVELS = ((True, MAX_JACCARD, True, ALT_MIN_SCORE),
           (False, MAX_JACCARD, True, ALT_MIN_SCORE),
           (False, 1.0 / 3 + 1e-9, False, 0.0))


def _select(A, cands, info, ctx):
    """Maximal marginal relevance over (candidate, visual type): λ·score +
    (1-λ)·(1 - max trigram Jaccard) + a bonus for a new archetype and a new
    card. Always distinct visual types and first three words (§1.2); the
    archetype's own pairings (hooks-deep-dive §2.5) before other frames;
    learned priors break ties only (n >= 3)."""
    d = data()
    w_vt, w_nov, bsum = d["_feat_w"]["visual_type_strength"], d["_feat_w"]["novelty"], \
        d["_bonus_sum"]
    drop = set(info["kw"])
    sel = [{"verbal": A["verbal"], "archetype": A["archetype"], "vt": A["visual_type"],
            "overlay": A["overlay"], "tri": trigrams(A["verbal"], drop),
            "f3": first3(A["verbal"])}]
    used = set()
    niche = ctx.get("niche")
    pri = _load_priors()
    while len(sel) < MAX_VARIANTS:
        arcs = [x["archetype"] for x in sel]
        f3s = {x["f3"] for x in sel}
        vts = {x["vt"] for x in sel}
        ovs = {x["overlay"] for x in sel}
        clusters = {}
        for x in sel:
            cl = cluster_of(x["archetype"])
            clusters[cl] = clusters.get(cl, 0) + 1
        best = None
        for lvl, (new_only, max_jac, cap, floor) in enumerate(_LEVELS):
            if lvl == 2 and len(sel) >= 4:
                break          # near-miss wording only to reach 4 openings
            best_key = None
            for c in cands:
                if c["idx"] in used or c["f3"] in f3s:
                    continue
                jac = max(jaccard(c["tri"], x["tri"]) for x in sel)
                new_arc = c["archetype"] not in arcs
                if jac > max_jac or (new_only and not new_arc):
                    continue
                if cap and clusters.get(cluster_of(c["archetype"]), 0) >= MAX_PER_CLUSTER:
                    continue
                if not new_arc and len(set(arcs)) < 3 and len(sel) >= 3:
                    continue   # a 4th+ opening keeps >= 3 distinct archetypes
                free = [v for v in c["vts"] if v not in vts]
                paired = [v for v in free if v in c["pair"]]
                for vt in (paired or free):
                    vh = d["VISUAL_HOOKS"][vt]
                    vx = float(vh["prior"]) * (1.0 if c["archetype"] in vh["best_archetypes"]
                                               else 0.6)
                    raw = c["raw0"] + w_vt * vx + w_nov * (1.0 - jac)
                    score = max(0.0, min(1.0, raw / bsum))
                    if score < floor:
                        continue
                    mmr = MMR_LAMBDA * score + (1 - MMR_LAMBDA) * (1.0 - jac) + \
                        0.05 * new_arc + 0.02 * (c["overlay"] not in ovs)
                    pa, pv = _prior_means(pri, niche, c["archetype"], vt)
                    key = (round(mmr, 2), round(pa, 4), round(pv, 4), -c["idx"], vt)
                    if best_key is None or key > best_key:
                        best, best_key = dict(c, vt=vt), key
            if best is not None:
                break
        if best is None:
            break
        used.add(best["idx"])
        sel.append(best)
    # §1.2: >= 3 distinct archetypes once there are 4+ variants
    while len(sel) >= 4 and len({x["archetype"] for x in sel}) < 3:
        sel.pop()
    return sel


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


# ------------------------------------------------------------- checker
_LINK_FORBIDDEN = CV.BUNDLE_FORBIDDEN


def _norm_words(text):
    return L.norm(text).split()


def check_variants(hv, script, ctx=None):
    """The docs/CREATIVE-PLAN.md §1.2 hard rules (gate D154) -> [problems].
    Independent of how the variants were chosen: ids, the primary, the
    distinctness rules, every screen of the primary hook on every variant
    (D73 8 words, D144 card, D37, D136, D139, D141, D158, D137 + human_only
    archetypes for an AI presenter, requires_price/proof), payoff
    compatibility, and the frame-0 / audio / caption fields."""
    p = []
    if not isinstance(hv, list) or not MIN_VARIANTS <= len(hv) <= MAX_VARIANTS:
        return [f"hook_variants: need {MIN_VARIANTS}-{MAX_VARIANTS} variants, got "
                f"{len(hv) if isinstance(hv, list) else type(hv).__name__}"]
    if any(not isinstance(v, dict) for v in hv):
        return ["hook_variants: every variant is an object"]
    ids = [v.get("id") for v in hv]
    if ids != list(IDS[:len(hv)]):
        p.append(f"ids {ids} are not A, B, C… in order")
    prim = [v.get("id") for v in hv if v.get("is_primary") is True]
    if prim != ["A"] or any(v.get("is_primary") not in (True, False) for v in hv):
        p.append(f"exactly one is_primary, variant A (got {prim})")
    vt_item, vh_item = _hook_items(script)
    A = hv[0]
    if vh_item is None or A.get("verbal") != " ".join(str(vh_item.get("dialogue") or "").split()):
        p.append("A.verbal != the script's VERBAL HOOK dialogue")
    if vt_item is None or A.get("overlay") != str(vt_item.get("on_screen") or ""):
        p.append("A.overlay != the VISUAL TRIGGER on_screen")
    if vt_item is not None and A.get("visual_type") != visual_type_of_direction(
            vt_item.get("direction")):
        p.append(f"A.visual_type {A.get('visual_type')!r} does not describe the frame-0 "
                 f"direction")
    vts = [v.get("visual_type") for v in hv]
    if len(set(vts)) != len(vts):
        p.append(f"visual_type values repeat: {vts}")
    f3 = [first3(v.get("verbal")) for v in hv]
    if len(set(f3)) != len(f3):
        p.append(f"first three words repeat: {f3}")
    arcs = [v.get("archetype") for v in hv]
    if len(hv) >= 4 and len(set(arcs)) < 3:
        p.append(f"{len(hv)} variants but only {len(set(arcs))} archetypes")
    prompt = str(script.get("prompt") or "")
    ai = str(script.get("presenter") or "").strip().lower() == "ai"
    pt = payoff_type(script, ctx)
    compat = data()["_compat"].get(pt, [])
    arch = data()["ARCHETYPES"]
    feat_ids = [f["id"] for f in data()["HOOK_SCORE_FEATURES"]]
    link_caption = CV.link_groups_in(script.get("caption") or "")
    for v in hv:
        vid = v.get("id")
        a, vt = v.get("archetype"), v.get("visual_type")
        verbal, ov, cap = (str(v.get(k) or "") for k in ("verbal", "overlay", "caption_line"))
        if a not in CV.HOOK_ARCHETYPES:
            p.append(f"{vid}: archetype {a!r} is not a HOOK_ARCHETYPES id")
        if vt not in CV.VISUAL_TYPES:
            p.append(f"{vid}: visual_type {vt!r} is not a VISUAL_TYPES id")
        if not v.get("family"):
            p.append(f"{vid}: no family")
        if not verbal or len(verbal.split()) > 8:
            p.append(f"{vid}: verbal is {len(verbal.split())} words (D73: 1-8)")
        n_ov = len(_norm_words(ov))
        if not ov or (n_ov > 3 and "|" not in ov):
            p.append(f"{vid}: overlay {ov!r} is not 1-3 words")
        ok, why = L.overlay_is_clean(ov, verbal)
        if not ok:
            p.append(f"{vid}: overlay {ov!r}: {why} (D144)")
        for label, text in (("verbal", verbal), ("overlay", ov), ("caption_line", cap)):
            for prob in screen_text(text, prompt, ai):
                if label == "overlay" and prob.startswith("R02"):
                    continue
                p.append(f"{vid}.{label}: {prob}")
        if not cap:
            p.append(f"{vid}: no caption_line")
        flags = CV.HOOK_ARCHETYPES.get(a) or {}
        if ai and (flags.get("human_only") or (arch.get(a) or {}).get("ai_safe") is False):
            p.append(f"{vid}: human_only archetype {a} for an AI presenter (D137)")
        if flags.get("requires_price") and not L.PRICE.search(prompt):
            p.append(f"{vid}: {a} needs a price in the prompt (D37)")
        if flags.get("requires_proof") and not L.first_match(L.SOCIAL_PROOF, prompt):
            p.append(f"{vid}: {a} needs proof in the prompt (D136)")
        if flags.get("requires_offer") and not prompt_has_offer(prompt):
            p.append(f"{vid}: {a} needs an offer in the prompt (D158)")
        if a not in compat:
            p.append(f"{vid}: archetype {a} is not paid by the {pt} payoff (D35)")
        vis = str(v.get("visual") or "")
        if not vis.startswith("Frame 0"):
            p.append(f"{vid}: visual does not start with 'Frame 0'")
        for text, what in ((vis, "visual"), (str(v.get("audio") or ""), "audio")):
            if not text:
                p.append(f"{vid}: no {what}")
            if '"' in text or "\u201c" in text:
                p.append(f"{vid}: quoted dialogue in {what} (D160)")
            if any(f in text for f in _LINK_FORBIDDEN):
                p.append(f"{vid}: forbidden bundle phrase in {what}")
            if CV.link_groups_in(text) - link_caption:
                p.append(f"{vid}: a new D46 link group in {what}")
        sc = v.get("score")
        if not isinstance(sc, (int, float)) or not 0.0 <= sc <= 1.0:
            p.append(f"{vid}: score {sc!r} not in [0, 1]")
        feats = v.get("features")
        if not isinstance(feats, dict) or sorted(feats) != sorted(feat_ids):
            p.append(f"{vid}: features are not the 19 HOOK_SCORE_FEATURES")
        if not isinstance(v.get("reasons"), list) or not v.get("reasons"):
            p.append(f"{vid}: no reasons")
    return p


# ----------------------------------------------------------- render_md
def render_md(hv, script):
    """hooks.md: the variant table, each opening's frame 0 / audio / caption
    line / score reasons, and the test protocol, metrics and Bayesian stop
    rule of hooks-deep-dive VARIANT_POLICY."""
    pol = data()["VARIANT_POLICY"]
    script = script or {}
    hv = [v for v in (hv or []) if isinstance(v, dict)]
    out = ["## HOOK VARIANTS — alternate openings", ""]
    out.append(f"Prompt: {script.get('prompt', '')} · format {script.get('format', '')} · "
               f"presenter {script.get('presenter', '')} · payoff "
               f"{payoff_type(script, None)}")
    out.append("")
    out.append(f"Variant A is the master's own opening; {max(0, len(hv) - 1)} alternates "
               "change only the first 3 seconds (frame 0, card, spoken hook). Everything "
               "from 3.0 s stays fixed, so a test isolates the hook. Scores rank openings "
               "within this script (hooks-deep-dive §4); they are not virality forecasts.")
    out.append("")
    out.append("| ID | Role | Archetype | Frame 0 | Card (0.0 s) | Hook (0.5–3.0 s) | Score |")
    out.append("|---|---|---|---|---|---|---|")
    for v in hv:
        role = "primary" if v.get("is_primary") else "alternate"
        out.append(f"| {v.get('id')} | {role} | {v.get('archetype')} | {v.get('visual_type')} "
                   f"| {v.get('overlay')} | {v.get('verbal')} | "
                   f"{int(round(100 * float(v.get('score') or 0)))} |")
    out.append("")
    for v in hv:
        out.append(f"#### {v.get('id')} — {v.get('archetype')} / {v.get('visual_type')} "
                   f"(score {int(round(100 * float(v.get('score') or 0)))})")
        out.append(f"- Visual: {v.get('visual')}")
        out.append(f"- Audio: {v.get('audio')}")
        out.append(f"- Caption line 1: {v.get('caption_line')}")
        rs = "; ".join(str(r) for r in (v.get("reasons") or [])[:3])
        out.append(f"- Why: {rs}")
        out.append("")
    tp, mt, th, st = pol["testing_protocol"], pol["metrics"], pol["thresholds"], pol["stats"]
    out += ["## Test protocol", "",
            f"- Paid (Meta / TikTok ad groups): {tp['paid']}. TikTok recommends 3–5 "
            "creatives per ad group; one variant = one creative.",
            f"- Instagram Trial Reels: {tp['instagram_trial_reels']}.",
            f"- Other organic slots: {tp['organic_other']}.",
            f"- Looks: {tp['looks']}.",
            "- Log per post: " + ", ".join(tp["log"]) + ". The caption's first line "
            "(each variant's caption line) links a post back to its variant.",
            "", "## Metrics", "",
            f"- Instagram: {mt['primary']['instagram']} (reels_skip_rate = share of views "
            f"skipped within 3 s; healthy below {th['instagram_skip_rate']['healthy_below']:.0%}, "
            f"failing above {th['instagram_skip_rate']['failing_above']:.0%}; trackers, no "
            "official benchmark).",
            f"- Meta paid: {mt['primary']['meta_paid']} — the 3-second hold (kill below "
            f"{th['hook_rate_paid']['kill_below']['meta']:.0%}, median "
            f"{th['hook_rate_paid']['median']['meta']:.0%}, top decile "
            f"{th['hook_rate_paid']['top_decile']['meta']:.0%}).",
            f"- TikTok paid: {mt['primary']['tiktok_paid']}; organic: "
            f"{mt['primary']['tiktok_organic']}.",
            f"- YouTube Shorts: {mt['primary']['youtube_shorts']}.",
            "- Guardrails: " + ", ".join(mt["guardrails"]) + f" — {mt['guardrail_rule']}.",
            "", "## Stop rule (Bayesian)", "",
            f"- Model: {st['model']}.",
            f"- Prior: {st['prior']}.",
            f"- Decide: {st['decision']}.",
            f"- Minimum: {st['min_n_per_variant']} views per variant before any decision "
            f"(a 5-point lift at a 30% hold needs about "
            f"{st['power_guide']['lift_5pp_at_30pct']} per variant, a 10-point lift about "
            f"{st['power_guide']['lift_10pp_at_30pct']}).",
            f"- Futility: {st['futility']}.",
            f"- Early kill: {st['early_kill']}.",
            f"- Learning: {st['prior_update']}; vsp.feedback writes the archetype and "
            "visual_type priors, which only ever break ties.", ""]
    return "\n".join(out)


# ----------------------------------------------------------- selfcheck
_EXPECTED_SLOTS = frozenset("""after before category category_pl common expensive flaw
identity mistake moment ndays persona_note price product proof situation thing
timespan""".split())
FORMATS = ("demo", "talking-head", "pov-vlog", "transformation", "review")
PRESENTERS = ("human", "ai")


def _repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _prompts(name):
    path = os.path.join(_repo_root(), "evals", name)
    with open(path, encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip() and not ln.startswith("//")]


def selfcheck():
    """Hermetic, in-process (no network, no file writes, priors off):
    research tables, the maker's hook metadata, and generate() over
    evals/golden.jsonl + evals/holdout.jsonl x 5 formats x 2 presenters at
    seed 1 — every script carries 3-5 variants passing check_variants, A is
    the actual hook, byte-identical twice, < 15 ms per variants() call on
    average, no creative_warnings, the primary still passes gate 1."""
    import time
    lines, fails = [], []

    def chk(name, cond, detail=""):
        lines.append(("ok   " if cond else "FAIL ") + name +
                     (f" — {detail}" if detail and not cond else ""))
        if not cond:
            fails.append(name)

    import shutil
    import tempfile
    saved = {k: os.environ.get(k) for k in ("VSP_NO_PRIORS", "VSP_VIRAL_DB",
                                            "VSP_FIXTURE_OK")}
    os.environ["VSP_NO_PRIORS"] = "1"
    tmp = tempfile.mkdtemp(prefix="vsp_hooks_selfcheck_")
    try:
        try:
            from vsp.fixtures import build_fixture_db
            os.environ["VSP_VIRAL_DB"] = build_fixture_db(os.path.join(tmp, "viral.db"))
            os.environ["VSP_FIXTURE_OK"] = "1"
        except Exception:  # noqa: BLE001 — gate 2 is then reported, not run
            pass
        _selfcheck_body(chk, time)
    except Exception as e:  # noqa: BLE001 — a crashing check fails closed
        import traceback
        chk("selfcheck ran", False, f"{type(e).__name__}: {e} "
            f"{traceback.format_exc()[-400:]}")
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(tmp, ignore_errors=True)
    return (not fails), lines


def _selfcheck_body(chk, time):
    d = data()
    arcs = d["ARCHETYPES"]
    chk("archetypes: 19 ids = creative_vocab.HOOK_ARCHETYPES",
        sorted(arcs) == sorted(CV.HOOK_ARCHETYPES))
    chk("archetypes: 115 research templates",
        sum(len(a["templates"]) for a in arcs.values()) == 115)
    chk("visual hooks: 11 ids = creative_vocab.VISUAL_TYPES",
        sorted(d["VISUAL_HOOKS"]) == sorted(CV.VISUAL_TYPES))
    ws = [float(f["weight"]) for f in d["HOOK_SCORE_FEATURES"]]
    chk("score features: 19, weights sum 1.0, bonus sum 0.81",
        len(ws) == 19 and abs(sum(ws) - 1.0) < 1e-9 and abs(d["_bonus_sum"] - 0.81) < 1e-9)
    chk("risky phrases: 20 compiled", len(d["_risky"]) == 20)
    import viral_script_maker as vsm
    from vsp.gates import gate1, gate2
    try:
        import make_shotlist
    except Exception:  # noqa: BLE001
        make_shotlist = None
    chk("maker: HOOK_SLOTS unchanged (pack loader / evolve contract)",
        frozenset(vsm.HOOK_SLOTS) == _EXPECTED_SLOTS, str(sorted(vsm.HOOK_SLOTS)))
    chk("maker: every HOOKS family is a HOOK_ARCHETYPES id",
        all(f in CV.HOOK_ARCHETYPES for f in vsm.HOOKS), str(sorted(vsm.HOOKS)))
    mc = {k: sorted(v) for k, v in vsm.HOOK_PAYOFF_COMPAT.items()}
    chk("maker: HOOK_PAYOFF_COMPAT == hooks.json payoff_compat",
        mc == {k: sorted(v) for k, v in d["_compat"].items()})
    # human_only (D137): never for presenter=ai
    ctx = vsm.parse_prompt("electric milk frother")
    ctx.update(fmt="review", presenter="ai", named_competitor="the name brand")
    leaks = [t for t in vsm.HOOK_HUMAN_ONLY
             if vsm._hook_template_ok(ctx, "bold-claim", t, None, True) is not None]
    leaks += [f"{f}: {t}" for f in ("story-time", "confession") for t in vsm.HOOKS[f]
              if vsm._hook_template_ok(ctx, f, t, None, True) is not None]
    chk("maker: human_only templates / families never pass for presenter=ai", not leaks,
        "; ".join(leaks[:3]))
    # price once, with its currency
    pc = vsm.parse_prompt("a $12 LED sunrise alarm lamp")
    pc.update(fmt="review", presenter="human")
    r = vsm._render_hook_line(pc, None, "{Domain} finds under ${price}.", None)
    r2 = vsm._render_hook_line(pc, None, "At {price}: the {category} verdict.", None)
    chk("maker: {price} renders once with its currency",
        r.count("$12") == 1 and "$$" not in r and r2.count("$12") == 1, f"{r} / {r2}")
    # price / proof / newness only from the prompt
    np_ctx = vsm.parse_prompt("silk pillowcase")
    np_ctx.update(fmt="review", presenter="human")
    gated = [t for t in ("{product} is {price}. Worth it?", "Proof first: {proof}.",
                         "New {category} just dropped. First look.")
             if vsm._hook_template_ok(np_ctx, "question", t, None, False) is not None]
    chk("maker: price / proof / 'new' templates need the prompt's input", not gated,
        "; ".join(gated))
    new_ctx = vsm.parse_prompt("new silk pillowcase")
    new_ctx.update(fmt="demo", presenter="human")
    chk("maker: a newness fact in the prompt unlocks 'new' templates",
        vsm._hook_template_ok(new_ctx, "newness", "New {category} just dropped. First look.",
                              None, False) == "newness")
    # score_hook: deterministic, bounded, explained
    s1 = score_hook("Stop buying milk frothers on looks alone.", "BUYING MILK FROTHERS",
                    "problem-state", {"prompt": "electric milk frother", "presenter": "ai",
                                      "format": "demo"}, ctx=dict(ctx, fmt="demo"),
                    archetype="negative-command")
    s2 = score_hook("Stop buying milk frothers on looks alone.", "BUYING MILK FROTHERS",
                    "problem-state", {"prompt": "electric milk frother", "presenter": "ai",
                                      "format": "demo"}, ctx=dict(ctx, fmt="demo"),
                    archetype="negative-command")
    chk("score_hook: deterministic, in [0,1], 19 features, reasons",
        s1 == s2 and 0 <= s1[0] <= 1 and len(s1[1]) == 19 and s1[2], str(s1[0]))
    bait = score_hook("You won't believe this lamp!!", "LAMP", "text-first",
                      {"prompt": "lamp", "presenter": "human", "format": "demo"})
    chk("score_hook: clickbait and hype cost points", bait[0] < s1[0] and
        bait[1]["clickbait_marker"] == 1.0, str(bait[0]))
    chk("risky: fake urgency needs the prompt's offer",
        risky_hits("Last chance, ends tonight", "a lamp") == ["UR-01"] and
        risky_hits("Last chance, ends tonight", "a lamp, 20% off sale ends tonight") == [])
    # the in-process sweep
    rows = []
    for name in ("golden.jsonl", "holdout.jsonl"):
        for g in _prompts(name):
            rows.append((name, g["id"], g["prompt"]))
    times = []
    real = sys.modules[__name__].variants
    import importlib
    mod = importlib.import_module("vsp.hooks")   # what vsp.creative calls

    def timed(script, ctx=None, seed=None, maker=None):
        t0 = time.perf_counter()
        try:
            return real(script, ctx=ctx, seed=seed, maker=maker)
        finally:
            times.append(time.perf_counter() - t0)

    bad, nondet, warns, g1, missing, counts, not_a = [], [], [], [], [], {}, []
    g2, g2_runs = [], 0
    can_g2 = make_shotlist is not None and bool(os.environ.get("VSP_VIRAL_DB"))
    if mod is not None:
        mod.variants = timed
    try:
        for name, pid, prompt in rows:
            for fmt in FORMATS:
                for pr in PRESENTERS:
                    key = f"{pid}|{fmt}|{pr}"
                    s = json.loads(json.dumps(vsm.generate(prompt, presenter=pr, fmt=fmt,
                                                           duration=30, seed=1)))
                    s2 = json.loads(json.dumps(vsm.generate(prompt, presenter=pr, fmt=fmt,
                                                            duration=30, seed=1)))
                    if json.dumps(s, sort_keys=True) != json.dumps(s2, sort_keys=True):
                        nondet.append(key)
                    if s.get("creative_warnings"):
                        warns.append(f"{key}: {s['creative_warnings']}")
                    hv = s.get("hook_variants")
                    if not hv:
                        missing.append(key)
                        continue
                    counts[len(hv)] = counts.get(len(hv), 0) + 1
                    probs = check_variants(hv, s)
                    if probs:
                        bad.append(f"{key}: {probs[0]}")
                    _vt, vh = _hook_items(s)
                    if hv[0].get("verbal") != (vh or {}).get("dialogue"):
                        not_a.append(key)
                    if gate1(s):
                        g1.append(f"{key}: {gate1(s)[0][:90]}")
                    elif can_g2:
                        try:
                            bt, _, _ = make_shotlist.build_bundle(s)
                            e2 = gate2(bt, s)
                        except Exception as e:  # noqa: BLE001
                            e2 = [f"stage 2 crash {type(e).__name__}: {e}"]
                        g2_runs += 1
                        if e2:
                            g2.append(f"{key}: {str(e2[0])[:90]}")
    finally:
        if mod is not None:
            mod.variants = real
    n = len(rows) * len(FORMATS) * len(PRESENTERS)
    chk(f"sweep: {n} scripts (golden + holdout x 5 formats x 2 presenters, seed 1) "
        f"all carry hook_variants", not missing, "; ".join(missing[:3]))
    chk("sweep: every script passes the §1.2 rules (check_variants)", not bad,
        "; ".join(bad[:3]) + (f" (+{len(bad) - 3})" if len(bad) > 3 else ""))
    chk("sweep: A == the actual hook (VERBAL HOOK dialogue)", not not_a, "; ".join(not_a[:3]))
    chk("sweep: byte-identical twice", not nondet, "; ".join(nondet[:3]))
    chk("sweep: no creative_warnings", not warns, "; ".join(warns[:2]))
    chk("sweep: primary hooks still pass gate 1", not g1, "; ".join(g1[:2]))
    chk(f"sweep: bundles pass gate 2 ({g2_runs} built, fixture reference DB)",
        can_g2 and g2_runs == n and not g2, "; ".join(g2[:2]) or
        ("" if can_g2 else "no fixture DB / make_shotlist"))
    avg = 1000 * sum(times) / max(1, len(times))
    chk(f"sweep: variants() averages {avg:.1f} ms over {len(times)} calls (< 15 ms)",
        avg < 15.0)
    chk("sweep: variant counts " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())),
        all(MIN_VARIANTS <= k <= MAX_VARIANTS for k in counts))
    # determinism across processes and PYTHONHASHSEED
    import subprocess
    code = ("import json, sys; sys.path.insert(0, %r); import viral_script_maker as v; "
            "print(json.dumps([v.generate(p, presenter=pr, fmt=f, seed=7).get('hook_variants') "
            "for p, pr, f in [('electric milk frother','ai','demo'), ('silk pillowcase',"
            "'human','review'), ('I quit sugar for 21 days','human','pov-vlog'), "
            "('things in my car that just make sense','ai','transformation'), "
            "('why your hooks fail','human','talking-head'), ('my 5am morning routine',"
            "'ai','review')]], sort_keys=True))" % _repo_root())
    outs = []
    for hs in ("0", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=hs)
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                           env=env, timeout=300)
        outs.append(r.stdout if r.returncode == 0 else f"exit {r.returncode}: {r.stderr[-200:]}")
    chk("determinism: byte-identical across processes and PYTHONHASHSEED",
        outs[0] == outs[1] and outs[0].startswith("[["), outs[0][:120])
    # --script-json path: no ctx -> derived from the prompt; never raises
    s = json.loads(json.dumps(vsm.generate("electric milk frother", presenter="ai",
                                           fmt="demo", seed=3)))
    s.pop("hook_variants", None)
    hv = variants(s, seed=3)
    chk("no ctx: variants derived from the prompt pass §1.2",
        bool(hv) and not check_variants(hv, s), "; ".join(check_variants(hv, s)[:2])
        if hv else "None")
    chk("no ctx: a script without a hook stack gives None (never raises)",
        variants({"prompt": "x"}) is None and variants(None) is None)
    md = render_md(hv, s)
    chk("render_md: table, protocol, metrics, Bayesian stop rule",
        all(k in md for k in ("| ID |", "## Test protocol", "Trial Reels", "reels_skip_rate",
                              "3-second", "## Stop rule (Bayesian)", "P(v is best)")) and
        not any(f in md for f in CV.BUNDLE_FORBIDDEN))


def _cli(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="python3 -m vsp.hooks",
                                 description="hook variants (docs/CREATIVE-PLAN.md §1.2)")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("selfcheck", help="hermetic self-check")
    sh = sub.add_parser("show", help="generate a script and print its hooks.md")
    sh.add_argument("prompt")
    sh.add_argument("--format", default="demo",
                    choices=list(FORMATS))
    sh.add_argument("--presenter", default="ai", choices=list(PRESENTERS))
    sh.add_argument("--seed", type=int, default=1)
    sh.add_argument("--duration", type=int, default=30)
    sh.add_argument("--json", action="store_true", help="print the variants as JSON")
    a = ap.parse_args(argv)
    if a.cmd == "selfcheck":
        ok, lines = selfcheck()
        print("\n".join(lines))
        print(f"vsp.hooks selfcheck: {'OK' if ok else 'FAILED'}")
        return 0 if ok else 1
    if a.cmd == "show":
        sys.path.insert(0, _repo_root())
        import viral_script_maker as vsm
        s = vsm.generate(a.prompt, presenter=a.presenter, fmt=a.format,
                         duration=a.duration, seed=a.seed)
        hv = s.get("hook_variants")
        if a.json:
            print(json.dumps(hv, indent=1, ensure_ascii=False))
        else:
            print(render_md(hv, s) if hv else "(no hook variants)")
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(_cli())
