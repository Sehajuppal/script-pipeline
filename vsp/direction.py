"""Creative direction (pipeline v2.1, WS-VIBE): vibe, tone, pacing, energy
curve, music, look, camera, text style and voice spec for every script.

  direct(script, ctx=None, seed=None, maker=None) -> dict  script["direction"]
  render_md(direction) -> str        the "## CREATIVE DIRECTION — vibe & tone"
                                     bundle section (direction.md)
  style_paragraph(direction) -> str  replaces the bundle's ## STYLE body
  voice_spec(direction) -> str       replaces the VOICEOVER "Voice spec:" line
  selfcheck() -> (ok, lines)         hermetic golden-matrix check

Contract: docs/CREATIVE-PLAN.md §1.1. Tables: vsp/data/vibes.json
(docs/research/vibe-tone-music.md §5 transcribed; §2/§3.1/§4 prose tables).

Vibe resolution (research §5.2): base = concept rule | format x niche |
format default; then the first prompt cue; then the research pack's niche
pattern (only while the vibe is still raw-ugc); then the fit and duration
swaps (defaults); then the policy lanes, which always win: the TikTok Shop
lane, the presenter lane (an AI persona is never story-vlog or raw-ugc) and
the niche veto. Learned priors (vsp.priors, section "vibe", n >= 3) only
choose between the primary and the secondary vibe, both of which already
passed every lane.

Pacing never asks for speech slower than a beat was sized for: the maker and
gate D43 size each window at vsp.timing.wps(delivery) (3.0 w/s, 2.5 with a
slow key), so every energy_curve entry carries wpm = 60 x that rate as a
floor, and target_wpm is the profile band raised to cover those floors,
clamped to 140-200.

Deterministic: data order only (no set iteration), a local RNG from
vsp.seeding.derive_seed(seed, "direction"); the maker's rng is never touched.
"""
import copy
import hashlib
import json
import os
import random
import re
import sys
import time

from vsp import creative_vocab as CV
from vsp import seeding
from vsp.timing import wps as _gate_wps

SCHEMA_VERSION = 1
HEADING = "## CREATIVE DIRECTION \u2014 vibe & tone"
DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data",
                         "vibes.json")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORMATS = ("demo", "talking-head", "pov-vlog", "transformation", "review")
PRESENTERS = ("ai", "human")
CONCEPTS = ("product", "showcase", "challenge", "routine", "advice")
WPM_MIN, WPM_MAX = 140, 200
MAX_STATIC_S = 3.5              # D48 / vsp.timing.STATIC_CAP
PACK_SHARE_MIN = 0.25           # DEFAULT_VIBE.pack_pattern.apply_if
PACK_MIN_ROWS = 5               # niche rows needed before a niche pattern counts
NEUTRAL = 0.5                   # vsp.priors.NEUTRAL
FRAME0_MAX_WORDS = 3
# CAMERA_MOVES ids that gate 2 (D48) accepts as a named move on a long shot
D48_MOVES = ("push-in", "pan", "tilt", "dolly", "handheld", "tracking")
FORBIDDEN_CLAIMS = ("polish kills trust",)
_PRICE = re.compile(r"(?:[$\u20ac\u00a3]\s?\d[\d,]*(?:\.\d+)?)")
_GENDER = ((re.compile(r"(?i)\b(?:woman|female|girl|lady)\b"), "female"),
           (re.compile(r"(?i)\b(?:man|male|guy)\b"), "male"))

_DATA = None
_PACK_CACHE = {}


# ------------------------------------------------------------------ data
def data():
    """vibes.json, loaded once per process (callers must not mutate it)."""
    global _DATA
    if _DATA is None:
        with open(DATA_PATH, encoding="utf-8") as f:
            _DATA = json.load(f)
    return _DATA


def _profiles():
    return data()["VIBE_PROFILES"]


def _pack(maker=None):
    """The research pack via vsp.research.load_pack(), cached per process and
    path; None when absent/invalid or when the maker runs --no-research."""
    if maker is not None and getattr(maker, "_NO_RESEARCH", False):
        return None
    try:
        from vsp import config
        path = os.path.abspath(config.research_pack_path())
    except Exception:  # noqa: BLE001 — no pack is a normal state
        return None
    if path not in _PACK_CACHE:
        pack = None
        try:
            from vsp import research
            pack, _meta = research.load_pack(path)
        except Exception:  # noqa: BLE001
            pack = None
        _PACK_CACHE[path] = pack if isinstance(pack, dict) else None
    return _PACK_CACHE[path]


def _priors():
    try:
        from vsp import priors
        return priors.load_priors()
    except Exception:  # noqa: BLE001 — the direction never dies on priors
        return None


def _mean(priors, niche, vibe):
    if priors is None:
        return None
    try:
        from vsp import priors as P
        return P.mean_for(priors, "vibe", niche, vibe)
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------- helpers
def _items(script):
    return [it for it in list(script.get("hook_stack") or []) +
            list(script.get("beats") or []) if isinstance(it, dict)]


def _spoken(it):
    return bool((it.get("dialogue") or "").strip() or
                (it.get("rehook") or "").strip())


def _dedupe(seq):
    out = []
    for x in seq:
        if x and x not in out:
            out.append(x)
    return out


def _cap(s):
    return s[:1].upper() + s[1:] if s else s


def _num(v, default):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return f if f > 0 else default


def infer_concept(script, ctx=None):
    """-> (concept, source). ctx["concept"] wins; else beat types (STORY /
    RITUAL / TEACHING BEAT), the hook family (listicle, challenge,
    day-counter), prompt markers, else "product"."""
    if isinstance(ctx, dict) and ctx.get("concept") in CONCEPTS:
        return ctx["concept"], "ctx"
    M = data()["CONCEPT_MARKERS"]
    for it in _items(script):
        c = M["beat_types"].get(it.get("type"))
        if c:
            return c, f"{it.get('type')} in the script"
    fam = script.get("hook_family")
    if fam in M["hook_family"]:
        return M["hook_family"][fam], f"hook family {fam}"
    prompt = script.get("prompt") or ""
    for pat, c in M["prompt"]:
        if re.search(pat, prompt, re.I):
            return c, "prompt wording"
    return M["default"], "default"


def _clean_prompt(prompt):
    p = re.sub(r"[{}]", "", prompt or "")
    p = re.sub(r"\btik[ -]?tok[ -]?shop\b", " ", p, flags=re.I)
    return re.sub(r"\s+", " ", p).strip()


def _subject(script, ctx, concept):
    """-> (subject phrase or None, reference with its determiner)."""
    prod = ctx.get("product") if isinstance(ctx, dict) else None
    prod = _clean_prompt(prod) if isinstance(prod, str) else ""
    p = _clean_prompt(script.get("prompt"))
    if concept == "showcase":
        if not prod:
            m = re.search(r"\bthings in my ([a-z][a-z ]*?)\s+(?:that|which|i)\b",
                          p, re.I)
            prod = f"these {m.group(1).strip().lower()} finds" if m else \
                "these finds"
        return prod, prod
    if concept != "product":
        return None, {"challenge": "the challenge", "routine": "the routine",
                      "advice": "the tip"}.get(concept, "the product")
    if not prod:
        prod = _PRICE.sub(" ", p)
        prod = re.sub(r"^(?:an?|the)\s+", "", prod.strip(), flags=re.I)
        prod = re.sub(r"\s+", " ", prod).strip(" ,.-")
    return (prod, f"the {prod}") if prod else (None, "the product")


def _place(script, ctx, niche):
    P = data()["PLACES"]
    low = " ".join(x for x in (_clean_prompt(script.get("prompt")),
                               (ctx or {}).get("product") or "")
                   if isinstance(x, str)).lower()
    for pat, place in P["by_product"]:
        if re.search(pat, low):
            return place
    return P["by_niche"].get(niche) or P["by_niche"]["default"]


def shop_lane(script):
    """True when the prompt asks for the TikTok Shop lane (policy lane)."""
    pat = data()["LANES"]["tiktok_shop"]["pattern"]
    return bool(re.search(pat, script.get("prompt") or "", re.I))


# ----------------------------------------------------------- pack pattern
def _ranked_top(rows, denom=None):
    best = None
    tot = 0
    for i, r in enumerate(rows if isinstance(rows, list) else []):
        if not isinstance(r, dict) or not isinstance(r.get("pattern"), str):
            continue
        t = r.get("times_seen")
        if isinstance(t, bool) or not isinstance(t, (int, float)) or t <= 0:
            continue
        tot += t
        if best is None or t > best[1]:
            best = (r["pattern"], t)
    if best is None:
        return None
    d = denom if (isinstance(denom, (int, float)) and not isinstance(denom, bool)
                  and denom >= tot and denom > 0) else tot
    return best[0], round(best[1] / float(d), 4)


def niche_pattern(pack, niche):
    """The research pack's top production pattern for a maker niche ->
    (pattern, share, source) | None. Order: an explicit per-niche ranking
    (pack["niche_patterns"]), the niche's own reel rows (top_hooks /
    fresh_hook_lines with a pattern, >= PACK_MIN_ROWS), else the pack-wide
    top_patterns as a share of reels_total."""
    if not isinstance(pack, dict):
        return None
    try:
        from vsp import research
        names = research.pack_niches_for(niche, pack)
    except Exception:  # noqa: BLE001
        names = [niche]
    npat = pack.get("niche_patterns")
    if isinstance(npat, dict):
        for n in names:
            top = _ranked_top(npat.get(n))
            if top:
                return top + (f"pack niche_patterns[{n}]",)
    for n in names:
        counts, order = {}, []
        for key in ("top_hooks", "fresh_hook_lines"):
            for r in pack.get(key) or []:
                if (isinstance(r, dict) and r.get("niche") == n and
                        isinstance(r.get("pattern"), str) and r["pattern"]):
                    if r["pattern"] not in counts:
                        counts[r["pattern"]] = 0
                        order.append(r["pattern"])
                    counts[r["pattern"]] += 1
        total = sum(counts.values())
        if total >= PACK_MIN_ROWS:
            best = order[0]
            for p in order:
                if counts[p] > counts[best]:
                    best = p
            return best, round(counts[best] / float(total), 4), \
                f"{total} pack reels in {n}"
    top = _ranked_top(pack.get("top_patterns"), denom=pack.get("reels_total"))
    return top + ("pack top_patterns",) if top else None


# ----------------------------------------------------------------- vibe
def _duration_rule(duration):
    rules = data()["DEFAULT_VIBE"]["duration"]
    if duration <= rules[0]["max_s"]:
        return 0, rules[0]
    if duration >= rules[-1]["min_s"]:
        return len(rules) - 1, rules[-1]
    return 1, rules[1]


def _lanes(v, fit, duration, presenter, niche, shop, trail=None):
    """Swaps (fit, duration: defaults) then policy lanes (TikTok Shop,
    presenter, niche veto: always win). Appends reasons to `trail`."""
    D = data()["DEFAULT_VIBE"]
    note = trail.append if trail is not None else (lambda _m: None)
    steps = [("fit", (D["fit"].get(fit) or {}).get("swap") or {},
              f"{fit} fit"),
             ("duration", _duration_rule(duration)[1].get("swap") or {},
              f"{duration:g}s duration")]
    if shop:
        steps.append(("shop", data()["LANES"]["tiktok_shop"]["swap"],
                      "TikTok Shop lane (real people on screen)"))
    steps.append(("presenter", (D["presenter"].get(presenter) or {})
                  .get("swap") or {}, f"{presenter.upper()} presenter lane"))
    for _k, swap, why in steps:
        if v in swap and swap[v] != v:
            note(f"{why}: {v} -> {swap[v]}")
            v = swap[v]
    veto = D["niche_veto"].get(niche)
    if veto and v in veto["never"]:
        note(f"{niche} veto: {v} -> {veto['fallback']}")
        v = veto["fallback"]
    return v


def resolve_vibe(concept, fmt, niche, fit, presenter, duration, prompt,
                 pack=None, priors=None, shop=False):
    """-> (vibe, secondary, reason trail list)."""
    D = data()["DEFAULT_VIBE"]
    trail, replaced = [], []
    vibe = None
    for r in D["concept_rules"]:
        if r["concept"] != concept:
            continue
        if "niche" in r and niche not in r["niche"]:
            continue
        if "format" in r and fmt not in r["format"]:
            continue
        vibe = r["vibe"]
        trail.append(f"{concept} concept -> {vibe}")
        break
    fn = D["format_niche"].get(fmt) or {}
    if vibe is None:
        if niche in fn:
            vibe = fn[niche]
            trail.append(f"{fmt} x {niche} -> {vibe}")
        elif fmt in D["format_default"]:
            vibe = D["format_default"][fmt]
            trail.append(f"{fmt} default -> {vibe}")
        else:
            vibe = D["global_default"]
            trail.append(f"global default -> {vibe}")
    low = (prompt or "").lower()
    for c in D["prompt_cues"]:
        if fmt not in c["formats"]:
            continue
        m = re.search(c["pattern"], low)
        if m:
            if c["vibe"] != vibe:
                replaced.append(vibe)
                trail.append(f"prompt cue '{m.group(0)}' -> {c['vibe']}")
                vibe = c["vibe"]
            break
    if vibe == "raw-ugc" and pack is not None:
        pp = niche_pattern(pack, niche)
        new = D["pack_pattern"]["map"].get(pp[0]) if pp else None
        if pp and new and new != vibe and pp[1] >= PACK_SHARE_MIN:
            replaced.append(vibe)
            trail.append(f"research pack pattern {pp[0]} ({pp[1]:.0%} of "
                         f"{pp[2]}) -> {new}")
            vibe = new
    primary = _lanes(vibe, fit, duration, presenter, niche, shop, trail)
    # secondary: the first other candidate that survives the same lanes
    cands = list(reversed(replaced)) + [fn.get(niche),
                                        D["format_default"].get(fmt),
                                        D["global_default"]]
    VP = _profiles()
    cands += [v for v in CV.VIBES if niche in VP[v]["best_niches"]
              and fmt in VP[v]["best_formats"]]
    cands += [v for v in CV.VIBES if fmt in VP[v]["best_formats"]]
    secondary = None
    for c in cands:
        if c in CV.VIBES:
            c2 = _lanes(c, fit, duration, presenter, niche, shop)
            if c2 != primary:
                secondary = c2
                break
    # learned tie-break: only between two lane-approved alternatives
    if secondary and priors is not None:
        m1, m2 = _mean(priors, niche, primary), _mean(priors, niche, secondary)
        base = m1 if m1 is not None else NEUTRAL
        if (m2 is not None and m2 > base and
                _lanes(secondary, fit, duration, presenter, niche, shop)
                == secondary):
            trail.append(f"learned tie-break ({niche}): {secondary} "
                         f"{m2:.2f} > {primary} {base:.2f}")
            primary, secondary = secondary, primary
    return primary, secondary, trail


# ----------------------------------------------------------------- tone
def _tone(vibe, presenter, niche):
    prof = _profiles()[vibe]["tone"]
    VR = data()["VOICE_RULES"]
    allowed = list(prof["allowed"])
    voice = prof["default"]
    notes = []
    if presenter == "ai":
        ok = VR["ai"]["tones_allowed"]
        allowed = [t for t in allowed if t in ok]
        if vibe == "playful-comedic":
            voice = "deadpan"
        elif voice == "excited":
            voice = "confident"
        elif voice not in ok:
            voice = "warm"
        if voice not in allowed:
            allowed.insert(0, voice)
        notes.append("AI persona: " + "; ".join(
            f"{k} {v}" for k, v in VR["ai"]["tones_restricted"].items()) +
            ", never as testimonial or confession")
    tp = data()["TONE_PROFILES"][voice]
    notes.insert(0, tp["delivery_notes"])
    H = data()["HUMOR"]
    humor = H["by_vibe"].get(vibe, "none")
    if niche in H["none_niches"]:
        humor = "none"
    if presenter == "ai" and humor == "high":
        humor = H["ai_max"]
    if humor != "none":
        notes.append(H["rule"])
    return {"voice": voice, "allowed": allowed, "humor": humor,
            "notes": " ".join(n.rstrip(".") + "." for n in notes)}


# --------------------------------------------------------------- pacing
def _pacing(vibe, items, duration):
    p = _profiles()[vibe]["pacing"]
    lo, hi = p["target_wpm"]
    idx, _rule = _duration_rule(duration)
    if idx == 0:                       # <= 15 s: upper half of the band
        lo = int(round((lo + hi) / 2.0))
    floors = [60.0 * _gate_wps(it.get("delivery")) for it in items
              if _spoken(it)]
    if floors:                         # never slower than any beat's sizing
        lo = max(lo, min(floors))
        hi = max(hi, max(floors))
    lo = int(round(min(max(lo, WPM_MIN), WPM_MAX)))
    hi = int(round(min(max(hi, lo), WPM_MAX)))
    pi = float(p["pattern_interrupt_s"])
    if idx == 0:
        pi = min(pi, 3.0)
    elif idx == 2:
        pi = min(pi, 6.0)
    return {"target_wpm": [lo, hi],
            "avg_shot_s": [float(x) for x in p["avg_shot_s"]],
            "cuts_per_10s": [int(x) for x in p["cuts_per_10s"]],
            "max_static_s": MAX_STATIC_S, "pattern_interrupt_s": pi}


# --------------------------------------------------------- energy curve
def _shape(lv, types, n_hook, dips):
    """ENERGY_CURVE.rules: a single peak at the PAYOFF, a dip before the
    demo/payoff (two at >= 46 s), CTA in [2, PAYOFF), >= 3 distinct levels."""
    lv = [min(5, max(1, int(x))) for x in lv]
    k = types.index("PAYOFF") if "PAYOFF" in types else None
    if k is not None:
        lv[k] = max(lv[k], 2)
        for i in range(len(lv)):
            if i != k and lv[i] >= lv[k]:
                lv[i] = lv[k] - 1
    for i, t in enumerate(types):
        if t == "CTA":
            top = lv[k] - 1 if k is not None else 5
            lv[i] = min(max(lv[i], 2), max(top, 1))
    hooks = [lv[i] for i in range(min(n_hook, len(lv)))
             if types[i] == "VERBAL HOOK + LOCK"] or lv[:n_hook]
    if hooks and max(hooks) > 1:
        hook = max(hooks)
        stop = next((i for i in range(n_hook, len(lv))
                     if types[i] in ("DEMO BEAT", "PAYOFF")), len(lv))
        if dips > 1 and k is not None:
            stop = k
        region = [i for i in range(n_hook, stop)
                  if types[i] not in ("PAYOFF", "CTA")]
        need = dips - sum(1 for i in region if lv[i] <= hook - 1)
        for i in region:
            if need <= 0:
                break
            if lv[i] > hook - 1:
                lv[i] = hook - 1
                need -= 1
    if len(set(lv)) < 3:
        for i in range(n_hook, len(lv)):
            if types[i] in ("PAYOFF", "CTA"):
                continue
            if lv[i] - 1 >= 1 and (lv[i] - 1) not in lv:
                lv[i] -= 1
                break
    return lv


def _energy_curve(vibe, script, items, duration):
    EC = data()["ENERGY_CURVE"]
    table = EC["by_vibe"].get(vibe) or EC["base"]
    types = [it.get("type") or "" for it in items]
    lv = [table.get(t, EC["base"].get(t, 3)) for t in types]
    n_hook = len([it for it in (script.get("hook_stack") or [])
                  if isinstance(it, dict)])
    lv = _shape(lv, types, n_hook, 2 if _duration_rule(duration)[0] == 2 else 1)
    out = []
    for it, t, e in zip(items, types, lv):
        row = {"t": it.get("t") or "", "type": t, "energy": e}
        if _spoken(it):
            row["wpm"] = int(round(60.0 * _gate_wps(it.get("delivery"))))
        out.append(row)
    return out


# ---------------------------------------------------------------- music
def _queries(moods, genres, bpm):
    ms = [m for m in moods if m and m != "none"] or ["ambient"]
    gs = []
    for g in genres:
        if g.startswith("none"):
            continue
        g = re.sub(r"\s*\([^)]*\)", "", g)
        g = re.split(r"\s+(?:with|into)\s+", g)[0]
        g = re.sub(r"^optional\s+", "", g).strip()
        if g and g not in gs:
            gs.append(g)
    gs = gs or ["ambient pad"]
    lo, hi = int(bpm[0]), int(bpm[1])
    tails = (f"instrumental {lo}-{hi} BPM", f"no vocals {(lo + hi) // 2} BPM",
             f"background music {hi} BPM")
    out = []
    for i, tail in enumerate(tails):
        m, g = ms[i % len(ms)], gs[i % len(gs)]
        head = g if m in g.split() else f"{m} {g}"
        out.append(f"{head} {tail}")
    return out


def _key2(s):
    return " ".join(s.lower().split()[:2])


def _licence(platform, lane, presenter):
    ML = data()["MUSIC_LICENSING"]
    cells = ML["matrix"][platform]
    base = cells["creator"][lane]
    never, seen = [], []
    for acct in ("creator", "personal", "business"):
        for n in cells[acct][lane]["never"]:
            k = _key2(n)
            if k not in seen:
                seen.append(k)
                never.append(n)
    parts = [f"{lane} lane; product content is commercial on every account "
             f"type (personal, creator, business)"]
    if base["also_ok"]:
        parts.append("also OK: " + "; ".join(base["also_ok"][:2]))
    ai_ok = platform != "tiktok" and lane == "organic"
    never = [n for n in never if not n.lower().startswith("ai-generated music")]
    never.append("AI-generated music (TikTok commercial content)"
                 if platform == "tiktok" else
                 ("AI-generated music" if not ai_ok else ""))
    parts.append("never: " + "; ".join(n for n in never if n))
    if base.get("max_music_s"):
        parts.append(f"music clip up to {base['max_music_s']} s")
    if ai_ok:
        parts.append("AI music only from a paid plan with commercial rights, "
                     "with the platform's AI label on")
    flags = [f for f in base.get("flags") or []
             if presenter == "ai" or "AI" not in f]
    if flags:
        parts.append("flags: " + "; ".join(flags[:2]))
    return {"library": base["library"], "note": ". ".join(
        _cap(p) for p in parts) + "."}


def _music(vibe, fit, presenter, lanes):
    m = _profiles()[vibe]["music"]
    moods = list(m["moods"])
    if fit == "utilitarian":
        moods = [x for x in moods if x not in ("nostalgic", "sentimental")] \
            or ["steady"]
    elif fit == "hedonic":
        moods = [x for x in moods if x not in ("steady", "neutral")] \
            or ["warm"]
    return {"moods": moods, "bpm": [int(m["bpm"][0]), int(m["bpm"][1])],
            "genres": list(m["genres"]), "vo_ducking_db": m["vo_ducking_db"],
            "sfx": list(m["sfx"]), "in_master": False,
            "search_queries": _queries(moods, m["genres"], m["bpm"]),
            "licensing": {p: _licence(p, lanes[p], presenter)
                          for p in CV.PLATFORMS}}


# --------------------------------------------------- look / camera / text
def _look(vibe, place, subj, presenter):
    L = _profiles()[vibe]["look"]
    wardrobe = L["wardrobe"]
    if presenter == "ai":
        wardrobe = ("the persona's locked outfit (identity lock; never "
                    f"restyle); otherwise {wardrobe}")
    return {"lighting": L["lighting"],
            "palette_names": list(L["palette_names"]),
            "palette_hex": list(L["palette_hex"]), "grade": L["grade"],
            "set": data()["SET_TEMPLATES"][vibe].format(place=place, subj=subj),
            "wardrobe": wardrobe}


def _camera(vibe, presenter, shop):
    C = _profiles()[vibe]["camera"]
    drop = []
    if presenter == "ai":
        drop.append("handheld")        # faked shake on an AI render (F133)
    if shop:
        drop += data()["LANES"]["tiktok_shop"]["camera_drop"]
    mv = [m for m in C["movement"] if m not in drop]
    if not any(m in D48_MOVES for m in mv):
        mv.append("push-in")
    return {"style": C["style"], "lens": C["lens"], "movement": mv}


def _text_style(vibe):
    T = _profiles()[vibe]["text_style"]
    n = int(T["max_words_per_card"])
    placement = (T["placement"] + f"; frame-0 card: up to {FRAME0_MAX_WORDS} "
                 "words, UPPER, no emoji")
    if n > FRAME0_MAX_WORDS:
        placement += f"; later cards up to {n} words"
    return {"case": T["case"], "weight": T["weight"],
            "max_words_per_card": min(FRAME0_MAX_WORDS, n),
            "placement": placement}


def _showmanship(vibe, presenter, seed, subj):
    S = data()["SHOWMANSHIP"]
    pool = [d for d in S["by_vibe"][vibe]
            if presenter in S["devices"][d]["presenters"]]
    rng = random.Random(seeding.derive_seed(seed, "direction"))
    pick = pool[rng.randrange(len(pool))]
    return S["devices"][pick]["text"].format(subj=subj)


def _gender(script):
    ident = ((script.get("persona") or {}).get("identity")
             if isinstance(script.get("persona"), dict) else "") or ""
    for rx, g in _GENDER:
        if rx.search(ident):
            return g
    return None


def _voice(script, presenter, tone, curve, pacing, shop):
    floors = [e["wpm"] for e in curve if "wpm" in e]
    one_rate = max(floors) if floors else pacing["target_wpm"][0]
    g = _gender(script)
    if presenter == "ai":
        spec = ("Natural-prosody synthetic AI voice, disclosed as AI-generated: "
                "one consistent, consented voice for this persona in every "
                "video" + (f" ({g}, matching the presenter identity)" if g else "")
                + f"; {tone} tone, no robotic cadence; never claims to be human "
                f"or to have used the product; never slower than each beat's "
                f"listed wpm (one TTS rate for the whole track: at least "
                f"{one_rate} wpm), pauses as commas or 300 ms breaks at beat "
                f"seams; stress names and numbers and end claims on a falling "
                f"contour")
        if shop:
            spec += "; " + data()["LANES"]["tiktok_shop"]["ai_note"]
    else:
        spec = (f"Real voice, recorded on the day; no TTS, no voice changer; "
                f"{tone} tone at a natural pace, never slower than each beat's "
                f"listed wpm; 1-2 natural disfluencies are fine; no scripted "
                f"laughs")
        if shop:
            spec += "; microphone in a quiet room (TikTok Shop)"
    return {"presenter": presenter, "spec": spec}


def _do_dont(vibe, concept, subj, niche, presenter, fit, shop):
    VP = _profiles()[vibe]
    sub = (lambda s: s.replace("the product", subj)) \
        if concept in ("product", "showcase") else (lambda s: s)
    do = [sub(x) for x in VP["do"]]
    dont = [sub(x) for x in VP["dont"]]
    do.append(data()["IN_FRAME"][concept].format(subj=subj))
    do.append(data()["NICHE_DO"].get(niche) or data()["NICHE_DO"]["default"])
    do.append(VP["presenter_notes"][presenter])
    if presenter == "ai":
        if fit == "hedonic":
            do.append("hedonic product with an AI persona: keep it product-led "
                      "with hands and objects (humans convert better, F32)")
        dont.append("no lived-experience, testimonial or human-voice claims "
                    "from the AI persona (FTC 465, D137)")
        if "handheld" in VP["camera"]["movement"]:
            dont.append("no faked handheld shake on the AI render (F133)")
    if shop:
        L = data()["LANES"]["tiktok_shop"]
        do += L["do"]
        dont += L["dont"]
    return _dedupe(do), _dedupe(dont)


def _evidence(vibe, presenter, shop):
    EV = data()["EVIDENCE"]
    keys = [k for k in _profiles()[vibe]["evidence"] if k in EV][:3]
    keys += ["tiktok-cml-terms"]
    if shop:
        keys.append("tiktok-shop-2026")
    keys.append("calm-tts-2023" if presenter == "ai" else "vanzant-berger-2020")
    keys.append("system1-tiktok")
    return [dict(EV[k]) for k in _dedupe(keys)][:6]


# ---------------------------------------------------------------- build
def _build(script, ctx, seed, pack, priors):
    fmt = script.get("format") or "demo"
    presenter = "ai" if script.get("presenter") == "ai" else "human"
    niche = script.get("niche") or "default"
    fit = script.get("fit") or "neutral"
    duration = _num(script.get("duration_s"), 30.0)
    items = _items(script)
    concept, csrc = infer_concept(script, ctx)
    subject, subj = _subject(script, ctx, concept)
    shop = shop_lane(script)
    vibe, secondary, trail = resolve_vibe(
        concept, fmt, niche, fit, presenter, duration,
        _clean_prompt(script.get("prompt")), pack=pack, priors=priors,
        shop=shop)
    if presenter == "ai" and fit == "hedonic":
        trail.append("hedonic product + AI persona: vibe kept, humans convert "
                     "better (F32)")
    if csrc != "ctx":
        trail.insert(0, f"concept {concept} (from {csrc})")
    tone = _tone(vibe, presenter, niche)
    pacing = _pacing(vibe, items, duration)
    curve = _energy_curve(vibe, script, items, duration)
    lanes = dict(data()["LANES"]["tiktok_shop"]["lanes"]) if shop else \
        {p: "organic" for p in CV.PLATFORMS}
    do, dont = _do_dont(vibe, concept, subj, niche, presenter, fit, shop)
    return {
        "schema_version": SCHEMA_VERSION,
        "vibe": vibe,
        "vibe_reason": "; ".join(trail),
        "secondary_vibe": secondary,
        "tone": tone,
        "energy": int(_profiles()[vibe]["energy"]),
        "pacing": pacing,
        "energy_curve": curve,
        "music": _music(vibe, fit, presenter, lanes),
        "look": _look(vibe, _place(script, ctx, niche), subj, presenter),
        "camera": _camera(vibe, presenter, shop),
        "text_style": _text_style(vibe),
        "transitions": list(_profiles()[vibe]["transitions"]),
        "showmanship": _showmanship(vibe, presenter, seed, subj),
        "voice": _voice(script, presenter, tone["voice"], curve, pacing, shop),
        "do": do,
        "dont": dont,
        "evidence": _evidence(vibe, presenter, shop),
    }


def direct(script, ctx=None, seed=None, maker=None):
    """-> the script["direction"] dict (docs/CREATIVE-PLAN.md §1.1), or None
    for a non-dict. Works without ctx (--script-json inputs): the concept is
    then inferred from the script. Never mutates script/ctx and never touches
    the maker's rng."""
    if not isinstance(script, dict):
        return None
    return _build(script, ctx if isinstance(ctx, dict) else None, seed,
                  _pack(maker), _priors())
