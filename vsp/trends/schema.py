"""Record schemas (v1) of the trend dataset, their validation and the JSON
Schema files in trends-db-template/schema/ (generated from the specs here,
so the two can never drift — the selfcheck compares them).

    normalize_observation(raw, now=None) -> (record, errors)
        flat aliases -> nested fields, type coercion (CSV strings), defaults
        (post_id from the permalink, obs_id, observed_at, analyst,
        creator.tier, trend_keys, retention), then validate(). `record` is
        the full canonical form (every field present, None when unknown).
    normalize_creator(raw, now=None) / normalize_signal(raw, now=None)
    validate(record, spec=OBSERVATION, now=None) -> [errors]
    json_schema(name) -> dict       observation | creator | signal | trend | recipe
    obs_id(platform, post_id)       sha1("<platform>:<post_id>")[:16]
    canonical_post_id(platform, permalink, post_id=None)
    norm_trend_key(key) / derive_trend_keys(record)
    tier_for(followers)             emerging | nano | micro | mid | macro | mega
    compact(record) / expand(record, spec)   on-disk (nulls dropped) <-> full

Validation REJECTS (the text itself is never altered): missing required
fields, bad enums (creative-vocab ids for hook.archetype, hook.frame0_visual,
vibe), hook.first_words over 12 words, hook.on_screen_text over 8 words,
notes over 280 chars, media/CDN URLs anywhere in a record (cdninstagram,
fbcdn, tiktokcdn, googlevideo, ytimg, twimg, pinimg, .mp4 / .mov / ...),
instruction-like text in any free-text field ("ignore previous ...", a
line starting "system:", chat-template tokens — reel text is data, never
instructions: AGENTS.md rule 8), timestamps in the future, non-https or
off-platform permalinks, and unknown fields. A whole `caption` is an
unknown field on purpose: captions are summarised as a <= 12-word
hook.first_words excerpt plus our own analysis, never stored whole.
"""
import hashlib
import re
import unicodedata
from datetime import datetime, timedelta, timezone

from vsp import creative_vocab as CV
from vsp.router import FORMATS, PRESENTERS

SCHEMA_VERSION = 1

PLATFORMS = ("instagram", "tiktok", "youtube", "pinterest", "x", "other")
SOURCES = ("ig_graph_hashtag", "ig_graph_bd", "yt_data_api",
           "tiktok_creative_center", "agent_observed", "user_shared", "import")
ANALYSTS = ("api", "agent", "human")
DEFAULT_ANALYST = {"ig_graph_hashtag": "api", "ig_graph_bd": "api",
                   "yt_data_api": "api", "tiktok_creative_center": "agent",
                   "agent_observed": "agent", "user_shared": "human",
                   "import": "human"}
AUDIO_TYPES = ("trending_sound", "original_voiceover", "original_sound",
               "licensed_music", "none")
PARTICIPATION = ("duet", "stitch", "template", "challenge", "comment_prompt", "none")
CTAS = ("comment_keyword", "follow", "link_in_bio", "save", "share", "none", "other")
EMOTIONS = ("awe", "humor", "surprise", "relatable", "aspirational", "curiosity",
            "satisfaction", "nostalgia", "outrage", "fear", "tension", "other")
PRODUCTION_COSTS = ("low", "med", "high")
TIERS = ("emerging", "nano", "micro", "mid", "macro", "mega")
SMALL_MEDIUM_TIERS = ("emerging", "nano", "micro", "mid")
TREND_KINDS = ("sound", "format", "tag", "topic")
SIGNAL_KINDS = ("tag", "sound")
STAGES = ("emerging", "rising", "peak", "saturated", "declining", "steady")
SPEEDS = ("moment", "signal", "force")
BANDS = ("normal", "notable", "outlier", "breakout", "mega", "unscored")
OPERATORS = ("ride", "transplant", "combine", "substitute", "reverse", "serialize",
             "constrain", "escalate", "mashup", "invent")
RECIPE_STAGES = STAGES + ("outlier", "invented")
DURATIONS = (15, 30, 45, 60)

HOOK_ARCHETYPE_IDS = tuple(CV.HOOK_ARCHETYPES)
VISUAL_TYPE_IDS = tuple(CV.VISUAL_TYPES)
VIBE_IDS = tuple(CV.VIBES)

# D163: trend data compliance — permalinks + public metrics + a <=12-word
# hook excerpt + own analysis; never media, CDN URLs or whole captions
MAX_FIRST_WORDS = 12
MAX_ON_SCREEN_WORDS = 8
MAX_NOTES = 280
FUTURE_TOLERANCE = timedelta(minutes=15)      # clock skew allowance
YT_RETENTION_DAYS = 30                        # YouTube API policy: refresh or delete

# Noise hashtags: carry no trend information (every post uses them).
GENERIC_TAGS = frozenset("""fyp foryou foryoupage fy viral viralvideo viralreels
trending trend reels reel reelsinstagram shorts short youtubeshorts ytshorts
explore explorepage instagood instagram tiktok xyzbca capcut""".split())

# Maker niche names for the research-DB spellings with a unique mapping.
RESEARCH_NICHES = {"fashion-beauty": "beauty", "automotive-business": "automotive",
                   "ai-education": "education", "travel": "outdoors",
                   "faceless-truth-teller": "commentary"}

_SLUG = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
_TREND_KEY = r"^(?:sound|format|tag|topic):[a-z0-9][a-z0-9._-]{0,63}$"
_HANDLE = r"^(?:[a-z0-9._-]{1,64}|channel/[A-Za-z0-9_-]{8,64})$"
_ISO = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
_DATE = r"^\d{4}-\d{2}-\d{2}$"
_HEX16 = r"^[0-9a-f]{16}$"


def _words_pattern(n):
    return r"^\s*\S+(?:\s+\S+){0,%d}\s*$" % (n - 1)


# ------------------------------------------------------------------ specs
def F(type_, required=False, enum=None, desc="", **kw):
    """One field spec. type_: str | slug | url | datetime | date | int |
    number | bool | trend_key | list (items=spec) | object (fields={})."""
    d = {"type": type_, "required": bool(required), "desc": desc}
    if enum is not None:
        d["enum"] = tuple(enum)
    d.update(kw)
    return d


def _nums(desc):
    return F("int", minimum=0, desc=desc)


OBSERVATION = {
    "schema_version": F("int", True, (SCHEMA_VERSION,), "record schema version"),
    "obs_id": F("str", True, pattern=_HEX16,
                desc="sha1('<platform>:<post_id>') first 16 hex chars"),
    "platform": F("str", True, PLATFORMS),
    "post_id": F("str", True, max_len=128,
                 desc="platform post id (Instagram: the shortcode; derived from "
                      "the permalink when possible)"),
    "permalink": F("url", True, desc="https post page URL, never a media/CDN URL"),
    "observed_at": F("datetime", True, desc="when the metrics were observed (UTC)"),
    "posted_at": F("datetime", desc="when the post was published (UTC)"),
    "source": F("str", True, SOURCES),
    "analyst": F("str", True, ANALYSTS, "who filled the analysis fields"),
    "creator": F("object", fields={
        "handle": F("str", pattern=_HANDLE, desc="lower-case handle without @ "
                    "(YouTube without a custom URL: channel/<id>)"),
        "followers": _nums("followers / subscribers at observed_at"),
        "median_views_recent": _nums("median views of the creator's recent posts "
                                     "(>= 5 posts, each older than 7 days)"),
        "baseline_n": _nums("posts in that median"),
        "tier": F("str", enum=TIERS, desc="from followers (filled)"),
    }),
    "metrics": F("object", fields={
        "views": _nums("views / plays"), "likes": _nums("likes"),
        "comments": _nums("comments"), "shares": _nums("shares"),
        "saves": _nums("saves")}),
    "niche": F("slug", max_len=40, desc="maker niche (vsp.router names)"),
    "topic": F("str", max_len=60, free_text=True, desc="short topic label"),
    "language": F("str", pattern=r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$"),
    "region": F("str", pattern=r"^(?:[A-Z]{2}|global)$"),
    "duration_s": F("number", minimum=0, maximum=3600),
    "hook": F("object", fields={
        "first_words": F("str", max_words=MAX_FIRST_WORDS, max_len=160, free_text=True,
                         desc="<= 12-word excerpt of the spoken/caption hook"),
        "archetype": F("str", enum=HOOK_ARCHETYPE_IDS, desc="creative_vocab.HOOK_ARCHETYPES id"),
        "frame0_visual": F("str", enum=VISUAL_TYPE_IDS, desc="creative_vocab.VISUAL_TYPES id"),
        "on_screen_text": F("str", max_words=MAX_ON_SCREEN_WORDS, max_len=100,
                            free_text=True, desc="<= 8 words of frame-0 overlay text"),
    }),
    "structure": F("object", fields={
        "beats": F("list", items=F("str", max_len=40, free_text=True), max_items=12,
                   desc="short beat labels in order"),
        "cuts_per_10s": F("number", minimum=0, maximum=40),
        "payoff_reveal": F("bool"), "loop": F("bool"), "series": F("bool"),
    }),
    "audio": F("object", fields={
        "type": F("str", enum=AUDIO_TYPES),
        "sound_id": F("str", pattern=r"^[A-Za-z0-9._:-]{1,64}$"),
        "sound_title": F("str", max_len=100, free_text=True),
    }),
    "format_key": F("slug", max_len=48, desc="reusable template slug, e.g. pov-reveal"),
    "participation": F("str", enum=PARTICIPATION),
    "cta": F("str", enum=CTAS),
    "emotion": F("str", enum=EMOTIONS),
    "vibe": F("str", enum=VIBE_IDS, desc="creative_vocab.VIBES id"),
    "replicability": F("int", minimum=1, maximum=5, desc="1 = hard to copy, 5 = anyone"),
    "production_cost": F("str", enum=PRODUCTION_COSTS),
    "needs_real_person": F("bool", desc="dance, face reaction, real-person challenge"),
    "trend_keys": F("list", items=F("trend_key"), max_items=20,
                    desc="sound:<id> format:<slug> tag:<hashtag> topic:<slug>"),
    "notes": F("str", max_len=MAX_NOTES, free_text=True, desc="our own analysis"),
    "retention": F("object", fields={
        "purge_after": F("datetime", future_ok=True,
                         desc="delete after (yt_data_api: observed_at + 30 days)")}),
}

CREATOR = {
    "schema_version": F("int", True, (SCHEMA_VERSION,)),
    "platform": F("str", True, PLATFORMS),
    "handle": F("str", True, pattern=_HANDLE),
    "followers": _nums("followers / subscribers"),
    "median_views_recent": _nums("median views, recent posts older than 7 days"),
    "baseline_n": _nums("posts in the median (>= 5 to be used)"),
    "tier": F("str", enum=TIERS),
    "snapshot_at": F("datetime", True),
    "source": F("str", True, SOURCES),
    "retention": F("object", fields={"purge_after": F("datetime", future_ok=True)}),
}

SIGNAL = {
    "schema_version": F("int", True, (SCHEMA_VERSION,)),
    "signal_id": F("str", True, pattern=_HEX16,
                   desc="sha1('<platform>:<key>:<region>:<industry>:<date>')[:16]"),
    "platform": F("str", True, PLATFORMS),
    "source": F("str", True, SOURCES),
    "kind": F("str", True, SIGNAL_KINDS),
    "key": F("trend_key", True),
    "name": F("str", True, max_len=80, free_text=True, desc="hashtag or song as listed"),
    "rank": F("int", minimum=1, maximum=10000),
    "posts": _nums("posts using it (aggregate, as listed)"),
    "growth_pct": F("number", minimum=-100, maximum=1000000),
    "region": F("str", pattern=r"^(?:[A-Z]{2}|global)$"),
    "industry": F("str", max_len=60, free_text=True),
    "date": F("date", True, desc="the list's date"),
    "observed_at": F("datetime", True),
    "retention": F("object", fields={"purge_after": F("datetime", future_ok=True)}),
}

TREND = {
    "key": F("trend_key", True), "kind": F("str", True, TREND_KINDS),
    "label": F("str", True, max_len=120),
    "first_seen": F("date", True), "last_seen": F("date", True),
    "span_days": F("int", True, minimum=0),
    "creators_total": F("int", True, minimum=2),
    "creators_7d": F("int", True, minimum=0), "creators_prev7d": F("int", True, minimum=0),
    "creators_3d": F("int", True, minimum=0),
    "growth": F("number", True, minimum=0),
    "median_outlier_x": F("number", minimum=0,
                          desc="median views / creator median (median basis only)"),
    "median_multiple": F("number", minimum=0, desc="median multiple, any basis"),
    "small_medium_share": F("number", minimum=0, maximum=1),
    "platforms": F("list", True, items=F("str", enum=PLATFORMS)),
    "niches": F("list", True, items=F("slug")),
    "examples": F("list", True, items=F("str", pattern=_HEX16), max_items=5),
    "stage": F("str", True, STAGES), "speed": F("str", True, SPEEDS),
    "evergreen": F("bool", True), "jump_in": F("str", True, max_len=200),
    "evidence_score": F("number", True, minimum=0),
    "profile": F("object", True, fields={
        "format_key": F("slug"), "archetype": F("str", enum=HOOK_ARCHETYPE_IDS),
        "archetypes": F("list", items=F("str", enum=HOOK_ARCHETYPE_IDS)),
        "frame0_visual": F("str", enum=VISUAL_TYPE_IDS),
        "emotion": F("str", enum=EMOTIONS), "participation": F("str", enum=PARTICIPATION),
        "cta": F("str", enum=CTAS), "audio_type": F("str", enum=AUDIO_TYPES),
        "sound_title": F("str", max_len=100), "vibe": F("str", enum=VIBE_IDS),
        "replicability": F("number", minimum=1, maximum=5),
        "production_cost": F("str", enum=PRODUCTION_COSTS),
        "needs_real_person": F("bool", True), "duration_s": F("number", minimum=0),
        "cuts_per_10s": F("number", minimum=0), "payoff_reveal": F("bool", True),
        "loop": F("bool", True), "series": F("bool", True),
        "beats": F("list", items=F("str", max_len=40), max_items=8),
        "tags": F("list", items=F("str"), max_items=5)}),
    "related": F("list", items=F("trend_key"), max_items=6,
                 desc="keys whose posts overlap >= 80%: the same trend's other elements"),
    "signals": F("object", fields={
        "best_rank": F("int", minimum=1), "posts": F("int", minimum=0),
        "growth_pct": F("number"), "regions": F("list", items=F("str")),
        "dates": F("list", items=F("date")), "source": F("str", enum=SOURCES)}),
}

RECIPE = {
    "schema_version": F("int", True, (SCHEMA_VERSION,)),
    "recipe_id": F("str", True, pattern=r"^rcp-\d{8}-\d{2,3}$"),
    "date": F("date", True), "created_at": F("datetime", True),
    "operator": F("str", True, OPERATORS),
    "title": F("str", True, max_len=160), "rationale": F("str", True, max_len=320),
    "niche": F("slug", True), "lanes": F("list", True, items=F("str", enum=PRESENTERS),
                                         min_items=1, desc="feasible presenter lanes"),
    "trend_keys": F("list", True, items=F("trend_key"), max_items=10),
    "stage": F("str", True, RECIPE_STAGES), "speed": F("str", enum=SPEEDS),
    "score": F("number", True, minimum=0, maximum=1),
    "score_parts": F("object", True, fields={
        k: F("number", True, minimum=0, maximum=1)
        for k in ("evidence", "velocity", "novelty", "feasibility")}),
    "hook_archetypes": F("list", True, items=F("str", enum=HOOK_ARCHETYPE_IDS),
                         max_items=4, desc="ordered; empty = no hook steering"),
    "frame0_visual_type": F("str", enum=VISUAL_TYPE_IDS),
    "vibe": F("str", enum=VIBE_IDS), "format": F("str", enum=FORMATS),
    "duration_s": F("int", enum=DURATIONS),
    "beats_note": F("str", True, max_len=400), "audio_note": F("str", True, max_len=400),
    "text_note": F("str", True, max_len=400),
    "participation_note": F("str", True, max_len=400),
    "originality": F("list", True, items=F("str", max_len=220), min_items=2, max_items=8),
    "evidence": F("list", True, max_items=6, items=F("object", fields={
        "permalink": F("url", True), "platform": F("str", True, PLATFORMS),
        "tier": F("str", enum=TIERS), "outlier_x": F("number", minimum=0),
        "band": F("str", enum=BANDS)})),
    "risk": F("list", True, items=F("str", max_len=220), max_items=10),
    "needs_real_person": F("bool", True),
    "fingerprint": F("str", True, pattern=_HEX16),
    "tokens": F("list", True, items=F("str", max_len=80), min_items=1, max_items=40,
                desc="novelty tokens (compared with used recipes)"),
    "invent": F("object", fields={
        "signature": F("object", True, fields={
            "name": F("str", True, max_len=60), "marker": F("str", True, max_len=160),
            "hashtag": F("str", True, pattern=r"^#[a-z0-9]{3,40}$")}),
        "slot": F("str", True, max_len=200), "hypothesis": F("str", True, max_len=400),
        "test_plan": F("list", True, items=F("str", max_len=240), min_items=3),
        "elements": F("object", True, fields={
            "participation": F("str", True, PARTICIPATION),
            "format_key": F("slug", True), "emotion": F("str", True, EMOTIONS),
            "signature": F("str", True, max_len=60)})}),
    "used": F("bool", True), "used_at": F("datetime"),
    "script_sha": F("str", pattern=r"^[0-9a-f]{8,64}$"),
}

SPECS = {"observation": OBSERVATION, "creator": CREATOR, "signal": SIGNAL,
         "trend": TREND, "recipe": RECIPE}
TITLES = {
    "observation": "One observed short-form post: public metrics + our analysis",
    "creator": "Creator snapshot: followers and recent-views baseline",
    "signal": "Aggregate trend signal (e.g. a TikTok Creative Center list row)",
    "trend": "Trend card (derived/trends.json -> trends[])",
    "recipe": "Synthesised trend recipe (derived/recipes.jsonl)",
}

# ------------------------------------------------------------- text checks
MEDIA_HOST_RE = re.compile(
    r"(?i)(?:cdninstagram|fbcdn|tiktokcdn|tiktokv\.com|googlevideo|ytimg\.com|"
    r"twimg\.com|pinimg\.com|muscdn|akamaized\.net/.*\.(?:mp4|m3u8))")
MEDIA_EXT_RE = re.compile(
    r"(?i)\.(?:mp4|m4v|mov|webm|mkv|m3u8|mp3|m4a|aac|wav|jpe?g|png|webp|gif|heic)"
    r"(?:$|[?#&])")
_URL_RE = re.compile(r"(?i)\bhttps?://[^\s\"'<>]+")
INSTRUCTION_RE = re.compile(
    r"(?im)(?:\b(?:ignore|disregard|forget|override)\s+(?:all\s+|any\s+|the\s+|your\s+|"
    r"of\s+)*(?:previous|prior|above|earlier|preceding|system)\b"
    r"|^\s*(?:system|assistant|developer)\s*:"
    r"|\[/?(?:inst|system)\]|<<\s*/?sys\s*>>|<\|\s*(?:im_start|im_end|system|endoftext)"
    r"|###\s*(?:system|instruction)"
    r"|\bnew\s+instructions?\s*:"
    r"|\bjailbreak\b|\bprompt\s+injection\b)")


def media_url_problem(text):
    """Why `text` carries a media/CDN URL, or None."""
    if not isinstance(text, str):
        return None
    m = MEDIA_HOST_RE.search(text)
    if m:
        return f"media/CDN URL ({m.group(0)}) — store permalinks only, never media"
    for u in _URL_RE.findall(text):
        path = u.split("://", 1)[1]
        path = path.split("/", 1)[1] if "/" in path else ""
        if MEDIA_EXT_RE.search("/" + path):
            return "media file URL — store permalinks only, never media"
    return None


def instruction_like(text):
    """The instruction-like fragment in `text` (reel text is data), or None."""
    if not isinstance(text, str):
        return None
    m = INSTRUCTION_RE.search(text)
    return m.group(0).strip() if m else None


def word_count(text):
    return len(re.findall(r"\S+", text or ""))


def first_words(text, n=MAX_FIRST_WORDS):
    """The first n whitespace-separated words of `text` (None if empty)."""
    ws = re.findall(r"\S+", text or "")
    return " ".join(ws[:n]) if ws else None


# ------------------------------------------------------------------ time
def utc(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def now_utc():
    return datetime.now(timezone.utc).replace(microsecond=0)


def parse_time(value):
    """Aware UTC datetime or None (vsp.ingest.util.parse_ts semantics)."""
    from vsp.ingest.util import parse_ts
    return parse_ts(value)


def iso(dt):
    """'YYYY-MM-DDTHH:MM:SSZ' (UTC) or None."""
    if dt is None:
        return None
    if not isinstance(dt, datetime):
        dt = parse_time(dt)
        if dt is None:
            return None
    return utc(dt).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_or_raw(value):
    """ISO string when parseable, else the raw value (so validation can
    name the bad input instead of silently dropping it)."""
    if value is None or value == "":
        return None
    out = iso(value)
    return out if out else value


# ------------------------------------------------------------ identities
def obs_id(platform, post_id):
    return hashlib.sha1(f"{platform}:{post_id}".encode("utf-8")).hexdigest()[:16]


def _ascii_fold(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")


def slug(text, max_len=48):
    s = re.sub(r"[^a-z0-9]+", "-", _ascii_fold(text).lower()).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    return s[:max_len].strip("-") or None


_PID = {
    "instagram": [r"instagram\.com/(?:[\w.]+/)?(?:reels?|p|tv)/([A-Za-z0-9_-]{5,64})"],
    "tiktok": [r"tiktok\.com/@[\w.-]+/(?:video|photo)/(\d{6,25})", r"tiktok\.com/(?:v|t)/(\w+)"],
    "youtube": [r"youtube\.com/shorts/([A-Za-z0-9_-]{11})",
                r"youtube\.com/watch\?(?:.*&)?v=([A-Za-z0-9_-]{11})",
                r"youtu\.be/([A-Za-z0-9_-]{11})", r"youtube\.com/live/([A-Za-z0-9_-]{11})"],
    "pinterest": [r"pinterest\.[a-z.]+/pin/(\d{5,25})"],
    "x": [r"(?:x|twitter)\.com/[\w]+/status/(\d{5,25})"],
}
_HOSTS = {"instagram": ("instagram.com",), "tiktok": ("tiktok.com",),
          "youtube": ("youtube.com", "youtu.be"),
          "pinterest": ("pinterest.",), "x": ("x.com", "twitter.com")}


def canonical_post_id(platform, permalink, post_id=None):
    """The platform's post id from the permalink (Instagram: shortcode), else
    the given post_id, else a stable url:<sha1> id; None without both."""
    for rx in _PID.get(platform, []):
        m = re.search(rx, permalink or "")
        if m:
            return m.group(1)
    if post_id not in (None, ""):
        return str(post_id).strip()
    if permalink:
        return "url:" + hashlib.sha1(permalink.encode("utf-8")).hexdigest()[:12]
    return None


def canonical_permalink(platform, url):
    """Drop tracking query strings / fragments (YouTube keeps ?v=<id>)."""
    if not isinstance(url, str):
        return url
    u = url.strip()
    m = re.match(r"^([A-Za-z][A-Za-z0-9+.-]*://)([^/?#]+)(.*)$", u)
    if m:                                   # scheme and host are case-insensitive
        u = m.group(1).lower() + m.group(2).lower() + m.group(3)
    if platform == "youtube":
        m = re.search(r"(?:watch\?(?:.*&)?v=|youtu\.be/)([A-Za-z0-9_-]{11})", u)
        if m:
            return "https://www.youtube.com/watch?v=" + m.group(1)
    return u.split("#", 1)[0].split("?", 1)[0]


def permalink_problem(platform, url):
    if not isinstance(url, str) or not url:
        return None
    if not re.match(r"^https://[^\s/]+\.[^\s/]+(?:/\S*)?$", url):
        return "permalink must be an https URL of the post page"
    host = url.split("://", 1)[1].split("/", 1)[0].lower()
    hosts = _HOSTS.get(platform)
    if hosts and not any(h in host for h in hosts):
        return f"permalink host {host!r} does not match platform {platform!r}"
    return None


def norm_handle(handle):
    if handle is None:
        return None
    h = str(handle).strip()
    if not h:
        return None
    if h.startswith("channel/"):
        return h
    return h.lstrip("@").strip().lower() or None


def norm_niche(niche):
    if niche is None or str(niche).strip() == "":
        return None
    n = slug(niche, 40)
    return RESEARCH_NICHES.get(n, n)


def tier_for(followers):
    """Creator tier from followers (HypeAuditor 2026 bounds; < 1k = emerging)."""
    if not isinstance(followers, int) or isinstance(followers, bool) or followers < 0:
        return None
    for name, lo, hi in TIER_BOUNDS:
        if followers >= lo and (hi is None or followers < hi):
            return name
    return None


TIER_BOUNDS = (("emerging", 0, 1000), ("nano", 1000, 10000), ("micro", 10000, 100000),
               ("mid", 100000, 500000), ("macro", 500000, 1000000), ("mega", 1000000, None))


def norm_trend_key(key):
    """'Tag:#GirlDinner' -> 'tag:girldinner'; None if not a trend key or a
    generic noise tag."""
    if not isinstance(key, str) or ":" not in key:
        return None
    kind, _, val = key.partition(":")
    kind = {"hashtag": "tag", "#": "tag", "song": "sound", "audio": "sound"}.get(
        kind.strip().lower(), kind.strip().lower())
    if kind not in TREND_KINDS:
        return None
    val = val.strip()
    if kind == "tag":
        val = re.sub(r"[^a-z0-9_]", "", _ascii_fold(val.lstrip("#")).lower())[:64]
        if not val or val in GENERIC_TAGS:
            return None
    elif kind == "sound" and re.fullmatch(r"[A-Za-z0-9._-]{1,64}", val) and \
            re.search(r"\d", val):
        val = val.lower()                       # a platform sound id
    else:
        val = slug(val, 64)
    if not val or not re.match(r"^[a-z0-9]", val):
        return None
    return f"{kind}:{val}"


def _is_generic_tag(key):
    if not isinstance(key, str) or ":" not in key:
        return False
    kind, _, val = key.partition(":")
    val = re.sub(r"[^a-z0-9_]", "", _ascii_fold(val.strip().lstrip("#")).lower())
    return kind.strip().lower() in ("tag", "hashtag", "#") and val in GENERIC_TAGS


def derive_trend_keys(rec):
    """Given keys (normalised) + format:<format_key> + sound:<id|title> +
    topic:<topic>, sorted and unique. Generic noise tags are dropped; keys
    that cannot be normalised stay as given so validate() names them."""
    keys = set()
    bad = []
    for k in rec.get("trend_keys") or []:
        if k is None or (isinstance(k, str) and not k.strip()):
            continue
        nk = norm_trend_key(k)
        if nk:
            keys.add(nk)
        elif not _is_generic_tag(k):
            bad.append(k)
    if rec.get("format_key"):
        nk = norm_trend_key("format:" + str(rec["format_key"]))
        if nk:
            keys.add(nk)
    a = rec.get("audio") or {}
    if a.get("sound_id"):
        nk = norm_trend_key("sound:" + str(a["sound_id"]))
        if nk:
            keys.add(nk)
    elif a.get("sound_title") and a.get("type") in ("trending_sound", "original_sound",
                                                     "licensed_music"):
        title = slug(a["sound_title"], 64)
        nk = norm_trend_key("sound:" + title) if title else None
        if nk:
            keys.add(nk)
    if rec.get("topic"):
        nk = norm_trend_key("topic:" + str(rec["topic"]))
        if nk:
            keys.add(nk)
    return sorted(keys) + bad


# ------------------------------------------------------------ coercion
ALIASES = {
    "handle": "creator.handle", "username": "creator.handle",
    "followers": "creator.followers", "subscribers": "creator.followers",
    "median_views": "creator.median_views_recent",
    "median_views_recent": "creator.median_views_recent",
    "baseline_n": "creator.baseline_n", "tier": "creator.tier",
    "views": "metrics.views", "likes": "metrics.likes", "like_count": "metrics.likes",
    "comments": "metrics.comments", "comments_count": "metrics.comments",
    "shares": "metrics.shares", "saves": "metrics.saves",
    "first_words": "hook.first_words", "archetype": "hook.archetype",
    "hook_archetype": "hook.archetype", "frame0": "hook.frame0_visual",
    "frame0_visual": "hook.frame0_visual", "visual_type": "hook.frame0_visual",
    "on_screen_text": "hook.on_screen_text",
    "beats": "structure.beats", "cuts_per_10s": "structure.cuts_per_10s",
    "payoff_reveal": "structure.payoff_reveal", "loop": "structure.loop",
    "series": "structure.series",
    "audio_type": "audio.type", "sound_id": "audio.sound_id",
    "sound_title": "audio.sound_title", "purge_after": "retention.purge_after",
}
_TRUE = ("1", "true", "yes", "y", "on", "t")
_FALSE = ("0", "false", "no", "n", "off", "f")


def _get(d, dotted):
    cur = d
    for p in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


def _set(d, dotted, value):
    parts = dotted.split(".")
    cur = d
    for p in parts[:-1]:
        nxt = cur.get(p)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[p] = nxt
        cur = nxt
    cur[parts[-1]] = value


def unflatten(raw):
    """Flat aliases / dotted keys -> the nested observation shape. `tags`
    (list or 'a b,c') become tag:<t> trend keys."""
    out = {}
    tags = []
    for k in raw:
        v = raw[k]
        key = str(k).strip()
        if key == "tags":
            tags += v if isinstance(v, list) else re.split(r"[\s,|]+", str(v or ""))
            continue
        if key in ALIASES:
            _set(out, ALIASES[key], v)
        elif "." in key:
            _set(out, key, v)
        elif isinstance(v, dict) and isinstance(out.get(key), dict):
            merged = dict(out[key])
            merged.update(v)
            out[key] = merged
        else:
            out[key] = v
    if tags:
        tk = out.get("trend_keys")
        if isinstance(tk, list):
            tk = list(tk)
        else:
            tk = [x for x in re.split(r"[\s,|;]+", str(tk or "")) if x]
        out["trend_keys"] = tk + ["tag:" + str(t).strip() for t in tags
                                  if str(t).strip()]
    return out


def _coerce(value, spec):
    """CSV-friendly coercion toward the spec type (invalid input is left as
    is so validate() reports it)."""
    from vsp.ingest.util import to_float, to_int
    t = spec["type"]
    if isinstance(value, str) and value.strip() == "" and t != "object":
        return None
    if value is None:
        return None
    if t == "int":
        if isinstance(value, bool):
            return value
        if isinstance(value, float) and value == int(value):
            return int(value)
        if isinstance(value, str):
            iv = to_int(value)
            return iv if iv is not None else value
        return value
    if t == "number":
        if isinstance(value, str):
            fv = to_float(value)
            return fv if fv is not None else value
        return value
    if t == "bool":
        if isinstance(value, str):
            low = value.strip().lower()
            if low in _TRUE:
                return True
            if low in _FALSE:
                return False
        if isinstance(value, int) and not isinstance(value, bool) and value in (0, 1):
            return bool(value)
        return value
    if t == "list":
        if isinstance(value, str):
            if spec["items"]["type"] == "trend_key":
                sep = r"[\s,|;]+"
            elif re.search(r"[|>;\u2192]", value):
                sep = r"\s*[|>;\u2192]\s*"      # 'hook > setup > reveal'
            else:
                sep = r"\s*,\s*"
            value = [x for x in re.split(sep, value.strip()) if x]
        if isinstance(value, list):
            return [_coerce(x, spec["items"]) for x in value]
        return value
    if t == "object":
        if isinstance(value, dict):
            return {k: (_coerce(v, spec["fields"][k]) if k in spec["fields"] else v)
                    for k, v in value.items()}
        return value
    if t in ("str", "slug", "url", "trend_key", "datetime", "date") and \
            isinstance(value, (int, float)) and not isinstance(value, bool) and \
            t not in ("datetime",):
        return str(value)
    return value


def expand(rec, spec=None):
    """Full form: every field present (None / [] defaults)."""
    spec = spec or OBSERVATION
    out = {}
    for k, s in spec.items():
        v = rec.get(k) if isinstance(rec, dict) else None
        if s["type"] == "object":
            out[k] = expand(v if isinstance(v, dict) else {}, s["fields"])
            if isinstance(v, dict):
                for extra in v:
                    if extra not in s["fields"]:
                        out[k][extra] = v[extra]
        elif s["type"] == "list":
            out[k] = list(v) if isinstance(v, list) else ([] if v is None else v)
        else:
            out[k] = v
    if isinstance(rec, dict):
        for extra in rec:
            if extra not in spec:
                out[extra] = rec[extra]
    return out


def compact(rec):
    """On-disk form: None values, empty lists and empty objects dropped."""
    if isinstance(rec, dict):
        out = {}
        for k in sorted(rec):
            v = compact(rec[k])
            if v is None or v == [] or v == {}:
                continue
            out[k] = v
        return out
    if isinstance(rec, list):
        return [compact(x) for x in rec]
    return rec


# ------------------------------------------------------------- validation
def _walk_strings(obj, path=""):
    if isinstance(obj, dict):
        for k in sorted(obj):
            yield from _walk_strings(obj[k], f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_strings(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


def _check(value, spec, path, errs, now):
    if value is None and spec["type"] == "list" and spec["required"]:
        value = []                      # the on-disk form drops empty lists
    if value is None or (spec["type"] == "list" and value == [] and not spec["required"]):
        if value is None and spec["required"]:
            errs.append(f"missing required field {path!r}")
        return
    t = spec["type"]
    if t == "object":
        if not isinstance(value, dict):
            errs.append(f"{path}: must be an object")
            return
        for k in sorted(value):
            if k not in spec["fields"]:
                errs.append(f"{path}.{k}: unknown field")
        for k, sub in spec["fields"].items():
            _check(value.get(k), sub, f"{path}.{k}", errs, now)
        return
    if t == "list":
        if not isinstance(value, list):
            errs.append(f"{path}: must be a list")
            return
        if spec.get("max_items") is not None and len(value) > spec["max_items"]:
            errs.append(f"{path}: {len(value)} items (max {spec['max_items']})")
        if spec.get("min_items") and len(value) < spec["min_items"]:
            errs.append(f"{path}: needs at least {spec['min_items']} item(s)")
        for i, v in enumerate(value):
            _check(v, dict(spec["items"], required=True), f"{path}[{i}]", errs, now)
        return
    if t in ("int", "number"):
        ok = (isinstance(value, int) if t == "int" else isinstance(value, (int, float))) \
            and not isinstance(value, bool)
        if not ok or (t == "number" and value != value):
            errs.append(f"{path}: must be {'an integer' if t == 'int' else 'a number'}, "
                        f"got {value!r}")
            return
        if "minimum" in spec and value < spec["minimum"]:
            errs.append(f"{path}: {value} < {spec['minimum']}")
        if "maximum" in spec and value > spec["maximum"]:
            errs.append(f"{path}: {value} > {spec['maximum']}")
        if "enum" in spec and value not in spec["enum"]:
            errs.append(f"{path}: {value!r} not one of {list(spec['enum'])}")
        return
    if t == "bool":
        if not isinstance(value, bool):
            errs.append(f"{path}: must be true/false, got {value!r}")
        return
    if not isinstance(value, str):
        errs.append(f"{path}: must be a string, got {type(value).__name__}")
        return
    if "enum" in spec and value not in spec["enum"]:
        errs.append(f"{path}: {value!r} is not a valid value (allowed: "
                    f"{', '.join(spec['enum'])})")
        return
    if t == "datetime":
        if not re.match(_ISO, value) or parse_time(value) is None:
            errs.append(f"{path}: {value!r} is not an ISO UTC timestamp")
            return
        if now is not None and not spec.get("future_ok") and \
                parse_time(value) > utc(now) + FUTURE_TOLERANCE:
            errs.append(f"{path}: {value} is in the future")
        return
    if t == "date":
        if not re.match(_DATE, value):
            errs.append(f"{path}: {value!r} is not YYYY-MM-DD")
        return
    if t == "slug" and not re.match(_SLUG, value):
        errs.append(f"{path}: {value!r} is not a lower-case slug")
    if t == "trend_key" and not re.match(_TREND_KEY, value):
        errs.append(f"{path}: {value!r} is not a trend key (sound|format|tag|topic:<slug>)")
    if spec.get("pattern") and not re.match(spec["pattern"], value):
        errs.append(f"{path}: {value!r} has an invalid format")
    if spec.get("max_len") and len(value) > spec["max_len"]:
        errs.append(f"{path}: {len(value)} chars (max {spec['max_len']})")
    if spec.get("max_words") and word_count(value) > spec["max_words"]:
        errs.append(f"{path}: {word_count(value)} words (max {spec['max_words']}) — "
                    f"store a short excerpt, never the whole caption")
    if spec.get("free_text"):
        frag = instruction_like(value)
        if frag:
            errs.append(f"{path}: instruction-like text {frag!r} — reel text is data, "
                        f"not instructions (AGENTS.md rule 8); rephrase as analysis")


def validate(rec, spec=None, now=None):
    """-> [errors] (empty = valid). `now` enables the future-timestamp check."""
    spec = spec or OBSERVATION
    errs = []
    if not isinstance(rec, dict):
        return ["record must be a JSON object"]
    for k in sorted(rec):
        if k not in spec:
            hint = ""
            if k in ("caption", "description", "transcript", "text"):
                hint = " — full captions/transcripts are never stored; use " \
                       "hook.first_words (<= 12 words) and notes"
            elif "url" in k.lower() or k in ("thumbnail", "video", "media"):
                hint = " — media is never stored; permalink only"
            errs.append(f"unknown field {k!r}{hint}")
    for k, s in spec.items():
        _check(rec.get(k), s, k, errs, now)
    for path, text in _walk_strings(rec):
        prob = media_url_problem(text)
        if prob:
            errs.append(f"{path}: {prob}")
    if spec is OBSERVATION:
        prob = permalink_problem(rec.get("platform"), rec.get("permalink"))
        if prob:
            errs.append(f"permalink: {prob}")
        if rec.get("obs_id") and rec.get("platform") and rec.get("post_id") and \
                rec["obs_id"] != obs_id(rec["platform"], rec["post_id"]):
            errs.append("obs_id does not match sha1('<platform>:<post_id>')[:16]")
    return errs


def normalize_observation(raw, now=None, defaults=None):
    """-> (record, errors). See module doc. `defaults` fill fields the raw
    record lacks (e.g. {"source": "agent_observed"})."""
    now = utc(now or now_utc())
    if not isinstance(raw, dict):
        return None, ["record must be a JSON object"]
    rec = unflatten(raw)
    for k, v in (defaults or {}).items():
        if _get(rec, k) in (None, ""):
            _set(rec, k, v)
    rec = {k: (_coerce(v, OBSERVATION[k]) if k in OBSERVATION else v)
           for k, v in rec.items()}
    rec = expand(rec)
    if rec.get("schema_version") is None:
        rec["schema_version"] = SCHEMA_VERSION
    for k in ("platform", "source", "analyst", "participation", "cta", "emotion",
              "production_cost", "vibe", "format_key"):
        if isinstance(rec.get(k), str):
            rec[k] = rec[k].strip().lower() or None
    if isinstance(rec.get("format_key"), str):
        rec["format_key"] = slug(rec["format_key"], 48) or rec["format_key"]
    plat = rec.get("platform")
    rec["permalink"] = canonical_permalink(plat, rec.get("permalink"))
    if plat and rec.get("permalink"):
        rec["post_id"] = canonical_post_id(plat, rec["permalink"], rec.get("post_id"))
    elif rec.get("post_id") is not None:
        rec["post_id"] = str(rec["post_id"]).strip() or None
    if plat and rec.get("post_id"):
        rec["obs_id"] = obs_id(plat, rec["post_id"])
    rec["observed_at"] = iso_or_raw(rec.get("observed_at")) or iso(now)
    rec["posted_at"] = iso_or_raw(rec.get("posted_at"))
    if rec.get("analyst") is None and rec.get("source") in DEFAULT_ANALYST:
        rec["analyst"] = DEFAULT_ANALYST[rec["source"]]
    cr = rec["creator"]
    cr["handle"] = norm_handle(cr.get("handle"))
    if isinstance(cr.get("followers"), int) and not isinstance(cr["followers"], bool):
        cr["tier"] = tier_for(cr["followers"])
    elif isinstance(cr.get("tier"), str):
        cr["tier"] = cr["tier"].strip().lower()
    rec["niche"] = norm_niche(rec.get("niche"))
    for k, sub in (("hook", "archetype"), ("hook", "frame0_visual"), ("audio", "type")):
        if isinstance(rec[k].get(sub), str):
            rec[k][sub] = rec[k][sub].strip().lower() or None
    if isinstance(rec.get("region"), str):
        r = rec["region"].strip()
        rec["region"] = "global" if r.lower() == "global" else r.upper()
    if isinstance(rec.get("language"), str):
        parts = rec["language"].strip().replace("_", "-").split("-")
        rec["language"] = "-".join([parts[0].lower()] + parts[1:]) if parts[0] else None
    if isinstance(rec.get("trend_keys"), list):
        rec["trend_keys"] = derive_trend_keys(rec)
    ret = rec["retention"]
    ret["purge_after"] = iso_or_raw(ret.get("purge_after"))
    if ret.get("purge_after") is None and rec.get("source") == "yt_data_api":
        seen = parse_time(rec.get("observed_at")) or now
        ret["purge_after"] = iso(seen + timedelta(days=YT_RETENTION_DAYS))
    errs = validate(rec, OBSERVATION, now=now)
    return rec, errs


def normalize_creator(raw, now=None):
    now = utc(now or now_utc())
    rec = expand(dict(raw or {}), CREATOR)
    rec["schema_version"] = rec.get("schema_version") or SCHEMA_VERSION
    rec["handle"] = norm_handle(rec.get("handle"))
    for k in ("followers", "median_views_recent", "baseline_n"):
        rec[k] = _coerce(rec.get(k), CREATOR[k])
    if isinstance(rec.get("followers"), int) and not isinstance(rec["followers"], bool):
        rec["tier"] = tier_for(rec["followers"])
    rec["snapshot_at"] = iso_or_raw(rec.get("snapshot_at")) or iso(now)
    rec["retention"]["purge_after"] = iso_or_raw(rec["retention"].get("purge_after"))
    return rec, validate(rec, CREATOR, now=now)


def signal_id(platform, key, region, industry, date):
    raw = f"{platform}:{key}:{region or ''}:{industry or ''}:{date}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def normalize_signal(raw, now=None):
    now = utc(now or now_utc())
    rec = expand(dict(raw or {}), SIGNAL)
    rec["schema_version"] = rec.get("schema_version") or SCHEMA_VERSION
    for k in ("rank", "posts", "growth_pct"):
        rec[k] = _coerce(rec.get(k), SIGNAL[k])
    if isinstance(rec.get("key"), str):
        rec["key"] = norm_trend_key(rec["key"]) or rec["key"]
    if isinstance(rec.get("region"), str):
        r = rec["region"].strip()
        rec["region"] = "global" if r.lower() in ("global", "all", "") else r.upper()
    rec["observed_at"] = iso_or_raw(rec.get("observed_at")) or iso(now)
    rec["signal_id"] = signal_id(rec.get("platform"), rec.get("key"), rec.get("region"),
                                 rec.get("industry"), rec.get("date"))
    return rec, validate(rec, SIGNAL, now=now)


# --------------------------------------------------------- JSON Schema
_JS_TYPES = {"str": "string", "slug": "string", "url": "string", "datetime": "string",
             "date": "string", "trend_key": "string", "int": "integer",
             "number": "number", "bool": "boolean", "list": "array", "object": "object"}


def _js(spec, nullable=True):
    t = spec["type"]
    out = {"type": _JS_TYPES[t]}
    if spec.get("desc"):
        out["description"] = spec["desc"]
    if t == "object":
        out["properties"] = {k: _js(v) for k, v in spec["fields"].items()}
        req = [k for k, v in spec["fields"].items() if v["required"]]
        if req:
            out["required"] = req
        out["additionalProperties"] = False
    elif t == "list":
        out["items"] = _js(dict(spec["items"], required=True), nullable=False)
        if spec.get("max_items") is not None:
            out["maxItems"] = spec["max_items"]
        if spec.get("min_items"):
            out["minItems"] = spec["min_items"]
    else:
        pat = {"slug": _SLUG, "datetime": _ISO, "date": _DATE, "trend_key": _TREND_KEY,
               "url": r"^https://"}.get(t, spec.get("pattern"))
        if spec.get("max_words"):
            pat = _words_pattern(spec["max_words"])
        if spec.get("pattern") and t != "str":
            pat = spec["pattern"]
        if pat:
            out["pattern"] = pat
        if t == "datetime":
            out["format"] = "date-time"
        if t == "date":
            out["format"] = "date"
        if t == "url":
            out["format"] = "uri"
        if spec.get("max_len"):
            out["maxLength"] = spec["max_len"]
        for a, b in (("minimum", "minimum"), ("maximum", "maximum")):
            if a in spec:
                out[b] = spec[a]
        if "enum" in spec:
            out["enum"] = list(spec["enum"])
    if nullable and not spec["required"]:
        out["type"] = [out["type"], "null"]
        if "enum" in out:
            out["enum"] = out["enum"] + [None]
    return out


def json_schema(name):
    """Draft 2020-12 JSON Schema for one record kind (see SPECS)."""
    spec = SPECS[name]
    body = _js({"type": "object", "required": True, "fields": spec, "desc": TITLES[name]},
               nullable=False)
    out = {"$schema": "https://json-schema.org/draft/2020-12/schema",
           "$id": f"{name}.v{SCHEMA_VERSION}.json", "title": f"{name} v{SCHEMA_VERSION}"}
    out.update(body)
    return out
