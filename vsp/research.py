"""Stage 2 — RESEARCH: load, validate, hash-pin and age-check the research
pack (RULES.md §66 D148), plus the maker<->research niche/hook-family maps.

    load_pack(path=None) -> (pack | None, meta)
        meta = {path, sha256, generated_at, age_hours, stale, errors,
                warnings, schema_version}
        pack is None when the file is absent, unreadable, not JSON, or fails
        validate_pack (errors listed in meta) — a broken pack never feeds the
        maker. Stale (> STALE_HOURS) is a warning, not an error: the pipeline
        decides (--require-fresh-research fails on it).
    validate_pack(pack) -> list[str]   structural errors ([] = valid)
    niche_fresh_lines(pack, maker_niche, k=3)   in-niche, spoken-hook lines
    live_hook_family(pack, maker_niche)         first mappable family in the
                                                niche's WHOLE ranked list
Read-only: nothing here writes the pack (research_bridge.py builds it).
Stdlib only; Python >= 3.9.
"""
import hashlib
import json
import os
import re
from datetime import datetime, timezone

from vsp import config

STALE_HOURS = 48.0
SCHEMA_VERSION = 2          # research_bridge.py writes this; v1 = no field

# Maker niches (viral_script_maker.NICHE_KEYWORDS + "default") -> research-DB
# niche spellings, most specific first. The maker's own niche name is always
# tried last so fixture/hermetic packs (which use maker spellings) resolve.
MAKER_TO_PACK_NICHES = {
    "beauty": ["fashion-beauty"],
    "fitness": ["fitness"],
    "food": ["food"],
    "finance": ["finance"],
    "education": ["ai-education"],
    "automotive": ["automotive-business"],
    "gadgets": ["ugc-ads"],
    "tools": ["ugc-ads"],
    "home": ["ugc-ads", "lifestyle"],
    "wellness": ["ugc-ads", "lifestyle"],
    "pets": ["ugc-ads"],
    "outdoors": ["ugc-ads", "travel"],
    "commentary": ["faceless-truth-teller", "regional-news",
                   "travel-commentary"],
    "default": ["ugc-ads"],
}

# Research-DB hook categories -> viral_script_maker.HOOKS families. Never
# maps to a family whose templates need invented proof ("proof-first": its
# {proof} slot renders '4.9★' / '12,000+ orders' — a D136 violation by
# construction) and never maps bait/absolute categories (comment-bait,
# tag-challenge -> D139; superlative -> D141).
PACK_FAMILY_TO_HOOKS = {
    "curiosity-gap": "curiosity-gap",
    "question": "curiosity-gap",
    "payoff-tease": "curiosity-gap",
    "fomo": "curiosity-gap",
    "unboxing": "curiosity-gap",
    "day-counter": "curiosity-gap",
    "bold-claim": "bold-claim",
    "transformation": "transformation",
    "before-after": "transformation",
    "satisfying-process": "transformation",
    "satisfaction-payoff": "transformation",
    "disgust-reveal": "transformation",
    "grwm-hook": "transformation",
    "story-time": "story-time",
    "pov": "story-time",
    "relatable": "story-time",
    "relatable-realness": "story-time",
    "gym-relatable": "story-time",
    "money-origin": "story-time",
    "what-i-eat": "story-time",
    "controversy": "contrarian-reframe",
    "loophole-tip": "contrarian-reframe",
    "problem-solution": "negative-command",
    "tease-command": "negative-command",
}
NEVER_FAMILIES = {"proof-first"}          # need invented receipts (D136)
# first-person-anecdote families: an AI persona would voice lived experience
# (D137) — skipped when the caller says presenter="ai"
AI_UNSAFE_FAMILIES = {"story-time", "identity-reveal"}
_FALLBACK_HOOK_FAMILIES = ("curiosity-gap", "bold-claim", "negative-command",
                           "proof-first", "transformation", "story-time",
                           "contrarian-reframe", "identity-reveal")

_NULL_LIKE = {"", "none", "null", "nil", "n/a", "na", "unknown", "-", "--",
              "tbd", "?", "(none)", "no hook", "nan"}
# annotator descriptions of a visual/format, not a spoken hook line
_VISUAL_DESC = re.compile(
    r"\b(?:visual|text-only|teaser|skit|backdrop|b-roll|montage|footage|"
    r"animated|animation|silent|music only|no dialogue|voiceover|"
    r"caption-only|on-screen text|shot of|clip of|video of|two-part|"
    r"low-effort|character skit|compilation|slideshow)\b", re.I)


# ------------------------------------------------------------------ load
def _parse_iso(value):
    if not isinstance(value, str) or not value.strip():
        return None
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        try:
            dt = datetime.strptime(v[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def load_pack(path=None, now=None):
    """-> (pack | None, meta). Never raises on a bad file."""
    p = path or config.research_pack_path()
    meta = {"path": os.path.abspath(p), "sha256": None, "generated_at": None,
            "age_hours": None, "stale": None, "errors": [], "warnings": [],
            "schema_version": None}
    if not os.path.isfile(p):
        meta["errors"].append(f"research pack not found: {p}")
        return None, meta
    try:
        with open(p, "rb") as f:
            raw = f.read()
    except OSError as e:
        meta["errors"].append(f"research pack unreadable: {e}")
        return None, meta
    meta["sha256"] = hashlib.sha256(raw).hexdigest()
    try:
        pack = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        meta["errors"].append(f"research pack is not valid JSON: {e}")
        return None, meta
    errs = validate_pack(pack)
    if not isinstance(pack, dict):
        meta["errors"] += errs
        return None, meta
    meta["generated_at"] = pack.get("generated_at")
    meta["schema_version"] = pack.get("schema_version", 1)
    dt = _parse_iso(pack.get("generated_at"))
    now = now or datetime.now(timezone.utc)
    if dt is not None:
        age = (now - dt).total_seconds() / 3600.0
        meta["age_hours"] = round(age, 2)
        meta["stale"] = age > STALE_HOURS
        if age < -1.0:
            meta["warnings"].append(
                f"generated_at is {-age:.1f} h in the future — clock skew?")
    else:
        meta["stale"] = True          # unknown age is never "fresh"
    if meta["stale"]:
        meta["warnings"].append(
            f"research pack is stale (age {meta['age_hours']} h > "
            f"{STALE_HOURS:g} h)" if meta["age_hours"] is not None else
            "research pack age unknown — treated as stale")
    if not pack.get("reels_total"):
        meta["warnings"].append("research pack has no reels (reels_total 0) — "
                                "built without the research DB")
    meta["errors"] += errs
    if errs:
        return None, meta
    return pack, meta


# -------------------------------------------------------------- validate
def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _check_ranked(errs, where, lst, key):
    if not isinstance(lst, list):
        errs.append(f"{where} must be a list")
        return
    for i, row in enumerate(lst):
        if not isinstance(row, dict):
            errs.append(f"{where}[{i}] must be an object")
        elif not isinstance(row.get(key), str) or not row.get(key):
            errs.append(f"{where}[{i}].{key} must be a non-empty string")
        elif row.get("times_seen") is not None and not _is_num(row["times_seen"]):
            errs.append(f"{where}[{i}].times_seen must be a number")


def validate_pack(pack):
    """Structural validation (v1 and v2 packs). Returns error strings."""
    if not isinstance(pack, dict):
        return [f"research pack must be a JSON object, got {type(pack).__name__}"]
    errs = []
    if _parse_iso(pack.get("generated_at")) is None:
        errs.append("generated_at missing or not ISO-8601")
    if "reels_total" not in pack:
        errs.append("reels_total missing")
    elif not isinstance(pack["reels_total"], int) or isinstance(pack["reels_total"], bool) \
            or pack["reels_total"] < 0:
        errs.append("reels_total must be a non-negative integer")
    if "reels_analyzed_last_7d" in pack and not (
            isinstance(pack["reels_analyzed_last_7d"], int)
            and pack["reels_analyzed_last_7d"] >= 0):
        errs.append("reels_analyzed_last_7d must be a non-negative integer")
    if "sources" in pack and not isinstance(pack["sources"], dict):
        errs.append("sources must be an object")
    sv = pack.get("schema_version", 1)
    if not isinstance(sv, int) or isinstance(sv, bool) or not 1 <= sv <= SCHEMA_VERSION:
        errs.append(f"schema_version {sv!r} unsupported (1..{SCHEMA_VERSION})")
    if "top_hooks" in pack:
        _check_ranked(errs, "top_hooks", pack["top_hooks"], "category")
    if "top_patterns" in pack:
        _check_ranked(errs, "top_patterns", pack["top_patterns"], "pattern")
    nh = pack.get("niche_hooks")
    if nh is not None:
        if not isinstance(nh, dict):
            errs.append("niche_hooks must be an object")
        else:
            for n, lst in nh.items():
                _check_ranked(errs, f"niche_hooks[{n!r}]", lst, "category")
    fl = pack.get("fresh_hook_lines")
    if fl is not None:
        if not isinstance(fl, list):
            errs.append("fresh_hook_lines must be a list")
        else:
            for i, row in enumerate(fl):
                if not isinstance(row, dict):
                    errs.append(f"fresh_hook_lines[{i}] must be an object")
                elif row.get("hook") is not None and not isinstance(row["hook"], str):
                    errs.append(f"fresh_hook_lines[{i}].hook must be a string")
    vr = pack.get("verified_rules")
    if vr is not None:
        if not isinstance(vr, list):
            errs.append("verified_rules must be a list")
        else:
            for i, row in enumerate(vr):
                if not isinstance(row, dict) or not isinstance(row.get("rule"), str):
                    errs.append(f"verified_rules[{i}] must be an object with a "
                                f"string 'rule'")
    nm = pack.get("niche_map")
    if nm is not None:
        if not isinstance(nm, dict) or not all(
                isinstance(v, list) and all(isinstance(x, str) for x in v)
                for v in nm.values()):
            errs.append("niche_map must map maker niche -> list of pack niches")
    return errs


# ------------------------------------------------------------ niche maps
def pack_niches_for(maker_niche, pack=None):
    """Research-niche spellings to try for a maker niche, in order. A v2
    pack's own niche_map wins; the maker's niche name is always last."""
    order = []
    nm = (pack or {}).get("niche_map") if isinstance(pack, dict) else None
    if isinstance(nm, dict) and isinstance(nm.get(maker_niche), list):
        order += [n for n in nm[maker_niche] if isinstance(n, str)]
    order += MAKER_TO_PACK_NICHES.get(maker_niche, [])
    order.append(maker_niche)
    out = []
    for n in order:
        if n and n not in out:
            out.append(n)
    return out


def pack_to_maker_niches():
    """Inverse map: research niche -> maker niches that list it."""
    inv = {}
    for mk, lst in MAKER_TO_PACK_NICHES.items():
        for pn in lst:
            inv.setdefault(pn, []).append(mk)
    return inv


def build_niche_map(pack_niches):
    """maker niche -> the research niches present in `pack_niches` (what
    research_bridge.py stores as the pack's "niche_map")."""
    present = set(pack_niches)
    return {mk: [n for n in pack_niches_for(mk) if n in present]
            for mk in MAKER_TO_PACK_NICHES}


def maker_hook_families():
    """viral_script_maker.HOOKS keys (read lazily from the maker; static
    fallback if it cannot be imported)."""
    try:
        import viral_script_maker as vsm
        keys = tuple(vsm.HOOKS.keys())
        if keys:
            return keys
    except Exception:  # noqa: BLE001 — maker unavailable: static copy
        pass
    return _FALLBACK_HOOK_FAMILIES


def map_family(category, families=None):
    """Research hook category -> maker HOOKS family, or None."""
    fams = families or maker_hook_families()
    c = (category or "").strip().lower()
    fam = PACK_FAMILY_TO_HOOKS.get(c) or (c if c in fams else None)
    if fam in NEVER_FAMILIES or fam not in fams:
        return None
    return fam


def live_hook_source(pack, maker_niche, presenter=None, min_seen=0):
    """Provenance of the live hook family: walks every mapped research niche
    and the WHOLE ranked list of each (not just [0]) and returns the first
    category that maps to a usable maker family:
        {family, pack_niche, category, rank, times_seen} | None
    presenter="ai" skips first-person-anecdote families (D137); min_seen
    skips categories seen fewer times (thin evidence)."""
    if not isinstance(pack, dict):
        return None
    nh = pack.get("niche_hooks")
    if not isinstance(nh, dict):
        return None
    fams = maker_hook_families()
    for pn in pack_niches_for(maker_niche, pack):
        ranked = nh.get(pn)
        if not isinstance(ranked, list):
            continue
        rows = [r for r in ranked if isinstance(r, dict)]
        rows = sorted(enumerate(rows), key=lambda ir: (
            -(ir[1].get("times_seen") or 0) if _is_num(ir[1].get("times_seen"))
            else 0, ir[0]))
        for rank, (_, row) in enumerate(rows):
            fam = map_family(row.get("category"), fams)
            if fam is None:
                continue
            seen_n = row.get("times_seen")
            if min_seen and not (_is_num(seen_n) and seen_n >= min_seen):
                continue
            if presenter == "ai" and fam in AI_UNSAFE_FAMILIES:
                continue
            return {"family": fam, "pack_niche": pn,
                    "category": row.get("category"), "rank": rank,
                    "times_seen": row.get("times_seen")}
    return None


def live_hook_family(pack, maker_niche, presenter=None, min_seen=0):
    """The live hook family for a maker niche (see live_hook_source)."""
    src = live_hook_source(pack, maker_niche, presenter=presenter,
                           min_seen=min_seen)
    return src["family"] if src else None


# ------------------------------------------------------------ fresh lines
def is_spoken_hook_line(text):
    """False for null-likes and annotator notes: parentheticals/brackets,
    visual/format descriptions ("(visual open, playground backdrop)",
    "text-only teaser for car argument", "rustic kitchen character skit")."""
    if not isinstance(text, str):
        return False
    t = " ".join(text.split())
    if t.strip(" .…").lower() in _NULL_LIKE:
        return False
    if re.search(r"[()\[\]]", t):
        return False
    if _VISUAL_DESC.search(t):
        return False
    return len(re.findall(r"[A-Za-z0-9']+", t)) >= 2


def niche_fresh_lines(pack, maker_niche, k=3):
    """Up to k fresh hook lines from the maker niche's research niches (in
    map order), dropping annotator descriptions and null-likes, deduped.
    Returns copies of the pack entries (hook/niche/account/... preserved)."""
    if not isinstance(pack, dict) or k <= 0:
        return []
    rows = [r for r in (pack.get("fresh_hook_lines") or [])
            if isinstance(r, dict)]
    out, seen = [], set()
    for pn in pack_niches_for(maker_niche, pack):
        for r in rows:
            if r.get("niche") != pn or not is_spoken_hook_line(r.get("hook")):
                continue
            key = " ".join(r["hook"].lower().split())
            if key in seen:
                continue
            seen.add(key)
            out.append(dict(r))
            if len(out) >= k:
                return out
    return out
