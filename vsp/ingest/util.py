"""Shared helpers for vsp.ingest and vsp.feedback (stdlib only, py3.9+).

  utcnow() / sql_ts(dt)   UTC time in the research DB's text format
                          'YYYY-MM-DD HH:MM:SS' (what SQLite datetime('now')
                          writes and research_bridge's 7-day filter compares)
  parse_ts(value)         aware UTC datetime from Graph API timestamps
                          ('+0000' offsets, which py3.9 fromisoformat rejects),
                          ISO strings, 'YYYY-MM-DD[ HH:MM:SS]', US dates, or
                          unix seconds / milliseconds; None if unparseable
  clean_text(s, limit)    prompt-injection hygiene (oss-pipelines #16): drops
                          control / zero-width / bidi characters, template
                          braces, angle brackets and <<< >>> boundary markers,
                          collapses whitespace, caps the length
  hook_from_caption(c)    the research doc §9 hook: first caption line that is
                          non-empty once hashtags, mentions, URLs and emoji are
                          stripped, <= 150 chars
  to_int(v)               "1.2M" / "12,345" / "3.4k" / 12.0 -> int (None if not
                          a number)
"""
import re
import unicodedata
from datetime import datetime, timedelta, timezone

SQL_TS = "%Y-%m-%d %H:%M:%S"
HOOK_MAX = 150
CAPTION_MAX = 2200          # Instagram's caption limit


# ------------------------------------------------------------------ time
def utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0)


def sql_ts(dt=None):
    """'YYYY-MM-DD HH:MM:SS' in UTC (== SQLite datetime('now'))."""
    dt = dt or utcnow()
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime(SQL_TS)


def iso_ts(dt=None):
    dt = dt or utcnow()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


_TZ_NOCOLON = re.compile(r"^(.*\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?)([+-]\d{2})(\d{2})$")
_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M", "%Y/%m/%d", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M",
            "%m/%d/%Y")


def parse_ts(value):
    """Aware UTC datetime or None. Never raises."""
    if value is None or isinstance(value, bool):
        return None
    dt = None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        v = float(value)
        if v > 1e11:                      # milliseconds
            v /= 1000.0
        try:
            return datetime.fromtimestamp(v, timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    else:
        s = str(value).strip()
        if not s:
            return None
        if re.fullmatch(r"\d{9,13}(?:\.\d+)?", s):
            return parse_ts(float(s))
        if s.endswith(("Z", "z")):
            s = s[:-1] + "+00:00"
        m = _TZ_NOCOLON.match(s)
        if m:                             # Graph API: 2026-09-27T18:04:11+0000
            s = f"{m.group(1)}{m.group(2)}:{m.group(3)}"
        # py3.9 fromisoformat wants 0, 3 or 6 fractional digits
        s = re.sub(r"(\.\d{1,6})\d*(?=[+-]\d{2}:\d{2}$|$)",
                   lambda mm: (mm.group(1) + "000000")[:7], s)
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            for fmt in _FORMATS:
                try:
                    dt = datetime.strptime(s, fmt)
                    break
                except ValueError:
                    continue
        if dt is None:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_sql_ts(value):
    dt = parse_ts(value)
    return sql_ts(dt) if dt else None


def hours_between(later, earlier):
    a, b = parse_ts(later), parse_ts(earlier)
    if a is None or b is None:
        return None
    return (a - b).total_seconds() / 3600.0


def plus_days(dt, days):
    return (parse_ts(dt) or utcnow()) + timedelta(days=days)


# ------------------------------------------------------------------ numbers
def to_int(v):
    """12 / 12.0 / "12,345" / "1.2M" / "3.4k" / "1 234" -> int; else None."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(round(v)) if v == v else None       # NaN -> None
    s = str(v).strip().lower().replace(",", "").replace("\u00a0", "").replace(" ", "")
    if not s or s in ("-", "--", "n/a", "na", "none", "null", "nan"):
        return None
    m = re.fullmatch(r"([0-9]*\.?[0-9]+)([kmb]?)", s)
    if not m:
        return None
    mult = {"": 1, "k": 1e3, "m": 1e6, "b": 1e9}[m.group(2)]
    return int(round(float(m.group(1)) * mult))


def to_float(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if v == v else None
    s = str(v).strip().replace(",", "").rstrip("%")
    try:
        return float(s)
    except ValueError:
        return None


# ------------------------------------------------------------------ text
_INVISIBLE = re.compile(
    "[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f"
    "\u00ad\u061c\u180e\u200b-\u200f\u202a-\u202e\u2060-\u2064"
    "\u2066-\u2069\ufeff\ufff9-\ufffb]")
_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U0001FC00-\U0001FFFF"   # pictographs, emoticons, flags
    "\u2600-\u27BF\u2B00-\u2BFF\u2300-\u23FF"         # misc symbols, dingbats
    "\u203C\u2049\u2139\u3030\u303D\u3297\u3299"
    "\uFE00-\uFE0F\u200D\u20E3\U000E0020-\U000E007F]")
_URL = re.compile(r"(?i)\b(?:https?://|www\.)\S+")
# a hashtag has at least one non-digit ("#1 mistake" is not a tag); the
# pipeline's own #vsp-<sha8> caption tag goes with its suffix
_HASHTAG = re.compile(r"#vsp-\w+|#(?!\d+\b)\w+(?:-[0-9a-fA-F]{8}\b)?")
_MENTION = re.compile(r"(?<![\w.@])@[\w.]*\w")
_EDGE = " \t-\u2013\u2014|\u2022\u00b7:;,/_*~=+^"


def clean_text(s, limit=None, keep_newlines=False, fold=False):
    """Plain, prompt-safe text. fold=True applies NFKC (fancy 'bold' unicode
    letters -> ASCII), used for hooks; captions keep NFC."""
    if s is None:
        return None
    t = unicodedata.normalize("NFKC" if fold else "NFC", str(s))
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = _INVISIBLE.sub("", t)
    t = t.replace("<<<", " ").replace(">>>", " ")
    t = re.sub(r"[{}<>]", "", t)
    if keep_newlines:
        t = "\n".join(" ".join(line.split()) for line in t.split("\n"))
        t = re.sub(r"\n{3,}", "\n\n", t).strip()
    else:
        t = " ".join(t.split())
    if limit is not None and len(t) > limit:
        t = t[:limit].rstrip()
    return t


def _cap_hook(t, limit):
    if len(t) <= limit:
        return t
    head = t[:limit + 1]
    ends = [m.end() for m in re.finditer(r"[.!?](?=\s)", head)]
    ends = [e for e in ends if 20 <= e <= limit]
    if ends:                              # prefer a whole first sentence
        return head[:ends[0]].strip()
    cut = head.rfind(" ", 0, limit + 1)
    out = head[:cut] if cut >= limit * 0.6 else t[:limit]
    return out.rstrip(_EDGE + " ")


def strip_caption_line(line):
    t = _URL.sub(" ", line)
    t = _HASHTAG.sub(" ", t)
    t = _MENTION.sub(" ", t)
    t = _EMOJI.sub(" ", t)
    t = " ".join(t.split())
    return t.strip(_EDGE)


def hook_from_caption(caption, limit=HOOK_MAX):
    """First non-empty caption line with hashtags, mentions, URLs and emoji
    stripped, <= limit chars (whole first sentence when it fits); None when
    nothing is left."""
    if not caption:
        return None
    text = clean_text(caption, keep_newlines=True, fold=True) or ""
    for line in text.split("\n"):
        t = strip_caption_line(line)
        if len(re.findall(r"\w", t)) >= 2:
            return _cap_hook(t, limit)
    return None


def hook_from_transcript(text, limit=HOOK_MAX):
    t = clean_text(text, fold=True)
    if not t or len(re.findall(r"\w", t)) < 2:
        return None
    return _cap_hook(t, limit)


def shortcode(url):
    """Instagram shortcode from a /reel/ /reels/ /p/ /tv/ permalink."""
    m = re.search(r"instagram\.com/(?:[\w.]+/)?(?:reels?|p|tv)/([A-Za-z0-9_-]+)",
                  url or "")
    return m.group(1) if m else None


def canonical_permalink(url):
    """Permalink without query string / fragment (tracking params)."""
    if not url:
        return None
    u = str(url).strip().split("#", 1)[0].split("?", 1)[0]
    return u or None


def mask(secret):
    """Never prints any part of a secret — only whether it is set."""
    if not secret:
        return "(unset)"
    return f"set ({len(str(secret))} chars)"
