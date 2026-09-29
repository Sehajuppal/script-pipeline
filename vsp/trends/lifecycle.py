"""Trend clustering and lifecycle -> derived/trends.json.

    build(observations, score_rows, signals, now) -> doc
    stage_for(first_seen_age, silence_days, total, c7, growth) -> stage
    speed_for(span_days) -> moment | signal | force
    jump_in(stage, evergreen) -> advice

A trend is a trend_key (sound:/format:/tag:/topic:) used by >= 2 distinct
creators (anonymous hashtag rows count one creator per post). A sighting
is dated by posted_at (else observed_at); windows are whole days back from
`now`: 3d = days 0-2, 7d = days 0-6, prev7d = days 7-13, growth =
creators_7d / max(1, creators_prev7d).

Stages, checked in this order (STAGE_RULES, configurable):
  emerging   first_seen <= 7 days ago and >= 2 creators
  rising     growth >= 1.5 and >= 3 creators in 7d
  peak       >= 10 creators in 7d and 0.8 <= growth < 1.5
  saturated  >= 20 creators in 7d and growth < 0.8
  declining  growth <= 0.5, or no sighting for 14 days
  steady     otherwise
Speed (TikTok "Speeds of Culture"): seen < 21 days = moment, 21-180 =
signal, > 180 = force. A format/topic trend that is a signal or force is
"evergreen" (Publicis x TikTok 2026: utility and cultural codes persist).
Aggregate signals (TikTok Creative Center lists) attach to the card with
the same key; keys only seen as signals are listed in `signals_only` to be
verified by watching examples before anything rides them.
"""
import statistics

from vsp.trends import schema as S

STAGE_RULES = {
    "min_creators": 2,
    "emerging_max_age_days": 7,
    "rising_growth": 1.5, "rising_min_7d": 3,
    "peak_min_7d": 10, "peak_growth_lo": 0.8, "peak_growth_hi": 1.5,
    "saturated_min_7d": 20, "saturated_growth": 0.8,
    "declining_growth": 0.5, "declining_silence_days": 14,
}
SPEED_BOUNDS = {"moment_max_days": 21, "signal_max_days": 180}
STAGE_ORDER = ("emerging", "rising", "peak", "steady", "saturated", "declining")
STAGE_VELOCITY = {"emerging": 1.0, "rising": 0.9, "steady": 0.5, "peak": 0.6,
                  "saturated": 0.25, "declining": 0.1}
JUMP_IN = {
    "emerging": "jump in now: it is new; keep 2 of its 4 elements and change 2",
    "rising": "jump in now: it is growing week over week",
    "peak": "only with a twist: combine it with another trend or transplant it "
            "into a new niche",
    "steady": "usable as a base with a twist; watch its growth",
    "saturated": "skip unless it is an evergreen utility format",
    "declining": "skip unless it is an evergreen utility format",
}
EVERGREEN_ADVICE = ("evergreen utility format: usable with a fresh angle, "
                    "not as a trend ride")
MAX_CARDS = 500
MAX_EXAMPLES = 5
RELATED_OVERLAP = 0.8          # Jaccard of two keys' posts: the same trend's elements
MAX_RELATED = 6


def stage_for(first_age, silence, total, c7, growth, rules=None):
    r = rules or STAGE_RULES
    if first_age <= r["emerging_max_age_days"] and total >= r["min_creators"]:
        return "emerging"
    if growth >= r["rising_growth"] and c7 >= r["rising_min_7d"]:
        return "rising"
    if c7 >= r["peak_min_7d"] and r["peak_growth_lo"] <= growth < r["peak_growth_hi"]:
        return "peak"
    if c7 >= r["saturated_min_7d"] and growth < r["saturated_growth"]:
        return "saturated"
    if growth <= r["declining_growth"] or silence >= r["declining_silence_days"]:
        return "declining"
    return "steady"


def speed_for(span_days):
    if span_days < SPEED_BOUNDS["moment_max_days"]:
        return "moment"
    if span_days <= SPEED_BOUNDS["signal_max_days"]:
        return "signal"
    return "force"


def jump_in(stage, evergreen=False):
    if evergreen and stage in ("saturated", "declining"):
        return EVERGREEN_ADVICE
    return JUMP_IN[stage]


def label_for(key):
    kind, _, val = key.partition(":")
    if kind == "tag":
        return "#" + val
    words = val.replace("-", " ").replace("_", " ").replace(".", " ").strip()
    if kind == "sound":
        return f"sound '{words}'"
    if kind == "topic":
        return f"topic '{words}'"
    return f"{words} format"


# ------------------------------------------------------------------ helpers
def _mode(pairs):
    """Most frequent value (ties: higher weight, then alphabetical) of
    [(value, weight)]; None values ignored."""
    counts = {}
    for v, w in pairs:
        if v is None:
            continue
        c, s = counts.get(v, (0, 0.0))
        counts[v] = (c + 1, s + (w or 0.0))
    if not counts:
        return None
    return sorted(counts, key=lambda v: (-counts[v][0], -counts[v][1], str(v)))[0]


def _top(pairs, n):
    counts = {}
    for v, w in pairs:
        if v is None:
            continue
        c, s = counts.get(v, (0, 0.0))
        counts[v] = (c + 1, s + (w or 0.0))
    return sorted(counts, key=lambda v: (-counts[v][0], -counts[v][1], str(v)))[:n]


def _share(values):
    known = [v for v in values if isinstance(v, bool)]
    return (sum(1 for v in known if v) / float(len(known))) if known else 0.0


def _median(values):
    vals = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    return round(float(statistics.median(vals)), 2) if vals else None


def profile(obs_list, weights, exclude_key=None):
    """The card's dominant analysis values (what synth copies)."""
    w = [weights.get(o["obs_id"], 0.0) for o in obs_list]

    def col(fn):
        return [(fn(o), wi) for o, wi in zip(obs_list, w)]
    beats_seq = _mode([(tuple(o["structure"].get("beats") or ()) or None, wi)
                       for o, wi in zip(obs_list, w)])
    tags = _top([(k.split(":", 1)[1], wi) for o, wi in zip(obs_list, w)
                 for k in o.get("trend_keys") or [] if k.startswith("tag:") and
                 k != exclude_key], 5)
    return {
        "format_key": _mode(col(lambda o: o.get("format_key"))),
        "archetype": _mode(col(lambda o: o["hook"].get("archetype"))),
        "archetypes": _top(col(lambda o: o["hook"].get("archetype")), 3),
        "frame0_visual": _mode(col(lambda o: o["hook"].get("frame0_visual"))),
        "emotion": _mode(col(lambda o: o.get("emotion"))),
        "participation": _mode(col(lambda o: o.get("participation"))),
        "cta": _mode(col(lambda o: o.get("cta"))),
        "audio_type": _mode(col(lambda o: o["audio"].get("type"))),
        "sound_title": _mode(col(lambda o: o["audio"].get("sound_title"))),
        "vibe": _mode(col(lambda o: o.get("vibe"))),
        "replicability": _median([o.get("replicability") for o in obs_list]),
        "production_cost": _mode(col(lambda o: o.get("production_cost"))),
        "needs_real_person": _share([o.get("needs_real_person") for o in obs_list]) >= 0.5,
        "duration_s": _median([o.get("duration_s") for o in obs_list]),
        "cuts_per_10s": _median([o["structure"].get("cuts_per_10s") for o in obs_list]),
        "payoff_reveal": _share([o["structure"].get("payoff_reveal") for o in obs_list]) >= 0.5,
        "loop": _share([o["structure"].get("loop") for o in obs_list]) >= 0.5,
        "series": _share([o["structure"].get("series") for o in obs_list]) >= 0.5,
        "beats": list(beats_seq)[:8] if beats_seq else [],
        "tags": tags,
    }


def _sighting_day(o):
    t = S.parse_time(o.get("posted_at")) or S.parse_time(o.get("observed_at"))
    return t.date() if t else None


def _creator_of(o):
    h = (o.get("creator") or {}).get("handle")
    return f"{o.get('platform')}:{h}" if h else f"{o.get('platform')}:post:{o.get('post_id')}"


def _signal_summary(sigs):
    latest = sorted(sigs, key=lambda s: (s.get("date") or "", s.get("rank") or 0))[-1]
    ranks = [s["rank"] for s in sigs if isinstance(s.get("rank"), int)]
    return {"best_rank": min(ranks) if ranks else None, "posts": latest.get("posts"),
            "growth_pct": latest.get("growth_pct"),
            "regions": sorted({s.get("region") for s in sigs if s.get("region")}),
            "dates": sorted({s["date"] for s in sigs if s.get("date")})[-10:],
            "source": latest.get("source")}


def card_for(key, obs_list, rows_by_id, today):
    """One trend card, or None below the 2-creator threshold."""
    sights = []
    for o in obs_list:
        day = _sighting_day(o)
        if day is not None and day <= today:
            sights.append((day, _creator_of(o), o))
    creators = {c for _, c, _ in sights}
    if len(creators) < STAGE_RULES["min_creators"]:
        return None

    def window(lo, hi):
        return len({c for day, c, _ in sights if lo <= (today - day).days <= hi})
    first = min(day for day, _, _ in sights)
    last = max(day for day, _, _ in sights)
    c7, p7, c3 = window(0, 6), window(7, 13), window(0, 2)
    growth = round(c7 / float(max(1, p7)), 3)
    stage = stage_for((today - first).days, (today - last).days, len(creators), c7, growth)
    span = (last - first).days
    speed = speed_for(span)
    kind = key.split(":", 1)[0]
    evergreen = kind in ("format", "topic") and speed in ("signal", "force")
    label = label_for(key)
    used = [o for _, _, o in sights]
    rows = [rows_by_id.get(o["obs_id"]) for o in used]
    weights = {r["obs_id"]: r["inspiration_score"] for r in rows if r}
    ox = [r["outlier_x"] for r in rows if r and r.get("outlier_x") is not None]
    mult = [r["multiple"] for r in rows if r and r.get("multiple") is not None]
    tiers = {}
    for r in rows:
        if r and r.get("tier"):
            tiers[_creator_of_row(r)] = r["tier"]
    sm = (sum(1 for t in tiers.values() if t in S.SMALL_MEDIUM_TIERS) / float(len(tiers))
          if tiers else None)
    examples = sorted(used, key=lambda o: (-weights.get(o["obs_id"], 0.0), o["obs_id"]))
    prof = profile(used, weights, exclude_key=key)
    if kind == "sound" and prof.get("sound_title"):
        from vsp.trends.synth import safe_text
        label = f"sound '{safe_text(prof['sound_title'], 80)}'"
    return {
        "key": key, "kind": kind, "label": label,
        "first_seen": first.isoformat(), "last_seen": last.isoformat(), "span_days": span,
        "creators_total": len(creators), "creators_7d": c7, "creators_prev7d": p7,
        "creators_3d": c3, "growth": growth,
        "median_outlier_x": _median(ox), "median_multiple": _median(mult),
        "small_medium_share": round(sm, 3) if sm is not None else None,
        "platforms": sorted({o.get("platform") for o in used if o.get("platform")}),
        "niches": sorted({o.get("niche") for o in used if o.get("niche")}),
        "examples": [o["obs_id"] for o in examples[:MAX_EXAMPLES]],
        "stage": stage, "speed": speed, "evergreen": evergreen,
        "jump_in": jump_in(stage, evergreen),
        "evidence_score": round(sum(weights.values()), 4),
        "profile": prof, "related": [],
    }


def _relate(cards, by_key):
    """card["related"] = other card keys whose posts overlap >= RELATED_OVERLAP
    (Jaccard): the same trend's other elements (its sound, hashtag, topic)."""
    card_keys = {c["key"] for c in cards}
    sets = {k: {o["obs_id"] for o in by_key[k]} for k in card_keys}
    for c in cards:
        mine = sets[c["key"]]
        counts = {}
        for o in by_key[c["key"]]:
            for k in o.get("trend_keys") or []:
                if k != c["key"] and k in card_keys:
                    counts[k] = counts.get(k, 0) + 1
        rel = []
        for k, n in counts.items():
            jac = n / float(len(mine) + len(sets[k]) - n)
            if jac >= RELATED_OVERLAP:
                rel.append((-jac, k))
        c["related"] = [k for _, k in sorted(rel)[:MAX_RELATED]]


def _creator_of_row(r):
    h = r.get("handle")
    return f"{r.get('platform')}:{h}" if h else f"{r.get('platform')}:post:{r.get('post_id')}"


def build(observations, rows, signals, now):
    """-> the derived/trends.json document (cards sorted by stage order,
    evidence, key; capped at MAX_CARDS)."""
    today = S.utc(now).date()
    rows_by_id = {r["obs_id"]: r for r in rows}
    by_key = {}
    for o in observations:
        for k in o.get("trend_keys") or []:
            by_key.setdefault(k, []).append(o)
    cards = []
    for key in sorted(by_key):
        c = card_for(key, by_key[key], rows_by_id, today)
        if c:
            cards.append(c)
    _relate(cards, by_key)
    sig_by_key = {}
    for s in signals or []:
        if s.get("key"):
            sig_by_key.setdefault(s["key"], []).append(s)
    card_keys = set()
    for c in cards:
        card_keys.add(c["key"])
        if c["key"] in sig_by_key:
            c["signals"] = _signal_summary(sig_by_key[c["key"]])
    signals_only = []
    for key in sorted(sig_by_key):
        if key in card_keys:
            continue
        summ = _signal_summary(sig_by_key[key])
        names = sorted({s.get("name") for s in sig_by_key[key] if s.get("name")})
        signals_only.append(dict(summ, key=key, kind=key.split(":", 1)[0],
                                 name=names[0] if names else label_for(key),
                                 first_date=summ["dates"][0] if summ["dates"] else None,
                                 last_date=summ["dates"][-1] if summ["dates"] else None,
                                 watch="verify first: watch 3-5 top examples on Creative "
                                       "Center and log them with `observe` before any "
                                       "recipe rides it"))
    signals_only.sort(key=lambda s: (s["best_rank"] if s["best_rank"] else 10 ** 6, s["key"]))
    cards.sort(key=lambda c: (STAGE_ORDER.index(c["stage"]), -c["evidence_score"], c["key"]))
    by_stage = {s: sum(1 for c in cards if c["stage"] == s) for s in STAGE_ORDER}
    return {
        "schema_version": S.SCHEMA_VERSION, "generated_at": S.iso(now),
        "today": today.isoformat(),
        "rules": dict(STAGE_RULES, **SPEED_BOUNDS),
        "counts": {"observations": len(observations), "keys_seen": len(by_key),
                   "trends": len(cards), "by_stage": by_stage,
                   "signals_only": len(signals_only)},
        "trends": cards[:MAX_CARDS], "signals_only": signals_only[:200],
    }


def velocity(stage):
    return STAGE_VELOCITY.get(stage, 0.5)


def rows_index(rows):
    return {r["obs_id"]: r for r in rows}

