"""evolve — GEPA / MAP-Elites-lite search over hook TEMPLATES -> a PROPOSED
hook pack (learned/hook_packs/<date>-<nn>.json). Nothing here edits the maker:
a pack only reaches production through `promote` (full-scorecard A/B).

Seeds      the maker's current HOOKS (+ approved packs) and hooks mined from
           the research pack (fresh_hook_lines, top_reels if present) and the
           research DB if present (reels.hook_text by likes), templatized:
           product/category nouns -> {product} / {category} / {category_pl}.
Mutations  deterministic and seeded: opener swap and tail (lexicon) swap
           inside interchangeable phrase groups mined from the top hooks
           (PHRASE_GROUPS + openers of the mined lines), slot swap
           ({product} <-> the {category}), clause reorder, trimming. Optional
           LLM reflective mutations (vsp.llm.complete_json) read the failing
           renders + gate/rubric messages + top-reel hooks and return
           {"templates": [{"family", "template", "rationale"}]}. The LLM only
           proposes; its templates are scored exactly like the others.
Fitness    each candidate is rendered over a sample of golden PRODUCT prompts
           x 5 formats x 2 presenters with the maker's own code, read-only
           (parse_prompt, _hook_nouns, _render_hook_line, humanize_dialogue,
           overlay_truncate, _hook_candidates), and checked: D73 <= 8 words,
           D31 no braces, D37 prices, D136 / D137 (ai) / D139 / D141 via
           vsp.lexicon, D144 overlay_is_clean, R01/R07 hygiene, R02
           specificity, R15 product named.
             fitness = quality x (0.6 + 0.4 novelty) x gain
           gain = expected extra DISTINCT hooks per context (3 seeds) when the
           template joins the maker's top-scored tie pool, relative to the best
           case (a one-template pool gaining a second); a template that would
           out-score every existing line collapses that pool (negative gain).
Archive    MAP-Elites keyed by (family, opening device, length bucket); a
           candidate whose trigram Jaccard with any existing template or elite
           exceeds 0.5 is rejected (novelty).
Pack       greedy marginal-gain selection over the elites (pool sizes are
           updated as templates are picked), then an offline preview:
           in-process generate() + gate 1 + rubric on the SAME golden sample
           with and without the pack. Written only if the preview shows more
           distinct hooks with no gate-1 or rubric loss.
Guard      evals/holdout.jsonl is never read here: the run executes under
           holdout_guard(), which raises HoldoutRead on any attempt to open it.
"""
import builtins
import collections
import contextlib
import io
import json
import math
import os
import random
import re
import sys
import time

from vsp.improve import common as C
from vsp.improve import packs as P

VERSION = "1"
SKIP_FAMILIES = ("proof-first",)      # {proof} needs prompt-supplied proof (D136)
NOVELTY_MAX = 0.5                     # reject above this trigram Jaccard
DRAWS = 3                             # seeds per context in the full scorecard
BUDGETS = {
    "small": {"prompts": 10, "generations": 2, "per_gen": 160, "screen_ctx": 30,
              "pack_max": 8, "per_family": 3, "llm_calls": 1, "llm_n": 12},
    "full": {"prompts": 0, "generations": 3, "per_gen": 400, "screen_ctx": 50,
             "pack_max": 14, "per_family": 5, "llm_calls": 2, "llm_n": 16},
}
HARD = ("D73", "D31", "D37", "D136", "D137", "D139", "D141", "D144", "R01", "R07")
SOFT = ("R02", "R15", "P2", "CARD")
# a frame-0 card that ends on a verb reads as a fragment ("RESISTANCE BANDS WEAR")
CARD_VERB_END = frozenset("""wear wears break breaks quit quits fail fails last lasts
work works hold holds held lasted broke use uses using used tested tried went made
needed do does did make makes keep keeps kept got get gets""".split())
SLOT_RE = P.SLOT_RE
TOKEN_RE = re.compile(r"\{\w+\}|[A-Za-z0-9][A-Za-z0-9'\u2019-]*")
# an object noun phrase: what opener / tail swaps pivot on
NP_RE = re.compile(r"(?:(?<![A-Za-z])(?:[Tt]he|[Tt]his) \{category\}|\{product\}|"
                   r"\{category_pl\}|\{category\})")
# promises no payoff card pays and authority/virality claims: an engine-side
# screen for NEW templates only (the D35 industry-secret class, D136 class)
PROMISE_BLOCK = re.compile(
    r"\b(?:secrets?|hacks?|tricks?|industry|brands? (?:hide|don'?t)|don'?t want you "
    r"to know|banned|illegal|doctors?|dermatologists?|experts?|scientists?|viral|"
    r"trending|millions?|thousands?|everyone(?:'s| is) buying|sold)\b", re.I)
_FUNC_END = frozenset("""the a an of to for with about on in at by from and or but
my your our their its is are was were be""".split())

# Interchangeable phrase groups. Every member takes the same continuation, so a
# swap inside a group keeps the line grammatical and keeps the family's payoff
# contract (verdict tails keep "worth it" / "or skip" — the maker's review
# detector; day-count tails keep {ndays}, D35/D40). Members: the openers/tails
# of the maker's HOOKS (distilled from the research DB's top hooks), plus hook
# tactics from docs/research/short-form-virality.md §1 (negative words lift
# CTR, Robertson 2023; "I" helps, Gligorić 2023; showcase / comparison hooks,
# Motion + OpusClip). Openers of mined research/DB hooks join at runtime.
PHRASE_GROUPS = {
    "opener": {
        "about": ["Nobody is talking about", "Nobody talks about", "No one talks about",
                  "Nobody warns you about", "What nobody tells you about",
                  "Here's what nobody shows about", "Here's what nobody says about",
                  "The truth about"],
        "catch": ["The catch with", "The real test of", "The problem with"],
        "detail": ["One detail on", "One thing on", "The one detail on",
                   "One small detail on"],
        "test": ["I tested", "I tried", "I used", "I lived with"],
        "buy": ["Stop buying", "Don't buy", "Quit buying", "Never buy"],
        "use": ["You're using", "Everyone's using", "Most people use"],
        "after": ["Here's the after with", "This is the after with", "The after, with"],
        "days": ["{ndays} days with", "Day {ndays} with", "{ndays} days using"],
        "most": ["Most", "Nearly all", "So many"],
        "wrong_about": ["I was wrong about", "I was so wrong about", "I underestimated"],
        "returned": ["So I almost returned", "I almost returned", "I nearly returned",
                     "I almost sent back"],
    },
    "tail": {
        "end": ["."],
        "nobody": [" nobody mentions.", " nobody shows you.", " everyone misses.",
                   " everyone skips.", " nobody points out."],
        "until": [" until you see this.", " before you see this.", " on looks alone."],
        "verdict": [": buy or skip?", ": worth it?", ": worth it or not?", ". Worth it?",
                    ": the honest verdict."],
        "days": [" for {ndays} days.", " for {ndays} days straight.",
                 " every day for {ndays} days."],
        "zero": [". Zero failures.", ". No failures.", ". Still going.",
                 ". Not one failure.", ". Still holding up."],
        "after": [". This is the after.", ". Here's the after."],
        "wrong": [" wrong.", " all wrong.", " the wrong way."],
        "afterdays": [" after {ndays} days: buy or skip?", " after {ndays} days: worth it?",
                      " after {ndays} days. Worth it?", ", {ndays} days in: worth it?"],
        "dayvs": [", day 1 vs day {ndays}.", ": day 1 vs day {ndays}."],
        "most_fail": [" fail. This one didn't.", " break. This one didn't.",
                      " quit early. This one didn't.", " fail. Not this one.",
                      " wear out. This one didn't."],
        "most_worth": [" aren't worth it. This one?", " aren't worth it. Is this one?",
                       " aren't worth it. This one might be."],
    },
}
FILLERS = ("just", "really", "actually", "honestly", "literally", "ever", "even")
# an NP followed by one of these is the head of its clause, so {product} fits
HEAD_TAIL = re.compile(r"^(?:[.,:;?!\u2014]|\s(?:nobody|no one|everyone|for|after|is|"
                       r"isn't|was|does|did|just|wrong|all|the wrong|until|before|on|"
                       r"made|with|every|vs)\b)")
# second sentences that carry no claim or contract (trim may drop them)
CODA = re.compile(r"(?i)^(?:the result surprised me|no regrets|here's (?:what it took|"
                  r"my honest take)|do this instead)\.$")
ANAPHORA = re.compile(r"(?i)\b(?:this|that|it|here's|there|instead|one|so|which)\b")
OPERATORS = (("opener_swap", 3), ("tail_swap", 3), ("slot_swap", 2),
             ("reorder", 1), ("trim", 1))
NUMBER_WORDS = frozenset("""two three four five six seven eight nine ten
twenty thirty ninety hundred""".split())
SLOT_WORDS = {"product": 3, "category": 1, "category_pl": 1, "ndays": 1, "flaw": 5,
              "mistake": 5, "common": 3, "price": 1, "expensive": 3, "identity": 1,
              "proof": 2}


class HoldoutRead(C.ImproveError):
    """Raised when anything inside evolve tries to open the holdout suite."""


# ------------------------------------------------------------ holdout guard
def _is_holdout(path):
    try:
        p = os.fspath(path)
    except TypeError:
        return False
    if isinstance(p, bytes):
        p = p.decode("utf-8", "ignore")
    return isinstance(p, str) and os.path.basename(p) == C.HOLDOUT_NAME


@contextlib.contextmanager
def holdout_guard(record=None, strict=True):
    """Wrap builtins.open / io.open / os.open for the duration: opening any
    holdout suite is recorded and (strict) raises HoldoutRead. Fitness can
    therefore never see holdout prompts, even through a helper."""
    real = (builtins.open, io.open, os.open)

    def _chk(f):
        if _is_holdout(f):
            if record is not None:
                record.append(os.fspath(f))
            if strict:
                raise HoldoutRead(f"evolve must never read the holdout suite ({f})")

    def g_open(file, *a, **k):
        _chk(file)
        return real[0](file, *a, **k)

    def g_io_open(file, *a, **k):
        _chk(file)
        return real[1](file, *a, **k)

    def g_os_open(path, *a, **k):
        _chk(path)
        return real[2](path, *a, **k)

    builtins.open, io.open, os.open = g_open, g_io_open, g_os_open
    try:
        yield record
    finally:
        builtins.open, io.open, os.open = real


def golden_rows(repo=None):
    """The golden suite (fitness data). Refuses anything named holdout."""
    path = C.suite_path("golden", repo)
    if _is_holdout(path):
        raise HoldoutRead("golden path resolves to the holdout suite")
    return C.load_jsonl(path)


# ------------------------------------------------------------------ maker
def load_maker():
    if C.REPO not in sys.path:
        sys.path.insert(0, C.REPO)
    import viral_script_maker as vsm
    missing = [n for n in ("HOOKS", "parse_prompt", "_render_hook_line",
                           "overlay_truncate") if not hasattr(vsm, n)]
    if missing:
        raise C.ImproveError("maker lacks " + ", ".join(missing) + " — evolve needs them")
    return vsm


def effective_hooks(vsm):
    """(hooks, known slots, approved pack ids): the pool production draws
    from — built-in HOOKS plus approved packs (deduped; idempotent when the
    maker's native loader already added them)."""
    hooks = {f: list(v) for f, v in vsm.HOOKS.items()}
    known = frozenset(getattr(vsm, "HOOK_SLOTS", None) or P.hook_slots(hooks))
    loaded, _added, _warns = P.load_into(hooks, known=known)
    return hooks, known, loaded


def _lex():
    from vsp import lexicon
    return lexicon


def _rub():
    from vsp import rubric
    return rubric


def make_ctx(vsm, prompt, fmt, presenter, ndays=7):
    """ctx exactly as build_beats hands it to pick_hook (D31 brace strip,
    fmt/presenter, transformation day-count)."""
    ctx = vsm.parse_prompt(re.sub(r"\s+", " ", re.sub(r"[{}]", "", prompt)).strip())
    ctx["_prompt"] = prompt
    ctx["fmt"] = fmt
    ctx["presenter"] = presenter
    if fmt == "transformation":
        ctx["ndays"] = ndays
    return ctx


def pref_family(vsm, ctx, hooks):
    fam = getattr(vsm, "NICHE_HOOK", {}).get(ctx.get("niche"), "curiosity-gap")
    pack = getattr(vsm, "_PACK", None)
    if isinstance(pack, dict):
        live = (pack.get("niche_hooks") or {}).get(ctx.get("niche"))
        if isinstance(live, list) and live and isinstance(live[0], dict) \
                and live[0].get("category") in hooks:
            fam = live[0]["category"]
    return fam


def render_hook(vsm, ctx, template):
    """(line, overlay) at the most specific product phrase that fits 8 words
    (the maker's renderer), or (None, why)."""
    levels = vsm._hook_nouns(ctx) if hasattr(vsm, "_hook_nouns") and \
        ctx.get("concept", "product") == "product" else [(None, None)]
    cap = getattr(vsm, "_cap1", lambda s: s[:1].upper() + s[1:])
    hum = getattr(vsm, "humanize_dialogue", lambda s: s)
    last = None
    for pv, noun in levels:
        try:
            r = vsm._render_hook_line(ctx, None, template, None, pv, noun)
        except (KeyError, IndexError, ValueError, AttributeError, TypeError) as e:
            return None, f"render error {type(e).__name__}: {e}"
        last = cap(" ".join(hum(r).split()))
        if len(last.split()) <= 8:
            break
    if last is None:
        return None, "no render"
    return last, vsm.overlay_truncate(last.split(".")[0])


def anchors(prompt):
    return _rub().prompt_anchors(prompt)


def check_line(line, overlay, prompt, ai, anc, vsm=None):
    """The spec's fitness checks on one rendered hook. -> {id: (ok, detail)}"""
    L, R = _lex(), _rub()
    out = {}
    n = len(line.split())
    out["D73"] = (n <= 8, f"{n} words")
    out["D31"] = ("{" not in line and "}" not in line and "None" not in line,
                  "raw slot" if "{" in line or "}" in line else "clean")
    supplied = {re.sub(r"[^\d.]", "", p).rstrip(".").rstrip("0").rstrip(".")
                for p in L.PRICE.findall(prompt)}
    bad = [p for p in L.PRICE.findall(line)
           if re.sub(r"[^\d.]", "", p).rstrip(".").rstrip("0").rstrip(".") not in supplied]
    out["D37"] = (not bad, f"invented price {bad[0]!r}" if bad else "clean")
    sp = [rx.search(line).group(0) for rx in L.SOCIAL_PROOF
          if rx.search(line) and not rx.search(prompt)]
    out["D136"] = (not sp, f"social proof {sp[0]!r}" if sp else "clean")
    if ai:
        m = L.first_match(L.AI_FIRST_PERSON, line)
        fp = getattr(vsm, "_HOOK_FIRST_PERSON", None) if vsm is not None else None
        m2 = fp.search(line) if fp is not None else None
        out["D137"] = (m is None and m2 is None,
                       f"AI lived experience {(m or m2).group(0)!r}" if (m or m2) else "curator")
    else:
        out["D137"] = (True, "n/a (human)")
    m = L.GENERIC_BAIT.search(line)
    out["D139"] = (m is None, f"engagement bait {m.group(0)!r}" if m else "clean")
    m = L.ABSOLUTE.search(line)
    out["D141"] = (m is None, f"absolute claim {m.group(0)!r}" if m else "clean")
    ok, why = L.overlay_is_clean(overlay, line)
    out["D144"] = (ok, f"overlay {overlay!r}: {why}")
    nw = len(R._words(line))
    out["R01"] = (0 < nw <= 8, f"{nw} rubric words")
    probs = []
    m = re.search(r"\b([A-Za-z]+) \1\b", line, re.I)
    if m and m.group(1).lower() not in ("that", "had", "very", "no"):
        probs.append(f"doubled word {m.group(0)!r}")
    if re.search(r"[.!?] +[a-z]", line):
        probs.append("lowercase after sentence end")
    if re.search(r"\b(?:null|undefined)\b", line):
        probs.append("null leak")
    out["R07"] = (not probs, "; ".join(probs) or "clean")
    h = line.strip()
    if L.FALLBACK_HOOK.match(h) or L.VAGUE_HOOK.search(h):
        out["R02"] = (False, "fallback/vague hook")
    else:
        toks = {R._stem(w) for w in R._words(h)}
        anchored = bool(toks & anc) or bool(re.search(r"\d", h)) or \
            bool(re.search(r"\b(?:I|my|I'm|I've)\b", h))
        out["R02"] = (anchored, "anchored" if anchored else "no concrete anchor")
    toks = {R._stem(w) for w in R._words(line + " " + (overlay or ""))}
    out["R15"] = (bool(toks & anc), "product named" if toks & anc else "product absent")
    m = L.SLOP.search(line)
    out["P2"] = (m is None, f"slop {m.group(0)!r}" if m else "clean")
    last = (overlay or "").split()[-1:] or [""]
    out["CARD"] = (last[0].lower().strip(".,!?") not in CARD_VERB_END,
                   f"card {overlay!r}" + (" ends on a verb" if last[0].lower() in CARD_VERB_END
                                          else ""))
    return out


def _fallback_candidates(vsm, ctx, pool, ai, lex, pref):
    """For makers without _hook_candidates: every template rendered and kept
    when the explicit hard checks pass; score = (R02, R15, preferred family)."""
    out = []
    anc = anchors(ctx.get("_prompt") or ctx.get("prompt_text") or "")
    for fam, t, _ in pool:
        line, ov = render_hook(vsm, ctx, t)
        if line is None:
            continue
        chk = check_line(line, ov, str(ctx.get("prompt_text") or ""), ai, anc, vsm)
        if all(chk[k][0] for k in HARD):
            out.append({"family": fam, "line": line, "overlay": ov,
                        "score": (chk["R02"][0], chk["R15"][0], fam == pref)})
    return out


def maker_candidates(vsm, ctx, pool, ai, lex, pref):
    fn = getattr(vsm, "_hook_candidates", None)
    if fn is None:
        return _fallback_candidates(vsm, ctx, pool, ai, lex, pref)
    return fn(ctx, pool, ai, lex, pref)


def expected_distinct(k, draws=DRAWS):
    return k * (1.0 - (1.0 - 1.0 / k) ** draws) if k > 0 else 0.0


GAIN_UNIT = expected_distinct(2) - expected_distinct(1)   # 0.75 for 3 draws


def build_contexts(vsm, hooks, rows):
    lex = _lex()
    extra = getattr(vsm, "NICHE_HOOK_EXTRA", {}) or {}
    base_pool = [(f, t, None) for f, lines in hooks.items() for t in lines]
    out = []
    for r in rows:
        anc = anchors(r["prompt"])
        for fmt in C.FORMATS:
            for pres in C.PRESENTERS:
                ctx = make_ctx(vsm, r["prompt"], fmt, pres)
                pref = pref_family(vsm, ctx, hooks)
                pool = base_pool + [(pref, t, None) for t in extra.get(ctx.get("niche"), [])]
                cands = maker_candidates(vsm, ctx, pool, pres == "ai", lex, pref)
                top = max((c["score"] for c in cands), default=None)
                best = sorted({c["line"] for c in cands if c["score"] == top})
                out.append({"key": f"{r['id']}|{fmt}|{pres}", "id": r["id"],
                            "prompt": r["prompt"], "fmt": fmt, "presenter": pres,
                            "ai": pres == "ai", "ctx": ctx, "pref": pref,
                            "niche": ctx.get("niche"), "top": top, "k": len(best),
                            "lines": set(best), "all_lines": {c["line"] for c in cands},
                            "anchors": anc, "prompt_text": str(ctx.get("prompt_text") or "")})
    return out


# ------------------------------------------------------- template features
def tokens(t):
    return [w.lower() for w in TOKEN_RE.findall(t)]


def trigrams(t):
    w = tokens(t)
    if len(w) < 3:
        return {tuple(w)} if w else set()
    return {tuple(w[i:i + 3]) for i in range(len(w) - 2)}


def jaccard(a, b):
    u = a | b
    return len(a & b) / len(u) if u else 0.0


def np_normal(t):
    """Slot-normalised form: every object NP -> <np> (pack de-duplication)."""
    return " ".join(tokens(NP_RE.sub(" np ", t)))


def device(t):
    """Opening device (MAP-Elites axis)."""
    s = t.strip()
    toks = TOKEN_RE.findall(s)
    f = toks[0].lower() if toks else ""
    low = s.lower()
    if s.endswith("?") or f in ("what", "why", "how", "is", "are", "does", "do",
                                "would", "can", "which"):
        return "question"
    if f in ("{ndays}", "{price}", "day") or f.isdigit() or f in NUMBER_WORDS:
        return "number"
    if f == "pov" or low.startswith(("when you", "if you")):
        return "pov"
    if f in ("nobody", "no", "never", "don't", "stop", "quit", "skip", "not", "zero"):
        return "negation"
    if f in ("i", "i'm", "i've", "i'd", "my") or low.startswith("so i "):
        return "first-person"
    if re.match(r"^[A-Za-z ]{2,24}:", s):
        return "label"
    if f.startswith("{") or (f in ("the", "this") and len(toks) > 1 and toks[1].startswith("{")):
        return "object-first"
    if f in ("most", "every", "only", "all", "everyone", "nearly", "many", "so"):
        return "claim"
    if f in ("here's", "here", "one", "there's", "the", "this", "you're", "everyone's"):
        return "reveal"
    return "other"


def est_words(t):
    lit = len([w for w in TOKEN_RE.findall(SLOT_RE.sub(" ", t))])
    return lit + sum(SLOT_WORDS.get(s, 2) for s in SLOT_RE.findall(t))


def length_bucket(t):
    n = est_words(t)
    return "short" if n <= 4 else "mid" if n <= 6 else "long"


def cell_of(family, t):
    return (family, device(t), length_bucket(t))


def form_problems(t):
    """Template-level fluency screen for NEW templates (the maker's screens
    and the gates cannot see awkward English)."""
    s = t.strip()
    if not s:
        return ["empty"]
    probs = []
    if not re.search(r"[.?!\u2014]$", s):
        probs.append("no end punctuation")
    if re.search(r"\s[.,:;?!]", s) or "  " in s or re.search(r"[,:;?!]{2,}|\.{2}", s):
        probs.append("spacing/punctuation")
    sents = [x.strip() for x in re.split(r"(?<=[.?!])\s+", s) if x.strip()]
    if len(sents) > 2:
        probs.append(f"{len(sents)} sentences")
    for x in sents:
        toks = TOKEN_RE.findall(x)
        if not toks:
            probs.append("empty sentence")
            continue
        if toks[-1].lower() in _FUNC_END:
            probs.append(f"sentence ends on {toks[-1]!r}")
        first = x.lstrip("\"'(")[:1]
        if first.isalpha() and first.islower():
            probs.append("lowercase sentence start")
    words = [w.lower() for w in re.findall(r"[A-Za-z']+", SLOT_RE.sub(" ", s))]
    if len(words) < 2:
        probs.append("fewer than 2 hook words besides slots")
    for a, b in zip(words, words[1:]):
        if a == b:
            probs.append(f"doubled word {a!r}")
            break
    cnt = collections.Counter(w for w in words if len(w) >= 4 and w not in _FUNC_END)
    dup = sorted(w for w, n in cnt.items() if n > 1)
    if dup:
        probs.append(f"repeated word {dup[0]!r}")
    if PROMISE_BLOCK.search(s):
        probs.append(f"unpayable promise / authority claim {PROMISE_BLOCK.search(s).group(0)!r}")
    return probs


# ---------------------------------------------------------------- mining
_DETS = ("the", "this", "my", "a", "an", "your", "that", "these")
_PREPS = ("about", "on", "with", "for", "of", "vs", "than", "without", "from", "into")
_NOUN_STOP = frozenset("""tech tool kitchen organize clean lunch mealprep alarm
desk light lighting home room house car office trunk skin hair face body day
days week night morning thing things stuff video reel post""".split())


def product_niches(vsm):
    """Maker niches + the research niches that map onto them (a comedy or
    dance reel's hook is not product copy)."""
    out = set(getattr(vsm, "NICHE_KEYWORDS", {}) or {}) | {"default"}
    try:
        from vsp import research
        out |= set(research.pack_to_maker_niches())
    except Exception:  # noqa: BLE001
        pass
    return out


# common product head nouns (beyond the maker's niche keywords), so trending
# products in reels' hooks/captions are recognised by mining and golden-refresh
PRODUCT_HEADS = frozenset("""mask scrubber board mat bottle brush bag case charger
stand holder mount lamp fan heater humidifier diffuser purifier vacuum mop blender
kettle toaster fryer grill pan pot knife sharpener scale timer clock watch band ring
necklace bracelet wallet backpack tote pillow pillowcase blanket towel robe slippers
socks sneakers boots jacket hoodie leggings glasses sunglasses headphones earbuds
speaker keyboard mouse monitor webcam microphone tripod gimbal drone camera projector
tablet stylus cable adapter hub organizer rack shelf hanger bin basket container jar
dispenser tumbler mug cup straw filter shaker roller massager serum cream cleanser
toner moisturizer sunscreen patch lipstick mascara eyeliner sponge curler
straightener dryer clip comb wax shampoo conditioner perfume candle collar leash
harness feeder fountain crate scraper inflator starter protector planner notebook
journal lock pad bands stone kit set tracker purse sprayer steamer iron""".split())


def product_nouns(vsm, rows):
    nouns = set(PRODUCT_HEADS)
    for kws in (getattr(vsm, "NICHE_KEYWORDS", {}) or {}).values():
        for kw in kws:
            w = kw.replace("\\b", "")
            w = re.sub(r"s\?$", "", w)
            if re.fullmatch(r"[a-z]{3,}", w):
                nouns.add(w)
    for name in ("CATEGORY_MECHANISM_FAIL", "CATEGORY_CARD", "CATEGORY_PURPOSE_PROOF"):
        for k in getattr(vsm, name, {}) or {}:
            if re.fullmatch(r"[a-z]{3,}", str(k)):
                nouns.add(k)
    for r in rows:
        try:
            ctx = vsm.parse_prompt(r["prompt"])
            for _pv, noun in vsm._hook_nouns(ctx):
                nouns.add(str(noun).split()[-1].lower())
        except Exception:  # noqa: BLE001 — mining is best-effort
            continue
    return {n for n in nouns if n not in _NOUN_STOP and not n.endswith("ing")}


def _noun_hit(word, nouns):
    w = word.lower().strip(".,!?:;'\u2019")
    if w in nouns:
        return "sg"
    for suf in ("es", "s"):
        if w.endswith(suf) and w[: -len(suf)] in nouns:
            return "pl"
    return None


def templatize(line, nouns, adj_like=None):
    """A mined hook line -> template: the first product NP becomes {product}
    (after a determiner) / {category} / {category_pl}. None when no product
    noun is found."""
    words = line.split()
    for i, w in enumerate(words):
        num = _noun_hit(w, nouns)
        if not num:
            continue
        j = i
        while j > 0 and (words[j - 1].isupper() or (adj_like and adj_like(words[j - 1]))
                         or _noun_hit(words[j - 1], nouns)):
            j -= 1
        if j > 0 and words[j - 1].lower() not in _DETS + _PREPS and \
                not re.fullmatch(r"\$?\d[\d.,]*", words[j - 1]):
            continue          # not in an object position ("went camping")
        trail = re.search(r"[.,!?:;'\u2019]+$", w)
        trail = trail.group(0) if trail else ""
        det = j > 0 and words[j - 1].lower() in _DETS
        if det and num == "sg":
            head = words[: j - 1]
            slot = "{product}"
        else:
            head = words[:j]
            slot = "{category_pl}" if num == "pl" else "{category}"
        if not head:
            slot = slot[0].upper() + slot[1:] if not slot.startswith("{") else slot
        out = " ".join(head + [slot + trail] + words[i + 1:])
        out = out[0].upper() + out[1:] if out and out[0].isalpha() else out
        if not re.search(r"[.?!\u2014]$", out):
            out += "."
        return out
    return None


FAMILY_CUES = (
    ("negative-command", r"^(?:stop|don'?t|never|quit|skip)\b"),
    ("identity-reveal", r"\bi was wrong\b|^i'?m an?\b|^full disclosure"),
    ("story-time", r"^(?:story ?time|so i\b|pov\b)"),
    ("transformation", r"\b(?:before|after|day \d+|days? (?:later|in))\b"),
    ("contrarian-reframe", r"\b(?:everyone|myth|overrated|unpopular)\b"),
    ("bold-claim", r"^(?:most|every|only|the only)\b|\bobsolete\b|\bbetter than\b"),
    ("curiosity-gap", r"\b(?:nobody|no one|what|why|how|here'?s|hidden)\b|\?$"),
)


def classify_family(text, hooks, category=None):
    try:
        from vsp import research
        fam = research.map_family(category, tuple(hooks)) if category else None
    except Exception:  # noqa: BLE001
        fam = None
    if fam in hooks:
        return fam
    low = text.lower()
    for fam, rx in FAMILY_CUES:
        if fam in hooks and re.search(rx, low):
            return fam
    return None               # no cue: never guess a family (D145 honesty)


def mined_lines(limit=200):
    """Spoken hook lines from the research pack and the research DB (if any).
    -> ([{text, source, niche, likes, category}], notes)"""
    out, notes = [], []
    try:
        from vsp import research
        pack, meta = research.load_pack()
    except Exception as e:  # noqa: BLE001
        pack, meta, research = None, {"errors": [repr(e)]}, None
    if pack:
        fresh = [r for r in pack.get("fresh_hook_lines") or [] if isinstance(r, dict)]
        spoken = [r for r in fresh if research.is_spoken_hook_line(r.get("hook"))]
        for r in spoken:
            out.append({"text": " ".join(r["hook"].split()), "source": "pack:fresh_hook_lines",
                        "niche": r.get("niche"), "likes": r.get("likes"),
                        "category": r.get("category") or r.get("hook_category")})
        tops = [r for r in pack.get("top_reels") or [] if isinstance(r, dict)]
        for r in tops:
            h = r.get("hook") or r.get("hook_text")
            if research.is_spoken_hook_line(h):
                out.append({"text": " ".join(h.split()), "source": "pack:top_reels",
                            "niche": r.get("niche"), "likes": r.get("likes") or r.get("like_count"),
                            "category": r.get("category") or r.get("hook_category")})
        notes.append(f"research pack: {len(fresh)} fresh lines ({len(spoken)} spoken), "
                     f"{len(tops)} top reels")
    else:
        notes.append("research pack: unavailable (" + "; ".join((meta or {}).get("errors") or [])[:120] + ")")
    try:
        from vsp import config
        con = config.connect_ro()
    except Exception:  # noqa: BLE001
        con = None
    if con is None:
        notes.append("research DB: absent")
    else:
        try:
            rows = con.execute(
                "SELECT hook_text, niche, like_count FROM reels WHERE hook_text IS NOT NULL "
                "AND hook_text != '' ORDER BY like_count DESC LIMIT ?", (limit,)).fetchall()
            n0 = len(out)
            for h, niche, likes in rows:
                if research is None or research.is_spoken_hook_line(h):
                    out.append({"text": " ".join(str(h).split()), "source": "db:reels",
                                "niche": niche, "likes": likes, "category": None})
            notes.append(f"research DB: {len(rows)} reels, {len(out) - n0} spoken hooks")
        except Exception as e:  # noqa: BLE001
            notes.append(f"research DB: query failed ({type(e).__name__})")
        finally:
            con.close()
    seen, uniq = set(), []
    for r in out:
        k = r["text"].lower()
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    return uniq, notes


# ------------------------------------------------------------- mutations
def split_np(t):
    """(opener, np, tail) around the first object NP, or None."""
    m = NP_RE.search(t)
    if not m:
        return None
    return t[:m.start()].rstrip(), m.group(0), t[m.end():]


def _group_of(kind, text):
    for g, members in PHRASE_GROUPS[kind].items():
        if text in members:
            return g
    return None


def _join(opener, np_, tail):
    if not opener:
        np_ = np_[:1].upper() + np_[1:] if np_[:1].isalpha() else np_
        return f"{np_}{tail}"
    return f"{opener} {np_}{tail}"


def op_opener_swap(t, rng):
    parts = split_np(t)
    if not parts:
        return []
    o, np_, tail = parts
    g = _group_of("opener", o)
    if g is None:
        return []
    return [_join(o2, np_, tail) for o2 in PHRASE_GROUPS["opener"][g] if o2 != o]


def op_tail_swap(t, rng):
    parts = split_np(t)
    if not parts:
        return []
    o, np_, tail = parts
    g = _group_of("tail", tail)
    if g is None:
        return []
    return [_join(o, np_, t2) for t2 in PHRASE_GROUPS["tail"][g] if t2 != tail]


def op_slot_swap(t, rng):
    parts = split_np(t)
    if not parts:
        return []
    o, np_, tail = parts
    low = np_.lower()
    # never "this {category}": the hook noun may be plural ("this resistance bands")
    alts = {"{product}": ["the {category}"], "the {category}": ["{product}"],
            "this {category}": ["{product}", "the {category}"]}.get(low, [])
    if not HEAD_TAIL.match(tail):
        alts = [a for a in alts if a != "{product}"]    # "{category} test": a modifier
    return [_join(o, a, tail) for a in alts]


def op_reorder(t, rng):
    sents = [x.strip() for x in re.split(r"(?<=[.?!])\s+", t.strip()) if x.strip()]
    if len(sents) != 2:
        return []
    a, b = sents
    if ANAPHORA.search(b):
        return []           # the second sentence leans on the first
    if not SLOT_RE.search(b + a):
        return []
    return [f"{b} {a}"]


def op_trim(t, rng):
    out = []
    sents = [x.strip() for x in re.split(r"(?<=[.?!])\s+", t.strip()) if x.strip()]
    if len(sents) == 2 and SLOT_RE.search(sents[0]) and CODA.match(sents[1]):
        out.append(sents[0])      # only a coda goes: claim-carrying sentences stay
    for f in FILLERS:
        s = re.sub(rf"\s+{f}\b", "", t, flags=re.I)
        if s != t:
            out.append(s)
    # (never trims an "until you see this" turn: "Stop buying lamps." would
    # tell the viewer not to buy the product the video sells)
    return out


OP_FUNCS = {"opener_swap": op_opener_swap, "tail_swap": op_tail_swap,
            "slot_swap": op_slot_swap, "reorder": op_reorder, "trim": op_trim}


def mutate_all(t):
    """Every single-step neighbour of t: [(child, operator)]."""
    out = []
    for name, _w in OPERATORS:
        for c in OP_FUNCS[name](t, None):
            c = P.normalize(c)
            if c and c != t:
                out.append((c, name))
    return out


def mine_openers(templates):
    """Openers of mined templates that end like an 'about' opener join that
    group (the phrase bank grows with the research)."""
    added = []
    for t in templates:
        parts = split_np(t)
        if not parts:
            continue
        o = parts[0]
        if 2 <= len(o.split()) <= 6 and re.search(r"\b(?:about|on|with)$", o) \
                and parts[2] in (".", "?") and o not in PHRASE_GROUPS["opener"]["about"] \
                and not form_problems(t):
            PHRASE_GROUPS["opener"]["about"].append(o)
            added.append(o)
    return added


# -------------------------------------------------------------- fitness
class Evaluator:
    def __init__(self, vsm, contexts, existing, known, hooks):
        self.vsm, self.contexts, self.known, self.hooks = vsm, contexts, known, hooks
        self.existing = {P.normalize(t) for t in existing}
        self.existing_tri = [trigrams(t) for t in self.existing]
        self.lex = _lex()
        self.cache = {}
        self.n_eval = 0

    def screen(self, family, t):
        """Template-level checks (cheap). -> list of problems."""
        probs = []
        if family not in self.hooks or family in SKIP_FAMILIES:
            probs.append(f"family {family!r} not evolvable")
        why = P.template_problem(t, self.known)
        if why:
            probs.append(f"contract: {why}")
        if P.normalize(t) in self.existing:
            probs.append("duplicate of an existing template")
        probs += form_problems(t)
        return probs

    def novelty(self, t, others=()):
        tri = trigrams(t)
        sims = [jaccard(tri, e) for e in self.existing_tri]
        sims += [jaccard(tri, trigrams(o)) for o in others if o != t]
        return 1.0 - max(sims or [0.0])

    def evaluate(self, family, t, contexts=None, diag=3):
        key = (family, t, len(contexts) if contexts is not None else -1)
        if key in self.cache:
            return self.cache[key]
        ctxs = self.contexts if contexts is None else contexts
        self.n_eval += 1
        n = len(ctxs)
        elig = joins = doms = 0
        gain = qsum = 0.0
        risk = 0
        soft_fail = collections.Counter()
        why_not = collections.Counter()
        join_keys, dom_keys, samples, failing = [], [], [], []
        for c in ctxs:
            cands = maker_candidates(self.vsm, c["ctx"], [(family, t, None)], c["ai"],
                                     self.lex, c["pref"])
            if not cands:
                if len(failing) < diag:
                    line, ov = render_hook(self.vsm, c["ctx"], t)
                    if line is None:
                        failing.append({"ctx": c["key"], "line": None, "why": [ov]})
                    else:
                        chk = check_line(line, ov, c["prompt_text"], c["ai"], c["anchors"],
                                         self.vsm)
                        msgs = [f"{k}: {chk[k][1]}" for k in HARD + SOFT if not chk[k][0]]
                        failing.append({"ctx": c["key"], "line": line,
                                        "why": msgs or ["maker contract filter (format/slot)"]})
                why_not["filtered"] += 1
                continue
            cd = cands[0]
            elig += 1
            chk = check_line(cd["line"], cd["overlay"], c["prompt_text"], c["ai"],
                             c["anchors"], self.vsm)
            hard_ok = all(chk[k][0] for k in HARD)
            if not hard_ok:
                risk += 1
                if len(failing) < diag:
                    failing.append({"ctx": c["key"], "line": cd["line"],
                                    "why": [f"{k}: {chk[k][1]}" for k in HARD if not chk[k][0]]})
                continue
            q = 1.0 - 0.25 * sum(1 for k in SOFT if not chk[k][0])
            for k in SOFT:
                if not chk[k][0]:
                    soft_fail[k] += 1
            qsum += q
            if c["top"] is None or cd["score"] > c["top"]:
                doms += 1
                dom_keys.append(c["key"])
                gain += 1.0 - expected_distinct(c["k"]) if c["k"] else GAIN_UNIT
            elif cd["score"] == c["top"]:
                if cd["line"] in c["lines"]:
                    why_not["same line as pool"] += 1
                else:
                    joins += 1
                    join_keys.append(c["key"])
                    gain += expected_distinct(c["k"] + 1) - expected_distinct(c["k"])
            else:
                why_not["below top score"] += 1
            if len(samples) < 4 and (c["key"] in join_keys[-1:] or c["key"] in dom_keys[-1:]):
                samples.append({"ctx": c["key"], "line": cd["line"], "overlay": cd["overlay"],
                                "pool": c["k"]})
        quality = (qsum / (elig - risk)) if elig - risk > 0 else 0.0
        gain_n = gain / (n * GAIN_UNIT) if n else 0.0
        res = {"family": family, "template": t, "contexts": n, "eligible": elig,
               "joins": joins, "dominates": doms, "gate_risk": risk,
               "quality": round(quality, 4), "gain": round(gain_n, 5),
               "reach": round((joins + doms) / n, 4) if n else 0.0,
               "soft_fail": dict(soft_fail), "why_not": dict(why_not),
               "join_keys": join_keys, "dom_keys": dom_keys, "samples": samples,
               "failing": failing}
        self.cache[key] = res
        return res


def fitness(ev, novelty):
    if ev["gate_risk"] or ev["gain"] <= 0:
        return round(min(0.0, ev["gain"]), 5)
    return round(ev["quality"] * (0.6 + 0.4 * novelty) * ev["gain"], 5)


# ------------------------------------------------------------- LLM step
LLM_SCHEMA = {
    "type": "object",
    "properties": {"templates": {"type": "array", "maxItems": 40, "items": {
        "type": "object",
        "properties": {"family": {"type": "string"}, "template": {"type": "string"},
                       "rationale": {"type": "string"}},
        "required": ["family", "template"]}}},
    "required": ["templates"],
}
LLM_SYSTEM = ("You write hook TEMPLATES for a short-form product video script "
              "generator. You are advisory: every template you propose is "
              "machine-checked and A/B tested before it can ship.")


def llm_prompt(hooks, known, thin, failing, reels, n):
    fam_lines = []
    for fam in sorted(hooks):
        if fam in SKIP_FAMILIES:
            continue
        ex = [t for t in hooks[fam] if "{" in t][:2]
        fam_lines.append(f"- {fam}: e.g. " + " | ".join(json.dumps(e) for e in ex))
    L = ["Families (a template joins one existing family):"] + fam_lines + [
        "",
        "Slots: " + ", ".join("{%s}" % s for s in sorted(known)) + ". Use mainly {product} "
        "(renders 'the <product name>', e.g. 'the car trash can'), {category} (head noun, "
        "'trash can'), {category_pl} ('trash cans'), {ndays} (a day count, '7').",
        "Hard contract (anything else is discarded):",
        "- one line, <= 120 characters, only the slots above, one or two sentences",
        "- rendered with a 3-word product name it must be <= 8 words",
        "- no social proof (stars, reviews, orders, sold out, best seller), no prices, no "
        "absolute claims (guaranteed, #1, best ever, cure, miracle, risk-free, clinically "
        "proven), no engagement bait (like if, tag a friend, comment yes, double tap), no "
        "slop (game changer, you won't believe, wait for it, must-have, trust me), no "
        "secrets/hacks/experts/virality claims",
        "- the presenter may be an AI persona: no first person ('I', 'my', 'me') except in "
        "story-time and identity-reveal",
        "- the first 1-3 content words become the on-screen card: name the product early",
        "- review hooks must ask for a verdict with 'worth it', 'verdict' or 'or skip'; "
        "transformation-format hooks need {ndays}; only transformation may say 'day 1 vs day'",
        "",
        "Where the generator is thin (few fitting templates, so every seed ships the same "
        "hook) — fill these first:"]
    L += [f"- {x}" for x in thin[:12]] or ["- (none measured)"]
    L += ["", "Recent candidates that FAILED, with the checker's messages (learn from them):"]
    L += [f"- {json.dumps(f['template'])} -> {json.dumps(f.get('line'))}: "
          + "; ".join(f["why"])[:200] for f in failing[:12]] or ["- (none)"]
    L += ["", "Hooks from top-performing reels (inspiration only, do not copy niche words):"]
    L += [f"- {json.dumps(r)}" for r in reels[:12]] or ["- (none available)"]
    L += ["", f"Write {n} NEW templates (not paraphrases of the examples). Return JSON "
          '{"templates": [{"family": "...", "template": "...", "rationale": "..."}]}.']
    return "\n".join(L)


def llm_mutations(hooks, known, thin, failing, reels, n, provider=None):
    from vsp import llm
    prov = provider or llm.get_provider()
    if prov is None:
        return [], {"used": False, "reason": "no LLM configured"}
    prompt = llm_prompt(hooks, known, thin, failing, reels, n)
    obj = llm.complete_json(prompt, LLM_SCHEMA, system=LLM_SYSTEM, provider=prov,
                            name="hook_templates")
    info = {"used": True, "provider": prov.name, "model": prov.model,
            "prompt_chars": len(prompt)}
    if not isinstance(obj, dict):
        info["reason"] = "no valid JSON reply"
        return [], info
    out = []
    for it in obj.get("templates") or []:
        if isinstance(it, dict) and isinstance(it.get("template"), str) \
                and isinstance(it.get("family"), str):
            out.append((it["family"].strip(), P.normalize(it["template"]),
                        str(it.get("rationale") or "")[:200]))
    info["returned"] = len(out)
    return out, info


# ------------------------------------------------------------------ run
def _sample_rows(vsm, rows, budget, seed):
    prods = [r for r in rows if r.get("concept", "product") == "product"]
    k = budget if isinstance(budget, int) else BUDGETS[budget]["prompts"]
    if not k or k >= len(prods):
        return prods
    by = collections.defaultdict(list)
    for r in prods:
        try:
            by[vsm.parse_prompt(r["prompt"]).get("niche")].append(r)
        except Exception:  # noqa: BLE001
            by[None].append(r)
    rng = random.Random(seed)
    groups = [sorted(v, key=lambda r: r["id"]) for _k, v in sorted(by.items(), key=lambda kv: str(kv[0]))]
    for g in groups:
        rng.shuffle(g)
    out = []
    while len(out) < k and any(groups):
        for g in groups:
            if g and len(out) < k:
                out.append(g.pop(0))
    return sorted(out, key=lambda r: r["id"])


def stride_sample(contexts, n):
    """~n contexts spread over every (format, presenter) cell: the stride is
    coprime with the 10 cells per prompt, so no format is skipped."""
    cells = len(C.FORMATS) * len(C.PRESENTERS)
    step = max(1, len(contexts) // max(1, n))
    while math.gcd(step, cells) != 1:
        step += 1
    return contexts[::step]


def thin_spots(contexts):
    agg = collections.defaultdict(lambda: [0, 0, None])
    for c in contexts:
        if c["k"] <= 1:
            a = agg[(c["pref"], c["fmt"], c["presenter"])]
            a[0] += 1
            a[1] += c["k"]
            a[2] = a[2] or next(iter(c["lines"]), None)
    rows = sorted(agg.items(), key=lambda kv: -kv[1][0])
    return [f"{fam} family x {fmt} format ({pres} presenter): {n} contexts with <= 1 "
            f"fitting template, e.g. {ex!r}" for (fam, fmt, pres), (n, _k, ex) in rows]


def select_pack(elites, contexts, pack_max, per_family):
    """Greedy marginal-gain selection: after each pick the joined pools grow,
    so a second template for the same thin spot earns less."""
    k = {c["key"]: c["k"] for c in contexts}
    n = len(contexts) or 1
    chosen, fam_n, norms = [], collections.Counter(), []
    pool = [e for e in elites if not e["dominates"] and not e["gate_risk"]
            and e["quality"] >= 0.9 and e["gain"] > 0]
    while len(chosen) < pack_max:
        best, best_s = None, 0.0
        for e in pool:
            if e in chosen or fam_n[e["family"]] >= per_family:
                continue
            nn = np_normal(e["template"])
            if any(jaccard(trigrams(nn), trigrams(x)) > NOVELTY_MAX for x in norms):
                continue
            m = sum(expected_distinct(k[x] + 1) - expected_distinct(k[x]) for x in e["join_keys"])
            s = m / (n * GAIN_UNIT) * e["quality"] * (0.6 + 0.4 * e["novelty"])
            if s > best_s + 1e-12:
                best, best_s = e, s
        if best is None:
            break
        best["marginal"] = round(best_s, 5)
        chosen.append(best)
        fam_n[best["family"]] += 1
        norms.append(np_normal(best["template"]))
        for x in best["join_keys"]:
            k[x] += 1
    return chosen


def _distinct2(lines):
    R = _rub()
    grams, total = set(), 0
    for ln in lines:
        w = R._norm(ln).split()
        for i in range(len(w) - 1):
            grams.add((w[i], w[i + 1]))
            total += 1
    return len(grams) / total if total else 0.0


def preview(vsm, rows, hooks, additions, seeds=(1, 2, 3)):
    """Offline mini A/B on the evolve sample (golden product prompts only):
    in-process generate() + gate 1 + rubric with the production pool, then
    with the additions. vsm.HOOKS is restored afterwards."""
    from vsp import gates
    R = _rub()
    saved = {f: list(v) for f, v in vsm.HOOKS.items()}
    add_set = {t for _f, t in additions}

    def run_all():
        hk, g1, rub = [], 0, []
        for r in rows:
            for fmt in C.FORMATS:
                for pres in C.PRESENTERS:
                    for sd in seeds:
                        s = vsm.generate(r["prompt"], presenter=pres, fmt=fmt,
                                         duration=30, seed=sd)
                        h = R.hook_line(s)
                        hk.append(h)
                        g1 += bool(gates.gate1(s))
                        rub.append(R.score(s)["score"])
        return hk, g1, rub

    try:
        for f in vsm.HOOKS:
            vsm.HOOKS[f][:] = list(hooks.get(f, saved[f]))
        hb, gb, rb = run_all()
        for f, t in additions:
            if t not in vsm.HOOKS[f]:
                vsm.HOOKS[f].append(t)
        hc, gc, rc = run_all()
    finally:
        for f in list(vsm.HOOKS):
            vsm.HOOKS[f][:] = saved.get(f, [])
    n = len(hb)
    changed = sum(1 for a, b in zip(hb, hc) if a != b)
    new_lines = collections.Counter(b for a, b in zip(hb, hc) if a != b and b not in set(hb))
    return {"runs": n, "seeds": list(seeds), "changed": changed,
            "distinct_base": round(len(set(hb)) / max(1, n), 4),
            "distinct_cand": round(len(set(hc)) / max(1, n), 4),
            "distinct2_base": round(_distinct2(hb), 4), "distinct2_cand": round(_distinct2(hc), 4),
            "gate1_fail_base": gb, "gate1_fail_cand": gc,
            "rubric_base": round(sum(rb) / max(1, n), 2), "rubric_cand": round(sum(rc) / max(1, n), 2),
            "rubric_min_cand": min(rc) if rc else None,
            "new_lines_top": new_lines.most_common(5), "templates": len(add_set)}


def evolve(budget="full", use_llm="auto", seed=0, write=True, log=None, provider=None,
           rows=None, pack_dir=None, limits=None):
    """-> result dict (see render()). write=False: nothing is written.
    rows: golden rows to use (default: evals/golden.jsonl); limits: overrides
    of BUDGETS[budget] (selfcheck runs a tiny search)."""
    if budget not in BUDGETS:
        raise C.ImproveError(f"budget must be one of {tuple(BUDGETS)}")
    say = log or (lambda m: None)
    t0 = time.time()
    record = []
    with holdout_guard(record):
        res = _evolve(budget, use_llm, seed, write, say, provider, rows, pack_dir, limits)
    res["holdout_opened"] = list(record)
    res["secs"] = round(time.time() - t0, 2)
    return res


def _evolve(budget, use_llm, seed, write, say, provider, rows, pack_dir, limits=None):
    B = dict(BUDGETS[budget], **(limits or {}))
    rng = random.Random(seed)
    vsm = load_maker()
    hooks, known, approved = effective_hooks(vsm)
    rows = rows if rows is not None else golden_rows()
    sample = _sample_rows(vsm, rows, B["prompts"], seed)
    say(f"evolve: {len(sample)} golden product prompts x {len(C.FORMATS)} formats x "
        f"{len(C.PRESENTERS)} presenters; {sum(len(v) for v in hooks.values())} templates "
        f"in the production pool ({len(approved)} approved pack(s))")
    contexts = build_contexts(vsm, hooks, sample)
    existing = [t for v in hooks.values() for t in v]
    ev = Evaluator(vsm, contexts, existing, known, hooks)
    screen_ctx = stride_sample(contexts, B["screen_ctx"])
    base_stats = {"contexts": len(contexts),
                  "singleton_pools": sum(1 for c in contexts if c["k"] == 1),
                  "empty_pools": sum(1 for c in contexts if c["k"] == 0),
                  "mean_pool": round(sum(c["k"] for c in contexts) / max(1, len(contexts)), 3),
                  "expected_distinct_per_ctx": round(sum(expected_distinct(c["k"]) for c in contexts)
                                                     / max(1, len(contexts)), 4)}
    # ---- seeds
    seeds = [(f, t, "hooks") for f in sorted(hooks) if f not in SKIP_FAMILIES
             for t in hooks[f]]
    mined, notes = mined_lines()
    nouns = product_nouns(vsm, sample)
    adj = getattr(vsm, "_adj_like", None)
    niches = product_niches(vsm)
    mined_t = []
    for m in mined:
        if m.get("niche") and m["niche"] not in niches:
            continue
        t = templatize(m["text"], nouns, adj)
        if t is None:
            continue
        fam = classify_family(m["text"], hooks, m.get("category"))
        if fam and fam not in SKIP_FAMILIES:
            t = P.normalize(t)
            mined_t.append({"family": fam, "template": t, "source": m["source"],
                            "text": m["text"]})
            seeds.append((fam, t, m["source"]))
    grown = mine_openers([m["template"] for m in mined_t])
    notes.append(f"mined: {len(mined)} spoken hook lines, {len(mined_t)} templatized, "
                 f"{len(grown)} opener(s) added to the phrase bank")
    say("evolve: " + " · ".join(notes))
    # ---- archive
    archive, rejected, evaluated = {}, collections.Counter(), []
    failing_all = []
    lineage = {}

    def consider(fam, t, op, parent, rationale=None):
        t = P.normalize(t)
        if (fam, t) in lineage:
            return None
        lineage[(fam, t)] = {"operator": op, "parent": parent, "rationale": rationale}
        probs = ev.screen(fam, t)
        if probs:
            rejected[probs[0].split(":")[0].split(" '")[0][:40]] += 1
            if op == "llm":
                failing_all.append({"template": t, "line": None, "why": probs[:2]})
            return None
        nov = ev.novelty(t, [e["template"] for e in archive.values()])
        if 1.0 - nov > NOVELTY_MAX:
            rejected["novelty (trigram Jaccard > 0.5)"] += 1
            return None
        pre = ev.evaluate(fam, t, screen_ctx, diag=1)       # cheap-first cascade
        if pre["eligible"] == 0 or pre["gate_risk"]:
            rejected["never renders on the screen sample" if not pre["gate_risk"]
                     else "gate risk"] += 1
            for f in pre["failing"][:1]:
                failing_all.append({"template": t, **f})
            return None
        r = dict(ev.evaluate(fam, t))
        r["novelty"] = round(nov, 4)
        r["fitness"] = fitness(r, nov)
        r["cell"] = list(cell_of(fam, t))
        r.update(lineage[(fam, t)])
        evaluated.append(r)
        if r["gate_risk"]:
            rejected["gate risk"] += 1
            failing_all.extend({"template": t, **f} for f in r["failing"][:1])
            return r
        if r["fitness"] <= 0:
            rejected["no diversity gain"] += 1
            if r["failing"]:
                failing_all.append({"template": t, **r["failing"][0]})
            return r
        cell = tuple(r["cell"])
        inc = archive.get(cell)
        if inc is None or r["fitness"] > inc["fitness"]:
            archive[cell] = r
        else:
            rejected["lost its cell"] += 1
        return r

    for fam, t, src in seeds:
        if src != "hooks":
            consider(fam, t, "mined", src)
    parents = [(f, t) for f, t, _s in seeds]
    llm_info = {"used": False, "calls": 0, "returned": 0, "accepted": 0}
    want_llm = use_llm == "on" or (use_llm == "auto" and _llm_available(provider))
    if use_llm == "on" and not _llm_available(provider):
        llm_info["reason"] = "--llm on but no LLM is configured (VSP_LLM_MODEL + key)"
    for gen in range(B["generations"]):
        kids = []
        for fam, t in parents:
            for child, op in mutate_all(t):
                kids.append((fam, child, op, t))
        uniq = {}
        for k in kids:
            uniq.setdefault((k[0], P.normalize(k[1])), k)
        kids = sorted(uniq.values(), key=lambda k: (k[0], k[1]))
        rng.shuffle(kids)
        kids = kids[:B["per_gen"]]
        n0 = len(evaluated)
        for fam, child, op, parent in kids:
            consider(fam, child, op, parent)
        if want_llm and llm_info["calls"] < B["llm_calls"]:
            reels = [m["text"] for m in mined
                     if not m.get("niche") or m["niche"] in niches][:12]
            props, info = llm_mutations(hooks, known, thin_spots(contexts),
                                        failing_all[-12:], reels, B["llm_n"], provider)
            llm_info["calls"] += 1
            llm_info.update({k: v for k, v in info.items() if k in ("used", "provider", "model",
                                                                    "reason")})
            llm_info["returned"] += len(props)
            for fam, t, why in props:
                r = consider(fam, t, "llm", "llm", rationale=why)
                if r is not None and r.get("fitness", 0) > 0:
                    llm_info["accepted"] += 1
        say(f"evolve: generation {gen + 1}: {len(kids)} children, {len(evaluated) - n0} "
            f"fully evaluated, archive {len(archive)} cells")
        parents = [(e["family"], e["template"]) for e in
                   sorted(archive.values(), key=lambda e: -e["fitness"])]
        if not parents:
            break
    elites = sorted(archive.values(), key=lambda e: (-e["fitness"], e["template"]))
    chosen = select_pack(elites, contexts, B["pack_max"], B["per_family"])
    additions = [(e["family"], e["template"]) for e in chosen]
    pv = preview(vsm, sample, hooks, additions) if additions else None
    verdict, why = "no-pack", "no elite adds diversity"
    if additions:
        if pv["gate1_fail_cand"] > pv["gate1_fail_base"]:
            why = "offline preview: gate-1 failures rose"
        elif pv["rubric_cand"] < pv["rubric_base"] - 0.5:
            why = "offline preview: rubric fell"
        elif pv["distinct_cand"] <= pv["distinct_base"]:
            why = "offline preview: no distinct-hook gain"
        else:
            verdict, why = "proposed", "offline preview: more distinct hooks, no gate/rubric loss"
    cells_possible = len({(f,) for f in hooks if f not in SKIP_FAMILIES}) * 10 * 3
    res = {"version": VERSION, "budget": budget, "seed": seed, "created": C.now_iso(),
           "git_sha": C.git_sha(), "prompts": [r["id"] for r in sample],
           "baseline": base_stats, "approved_packs": approved,
           "seeds": {"hooks": sum(1 for s in seeds if s[2] == "hooks"),
                     "mined": len(mined_t), "notes": notes,
                     "mined_examples": mined_t[:5]},
           "evaluated": ev.n_eval, "fully_evaluated": len(evaluated),
           "rejected": dict(rejected.most_common()),
           "archive": {"cells": len(archive), "coverage": round(len(archive) / cells_possible, 4),
                       "elites": [_brief(e) for e in elites[:40]]},
           "llm": llm_info, "pack": [_brief(e, samples=True) for e in chosen],
           "preview": pv, "verdict": verdict, "why": why, "path": None, "id": None}
    if write and verdict == "proposed":
        path, pid = P.next_pack_path(pack_dir)
        fams = collections.OrderedDict()
        for f, t in additions:
            fams.setdefault(f, []).append(t)
        pack = {"schema_version": P.PACK_SCHEMA, "id": pid, "status": "proposed",
                "families": dict(fams),
                "provenance": {
                    "created": res["created"], "source": "evolve+llm" if llm_info["accepted"]
                    else "evolve", "engine": f"vsp.improve evolve v{VERSION}",
                    "git_sha": res["git_sha"], "budget": budget, "seed": seed,
                    "evidence": {"fitness": {e["template"]: _brief(e, samples=True)
                                             for e in chosen},
                                 "baseline": base_stats, "preview": pv,
                                 "golden_prompts": res["prompts"],
                                 "holdout_read": False, "llm": llm_info,
                                 "archive_cells": len(archive)}}}
        probs = P.validate_pack(pack, hooks, known)
        if probs:
            raise C.ImproveError("evolve built an invalid pack: " + "; ".join(probs[:3]))
        C.write_json(path, pack)
        res["path"], res["id"] = path, pid
    return res


def _llm_available(provider):
    if provider is not None:
        return True
    try:
        from vsp import llm
        return llm.available()
    except Exception:  # noqa: BLE001
        return False


def _brief(e, samples=False):
    out = {k: e.get(k) for k in ("family", "template", "fitness", "quality", "gain",
                                 "novelty", "reach", "joins", "dominates", "eligible",
                                 "contexts", "gate_risk", "cell", "operator", "parent")}
    if e.get("marginal") is not None:
        out["marginal"] = e["marginal"]
    if e.get("rationale"):
        out["rationale"] = e["rationale"]
    if samples:
        out["samples"] = e.get("samples", [])[:3]
        out["soft_fail"] = e.get("soft_fail", {})
    return out


def render_result(res):
    b = res["baseline"]
    L = [f"evolve v{res['version']} · budget {res['budget']} · seed {res['seed']} · "
         f"{len(res['prompts'])} golden product prompts ({b['contexts']} contexts) · "
         f"{res.get('secs')}s",
         f"  baseline: mean tie-pool {b['mean_pool']} templates, {b['singleton_pools']} "
         f"single-template contexts, E[distinct/ctx, 3 seeds] {b['expected_distinct_per_ctx']}",
         f"  seeds: {res['seeds']['hooks']} HOOKS + {res['seeds']['mined']} mined · "
         + " · ".join(res["seeds"]["notes"]),
         f"  evaluated {res['evaluated']} ({res['fully_evaluated']} full) · archive "
         f"{res['archive']['cells']} cells · rejected {res['rejected']}",
         f"  llm: {res['llm']}",
         f"  holdout opened: {res.get('holdout_opened') or 'never'}"]
    if res["pack"]:
        L.append("  pack (greedy marginal gain):")
        L.append(f"    {'fitness':>8} {'gain':>7} {'qual':>5} {'nov':>5} {'reach':>6}  "
                 f"family / template  (operator)")
        for e in res["pack"]:
            L.append(f"    {e['fitness']:>8.4f} {e['gain']:>7.4f} {e['quality']:>5.2f} "
                     f"{e['novelty']:>5.2f} {e['reach']:>6.3f}  {e['family']}: "
                     f"{e['template']!r}  ({e['operator']})")
            for s in e.get("samples", [])[:1]:
                L.append(f"             e.g. {s['ctx']}: {s['line']!r} · card {s['overlay']!r}"
                         f" (pool {s['pool']} -> {s['pool'] + 1})")
    pv = res.get("preview")
    if pv:
        L.append(f"  offline preview ({pv['runs']} golden product runs, seeds "
                 f"{pv['seeds']}): distinct {pv['distinct_base']} -> {pv['distinct_cand']} · "
                 f"distinct-2 {pv['distinct2_base']} -> {pv['distinct2_cand']} · gate-1 fails "
                 f"{pv['gate1_fail_base']} -> {pv['gate1_fail_cand']} · rubric "
                 f"{pv['rubric_base']} -> {pv['rubric_cand']} · {pv['changed']} hooks changed")
    L.append(f"  verdict: {res['verdict']} — {res['why']}"
             + (f" -> {C.rel(res['path'])} ({res['id']})" if res.get("path") else ""))
    return "\n".join(L)


render = render_result
