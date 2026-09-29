"""The daily digest (digests/YYYY-MM-DD.md), written for the agent to
summarise for the user.

    render(observations, rows, doc, recipes, day, now) -> markdown

Sections: top outliers (small and medium creators first, each with why it
popped), rising / emerging trends (+ peak trends that need a twist),
recipes of the day, three "post this week" picks, an invented-trend
experiment, Creative Center signals still to verify, a compliance footer.
Everything is sorted explicitly, so the same data renders byte-identically.
"""
from vsp.trends.synth import safe_text, words_of

TOP_OUTLIERS = 10
TOP_TRENDS = 10
TOP_RECIPES = 8
BASIS_TEXT = {"median": "x the creator's median views",
              "followers": "x views per follower",
              "engagement": "x the tier's typical engagement"}


def why_popped(o, r):
    """One line: the multiple plus the analysis fields that explain it."""
    bits = [f"{r['multiple']:g}{BASIS_TEXT.get(r['basis'], 'x')} ({r['band']})"]
    if r.get("small_medium"):
        bits.append(f"a {r['tier']} account, so the format won, not the audience")
    h = o.get("hook") or {}
    if h.get("archetype") or h.get("frame0_visual"):
        bits.append(" + ".join(x for x in (
            f"{h['archetype']} hook" if h.get("archetype") else None,
            f"{h['frame0_visual']} frame 0" if h.get("frame0_visual") else None) if x))
    if o.get("format_key"):
        bits.append(f"{words_of(o['format_key'])} format")
    if o.get("emotion"):
        bits.append(o["emotion"])
    st = o.get("structure") or {}
    extra = [x for x, on in (("loops", st.get("loop")), ("payoff at the end",
                                                          st.get("payoff_reveal")),
                             ("series", st.get("series"))) if on]
    if o.get("participation") and o["participation"] != "none":
        extra.append(words_of(o["participation"]) + " mechanic")
    if o.get("cta") == "comment_keyword":
        extra.append("keyword-comment CTA")
    bits += extra
    if r.get("vph") and r["vph"] >= 1000:
        bits.append(f"{int(r['vph']):,} views/hour")
    return safe_text("; ".join(bits), 300)


def _n(count, noun):
    return f"{count} {noun}{'' if count == 1 else 's'}"


def _pct(x):
    return f"{int(round(x * 100))}%" if isinstance(x, (int, float)) else "n/a"


def _trend_line(c, labels=None):
    mx = c.get("median_outlier_x") or c.get("median_multiple")
    rel = [labels.get(k, k) for k in c.get("related") or []] if labels is not None else []
    return (f"- `{c['key']}` ({c['label']}): **{c['stage']}**, {c['speed']}; "
            f"{c['creators_7d']} creators this week vs {c['creators_prev7d']} (x{c['growth']:g})"
            f"{f', median {mx:g}x' if mx else ''}, {_pct(c.get('small_medium_share'))} "
            f"small/medium; {', '.join(c['platforms'])}; niches "
            f"{', '.join(c['niches']) or 'n/a'}"
            f"{'; same trend: ' + ', '.join(rel) if rel else ''}. Advice: {c['jump_in']}.")


def _grouped(cards):
    """Cards minus the ones already listed as a shown card's related keys."""
    shown, seen = [], set()
    for c in cards:
        if c["key"] in seen:
            continue
        shown.append(c)
        seen.add(c["key"])
        seen.update(c.get("related") or [])
    return shown


def _recipe_line(r):
    lanes = "/".join(r.get("lanes") or [])
    return (f"- `{r['recipe_id']}` [{r['niche']}, {r['operator']}, {lanes}] "
            f"score {r['score']:.3f}: {r['title']}. {r['rationale']}")


def _picks(batch):
    """Three diverse recipes: distinct operators and primary trend keys."""
    out, ops, keys = [], set(), set()
    for r in sorted(batch, key=lambda r: (-r["score"], r["recipe_id"])):
        if r["operator"] == "invent":
            continue
        k0 = (r.get("trend_keys") or [None])[0]
        if r["operator"] in ops or (k0 and k0 in keys):
            continue
        out.append(r)
        ops.add(r["operator"])
        if k0:
            keys.add(k0)
        if len(out) == 3:
            break
    return out


def render(observations, rows, doc, recipes, day, now):
    obs_by_id = {o["obs_id"]: o for o in observations}
    creators = {(o.get("platform"), (o.get("creator") or {}).get("handle"))
                for o in observations if (o.get("creator") or {}).get("handle")}
    latest_day = max((r["date"] for r in recipes if not r.get("used")), default=None)
    batch = [r for r in recipes if not r.get("used") and r["date"] == latest_day]
    out = [f"# Trend digest: {day}", "",
           f"_{_n(len(observations), 'post')} from {_n(len(creators), 'named creator')}; "
           f"{_n(len(doc.get('trends') or []), 'trend card')}; {_n(len(batch), 'recipe')} "
           f"in the latest batch{f' ({latest_day})' if latest_day else ''}. Small and "
           f"medium creators come first: on Instagram a new post is first shown to a small "
           f"audience, so a small account's outlier means the format won._", ""]
    out += ["## Top outliers (small and medium creators first)", ""]
    scored = [r for r in rows if r["status"] == "scored" and r["band"] != "normal"]
    scored.sort(key=lambda r: (0 if r.get("small_medium") else 1, -r["inspiration_score"],
                               r["obs_id"]))
    if not scored:
        out.append("- none yet (no post reached 3x its creator's baseline)")
    for i, r in enumerate(scored[:TOP_OUTLIERS], 1):
        o = obs_by_id.get(r["obs_id"], {})
        who = f"@{r['handle']}" if r.get("handle") else "an unnamed account"
        out.append(f"{i}. **{r.get('tier') or 'unknown tier'}** {who} on {r['platform']}"
                   f"{' (' + r['niche'] + ')' if r.get('niche') else ''}: "
                   f"{why_popped(o, r)}. {r['permalink']}")
    out += ["", "## Rising and emerging trends", ""]
    cards = doc.get("trends") or []
    labels = {c["key"]: c["label"] for c in cards}
    prio = {"format": 0, "sound": 1, "topic": 2, "tag": 3}
    ordered = sorted(cards, key=lambda c: (("emerging", "rising", "peak").index(c["stage"])
                                           if c["stage"] in ("emerging", "rising", "peak")
                                           else 3, prio.get(c["kind"], 4),
                                           -c["evidence_score"], c["key"]))
    groups = _grouped(ordered)
    hot = [c for c in groups if c["stage"] in ("emerging", "rising")][:TOP_TRENDS]
    out += [_trend_line(c, labels) for c in hot] or ["- none this week"]
    peak = [c for c in groups if c["stage"] == "peak"][:5]
    if peak:
        out += ["", "Peak (only with a twist):"] + [_trend_line(c, labels) for c in peak]
    out += ["", "## Recipes of the day", ""]
    top = sorted(batch, key=lambda r: (-r["score"], r["recipe_id"]))[:TOP_RECIPES]
    out += [_recipe_line(r) for r in top] or ["- none: run `python3 -m vsp.trends synth`"]
    out += ["", "## Post this week", ""]
    picks = _picks(batch)
    for i, r in enumerate(picks, 1):
        lane = "" if "ai" in (r.get("lanes") or []) else ", human presenter only"
        out.append(f"{i}. `{r['recipe_id']}` {r['title']} ({r['niche']}{lane}). Hooks: "
                   f"{', '.join(r['hook_archetypes'])}; frame 0: "
                   f"{r.get('frame0_visual_type') or 'free'}; format: "
                   f"{r.get('format') or 'free'}. Run: `python3 pipeline.py \"<product>\" "
                   f"--trend {r['recipe_id']}`")
    if not picks:
        out.append("- nothing yet")
    out += ["", "## Invented-trend experiment", ""]
    inv = sorted([r for r in batch if r["operator"] == "invent"],
                 key=lambda r: (-r["score"], r["recipe_id"]))
    if inv:
        r = inv[0]
        sig = r["invent"]["signature"]
        out += [f"**{sig['name']}** (`{r['recipe_id']}`, {r['niche']}): {sig['marker']}; "
                f"hashtag {sig['hashtag']}.", "",
                f"- Slot: {r['invent']['slot']}",
                f"- Hypothesis: {r['invent']['hypothesis']}", "- Test plan:"]
        out += [f"  {i}. {t}" for i, t in enumerate(r["invent"]["test_plan"], 1)]
    else:
        out.append("- none (needs observations with a format_key)")
    sig_only = doc.get("signals_only") or []
    if sig_only:
        out += ["", "## Creative Center signals to verify", ""]
        for s in sig_only[:10]:
            g = s.get("growth_pct")
            out.append(f"- `{s['key']}` ({safe_text(s.get('name'), 80)}): rank "
                       f"{s.get('best_rank') or 'n/a'}, {s.get('posts') or 'n/a'} posts, "
                       f"growth {f'{g:+g}%' if g is not None else 'n/a'} "
                       f"({', '.join(s.get('regions') or []) or 'n/a'}). {s['watch']}.")
    out += ["", "## Compliance", "",
            "- Sources: the official Instagram Graph API (Hashtag Search, Business "
            "Discovery), the official YouTube Data API, TikTok Creative Center lists copied by "
            "hand, and human-scale agent/user observation. No scraping, no automated "
            "crawling of Instagram or TikTok, no media downloads.",
            "- Stored: permalinks, public metrics, hook excerpts of at most 12 words and our "
            "own analysis; never media or whole captions. YouTube stats are refreshed or "
            "purged within 30 days.",
            "- Deletion requests: `python3 -m vsp.trends purge --creator HANDLE`, then "
            "rewrite git history (README, Deletion).",
            "- Audio: licensed tracks only in commercial posts; never another creator's "
            "original sound. Every recipe keeps 2 of a trend's 4 elements and changes 2.",
            ""]
    return "\n".join(out)

