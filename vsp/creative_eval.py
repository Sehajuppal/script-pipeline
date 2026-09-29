"""Bundle-level creative metrics for one pipeline run (pipeline v2.1).

    evaluate(outdir) -> row          reads script.json, shots.json, bundle.md
    evaluate_files(script, shots, bundle_text) -> row      (in memory)
    summarize(rows) -> dict          the scorecard's "creative" block
    python3 -m vsp.creative_eval OUTDIR [OUTDIR ...]       print rows + summary

The evaluator's own view of a run (docs/CREATIVE-PLAN.md §1, RULES.md §68),
computed from the files a run ships — never from a builder module. Every
field degrades to a zero / False / None when a file or key is absent, so a
pre-2.1 run (the baseline worktree) scores zeros instead of crashing.

Row fields
  keys                  {direction, hook_variants, discovery}: key present
  variant_count, distinct_visual_types, distinct_archetypes
  vibe, tone, primary_keyword
  keyword_placement_pass  D161 (vsp.rubric.keyword_placement)
  hook_strength         the shipped hook, independent HOOK_SCORE_FEATURES
                        scorer (novelty neutral: comparable across versions)
  hook_strength_primary the primary variant with its alternates (R23 view)
  shots, shots_typed, shot_typed_share   bundle '### Shot' blocks with a
                        valid '- Shot type:' line
  shots_json_typed_share  shots.json rows carrying shot_type/scale/move/
                        purpose/energy/ai_risk
  avg_shot_s, cuts_per_10s, cadence_in_band (avg shot length inside
                        direction.pacing.avg_shot_s; None without a band)
  human_by_3s           >= 1.0 s of face/hands shots by 3.0 s (D157 signal)
  frame0_product_result the frame-0 shot shows product/result/subject
  loop_ok               loop marker on the last shot (None above 15 s)
  real_footage_marked   presenter=ai: every proof shot (strict: EVIDENCE /
                        PAYOFF / DEMO-result / purpose proof, any purpose)
                        carries REAL FOOTAGE (bundle line or shots.json
                        real_footage) — None for human presenters
  high_ai_risk_share    share of typed shots with AI risk high
  sections              the four v2.1 sections present; sections_present
  alt_openings          '#### Alt opening' blocks; alt_openings_match (one
                        per non-primary variant); alt_prompt_problems (D160
                        screens on the alternate-opening prompts, audit)
  shot_plan_pass        typed v2.1 bundle with no D157 finding
  findings              {D157, D159, D160}: gate-2 messages
  gate1_findings        {D154, D155, D156, D158}: message counts
  creative_warnings     script['creative_warnings'] (module crashes)
"""
import json
import os
import re
import statistics
import sys

SECTION_NAMES = ("CREATIVE DIRECTION", "ALTERNATE OPENINGS", "SHOOT PLAN",
                 "POSTING & DISCOVERY")
SHOT_KEYS = ("shot_type", "scale", "move", "purpose", "energy", "ai_risk")
ALT_HEAD = re.compile(r"^#### Alt opening ([A-Z])\b", re.M)
GATE2_IDS = ("D157", "D159", "D160")
GATE1_IDS = ("D154", "D155", "D156", "D158")


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def evaluate(outdir):
    """Metrics for one run directory (missing files -> zeros)."""
    script = _load_json(os.path.join(outdir, "script.json"))
    shots = _load_json(os.path.join(outdir, "shots.json"))
    bundle = _read(os.path.join(outdir, "bundle.md"))
    return evaluate_files(script, shots, bundle)


def _shot_rows(shots):
    if isinstance(shots, dict):
        shots = shots.get("shots")
    return [r for r in shots or [] if isinstance(r, dict)]


def _n(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def evaluate_files(script, shots, bundle_text):
    from vsp import rubric as RUB
    from vsp import rules as RL
    s = script if isinstance(script, dict) else {}
    text = bundle_text or ""
    rows = _shot_rows(shots)
    ai = s.get("presenter") == "ai"
    hv = s.get("hook_variants") if isinstance(s.get("hook_variants"), list) else []
    hv = [v for v in hv if isinstance(v, dict)]
    d = s.get("direction") if isinstance(s.get("direction"), dict) else {}
    disc = s.get("discovery") if isinstance(s.get("discovery"), dict) else {}
    tone = d.get("tone") if isinstance(d.get("tone"), dict) else {}
    row = {"keys": {k: k in s for k in ("direction", "hook_variants", "discovery")},
           "variant_count": len(hv),
           "distinct_visual_types": len({v.get("visual_type") for v in hv
                                         if v.get("visual_type")}),
           "distinct_archetypes": len({v.get("archetype") for v in hv
                                       if v.get("archetype")}),
           "vibe": d.get("vibe") if isinstance(d.get("vibe"), str) else None,
           "tone": tone.get("voice") if isinstance(tone.get("voice"), str) else None,
           "primary_keyword": RUB.script_keyword(s) or None,
           "creative_warnings": list(s.get("creative_warnings") or [])}
    try:
        row["keyword_placement_pass"] = bool(s) and RUB.keyword_placement(s)[0]
    except Exception:  # noqa: BLE001 — a metric bug never kills a scorecard
        row["keyword_placement_pass"] = False
    prim = next((v for v in hv if v.get("is_primary")), hv[0] if hv else {})
    arche = prim.get("archetype") or s.get("hook_family")
    try:
        row["hook_strength"] = RUB.hook_score(
            RUB.hook_line(s), RUB.frame0_overlay(s), prim.get("visual_type"),
            arche, s)[0] if s and RUB.hook_line(s) else None
        verbals = [v.get("verbal") or "" for v in hv]
        row["hook_strength_primary"] = RUB.hook_score(
            prim.get("verbal"), prim.get("overlay"), prim.get("visual_type"),
            prim.get("archetype"), s,
            others=[x for v, x in zip(hv, verbals) if v is not prim])[0] if hv else None
    except Exception:  # noqa: BLE001
        row["hook_strength"] = row["hook_strength_primary"] = None
    blocks = sorted(RL.shot_blocks(text), key=lambda b: (b["s"], b["e"]))
    typed = [b for b in blocks if b["typed"]]
    row["shots"] = len(blocks) or len(rows)
    row["shots_typed"] = len(typed)
    row["shot_typed_share"] = round(len(typed) / len(blocks), 4) if blocks else 0.0
    row["shots_json_typed_share"] = round(
        sum(1 for r in rows if all(r.get(k) not in (None, "") for k in SHOT_KEYS))
        / len(rows), 4) if rows else 0.0
    spans = [(b["s"], b["e"]) for b in blocks] or [
        (float(r.get("start_s") or 0), float(r.get("end_s") or 0)) for r in rows
        if _n(r.get("start_s")) and _n(r.get("end_s"))]
    durs = [e - a for a, e in spans if e > a]
    dur = s.get("duration_s") if _n(s.get("duration_s")) else (
        max(e for _, e in spans) if spans else None)
    row["avg_shot_s"] = round(statistics.mean(durs), 3) if durs else None
    row["cuts_per_10s"] = round(10.0 * max(0, len(durs) - 1) / dur, 3) \
        if durs and dur else None
    band = (d.get("pacing") or {}).get("avg_shot_s") \
        if isinstance(d.get("pacing"), dict) else None
    if row["avg_shot_s"] is not None and isinstance(band, list) and len(band) == 2 \
            and all(_n(x) for x in band):
        row["cadence_in_band"] = band[0] - 1e-9 <= row["avg_shot_s"] <= band[1] + 1e-9
    else:
        row["cadence_in_band"] = None
    row["human_by_3s"] = row["frame0_product_result"] = False
    row["loop_ok"] = None if not (_n(dur) and dur <= 15) else False
    row["real_footage_marked"] = None if not ai else False
    row["high_ai_risk_share"] = None
    if blocks:
        human = sum(max(0.0, min(b["e"], 3.0) - max(b["s"], 0.0)) for b in blocks
                    if any(RL.shot_signals(b).values()))
        row["human_by_3s"] = human >= 1.0 - 1e-9
        row["frame0_product_result"] = RL.frame0_shows_subject(blocks[0], s)
        if row["loop_ok"] is not None:
            last = max(blocks, key=lambda b: (b["e"], b["s"]))
            row["loop_ok"] = RL.has_loop_marker(last, blocks[0])
        if ai:
            rf_rows = {str(r.get("n")): bool(r.get("real_footage")) for r in rows}
            proof = [b for b in blocks if RL.is_proof_shot(b, strict=True)]
            row["real_footage_marked"] = all(b["real_footage"] or rf_rows.get(b["n"])
                                             for b in proof)
            row["proof_shots"] = len(proof)
        risks = [(b.get("parsed") or {}).get("ai_risk") for b in typed]
        if risks:
            row["high_ai_risk_share"] = round(risks.count("high") / len(risks), 4)
    elif rows:
        risks = [r.get("ai_risk") for r in rows if r.get("ai_risk")]
        if risks:
            row["high_ai_risk_share"] = round(risks.count("high") / len(risks), 4)
    titles = [t.upper() for t, _ in RL.bundle_sections(text)]
    row["sections"] = {n: any(t.startswith(n) for t in titles) for n in SECTION_NAMES}
    row["sections_present"] = sum(row["sections"].values())
    alts = ALT_HEAD.findall(RL.section(text, "ALTERNATE OPENINGS") or "")
    row["alt_openings"] = len(alts)
    row["alt_openings_match"] = (sorted(alts) == sorted(
        v.get("id") for v in hv if not v.get("is_primary"))) if hv else None
    # audit: the D160 hygiene screens applied to the alternate-opening render
    # prompts too (the gate reads SHOT PROMPTS only)
    row["alt_prompt_problems"] = sum(
        len(RL.render_prompt_problems(b))
        for _, b in RL.prompt_blocks(text, "ALTERNATE OPENINGS", ALT_HEAD))
    findings = {}
    g1 = {}
    try:
        ctx = RL.build_ctx(s)
        for rid, fn in (("D157", RL.check_d157), ("D159", RL.check_d159),
                        ("D160", RL.check_d160)):
            findings[rid] = list(fn(s, text, ctx) or []) if text else []
        for rid, fn in (("D154", RL.check_d154), ("D155", RL.check_d155),
                        ("D156", RL.check_d156), ("D158", RL.check_d158)):
            g1[rid] = len(fn(s, None, ctx) or []) if s else 0
    except Exception as e:  # noqa: BLE001
        findings = {rid: [f"{rid}: metric crashed ({type(e).__name__}: {e})"]
                    for rid in GATE2_IDS}
    row["findings"] = {rid: findings.get(rid, []) for rid in GATE2_IDS}
    row["gate1_findings"] = {rid: g1.get(rid, 0) for rid in GATE1_IDS}
    row["shot_plan_pass"] = bool(typed) and not row["findings"]["D157"]
    return row


def _rate(rows, key):
    vals = [r.get(key) for r in rows if r.get(key) is not None]
    k = sum(1 for v in vals if v)
    return {"k": k, "n": len(vals), "rate": round(k / len(vals), 4) if vals else 0.0}


def _mean(rows, key):
    vals = [r[key] for r in rows if _n(r.get(key))]
    return round(statistics.mean(vals), 3) if vals else 0.0


def summarize(rows):
    """Aggregate creative_eval rows -> the scorecard 'creative' block. Rates
    carry {k, n, rate}; n counts rows where the metric applies (loop_ok only
    <= 15 s, real_footage_marked only presenter=ai, cadence only with a
    direction band). No creative files anywhere -> zeros."""
    rows = [r for r in rows if isinstance(r, dict)]
    n = len(rows)
    vibes, secs = {}, {name: 0 for name in SECTION_NAMES}
    for r in rows:
        if r.get("vibe"):
            vibes[r["vibe"]] = vibes.get(r["vibe"], 0) + 1
        for name, ok in (r.get("sections") or {}).items():
            secs[name] = secs.get(name, 0) + bool(ok)
    out = {"runs": n,
           "with_direction": sum(1 for r in rows if (r.get("keys") or {}).get("direction")),
           "with_hook_variants": sum(1 for r in rows if r.get("variant_count")),
           "with_discovery": sum(1 for r in rows if (r.get("keys") or {}).get("discovery")),
           "with_shot_types": sum(1 for r in rows if r.get("shots_typed")),
           "hook_variants_per_script": round(sum(r.get("variant_count") or 0
                                                 for r in rows) / n, 3) if n else 0.0,
           "distinct_visual_types_mean": _mean(rows, "distinct_visual_types"),
           "distinct_archetypes_mean": _mean(rows, "distinct_archetypes"),
           "vibes": dict(sorted(vibes.items())),
           "keyword_placement_pass": _rate(rows, "keyword_placement_pass"),
           "hook_strength_mean": _mean(rows, "hook_strength"),
           "hook_strength_primary_mean": _mean(rows, "hook_strength_primary"),
           "shot_typed_share_mean": _mean(rows, "shot_typed_share"),
           "shots_json_typed_share_mean": _mean(rows, "shots_json_typed_share"),
           "avg_shot_s_mean": _mean(rows, "avg_shot_s"),
           "cuts_per_10s_mean": _mean(rows, "cuts_per_10s"),
           "cadence_in_band": _rate(rows, "cadence_in_band"),
           "human_by_3s": _rate(rows, "human_by_3s"),
           "frame0_product_result": _rate(rows, "frame0_product_result"),
           "loop_ok": _rate(rows, "loop_ok"),
           "real_footage_marked": _rate(rows, "real_footage_marked"),
           "high_ai_risk_share_mean": _mean(rows, "high_ai_risk_share"),
           "sections_present_mean": _mean(rows, "sections_present"),
           "sections": secs,
           "alt_openings_match": _rate(rows, "alt_openings_match"),
           "alt_prompt_problems": sum(r.get("alt_prompt_problems") or 0 for r in rows),
           "shot_plan_pass": _rate(rows, "shot_plan_pass"),
           "findings": {rid: sum(len((r.get("findings") or {}).get(rid) or [])
                                 for r in rows) for rid in GATE2_IDS},
           "gate1_findings": {rid: sum((r.get("gate1_findings") or {}).get(rid) or 0
                                       for r in rows) for rid in GATE1_IDS},
           "creative_warning_runs": sum(1 for r in rows if r.get("creative_warnings"))}
    for key in ("keyword_placement_pass", "shot_plan_pass"):
        out[key]["runs_rate"] = round(out[key]["k"] / n, 4) if n else 0.0
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__.strip().split("\n\n")[0])
        return 2
    rows = []
    for p in argv:
        r = evaluate(p)
        rows.append(r)
        print(json.dumps({"outdir": p, **r}, ensure_ascii=False))
    print(json.dumps({"summary": summarize(rows)}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.exit(main())
