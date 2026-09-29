"""Outlier scoring with a small/medium-creator focus.

    score_all(observations, creators, now) -> [row]   (sorted, deterministic)
    creator_baseline(obs, creators, by_creator, now) -> (median, n, from)
    band_for(multiple), inspiration(multiple, tier, age_days, replicability, basis)
    outlier_rows(rows) -> the rows written to derived/outliers.jsonl

Per observation (latest merged snapshot):
  outlier_x = views / the creator's median views of recent posts. The
              baseline needs >= 5 posts, each older than 7 days (young posts
              are still growing), at most the 30 most recent. Taken from
              the observation's own creator block, else the creator snapshot
              (creators.jsonl), else computed from that creator's other
              observations.                         basis "median"
  reach_x   = views / followers                    basis "followers"
  eng_x     = ((likes + comments) / followers) / the tier's typical
              engagement rate — the proxy for rows without views (Instagram
              hashtag rows)                         basis "engagement"
  vph       = views per hour since posting
  multiple  = the first available of outlier_x, reach_x, eng_x; no multiple
              -> band "unscored"
Bands: < 3 normal, 3-5 notable, 5-10 outlier, 10-50 breakout, >= 50 mega.
inspiration_score in [0, 1] = saturating(multiple) x tier weight (small and
medium creators 1.0 / 0.9, macro 0.6, mega 0.3: a small account's outlier
means the FORMAT won, not the audience) x recency (halves every 7 days) x
replicability / 5 x basis weight (proxies count less).
Sources and grades: docs/research/trend-discovery-rules.md.
"""
import math
import statistics

from vsp.trends import schema as S

BASELINE_MIN_POSTS = 5
BASELINE_MIN_AGE_DAYS = 7
BASELINE_MAX_POSTS = 30
BAND_BOUNDS = (("normal", 0.0, 3.0), ("notable", 3.0, 5.0), ("outlier", 5.0, 10.0),
               ("breakout", 10.0, 50.0), ("mega", 50.0, None))
OUTLIER_BANDS = ("notable", "outlier", "breakout", "mega")
TIER_WEIGHTS = {"emerging": 1.0, "nano": 1.0, "micro": 1.0, "mid": 0.9,
                "macro": 0.6, "mega": 0.3}
UNKNOWN_TIER_WEIGHT = 0.7
RECENCY_HALF_LIFE_DAYS = 7.0
MULTIPLE_CAP = 50.0
DEFAULT_REPLICABILITY = 3
BASIS_WEIGHTS = {"median": 1.0, "followers": 0.8, "engagement": 0.6}
# typical (likes + comments) / followers by tier. Instagram nano 1.78 % and
# macro/mega 0.33-0.35 %, TikTok nano 11.6 % vs 6.8 % (HypeAuditor 2026, S);
# micro / mid are interpolated (A).
ENGAGEMENT_BASELINE = {
    "instagram": {"emerging": 0.0178, "nano": 0.0178, "micro": 0.0100, "mid": 0.0060,
                  "macro": 0.0035, "mega": 0.0033},
    "tiktok": {"emerging": 0.116, "nano": 0.116, "micro": 0.100, "mid": 0.085,
               "macro": 0.070, "mega": 0.068},
}
MAX_OUTLIER_ROWS = 2000


def band_for(multiple):
    if multiple is None:
        return "unscored"
    for name, lo, hi in BAND_BOUNDS:
        if multiple >= lo and (hi is None or multiple < hi):
            return name
    return "normal"


def inspiration(multiple, tier, age_days, replicability, basis):
    """[0, 1]; 0 for an unscored row."""
    if multiple is None or basis not in BASIS_WEIGHTS:
        return 0.0
    m = min(1.0, math.log10(1.0 + max(0.0, multiple)) / math.log10(1.0 + MULTIPLE_CAP))
    tw = TIER_WEIGHTS.get(tier, UNKNOWN_TIER_WEIGHT)
    rw = 0.5 ** (max(0.0, age_days or 0.0) / RECENCY_HALF_LIFE_DAYS)
    rp = (replicability if isinstance(replicability, int) else DEFAULT_REPLICABILITY) / 5.0
    return round(m * tw * rw * rp * BASIS_WEIGHTS[basis], 4)


def _days_between(later, earlier):
    a, b = S.parse_time(later), S.parse_time(earlier)
    if a is None or b is None:
        return None
    return (a - b).total_seconds() / 86400.0


def _creator_id(o):
    h = (o.get("creator") or {}).get("handle")
    return (o.get("platform"), h) if h else None


def index_by_creator(observations):
    out = {}
    for o in observations:
        cid = _creator_id(o)
        if cid:
            out.setdefault(cid, []).append(o)
    return out


def median_of_posts(posts, now, exclude_id=None):
    """(median, n) over posts with views, older than BASELINE_MIN_AGE_DAYS,
    the BASELINE_MAX_POSTS most recent; median None when n < 5."""
    elig = []
    for p in posts:
        if p.get("obs_id") == exclude_id:
            continue
        v = (p.get("metrics") or {}).get("views")
        age = _days_between(S.iso(now), p.get("posted_at"))
        if isinstance(v, int) and age is not None and age >= BASELINE_MIN_AGE_DAYS:
            elig.append((p.get("posted_at"), p.get("obs_id"), v))
    elig.sort(reverse=True)
    vals = [v for _, _, v in elig[:BASELINE_MAX_POSTS]]
    if len(vals) < BASELINE_MIN_POSTS:
        return None, len(vals)
    return float(statistics.median(vals)), len(vals)


def creator_baseline(o, creators, by_creator, now):
    """-> (median, n, from) — from: inline | snapshot | observations | None."""
    cr = o.get("creator") or {}
    med, n = cr.get("median_views_recent"), cr.get("baseline_n")
    if isinstance(med, int) and isinstance(n, int) and n >= BASELINE_MIN_POSTS and med > 0:
        return float(med), n, "inline"
    cid = _creator_id(o)
    if cid:
        snap = creators.get(cid)
        if snap:
            med, n = snap.get("median_views_recent"), snap.get("baseline_n")
            if isinstance(med, int) and isinstance(n, int) and \
                    n >= BASELINE_MIN_POSTS and med > 0:
                return float(med), n, "snapshot"
        med, n = median_of_posts(by_creator.get(cid, []), now, exclude_id=o.get("obs_id"))
        if med:
            return med, n, "observations"
        return None, n, None
    return None, 0, None


def _followers(o, creators):
    f = (o.get("creator") or {}).get("followers")
    if isinstance(f, int):
        return f
    cid = _creator_id(o)
    snap = creators.get(cid) if cid else None
    f = (snap or {}).get("followers")
    return f if isinstance(f, int) else None


def score_one(o, creators, by_creator, now):
    m = o.get("metrics") or {}
    views, likes, comments = m.get("views"), m.get("likes"), m.get("comments")
    followers = _followers(o, creators)
    tier = S.tier_for(followers) if followers is not None else \
        (o.get("creator") or {}).get("tier")
    med, n, frm = creator_baseline(o, creators, by_creator, now)
    outlier_x = round(views / med, 3) if isinstance(views, int) and med else None
    reach_x = round(views / float(followers), 3) \
        if isinstance(views, int) and followers else None
    eng_rate = eng_x = None
    if views is None and followers and (isinstance(likes, int) or isinstance(comments, int)):
        eng_rate = ((likes or 0) + (comments or 0)) / float(followers)
        base = ENGAGEMENT_BASELINE.get(o.get("platform"), ENGAGEMENT_BASELINE["instagram"])
        eng_x = round(eng_rate / base.get(tier or "micro", base["micro"]), 3)
        eng_rate = round(eng_rate, 5)
    if outlier_x is not None:
        multiple, basis = outlier_x, "median"
    elif reach_x is not None:
        multiple, basis = reach_x, "followers"
    elif eng_x is not None:
        multiple, basis = eng_x, "engagement"
    else:
        multiple, basis = None, None
    age = _days_between(S.iso(now), o.get("posted_at"))
    if age is None:
        age = _days_between(S.iso(now), o.get("observed_at"))
    hours = age * 24.0 if age is not None and o.get("posted_at") else None
    vph = round(views / max(1.0, hours), 2) if isinstance(views, int) and hours is not None \
        else None
    return {
        "obs_id": o.get("obs_id"), "platform": o.get("platform"),
        "post_id": o.get("post_id"), "permalink": o.get("permalink"),
        "source": o.get("source"), "niche": o.get("niche"),
        "format_key": o.get("format_key"), "trend_keys": list(o.get("trend_keys") or []),
        "handle": (o.get("creator") or {}).get("handle"), "followers": followers,
        "tier": tier, "small_medium": tier in S.SMALL_MEDIUM_TIERS,
        "views": views, "likes": likes, "comments": comments,
        "baseline_median": round(med, 1) if med else None, "baseline_n": n,
        "baseline_from": frm, "outlier_x": outlier_x, "reach_x": reach_x,
        "eng_rate": eng_rate, "eng_x": eng_x, "vph": vph, "basis": basis,
        "multiple": multiple, "band": band_for(multiple),
        "inspiration_score": inspiration(multiple, tier, age, o.get("replicability"), basis),
        "age_days": round(age, 2) if age is not None else None,
        "posted_at": o.get("posted_at"), "observed_at": o.get("observed_at"),
        "status": "scored" if multiple is not None else "unscored",
    }


def sort_key(r):
    scored = r["status"] == "scored"
    return (0 if scored else 1, -r["inspiration_score"], -(r["multiple"] or 0.0),
            r["obs_id"] or "")


def score_all(observations, creators, now):
    """Score every (merged) observation. -> rows sorted by sort_key."""
    by_creator = index_by_creator(observations)
    rows = [score_one(o, creators or {}, by_creator, now) for o in observations]
    return sorted(rows, key=sort_key)


def outlier_rows(rows):
    """What derived/outliers.jsonl holds: scored rows in a notable-or-higher
    band, best first, capped."""
    out = [r for r in rows if r["status"] == "scored" and r["band"] in OUTLIER_BANDS]
    return out[:MAX_OUTLIER_ROWS]
