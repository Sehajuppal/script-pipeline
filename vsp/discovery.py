"""Discovery packaging (pipeline v2.1, WS-DISCOVERY) — CREATIVE-PLAN §1.3.

One primary search keyword per video, placed where the three platforms match
queries on text (spoken by 3.0 s, on screen by 3.0 s, the first 60 chars of
caption line 1, one hashtag, the cover), plus post-ready packaging for
TikTok, Instagram Reels and YouTube Shorts, cover and posting guidance.

    keywords_for(script, ctx=None, pack=None) -> (primary, secondary, intents)
    build(script, ctx=None, seed=None, maker=None) -> dict | None
    check(discovery, script) -> [str]           (own D155 checker, errors)
    render_md(discovery, script) -> str         ("## POSTING & DISCOVERY")
    selfcheck() -> (ok, lines)                  (hermetic, in-process)
    python3 -m vsp.discovery selfcheck | show "<prompt>" [--format F --presenter P]

Evidence and tables: docs/research/discovery-seo.md, transcribed into
vsp/data/discovery.json (research blocks verbatim; ENGINE = engine tables).

The maker's caption region (viral_script_maker.build_caption, _cta_word,
_scoped_tags) calls primary_keyword / caption_line1 / compact_tag /
comment_word_parts, so the script caption and the discovery packaging share
one keyword. Deterministic: no rng, no set iteration in outputs, stdlib only,
no network.
"""
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(_HERE, "data", "discovery.json")
_DATA = None


def data():
    """The discovery tables (loaded once)."""
    global _DATA
    if _DATA is None:
        with open(DATA_PATH, encoding="utf-8") as f:
            _DATA = json.load(f)
    return _DATA


def _eng():
    return data()["ENGINE"]


def _kwt():
    return _eng()["keyword"]


_SETS = {}


def _set(name):
    """frozenset view of an ENGINE.keyword list (membership only — never
    iterated into an output)."""
    s = _SETS.get(name)
    if s is None:
        s = _SETS[name] = frozenset(_kwt()[name])
    return s


# ------------------------------------------------------------ text helpers
_TOK = re.compile(r"[a-z0-9]+(?:[-'’][a-z0-9]+)*")
_FUNCTION = frozenset("""a an the of for with to and or in on at by from my your
our their his her its this that these those no not is are be was were it i
you me we they them just so very""".split())
_LEMMA_KEEP3 = frozenset({"yes", "its", "his", "has", "was", "gas", "bus",
                          "ups", "abs", "his", "this", "plus", "does", "goes"})
_ADJ_RX = re.compile(r"(?:ic|ical|able|ible|less|ive|ous|ful|ized|ised|ated)$")


def tokens(text):
    """Lowercase word tokens ("self-cleaning", "3-in-1", "5am" stay whole)."""
    return _TOK.findall(str(text or "").lower().replace("’", "'"))


def lemma(word):
    """Singular form for matching and for the keyword head noun. Pair nouns
    (earbuds, glasses, eyelashes) keep their plural."""
    w = str(word or "").lower()
    if w in _set("pair_nouns") or w in _set("no_singular"):
        return w
    if len(w) <= 2 or w in _LEMMA_KEEP3:
        return w
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith(("ches", "shes", "sses", "xes", "zes")):
        return w[:-2]
    if w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def _adj_like(w):
    return len(w) >= 6 and bool(_ADJ_RX.search(w))


def content_lemmas(text):
    return [lemma(t) for t in tokens(text) if t not in _FUNCTION]


def _word_rx(word, last):
    """Regex for one keyword token; the last token tolerates its plural."""
    w = re.escape(word)
    if not last:
        return w
    if word.endswith("y") and len(word) > 2:
        return re.escape(word[:-1]) + "(?:y|ies)"
    base = word[:-1] if (word.endswith("s") and len(word) > 3) else word
    return re.escape(base) + "(?:s|es)?"


_RX_CACHE = {}


def phrase_rx(phrase):
    """Compiled matcher: the phrase's tokens in order, separated by spaces or
    hyphens, plural-tolerant on the last token, word-bounded."""
    rx = _RX_CACHE.get(phrase)
    if rx is None:
        toks = tokens(phrase)
        if not toks:
            rx = re.compile(r"(?!x)x")
        else:
            body = r"[\s\-]+".join(_word_rx(t, i == len(toks) - 1)
                                   for i, t in enumerate(toks))
            rx = re.compile(r"(?<![a-z0-9])" + body + r"(?![a-z0-9])", re.I)
        _RX_CACHE[phrase] = rx
    return rx


def keyword_end(text, keyword):
    """Char index just past the first exact (case/plural-tolerant) match of
    `keyword` in `text`, or -1."""
    m = phrase_rx(keyword).search(str(text or ""))
    return m.end() if m else -1


def has_keyword(text, keyword, within=None):
    """Exact phrase match (case-insensitive, plural-tolerant head), optionally
    ending within the first `within` chars."""
    end = keyword_end(text, keyword)
    return end >= 0 and (within is None or end <= within)


def has_lemmas(text, keyword):
    """Order-free match: every content-word lemma of the keyword occurs."""
    have = set(content_lemmas(text))
    need = content_lemmas(keyword)
    return bool(need) and all(n in have for n in need)


def head_noun(keyword):
    """The keyword's last word (singular head noun, pair nouns plural)."""
    toks = tokens(keyword)
    return toks[-1] if toks else ""


def anchor(keyword):
    """What placement matching looks for: the head noun, or the compound
    (previous word + head) when the head alone is ambiguous in speech
    ("trash can", "laptop stand", "power bank")."""
    toks = tokens(keyword)
    if not toks:
        return ""
    if toks[-1] in _set("weak_heads") and len(toks) >= 2:
        return " ".join(toks[-2:])
    return toks[-1]


def anchor_in(text, keyword):
    a = anchor(keyword)
    return bool(a) and phrase_rx(a).search(str(text or "")) is not None


def compact_tag(keyword):
    """"milk frother" -> "#milkfrother" (None when it carries < 3 letters)."""
    t = re.sub(r"[^a-z0-9]", "", str(keyword or "").lower())
    return "#" + t if len(re.sub(r"[^a-z]", "", t)) >= 3 else None


def _article(phrase):
    """"a milk frother" / "an eye mask" / "magnetic eyelashes" (plural)."""
    toks = tokens(phrase)
    if not toks:
        return phrase
    head = toks[-1]
    plural = (head in _set("pair_nouns")
              or (head.endswith("s") and lemma(head) != head))
    if plural:
        return phrase
    first = toks[0]
    an = first[:1] in "aeiou" and not first.startswith(("uni", "use", "eu"))
    return ("an " if an else "a ") + phrase


def _cap(s):
    return s[:1].upper() + s[1:] if s else s


# ----------------------------------------------------- primary keyword
def _product_phrase(product):
    """Normalized search phrase of a product name (KEYWORD_RULES rule 1):
    no price/brace/determiner, no "with/for ..." tail, no pack tail, spec
    modifiers dropped ("electric milk frother" -> "milk frother"), singular
    head, 2-4 words."""
    p = re.sub(r"[{}]", "", str(product or ""))
    p = re.sub(r"\$\s?\d+(?:[.,]\d+)?", " ", p)
    core = re.split(r"\s+(?:with|for|in|on|from)\s+", p.strip(), maxsplit=1,
                    flags=re.I)[0]
    toks = tokens(core)
    while toks and toks[0] in _set("strip_leading"):
        toks.pop(0)
    toks = [t for t in toks if not re.search(r"\d", t)] or toks
    if len(toks) >= 2 and toks[-1] in _set("pack_tails"):
        toks = toks[:-1]
    kept = [t for t in toks if t not in _set("drop_modifiers")]
    if len(kept) < 2 and len(toks) >= 2:
        kept = toks[-2:]              # "led lamp": never a 1-word keyword
    kept = kept or toks
    while len(kept) > 3 and _adj_like(kept[0]):
        kept.pop(0)                   # "reusable silicone food bags"
    kept = kept[-_kwt()["max_words"]:]
    if not kept:
        return ""
    kept[-1] = lemma(kept[-1])
    if len(kept) == 1:
        kept.append("review")         # KEYWORD_RULES min 2 words
    return " ".join(kept)


_CONSUME = ("drinking", "eating", "having", "using", "taking", "smoking")
_DETOX = ("instagram", "tiktok", "youtube", "netflix", "facebook", "twitter",
          "snapchat", "reddit", "threads", "social media", "phone")


def _challenge_phrase(ctx):
    n = str(ctx.get("span_n") or "30")
    toks = [t for t in tokens(ctx.get("challenge_noun"))
            if t not in _set("strip_leading")]
    if ctx.get("challenge_type") == "practice":
        g = toks[0] if toks else ""
        return f"{n} day {g} challenge" if g.endswith("ing") else f"{n} day challenge"
    if not toks or " ".join(toks) == "habit worth breaking":
        return f"{n} day challenge"
    if len(toks) >= 2 and toks[0] in _CONSUME:
        toks = toks[1:]               # "drinking soda" -> "soda"
    if toks[-1] == "apps" and len(toks) >= 2:
        toks = toks[:-1]              # "social media apps" -> "social media"
    thing = " ".join(toks)
    if thing in _DETOX:
        return f"{thing} detox"
    # gerund vices read as "quit buying coffee" / "quit doomscrolling"; noun
    # vices as the research's "no sugar challenge"
    cands = ((f"quit {thing}",) if toks[0].endswith("ing")
             else (f"no {thing} challenge", f"no {thing}"))
    for cand in cands:
        if len(cand.split()) <= _kwt()["max_words"]:
            return cand
    return f"{n} day challenge"


_ROUTINE_CUT = frozenset("before after for with on at in during while to".split())


def _routine_phrase(ctx):
    label = str(ctx.get("routine_label") or ctx.get("product") or "")
    low = label.lower()
    if re.search(r"\bday in (?:my|the) life\b", low):
        return "day in my life"
    if re.search(r"\bgrwm\b|\bget ready with me\b", low):
        return "grwm routine"
    toks = tokens(label)
    while toks and toks[0] in _set("strip_leading"):
        toks.pop(0)
    out = []
    for t in toks:
        if t in _ROUTINE_CUT and out:
            break
        out.append(t)
    out = out[:_kwt()["max_words"]]
    if len(out) == 1 and out[0] != "routine":
        out.append("routine")
    return " ".join(out) or "daily routine"


def _showcase_phrase(ctx):
    toks = [t for t in tokens(ctx.get("domain") or "space")
            if t not in _set("strip_leading")][-2:]
    return " ".join(toks + ["finds"])


def _advice_phrase(ctx):
    topic = str(ctx.get("product") or "")
    low = topic.lower().strip()
    m = re.match(r"^how to\s+(.+)$", low)
    if m:
        rest = [t for t in tokens(m.group(1)) if t not in _set("strip_leading")]
        return "how to " + " ".join(rest[:2]) if rest else "how to tips"
    toks = tokens(low)
    frame, verbs = _set("advice_frame"), _set("advice_verbs")
    head = str(ctx.get("category") or "").lower()
    if head in toks:
        i = toks.index(head)
    else:
        i = next((j for j, t in enumerate(toks)
                  if t not in frame and t not in verbs), None)
        if i is None:
            return "creator tips"
    phrase = [toks[i]]
    j = i + 1
    while (j < len(toks) and len(phrase) < 2 and toks[j] not in frame
           and toks[j] not in verbs and not toks[j].endswith("ing")):
        phrase.append(toks[j])
        j += 1
    phrase[-1] = lemma(phrase[-1])
    return " ".join(phrase) + " tips"


def primary_keyword(ctx):
    """The one primary search keyword for a parsed prompt (maker ctx), per
    concept: product -> head-noun phrase ("milk frother"); challenge -> "no
    sugar challenge" / "30 day reading challenge" / "instagram detox";
    routine -> "5am morning routine"; showcase -> "kitchen finds"; advice ->
    "<topic> tips" / "how to <topic>". Depends only on the prompt-derived
    ctx fields (never on format, seed or hook), so a product keeps one
    keyword across every run."""
    ctx = ctx or {}
    c = ctx.get("concept") or "product"
    if c == "challenge":
        kw = _challenge_phrase(ctx)
    elif c == "routine":
        kw = _routine_phrase(ctx)
    elif c == "showcase":
        kw = _showcase_phrase(ctx)
    elif c == "advice":
        kw = _advice_phrase(ctx)
    else:
        kw = _product_phrase(ctx.get("product") or ctx.get("category"))
    return " ".join(kw.split()) or "product review"


def comment_word_parts(keyword):
    """(head_word, fallback_word) for the comment word: the keyword's head
    noun uppercased (FROTHER, PILLOWCASE) — research §2: a comment word equal
    to the head noun seeds TikTok search suggestions. A container head
    (machine/stick/can/maker, D34) gives head_word=None and the previous
    keyword word as the fallback (WAFFLE); the maker then prefers its niche
    noun (CAR, SLEEP, HAIR). Single tokens only (the bait window is sized by
    words)."""
    toks = tokens(keyword)
    if not toks:
        return None, None
    over = _kwt()["comment_word_overrides"]
    hit = over.get(" ".join(toks[-2:])) or over.get(toks[-1])
    if hit:
        return hit, None

    def word(t):
        w = re.sub(r"[^A-Za-z0-9]", "", t).upper()
        return w if re.match(r"^[A-Z][A-Z0-9]+$", w) else None

    head = toks[-1]
    if head in _set("comment_generic_heads"):
        prev = toks[-2] if len(toks) >= 2 else None
        ok = prev and not _adj_like(prev) and prev not in _set("drop_modifiers")
        return None, (word(prev) if ok else None)
    return word(head), None


# ---------------------------------------------------- caption line 1
_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'-]*")


def display_keyword(keyword, ctx=None, text=None):
    """The keyword as it should read in copy: acronyms and mid-sentence
    proper nouns keep the prompt's casing ("UGC ad tips", "Instagram
    detox", "5AM routine"); everything else stays lowercase. The stored
    keyword (primary_keyword) is always lowercase."""
    ctx = ctx or {}
    src = text if text is not None else (ctx.get("prompt_text")
                                         or ctx.get("_prompt") or "")
    casing = {}
    for i, w in enumerate(_WORD.findall(str(src))):
        lw = w.lower()
        if lw in casing:
            continue
        acronym = len(w) >= 2 and w.isupper()
        proper = i > 0 and len(w) > 1 and w[0].isupper() and w[1:].islower()
        if acronym or proper:
            casing[lw] = w
    return " ".join(casing.get(t, t) for t in str(keyword or "").split())


def _fmt_vars(keyword, ctx=None):
    ctx = ctx or {}
    kw = display_keyword(keyword, ctx)
    return {"kw": kw, "Kw": _cap(kw), "KW": kw.upper(),
            "a_kw": _article(kw), "A_kw": _cap(_article(kw)),
            "n": str(ctx.get("span_n") or ""),
            "streak": str(ctx.get("streak") or "")}


def _concept_template(table, concept, fmt):
    t = table.get(concept if concept in table else "product")
    if isinstance(t, dict):
        t = t.get(fmt) or t.get("demo") or next(iter(t.values()))
    return t


def keyword_sentence(keyword, ctx=None, fmt="demo"):
    """The natural keyword-first sentence that joins caption line 1 when the
    hook does not carry the keyword ("No sugar challenge, day by day.")."""
    c = (ctx or {}).get("concept") or "product"
    t = _concept_template(_eng()["keyword_sentence"], c, fmt)
    return t.format(**_fmt_vars(keyword, ctx))


def caption_line1(hookline, keyword, ctx=None, fmt="demo"):
    """Caption line 1 with the primary keyword in its first 60 chars: the
    hook line when it already says the keyword there; otherwise the hook
    plus a keyword sentence (keyword still inside 60 chars), else the
    keyword sentence first. Line 1 stays <= 100 chars (TikTok's visible
    first line): past that the hook moves to line 2 (the return value then
    holds two lines)."""
    hook = " ".join(str(hookline or "").split())
    within = _eng()["d155"]["caption_first_line_within"]
    if not keyword or has_keyword(hook, keyword, within):
        return hook
    sent = keyword_sentence(keyword, ctx, fmt)
    if not hook:
        return sent
    joined = f"{hook} {sent}"
    if 0 <= keyword_end(joined, keyword) <= within and len(joined) <= 100:
        return joined
    first = f"{sent} {hook}"
    return first if len(first) <= 100 else f"{sent}\n{hook}"


# ------------------------------------------------------------ context
def _maker_module(maker=None):
    """The already-loaded maker (never imports it: it may be __main__)."""
    if maker is not None:
        return maker
    m = sys.modules.get("viral_script_maker")
    if m is None:
        main = sys.modules.get("__main__")
        if main is not None and hasattr(main, "parse_prompt") \
                and hasattr(main, "build_caption"):
            m = main
    return m


def _clean_prompt(prompt):
    return re.sub(r"\s+", " ", re.sub(r"[{}]", "", str(prompt or ""))).strip()


def _light_ctx(prompt):
    """Prompt -> minimal ctx when no maker is loaded (--script-json)."""
    p = _clean_prompt(prompt)
    low = p.lower()
    m = re.search(r"\bi\s+(?:stopped|quit|gave up|deleted|ditched|dropped|"
                  r"unfollowed)\s+(.+?)\s+for\s+(\d+)\s*days?\b", low)
    if m:
        return {"concept": "challenge", "challenge_type": "abstinence",
                "challenge_noun": m.group(1), "span_n": m.group(2),
                "prompt_text": p}
    m = re.search(r"\bi\s+([a-z]+ed|ran|read|ate|swam|wrote|woke)\s+(.+?)\s+"
                  r"for\s+(\d+)\s*days?\b", low)
    if m:
        verb = m.group(1)
        ger = {"ran": "running", "read": "reading", "ate": "eating",
               "swam": "swimming", "wrote": "writing", "woke": "waking"}.get(
            verb, re.sub(r"ed$", "ing", verb))
        return {"concept": "challenge", "challenge_type": "practice",
                "challenge_noun": f"{ger} {m.group(2)}", "span_n": m.group(3),
                "prompt_text": p}
    m = re.search(r"\bthings in my\s+([a-z ]+?)(?:\s+that\s|\s+which\s|\s*$)", low)
    if m:
        return {"concept": "showcase", "domain": m.group(1).strip(),
                "prompt_text": p}
    if re.search(r"\broutine\b|\bgrwm\b|\bget ready with me\b|\bday in (?:my|the) life\b", low):
        return {"concept": "routine", "routine_label": p, "prompt_text": p}
    if re.search(r"^(?:why|how|what no one|what nobody|the truth about|the secret)\b|"
                 r"\bmistakes?\b|\btips\b|\bhacks\b|\bfails?\b", low) \
            and not re.search(r"\$\d", p):
        return {"concept": "advice", "product": p, "prompt_text": p}
    prod = re.sub(r"^(?:make (?:me )?a (?:script|video) (?:about|for|on)\s*)", "",
                  p, flags=re.I)
    return {"concept": "product", "product": prod, "prompt_text": p,
            "price": (re.search(r"\$(\d+(?:\.\d+)?)", p) or [None, None])[1]}


def _ctx_for(script, ctx=None, maker=None):
    if isinstance(ctx, dict) and ctx.get("concept"):
        return ctx
    prompt = _clean_prompt(script.get("prompt"))
    m = _maker_module(maker)
    if m is not None and hasattr(m, "parse_prompt"):
        try:
            c = dict(m.parse_prompt(prompt))
            c.setdefault("prompt_text", prompt)
            return c
        except Exception:
            pass
    return _light_ctx(prompt)


_PACK_CACHE = {}


def _pack_for(maker=None, pack=None):
    """The research pack the maker itself runs on (maker._PACK, honouring
    --no-research), else vsp.research.load_pack() cached per file state."""
    if isinstance(pack, dict):
        return pack
    m = _maker_module(maker)
    if m is not None and hasattr(m, "_PACK"):
        if getattr(m, "_NO_RESEARCH", False):
            return None
        return m._PACK if isinstance(m._PACK, dict) else None
    try:
        from vsp import config, research
        path = config.research_pack_path()
        st = os.stat(path)
        key = (path, st.st_mtime_ns, st.st_size)
        if key not in _PACK_CACHE:
            _PACK_CACHE.clear()
            _PACK_CACHE[key] = research.load_pack(path)[0]
        return _PACK_CACHE[key]
    except Exception:
        return None


# ------------------------------------------------------------ screens
def _d158_rx():
    rx = _SETS.get("_d158")
    if rx is None:
        rx = _SETS["_d158"] = [re.compile(p, re.I) for p in _eng()["d158_patterns"]]
    return rx


def d158_hits(text, prompt=""):
    """D158: fake urgency / scarcity / offer phrases the prompt does not
    supply ("limited time", "only 3 left", "sale ends", "20% off")."""
    hits = []
    for rx in _d158_rx():
        m = rx.search(text or "")
        if m and not rx.search(prompt or ""):
            hits.append(m.group(0))
    return hits


def screen(text, script):
    """D37, D136, D139, D141 (the gate's own rule functions, run on `text`
    as if it were the caption) + D158 (the registry's rule when present, and
    this module's patterns). -> list of messages."""
    from vsp import gates as G
    from vsp import lexicon as L
    from vsp import rules as R
    prompt = str(script.get("prompt") or "")
    fake = {"prompt": prompt, "presenter": script.get("presenter", ""),
            "caption": text or "", "hook_stack": [], "beats": []}
    ctx = R.build_ctx(fake)
    out = list(G.g1_d37_price(fake))
    m = L.PRICE.search(text or "")
    if m and not L.PRICE.search(prompt) and not out:
        out.append(f"D37: price {m.group(0)!r} but none in the prompt")
    for fn in (R.check_d136, R.check_d139, R.check_d141):
        out += fn(fake, None, ctx)
    for r in R.REGISTRY:
        if r.id == "D158" and r.stage == "script":
            try:
                out += r.check(fake, None, ctx) or []
            except Exception as e:  # noqa: BLE001 — fail closed
                out.append(f"D158: check crashed ({type(e).__name__})")
    hits = d158_hits(text, prompt)
    if hits:
        out.append(f"D158: fake urgency/offer ({', '.join(repr(h) for h in hits[:3])})"
                   f" not supplied by the prompt")
    return out


def _clean_phrase(phrase, script):
    return not screen(phrase, script)


# --------------------------------------------------- keywords_for
_EDGE_STOP = _FUNCTION | frozenset("""how what why when who which where do does
did can could will would should get got make made just really so then than
also too more most much many every all any some one two three new day days
wait watch look here there""".split())


def _pack_lines(pack, niche):
    """(text, weight) hook lines of the niche's research niches: fresh hook
    lines and, when present, top_reels hook_text (views-weighted)."""
    if not isinstance(pack, dict):
        return []
    try:
        from vsp import research
        niches = research.pack_niches_for(niche or "default", pack)
        spoken = research.is_spoken_hook_line
    except Exception:
        niches, spoken = [niche or "default"], (lambda t: isinstance(t, str))
    out = []
    for r in pack.get("fresh_hook_lines") or []:
        if isinstance(r, dict) and r.get("niche") in niches and spoken(r.get("hook")):
            out.append((r["hook"], 1.0))
    tops = pack.get("top_reels")
    rows = []
    if isinstance(tops, dict):
        for n in niches:
            rows += [x for x in (tops.get(n) or []) if isinstance(x, dict)]
    elif isinstance(tops, list):
        rows = [x for x in tops if isinstance(x, dict) and x.get("niche") in niches]
    for r in rows:
        t = r.get("hook_text") or r.get("hook")
        if spoken(t):
            v = r.get("views") if isinstance(r.get("views"), (int, float)) else 0
            out.append((t, 1.0 + min(3.0, max(0.0, len(str(int(v))) - 3) / 2.0)))
    return out


def _mine_pack(pack, niche, primary, topic_words, script):
    """KEYWORD_RULES rule 4 (research-DB half): 2-3-word phrases from the
    niche's hook lines that share a content lemma with the keyword/topic,
    hashtags/emoji removed, weighted by views when present -> [(phrase, score)]."""
    lines = _pack_lines(pack, niche)
    if not lines:
        return []
    want = set(content_lemmas(primary)) | set(topic_words)
    counts, order = {}, []
    for text, w in lines:
        toks = tokens(re.sub(r"#\w+", " ", text))
        for n in (3, 2):
            for i in range(len(toks) - n + 1):
                g = toks[i:i + n]
                if g[0] in _EDGE_STOP or g[-1] in _EDGE_STOP:
                    continue
                if any(t.isdigit() for t in g):
                    continue
                if not want & {lemma(t) for t in g}:
                    continue
                ph = " ".join(g)
                if ph not in counts:
                    counts[ph] = 0.0
                    order.append(ph)
                counts[ph] += w
    if not counts:
        return []
    top = max(counts.values())
    out = [(ph, round(0.5 * counts[ph] / top, 3)) for ph in order]
    out.sort(key=lambda x: (-x[1], len(x[0].split()), x[0]))
    return [(ph, s) for ph, s in out[:8] if _clean_phrase(ph, script)][:4]


def _overlaps(a, b):
    la, lb = set(content_lemmas(a)), set(content_lemmas(b))
    return not la or not lb or la <= lb or lb <= la


def _topic_phrases(ctx, primary):
    e = _eng()
    c = ctx.get("concept") or "product"
    if c == "challenge":
        key = ("practice" if ctx.get("challenge_type") == "practice"
               else (ctx.get("abstinence_class") or "screen"))
        return list(e["challenge_topics"].get(key, []))
    if c == "routine":
        low = " ".join(str(ctx.get(k) or "") for k in ("routine_label", "routine_time")).lower()
        key = ("gym" if "gym" in low else "night" if "night" in low
               else "morning" if ("am" in tokens(low) or "morning" in low
                                  or re.search(r"\d(?:am)\b", low)) else "default")
        return list(e["routine_topics"][key])
    if c == "showcase":
        dom = " ".join(tokens(ctx.get("domain") or "space"))
        key = next((k for k in e["showcase_topics"] if k != "default" and k in dom), "default")
        return [p.format(domain=dom) for p in e["showcase_topics"][key]]
    if c == "advice":
        topic = " ".join(primary.split()[:-1]) if primary.endswith(" tips") else primary
        creator = re.search(r"\b(hooks?|views|followers|algorithm|content|creators?|"
                            r"reels?|captions?|videos?|ugc)\b", str(ctx.get("product") or ""), re.I)
        rows = e["advice_topics"]["creator" if creator else "default"]
        return [p.format(topic=topic) for p in rows]
    cue = " ".join(str(ctx.get(k) or "") for k in ("prompt_text", "product", "category")).lower()
    for row in e["secondary_topics"]:
        if re.search(row["match"], cue):
            return list(row["phrases"])
    return []


def _use_tail(ctx):
    m = re.search(r"\s+for\s+(?:the\s+|a\s+|an\s+|my\s+)?([a-z][a-z ]{1,24})$",
                  str(ctx.get("product") or "").lower())
    return m.group(1).strip() if m else None


def _intents(primary, ctx, fmt, script):
    """KEYWORD_RULES.intent_templates for the format (guardrails: no
    unsupported superlative claim — "best" only as a question label (D141);
    price intents only with a supplied price (D37); "vs" only with a named
    competitor; "before and after" only on the transformation format)."""
    c = ctx.get("concept") or "product"
    out = []
    if c == "product":
        for t in data()["KEYWORD_RULES"]["intent_templates"]:
            tpl = t["template"]
            fmts = list(t["formats"])
            if "before and after" in tpl:
                fmts = ["transformation"]
            if fmt not in fmts or "{habit}" in tpl or "{thing}" in tpl:
                continue
            if "{alternative}" in tpl and not ctx.get("named_competitor"):
                continue
            if "{price}" in tpl and not ctx.get("price"):
                continue
            use = _use_tail(ctx)
            if "{use}" in tpl and not use:
                continue
            s = tpl.format(product=primary, category=anchor(primary),
                           alternative=ctx.get("named_competitor") or "",
                           use=use or "", price=ctx.get("price") or "")
            if s.startswith("best "):
                s += "?"
            out.append(s)
        if not out:
            out = [f"is {_article(primary)} worth it", f"how to use {_article(primary)}"]
    elif c == "challenge":
        n = str(ctx.get("span_n") or "30")
        noun = " ".join(t for t in tokens(ctx.get("challenge_noun"))
                        if t not in _set("strip_leading"))
        if ctx.get("challenge_type") == "practice":
            out = [f"{n} day {noun.split()[0] if noun else 'habit'} challenge",
                   f"how to build a {noun.split()[0] if noun else 'daily'} habit"]
        else:
            out = [f"quit {noun} for {n} days", f"how to quit {noun}"]
    elif c == "routine":
        out = [f"{primary} ideas", f"{primary} for beginners"]
    elif c == "showcase":
        dom = " ".join(tokens(ctx.get("domain") or "space"))
        out = [f"{dom} must haves", f"best {dom} gadgets?"]
    else:
        topic = " ".join(primary.split()[:-1]) if primary.endswith(" tips") else primary
        q = " ".join(t for t in tokens(ctx.get("product")) if t not in ("your", "my"))
        out = [f"how to fix {topic}", q]
    res = []
    for s in out:
        s = " ".join(s.split())
        if s and s != primary and s not in res and _clean_phrase(s, script):
            res.append(s)
    return res[:4]


def keywords_for(script, ctx=None, pack=None):
    """-> (primary, secondary[<=2], intents[<=4]). The primary is the
    prompt's (primary_keyword, pack-independent, so every run of a product
    shares it); secondary keywords are mined read-only from the research
    pack's niche hook lines (fresh_hook_lines, top_reels hook_text) and the
    engine's topic table, non-overlapping with the primary and each other;
    intents come from KEYWORD_RULES.intent_templates under its guardrails."""
    primary, secondary, intents, _ = _keywords(script, ctx=ctx, pack=pack)
    return primary, secondary, intents


def _keywords(script, ctx=None, pack=None, maker=None):
    script = script if isinstance(script, dict) else {}
    ctx = _ctx_for(script, ctx, maker)
    if pack is None:
        pack = _pack_for(maker)
    primary = primary_keyword(ctx)
    topic_words = [lemma(t) for t in tokens(" ".join(str(ctx.get(k) or "") for k in
                   ("category", "domain", "challenge_noun"))) if t not in _FUNCTION]
    sources = [{"keyword": primary, "role": "primary", "source": "prompt",
                "score": None}]
    cands = [(p, "research-pack", s) for p, s in
             _mine_pack(pack, ctx.get("niche") or script.get("niche"), primary,
                        topic_words, script)]
    cands += [(p, "topic-table", None) for p in _topic_phrases(ctx, primary)]
    secondary = []
    for ph, src, score in cands:
        if len(secondary) >= 2:
            break
        if _overlaps(ph, primary) or any(_overlaps(ph, s) for s in secondary):
            continue
        if not _clean_phrase(ph, script):
            continue
        secondary.append(ph)
        sources.append({"keyword": ph, "role": "secondary", "source": src,
                        "score": score})
    intents = _intents(primary, ctx, str(script.get("format") or "demo"), script)
    sources += [{"keyword": s, "role": "intent", "source": "intent-template",
                 "score": None} for s in intents]
    return primary, secondary, intents, sources


# ------------------------------------------------------------ build
_T_RX = re.compile(r"(\d+(?:\.\d+)?)")


def _window(t):
    m = _T_RX.findall(str(t or ""))
    return (float(m[0]), float(m[1])) if len(m) >= 2 else (None, None)


def _timed(script):
    """[(start, end, item)] for hook_stack + beats, time-ordered."""
    out = []
    for key in ("hook_stack", "beats"):
        for it in script.get(key) or []:
            if isinstance(it, dict):
                s, e = _window(it.get("t"))
                if s is not None:
                    out.append((s, e, it))
    out.sort(key=lambda x: (x[0], x[1]))
    return out


def _verbal_hook(script):
    for it in script.get("hook_stack") or []:
        if isinstance(it, dict):
            t = str(it.get("type") or "").upper()
            if ("VERBAL HOOK" in t or t == "HOOK") and str(it.get("dialogue") or "").strip():
                return " ".join(str(it["dialogue"]).split())
    return ""


def _first_end(timed, fields, keyword):
    for s, e, it in timed:
        if any(anchor_in(it.get(f), keyword) for f in fields):
            return round(e, 2)
    return None


def _caption_parts(caption):
    lines = str(caption or "").split("\n")
    opening = []
    for ln in lines:
        if not ln.strip():
            break
        opening.append(ln.strip())
    cta = next((ln.strip() for ln in lines
                if re.match(r"^\s*[Cc]omment\s+[A-Z][A-Z0-9]+\b", ln)), None)
    from vsp import lexicon as L
    ai = next((ln.strip() for ln in lines if L.has_ai_disclosure_line(ln)), None)
    tags = re.findall(r"#\w+", str(caption or ""))
    return opening, cta, ai, tags


def _comment_word(script, cta_line):
    spoken = " ".join(str(it.get(k) or "") for _, _, it in _timed(script)
                      for k in ("dialogue", "rehook"))
    m = re.search(r"\bcomment\s+([A-Z][A-Z0-9]{1,})\b", spoken)
    if m:
        return m.group(1)
    m = re.search(r"\bcomment\s+([A-Z][A-Z0-9]{1,})\b", cta_line or "", re.I)
    return m.group(1).upper() if m else None


def _cover(script, ctx, keyword, fmt, timed):
    e = _eng()
    payoff = next(((s, it) for s, _, it in timed
                   if str(it.get("type") or "").upper() == "PAYOFF"), None)
    frame = round(payoff[0], 2) if payoff else 0.0
    c = ctx.get("concept") or "product"
    t = _concept_template(e["cover_text"], c, fmt)
    text = " ".join(t.format(**_fmt_vars(keyword, ctx)).split())
    if len(text.split()) > e["cover"]["max_words"]:
        text = display_keyword(keyword, ctx).upper()
    return {"frame_s": frame, "text": text, "safe_box": e["cover"]["safe_box"],
            "why": e["cover"]["why"]["payoff" if payoff else "frame0"]
                   + "; " + e["cover"]["safe_note"]}


def _join(lines):
    return "\n".join(ln for ln in lines if ln)


def _platforms(script, ctx, kw, secondary, parts, cover, cw):
    e = _eng()
    fmt = str(script.get("format") or "demo")
    c = ctx.get("concept") or "product"
    ai = str(script.get("presenter") or "").lower() == "ai"
    opening, cta, ai_line, tags = parts
    if ai and not ai_line:
        ai_line = "made with an AI persona"
    v = _fmt_vars(kw, ctx)
    pw = e["presenter_words"]["ai" if ai else "human"]
    tt_tags = tags[:e["d155"]["hashtags_max"]["tiktok"]]
    ig_tags = tags[:e["d155"]["hashtags_max"]["instagram"]]
    yt_tags = tags[:e["d155"]["hashtags_recommended"]["youtube_shorts"]]
    ms = int(round(cover["frame_s"] * 1000))
    # TikTok: line 1, a search-intent sentence, the single CTA, disclosure
    line2 = _concept_template(e["tiktok_line2"], c, fmt).format(**v)
    tt_caption = _join(opening + [line2, cta, ai_line if ai else None,
                                  " ".join(tt_tags)])
    tt_notes = [
        f"Cover: video_cover_timestamp_ms={ms} (the API picks a frame, no "
        f"image upload; covers reportedly cannot be changed after posting).",
        "After publish: Manage Keywords, suggest the keywords below and block "
        "off-topic auto keywords; pin a comment that repeats the keyword and "
        "the caption's CTA line.",
        "Hashtags label the video, they do not buy reach: keep 3 on-topic "
        "tags, never #fyp or #viral.",
        "Day 7: check the search share of views in Creator Search Insights.",
    ]
    if ai:
        tt_notes.insert(0, "is_aigc=true adds the 'Creator labeled as "
                           "AI-generated' tag (required with an AI persona).")
    # Instagram: the alt-text substitute replaces line 2
    desc_line = _concept_template(e["description_line"], c, fmt).format(**v, **pw)
    ig_caption = _join(opening + [desc_line, cta, ai_line if ai else None,
                                  " ".join(ig_tags)])
    variants = [x.get("id") for x in (script.get("hook_variants") or [])
                if isinstance(x, dict) and x.get("id")]
    if len(variants) >= 2:
        vid = ", ".join(variants[:-1]) + " and " + variants[-1]
        protocol = (f"Post hook variants {vid} as MANUAL Trial Reels on the "
                    f"same day (they differ only in 0-3 s and the cover); at "
                    f"24-72 h compare reels_skip_rate, average watch time and "
                    f"shares per reach, graduate the winner and log the trial "
                    f"status at publish.")
    else:
        variants = []
        protocol = ("Cut 2-3 openings from the master (0-3 s and cover only), "
                    "post them as MANUAL Trial Reels the same day, compare "
                    "reels_skip_rate, average watch time and shares per reach "
                    "at 24-72 h and graduate the winner.")
    ig_notes = [
        "Reels have no alt-text field: the description line stands in for "
        "it; turn on auto-captions and proofread them.",
        f"Cover: cover_url JPEG 9:16 (or thumb_offset {ms}) with the text "
        f"inside {cover['safe_box']}.",
        "Check the media_publish response: config_issue CAPTION_NOT_ATTACHED "
        "means the caption and its keywords were dropped.",
        "Keywords belong in the caption, not only in comments; the niche "
        "keyword also goes in the profile name.",
        "Trial Reels eligibility depends on follower count (threshold "
        "unverified); comment-word replies go out as Private Replies within "
        "7 days, one per comment.",
    ]
    # YouTube Shorts: keyword-first title, description, 2 hashtags
    hook = _verbal_hook(script) or (opening[0] if opening else "")
    hook_q = re.sub(r"[.!]+$", "", hook).strip()
    first = hook_q.split(" ", 1)[0]
    if first and not (first.isupper() or first.startswith("I'")):
        hook_q = hook_q[:1].lower() + hook_q[1:]
    title_t = _concept_template(e["yt_title"], c, fmt)
    title = " ".join(title_t.format(hook=hook_q, **v).split())
    title = title.replace("<", "").replace(">", "")
    if len(title) > e["d155"]["yt_title_max_chars"]:
        title = v["Kw"][:e["d155"]["yt_title_max_chars"]]
    desc1 = _concept_template(e["yt_desc_line1"], c, fmt).format(**v)
    if secondary:
        desc1 += f" Related: {secondary[0]}."
    yt_cta = None
    if cw:
        low = (cta or "").lower()
        what = ("the checklist" if "checklist" in low else "the full list"
                if "list" in low else None)
        yt_cta = (f"Comment {cw} for {what}." if what else
                  "Comment DAY1 to start your own count." if cw == "DAY1"
                  else f"Comment {cw} below.")
    plan = script.get("series_plan") if isinstance(script.get("series_plan"), dict) else None
    related = f"Part 2: {plan.get('next')}" if plan and plan.get("next") else None
    rel_line = (f"Part 2 ({plan.get('next')}) is the related video under this "
                f"Short." if related else None)
    yt_desc = _join([desc1, ai_line if ai else None, yt_cta, rel_line,
                     " ".join(yt_tags)])
    yt_notes = [
        "Upload captions.srt as the caption track (plain UTF-8 SRT).",
        "Custom Shorts thumbnail only for YPP channels in desktop Studio; "
        f"otherwise pick the cover frame at {cover['frame_s']:g} s.",
        "Description URLs are clickable only on verified or advanced-feature "
        "channels, so the CTA is the comment word or the related video, not "
        "a URL.",
        "No #Shorts tag needed; tags only for misspellings (<= 500 chars).",
    ]
    if related:
        yt_notes.append(f"Related video: link Part 2 ({plan.get('next')}) "
                        f"from the Shorts player once it is live.")
    return {
        "tiktok": {"caption": tt_caption, "hashtags": tt_tags,
                   "keywords_to_suggest": [kw] + list(secondary[:2]),
                   "toggles": {"is_aigc": ai}, "notes": tt_notes},
        "instagram": {"caption": ig_caption, "hashtags": ig_tags,
                      "description_line": desc_line,
                      "toggles": {"is_ai_generated": ai},
                      "trial_reels": {"recommended": True, "protocol": protocol,
                                      "variant_ids": variants},
                      "notes": ig_notes},
        "youtube_shorts": {"title": title, "description": yt_desc,
                           "hashtags": yt_tags, "related_video": related,
                           "toggles": {"containsSyntheticMedia": ai},
                           "notes": yt_notes},
    }


_PLATFORM_LABEL = {"all": "All", "tiktok": "TikTok", "instagram": "Instagram",
                   "youtube_shorts": "YouTube Shorts"}


def _posting():
    out = []
    for g in data()["POSTING_GUIDANCE"]:
        myth = str(g.get("label", "")).startswith("myth")
        out.append({"id": g["id"], "platform": g["platform"],
                    "item": g["guidance"],
                    "grade": "myth" if myth else g["grade"],
                    "evidence": g["grade"], "label": g["label"],
                    "source": g["source"]})
    return out


def _checklist():
    ck = data()["DISCOVERY_CHECKLIST"]
    return [f"{_PLATFORM_LABEL[p]}: {item}" for p in ("all", "tiktok", "instagram",
                                                        "youtube_shorts")
            for item in ck.get(p, [])]


def build(script, ctx=None, seed=None, maker=None):
    """script["discovery"] (CREATIVE-PLAN §1.3). None when the script has no
    caption to package. `seed` is accepted for the enrich() contract; the
    packaging is a pure function of (script, ctx, research pack)."""
    if not isinstance(script, dict) or not str(script.get("caption") or "").strip():
        return None
    ctx = _ctx_for(script, ctx, maker)
    primary, secondary, intents, sources = _keywords(
        script, ctx=ctx, pack=_pack_for(maker), maker=maker)
    fmt = str(script.get("format") or "demo")
    timed = _timed(script)
    parts = _caption_parts(script.get("caption"))
    opening, cta, _, tags = parts
    cw = _comment_word(script, cta)
    cover = _cover(script, ctx, primary, fmt, timed)
    tag = compact_tag(primary)
    within = _eng()["d155"]["caption_first_line_within"]
    placement = {
        "spoken_by_s": _first_end(timed, ("dialogue", "rehook"), primary),
        "on_screen_by_s": _first_end(timed, ("on_screen",), primary),
        "caption_first_60": has_keyword(opening[0] if opening else "", primary, within),
        "hashtag": tag if tag and tag.lower() in [t.lower() for t in tags] else None,
        "cover_text": bool(phrase_rx(head_noun(primary)).search(cover["text"])),
    }
    return {
        "schema_version": 1,
        "primary_keyword": primary,
        "secondary_keywords": secondary,
        "search_intents": intents,
        "keyword_sources": sources,
        "placement": placement,
        "comment_word": cw,
        "cover": cover,
        "platforms": _platforms(script, ctx, primary, secondary, parts, cover, cw),
        "posting": _posting(),
        "checklist": _checklist(),
    }


# ------------------------------------------------------ D155 checker
def platform_texts(disc):
    """[(platform, field, text, is_caption)] every posted text."""
    out = []
    p = (disc or {}).get("platforms") or {}
    for name, fields in (("tiktok", ("caption",)),
                         ("instagram", ("caption", "description_line")),
                         ("youtube_shorts", ("title", "description"))):
        for f in fields:
            t = (p.get(name) or {}).get(f)
            if isinstance(t, str):
                out.append((name, f, t, f in ("caption", "description")))
    return out


def check(disc, script):
    """Own D155 checker (CREATIVE-PLAN §1.3 hard rules) -> error messages.
    Silent (no messages) for a valid packaging."""
    from vsp import creative_vocab as V
    from vsp import lexicon as L
    if disc is None:
        return []
    if not isinstance(disc, dict):
        return ["D155: discovery is not an object"]
    e = _eng()["d155"]
    errs = []
    kw = disc.get("primary_keyword")
    if not isinstance(kw, str) or not kw.strip():
        errs.append("D155: no primary_keyword")
        kw = ""
    plats = disc.get("platforms") if isinstance(disc.get("platforms"), dict) else {}
    for name in V.PLATFORMS:
        if not isinstance(plats.get(name), dict):
            errs.append(f"D155: platforms.{name} missing")
    ai = str(script.get("presenter") or "").lower() == "ai"
    cap_groups = V.link_groups_in(script.get("caption") or "")
    for name in V.PLATFORMS:
        p = plats.get(name) or {}
        tags = p.get("hashtags") if isinstance(p.get("hashtags"), list) else []
        mx = e["hashtags_max"][name]
        if not 1 <= len(tags) <= mx:
            errs.append(f"D155: {name} carries {len(tags)} hashtags (1-{mx})")
        elif all(str(t).lstrip("#").lower() in L.GENERIC_TAGS for t in tags):
            errs.append(f"D155: {name} hashtags are generic-only")
    for name, field, text, is_cap in platform_texts(disc):
        where = f"{name}.{field}"
        for msg in screen(text, script):
            errs.append(f"D155: {where}: {msg}")
        extra = V.link_groups_in(text) - cap_groups
        if extra:
            errs.append(f"D155: {where} adds a CTA destination the caption "
                        f"does not have (D46 groups {sorted(extra)})")
        if ai and is_cap and not L.has_ai_disclosure_line(text):
            errs.append(f"D155: {where} lacks the AI disclosure line")
        if kw and field in ("caption", "description", "title"):
            first = text.split("\n")[0]
            if not has_keyword(first, kw):
                errs.append(f"D155: {where} line 1 lacks the primary keyword "
                            f"{kw!r}")
    yt = plats.get("youtube_shorts") or {}
    title = yt.get("title") if isinstance(yt.get("title"), str) else ""
    if not title or len(title) > e["yt_title_max_chars"]:
        errs.append(f"D155: youtube_shorts.title is {len(title)} chars (1-100)")
    if any(ch in title for ch in e["yt_title_forbidden"]):
        errs.append("D155: youtube_shorts.title contains < or >")
    desc = yt.get("description") if isinstance(yt.get("description"), str) else ""
    if len(desc.encode("utf-8")) > e["yt_desc_max_bytes"]:
        errs.append(f"D155: youtube_shorts.description is "
                    f"{len(desc.encode('utf-8'))} bytes (> 5000)")
    cov = disc.get("cover") if isinstance(disc.get("cover"), dict) else {}
    ct = str(cov.get("text") or "")
    if not ct or len(ct.split()) > _eng()["cover"]["max_words"]:
        errs.append(f"D155: cover text {ct!r} is not 1-5 words")
    elif kw and not phrase_rx(head_noun(kw)).search(ct):
        errs.append(f"D155: cover text {ct!r} lacks the head noun")
    for msg in screen(ct, script):
        errs.append(f"D155: cover.text: {msg}")
    return errs


def warnings(disc, script):
    """Soft discovery checks (DISC-05 stuffing, comment word = head noun,
    placement by 3.0 s) -> messages; never errors."""
    out = []
    if not isinstance(disc, dict):
        return out
    kw = disc.get("primary_keyword") or ""
    rx = phrase_rx(kw)
    for name, field, text, is_cap in platform_texts(disc):
        n = len(rx.findall(text))
        if n > _eng()["d155"]["caption_primary_exact_max"]:
            out.append(f"DISC-05: {name}.{field} repeats {kw!r} {n}x (max 2)")
    head = head_noun(kw).upper()
    cw = disc.get("comment_word")
    if cw and head and cw != head and lemma(cw.lower()) != lemma(head.lower()):
        out.append(f"comment word {cw} is not the keyword head noun {head}")
    pl = disc.get("placement") or {}
    if pl.get("spoken_by_s") is None or pl["spoken_by_s"] > 3.0:
        out.append(f"D161: {kw!r} not spoken by 3.0 s")
    if pl.get("on_screen_by_s") is None or pl["on_screen_by_s"] > 3.0:
        out.append(f"D161: {kw!r} not on screen by 3.0 s")
    return out
