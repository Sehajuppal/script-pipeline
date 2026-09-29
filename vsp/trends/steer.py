"""Steering for the script pipeline — the integration contract.

    for_run(prompt, presenter=None, fmt=None, niche=None, concept=None,
            dataset_dir=None, recipe_id=None, today=None) -> dict | None
    brief_md(steer) -> str          the standalone trend.md artifact
    mark_used(recipe_id, dataset_dir=None, script_sha=None) -> bool

for_run picks the best unused recipe of the latest batch (<= 7 days old)
for the prompt's niche (vsp.router.route classifies the prompt when niche
or concept is None), ranked by score x concept fit x format fit, feasible
for the presenter (presenter="ai" never gets a needs-real-person recipe);
recipes scoring below MIN_STEER_SCORE (0.05) are ignored in auto mode.
recipe_id: None / "auto" = pick; "none" = no steering; an id = that recipe
(None if unknown or infeasible for the presenter). Returns None when there
is no dataset, no recipes, or nothing fits. It only reads files.

Returned keys (all enums valid in vsp.creative_vocab / vsp.router):
  recipe_id, title, operator, trend_keys, stage, score,
  hook_archetypes     ordered HOOK_ARCHETYPES ids (may be empty: no hook
                      steering); human_only ids dropped for presenter=ai,
                      requires_proof always dropped, price-anchor only when
                      the prompt has a price
  frame0_visual_type  VISUAL_TYPES id | None
  vibe                VIBES id | None
  format              demo | talking-head | pov-vlog | transformation | review | None
  duration_s          15 | 30 | 45 | 60 | None
  beats_note, audio_note, text_note, participation_note   (bundle-safe text)
  originality         what must be ours / changed
  evidence            [{permalink, platform, tier, outlier_x, band}] — FIXTURE
                      permalinks only with VSP_FIXTURE_OK=1 (as gate 2 / D151)
  risk                [str]
"""
import re
import sys
from datetime import date, datetime, timezone

from vsp import config
from vsp import creative_vocab as CV
from vsp.trends import lifecycle as L
from vsp.trends import schema as S
from vsp.trends import store
from vsp.trends.synth import FORMAT_ARCHETYPE, safe_text, tokens_of

MAX_RECIPE_AGE_DAYS = 7
MIN_STEER_SCORE = 0.05          # auto mode ignores near-zero-evidence recipes
STEER_KEYS = ("recipe_id", "title", "operator", "trend_keys", "stage", "score",
              "hook_archetypes", "frame0_visual_type", "vibe", "format", "duration_s",
              "beats_note", "audio_note", "text_note", "participation_note",
              "originality", "evidence", "risk")
CONCEPT_ARCHETYPES = {
    "challenge": ("challenge", "day-counter"),
    "routine": ("pov", "day-counter", "transformation"),
    "showcase": ("showcase", "listicle", "pov"),
    "advice": ("contrarian-reframe", "negative-command", "listicle", "question",
               "curiosity-gap"),
}
CONCEPT_MISS = 0.85
FORMAT_MISS = 0.8
STAGE_TEXT = {"invented": "an invented trend: untested, run it as a Trial Reels experiment",
              "outlier": "a single outlier post (no multi-creator trend yet)"}
AUDIO_RULE = ("Never use another creator's original sound in commercial posts; music "
              "comes from the platform's licensed library, added at upload.")


def _today(today):
    if today is None:
        return datetime.now(timezone.utc).date()
    if isinstance(today, datetime):
        return today.date()
    if isinstance(today, date):
        return today
    return datetime.strptime(str(today)[:10], "%Y-%m-%d").date()


def _route(prompt, presenter, fmt):
    """(niche, concept, price) from vsp.router.route (the maker voter needs
    the repo root on sys.path)."""
    if config.REPO not in sys.path:
        sys.path.insert(0, config.REPO)
    from vsp import router
    try:
        r = router.route(prompt, presenter=presenter, fmt=fmt, pack=False)
    except Exception:  # noqa: BLE001 — steering must never break a run
        return "default", "product", None
    return r.get("niche") or "default", r.get("concept") or "product", r.get("price")


def _lane_ok(rec, presenter):
    if presenter not in ("ai", "human"):
        return True
    lanes = rec.get("lanes") or (["human"] if rec.get("needs_real_person") else ["ai", "human"])
    return presenter in lanes and not (presenter == "ai" and rec.get("needs_real_person"))


def _concept_fit(rec, concept):
    want = CONCEPT_ARCHETYPES.get(concept)
    if not want:
        return 1.0
    return 1.0 if any(a in want for a in rec.get("hook_archetypes") or []) else CONCEPT_MISS


def _format_fit(rec, fmt):
    if not fmt or not rec.get("format") or rec["format"] == fmt:
        return 1.0
    return FORMAT_MISS


def _archetypes(rec, presenter, price):
    out = []
    for a in rec.get("hook_archetypes") or []:
        flags = CV.HOOK_ARCHETYPES.get(a)
        if flags is None:
            continue
        if presenter == "ai" and flags.get("human_only"):
            continue
        if flags.get("requires_proof") or flags.get("requires_offer"):
            continue
        if flags.get("requires_price") and not price:
            continue
        if a not in out:
            out.append(a)
    if not out and rec.get("hook_archetypes") and rec.get("format") in FORMAT_ARCHETYPE:
        out = [FORMAT_ARCHETYPE[rec["format"]]]      # every evidence archetype was filtered
    return out


def _clean(text, limit=400):
    t = safe_text(text, limit)
    return "" if S.instruction_like(t) or S.media_url_problem(t) else t


def _evidence(items):
    out = []
    for e in items or []:
        link = e.get("permalink")
        if not isinstance(link, str) or not link.startswith("https://") or \
                S.media_url_problem(link):
            continue
        if "FIXTURE" in link and not config.fixture_ok():
            continue
        out.append({"permalink": link, "platform": e.get("platform"),
                    "tier": e.get("tier") if e.get("tier") in S.TIERS else None,
                    "outlier_x": e.get("outlier_x") if isinstance(e.get("outlier_x"),
                                                                  (int, float)) else None,
                    "band": e.get("band") if e.get("band") in S.BANDS else None})
    return out[:5]


def _steer_dict(rec, presenter, price):
    arch = _archetypes(rec, presenter, price)
    risk = [_clean(r, 220) for r in rec.get("risk") or []]
    if presenter == "ai" and any(a in ("day-counter", "challenge") for a in arch):
        from vsp.trends.synth import AI_D137_RISK
        if AI_D137_RISK not in risk:
            risk.append(AI_D137_RISK)
    return {
        "recipe_id": rec["recipe_id"], "title": _clean(rec.get("title"), 160),
        "operator": rec.get("operator"),
        "trend_keys": [k for k in rec.get("trend_keys") or [] if S.norm_trend_key(k) == k],
        "stage": rec.get("stage") if rec.get("stage") in S.RECIPE_STAGES else "steady",
        "score": float(rec.get("score") or 0.0),
        "hook_archetypes": arch,
        "frame0_visual_type": rec.get("frame0_visual_type")
        if rec.get("frame0_visual_type") in CV.VISUAL_TYPES else None,
        "vibe": rec.get("vibe") if rec.get("vibe") in CV.VIBES else None,
        "format": rec.get("format") if rec.get("format") in S.FORMATS else None,
        "duration_s": rec.get("duration_s") if rec.get("duration_s") in S.DURATIONS else None,
        "beats_note": _clean(rec.get("beats_note")),
        "audio_note": _clean(rec.get("audio_note")),
        "text_note": _clean(rec.get("text_note")),
        "participation_note": _clean(rec.get("participation_note")),
        "originality": [x for x in (_clean(o, 220) for o in rec.get("originality") or []) if x],
        "evidence": _evidence(rec.get("evidence")),
        "risk": [x for x in risk if x],
    }


def for_run(prompt, presenter=None, fmt=None, niche=None, concept=None, dataset_dir=None,
            recipe_id=None, today=None):
    """See module doc. Never raises on a missing or partial dataset."""
    rid = str(recipe_id).strip() if recipe_id is not None else "auto"
    if rid.lower() == "none":
        return None
    d = store.dataset_dir(dataset_dir)
    if not store.is_initialized(d):
        return None
    try:
        recipes = store.load_recipes(d)
    except Exception:  # noqa: BLE001
        return None
    if not recipes:
        return None
    presenter = (presenter or "").strip().lower() or None
    if rid.lower() not in ("", "auto"):
        rec = next((r for r in recipes if r.get("recipe_id") == rid), None)
        if rec is None or not _lane_ok(rec, presenter):
            return None
        price = _route(prompt, presenter, fmt)[2] if prompt else None
        return _steer_dict(rec, presenter, price)
    r_niche, r_concept, price = _route(prompt or "", presenter, fmt)
    niche = S.norm_niche(niche) or r_niche
    concept = concept or r_concept
    pool = [r for r in recipes if r.get("niche") == niche and not r.get("used") and
            _lane_ok(r, presenter) and (r.get("score") or 0) >= MIN_STEER_SCORE]
    if not pool:
        return None
    latest = max(r["date"] for r in pool)
    if (_today(today) - _today(latest)).days > MAX_RECIPE_AGE_DAYS:
        return None
    pool = [r for r in pool if r["date"] == latest]
    ranked = sorted(pool, key=lambda r: (-round(r["score"] * _concept_fit(r, concept) *
                                                _format_fit(r, fmt), 6), r["recipe_id"]))
    return _steer_dict(ranked[0], presenter, price)


def _stage_line(steer):
    st = steer.get("stage")
    if st in STAGE_TEXT:
        return STAGE_TEXT[st]
    if st in L.JUMP_IN:
        return f"{st}: {L.JUMP_IN[st]}"
    return str(st)


def brief_md(steer):
    """Markdown for the standalone trend.md artifact ('' for no steer)."""
    if not steer:
        return ""
    x = steer
    out = ["## TREND — what this video rides", "",
           f"Recipe `{x['recipe_id']}` ({x['operator']}, score {x['score']:.3f}): "
           f"{x['title']}", "", "### The trend(s) and stage", ""]
    for k in x.get("trend_keys") or []:
        out.append(f"- `{k}` ({L.label_for(k)})")
    out.append(f"- Stage: {_stage_line(x)}")
    out += ["", "### Why it works (evidence)", ""]
    ev = x.get("evidence") or []
    for e in ev:
        mult = f"{e['outlier_x']:g}x their median views" if e.get("outlier_x") else \
            f"{e.get('band') or 'unscored'} band"
        out.append(f"- {e.get('tier') or 'unknown-tier'} creator on {e.get('platform')}: "
                   f"{mult}. {e['permalink']}")
    if not ev:
        out.append("- No public example links in this run.")
    out.append("- Small and medium creators' outliers mean the format won, not the "
               "audience: new posts are first shown to a small audience.")
    out += ["", "### What to copy (structure and signature)", "",
            f"- Beats: {x.get('beats_note') or 'n/a'}",
            f"- Hook archetypes, in order: {', '.join(x.get('hook_archetypes') or [])}",
            f"- Frame 0: {x.get('frame0_visual_type') or 'free choice'}; vibe: "
            f"{x.get('vibe') or 'free choice'}; format: {x.get('format') or 'free choice'}; "
            f"duration: {str(x['duration_s']) + ' s' if x.get('duration_s') else 'free choice'}",
            f"- On-screen text: {x.get('text_note') or 'n/a'}",
            f"- Participation: {x.get('participation_note') or 'n/a'}",
            "", "### What to change (originality: keep 2 of 4 elements, change 2)", ""]
    out += [f"- {o}" for o in x.get("originality") or []] or ["- Our own footage and words."]
    out += ["", "### Audio (licensed only)", "", f"- {x.get('audio_note') or 'n/a'}",
            f"- {AUDIO_RULE}", "", "### Risks", ""]
    out += [f"- {r}" for r in x.get("risk") or []] or ["- None flagged."]
    text = "\n".join(out) + "\n"
    return "\n".join(ln for ln in text.split("\n")
                     if not any(b in ln for b in CV.BUNDLE_FORBIDDEN if b != "FIXTURE"))


def mark_used(recipe_id, dataset_dir=None, script_sha=None):
    """Record that a run used `recipe_id` (usage/used.jsonl + the used flag in
    derived/recipes.jsonl) so later batches rate similar recipes less novel.
    -> True when recorded, False when the dataset or recipe is missing."""
    d = store.dataset_dir(dataset_dir)
    if not recipe_id or not store.is_initialized(d):
        return False
    recipes = store.load_recipes(d)
    rec = next((r for r in recipes if r.get("recipe_id") == recipe_id), None)
    if rec is None:
        return False
    now = S.iso(S.now_utc())
    sha = str(script_sha).strip().lower() if script_sha else None
    if sha and not re.fullmatch(r"[0-9a-f]{8,64}", sha):
        sha = None
    store.append_usage(d, {"recipe_id": recipe_id, "used_at": now, "script_sha": sha,
                           "operator": rec.get("operator"), "niche": rec.get("niche"),
                           "title": rec.get("title"), "trend_keys": rec.get("trend_keys"),
                           "tokens": sorted(tokens_of(rec))})
    rec["used"], rec["used_at"] = True, now
    if sha:
        rec["script_sha"] = sha
    store.save_recipes(d, recipes)
    return True


__all__ = ["for_run", "brief_md", "mark_used", "STEER_KEYS", "MAX_RECIPE_AGE_DAYS"]
