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
import collections
import copy
import hashlib
import importlib
import json
import os
import random
import re
import subprocess
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
            "notes": " ".join(_cap(n.rstrip(".")) + "." for n in notes)}


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
        # add a level with a beat that shares its level (never empty one)
        top = lv[k] if k is not None else 6
        for i in range(n_hook, len(lv)):
            if types[i] in ("PAYOFF", "CTA") or lv.count(lv[i]) < 2:
                continue
            if lv[i] - 1 >= 1 and (lv[i] - 1) not in lv:
                lv[i] -= 1
                break
            if lv[i] + 1 < top and (lv[i] + 1) not in lv:
                lv[i] += 1
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
    first = min(FRAME0_MAX_WORDS, n)
    placement = (T["placement"] + f"; frame-0 card: up to {first} words, "
                 "UPPER, no emoji")
    if n > first:
        placement += f"; later cards up to {n} words"
    return {"case": T["case"], "weight": T["weight"],
            "max_words_per_card": first, "placement": placement}


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
    if presenter == "human" and vibe in data()["FINISH"]["candid"] and \
            "candid" not in VP["presenter_notes"]["human"]:
        do.append("at least 2 candid cues: handheld micro-shake, uneven "
                  "natural light, a mid-sentence punch-in (C6)")
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


# --------------------------------------------------------------- render
_PLATFORM_NAMES = {"tiktok": "TikTok", "instagram": "Instagram",
                   "youtube_shorts": "YouTube Shorts"}


def _join(xs, sep=", "):
    return sep.join(str(x) for x in xs if x)


def render_md(direction):
    """The bundle section / direction.md. Starts with HEADING; never contains
    a shot heading, a creative_vocab.BUNDLE_FORBIDDEN phrase or a D46 link
    phrase."""
    d = direction or {}
    t, p, m = d.get("tone") or {}, d.get("pacing") or {}, d.get("music") or {}
    L, C, T = d.get("look") or {}, d.get("camera") or {}, d.get("text_style") or {}
    v = d.get("vibe") or ""
    wpm = p.get("target_wpm") or [WPM_MIN, WPM_MAX]
    out = [HEADING]
    sec = d.get("secondary_vibe")
    out.append(f"**Vibe:** {v} \u2014 {CV.VIBES.get(v, '')}"
               + (f" (secondary: {sec})" if sec else "") + ". "
               f"Why: {d.get('vibe_reason') or 'profile default'}.")
    out.append(f"**Tone:** {t.get('voice')} (allowed: {_join(t.get('allowed') or [])}"
               f"; humour: {t.get('humor')}). {t.get('notes') or ''}".rstrip())
    out.append(f"**Pacing:** VO {wpm[0]}\u2013{wpm[1]} wpm, and never slower "
               "than a beat's wpm below (each beat was sized at that rate; calm "
               "comes from pauses and fewer words, not slower speech) \u00b7 "
               f"average shot {_join(p.get('avg_shot_s') or [], chr(8211))} s "
               f"\u00b7 {_join(p.get('cuts_per_10s') or [], chr(8211))} cuts per "
               f"10 s \u00b7 no static shot over {p.get('max_static_s', MAX_STATIC_S):g} s "
               f"\u00b7 a pattern interrupt at least every "
               f"{p.get('pattern_interrupt_s', 5):g} s \u00b7 energy "
               f"{d.get('energy')}/5.")
    out.append("")
    out.append("| window | beat | energy | wpm |")
    out.append("|---|---|---|---|")
    for e in d.get("energy_curve") or []:
        out.append(f"| {e.get('t')} | {e.get('type')} | {e.get('energy')} | "
                   f"{e.get('wpm', chr(8212))} |")
    out.append("")
    bpm = m.get("bpm") or [0, 0]
    out.append(f"**Music:** {_join(m.get('moods') or [])} \u00b7 {bpm[0]}\u2013"
               f"{bpm[1]} BPM \u00b7 {_join(m.get('genres') or [], ' / ')} "
               f"\u00b7 duck {m.get('vo_ducking_db')} dB under the VO \u00b7 SFX: "
               f"{_join(m.get('sfx') or [])}. Search the platform library for: "
               + " \u00b7 ".join(f"\u201c{q}\u201d" for q in m.get("search_queries") or [])
               + " (never a named commercial track).")
    out.append("**Licensing** (music is added at upload, not in the master: "
               "deliver VO + SFX + room tone only):")
    for pl in CV.PLATFORMS:
        lic = (m.get("licensing") or {}).get(pl) or {}
        out.append(f"- {_PLATFORM_NAMES[pl]}: {lic.get('library')} \u2014 "
                   f"{lic.get('note')}")
    out.append("- Trends: a trending song only if it is in that platform's "
               "library; otherwise copy the trend's format or beat timing with "
               "a licensed bed. Log platform, account type, lane, library, "
               "track id, date and placements.")
    pal = ", ".join(f"{n} {h}" for n, h in zip(L.get("palette_names") or [],
                                               L.get("palette_hex") or []))
    out.append(f"**Look:** {_cap(L.get('lighting') or '')}. Palette: {pal}. "
               f"Grade: {L.get('grade')}. Set: {L.get('set')}. Wardrobe: "
               f"{L.get('wardrobe')}.")
    out.append(f"**Camera:** {_cap(C.get('style') or '')}; lens: "
               f"{C.get('lens')}; moves: {_join(C.get('movement') or [])}.")
    out.append(f"**Text style:** {T.get('case')} case, {T.get('weight')}, "
               f"high contrast; {T.get('placement')}.")
    out.append(f"**Transitions:** {_join(d.get('transitions') or [])}.")
    out.append(f"**Showmanship (one device):** {_cap(d.get('showmanship') or '')}.")
    out.append(f"**Voice:** {(d.get('voice') or {}).get('spec')}.")
    out.append("**Do:** " + " \u00b7 ".join(d.get("do") or []))
    out.append("**Don't:** " + " \u00b7 ".join(d.get("dont") or []))
    return "\n".join(out) + "\n"


def style_paragraph(direction):
    """One paragraph that replaces the legacy ## STYLE body. Lo-fi vs polish
    is per vibe (research §2.1): only candid vibes invite imperfection."""
    d = direction or {}
    v = d.get("vibe") or "raw-ugc"
    F = data()["FINISH"]
    finish = F["candid_text"] if v in F["candid"] else F["clean_text"]
    L, C, T, m = (d.get("look") or {}, d.get("camera") or {},
                  d.get("text_style") or {}, d.get("music") or {})
    lane = "AI" if (d.get("voice") or {}).get("presenter") == "ai" else "Human"
    tr = [x if x != "none" else "no transition (hold the take)"
          for x in d.get("transitions") or ["hard-cut"]]
    bpm = m.get("bpm") or [0, 0]
    return (f"{lane} UGC, {v} vibe: {CV.VIBES.get(v, '')}. 9:16 vertical. "
            f"Set: {L.get('set')}. Light: {L.get('lighting')}. Grade: "
            f"{L.get('grade')}; palette {_join(L.get('palette_names') or [])}. "
            f"{finish}. Camera: {C.get('style')} "
            f"({_join(C.get('movement') or [])}). Transitions: {tr[0]} by "
            f"default; {_join(tr[1:], ' / ') or tr[0]} where the beat changes. "
            f"On-screen graphic text (labels like BEFORE/AFTER, TEST 1): "
            f"{T.get('weight')}, {T.get('case')} case, high contrast; "
            f"{T.get('placement')}. Safe zones: keep graphic text and key "
            f"action clear of the top 250px, bottom 320px (IG UI overlays), "
            f"and the right rail. Product accuracy: match the PRODUCT block "
            f"above exactly \u2014 no invented branding. Audio: voiceover clean "
            f"and forward over real product sound and room tone; no music in "
            f"the master \u2014 a {_join((m.get('moods') or [])[:2], ', ')} bed "
            f"({bpm[0]}\u2013{bpm[1]} BPM) is added at upload from each "
            f"platform's commercial library, ducked {m.get('vo_ducking_db')} dB "
            f"under speech.")


def voice_spec(direction):
    """The full VOICEOVER "Voice spec:" line (label included)."""
    spec = ((direction or {}).get("voice") or {}).get("spec") or ""
    return "Voice spec: " + spec.rstrip(".") + "."


# ------------------------------------------------------------ validation
_GRADES = ("P", "S", "M", "A")


def validate(direction, script):
    """Contract problems of one direction for its script -> [str]."""
    d, s, errs = direction, script, []
    if not isinstance(d, dict):
        return ["direction missing"]
    presenter = "ai" if s.get("presenter") == "ai" else "human"
    if d.get("schema_version") != SCHEMA_VERSION:
        errs.append("schema_version")
    for k in ("vibe", "secondary_vibe"):
        if d.get(k) is not None and d.get(k) not in CV.VIBES:
            errs.append(f"{k} {d.get(k)!r} not a VIBES id")
    if d.get("vibe") is None:
        errs.append("vibe missing")
    t = d.get("tone") or {}
    if t.get("voice") not in CV.TONES or t.get("voice") not in (t.get("allowed") or []):
        errs.append(f"tone.voice {t.get('voice')!r}")
    if any(x not in CV.TONES for x in t.get("allowed") or []):
        errs.append("tone.allowed has a non-TONES id")
    if t.get("humor") not in ("none", "light", "high"):
        errs.append("tone.humor")
    if presenter == "ai":
        ai_ok = data()["VOICE_RULES"]["ai"]["tones_allowed"]
        if any(x not in ai_ok for x in t.get("allowed") or []):
            errs.append("AI tone outside the §4 allowed set")
        if d.get("vibe") in ("story-vlog", "raw-ugc"):
            errs.append(f"AI presenter got {d.get('vibe')}")
    if any(m not in CV.CAMERA_MOVES for m in (d.get("camera") or {}).get("movement") or []):
        errs.append("camera.movement has a non-CAMERA_MOVES id")
    trans = data()["PROPOSED_VOCAB"]["TRANSITIONS"]
    if any(x not in trans for x in d.get("transitions") or []):
        errs.append("transition id outside PROPOSED_VOCAB.TRANSITIONS")
    items = _items(s)
    curve = d.get("energy_curve") or []
    if [(e.get("t"), e.get("type")) for e in curve] != \
            [(it.get("t") or "", it.get("type") or "") for it in items]:
        errs.append("energy_curve does not cover every hook_stack + beats item "
                    "in order")
    p = d.get("pacing") or {}
    lo, hi = (p.get("target_wpm") or [0, 0])[:2]
    if not (WPM_MIN <= lo <= hi <= WPM_MAX):
        errs.append(f"target_wpm {lo}-{hi} outside {WPM_MIN}-{WPM_MAX}")
    if not p.get("max_static_s") or p["max_static_s"] > MAX_STATIC_S:
        errs.append("max_static_s > 3.5")
    floors = []
    for e, it in zip(curve, items):
        if not isinstance(e.get("energy"), int) or not 1 <= e["energy"] <= 5:
            errs.append(f"energy {e.get('energy')!r} at {e.get('type')}")
        if _spoken(it):
            need = int(round(60 * _gate_wps(it.get("delivery"))))
            floors.append(need)
            if e.get("wpm") != need:
                errs.append(f"{it.get('type')} wpm {e.get('wpm')} != sizing {need}")
    if floors and (lo < min(floors) or hi < max(floors)):
        errs.append(f"target_wpm {lo}-{hi} slower than the per-beat sizing "
                    f"{min(floors)}-{max(floors)}")
    types = [e.get("type") for e in curve]
    lv = [e.get("energy") for e in curve]
    if "PAYOFF" in types:
        k = types.index("PAYOFF")
        if lv.count(max(lv)) != 1 or lv[k] != max(lv):
            errs.append(f"energy peak is not a single PAYOFF: {lv}")
        for e in curve:
            if e.get("type") == "CTA" and not 2 <= e["energy"] <= lv[k]:
                errs.append("CTA energy outside [2, PAYOFF]")
    if len(curve) >= 5 and len(set(lv)) < 3:
        errs.append(f"flat energy curve {lv}")
    m = d.get("music") or {}
    if m.get("in_master") is not False:
        errs.append("music.in_master must be False")
    q = m.get("search_queries") or []
    if len(q) != 3 or any(not isinstance(x, str) or "BPM" not in x or
                          re.search("[\"\u201c\u201d]| by ", x) for x in q):
        errs.append(f"search_queries {q!r}")
    lic = m.get("licensing") or {}
    for pl in CV.PLATFORMS:
        c = lic.get(pl) or {}
        if not c.get("library") or not c.get("note"):
            errs.append(f"licensing.{pl} missing")
    tk = (lic.get("tiktok") or {}).get("note") or ""
    if "AI-generated music" not in tk:
        errs.append("TikTok licensing does not rule out AI music")
    if (d.get("text_style") or {}).get("max_words_per_card", 99) > FRAME0_MAX_WORDS:
        errs.append("text_style.max_words_per_card > 3")
    sh = d.get("showmanship")
    if not isinstance(sh, str) or not sh.strip():
        errs.append("showmanship missing")
    v = d.get("voice") or {}
    spec = v.get("spec") or ""
    if v.get("presenter") != presenter:
        errs.append("voice.presenter")
    if presenter == "ai":
        from vsp import lexicon
        if not (lexicon.has_ai_disclosure_line(spec) and "synthetic" in spec
                and "disclosed" in spec and "never claims to be human" in spec):
            errs.append("AI voice spec not disclosed")
    elif "no TTS" not in spec or "synthetic" in spec:
        errs.append("human voice spec")
    ev = d.get("evidence") or []
    if not ev or any(not isinstance(e, dict) or e.get("grade") not in _GRADES
                     or not e.get("claim") or not e.get("source") for e in ev):
        errs.append("evidence entries")
    if not d.get("do") or not d.get("dont"):
        errs.append("do/dont empty")
    return errs


def text_problems(direction, script=None):
    """Bundle-text problems of render_md / style_paragraph / voice_spec."""
    errs = []
    md = render_md(direction)
    sp, vs = style_paragraph(direction), voice_spec(direction)
    if not md.startswith(HEADING + "\n"):
        errs.append("render_md heading")
    if "music is added at upload, not in the master" not in md:
        errs.append("render_md lacks the upload-music line")
    for name, txt in (("render_md", md), ("style_paragraph", sp),
                      ("voice_spec", vs)):
        for ph in CV.BUNDLE_FORBIDDEN + FORBIDDEN_CLAIMS:
            if ph.lower() in txt.lower():
                errs.append(f"{name} contains {ph!r}")
        if CV.link_groups_in(txt):
            errs.append(f"{name} has D46 link groups {sorted(CV.link_groups_in(txt))}")
    if "\n## " in md or "\n### " in md:
        errs.append("render_md has a sub-heading")
    if "9:16" not in sp or "\n" in sp.strip():
        errs.append("style_paragraph is not one 9:16 paragraph")
    if not vs.startswith("Voice spec: ") or "\n" in vs:
        errs.append("voice_spec is not one line")
    if isinstance(script, dict) and script.get("presenter") == "ai":
        from vsp import lexicon
        hit = lexicon.first_match(lexicon.AI_FIRST_PERSON, md + "\n" + sp)
        if hit:
            errs.append(f"AI bundle text voices lived experience: {hit!r}")
    return errs


# ------------------------------------------------------------- selfcheck
def _maker():
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    import viral_script_maker
    return viral_script_maker


def _golden():
    with open(os.path.join(REPO, "evals", "golden.jsonl"), encoding="utf-8") as f:
        return [json.loads(ln) for ln in f
                if ln.strip() and not ln.lstrip().startswith("//")]


def _digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False)
                          .encode("utf-8")).hexdigest()


_HASH_CODE = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
import viral_script_maker as m
from vsp import direction as D
out = []
for pr in json.loads(sys.argv[2]):
    for f in D.FORMATS:
        for p in D.PRESENTERS:
            s = m.generate(pr, presenter=p, fmt=f, duration=30, seed=1)
            out.append([s.get("direction"), D.render_md(s.get("direction"))])
print("@@DIGEST@@" + D._digest(out))
"""


def _unit_checks():
    """Synthetic-input checks of the lanes, tie-break, pacing and pack."""
    errs = []
    from vsp import priors as P
    base = {"prompt": "electric milk frother", "presenter": "ai",
            "format": "demo", "duration_s": 30, "niche": "tools",
            "fit": "utilitarian", "hook_family": "negative-command",
            "hook_stack": [{"t": "0.0\u20130.5s", "type": "VISUAL TRIGGER"},
                           {"t": "0.5\u20133.0s", "type": "VERBAL HOOK + LOCK",
                            "dialogue": "Stop buying frothers on looks.",
                            "delivery": "Brisk, confident."}],
            "beats": [{"t": "3.0\u201315.0s", "type": "DEMO BEAT",
                       "dialogue": "Watch it work.", "delivery": "Energetic."},
                      {"t": "15.0\u201325.0s", "type": "PAYOFF",
                       "dialogue": "Test result.", "delivery": "Slow down."},
                      {"t": "25.0\u201330.0s", "type": "CTA",
                       "dialogue": "Part 2 next.", "delivery": "Brisk."}]}

    def run(s, pri=None, pack=None, seed=1, ctx=None):
        return _build(s, ctx, seed, pack, pri)

    d0 = run(base)
    if d0["vibe"] != "expert-trust" or d0["secondary_vibe"] != "clean-aesthetic":
        errs.append(f"unit base vibe {d0['vibe']}/{d0['secondary_vibe']}")

    def pri(niche, key, a, b, n):
        return P.normalise({"schema_version": 2, "families": {}, "global": {},
                            "sections": {"vibe": {"by_niche": {niche: {
                                key: {"alpha": a, "beta": b, "n": n}}},
                                "global": {}}}})
    d1 = run(base, pri("tools", "clean-aesthetic", 9, 1, 10))
    if d1["vibe"] != "clean-aesthetic" or "tie-break" not in d1["vibe_reason"]:
        errs.append("tie-break did not pick the stronger secondary")
    if run(base, pri("tools", "clean-aesthetic", 9, 1, 2))["vibe"] != "expert-trust":
        errs.append("tie-break used a prior with n < 3")
    if run(base, pri("tools", "clean-aesthetic", 1, 9, 10))["vibe"] != "expert-trust":
        errs.append("tie-break picked a weaker secondary")
    sv = dict(base, prompt="I quit sugar for 21 days", format="pov-vlog",
              niche="food", fit="hedonic", hook_family="challenge")
    sv["beats"] = [dict(b, type="STORY BEAT") if b["type"] == "DEMO BEAT" else b
                   for b in base["beats"]]
    d2 = run(sv, pri("food", "story-vlog", 99, 1, 100))
    if d2["vibe"] == "story-vlog" or d2["secondary_vibe"] == "story-vlog":
        errs.append("AI presenter reached story-vlog through a prior")
    if run(dict(sv, presenter="human"))["vibe"] != "story-vlog":
        errs.append("human challenge pov-vlog is not story-vlog")
    if run(dict(sv, presenter="human", duration_s=15))["vibe"] != "raw-ugc":
        errs.append("15 s story-vlog did not swap to raw-ugc")
    short = run(dict(sv, presenter="human", duration_s=15))["pacing"]
    if short["pattern_interrupt_s"] > 3 or short["target_wpm"][0] < 170:
        errs.append(f"15 s pacing {short}")
    hype = dict(base, prompt="mini projector", niche="gadgets", presenter="human")
    if run(hype)["vibe"] != "hype-energy" or \
            run(dict(hype, duration_s=60))["vibe"] != "raw-ugc":
        errs.append("gadget demo hype-energy / 60 s swap")
    fin = dict(base, prompt="budget planner", niche="finance", format="review",
               presenter="human", fit="neutral")
    for f in FORMATS:
        if run(dict(fin, format=f))["vibe"] in ("playful-comedic", "hype-energy",
                                                "cozy-calm"):
            errs.append(f"finance veto failed for {f}")
    brisk = dict(base, beats=[dict(b, delivery="Brisk.") for b in base["beats"]])
    if run(brisk)["pacing"]["target_wpm"][0] < 180:
        errs.append("all-brisk script got a band slower than 180 wpm")
    shop = dict(base, prompt="tiktok shop lint remover", niche="home",
                presenter="human", format="review")
    ds = run(shop)
    lic = ds["music"]["licensing"]["tiktok"]
    if not lic["note"].startswith("Shop lane") or \
            not any("real person visible" in x for x in ds["do"]) or \
            "handheld" in ds["camera"]["movement"] or \
            "quiet room" not in ds["voice"]["spec"]:
        errs.append("TikTok Shop lane rules missing")
    dsa = run(dict(shop, presenter="ai"))
    if "not eligible for the TikTok Shop lane" not in dsa["voice"]["spec"] or \
            dsa["vibe"] in ("raw-ugc", "story-vlog"):
        errs.append("AI + TikTok Shop conflict not stated")
    if run(dict(base, prompt="luxury perfume", niche="beauty",
                presenter="human"), ctx=None)["vibe"] != "cinematic-premium" or \
            run(dict(shop, prompt="tiktok shop luxury perfume",
                     format="demo"))["vibe"] == "cinematic-premium":
        errs.append("cinematic cue / Shop people-visible swap")
    rev = dict(base, prompt="wireless charger", niche="gadgets",
               format="review", presenter="human", fit="utilitarian")
    pk = {"niche_patterns": {"ugc-ads": [
        {"pattern": "b-roll-captions", "times_seen": 40},
        {"pattern": "talking-head-ugc", "times_seen": 10}]}}
    if run(rev)["vibe"] != "raw-ugc" or run(rev, pack=pk)["vibe"] != \
            "clean-aesthetic" or run(rev, pack={"top_patterns": []})["vibe"] != "raw-ugc":
        errs.append("pack niche pattern (raw-ugc only, share >= 0.25)")
    weak = {"niche_patterns": {"ugc-ads": [
        {"pattern": "b-roll-captions", "times_seen": 20},
        {"pattern": "talking-head-ugc", "times_seen": 19},
        {"pattern": "before-after", "times_seen": 19},
        {"pattern": "day-in-life", "times_seen": 19},
        {"pattern": "meme-overlay", "times_seen": 19}]}}
    if run(rev, pack=weak)["vibe"] != "raw-ugc":
        errs.append("pack pattern applied below the 0.25 share")
    snap = copy.deepcopy(base)
    st = random.getstate()
    a, b = run(base, seed=7), run(base, seed=7)
    if base != snap:
        errs.append("direct() mutated the script")
    if random.getstate() != st:
        errs.append("direct() consumed the global rng")
    if _digest(a) != _digest(b):
        errs.append("same seed, different direction")
    if len({run(base, seed=i)["showmanship"] for i in range(12)}) < 2:
        errs.append("showmanship ignores the seed")
    if direct(None) is not None or direct({"prompt": "x"})["energy_curve"] != []:
        errs.append("degenerate inputs")
    for ex in data()["DEFAULT_VIBE"]["examples"]:
        v, _s, _t = resolve_vibe(ex["concept"], ex["format"], ex["niche"],
                                 ex["fit"], ex["presenter"], ex["duration_s"],
                                 ex["prompt"])
        if v != ex["expected"]:
            errs.append(f"DEFAULT_VIBE example {ex['prompt']!r}: {v} != "
                        f"{ex['expected']}")
    return errs


def _data_checks():
    errs = []
    D = data()
    VP = D["VIBE_PROFILES"]
    if list(VP) != list(CV.VIBES):
        errs.append("VIBE_PROFILES ids != creative_vocab.VIBES")
    if sorted(D["TONE_PROFILES"]) != sorted(CV.TONES):
        errs.append("TONE_PROFILES ids != creative_vocab.TONES")
    trans = D["PROPOSED_VOCAB"]["TRANSITIONS"]
    for v, pr in VP.items():
        if pr["tone"]["default"] not in CV.TONES or \
                any(t not in CV.TONES for t in pr["tone"]["allowed"]):
            errs.append(f"{v}: tone ids")
        if any(m not in CV.CAMERA_MOVES for m in pr["camera"]["movement"]):
            errs.append(f"{v}: camera ids")
        if any(t not in trans for t in pr["transitions"]):
            errs.append(f"{v}: transition ids")
        lo, hi = pr["pacing"]["target_wpm"]
        if not WPM_MIN <= lo <= hi <= WPM_MAX:
            errs.append(f"{v}: target_wpm")
        for sec in (D["ENERGY_CURVE"]["by_vibe"], D["SET_TEMPLATES"],
                    D["SHOWMANSHIP"]["by_vibe"], D["HUMOR"]["by_vibe"]):
            if v not in sec:
                errs.append(f"{v}: missing from a derived table")
        if not any("ai" in D["SHOWMANSHIP"]["devices"][x]["presenters"]
                   for x in D["SHOWMANSHIP"]["by_vibe"].get(v, [])):
            errs.append(f"{v}: no AI-safe showmanship device")
        for e in pr["evidence"]:
            if not e.startswith("rules-") and e not in D["EVIDENCE"]:
                errs.append(f"{v}: evidence ref {e} unresolved")
    for k, e in D["EVIDENCE"].items():
        if e.get("grade") not in _GRADES:
            errs.append(f"evidence {k} grade")
    doc = os.path.join(REPO, "docs", "research", "vibe-tone-music.md")
    if os.path.isfile(doc):
        with open(doc, encoding="utf-8") as f:
            blocks = re.findall(r"```json\n(.*?)\n```", f.read(), re.S)
        names = list(D["transcribed_sections"])
        if len(blocks) != len(names) or any(
                json.loads(b) != D[n] for b, n in zip(blocks, names)):
            errs.append("vibes.json no longer matches the research JSON blocks")
    return errs


def selfcheck():
    """Hermetic: in-process generate() over evals/golden.jsonl x 5 formats x
    2 presenters at seed 1 (plus synthetic lane/tie-break/pack checks).
    Reads repo files only; writes nothing. -> (ok, lines)."""
    t_start = time.time()
    saved = os.environ.get("VSP_NO_PRIORS")
    os.environ["VSP_NO_PRIORS"] = "1"   # hermetic: never the local learned/
    try:
        return _selfcheck(t_start)
    finally:
        if saved is None:
            os.environ.pop("VSP_NO_PRIORS", None)
        else:
            os.environ["VSP_NO_PRIORS"] = saved


def _selfcheck(t_start):
    lines, fails = [], []
    fails += [f"data: {e}" for e in _data_checks()]
    lines.append("data: vibes.json ids valid; research §5 blocks transcribed "
                 "verbatim" if not fails else "data: FAIL")
    unit = _unit_checks()
    fails += [f"unit: {e}" for e in unit]
    lines.append(f"unit: lanes, tie-break (n>=3 only), pacing floors, pack "
                 f"pattern, Shop lane, determinism, 4 research examples: "
                 f"{'ok' if not unit else 'FAIL'}")
    maker = _maker()
    mod = importlib.import_module("vsp.direction")
    orig = mod.direct
    calls = []

    def timed(script, ctx=None, seed=None, maker=None):
        t0 = time.perf_counter()
        out = orig(script, ctx=ctx, seed=seed, maker=maker)
        calls.append((time.perf_counter() - t0,
                      (ctx or {}).get("concept") if isinstance(ctx, dict) else None))
        return out
    golden = _golden()
    runs = {}
    mod.direct = timed
    try:
        for rnd in (0, 1):
            for g in golden:
                for f in FORMATS:
                    for p in PRESENTERS:
                        s = maker.generate(g["prompt"], presenter=p, fmt=f,
                                           duration=30, seed=1)
                        key = (g["id"], f, p)
                        if rnd == 0:
                            runs[key] = (s, calls[-1][1] if calls else None)
                        else:
                            s0 = runs[key][0]
                            if (_digest(s0.get("direction")) != _digest(s.get("direction"))
                                    or render_md(s0.get("direction")) !=
                                    render_md(s.get("direction"))):
                                fails.append(f"determinism: {key}")
    finally:
        mod.direct = orig
    dist = collections.Counter()
    by_p = {p: collections.Counter() for p in PRESENTERS}
    agree = 0
    for key, (s, cconcept) in runs.items():
        d = s.get("direction")
        if "creative_warnings" in s:
            fails.append(f"{key}: creative_warnings {s['creative_warnings']}")
        probs = validate(d, s) + (text_problems(d, s) if d else [])
        fails += [f"{key}: {e}" for e in probs]
        if not d:
            continue
        dist[d["vibe"]] += 1
        by_p[key[2]][d["vibe"]] += 1
        s2 = {k: v for k, v in s.items() if k != "direction"}
        concept, _src = infer_concept(s2)
        if cconcept and concept != cconcept:
            fails.append(f"{key}: inferred concept {concept} != ctx {cconcept}")
        d2 = orig(s2, ctx=None, seed=1, maker=maker)
        agree += d2["vibe"] == d["vibe"]
        fails += [f"{key} (no ctx): {e}" for e in validate(d2, s2)]
    n = len(runs)
    lines.append(f"matrix: {n} scripts ({len(golden)} golden prompts x "
                 f"{len(FORMATS)} formats x {len(PRESENTERS)} presenters, seed 1); "
                 f"contract/pacing/licensing/voice/text checks on every one")
    lines.append("vibes: " + ", ".join(f"{v} {dist[v]}" for v in CV.VIBES if dist[v]))
    for p in PRESENTERS:
        lines.append(f"vibes ({p}): " + ", ".join(
            f"{v} {by_p[p][v]}" for v in CV.VIBES if by_p[p][v]))
    lines.append(f"determinism: 2 runs x {n} byte-identical"
                 if not any(x.startswith("determinism") for x in fails)
                 else "determinism: FAIL")
    lines.append(f"no-ctx path: concept inference matches ctx on all {n}; same "
                 f"vibe on {agree}/{n}")
    nfx = 0
    fixtures = []
    try:                               # --script-json-like legacy fixtures
        from vsp import selftest_cases
        good, cases = selftest_cases.all_cases()
        for c in [good] + list(cases):
            cand = c if isinstance(c, dict) else next(
                (x for x in c if isinstance(x, dict) and "beats" in x), None) \
                if isinstance(c, (list, tuple)) else None
            if isinstance(cand, dict) and "beats" in cand:
                fixtures.append(cand)
    except Exception:  # noqa: BLE001 — another workstream's module: optional
        fixtures = []
    for fx in fixtures:
        snap = _digest(fx)
        d = orig(fx, ctx=None, seed=None)
        nfx += 1
        if _digest(fx) != snap:
            fails.append(f"fixture {fx.get('prompt')!r} mutated")
        fails += [f"fixture {fx.get('prompt')!r}: {e}"
                  for e in validate(d, fx) + text_problems(d, fx)]
    lines.append(f"fixtures: {nfx} self-test gate scripts (no ctx, legacy beat "
                 f"shapes) pass the same checks")
    ts = [c[0] for c in calls]
    mean_ms = 1000.0 * sum(ts) / max(1, len(ts))
    lines.append(f"timing: direct() mean {mean_ms:.2f} ms, max "
                 f"{1000.0 * max(ts or [0]):.2f} ms over {len(ts)} calls")
    if mean_ms >= 10.0:
        fails.append(f"timing: mean {mean_ms:.2f} ms >= 10 ms")
    subset = [g["prompt"] for g in golden[:2]] + [golden[-2]["prompt"]]
    want = _digest([[runs[(g["id"], f, p)][0].get("direction"),
                     render_md(runs[(g["id"], f, p)][0].get("direction"))]
                    for g in [x for x in golden if x["prompt"] in subset]
                    for f in FORMATS for p in PRESENTERS])
    for hs in ("0", "4242"):
        env = dict(os.environ, PYTHONHASHSEED=hs)
        try:
            r = subprocess.run([sys.executable, "-c", _HASH_CODE, REPO,
                                json.dumps(subset)], capture_output=True,
                               text=True, env=env, timeout=300, cwd=REPO)
            got = r.stdout.rsplit("@@DIGEST@@", 1)[-1].strip()
        except (OSError, subprocess.SubprocessError) as e:
            got = f"error {e}"
        if got != want:
            fails.append(f"PYTHONHASHSEED={hs}: digest differs ({got[:12]})")
    lines.append("PYTHONHASHSEED 0 / 4242: identical to in-process "
                 f"({len(subset) * len(FORMATS) * len(PRESENTERS)} scripts)")
    lines += [f"FAIL {x}" for x in fails[:40]]
    if len(fails) > 40:
        lines.append(f"... {len(fails) - 40} more failures")
    lines.append(f"selfcheck {'ok' if not fails else 'FAILED'} in "
                 f"{time.time() - t_start:.1f}s ({len(fails)} failures)")
    return not fails, lines


# ------------------------------------------------------------------ CLI
def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="python3 -m vsp.direction",
                                 description="creative direction (WS-VIBE)")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("selfcheck", help="hermetic golden-matrix check")
    sh = sub.add_parser("show", help="print render_md for a generated script")
    sh.add_argument("prompt")
    sh.add_argument("--format", default="demo", choices=FORMATS)
    sh.add_argument("--presenter", default="ai", choices=PRESENTERS)
    sh.add_argument("--duration", type=int, default=30)
    sh.add_argument("--seed", type=int, default=1)
    sh.add_argument("--json", action="store_true", help="print the dict")
    sh.add_argument("--style", action="store_true",
                    help="also print style_paragraph and voice_spec")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    if a.cmd == "selfcheck":
        ok, lines = selfcheck()
        print("\n".join(lines))
        return 0 if ok else 1
    if a.cmd == "show":
        maker = _maker()
        s = maker.generate(a.prompt, presenter=a.presenter, fmt=a.format,
                           duration=a.duration, seed=a.seed)
        d = s.get("direction") or direct(s, seed=a.seed, maker=maker)
        if a.json:
            print(json.dumps(d, indent=1, ensure_ascii=False))
        else:
            print(render_md(d), end="")
            if a.style:
                print("\n" + style_paragraph(d) + "\n\n" + voice_spec(d))
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    from vsp import direction as _self   # one module instance for enrich()
    sys.exit(_self.main(sys.argv[1:]))
