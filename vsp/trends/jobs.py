"""The commands behind `python3 -m vsp.trends` (each returns a report dict;
the CLI prints it). All take the dataset dir `d` and a pinned `now`.

    run_add(d, raws, now, defaults=None)        validate + append (add / observe)
    run_score(d, now)                           -> derived/outliers.jsonl
    run_lifecycle(d, now)                       -> derived/trends.json
    run_synth(d, now, niches, presenter, k, invent)   -> derived/recipes.jsonl
    run_digest(d, now, day)                     -> digests/<day>.md
    run_purge(d, now, creator=, platform=, source=, older_than=, expired=, dry_run=)
    validate_dataset(d, now), status(d, now)
    watchlist_suggest(d, now, min_x, cap, config_path, apply)
"""
import json
import os
from datetime import timedelta

from vsp.trends import lifecycle as L
from vsp.trends import schema as S
from vsp.trends import score as SC
from vsp.trends import store
from vsp.trends import synth as SY

NOVELTY_MEMORY_DAYS = 180
WATCHLIST_CAP = 150
WATCHLIST_MIN_X = 5.0
WATCHLIST_TIERS = ("nano", "micro", "mid")
ENV_NICHES = "VSP_TRENDS_NICHES"


def maker_niches():
    from vsp.ingest.settings import MAKER_NICHES
    return MAKER_NICHES


# -------------------------------------------------------------------- add
def run_add(d, raws, now, defaults=None):
    """Validate raw records; append the valid ones. -> report with
    accepted / rejected ([{row, id, errors}])."""
    store.require(d)
    ok, rejected = [], []
    for i, raw in enumerate(raws, 1):
        if isinstance(raw, dict) and raw.get("__error__"):
            rejected.append({"row": i, "permalink": None, "errors": [raw["__error__"]]})
            continue
        rec, errs = S.normalize_observation(raw, now=now, defaults=defaults)
        if errs:
            rejected.append({"row": i, "permalink": (raw or {}).get("permalink")
                             if isinstance(raw, dict) else None, "errors": errs})
        else:
            ok.append(rec)
    rep = {"rows": len(raws), "accepted": len(ok), "rejected": rejected}
    rep.update(store.add_observations(d, ok, now) if ok else
               {"new": 0, "updated": 0, "refreshed": 0, "unchanged": 0, "file": None})
    return rep


# ------------------------------------------------------------ derivations
def compute(d, now):
    """(observations, creators, rows, trends doc) — the in-memory state
    every derivation starts from."""
    obs = store.load_observations(d)
    creators = store.load_creators(d)
    rows = SC.score_all(obs, creators, now)
    doc = L.build(obs, rows, store.load_signals(d), now)
    return obs, creators, rows, doc


def run_score(d, now, write=True):
    store.require(d)
    obs = store.load_observations(d)
    rows = SC.score_all(obs, store.load_creators(d), now)
    out = SC.outlier_rows(rows)
    by_band = {}
    for r in rows:
        by_band[r["band"]] = by_band.get(r["band"], 0) + 1
    path = store.derived_path(d, "outliers.jsonl")
    if write and obs:
        store.write_jsonl(path, out)
    return {"observations": len(obs), "scored": sum(1 for r in rows if r["status"] == "scored"),
            "unscored": sum(1 for r in rows if r["status"] == "unscored"),
            "outliers": len(out), "by_band": dict(sorted(by_band.items())),
            "file": os.path.relpath(path, d) if write and obs else None,
            "top": [{k: r[k] for k in ("obs_id", "tier", "multiple", "basis", "band",
                                       "inspiration_score", "permalink")} for r in out[:5]]}


def run_lifecycle(d, now, write=True):
    store.require(d)
    obs, _creators, _rows, doc = compute(d, now)
    path = store.derived_path(d, "trends.json")
    if write and obs:
        store.write_json(path, doc)
    return {"observations": len(obs), "trends": len(doc["trends"]),
            "by_stage": doc["counts"]["by_stage"], "signals_only": len(doc["signals_only"]),
            "file": os.path.relpath(path, d) if write and obs else None, "doc": doc}


def usage_memory(d, now, recipes=None):
    """Token sets of recipes used within NOVELTY_MEMORY_DAYS (the usage log,
    plus used flags in derived/recipes.jsonl)."""
    cutoff = S.iso(S.utc(now) - timedelta(days=NOVELTY_MEMORY_DAYS))
    seen, mem = set(), []
    for u in sorted(store.load_usage(d), key=lambda u: (u.get("used_at") or "",
                                                         u.get("recipe_id") or "")):
        if (u.get("used_at") or "") < cutoff or u.get("recipe_id") in seen:
            continue
        seen.add(u.get("recipe_id"))
        if u.get("tokens"):
            mem.append(set(u["tokens"]))
    for r in recipes if recipes is not None else store.load_recipes(d):
        if r.get("used") and r.get("recipe_id") not in seen and \
                (r.get("used_at") or "") >= cutoff:
            seen.add(r["recipe_id"])
            mem.append(SY.tokens_of(r))
    return mem


def default_niches(obs, env=None):
    e = os.environ if env is None else env
    raw = (e.get(ENV_NICHES) or "").strip()
    if raw:
        return sorted({S.norm_niche(x) for x in raw.split(",") if S.norm_niche(x)})
    mk = set(maker_niches())
    return sorted({o["niche"] for o in obs if o.get("niche") in mk})


def run_synth(d, now, niches=None, presenter=None, k=10, invent=3, write=True):
    store.require(d)
    obs, _creators, rows, doc = compute(d, now)
    niches = sorted({S.norm_niche(n) for n in (niches or []) if S.norm_niche(n)}) or \
        default_niches(obs)
    if not obs or not niches:
        return {"recipes": 0, "niches": niches, "status": "nothing to do",
                "reason": "no observations" if not obs else "no niches (use --niche)"}
    lanes = [presenter] if presenter else ["ai", "human"]
    existing = store.load_recipes(d)
    used_ids = {u.get("recipe_id") for u in store.load_usage(d)}
    memory = usage_memory(d, now, existing)
    new = SY.synthesize(doc, obs, rows, niches, lanes=lanes, k=k, invent=invent, now=now,
                        memory=memory, existing=existing)
    cutoff = S.iso(S.utc(now) - timedelta(days=NOVELTY_MEMORY_DAYS))
    keep = []
    new_ids = {r["recipe_id"] for r in new}
    for r in existing:
        if r["recipe_id"] in new_ids:
            continue
        if r.get("used") or r["recipe_id"] in used_ids:
            if (r.get("used_at") or r.get("created_at") or "") >= cutoff:
                r["used"] = True
                keep.append(r)
        elif r.get("niche") not in niches:
            keep.append(r)            # other niches' batches stay until their next synth
    if write:
        store.save_recipes(d, keep + new)
    by_op = {}
    for r in new:
        by_op[r["operator"]] = by_op.get(r["operator"], 0) + 1
    return {"recipes": len(new), "kept": len(keep), "niches": niches, "lanes": lanes,
            "by_operator": dict(sorted(by_op.items())),
            "file": os.path.relpath(store.derived_path(d, "recipes.jsonl"), d) if write else None,
            "top": [{k2: r[k2] for k2 in ("recipe_id", "niche", "operator", "score", "title")}
                    for r in sorted(new, key=lambda r: (-r["score"], r["recipe_id"]))[:5]],
            "new": new}


def run_digest(d, now, day=None):
    from vsp.trends import digest as DG
    store.require(d)
    day = day or store.day_str(now)
    obs, creators, rows, doc = compute(d, now)
    md = DG.render(obs, rows, doc, store.load_recipes(d), day, now)
    path = store.digest_path(d, day)
    store.write_atomic(path, md)
    return {"file": path, "day": day, "bytes": len(md.encode("utf-8"))}


# -------------------------------------------------------------------- purge
def _ts_le(value, bound):
    t = S.parse_time(value)
    return t is not None and t <= bound


def _obs_reason(obj, crit, now):
    if crit.get("creator"):
        h = S.norm_handle((obj.get("creator") or {}).get("handle"))
        if h and h == crit["creator"] and (not crit.get("platform") or
                                          obj.get("platform") == crit["platform"]):
            return "creator"
    if crit.get("source") and obj.get("source") == crit["source"]:
        return "source"
    if crit.get("older_than") is not None and \
            _ts_le(obj.get("observed_at"), S.utc(now) - timedelta(days=crit["older_than"])):
        return "older_than"
    if crit.get("expired") and _ts_le((obj.get("retention") or {}).get("purge_after"), now):
        return "expired"
    return None


def _creator_reason(obj, crit, now):
    if crit.get("creator") and S.norm_handle(obj.get("handle")) == crit["creator"] and \
            (not crit.get("platform") or obj.get("platform") == crit["platform"]):
        return "creator"
    if crit.get("source") and obj.get("source") == crit["source"]:
        return "source"
    if crit.get("older_than") is not None and \
            _ts_le(obj.get("snapshot_at"), S.utc(now) - timedelta(days=crit["older_than"])):
        return "older_than"
    if crit.get("expired") and _ts_le((obj.get("retention") or {}).get("purge_after"), now):
        return "expired"
    return None


def _signal_reason(obj, crit, now):
    if crit.get("source") and obj.get("source") == crit["source"]:
        return "source"
    if crit.get("older_than") is not None and \
            _ts_le(obj.get("observed_at"), S.utc(now) - timedelta(days=crit["older_than"])):
        return "older_than"
    if crit.get("expired") and _ts_le((obj.get("retention") or {}).get("purge_after"), now):
        return "expired"
    return None


def _filter_file(path, reason_fn, crit, now, rep, dry_run, d, kind, removed_links):
    lines = store.read_jsonl(path)
    keep, dropped = [], 0
    for _, obj, _err in lines:
        if obj is None:
            continue
        why = reason_fn(obj, crit, now)
        if why:
            dropped += 1
            rep["by_reason"][why] = rep["by_reason"].get(why, 0) + 1
            if obj.get("permalink"):
                removed_links.add(obj["permalink"])
        else:
            keep.append(obj)
    if not dropped:
        return
    rep["removed"][kind] += dropped
    rel = os.path.relpath(path, d)
    if dry_run:
        return
    if keep:
        store.write_jsonl(path, keep)
        rep["files_rewritten"].append(rel)
    else:
        os.remove(path)
        rep["files_deleted"].append(rel)


def run_purge(d, now, creator=None, platform=None, source=None, older_than=None,
              expired=False, dry_run=False):
    """Delete matching rows (criteria are OR-ed), then regenerate derived
    files and scrub digests / recipe evidence of the removed posts."""
    store.require(d)
    crit = {"creator": S.norm_handle(creator), "platform": platform, "source": source,
            "older_than": older_than, "expired": bool(expired)}
    rep = {"dry_run": bool(dry_run), "removed": {"observations": 0, "creators": 0,
                                                 "signals": 0},
           "by_reason": {}, "files_rewritten": [], "files_deleted": [],
           "digests_scrubbed": [], "recipes_scrubbed": 0, "regenerated": []}
    links = set()
    for p in store.observation_files(d):
        _filter_file(p, _obs_reason, crit, now, rep, dry_run, d, "observations", links)
    cp = store.creators_path(d)
    if os.path.isfile(cp):
        _filter_file(cp, _creator_reason, crit, now, rep, dry_run, d, "creators", set())
    for p in store.signal_files(d):
        _filter_file(p, _signal_reason, crit, now, rep, dry_run, d, "signals", set())
    total = sum(rep["removed"].values())
    if dry_run or not total:
        return rep
    if os.path.isfile(store.derived_path(d, "outliers.jsonl")):
        run_score(d, now)
        rep["regenerated"].append("derived/outliers.jsonl")
    if os.path.isfile(store.derived_path(d, "trends.json")):
        run_lifecycle(d, now)
        rep["regenerated"].append("derived/trends.json")
    recipes = store.load_recipes(d)
    if recipes and links:
        n = 0
        for r in recipes:
            ev = [e for e in r.get("evidence") or [] if e.get("permalink") not in links]
            n += len(r.get("evidence") or []) - len(ev)
            r["evidence"] = ev
        if n:
            store.save_recipes(d, recipes)
            rep["recipes_scrubbed"] = n
    ddir = os.path.join(d, "digests")
    needles = sorted(links) + (["@" + crit["creator"]] if crit["creator"] else [])
    if os.path.isdir(ddir) and needles:
        for fn in sorted(os.listdir(ddir)):
            p = os.path.join(ddir, fn)
            if not fn.endswith(".md"):
                continue
            with open(p, encoding="utf-8") as f:
                text = f.read()
            kept = [ln for ln in text.split("\n") if not any(nd in ln for nd in needles)]
            if len(kept) != len(text.split("\n")):
                store.write_atomic(p, "\n".join(kept))
                rep["digests_scrubbed"].append(os.path.relpath(p, d))
    if os.path.isdir(os.path.join(d, ".git")):
        rep["git_history_note"] = ("the working tree is clean of these rows, but git history "
                                   "still has them: a human must rewrite history (git "
                                   "filter-repo) and force-push; see README 'Deletion'")
    return rep


# --------------------------------------------------------------- validate
def validate_dataset(d, now):
    store.require(d)
    problems, warnings = [], []
    checked = {"observations": 0, "creators": 0, "signals": 0, "recipes": 0, "trends": 0}

    def check_file(path, spec, kind):
        for ln, obj, err in store.read_jsonl(path):
            rel = f"{os.path.relpath(path, d)}:{ln}"
            if obj is None:
                problems.append(f"{rel}: {err}")
                continue
            checked[kind] += 1
            for e in S.validate(obj, spec, now=now if kind != "recipes" else None):
                problems.append(f"{rel}: {e}")
    for p in store.observation_files(d):
        check_file(p, S.OBSERVATION, "observations")
    if os.path.isfile(store.creators_path(d)):
        check_file(store.creators_path(d), S.CREATOR, "creators")
    for p in store.signal_files(d):
        check_file(p, S.SIGNAL, "signals")
    rp = store.derived_path(d, "recipes.jsonl")
    if os.path.isfile(rp):
        check_file(rp, S.RECIPE, "recipes")
    tdoc = store.read_json(store.derived_path(d, "trends.json"))
    if isinstance(tdoc, dict):
        for i, c in enumerate(tdoc.get("trends") or []):
            checked["trends"] += 1
            for e in S.validate(c, S.TREND):
                problems.append(f"derived/trends.json trends[{i}]: {e}")
    for rel, n in store.file_sizes(d):
        warnings.append(f"{rel} is {n // 1024} KB (GitHub's soft limit is ~1 MB per "
                        f"object: split or purge)")
    return {"ok": not problems, "problems": problems, "warnings": warnings,
            "checked": checked}


# ------------------------------------------------------------------ status
def status(d, now):
    store.require(d)
    snaps = store.load_snapshots(d)
    obs = store.load_observations(d)
    by = {"platform": {}, "source": {}, "niche": {}}
    for o in obs:
        for k in by:
            v = o.get(k) or "unknown"
            by[k][v] = by[k].get(v, 0) + 1
    last = {}
    for _, _, _, rec in snaps:
        s, t = rec.get("source"), rec.get("observed_at") or ""
        if s and t > last.get(s, ""):
            last[s] = t
    recipes = store.load_recipes(d)
    digests = sorted(fn[:-3] for fn in os.listdir(os.path.join(d, "digests"))
                     if fn.endswith(".md")) if os.path.isdir(os.path.join(d, "digests")) else []
    due = sum(1 for _, _, _, r in snaps if _ts_le((r.get("retention") or {})
                                                 .get("purge_after"), now))
    tdoc = store.read_json(store.derived_path(d, "trends.json"), {}) or {}
    return {"dir": d, "observation_lines": len(snaps), "posts": len(obs),
            "creators": len(store.load_creators(d)), "signals": len(store.load_signals(d)),
            "by_platform": dict(sorted(by["platform"].items())),
            "by_source": dict(sorted(by["source"].items())),
            "by_niche": dict(sorted(by["niche"].items())),
            "last_observed_by_source": dict(sorted(last.items())),
            "trends": len(tdoc.get("trends") or []), "trends_generated_at":
                tdoc.get("generated_at"),
            "recipes": len(recipes), "recipes_used": sum(1 for r in recipes if r.get("used")),
            "last_digest": digests[-1] if digests else None, "purge_due": due,
            "quota": store.load_quota(d).get("youtube"),
            "large_files": [f"{p} ({n // 1024} KB)" for p, n in store.file_sizes(d)],
            "git": os.path.isdir(os.path.join(d, ".git"))}


# --------------------------------------------------------------- watchlist
def watchlist_suggest(d, now, min_x=WATCHLIST_MIN_X, cap=WATCHLIST_CAP, config_path=None,
                      apply=False):
    """Instagram nano/micro/mid creators with >= min_x outliers (median or
    per-follower basis) that are not yet on the vsp.ingest watchlist. With
    apply=True they are appended to config/ingest.json (niches.<n>.handles)
    up to `cap` handles in total (Business Discovery rate limits)."""
    from vsp import config as C
    from vsp.ingest.settings import norm_handle as ig_handle
    store.require(d)
    obs = store.load_observations(d)
    rows = SC.score_all(obs, store.load_creators(d), now)
    groups = {}
    for r in rows:
        if r["platform"] != "instagram" or not r.get("handle") or \
                r.get("tier") not in WATCHLIST_TIERS or r.get("basis") not in \
                ("median", "followers") or (r.get("multiple") or 0) < min_x:
            continue
        g = groups.setdefault(r["handle"], {"handle": r["handle"], "tier": r["tier"],
                                            "outliers": 0, "best_x": 0.0, "niches": {}})
        g["outliers"] += 1
        g["best_x"] = max(g["best_x"], r["multiple"])
        if r.get("niche"):
            g["niches"][r["niche"]] = g["niches"].get(r["niche"], 0) + 1
    path = config_path or C.ingest_config_path()
    cfg = store.read_json(path) if os.path.isfile(path) else None
    have = set()
    if isinstance(cfg, dict):
        for spec in (cfg.get("niches") or {}).values():
            if isinstance(spec, dict):
                have |= {str(h).lstrip("@").lower() for h in spec.get("handles") or []}
    sugg = []
    for h in sorted(groups):
        g = groups[h]
        try:
            ig_handle(h)
        except ValueError:
            continue
        if h in have:
            continue
        niche = sorted(g["niches"], key=lambda n: (-g["niches"][n], n))[0] if g["niches"] \
            else None
        sugg.append({"handle": h, "tier": g["tier"], "outliers": g["outliers"],
                     "best_x": round(g["best_x"], 2), "niche": niche})
    sugg.sort(key=lambda s: (-s["outliers"], -s["best_x"], s["handle"]))
    rep = {"config": path, "config_found": isinstance(cfg, dict), "watchlist_size": len(have),
           "cap": cap, "suggestions": sugg, "added": [], "skipped": []}
    if apply:
        if not isinstance(cfg, dict):
            rep["error"] = (f"ingest config not found at {path}: copy "
                            f"config/ingest.example.json first")
            return rep
        size = len(have)
        for s in sugg:
            spec = (cfg.get("niches") or {}).get(s["niche"])
            if size >= cap:
                rep["skipped"].append({"handle": s["handle"], "why": f"watchlist cap {cap}"})
                continue
            if not isinstance(spec, dict):
                rep["skipped"].append({"handle": s["handle"],
                                       "why": f"niche {s['niche']!r} not in the config"})
                continue
            spec.setdefault("handles", []).append(s["handle"])
            rep["added"].append(s["handle"])
            size += 1
        if rep["added"]:
            store.write_atomic(path, json.dumps(cfg, indent=1, ensure_ascii=False) + "\n")
    return rep
