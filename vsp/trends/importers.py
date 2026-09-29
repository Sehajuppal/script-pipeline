"""Importers for the trend dataset — official or hand-collected sources only.

    read_records(path, stdin=None) -> (records, fmt)   JSON | JSONL | CSV ('-' = stdin)
    import_ingest(d, db_path, now, days=30) -> report  vsp.ingest's reels table
    youtube(d, now, query, ...) -> report              YouTube Data API v3
    tiktok_cc(d, path, now, ...) -> report             Creative Center lists

import_ingest maps the research DB (VSP_VIRAL_DB, written by `python3 -m
vsp.ingest hashtags|watchlist`, i.e. the official Instagram Graph API):
source ig_bd / business_discovery -> ig_graph_bd, ig_hashtag_* ->
ig_graph_hashtag, yt_* -> yt_data_api, import:* -> import. Own reels
(measured by vsp.feedback), vendor:* rows (possible scraping, research doc
§7) and legacy rows without a source are skipped. url -> permalink,
username -> creator.handle, followers from vsp.ingest's notes summary (the
reels table has no followers column), hook_text -> hook.first_words (first
12 words), caption hashtags (at most 5) -> tag: keys — the caption itself
is never copied. Creator baselines come from that username's rows (>= 5
reels older than 7 days). A post is re-snapshotted only when a metric grew
>= 10 %, the last snapshot is a week old, or its retention needs a refresh.

youtube(): search.list (type=video, videoDuration=short, order=viewCount,
100 units, its own 100-calls/day bucket since 1 Jun 2026) -> videos.list
(snippet, statistics, contentDetails; Shorts = duration <= 180 s) ->
channels.list (subscriberCount, uploads playlist) -> per channel
playlistItems.list + videos.list: the baseline is the median views of the
last 15 Shorts uploads older than 7 days (>= 5 needed). Units are tracked
per Pacific day (fixed UTC-8; the quota resets at midnight PT) in
derived/quota.json; a run stops before 9,000 units or 90 search calls.
Rows get purge_after = observed_at + 30 days (YouTube API policy: refresh
or delete stats of non-authorised channels within 30 days; the dataset is
refreshed by re-running, anything not refreshed is purged). dry_run prints
the exact request URLs with the key redacted; fixture=DIR serves canned
responses (FixtureYouTube), so the parser is covered without the network.
"""
import csv
import io
import json
import os
import re
import sqlite3
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta

from vsp.trends import schema as S
from vsp.trends import store

RESNAPSHOT_MIN_GROWTH = 0.10
RESNAPSHOT_MAX_AGE_DAYS = 7
REFRESH_WITHIN_DAYS = 7
MAX_CAPTION_TAGS = 5            # Instagram allows 5 hashtags per post (Dec 2025)

YT_BASE = "https://www.googleapis.com/youtube/v3/"
YT_ENV_KEY = "VSP_YT_API_KEY"
YT_COSTS = {"search": 100, "videos": 1, "channels": 1, "playlistItems": 1}
YT_UNIT_STOP = 9000
YT_SEARCH_STOP = 90
YT_DAILY_UNITS = 10000
YT_DAILY_SEARCH = 100
YT_DAY_OFFSET_H = 8             # quota day = Pacific (fixed UTC-8)
SHORT_MAX_S = 180
BASELINE_UPLOADS = 15
YT_RETENTION_DAYS = S.YT_RETENTION_DAYS


class ImportFailed(ValueError):
    """Input that cannot be imported at all (missing DB, bad file)."""


class NotConfigured(RuntimeError):
    """A credential / config is missing (exit 2)."""


class QuotaStop(RuntimeError):
    """The daily YouTube budget is (nearly) used up (exit 3)."""


# -------------------------------------------------------------- files
def read_records(path, stdin=None):
    """-> (records, fmt). JSON (object, list or {"observations": [...]}),
    JSONL (a bad line becomes {"__error__": ...}) or CSV (header row;
    dotted headers such as creator.handle nest)."""
    if path == "-":
        text = (stdin or sys.stdin).read()
        ext = ""
    else:
        try:
            with open(path, encoding="utf-8-sig") as f:
                text = f.read()
        except OSError as e:
            raise ImportFailed(f"cannot read {path}: {e}")
        ext = os.path.splitext(path)[1].lower()
    body = text.strip()
    if not body:
        return [], "empty"
    if ext == ".csv" or (ext not in (".json", ".jsonl") and body[0] not in "[{"):
        rows = list(csv.DictReader(io.StringIO(text)))
        out = []
        for r in rows:
            out.append({str(k).strip(): v.strip() for k, v in r.items()
                        if k is not None and isinstance(v, str) and v.strip() != ""})
        return out, "csv"
    if ext != ".jsonl":
        try:
            obj = json.loads(body)
        except ValueError:
            obj = None
        if isinstance(obj, list):
            return obj, "json"
        if isinstance(obj, dict):
            for k in ("observations", "items", "data", "rows"):
                if isinstance(obj.get(k), list):
                    return obj[k], "json"
            return [obj], "json"
        if ext == ".json":
            raise ImportFailed(f"{path}: not valid JSON")
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError as e:
            obj = {"__error__": f"line {i}: invalid JSON ({e})"}
        out.append(obj)
    return out, "jsonl"


# -------------------------------------------------------- research DB
SOURCE_MAP = {"ig_bd": "ig_graph_bd", "business_discovery": "ig_graph_bd",
              "bd": "ig_graph_bd", "ig_hashtag_top": "ig_graph_hashtag",
              "ig_hashtag_recent": "ig_graph_hashtag", "hashtag": "ig_graph_hashtag"}
WANTED_COLS = ("platform", "media_id", "url", "username", "niche", "like_count", "views",
               "comments", "hook_text", "caption", "source", "source_query", "posted_at",
               "analyzed_at", "last_seen_at", "purge_after", "is_own", "media_audio_type",
               "notes")
_FOLLOWERS_RE = re.compile(r"([\d,]+) followers\)")


def map_source(src, is_own=0):
    """research-DB source -> (dataset source | None, skip reason | None)."""
    if is_own:
        return None, "own reel (measured by vsp.feedback)"
    s = (src or "").strip().lower()
    if not s:
        return None, "legacy row without a source"
    if s.startswith("vendor:"):
        return None, "vendor row (possible scraping; research doc §7)"
    if s == "ig_own":
        return None, "own reel (measured by vsp.feedback)"
    if s in SOURCE_MAP:
        return SOURCE_MAP[s], None
    if s.startswith("ig_hashtag") or s.startswith("hashtag"):
        return "ig_graph_hashtag", None
    if s.startswith("yt_"):
        return "yt_data_api", None
    if s.startswith("import:"):
        return "import", None
    return None, f"unknown source {s!r}"


def _followers_from_notes(notes):
    m = _FOLLOWERS_RE.search(notes or "")
    return int(m.group(1).replace(",", "")) if m else None


def _caption_tags(caption, query=None):
    tags = []
    if query and str(query).startswith("#"):
        tags.append(str(query)[1:])
    for t in re.findall(r"#(\w+)", caption or ""):
        if t.lower().startswith("vsp") and re.fullmatch(r"vsp-?\w*", t.lower()):
            continue
        if t.lower() not in [x.lower() for x in tags]:
            tags.append(t)
    return tags[:MAX_CAPTION_TAGS]


def _grew(prev, rec):
    """True when any known metric grew by >= RESNAPSHOT_MIN_GROWTH."""
    pm, nm = prev.get("metrics") or {}, rec.get("metrics") or {}
    for k in ("views", "likes", "comments"):
        a, b = pm.get(k), nm.get(k)
        if isinstance(b, int) and (not isinstance(a, int) or
                                   (a == 0 and b > 0) or
                                   (a > 0 and (b - a) / float(a) >= RESNAPSHOT_MIN_GROWTH)):
            return True
    return False


def _needs_snapshot(prev, rec, now):
    if prev is None:
        return True
    if _grew(prev, rec):
        return True
    age = S.parse_time(prev.get("observed_at"))
    if age is None or (S.utc(now) - age).days >= RESNAPSHOT_MAX_AGE_DAYS:
        return True
    pa = S.parse_time(((prev.get("retention") or {}).get("purge_after")))
    na = S.parse_time(((rec.get("retention") or {}).get("purge_after")))
    if pa is not None and na is not None and na > pa and \
            pa <= S.utc(now) + timedelta(days=REFRESH_WITHIN_DAYS):
        return True
    return False


def import_ingest(d, db_path, now, days=30):
    """See module doc. -> report."""
    from vsp.ingest.util import parse_ts
    store.require(d)
    if not db_path or not os.path.isfile(db_path) or os.path.getsize(db_path) == 0:
        raise ImportFailed(f"research DB not found at {db_path} (VSP_VIRAL_DB / --db); "
                           f"create it with `python3 -m vsp.ingest init-db`")
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        cols = [r[1] for r in con.execute("PRAGMA table_info(reels)")]
        if "url" not in cols:
            raise ImportFailed(f"{db_path}: no reels table with a url column")
        sel = [c for c in WANTED_COLS if c in cols]
        rows = [dict(r) for r in con.execute(f"SELECT {', '.join(sel)} FROM reels ORDER BY "
                                             f"{'posted_at, ' if 'posted_at' in cols else ''}url")]
    finally:
        con.close()
    cutoff = S.utc(now) - timedelta(days=days)
    rep = {"db": db_path, "read": len(rows), "candidates": 0, "skipped": {},
           "rejected": [], "unchanged": 0, "creators": {}}
    by_user = {}
    for r in rows:
        if r.get("username") and not r.get("is_own"):
            by_user.setdefault(r["username"].strip().lower(), []).append(r)
    baselines = {}
    for user, urows in sorted(by_user.items()):
        elig = []
        for r in urows:
            t = parse_ts(r.get("posted_at"))
            if isinstance(r.get("views"), int) and t is not None and \
                    (S.utc(now) - t).days >= 7:
                elig.append((t, r["views"]))
        elig.sort(reverse=True)
        vals = [v for _, v in elig[:30]]
        fol = [f for f in (_followers_from_notes(r.get("notes")) for r in
                           sorted(urows, key=lambda r: r.get("analyzed_at") or ""))
               if f is not None]
        baselines[user] = {"median": int(statistics.median(vals)) if len(vals) >= 5 else None,
                           "n": len(vals), "followers": fol[-1] if fol else None,
                           "purge_after": max([r.get("purge_after") or "" for r in urows]) or None}
    merged = store.merge_snapshots(store.load_snapshots(d))
    recs = []
    for r in rows:
        src, why = map_source(r.get("source"), r.get("is_own"))
        if src is None:
            rep["skipped"][why] = rep["skipped"].get(why, 0) + 1
            continue
        seen = parse_ts(r.get("last_seen_at")) or parse_ts(r.get("analyzed_at"))
        if seen is not None and seen < cutoff:
            rep["skipped"]["older than --days"] = rep["skipped"].get("older than --days", 0) + 1
            continue
        rep["candidates"] += 1
        user = (r.get("username") or "").strip().lower() or None
        base = baselines.get(user) or {}
        at = (r.get("media_audio_type") or "").upper()
        raw = {"platform": (r.get("platform") or "instagram").lower(), "permalink": r["url"],
               "post_id": r.get("media_id"), "source": src, "analyst": "api",
               "observed_at": S.iso(seen) if seen else None,
               "posted_at": S.iso(parse_ts(r.get("posted_at"))) if r.get("posted_at") else None,
               "creator": {"handle": user, "followers": base.get("followers"),
                           "median_views_recent": base.get("median"),
                           "baseline_n": base.get("n") if user else None},
               "metrics": {"views": r.get("views"), "likes": r.get("like_count"),
                           "comments": r.get("comments")},
               "niche": r.get("niche"),
               "hook": {"first_words": S.first_words(r.get("hook_text"))},
               "audio": {"type": {"MUSIC": "licensed_music",
                                  "ORIGINAL_SOUND": "original_sound"}.get(at)},
               "trend_keys": ["tag:" + t for t in _caption_tags(r.get("caption"),
                                                                 r.get("source_query"))],
               "retention": {"purge_after": S.iso(parse_ts(r.get("purge_after")))
                             if r.get("purge_after") else None}}
        rec, errs = S.normalize_observation(raw, now=now)
        if errs:
            rep["rejected"].append({"permalink": r.get("url"), "errors": errs})
            continue
        if not _needs_snapshot(merged.get(rec["obs_id"]), rec, now):
            rep["unchanged"] += 1
            continue
        recs.append(rec)
    res = store.add_observations(d, recs, now) if recs else \
        {"new": 0, "updated": 0, "refreshed": 0, "unchanged": 0, "file": None}
    rep["unchanged"] += res.pop("unchanged", 0)
    rep.update(res)
    snaps = []
    for user, b in sorted(baselines.items()):
        if b["followers"] is None and b["median"] is None:
            continue
        snap, errs = S.normalize_creator({
            "platform": "instagram", "handle": user, "followers": b["followers"],
            "median_views_recent": b["median"], "baseline_n": b["n"],
            "snapshot_at": S.iso(now), "source": "ig_graph_bd",
            "retention": {"purge_after": S.iso(parse_ts(b["purge_after"]))
                          if b["purge_after"] else None}}, now=now)
        if not errs:
            snaps.append(snap)
    rep["creators"] = store.upsert_creators(d, snaps) if snaps else {"new": 0}
    return rep


# ------------------------------------------------------------- YouTube
def yt_url(endpoint, params, key):
    q = urllib.parse.urlencode(list(params.items()) + [("key", key)], safe=",:")
    return f"{YT_BASE}{endpoint}?{q}"


def redact(url):
    return re.sub(r"([?&]key=)[^&]*", r"\1REDACTED", url)


def parse_duration(value):
    """ISO 8601 'PT1M5S' -> 65 (None if unparseable)."""
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", str(value or ""))
    if not m or not any(m.groups()):
        return None
    d, h, mi, s = (int(x) if x else 0 for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def _quota_day(now):
    return (S.utc(now) - timedelta(hours=YT_DAY_OFFSET_H)).strftime("%Y-%m-%d")


class Quota:
    """YouTube units / search calls of the current Pacific day."""

    def __init__(self, d, now, persist=True):
        self.d, self.now, self.persist = d, now, persist
        self.doc = store.load_quota(d) if d else {}
        y = self.doc.get("youtube") or {}
        day = _quota_day(now)
        if y.get("day") != day:
            y = {"day": day, "units": 0, "search_calls": 0, "runs": []}
        y["day_basis"] = "Pacific day (fixed UTC-8): YouTube quota resets at midnight PT"
        y["limits"] = {"units_stop": YT_UNIT_STOP, "search_stop": YT_SEARCH_STOP,
                       "daily_units": YT_DAILY_UNITS, "daily_search_calls": YT_DAILY_SEARCH}
        self.y = y
        self.run_units = self.run_search = 0

    def charge(self, endpoint):
        cost = YT_COSTS[endpoint]
        if self.y["units"] + cost > YT_UNIT_STOP:
            raise QuotaStop(f"YouTube units: {self.y['units']} used today, a {endpoint}.list "
                            f"call ({cost}) would pass the {YT_UNIT_STOP} stop")
        if endpoint == "search" and self.y["search_calls"] + 1 > YT_SEARCH_STOP:
            raise QuotaStop(f"YouTube search.list: {self.y['search_calls']} calls today "
                            f"(stop at {YT_SEARCH_STOP} of the 100/day bucket)")
        self.y["units"] += cost
        self.run_units += cost
        if endpoint == "search":
            self.y["search_calls"] += 1
            self.run_search += 1

    def save(self, query, stopped=None):
        self.y["runs"] = (self.y.get("runs") or [])[-49:] + [
            {"at": S.iso(self.now), "query": query, "units": self.run_units,
             "search_calls": self.run_search, "stopped": stopped}]
        if self.persist and self.d:
            self.doc["youtube"] = self.y
            self.doc["schema_version"] = S.SCHEMA_VERSION
            store.save_quota(self.d, self.doc)


def http_transport(url, timeout=30):
    """GET -> parsed JSON. A 403 quotaExceeded raises QuotaStop."""
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": "vsp.trends/1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            body = {}
        reasons = [x.get("reason") for x in ((body.get("error") or {}).get("errors") or [])]
        if e.code == 403 and any(r in ("quotaExceeded", "dailyLimitExceeded",
                                       "rateLimitExceeded") for r in reasons):
            raise QuotaStop(f"YouTube API: {', '.join(r for r in reasons if r)}")
        raise ImportFailed(f"YouTube API HTTP {e.code} on {redact(url)}: "
                           f"{(body.get('error') or {}).get('message', e.reason)}")
    except urllib.error.URLError as e:
        raise ImportFailed(f"YouTube API unreachable ({e.reason}) for {redact(url)}")


class FixtureYouTube:
    """Serves canned Data API responses from DIR (search.list.json,
    videos.list.json, channels.list.json, playlistItems.list.json — see
    vsp.trends.fixtures.youtube_fixture). Records every URL in .calls."""

    def __init__(self, d):
        self.d = d
        self.calls = []

    def _load(self, name):
        p = os.path.join(self.d, name)
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError) as e:
            raise ImportFailed(f"YouTube fixture {p}: {e}")

    def __call__(self, url, timeout=None):
        self.calls.append(redact(url))
        parts = urllib.parse.urlsplit(url)
        endpoint = parts.path.rsplit("/", 1)[-1]
        params = dict(urllib.parse.parse_qsl(parts.query))
        if endpoint == "search":
            body = self._load("search.list.json")
            if isinstance(body, dict) and "items" not in body:
                body = body.get(params.get("q"), {"items": []})
            return body
        if endpoint in ("videos", "channels"):
            pool = {it["id"]: it for it in self._load(f"{endpoint}.list.json").get("items", [])}
            ids = [x for x in params.get("id", "").split(",") if x]
            return {"items": [pool[i] for i in ids if i in pool]}
        if endpoint == "playlistItems":
            return self._load("playlistItems.list.json").get(params.get("playlistId"),
                                                            {"items": []})
        raise ImportFailed(f"YouTube fixture: no canned response for {endpoint}")


def _yt_int(v):
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _title_bits(title, description):
    tags = []
    for t in re.findall(r"#(\w+)", f"{title or ''} {description or ''}"):
        if t.lower() not in [x.lower() for x in tags]:
            tags.append(t)
    words = re.sub(r"#\w+", " ", title or "")
    return S.first_words(" ".join(words.split())), tags[:MAX_CAPTION_TAGS]


def _classify_query(query):
    from vsp import config
    if config.REPO not in sys.path:
        sys.path.insert(0, config.REPO)
    try:
        from vsp import router
        n = router.route(query, pack=False).get("niche")
    except Exception:  # noqa: BLE001
        return None
    return None if n in (None, "default") else n


def _dry_templates(query, region, max_results, published_after):
    k = "REDACTED"
    search = yt_url("search", {"part": "snippet", "type": "video", "videoDuration": "short",
                               "order": "viewCount", "q": query, "maxResults": max_results,
                               "publishedAfter": published_after, "regionCode": region}, k)
    return [search,
            f"{YT_BASE}videos?part=snippet,statistics,contentDetails&id={{video ids from "
            f"search}}&maxResults=50&key={k}",
            f"{YT_BASE}channels?part=snippet,statistics,contentDetails&id={{channel ids}}"
            f"&maxResults=50&key={k}",
            f"{YT_BASE}playlistItems?part=contentDetails&playlistId={{uploads playlist, per "
            f"channel}}&maxResults=50&key={k}",
            f"{YT_BASE}videos?part=snippet,statistics,contentDetails&id={{last 50 uploads, "
            f"per channel}}&maxResults=50&key={k}"]


def youtube(d, now, query, region="US", max_results=25, days=7, niche=None, dry_run=False,
            fixture=None, api_key=None, transport=None, env=None):
    """See module doc. -> report ("stopped" is set when the quota stop hit)."""
    e = os.environ if env is None else env
    key = api_key or e.get(YT_ENV_KEY) or ""
    if not dry_run:
        store.require(d)
        if not key and not fixture and transport is None:
            raise NotConfigured(f"{YT_ENV_KEY} is not set (a YouTube Data API v3 key from "
                                f"Google Cloud; see docs/ws-trends-notes.md)")
    region = (region or "US").upper()
    max_results = max(1, min(50, int(max_results or 25)))
    published_after = S.iso(S.utc(now) - timedelta(days=days))
    niche = S.norm_niche(niche) or _classify_query(query)
    rep = {"query": query, "region": region, "niche": niche, "dry_run": bool(dry_run),
           "requests": [], "units": 0, "search_calls": 0, "videos": 0, "shorts": 0,
           "channels": 0, "baselines": 0, "rejected": [], "stopped": None}
    if dry_run and not fixture and transport is None:
        rep["requests"] = _dry_templates(query, region, max_results, published_after)
        rep["estimated_units"] = YT_COSTS["search"] + 2 + 2 * max_results
        return rep
    fetch = transport or (FixtureYouTube(fixture) if fixture else http_transport)
    quota = Quota(d if store.is_initialized(d) else None, now, persist=not dry_run)
    shorts, snaps = [], {}

    def call(endpoint, params):
        quota.charge(endpoint)
        url = yt_url(endpoint, params, key or "REDACTED")
        rep["requests"].append(redact(url))
        return fetch(url)
    try:
        found = call("search", {"part": "snippet", "type": "video", "videoDuration": "short",
                                "order": "viewCount", "q": query, "maxResults": max_results,
                                "publishedAfter": published_after, "regionCode": region})
        ids = [it["id"]["videoId"] for it in found.get("items") or []
               if isinstance(it.get("id"), dict) and it["id"].get("videoId")]
        vids = call("videos", {"part": "snippet,statistics,contentDetails",
                               "id": ",".join(ids), "maxResults": 50}).get("items", []) \
            if ids else []
        rep["videos"] = len(vids)
        for v in vids:
            dur = parse_duration((v.get("contentDetails") or {}).get("duration"))
            if dur is not None and dur <= SHORT_MAX_S:
                shorts.append((v, dur))
        rep["shorts"] = len(shorts)
        ch_ids = sorted({(v.get("snippet") or {}).get("channelId") for v, _ in shorts} - {None})
        chans = call("channels", {"part": "snippet,statistics,contentDetails",
                                  "id": ",".join(ch_ids), "maxResults": 50}).get("items", []) \
            if ch_ids else []
        rep["channels"] = len(chans)
        for ch in sorted(chans, key=lambda c: c.get("id") or ""):
            snaps[ch["id"]] = _channel_snapshot(ch, now)
        for ch in sorted(chans, key=lambda c: c.get("id") or ""):
            up = ((ch.get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads")
            if not up:
                continue
            items = call("playlistItems", {"part": "contentDetails", "playlistId": up,
                                           "maxResults": 50}).get("items", [])
            up_ids = [((it.get("contentDetails") or {}).get("videoId")) for it in items][:50]
            up_ids = [x for x in up_ids if x]
            if not up_ids:
                continue
            uv = call("videos", {"part": "snippet,statistics,contentDetails",
                                 "id": ",".join(up_ids), "maxResults": 50}).get("items", [])
            med, n = _upload_baseline(uv, now)
            snaps[ch["id"]]["median_views_recent"] = med
            snaps[ch["id"]]["baseline_n"] = n
            if med:
                rep["baselines"] += 1
    except QuotaStop as ex:
        rep["stopped"] = f"quota: {ex}"
    rep["units"], rep["search_calls"] = quota.run_units, quota.run_search
    rep["quota_today"] = {"day": quota.y["day"], "units": quota.y["units"],
                          "search_calls": quota.y["search_calls"]}
    recs = []
    for v, dur in shorts:
        rec, errs = _short_record(v, dur, snaps, now, niche, region, days)
        if rec is None:
            continue
        if errs:
            rep["rejected"].append({"video": v.get("id"), "errors": errs})
        else:
            recs.append(rec)
    rep["observations"] = len(recs)
    if dry_run:
        return rep
    quota.save(query, rep["stopped"])
    res = store.add_observations(d, recs, now) if recs else {"new": 0, "updated": 0,
                                                              "refreshed": 0, "unchanged": 0}
    rep.update({k: res[k] for k in ("new", "updated", "refreshed", "unchanged")})
    cs = []
    for cid in sorted(snaps):
        snap, errs = S.normalize_creator(snaps[cid], now=now)
        if not errs:
            cs.append(snap)
    rep["creators"] = store.upsert_creators(d, cs) if cs else {"new": 0}
    return rep


def _channel_handle(ch):
    cu = ((ch.get("snippet") or {}).get("customUrl") or "").strip()
    if cu:
        return S.norm_handle(cu)
    return "channel/" + ch.get("id", "")


def _channel_snapshot(ch, now):
    st = ch.get("statistics") or {}
    subs = None if st.get("hiddenSubscriberCount") else _yt_int(st.get("subscriberCount"))
    return {"platform": "youtube", "handle": _channel_handle(ch), "followers": subs,
            "median_views_recent": None, "baseline_n": 0, "snapshot_at": S.iso(now),
            "source": "yt_data_api",
            "retention": {"purge_after": S.iso(S.utc(now) + timedelta(days=YT_RETENTION_DAYS))}}


def _upload_baseline(videos, now):
    """(median, n) over the last BASELINE_UPLOADS Shorts older than 7 days."""
    elig = []
    for v in videos:
        dur = parse_duration((v.get("contentDetails") or {}).get("duration"))
        t = S.parse_time((v.get("snippet") or {}).get("publishedAt"))
        views = _yt_int((v.get("statistics") or {}).get("viewCount"))
        if dur is None or dur > SHORT_MAX_S or t is None or views is None:
            continue
        if (S.utc(now) - t).days < 7:
            continue
        elig.append((t, views))
    elig.sort(reverse=True)
    vals = [x for _, x in elig[:BASELINE_UPLOADS]]
    if len(vals) < 5:
        return None, len(vals)
    return int(statistics.median(vals)), len(vals)


def _short_record(v, dur, snaps, now, niche, region, days):
    sn, st = v.get("snippet") or {}, v.get("statistics") or {}
    t = S.parse_time(sn.get("publishedAt"))
    if t is None or (S.utc(now) - t).days > days:
        return None, []
    snap = snaps.get(sn.get("channelId")) or {}
    fw, tags = _title_bits(sn.get("title"), sn.get("description"))
    lang = (sn.get("defaultAudioLanguage") or sn.get("defaultLanguage") or "").strip() or None
    raw = {"platform": "youtube", "permalink": f"https://www.youtube.com/shorts/{v.get('id')}",
           "post_id": v.get("id"), "posted_at": S.iso(t), "observed_at": S.iso(now),
           "source": "yt_data_api", "analyst": "api",
           "creator": {"handle": snap.get("handle"), "followers": snap.get("followers"),
                       "median_views_recent": snap.get("median_views_recent"),
                       "baseline_n": snap.get("baseline_n")},
           "metrics": {"views": _yt_int(st.get("viewCount")), "likes": _yt_int(st.get("likeCount")),
                       "comments": _yt_int(st.get("commentCount"))},
           "niche": niche, "language": lang, "region": region, "duration_s": dur,
           "hook": {"first_words": fw}, "trend_keys": ["tag:" + x for x in tags],
           "retention": {"purge_after": S.iso(S.utc(now) + timedelta(days=YT_RETENTION_DAYS))}}
    return S.normalize_observation(raw, now=now)


# ------------------------------------------------------ TikTok CC lists
_CC_ALIASES = {"rank": ("rank", "#", "position"),
               "hashtag": ("hashtag", "tag", "hashtags"),
               "song": ("song", "sound", "music", "track", "song_title"),
               "artist": ("artist", "author"),
               "posts": ("posts", "videos", "video_count", "post_count", "publish_cnt"),
               "growth": ("growth", "change", "growth_pct", "trend"),
               "region": ("region", "country", "country_code"),
               "industry": ("industry", "category"), "date": ("date", "day", "period_end")}


def _cc_get(row, field):
    low = {str(k).strip().lower(): v for k, v in row.items()}
    for a in _CC_ALIASES[field]:
        v = low.get(a)
        if v not in (None, ""):
            return v
    return None


def _growth(v):
    if v is None:
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    m = re.search(r"([+-]?\d+(?:\.\d+)?)", str(v).replace(",", ""))
    return float(m.group(1)) if m else None


def tiktok_cc(d, path, now, region=None, industry=None, date=None, stdin=None):
    """Hand-copied Creative Center rows -> signals. -> report."""
    from vsp.ingest.util import to_int
    store.require(d)
    rows, fmt = read_records(path, stdin=stdin)
    day = date or store.day_str(now)
    recs, rejected = [], []
    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict) or row.get("__error__"):
            rejected.append({"row": i, "errors": [(row or {}).get("__error__", "not an object")
                                                  if isinstance(row, dict) else "not an object"]})
            continue
        tag, song = _cc_get(row, "hashtag"), _cc_get(row, "song")
        if tag:
            kind, name = "tag", "#" + str(tag).strip().lstrip("#")
            key = S.norm_trend_key("tag:" + str(tag))
        elif song:
            artist = _cc_get(row, "artist")
            kind, name = "sound", str(song).strip() + (f" - {artist}" if artist else "")
            key = S.norm_trend_key("sound:" + (S.slug(song, 64) or ""))
        else:
            rejected.append({"row": i, "errors": ["needs a hashtag or a song column"]})
            continue
        if not key:
            rejected.append({"row": i, "errors": [f"{name!r} is not usable as a trend key "
                                                  f"(generic tags such as #fyp are noise)"]})
            continue
        rec, errs = S.normalize_signal({
            "platform": "tiktok", "source": "tiktok_creative_center", "kind": kind, "key": key,
            "name": name[:80], "rank": to_int(_cc_get(row, "rank")),
            "posts": to_int(_cc_get(row, "posts")), "growth_pct": _growth(_cc_get(row, "growth")),
            "region": _cc_get(row, "region") or region, "industry": _cc_get(row, "industry")
            or industry, "date": str(_cc_get(row, "date") or day)[:10],
            "observed_at": S.iso(now)}, now=now)
        if errs:
            rejected.append({"row": i, "errors": errs})
        else:
            recs.append(rec)
    res = store.add_signals(d, recs, now) if recs else {"new": 0, "updated": 0,
                                                         "unchanged": 0, "files": []}
    return dict(res, rows=len(rows), format=fmt, accepted=len(recs), rejected=rejected)
