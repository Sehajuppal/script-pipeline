"""Graph API media items -> research-DB reels rows (research doc §9 mapping).

    is_reel(item)                         VIDEO + /reel/ permalink, or
                                          media_product_type == REELS
    normalize_item(item, source=..., source_query=..., niche=..., username=...,
                   followers=..., now=..., retention_days=30, is_own=False,
                   max_age_days=None) -> (row | None, skip_reason | None)
    upsert_reel(con, row) -> "inserted" | "updated" | "adopted"

Row mapping: url = permalink (query string dropped); username = the Business
Discovery / own account handle, NULL for hashtag rows (make_shotlist then
prints "@None", as the research doc accepts); niche from the hashtag->niche
map or the watchlist niche; like_count NULL when hidden; hook_text = the
first caption line with hashtags, mentions, URLs and emoji stripped (<= 150
chars), hook_source = 'caption'; analyzed_at = datetime('now') format
'YYYY-MM-DD HH:MM:SS' (UTC); notes = source + a metrics summary (Business
Discovery: the views / followers outlier score). media_url is NEVER copied
into a row (CDN links expire and deleted media must drop out).

Upsert key: (platform, media_id). A legacy research-agent row with the same
shortcode and no media_id is adopted (media_id + new columns filled, its
curated hook_text / niche / pattern kept) instead of duplicated. Re-fetching
refreshes metrics, analyzed_at, last_seen_at and purge_after; an ASR or
own-render hook is never overwritten by a caption hook; a changed hook_text
clears vsp.ingest's classification so `classify` re-labels it.
"""
from datetime import timedelta

from vsp.ingest.util import (CAPTION_MAX, canonical_permalink, clean_text,
                             hook_from_caption, parse_ts, shortcode, sql_ts,
                             to_int, utcnow)

SOURCES = ("ig_hashtag_top", "ig_hashtag_recent", "ig_bd", "ig_own")
_LABEL = {"ig_hashtag_top": "top reel for {q} (Instagram hashtag search)",
          "ig_hashtag_recent": "recent reel for {q} (Instagram hashtag search)",
          "ig_bd": "watchlist {q} (Business Discovery)",
          "ig_own": "own reel"}
ROW_KEYS = ("platform", "media_id", "url", "username", "niche", "like_count",
            "comments", "views", "shares", "saves", "notes", "hook_text",
            "hook_source", "caption", "transcript", "source", "source_query",
            "media_type", "media_product_type", "media_audio_type", "posted_at",
            "analyzed_at", "last_seen_at", "purge_after", "is_own", "is_trial",
            "script_slug")


def is_reel(item):
    if not isinstance(item, dict):
        return False
    if str(item.get("media_product_type") or "").upper() == "REELS":
        return True
    return (str(item.get("media_type") or "").upper() == "VIDEO"
            and "/reel/" in str(item.get("permalink") or ""))


def _fmt(n):
    return f"{n:,}" if isinstance(n, int) else "?"


def outlier_score(views, followers):
    if isinstance(views, int) and isinstance(followers, int) and followers > 0:
        return views / float(followers)
    return None


def build_notes(source, query, likes, comments, views, followers):
    label = _LABEL.get(source, source or "import").format(q=query or "")
    bits = []
    score = outlier_score(views, followers)
    if score is not None:
        bits.append(f"outlier {score:.1f}x views/followers ({_fmt(views)} views, "
                    f"{_fmt(followers)} followers)")
    elif isinstance(views, int):
        bits.append(f"{_fmt(views)} views")
    if isinstance(comments, int):
        bits.append(f"{_fmt(comments)} comments")
    if likes is None and source in ("ig_hashtag_top", "ig_hashtag_recent", "ig_bd"):
        bits.append("likes hidden")
    return clean_text(" · ".join(bits + [label]), limit=240)


def normalize_item(item, source, source_query=None, niche=None, username=None,
                   followers=None, now=None, retention_days=30, is_own=False,
                   max_age_days=None):
    """-> (row, None) or (None, reason). See module doc."""
    if not isinstance(item, dict):
        return None, "not an object"
    mid = str(item.get("id") or "").strip()
    if not mid:
        return None, "no id"
    if not is_reel(item):
        return None, "not a reel"
    url = canonical_permalink(item.get("permalink"))
    if not url:
        return None, "no permalink"
    now_dt = parse_ts(now) or utcnow()
    posted = parse_ts(item.get("timestamp"))
    if max_age_days is not None and posted is not None and \
            posted < now_dt - timedelta(days=float(max_age_days)):
        return None, "too old"
    likes = to_int(item.get("like_count"))
    comments = to_int(item.get("comments_count"))
    views = to_int(item.get("view_count"))
    caption = clean_text(item.get("caption"), limit=CAPTION_MAX, keep_newlines=True)
    hook = hook_from_caption(caption)
    ts = sql_ts(now_dt)
    user = clean_text(username, limit=64) if username else None
    row = {
        "platform": "instagram", "media_id": mid, "url": url,
        "username": user or None, "niche": niche or None,
        "like_count": likes, "comments": comments, "views": views,
        "shares": None, "saves": None,
        "notes": build_notes(source, source_query, likes, comments, views,
                             to_int(followers)),
        "hook_text": hook, "hook_source": "caption" if hook else None,
        "caption": caption or None, "transcript": None,
        "source": source, "source_query": source_query,
        "media_type": (str(item["media_type"]).upper() if item.get("media_type") else None),
        "media_product_type": (str(item["media_product_type"]).upper()
                               if item.get("media_product_type") else None),
        "media_audio_type": (str(item["media_audio_type"]).upper()
                             if item.get("media_audio_type") else None),
        "posted_at": sql_ts(posted) if posted else None,
        "analyzed_at": ts, "last_seen_at": ts,
        "purge_after": (None if is_own or retention_days is None
                        else sql_ts(now_dt + timedelta(days=float(retention_days)))),
        "is_own": 1 if is_own else 0, "is_trial": 0, "script_slug": None,
    }
    return row, None


# ------------------------------------------------------------------ upsert
_REFRESH = ("like_count", "comments", "views", "shares", "saves", "caption",
            "transcript", "media_type", "media_product_type", "media_audio_type",
            "posted_at", "url", "username")


def upsert_reel(con, row):
    """Insert or merge `row` on (platform, media_id). See module doc."""
    if "media_url" in row:
        raise ValueError("media_url must never be persisted")
    r = {k: row.get(k) for k in ROW_KEYS}
    r["platform"] = r["platform"] or "instagram"
    if not r["media_id"]:
        raise ValueError("upsert_reel needs a media_id")
    old = con.execute("SELECT * FROM reels WHERE platform=? AND media_id=?",
                      (r["platform"], r["media_id"])).fetchone()
    status = "updated"
    if old is None:
        sc = shortcode(r["url"])
        if sc:
            esc = sc.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            cands = con.execute(
                "SELECT * FROM reels WHERE media_id IS NULL AND (url LIKE ? ESCAPE '\\' "
                "OR url LIKE ? ESCAPE '\\') ORDER BY id",
                ("%/" + esc + "/%", "%/" + esc)).fetchall()
            old = next((c for c in cands if shortcode(c["url"]) == sc), None)
        if old is None:
            cols = [k for k in ROW_KEYS]
            con.execute(f"INSERT INTO reels({', '.join(cols)}) VALUES "
                        f"({', '.join('?' for _ in cols)})", [r[k] for k in cols])
            return "inserted"
        status = "adopted"
    old = dict(old)
    new = {}
    ours = old.get("source") is not None           # a row vsp.ingest wrote
    for k in _REFRESH:
        new[k] = r[k] if r[k] is not None else old.get(k)
    if status == "adopted":
        new["url"] = old.get("url") or r["url"]       # keep the curated URL
    new["media_id"] = r["media_id"]
    new["platform"] = r["platform"]
    new["niche"] = old.get("niche") or r["niche"]
    if r["is_own"]:
        new["is_own"], new["source"], new["source_query"] = 1, r["source"], r["source_query"]
        new["purge_after"] = old.get("purge_after") if old.get("purge_after") and \
            old.get("is_own") else None
    else:
        new["is_own"] = old.get("is_own") or 0
        new["source"] = old.get("source") or r["source"]
        new["source_query"] = old.get("source_query") or r["source_query"]
        new["purge_after"] = None if new["is_own"] else r["purge_after"]
    new["analyzed_at"] = r["analyzed_at"] or old.get("analyzed_at")
    new["last_seen_at"] = r["last_seen_at"] or old.get("last_seen_at")
    new["notes"] = r["notes"] if ours and r["notes"] else (old.get("notes") or r["notes"])
    new["is_trial"] = old.get("is_trial") or r["is_trial"] or 0
    new["script_slug"] = old.get("script_slug") or r["script_slug"]
    # hooks: a research-agent (curated) hook and ASR / own-render hooks win
    # over a caption hook; an adopted legacy hook is marked 'curated' so it
    # stays curated on every later refresh
    if not ours and old.get("hook_text") and not old.get("hook_source"):
        old["hook_source"] = "curated"
    keep_hook = old.get("hook_text") and old.get("hook_source") in (
        "asr", "own_render", "curated")
    if keep_hook or not r["hook_text"]:
        new["hook_text"], new["hook_source"] = old.get("hook_text"), old.get("hook_source")
    else:
        new["hook_text"], new["hook_source"] = r["hook_text"], r["hook_source"]
    if new["hook_text"] != old.get("hook_text") and old.get("classified_by"):
        new["hook_category"] = new["hook_family"] = new["classified_by"] = None
        new["pattern_id"] = None
    sets = ", ".join(f"{k}=?" for k in new)
    con.execute(f"UPDATE reels SET {sets} WHERE id=?", list(new.values()) + [old["id"]])
    return status
