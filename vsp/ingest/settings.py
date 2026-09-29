"""config/ingest.json — what vsp.ingest watches (template:
config/ingest.example.json; path override VSP_INGEST_CONFIG).

    load(path=None, required=True) -> cfg     defaults merged in; raises
                                              ConfigError listing every problem
    validate(cfg) -> [errors]
    hashtag_plan(cfg, niche=None) -> [(niche, tag)]
    watchlist(cfg, niche=None)    -> [(niche, handle)]
    tag_niche_map(cfg)            -> {tag: niche}  (query tags + explicit map)
    niche_for_tags(tags, cfg)     -> niche | None  (first mapped caption tag)

Niches use the maker's names. Hashtag Search allows 30 unique hashtags per
account per rolling 7 days (research doc §2), so the config holds at most 3
per niche and 25 in total — the budget keeps 5 spare for rotations and
manual use (§9 Job A.1).
"""
import copy
import json
import os
import re

from vsp import config

MAKER_NICHES = ("gadgets", "tools", "beauty", "wellness", "automotive", "pets",
                "home", "outdoors", "fitness", "food", "finance", "education",
                "commentary")
MAX_TAGS_PER_NICHE = 3
MAX_TAGS_TOTAL = 25
PLATFORM_HASHTAG_CAP = 30

DEFAULTS = {
    "schema_version": 1,
    "graph_version": None,            # None -> VSP_IG_GRAPH_VERSION or v26.0
    "niches": {},
    "hashtag_niche_map": {},
    "budget": {"max_active_hashtags": MAX_TAGS_TOTAL},
    "fetch": {
        "page_limit": 50,             # Hashtag Search max per page
        "top_pages": 2,               # §9 Job A.2: at most 2 pages
        "recent_pages": 1,
        "watchlist_media_limit": 25,
        "watchlist_pages": 1,
        "watchlist_min_hours": 20,    # once per handle per day
        "own_pages": 10,
        "max_age_days": {"hashtag": 7, "watchlist": 30},
        "retention_days": 30,         # others' media: purge_after = last seen + N
    },
    "classify": {"llm": "auto", "llm_max_calls": 50},
    "transcribe": {"enabled": False, "seconds": 3.5, "max_per_run": 20,
                   "keywords": [], "sources": ["own_render", "media_url"]},
    "vendor_rows": "include",         # include | exclude  (research doc §7)
}

_TAG_RE = re.compile(r"^[^\W_][\w]{0,99}$")
_HANDLE_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")


class ConfigError(ValueError):
    def __init__(self, problems, path=None):
        self.problems = list(problems)
        self.path = path
        super().__init__("; ".join(self.problems))


def config_path(path=None):
    return path or config.ingest_config_path()


def example_path():
    return os.path.join(config.REPO, "config", "ingest.example.json")


def norm_tag(tag):
    """'#SkinCare' -> 'skincare'; ValueError if not a valid hashtag."""
    t = str(tag or "").strip().lstrip("#").strip().lower()
    if not _TAG_RE.match(t) or t.isdigit():
        raise ValueError(f"invalid hashtag {tag!r} (letters, digits, underscores; "
                         f"not all digits)")
    return t


def norm_handle(handle):
    h = str(handle or "").strip().lstrip("@").strip()
    if not _HANDLE_RE.match(h):
        raise ValueError(f"invalid Instagram handle {handle!r} "
                         f"(1-30 letters, digits, '.', '_')")
    return h


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if k.startswith("_"):
            continue                  # "_comment" keys in the template
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def validate(cfg):
    errs = []
    niches = cfg.get("niches")
    if not isinstance(niches, dict):
        return ["'niches' must be an object: niche -> {hashtags, handles}"]
    seen_tags = {}
    for niche, spec in niches.items():
        if niche.startswith("_"):
            continue
        if niche not in MAKER_NICHES:
            errs.append(f"unknown niche {niche!r} — use the maker's niche names: "
                        + ", ".join(MAKER_NICHES))
        if not isinstance(spec, dict):
            errs.append(f"niches.{niche} must be an object")
            continue
        tags = spec.get("hashtags") or []
        if not isinstance(tags, list):
            errs.append(f"niches.{niche}.hashtags must be a list")
            tags = []
        if len(tags) > MAX_TAGS_PER_NICHE:
            errs.append(f"niches.{niche}: {len(tags)} hashtags (max "
                        f"{MAX_TAGS_PER_NICHE} per niche)")
        for t in tags:
            try:
                nt = norm_tag(t)
            except ValueError as e:
                errs.append(f"niches.{niche}: {e}")
                continue
            if nt in seen_tags and seen_tags[nt] != niche:
                errs.append(f"#{nt} listed under both {seen_tags[nt]} and {niche}")
            seen_tags[nt] = niche
        handles = spec.get("handles") or []
        if not isinstance(handles, list):
            errs.append(f"niches.{niche}.handles must be a list")
            handles = []
        for h in handles:
            try:
                norm_handle(h)
            except ValueError as e:
                errs.append(f"niches.{niche}: {e}")
    if len(seen_tags) > MAX_TAGS_TOTAL:
        errs.append(f"{len(seen_tags)} unique hashtags configured (max "
                    f"{MAX_TAGS_TOTAL}; Instagram allows {PLATFORM_HASHTAG_CAP} "
                    f"per rolling 7 days and the budget keeps spares)")
    tmap = cfg.get("hashtag_niche_map") or {}
    if not isinstance(tmap, dict):
        errs.append("'hashtag_niche_map' must map hashtag -> niche")
    else:
        for t, n in tmap.items():
            if t.startswith("_"):
                continue
            try:
                norm_tag(t)
            except ValueError as e:
                errs.append(f"hashtag_niche_map: {e}")
            if n not in MAKER_NICHES:
                errs.append(f"hashtag_niche_map[{t!r}]: unknown niche {n!r}")
    b = cfg.get("budget") or {}
    mx = b.get("max_active_hashtags", MAX_TAGS_TOTAL)
    if not isinstance(mx, int) or isinstance(mx, bool) or not 1 <= mx <= PLATFORM_HASHTAG_CAP:
        errs.append(f"budget.max_active_hashtags must be 1..{PLATFORM_HASHTAG_CAP}")
    if str(cfg.get("vendor_rows", "include")).lower() not in ("include", "exclude"):
        errs.append("vendor_rows must be 'include' or 'exclude'")
    gv = cfg.get("graph_version")
    if gv is not None and not re.fullmatch(r"v\d+\.\d+", str(gv)):
        errs.append(f"graph_version {gv!r} must look like v26.0")
    return errs


def load(path=None, required=True):
    """Config merged over DEFAULTS. required=False returns DEFAULTS (with
    cfg['_missing'] = path) when the file is absent."""
    p = config_path(path)
    if not os.path.isfile(p):
        if required:
            raise ConfigError([
                f"ingest config not found: {p}. Copy the template: "
                f"`cp config/ingest.example.json config/ingest.json`, then edit "
                f"niches/hashtags/handles (or set VSP_INGEST_CONFIG)"], p)
        cfg = copy.deepcopy(DEFAULTS)
        cfg["_missing"] = p
        return cfg
    try:
        with open(p, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError) as e:
        raise ConfigError([f"ingest config {p} is not valid JSON: {e}"], p)
    if not isinstance(raw, dict):
        raise ConfigError([f"ingest config {p} must be a JSON object"], p)
    cfg = _merge(DEFAULTS, raw)
    errs = validate(cfg)
    if errs:
        raise ConfigError(errs, p)
    cfg["_path"] = p
    return cfg


def hashtag_plan(cfg, niche=None):
    out = []
    for n, spec in (cfg.get("niches") or {}).items():
        if n.startswith("_") or (niche and n != niche):
            continue
        for t in (spec or {}).get("hashtags") or []:
            out.append((n, norm_tag(t)))
    return out


def watchlist(cfg, niche=None):
    out = []
    for n, spec in (cfg.get("niches") or {}).items():
        if n.startswith("_") or (niche and n != niche):
            continue
        for h in (spec or {}).get("handles") or []:
            out.append((n, norm_handle(h)))
    return out


def tag_niche_map(cfg):
    m = {}
    for t, n in (cfg.get("hashtag_niche_map") or {}).items():
        if not t.startswith("_"):
            try:
                m[norm_tag(t)] = n
            except ValueError:
                pass
    for n, t in hashtag_plan(cfg):
        m[t] = n                      # a query tag always maps to its niche
    return m


def niche_for_tags(tags, cfg):
    m = tag_niche_map(cfg)
    for t in tags or []:
        try:
            n = m.get(norm_tag(t))
        except ValueError:
            continue
        if n:
            return n
    return None


def caption_tags(caption):
    return re.findall(r"#(\w+)", caption or "")


def get(cfg, dotted, default=None):
    cur = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur
