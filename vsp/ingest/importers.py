"""Import JSON / CSV exports from tools the user legitimately has — their own
exports (Meta Business Suite, Instagram "Download your information"),
official-API suites (Sprout, Brandwatch, Later, ...) — into reels.

    import_file(con, path, source, niche=None, cfg=None, own=False, now=None,
                dry_run=False) -> report dict

  * source must be "import:<name>" (own exports, official-API vendors) or
    "vendor:<name>" (anything else). Known unofficial scrapers (Apify, Bright
    Data, HikerAPI, Data365, ...) are refused under import:* so they cannot
    slip past the vendor filter.
  * vendor:* imports print a warning: data from scraping vendors may violate
    Instagram's Terms of Use (automated collection without permission,
    logged in or out) and Meta's Platform Terms (research doc §7). Rows keep
    the vendor:* tag so gates/readers can exclude them (db.NOT_VENDOR_SQL,
    VSP_EXCLUDE_VENDOR=1, config "vendor_rows": "exclude").
  * rows are validated (Instagram URL or media id, reel-shaped, a maker niche
    from the row, --niche, or the caption hashtags via hashtag_niche_map),
    deduped within the file and against the DB (upsert on (platform,
    media_id); files without ids use "sc:<shortcode>", merged with the API
    row for the same shortcode later).
  * media URLs in exports (videoUrl, displayUrl, ...) are ignored — media is
    never stored. A transcript column becomes the hook (hook_source 'asr').
  * own=True (your own export): rows are is_own=1 and any per-reel metrics
    (views, reach, likes, comments, shares, saves, avg watch, skip rate) are
    written as a reel_metrics snapshot, which vsp.feedback can learn from
    before API access is approved.
"""
import csv
import io
import json
import os
import re
from collections import Counter

from vsp.ingest.db import is_vendor
from vsp.ingest.normalize import normalize_item, upsert_reel
from vsp.ingest.settings import MAKER_NICHES, caption_tags, niche_for_tags
from vsp.ingest.util import (clean_text, hook_from_transcript, hours_between,
                             parse_ts, shortcode, sql_ts, to_float, to_int, utcnow)

MAX_ROWS = 50000
SOURCE_RE = re.compile(r"^(import|vendor):[a-z0-9][a-z0-9._-]{0,40}$")
KNOWN_SCRAPERS = ("apify", "brightdata", "bright-data", "bright_data", "hikerapi",
                  "data365", "phantombuster", "scrapingbee", "scraperapi", "zenrows",
                  "instaloader", "ensembledata", "scrapecreators", "lamatok")
VENDOR_WARNING = (
    "WARNING: source {src!r} — data from unofficial scraping vendors may violate "
    "Instagram's Terms of Use (automated collection without express permission, "
    "logged in or out; buying/selling Instagram data) and Meta's Platform Terms "
    "(docs/research/instagram-data-access.md §7; the Bright Data ruling is not a "
    "licence). Rows stay tagged vendor:* so gates and readers can exclude them "
    "(VSP_EXCLUDE_VENDOR=1 or \"vendor_rows\": \"exclude\"). Keep vendor data out "
    "of the Meta app, get legal review, and store text and numbers only.")

_A = {
    "media_id": ["media_id", "id", "mediaid", "post_id", "postid", "ig_id", "pk",
                 "igmediaid", "instagram_media_id"],
    "url": ["permalink", "url", "link", "post_url", "posturl", "inputurl",
            "permanent_link", "permanentlink", "post_link"],
    "shortcode": ["shortcode", "short_code", "code"],
    "caption": ["caption", "text", "description", "caption_text", "title",
                "edge_media_to_caption"],
    "username": ["username", "owner_username", "ownerusername", "author", "account",
                 "handle", "account_username", "accountusername", "owner",
                 "user_posted", "userposted", "owner.username", "user.username"],
    "likes": ["like_count", "likes", "likescount", "likes_count", "digg_count",
              "num_likes"],
    "comments": ["comments_count", "comments", "commentscount", "comment_count",
                 "num_comments", "numcomments"],
    "views": ["view_count", "views", "videoviewcount", "videoplaycount", "play_count",
              "plays", "video_view_count", "ig_play_count", "igplaycount",
              "video_play_count"],
    "shares": ["shares", "share_count", "sharecount", "shares_count"],
    "saves": ["saves", "saved", "save_count", "saves_count"],
    "reach": ["reach", "accounts_reached", "accountsreached"],
    "reposts": ["reposts", "repost_count"],
    "skip_rate": ["reels_skip_rate", "skip_rate", "skiprate", "skip rate"],
    "avg_watch": ["ig_reels_avg_watch_time", "avg_watch_time", "average_watch_time",
                  "averagewatchtime", "avg_watch_time_ms", "average_watch_time_seconds"],
    "timestamp": ["timestamp", "taken_at", "takenat", "posted_at", "postedat", "date",
                  "created_time", "createtime", "publish_time", "publishtime",
                  "published", "upload_date", "date_posted", "dateposted"],
    "media_type": ["media_type", "type", "producttype", "product_type",
                   "media_product_type", "post_type", "posttype", "content_type",
                   "contenttype"],
    "transcript": ["transcript", "transcription", "transcript_text", "subtitles"],
    "niche": ["niche"],
}


def _k(key):
    return re.sub(r"[^a-z0-9]+", "", str(key).lower())


ALIASES = {field: [_k(a) for a in names] for field, names in _A.items()}
_REEL_TYPES = {"reel", "reels", "clips", "clip", "video", "igtv", "graphvideo"}
_NOT_REEL = {"image", "photo", "carousel", "carouselalbum", "sidecar", "graphimage",
             "graphsidecar", "album", "story", "text"}


class ImportError_(ValueError):
    """Bad source tag / unreadable file (named to avoid shadowing ImportError)."""


def check_source(source):
    s = str(source or "").strip().lower()
    if not SOURCE_RE.match(s):
        raise ImportError_(f"--source must be import:<name> or vendor:<name> "
                           f"(lowercase, e.g. import:business-suite, vendor:apify); "
                           f"got {source!r}")
    name = s.split(":", 1)[1]
    flat = re.sub(r"[^a-z0-9]", "", name)
    if s.startswith("import:") and any(re.sub(r"[^a-z0-9]", "", v) in flat
                                       for v in KNOWN_SCRAPERS):
        raise ImportError_(f"{name!r} is an unofficial scraping vendor — tag it "
                           f"vendor:{name} (Instagram Terms, research doc §7)")
    return s


def _flatten(obj, prefix=""):
    out = {}
    for k, v in (obj or {}).items():
        key = f"{prefix}{k}"
        if isinstance(v, dict) and len(prefix) < 40:
            out.update(_flatten(v, key + "."))
            if "text" in v and isinstance(v["text"], str):     # {"text": caption}
                out[key] = v["text"]
        else:
            out[key] = v
    return out


def _pick(rec, field):
    for alias in ALIASES[field]:
        if alias in rec and rec[alias] not in (None, ""):
            return rec[alias]
    return None


def read_records(path):
    """-> (records [dict], format). JSON array / {"data"|"items"|...: [...]} /
    JSONL / CSV (delimiter sniffed, BOM tolerated)."""
    if not os.path.isfile(path):
        raise ImportError_(f"file not found: {path}")
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8-sig", errors="replace")
    stripped = text.lstrip()
    if path.lower().endswith((".json", ".jsonl", ".ndjson")) or stripped[:1] in "[{":
        try:
            data = json.loads(text)
            fmt = "json"
        except ValueError:
            data, fmt = [], "jsonl"
            for i, line in enumerate(text.splitlines(), 1):
                if line.strip():
                    try:
                        data.append(json.loads(line))
                    except ValueError as e:
                        raise ImportError_(f"{path}:{i}: not JSON ({e})")
        if isinstance(data, dict):
            for key in ("data", "items", "results", "posts", "reels", "media"):
                if isinstance(data.get(key), list):
                    data = data[key]
                    break
            else:
                data = [data]
        if not isinstance(data, list):
            raise ImportError_(f"{path}: expected a list of records")
        return [d for d in data if isinstance(d, dict)][:MAX_ROWS], fmt
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.DictReader(io.StringIO(text), dialect=dialect))
    return rows[:MAX_ROWS], "csv"


def _is_reelish(mtype, url):
    t = _k(mtype or "")
    if t in _NOT_REEL:
        return False, f"not a reel (type {mtype})"
    if t in _REEL_TYPES:
        return True, None
    if url and re.search(r"/(?:reels?|tv)/", url):
        return True, None
    return False, "not a reel (no video type, not a /reel/ permalink)"


def _watch_ms(value, header_hint=""):
    """Average watch time -> ms: 'm:ss', seconds (<= 600) or ms."""
    if value is None or value == "":
        return None
    s = str(value).strip()
    m = re.fullmatch(r"(\d+):(\d{1,2})(?:\.(\d+))?", s)
    if m:
        return int((int(m.group(1)) * 60 + int(m.group(2))) * 1000)
    v = to_float(s.rstrip("s"))
    if v is None:
        return None
    if "ms" in header_hint:
        return int(round(v))
    return int(round(v * 1000)) if v <= 600 else int(round(v))


def import_file(con, path, source, niche=None, cfg=None, own=False, now=None,
                dry_run=False, warn=None):
    src = check_source(source)
    if niche is not None and niche not in MAKER_NICHES:
        raise ImportError_(f"--niche {niche!r} is not a maker niche: "
                           + ", ".join(MAKER_NICHES))
    warn = warn or (lambda msg: None)
    report = {"file": os.path.abspath(path), "source": src, "format": None,
              "rows_read": 0, "inserted": 0, "updated": 0, "adopted": 0,
              "metrics_snapshots": 0, "skipped": Counter(), "errors": [],
              "warnings": [], "own": bool(own), "dry_run": bool(dry_run)}
    if is_vendor(src):
        msg = VENDOR_WARNING.format(src=src)
        report["warnings"].append(msg)
        warn(msg)
    if own and is_vendor(src):
        raise ImportError_("own exports come from your own account: use import:<name>")
    records, fmt = read_records(path)
    report["format"], report["rows_read"] = fmt, len(records)
    now_dt = parse_ts(now) or utcnow()
    seen = set()
    for i, raw in enumerate(records, 1):
        rec = {_k(k): v for k, v in _flatten(raw).items()}
        url = _pick(rec, "url")
        url = str(url).strip() if url else None
        sc = _pick(rec, "shortcode")
        if not url and sc:
            url = f"https://www.instagram.com/reel/{str(sc).strip()}/"
        if url and not re.match(r"^https?://(?:www\.)?instagram\.com/", url, re.I):
            report["skipped"]["not an instagram.com URL"] += 1
            continue
        sc = shortcode(url) or (str(sc).strip() if sc else None)
        mid = _pick(rec, "media_id")
        mid = str(mid).strip() if mid not in (None, "") else None
        if mid and not re.fullmatch(r"[0-9A-Za-z_:-]{3,64}", mid):
            mid = None
        if not mid and sc:
            mid = "sc:" + sc
        if not mid or not url:
            report["skipped"]["no media id / URL"] += 1
            continue
        if own and mid.startswith("sc:"):
            report["skipped"]["own rows need the Instagram media id"] += 1
            continue
        if mid in seen:
            report["skipped"]["duplicate in file"] += 1
            continue
        seen.add(mid)
        ok, why = _is_reelish(_pick(rec, "media_type"), url)
        if not ok:
            report["skipped"][why] += 1
            continue
        caption = _pick(rec, "caption")
        caption = str(caption) if caption is not None else None
        row_niche = _pick(rec, "niche")
        row_niche = str(row_niche).strip().lower() if row_niche else None
        n = (row_niche if row_niche in MAKER_NICHES else None) or niche or \
            (niche_for_tags(caption_tags(caption), cfg) if cfg else None)
        if not n and not own:
            report["skipped"]["no niche (pass --niche or map a caption hashtag)"] += 1
            continue
        ts = _pick(rec, "timestamp")
        item = {"id": mid, "permalink": url, "caption": caption,
                "like_count": to_int(_pick(rec, "likes")),
                "comments_count": to_int(_pick(rec, "comments")),
                "view_count": to_int(_pick(rec, "views")),
                "timestamp": sql_ts(parse_ts(ts)) if parse_ts(ts) else None,
                "media_type": "VIDEO", "media_product_type": "REELS"}
        user = _pick(rec, "username")
        row, why = normalize_item(item, source=src, source_query=os.path.basename(path),
                                  niche=n, username=str(user).lstrip("@") if user else None,
                                  now=now_dt, is_own=own,
                                  retention_days=None if own else
                                  ((cfg or {}).get("fetch") or {}).get("retention_days", 30))
        if row is None:
            report["skipped"][why] += 1
            continue
        row["shares"] = to_int(_pick(rec, "shares"))
        row["saves"] = to_int(_pick(rec, "saves"))
        tr = _pick(rec, "transcript")
        if tr:
            row["transcript"] = clean_text(str(tr), limit=4000)
            hook = hook_from_transcript(row["transcript"])
            if hook:
                row["hook_text"], row["hook_source"] = hook, "asr"
        row["notes"] = clean_text(f"{row['notes']} · imported via {src}", limit=240)
        if dry_run:
            report["inserted"] += 1
            continue
        try:
            status = upsert_reel(con, row)
        except Exception as e:  # noqa: BLE001 — one bad row never aborts the file
            report["errors"].append(f"row {i}: {type(e).__name__}: {e}")
            continue
        report[status] += 1
        if own:
            report["metrics_snapshots"] += _own_snapshot(con, rec, mid, row, now_dt)
    if not dry_run:
        con.commit()
    report["skipped"] = dict(report["skipped"])
    return report


def _own_snapshot(con, rec, mid, row, now_dt):
    vals = {"views": to_int(_pick(rec, "views")), "reach": to_int(_pick(rec, "reach")),
            "likes": to_int(_pick(rec, "likes")),
            "comments": to_int(_pick(rec, "comments")),
            "shares": to_int(_pick(rec, "shares")), "saves": to_int(_pick(rec, "saves")),
            "reposts": to_int(_pick(rec, "reposts")),
            "skip_rate": to_float(_pick(rec, "skip_rate"))}
    hint = next((a for a in ALIASES["avg_watch"] if a in rec), "")
    vals["avg_watch_ms"] = _watch_ms(_pick(rec, "avg_watch"), hint)
    if all(v is None for v in vals.values()):
        return 0
    age = hours_between(now_dt, row.get("posted_at"))
    con.execute(
        "INSERT OR REPLACE INTO reel_metrics(media_id, captured_at, age_h, views, reach, "
        "likes, comments, shares, saves, reposts, avg_watch_ms, total_watch_ms, skip_rate) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (mid, sql_ts(now_dt), int(age) if age is not None else None, vals["views"],
         vals["reach"], vals["likes"], vals["comments"], vals["shares"], vals["saves"],
         vals["reposts"], vals["avg_watch_ms"], None, vals["skip_rate"]))
    return 1
