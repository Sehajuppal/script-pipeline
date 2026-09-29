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
