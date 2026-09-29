"""Stage 1 — ROUTE: input guardrails + a 3-voter prompt router (RULES.md §66
D147). This is AGENT-BRIEF's never-built "input-side prompt->fit
classifier": the maker only ever classified its own output.

    route(prompt, presenter=None, fmt=None, pack=None) -> dict

Voters (each votes {voter, concept, niche}):
  maker     viral_script_maker.parse_prompt — what the generator WILL do
            (imported read-only; the maker is never modified here)
  lexicon   an independent word-boundary keyword classifier (no substring
            hijacks: "chair" never matches "hair", "clamp" never "lamp")
  research  the research-pack niche map (vsp/research.py): a research-niche
            vocabulary, vouched by the niches the loaded pack actually has;
            it abstains on concept
agreement = min over {concept, niche} of majority_votes / max(2, voters
that voted); < 2/3 is a route warning (the pipeline's --strict-route turns
it into a failure). Advice follows RULES.md §4 F32 (AI for utilitarian,
human for hedonic), §9 B15 (high complexity -> AI is fine), D137 (a
challenge/routine is first-person lived experience -> human) and the TikTok
Shop quality rules (visible people, no AI voices in LIVE).

pack: None loads the configured pack (vsp.research.load_pack), False routes
without research (the research voter is then unvouched), a dict is used as
given. route() never raises: a voter that crashes is recorded in its vote
and in route_warnings; empty or over-long input is reported in
input_errors. Extra keys beyond the stage contract: route_warnings,
warnings (all three lists), strict_ok (what --strict-route checks),
presenter/format (as requested).
"""
import re
import unicodedata

from vsp import research as R

MAX_PROMPT_CHARS = 300
AGREEMENT_MIN = 2.0 / 3.0
FORMATS = ("demo", "talking-head", "pov-vlog", "transformation", "review")
PRESENTERS = ("ai", "human")

# regulated claim categories (TikTok/Meta ad policy, FTC substantiation)
REGULATED = [
    ("supplement", r"\bsupplements?\b|\bmelatonin\b|\bprobiotics?\b"),
    ("CBD/hemp/THC", r"\b(?:cbd|hemp|thc)\b"),
    ("weight loss", r"\bweight[- ]?loss\b|\bfat[- ]?burn(?:er|ers|ing)?\b|"
                    r"\bdiet pills?\b|\bslimming\b"),
    ("cure claim", r"\bcure[sd]?\b"),
    ("treatment claim", r"\btreat(?:s|ed|ing|ment|ments)?\b"),
    ("alcohol", r"\balcohol(?:ic)?\b|\bwine\b|\bbeer\b|\bvodka\b|"
                r"\bwhiske?y\b|\btequila\b|\bliquor\b"),
    ("nicotine/vape", r"\bnicotine\b|\bvap(?:e|es|ing)\b|\be-?cig(?:arette)?s?\b"),
]
_PET_TREATS = re.compile(r"\b(?:dog|cat|pet|puppy|kitten)s?\s+treats?\b", re.I)

# ------------------------------------------------------- lexicon voter
_LEX_PHRASES = {   # multi-word phrases first (weight 2)
    "gadgets": ["power bank", "power station", "battery bank"],
    "fitness": ["walking pad", "yoga mat", "resistance band", "pull-up bar",
                "foam roller"],
    "pets": ["lick mat", "bird feeder", "litter box", "cat tree"],
    "automotive": ["tire inflator", "car seat", "car mount", "car vacuum"],
    "wellness": ["white noise", "sleep mask", "noise machine", "self care",
                 "weight loss"],
    "commentary": ["spill the tea", "hot take"],
    "home": ["office chair", "door lock", "living room"],
    "beauty": ["hair wax", "get ready with me"],
}
_LEX_WORDS = {
    "pets": "pet pets dog dogs puppy puppies cat cats kitten kitty leash "
            "litter bird birds feeder birdhouse aquarium hamster",
    "automotive": "car cars auto vehicle truck dashboard headrest tire tires "
                  "engine motor garage driving trunk windshield inflator",
    "fitness": "fitness workout gym protein posture exercise yoga resistance "
               "band bands dumbbell dumbbells kettlebell treadmill pull-up "
               "pullup cardio running stretching",
    "beauty": "beauty skincare skin makeup serum cream moisturizer lipstick "
              "mascara eyelash eyelashes lash lashes hair shampoo conditioner "
              "straightener curler nail nails perfume fragrance silk grwm",
    "wellness": "sleep melatonin magnesium supplement supplements gummies "
                "wellness selfcare self-care relax relaxing anxiety stress "
                "meditation cbd probiotic snore snoring massager massage",
    "food": "food recipe recipes cook cooking snack snacks coffee espresso "
            "latte meal meals baking sugar tea matcha",
    "tools": "tool tools kitchen cleaning clean organizer organize knife "
             "drill waffle fryer toaster kettle blender cookware lunch "
             "mealprep frother mop vacuum trash",
    "gadgets": "gadget gadgets tech lamp alarm charger earbud earbuds "
               "headphones speaker keyboard mouse light lights led projector "
               "drone smartwatch phone desk cable fan laptop tablet camera",
    "outdoors": "camp camping tent outdoor outdoors hike hiking lantern "
                "flashlight headlamp backpack firewood",
    "home": "home apartment bedroom bathroom closet decor chair sofa couch "
            "rug curtain curtains shelf furniture bedding pillow pillowcase "
            "blanket",
    "finance": "finance money budget budgeting invest investing debt credit "
               "bank savings stocks",
    "education": "learn learning course study studying language exam tutor "
                 "hooks content creator algorithm",
    "commentary": "news politics drama gossip",
}
# tie-break order (earlier wins): specific communities before catch-alls
_LEX_ORDER = ["pets", "automotive", "fitness", "beauty", "wellness", "food",
              "tools", "gadgets", "outdoors", "home", "finance", "education",
              "commentary"]

_CHALLENGE = re.compile(
    r"\bi\s+(?:stopped|quit|gave up|tried|did|unfollowed|deleted|ditched|"
    r"dropped|cooked|ran|walked|meditated|woke|read|wrote|lifted|trained|"
    r"saved|drank|fasted|journaled|studied|stretched|cleaned|danced|swam|"
    r"biked|unplugged|ate|went)\b.*?\bfor\s+\d+\s*(?:days?|weeks?|months?)\b"
    r"|\b\d+[- ]day challenge\b|\bno\s+\w+(?:\s+\w+)?\s+for\s+\d+\s*days?\b",
    re.I)
_ROUTINE = re.compile(r"\broutine\b|\bgrwm\b|\bget ready with me\b|"
                      r"\bday in (?:my|the) life\b|\bmorning reset\b|"
                      r"\bwind[- ]?down\b", re.I)
_SHOWCASE = re.compile(r"\bthings in my\b|\b(?:finds|must[- ]haves|favorites)\b",
                       re.I)
_ADVICE = re.compile(r"^(?:why|how|what no one|the truth about|the secret)\b|"
                     r"\bmistakes?\b|\bsigns?\b|\bthings to (?:stop|avoid|never)\b"
                     r"|\bfails?\b|\bsecrets?\b|\btips\b|\bhacks\b", re.I)
_PRICE = re.compile(r"\$\s?(\d+(?:\.\d+)?)|\b(\d+(?:\.\d+)?)\s?(?:dollars|bucks|usd)\b",
                    re.I)

_UTIL = set("""gadget tech tool tools software app lamp charger earbud earbuds
speaker keyboard mouse projector cable fan humidifier vacuum mop kitchen
cleaning organizer alarm led phone desk car stand clamp lock inflator lantern
flashlight frother blender kettle toaster fryer waffle lunch trash feeder
camera bands band mat corrector chair posture ergonomic bank noise""".split())
_HEDONIC = set("""perfume fragrance luxury makeup lipstick mascara eyelash
eyelashes lash lashes fashion dress jewelry watch resort spa wine candle silk
romantic serum skincare glow""".split())
_HEDONIC_NICHES = {"beauty", "food"}
_UTIL_NICHES = {"gadgets", "tools", "automotive", "home", "outdoors", "pets",
                "fitness", "wellness"}
_COMPLEX = re.compile(
    r"\b(?:finance|invest(?:ing|ment)?|stocks?|etf|crypto|bitcoin|insurance|"
    r"mortgage|loan|tax(?:es)?|retirement|credit (?:card|score)|software|app|"
    r"saas|api|router|mesh wifi|nas|ssd|gpu|cpu|3d printer|drone|projector|"
    r"inverter|power station|ev charger|glucose|blood pressure|oximeter|"
    r"thermometer|hearing aid|cpap|medical)\b", re.I)
_TIKTOK_SHOP = re.compile(r"\btik ?tok[- ]?shop\b|\btt ?shop\b", re.I)


def _words(text):
    return re.findall(r"[a-z0-9]+(?:[-'][a-z0-9]+)*", text.lower())


def _lexicon_vote(p):
    low = p.lower()
    if _CHALLENGE.search(low):
        concept = "challenge"
    elif _ROUTINE.search(low):
        concept = "routine"
    elif _SHOWCASE.search(low):
        concept = "showcase"
    elif _ADVICE.search(low) and not re.search(r"\$\d", p):
        concept = "advice"
    else:
        concept = "product"
    toks = set(_words(low))
    scores = {}
    for niche, phrases in _LEX_PHRASES.items():
        for ph in phrases:
            if re.search(r"\b" + re.escape(ph) + r"\b", low):
                scores[niche] = scores.get(niche, 0) + 2
    for niche, words in _LEX_WORDS.items():
        hits = toks & set(words.split())
        if niche == "finance" and re.search(r"\b(?:power|battery) bank\b", low):
            hits = hits - {"bank"}
        if hits:
            scores[niche] = scores.get(niche, 0) + len(hits)
    if concept == "routine":
        niche = ("beauty" if re.search(r"\b(?:grwm|get ready with me|makeup|"
                                       r"skincare|beauty)\b", low) else "wellness")
        return {"concept": concept, "niche": niche, "confidence": 1.0,
                "scores": scores}
    if not scores:
        return {"concept": concept, "niche": "default", "confidence": 0.5,
                "scores": {}}
    best = max(scores.values())
    niche = next(n for n in _LEX_ORDER if scores.get(n) == best)
    return {"concept": concept, "niche": niche,
            "confidence": 1.0 if best >= 2 else 0.8, "scores": scores}


# ------------------------------------------------------ research voter
# research-DB niche -> (maker niche, vocabulary). Research spellings come
# from the pack's niche_hooks (fashion-beauty, automotive-business,
# ai-education, lifestyle, ugc-ads, ...); order breaks ties.
RESEARCH_VOCAB = [
    ("fashion-beauty", "beauty", "beauty makeup skincare skin serum lash lashes "
     "eyelash eyelashes hair wax lipstick nail nails fashion outfit dress silk "
     "grwm perfume fragrance glow"),
    ("fitness", "fitness", "fitness gym workout yoga bands resistance dumbbell "
     "kettlebell protein posture stretching running treadmill pilates"),
    ("food", "food", "food recipe recipes cooking cook meal meals snack snacks "
     "coffee espresso latte sugar baking eat eating diet tea matcha"),
    ("finance", "finance", "money budget budgeting saving savings invest "
     "investing debt credit finance income"),
    ("automotive-business", "automotive", "car cars truck vehicle tire tires "
     "trunk dashboard garage driving detailing inflator headrest"),
    ("ai-education", "education", "learn learning course study exam language "
     "hooks hook content creator algorithm views tutorial"),
    ("travel", "outdoors", "travel camping camp hiking hike tent lantern "
     "backpack trail outdoor outdoors"),
    ("lifestyle", "wellness", "routine morning night wind-down selfcare "
     "self-care sleep relax meditation journaling wellness"),
    ("lifestyle", "home", "home apartment room decor furniture chair sofa "
     "couch bedding pillow pillowcase blanket candle closet bathroom bedroom "
     "door lock"),
    ("ugc-ads", "pets", "dog dogs cat cats pet pets puppy kitten bird feeder "
     "leash lick"),
    ("ugc-ads", "tools", "kitchen frother blender kettle toaster fryer "
     "cleaning organizer tool drill knife lunch container trash mop vacuum"),
    ("ugc-ads", "gadgets", "gadget tech device charger earbuds headphones "
     "speaker projector lamp light led phone laptop keyboard mouse camera "
     "solar smart clamp stand desk"),
    ("faceless-truth-teller", "commentary", "news politics drama gossip truth "
     "exposed"),
]
_RESEARCH_PHRASES = {"white noise": ("lifestyle", "wellness"),
                     "weight loss": ("lifestyle", "wellness"),
                     "spill the tea": ("faceless-truth-teller", "commentary"),
                     "power bank": ("ugc-ads", "gadgets"),
                     "air fryer": ("ugc-ads", "tools")}


def _pack_niche_set(pack):
    s = set()
    if isinstance(pack, dict):
        nh = pack.get("niche_hooks")
        if isinstance(nh, dict):
            s |= {n for n, v in nh.items() if v}
        nm = pack.get("niche_map")
        if isinstance(nm, dict):
            for v in nm.values():
                if isinstance(v, list):
                    s |= {x for x in v if isinstance(x, str)}
    return s


def _research_vote(p, pack):
    low = p.lower()
    toks = set(_words(low))
    scores = {}
    for ph, key in _RESEARCH_PHRASES.items():
        if re.search(r"\b" + re.escape(ph) + r"\b", low):
            scores[key] = scores.get(key, 0) + 2
    for i, (rn, mk, vocab) in enumerate(RESEARCH_VOCAB):
        hits = toks & set(vocab.split())
        if hits:
            scores[(rn, mk)] = scores.get((rn, mk), 0) + len(hits)
    if not scores:
        return {"concept": None, "niche": "default", "confidence": 0.4,
                "research_niche": None, "vouched": False}
    order = [(rn, mk) for rn, mk, _ in RESEARCH_VOCAB]
    best = max(scores.values())
    rn, mk = next(k for k in order if scores.get(k) == best)
    present = _pack_niche_set(pack)
    vouched = bool(present) and (rn in present or mk in present)
    return {"concept": None, "niche": mk, "research_niche": rn,
            "vouched": vouched, "confidence": 1.0 if vouched else 0.6}


def _maker_vote(p):
    import viral_script_maker as vsm   # read-only use of the generator
    ctx = vsm.parse_prompt(p)
    return {"concept": ctx.get("concept"), "niche": ctx.get("niche"),
            "fit": ctx.get("fit"), "category": ctx.get("category"),
            "price": ctx.get("price"),
            "confidence": 0.5 if ctx.get("niche") == "default" else 1.0}


# ------------------------------------------------------------- helpers
def sanitize(prompt):
    """-> (sanitized, errors, warnings)."""
    errors, warnings = [], []
    if prompt is None:
        return "", ["empty prompt"], warnings
    p = unicodedata.normalize("NFKC", str(prompt))
    if re.search(r"[\x00-\x08\x0b-\x1f\x7f]", p):
        warnings.append("control characters removed from the prompt")
        p = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", " ", p)
    if "{" in p or "}" in p:
        warnings.append("template braces stripped from the prompt (D31) — "
                        "a {slot} is never product text")
        p = re.sub(r"[{}]", "", p)
    p = re.sub(r"\s+", " ", p).strip()
    if not p:
        errors.append("empty prompt")
    elif len(p) > MAX_PROMPT_CHARS:
        errors.append(f"prompt is {len(p)} chars (> {MAX_PROMPT_CHARS}) — "
                      f"a product prompt, not a brief")
    return p, errors, warnings


def _price(p):
    m = _PRICE.search(p)
    if not m:
        return None
    return m.group(1) or m.group(2)


def _regulated(p):
    out = []
    low = p.lower()
    for label, rx in REGULATED:
        m = re.search(rx, low)
        if not m:
            continue
        if label == "treatment claim" and _PET_TREATS.search(low):
            continue
        out.append(f"regulated claims category ({label}: {m.group(0)!r}) — "
                   f"claims need substantiation and platform ad-policy review "
                   f"(TikTok/Meta); absolute claims stay blocked (D141)")
    return out


def _majority(values, priority):
    """(winner, count, n_voted) over non-None values; ties -> priority order."""
    vals = [v for v in values if v]
    if not vals:
        return None, 0, 0
    counts = {}
    for v in vals:
        counts[v] = counts.get(v, 0) + 1
    best = max(counts.values())
    tied = [v for v in counts if counts[v] == best]
    for v in priority:
        if v in tied:
            return v, best, len(vals)
    return tied[0], best, len(vals)


def _fit(p, niche, concept, maker_fit):
    if concept == "challenge":
        return "hedonic"          # lived-experience story (maker: hedonic)
    if concept == "routine" or concept == "advice":
        return "neutral"
    if concept == "showcase":
        return "utilitarian"
    toks = set(_words(p))
    u, h = len(toks & _UTIL), len(toks & _HEDONIC)
    if h and not u:
        return "hedonic"
    if u and not h:
        return "utilitarian"
    if u and h:
        return "hedonic" if niche in _HEDONIC_NICHES else "utilitarian"
    if niche in _HEDONIC_NICHES:
        return "hedonic"
    if niche in _UTIL_NICHES:
        return "utilitarian"
    return maker_fit if maker_fit in ("utilitarian", "hedonic") else "neutral"


def _formats(concept, niche, complexity):
    if concept == "showcase":
        return ["pov-vlog", "demo"]
    if concept == "challenge":
        return ["pov-vlog", "talking-head"]
    if concept == "routine":
        return ["pov-vlog"]
    if concept == "advice":
        return ["talking-head"]
    out = ["demo", "review"]
    if niche in ("beauty", "fitness", "pets", "home", "wellness"):
        out.append("transformation")
    if complexity == "high":
        out = ["review", "talking-head", "demo"]
    return out


def _category(p, maker_cat):
    if maker_cat:
        return maker_cat
    toks = [t for t in _words(p) if t not in {"a", "an", "the", "my", "for",
                                               "with", "and", "of"}]
    return toks[-1] if toks else "product"


# --------------------------------------------------------------- route
def route(prompt, presenter=None, fmt=None, pack=None):
    p, input_errors, input_warnings = sanitize(prompt)
    route_warnings, lane_warnings = [], []
    presenter = (presenter or "").strip().lower() or None
    fmt = (fmt or "").strip().lower() or None
    if presenter and presenter not in PRESENTERS:
        input_warnings.append(f"unknown presenter {presenter!r}")
    if fmt and fmt not in FORMATS:
        input_warnings.append(f"unknown format {fmt!r}")
    if pack is None:              # default: the configured research pack
        try:
            pack, _meta = R.load_pack()
        except Exception:  # noqa: BLE001
            pack = None
    elif pack is False:           # explicit "no research" (--no-research)
        pack = None
    input_warnings += _regulated(p)

    votes, maker = [], {}
    for name, fn in (("maker", lambda: _maker_vote(p)),
                     ("lexicon", lambda: _lexicon_vote(p)),
                     ("research", lambda: _research_vote(p, pack))):
        if not p:
            votes.append({"voter": name, "concept": None, "niche": None,
                          "confidence": 0.0})
            continue
        try:
            v = fn()
        except Exception as e:  # noqa: BLE001 — a voter never kills routing
            v = {"concept": None, "niche": None, "confidence": 0.0,
                 "error": f"{type(e).__name__}: {e}"}
            route_warnings.append(f"{name} voter failed: {v['error']}")
        if name == "maker":
            maker = v
        vote = {"voter": name, "concept": v.get("concept"),
                "niche": v.get("niche"), "confidence": v.get("confidence", 0.0)}
        if v.get("error"):
            vote["error"] = v["error"]
        if name == "research":
            vote["research_niche"] = v.get("research_niche")
            vote["vouched"] = v.get("vouched")
        votes.append(vote)

    prio = [v["niche"] for v in votes]   # maker > lexicon > research on ties
    concept, c_n, c_tot = _majority([v["concept"] for v in votes],
                                    [v["concept"] for v in votes])
    niche, n_n, n_tot = _majority([v["niche"] for v in votes], prio)
    agr_c = c_n / max(2, c_tot) if c_tot else 0.0
    agr_n = n_n / max(2, n_tot) if n_tot else 0.0
    agreement = round(min(agr_c, agr_n), 3) if p else 0.0
    confs = [v.get("confidence") or 0.0 for v in votes]
    confidence = round(agreement * (sum(confs) / len(confs)), 3) if confs else 0.0
    if p and agreement < AGREEMENT_MIN - 1e-9:
        route_warnings.append(
            f"route agreement {agreement:.2f} < 0.67 — voters disagree: " +
            ", ".join(f"{v['voter']}={v['concept'] or '-'}/{v['niche'] or '-'}"
                      for v in votes))
    mk_niche = maker.get("niche")
    if p and mk_niche and niche and mk_niche != niche and n_n >= 2:
        why = ("maker fall-through to default" if mk_niche == "default"
               else "likely a substring hijack in the maker's niche routing")
        route_warnings.append(
            f"maker niche {mk_niche!r} outvoted by {niche!r} "
            f"({n_n}/{n_tot} voters) — {why} (D11 class)")
    if p and maker.get("concept") and concept and maker["concept"] != concept:
        route_warnings.append(f"maker concept {maker['concept']!r} differs "
                              f"from the routed concept {concept!r}")

    concept = concept or "product"
    niche = niche or "default"
    price = _price(p) if p else None
    fit = _fit(p, niche, concept, maker.get("fit"))
    category = _category(p, maker.get("category"))
    # B15: finance, medical and technical-spec SKUs (not creator advice)
    complexity = "high" if (niche == "finance" or _COMPLEX.search(p)) else "low"
    shop = bool(_TIKTOK_SHOP.search(p))

    if shop:
        rec, why = "human", ("TikTok Shop lane: Shop quality rules need "
                             "visible people and ban AI voices in LIVE")
    elif concept in ("challenge", "routine"):
        rec, why = "human", (f"D137: a {concept} is first-person lived "
                             f"experience — an AI persona cannot claim it")
    elif complexity == "high":
        rec, why = "ai", ("B15: high-complexity SKU — an AI presenter is "
                          "evidence-favored even where hedonic rules would "
                          "exclude it")
    elif fit == "utilitarian":
        rec, why = "ai", ("F32: utilitarian SKU — the congruent lane for AI "
                          "personas")
    elif fit == "hedonic":
        rec, why = "human", ("F32: hedonic SKU — humans convert better; an AI "
                             "persona is the wrong anchor")
    else:
        rec = presenter or "human"
        why = (f"F32: fit unclear — test both anchors (defaulting to {rec})")

    if presenter == "ai":
        if shop:
            lane_warnings.append("TikTok Shop + AI presenter: Shop quality "
                                 "rules need visible people and AI voices are "
                                 "banned in LIVE — route to a human or hybrid")
        if concept in ("challenge", "routine"):
            lane_warnings.append(f"AI presenter on a {concept}: the genre is "
                                 f"lived experience (D137) — use a human, or a "
                                 f"curator frame about someone else's log")
        if fit == "hedonic" and complexity != "high" and not shop:
            lane_warnings.append("F32: hedonic SKU + AI persona — humans "
                                 "convert better (consider --presenter human)")
        if any(w.startswith("regulated claims") for w in input_warnings):
            lane_warnings.append("AI persona in a regulated claims category: "
                                 "no testimonials (FTC 16 CFR 465.2), every "
                                 "claim needs substantiation")
    formats = _formats(concept, niche, complexity)
    if fmt and fmt in FORMATS and fmt not in formats:
        lane_warnings.append(f"format {fmt!r} is off-lane for concept "
                             f"{concept!r} (recommended: {', '.join(formats)})")

    warnings = input_warnings + route_warnings + lane_warnings
    return {
        "prompt": prompt, "sanitized_prompt": p, "price": price,
        "concept": concept, "niche": niche, "fit": fit, "category": category,
        "complexity": complexity, "votes": votes, "agreement": agreement,
        "confidence": confidence, "recommended_presenter": rec,
        "presenter_reason": why, "recommended_formats": formats,
        "lane_warnings": lane_warnings, "input_errors": input_errors,
        "input_warnings": input_warnings, "route_warnings": route_warnings,
        "warnings": warnings, "presenter": presenter, "format": fmt,
        "strict_ok": not input_errors and agreement >= AGREEMENT_MIN - 1e-9,
    }


def summary_line(r):
    return (f"route: {r['concept']}/{r['niche']} fit={r['fit']} "
            f"complexity={r['complexity']} agreement={r['agreement']:.2f} "
            f"-> presenter {r['recommended_presenter']} "
            f"({', '.join(r['recommended_formats'])})")


if __name__ == "__main__":
    import json
    import sys
    args = sys.argv[1:]
    print(json.dumps(route(" ".join(args) if args else ""), indent=1,
                     ensure_ascii=False))
