"""diagnose — turn the latest measurement into ranked opportunities and
agent-executable tasks.

Reads: learned/evals/latest.json (+ raw scorecards), the research pack
(vsp.research.load_pack), learned/priors.json (if present) and
docs/RULE-COVERAGE.md. Writes learned/DIAGNOSIS.md, learned/TASKS.md and
learned/tasks.json (the machine-readable twin that `delegate` reads).

Signals: gate / rubric failure clusters (with examples and repro commands),
compliance flags, crashes, audit-only vs selection gaps (gaming) and golden
vs holdout gaps (overfitting), hook diversity, hook-family mix vs the live
niche rankings (market drift), research-pack staleness, underperforming
families from priors, DOC-ONLY rules (D60) and runtime.

Scores are a transparent heuristic (impact ≈ share of runs × severity), not
a model: a compliance flag outranks everything but a red self-test.
"""
import collections
import os
import re
import shlex

from vsp.improve import common as C
from vsp.improve import measure as M

SEV = {"E": 3, "I": 2, "O": 1}
SUITE_W = {"golden": 1.0, "holdout": 1.2, "capability": 0.8}
NEVER_EDIT = ("vsp/gates.py", "vsp/rules.py", "vsp/lexicon.py")
RULE_FILES = [
    (("D43", "D55", "D74", "D78", "D94", "D43-NO-WINDOW"),
     ["vsp/timing.py", "viral_script_maker.py (_fit_timeline, build_beats)"]),
    (("D103", "D142"), ["viral_script_maker.py (payoff cards: _pick_card, _card_variants)"]),
    (("D44", "D58"), ["viral_script_maker.py (re-hook / beat banks: stage verbs)"]),
    (("D47", "D48", "SHOT-DRIFT", "REF-REELS", "DELIVERABLE", "RENDER-9x16",
      "WORDS-JSON", "DO-NOT", "WORDS-SCHEMA", "D151"), ["make_shotlist.py"]),
    (("D36", "B4a", "D46"), ["viral_script_maker.py (beat copy)", "make_shotlist.py"]),
    (("D136", "D137", "D139", "D141", "D37"),
     ["viral_script_maker.py (hook/beat banks, AI curator voice, proof slot)"]),
    (("D138",), ["viral_script_maker.py (build_caption disclosure line, PERSONA_DISCLOSURE)"]),
    (("D140", "TAG-MISMATCH"), ["viral_script_maker.py (build_caption, _scoped_tags)"]),
    (("D144", "D17"), ["viral_script_maker.py (overlay_truncate, pick_hook)"]),
    (("D31",), ["viral_script_maker.py (template slots)"]),
    (("D73",), ["viral_script_maker.py (pick_hook, HOOKS)", "learned/hook_packs/"]),
    (("D93",), ["viral_script_maker.py (RehookDeck, REHOOKS)"]),
    (("D146", "D111"), ["viral_script_maker.py (CTA, series_plan)"]),
]
RUBRIC_FILES = {
    "R01": "viral_script_maker.py (pick_hook budget)", "R02": "viral_script_maker.py (HOOKS, pick_hook)",
    "R03": "vsp/timing.py, viral_script_maker.py (_fit_timeline)", "R04": "vsp/timing.py (payoff band)",
    "R05": "viral_script_maker.py (claims/proof slots)", "R06": "viral_script_maker.py (AI curator voice)",
    "R07": "viral_script_maker.py (templates, humanize_dialogue)", "R08": "viral_script_maker.py (overlay_truncate)",
    "R09": "viral_script_maker.py (on-screen cards)", "R10": "viral_script_maker.py (RehookDeck)",
    "R11": "viral_script_maker.py (CTAS)", "R12": "vsp/timing.py (speech rate)",
    "R13": "viral_script_maker.py (build_caption tags)", "R14": "viral_script_maker.py (build_caption, _cta_word)",
    "R15": "viral_script_maker.py (pick_hook, overlay)", "R16": "viral_script_maker.py (disclosure)",
    "R17": "viral_script_maker.py (COMMENT_BAIT)", "R18": "viral_script_maker.py (bait lines)",
    "R19": "viral_script_maker.py (absolute claims)", "R20": "viral_script_maker.py (series_plan)",
}


def _files_for_rule(rid):
    for ids, files in RULE_FILES:
        if rid in ids:
            return list(files)
    return ["viral_script_maker.py"]


def _rubric_meta():
    try:
        from vsp import rubric
        return {cid: {"title": t, "tier": tier, "weight": w, "audit": audit}
                for cid, t, tier, w, audit, _ in rubric.CHECKS}
    except Exception:  # noqa: BLE001
        return {}


def _repro(row):
    """Shell command that reproduces one scorecard run."""
    out = f"/tmp/vsp-repro-{C.slug(row.get('key', 'x'), 40)}"
    return (f"python3 pipeline.py {shlex.quote(row['prompt'])} --format {row['format']} "
            f"--presenter {row['presenter']} --seed {row['seed']} --duration "
            f"{row.get('duration') or 30} --out-dir {out} ; python3 vsp/rubric.py "
            f"{out}/script.json")


def _ex(row, msg=None):
    s = f"`{row['key']}` hook {row.get('hook')!r}"
    if row.get("overlay"):
        s += f" · overlay {row['overlay']!r}"
    if msg:
        s += f" — {msg[:160]}"
    return s


# ----------------------------------------------------------------- inputs
def load_inputs(latest=None):
    latest = latest or M.latest()
    runs = {}
    for suite in C.SUITES:
        res = M.load_raw(latest, suite) if latest else None
        if res:
            runs[suite] = res
    try:
        from vsp import research
        pack, meta = research.load_pack()
    except Exception as e:  # noqa: BLE001
        pack, meta = None, {"errors": [repr(e)]}
    priors = C.read_json(os.path.join(C.learned_dir(), "priors.json"))
    cov = parse_rule_coverage(os.path.join(C.REPO, "docs", "RULE-COVERAGE.md"))
    return {"latest": latest, "results": runs, "pack": pack, "pack_meta": meta,
            "priors": priors if isinstance(priors, dict) else None,
            "coverage": cov, "history": M.history()}


def parse_rule_coverage(path):
    rows = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                m = re.match(r"^\|\s*(D\d+[a-z]?|B\d+[a-z]?)\s*\|\s*([A-Z-]+)\s*\|\s*(.*?)\s*\|"
                             r"\s*(.*?)\s*\|\s*(.*?)\s*\|\s*$", line)
                if m:
                    rows.append({"id": m.group(1), "class": m.group(2),
                                 "title": m.group(3), "section": m.group(4),
                                 "refs": m.group(5)})
    except OSError:
        return None
    return rows


# ------------------------------------------------------------ opportunities
def _opp(key, kind, title, score, summary, evidence=(), examples=(), task=None):
    return {"key": key, "kind": kind, "title": title, "score": round(float(score), 1),
            "summary": summary, "evidence": list(evidence), "examples": list(examples),
            "task": task}


def _task(tid, title, rationale, files, done_when, kind, self_serve=None):
    return {"id": tid, "title": title, "kind": kind, "rationale": rationale,
            "files": files, "done_when": done_when, "self_serve": self_serve}


def gate_clusters(suite, res):
    rows = res.get("runs") or []
    n = len(rows) or 1
    by = collections.defaultdict(list)
    for r in rows:
        for rid in r.get("rules_failed") or []:
            by[rid].append(r)
    out = []
    for rid, rs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        share = len(rs) / n
        exs = []
        for r in rs[:3]:
            msg = next((m for m in (r.get("gate1") or []) + (r.get("gate2") or [])
                        if C.slug(m).startswith(C.slug(rid))), None) or \
                ((r.get("gate1") or []) + (r.get("gate2") or []) or [""])[0]
            exs.append(_ex(r, msg) + f"\n    repro: `{_repro(r)}`")
        compliance = rid in C.COMPLIANCE_RULES
        score = (100 if compliance else 10) + 60 * share * SUITE_W.get(suite, 1.0)
        out.append(_opp(
            f"gate:{rid}", "gate", f"{rid} fails in {len(rs)}/{n} {suite} runs", score,
            f"{rid} blocks {share:.1%} of {suite} runs",
            [f"{suite}: {len(rs)} runs; by format "
             f"{dict(collections.Counter(r['format'] for r in rs).most_common())}; by concept "
             f"{dict(collections.Counter(r.get('concept') for r in rs).most_common())}"],
            exs,
            _task(f"T-GATE-{rid}", f"Fix the maker so {rid} stops failing ({suite})",
                  f"{rid} rejects {len(rs)}/{n} {suite} runs. Fix what the maker/shot list "
                  f"generates; the gate is right by definition.",
                  _files_for_rule(rid), f"{rid} failures on {suite} = 0 and verify ACCEPT",
                  "gate")))
    return out


def rubric_clusters(suite, res, meta):
    rows = [r for r in res.get("runs") or [] if "rubric" in r]
    n = len(rows) or 1
    by = collections.defaultdict(list)
    for r in rows:
        for cid in r.get("rubric_failed") or []:
            by[cid].append(r)
    out = []
    for cid, rs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        m = meta.get(cid, {})
        share = len(rs) / n
        w = SEV.get(m.get("tier"), 1)
        score = 3 + 10 * w * share * SUITE_W.get(suite, 1.0) * (1.2 if m.get("audit") else 1.0)
        exs = [_ex(r) + f"\n    repro: `{_repro(r)}`" for r in rs[:3]]
        concepts = dict(collections.Counter(r.get("concept") for r in rs).most_common())
        out.append(_opp(
            f"rubric:{cid}", "rubric",
            f"{cid} ({m.get('title', '?')}) fails in {len(rs)}/{n} {suite} runs", score,
            f"tier {m.get('tier', '?')}{' · AUDIT-ONLY (never selects)' if m.get('audit') else ''}",
            [f"{suite}: by concept {concepts}; by format "
             f"{dict(collections.Counter(r['format'] for r in rs).most_common())}; by presenter "
             f"{dict(collections.Counter(r['presenter'] for r in rs).most_common())}"],
            exs,
            _task(f"T-RUBRIC-{cid}", f"Raise {cid}: {m.get('title', cid)}",
                  f"{cid} fails on {share:.1%} of {suite} runs ({concepts}). "
                  + ("It is audit-only: fix the generator, never the selector. "
                     if m.get("audit") else ""),
                  [RUBRIC_FILES.get(cid, "viral_script_maker.py")],
                  f"{cid} failures on {suite} drop (target 0) with verify ACCEPT", "rubric")))
    return out


def compliance_and_crash(suite, res):
    s = res.get("summary") or {}
    out = []
    comp = s.get("compliance_flag_counts") or {}
    for flag, k in sorted(comp.items()):
        rs = [r for r in res.get("runs") or [] if flag in (r.get("compliance_flags") or [])]
        out.append(_opp(
            f"compliance:{flag}", "compliance", f"compliance flag {flag} on {k} {suite} runs",
            150 + k, "compliance flags block shipping outright", [],
            [_ex(r) + f"\n    repro: `{_repro(r)}`" for r in rs[:3]],
            _task(f"T-COMPLIANCE-{flag}", f"Eliminate compliance flag {flag} ({suite})",
                  f"{k} {suite} runs carry {flag}; nothing with a compliance flag may ship.",
                  [RUBRIC_FILES.get(flag, "viral_script_maker.py")],
                  f"{flag} count = 0 on golden and holdout with verify ACCEPT", "compliance")))
    crash = (s.get("crash") or {}).get("k") or 0
    if crash:
        rs = [r for r in res.get("runs") or [] if r.get("status") == "crash"]
        out.append(_opp(
            f"crash:{suite}", "crash", f"{crash} crashes on {suite}",
            90 + 100 * crash / max(1, s.get("runs") or 1), "any crash is a regression",
            [], [f"`{r['key']}` stderr: {r.get('stderr_tail', '')[:160]!r}"
                 f"\n    repro: `{_repro(r)}`" for r in rs[:3]],
            _task(f"T-CRASH-{suite}", f"Fix {crash} crash(es) on {suite}",
                  "A crash means no script at all.", ["viral_script_maker.py", "pipeline.py"],
                  f"0 crashes on {suite} with verify ACCEPT", "crash")))
    return out


def gaming_signals(results):
    out, lines = [], []
    for suite, res in sorted(results.items()):
        rows = [r for r in res.get("runs") or [] if "rubric" in r]
        if not rows:
            continue
        groups = collections.defaultdict(list)
        for r in rows:
            for dim in ("concept", "format", "presenter", "hook_family"):
                groups[(dim, r.get(dim))].append(r)
        worst = []
        for (dim, val), rs in groups.items():
            if len(rs) < 20:
                continue
            sel = sum(r["rubric_selection"] for r in rs) / len(rs)
            aud = sum(r["rubric_audit"] for r in rs) / len(rs)
            worst.append((sel - aud, dim, val, len(rs), sel, aud))
        worst.sort(reverse=True)
        s = (res.get("summary") or {}).get("rubric") or {}
        lines.append(f"{suite}: selection {s.get('selection_mean')} vs audit-only "
                     f"{s.get('audit_mean')} (overall)")
        for gap, dim, val, n, sel, aud in worst[:2]:
            lines.append(f"{suite}: largest group gap {dim}={val} (n={n}) selection "
                         f"{sel:.1f} vs audit {aud:.1f} (gap {gap:+.1f})")
            if gap > 2.0:
                out.append(_opp(
                    f"gaming:{suite}:{dim}={val}", "gaming",
                    f"audit-only checks trail selection by {gap:.1f} for {dim}={val} ({suite})",
                    8 + 3 * gap, "selection may be optimising what the audit checks don't see",
                    [f"n={n}; selection {sel:.1f}; audit {aud:.1f}"], [],
                    _task(f"T-GAMING-{C.slug(dim)}-{C.slug(val)}",
                          f"Close the audit-only gap for {dim}={val}",
                          "Audit-only checks (R12/R15/R17/P2) never select; a gap means the "
                          "generator satisfies the selected checks at their expense.",
                          ["viral_script_maker.py"], "audit mean within 1 point of selection",
                          "gaming")))
    g, h = results.get("golden"), results.get("holdout")
    if g and h:
        gs, hs = g.get("summary") or {}, h.get("summary") or {}
        gr, hr = (gs.get("rubric") or {}).get("mean"), (hs.get("rubric") or {}).get("mean")
        ge, he = (gs.get("e2e_pass") or {}).get("rate"), (hs.get("e2e_pass") or {}).get("rate")
        lines.append(f"golden vs holdout: e2e {ge} vs {he}, rubric {gr} vs {hr}")
        if None not in (gr, hr, ge, he) and (gr - hr > 1.0 or ge - he > 0.02):
            out.append(_opp("overfit", "gaming", "holdout trails golden (overfitting signal)",
                            25 + 5 * max(gr - hr, 100 * (ge - he)),
                            "changes tuned on golden do not generalise",
                            [f"e2e {ge} vs {he}; rubric {gr} vs {hr}"], [],
                            _task("T-OVERFIT", "Generalise: close the golden → holdout gap",
                                  "Holdout prompts are never used for tuning; a gap means "
                                  "golden-specific fixes.", ["viral_script_maker.py"],
                                  "holdout within 1 rubric point / 2% e2e of golden", "gaming")))
    return out, lines


def diversity_signals(results):
    out, lines = [], []
    for suite in ("golden", "holdout", "capability"):
        res = results.get(suite)
        if not res:
            continue
        h = (res.get("summary") or {}).get("hooks") or {}
        rows = [r for r in res.get("runs") or [] if r.get("hook")]
        fam = collections.defaultdict(set)
        famn = collections.Counter()
        for r in rows:
            if r.get("concept") == "product":
                fam[r.get("hook_family")].add(r["hook"])
                famn[r.get("hook_family")] += 1
        per = {f: f"{len(v)} distinct / {famn[f]} runs" for f, v in sorted(fam.items())}
        lines.append(f"{suite}: hooks distinct {h.get('distinct_ratio')} · distinct-2 "
                     f"{h.get('distinct2')} · seed diversity {h.get('per_cell_seed_diversity')}"
                     f" · fallback {h.get('fallback_rate')} · product families {per}")
        dr = h.get("distinct_ratio")
        if suite == "golden" and dr is not None and dr < 0.5:
            out.append(_opp(
                "diversity:hooks", "diversity",
                f"hook diversity is low ({dr:.0%} distinct hooks on golden)", 30 * (1 - dr),
                "few top-tied templates per niche family → seeds cannot vary the hook",
                [lines[-1]], [],
                _task("T-HOOK-DIVERSITY", "Grow the hook template pool where it is thinnest",
                      "pick_hook draws among the top-scored templates of the niche's family; "
                      "families with 1-2 fitting templates ship the same hook for every seed.",
                      ["learned/hook_packs/ (via evolve + promote)",
                       "viral_script_maker.py (HOOKS)"],
                      "golden hook distinct ratio up with verify ACCEPT", "diversity",
                      self_serve="python3 -m vsp.improve evolve --budget full && "
                                 "python3 -m vsp.improve promote <new pack>")))
    return out, lines


STRONG_SEEN = 10     # research evidence below this many reels is "thin"


def _live_family(research, pack, niche, presenter):
    """(source, strong): the live family with >= STRONG_SEEN reels behind
    it, else the thin-evidence one."""
    try:
        src = research.live_hook_source(pack, niche, presenter=presenter,
                                        min_seen=STRONG_SEEN)
        if src:
            return src, True
        return research.live_hook_source(pack, niche, presenter=presenter), False
    except Exception:  # noqa: BLE001
        return None, False


def drift_signals(results, pack, meta):
    out, lines = [], []
    if meta:
        lines.append(f"research pack: generated {meta.get('generated_at')} · age "
                     f"{meta.get('age_hours')} h · stale {meta.get('stale')} · sha "
                     f"{str(meta.get('sha256'))[:12]} · errors {meta.get('errors') or 'none'}")
        if meta.get("stale") or meta.get("errors"):
            out.append(_opp("pack:stale", "drift", "research pack is stale or invalid",
                            20, "live niche rankings are out of date",
                            [lines[-1]], [],
                            _task("T-PACK-STALE", "Refresh the research pack",
                                  "The maker's live hook family comes from the pack (D148).",
                                  ["research_pack.json (python3 research_bridge.py --refresh)"],
                                  "load_pack() fresh (age < 48 h) and self-test green", "drift")))
    if not pack:
        lines.append("market drift: no valid research pack — skipped")
        return out, lines
    try:
        from vsp import research
    except Exception:  # noqa: BLE001
        return out, lines
    res = results.get("golden")
    if not res:
        return out, lines
    cells = collections.defaultdict(list)
    for r in res.get("runs") or []:
        if r.get("concept") == "product" and r.get("niche"):
            cells[(r["niche"], r["presenter"])].append(r.get("hook_family"))
    drift = []
    for (niche, pres), fams in sorted(cells.items()):
        src, strong = _live_family(research, pack, niche, pres)
        if not src:
            continue
        miss = sum(1 for f in fams if f != src["family"]) / len(fams)
        used = dict(collections.Counter(fams).most_common(3))
        lines.append(f"drift {niche}/{pres}: live {src['family']} (research "
                     f"{src['pack_niche']}:{src['category']}, seen {src.get('times_seen')}"
                     f"{'' if strong else ', THIN evidence'}) vs used {used} → mismatch "
                     f"{miss:.0%}")
        if miss >= 0.5 and len(fams) >= 5:
            drift.append((miss * (1.0 if strong else 0.3), miss, niche, pres, src, used,
                          len(fams), strong))
    if drift:
        drift.sort(key=lambda x: (-x[0] * x[6], x[2], x[3]))
        total = max(1, sum(len(v) for v in cells.values()))
        share = sum(d[0] * d[6] for d in drift) / total
        n_strong = sum(1 for d in drift if d[7])
        out.append(_opp(
            "drift:families", "drift",
            f"hook-family mix ignores the live niche ranking in {len(drift)} niche×presenter "
            f"cells ({n_strong} with >= {STRONG_SEEN} reels of evidence)",
            8 + 20 * share, "the market moved; the maker's family choice did not",
            [f"{n}/{p}: live {s['family']} ({s['pack_niche']}:{s['category']}, seen "
             f"{s.get('times_seen')}{'' if st else ', thin'}) vs used {u} (mismatch {m:.0%}, "
             f"n={k})" for _w, m, n, p, s, u, k, st in drift[:6]], [],
            _task("T-DRIFT-FAMILIES", "Follow the live hook-family ranking (D148)",
                  "pick_hook should prefer vsp.research.live_hook_family(pack, niche, presenter) "
                  "(whole ranked list, mapped research niches) over the static NICHE_HOOK map.",
                  ["viral_script_maker.py (pick_hook, NICHE_HOOK)", "vsp/research.py"],
                  "golden family mismatch vs live ranking < 50% per cell with verify ACCEPT",
                  "drift")))
    return out, lines


def priors_signals(priors, results):
    out, lines = [], []
    if not priors:
        lines.append("priors: learned/priors.json absent (python3 -m vsp.feedback learn "
                     "writes it from posted-reel performance) — skipped")
        return out, lines
    fams = priors.get("families") or {}
    used = collections.defaultdict(collections.Counter)
    for res in results.values():
        for r in res.get("runs") or []:
            used[r.get("niche")][r.get("hook_family")] += 1
    lines.append(f"priors: updated {priors.get('updated_at')} · metric {priors.get('metric')} · "
                 f"{len(fams)} niches")
    for niche, fd in sorted(fams.items()):
        rows = []
        for fam, p in sorted((fd or {}).items()):
            try:
                a, b, n = float(p["alpha"]), float(p["beta"]), int(p.get("n", 0))
            except (KeyError, TypeError, ValueError):
                continue
            rows.append((a / (a + b) if a + b else 0.0, fam, n))
        if len(rows) < 2:
            continue
        avg = sum(m for m, _, _ in rows) / len(rows)
        tot = sum(used[niche].values()) or 1
        for mean, fam, n in rows:
            share = used[niche][fam] / tot
            if n >= 5 and mean < avg - 0.05 and share >= 0.1:
                lines.append(f"priors {niche}: {fam} underperforms (mean {mean:.2f} vs niche "
                             f"{avg:.2f}, n={n}) yet ships in {share:.0%} of runs")
                out.append(_opp(
                    f"priors:{niche}:{fam}", "priors",
                    f"{fam} underperforms in {niche} but is used in {share:.0%} of runs",
                    6 + 40 * (avg - mean) * share, "real posted-reel performance disagrees",
                    [lines[-1]], [],
                    _task(f"T-PRIOR-{C.slug(niche)}-{C.slug(fam)}",
                          f"Down-weight or re-template {fam} for {niche}",
                          "learned/priors.json shows this family's hook rate trails the niche.",
                          ["viral_script_maker.py (pick_hook priors)", "learned/hook_packs/"],
                          f"{fam} share in {niche} falls or its templates change, verify ACCEPT",
                          "priors")))
    return out, lines


def doc_only_signals(cov):
    out, lines = [], []
    if cov is None:
        lines.append("rule coverage: docs/RULE-COVERAGE.md missing — skipped")
        return out, lines
    doc = [r for r in cov if r["class"] == "DOC-ONLY"]
    lines.append(f"rule coverage: {len(cov)} tracked ids, {len(doc)} DOC-ONLY (D60 drafts): "
                 + ", ".join(r["id"] for r in doc))
    for r in doc:
        out.append(_opp(
            f"d60:{r['id']}", "doc-only", f"{r['id']} {r['title'].title()} is DOC-ONLY", 2.0,
            "D60: a rule is a draft until code-traceable", [f"section {r['section']}"], [],
            _task(f"T-D60-{r['id']}", f"Make {r['id']} ({r['title'].title()}) code-traceable "
                  f"or mark it superseded",
                  f"{r['id']} has no code reference (docs/RULE-COVERAGE.md). Implement it in the "
                  f"maker/shot list with a self-test case, or record in RULES.md why it is "
                  f"superseded (humans own RULES.md).",
                  ["viral_script_maker.py or make_shotlist.py", "vsp/selftest_cases.py (new case)",
                   "RULES.md (human review)"],
                  f"tools/rule_coverage.py no longer lists {r['id']} as DOC-ONLY, verify ACCEPT",
                  "doc-only")))
    return out, lines


def runtime_signals(results, hist):
    out, lines = [], []
    for suite, res in sorted(results.items()):
        s = res.get("summary") or {}
        rows = sorted(res.get("runs") or [], key=lambda r: -r.get("runtime_s", 0))[:3]
        lines.append(f"runtime {suite}: {s.get('runtime_mean_s')}s/run · wall "
                     f"{res.get('wall_s')}s · slowest "
                     + ", ".join(f"{r['key']} {r['runtime_s']}s" for r in rows))
    if len(hist) >= 2:
        prev, cur = hist[-2].get("suites", {}), hist[-1].get("suites", {})
        for suite in sorted(set(prev) & set(cur)):
            a, b = prev[suite].get("runtime_mean_s"), cur[suite].get("runtime_mean_s")
            if a and b and b > 1.2 * a and b - a > 0.02:
                out.append(_opp(
                    f"runtime:{suite}", "runtime", f"{suite} runtime up {b / a - 1:.0%}",
                    10 + 20 * (b / a - 1), "slower runs cost every cycle and every user",
                    [f"{a}s → {b}s per run"], [],
                    _task(f"T-RUNTIME-{suite}", f"Recover {suite} runtime ({a}s → {b}s per run)",
                          "Runtime regressed between the last two measurements.",
                          ["pipeline.py", "viral_script_maker.py", "vsp/select.py"],
                          "runtime back within 20% of the previous measure, verify ACCEPT",
                          "runtime")))
    return out, lines


def health_signals(health):
    out, lines = [], []
    if not health:
        return out, lines
    st = health.get("selftest") or {}
    lines.append(f"health: self-test {'green' if st.get('ok') else 'RED'} ("
                 + ", ".join(f"{r.get('version')} rc {r.get('rc')}" for r in st.get("runs", []))
                 + f") · hook packs {health.get('packs')}")
    if st and not st.get("ok"):
        out.append(_opp("health:selftest", "health", "self-test is RED", 300,
                        "nothing may change until the self-test is green",
                        [r.get("tail", "")[:300] for r in st.get("runs", []) if r.get("rc")], [],
                        _task("T-SELFTEST", "Make `python3 pipeline.py --self-test` green",
                              "Every change is gated on the self-test.",
                              ["the file named in the failure"], "self-test green on 3.9 and 3.12",
                              "health")))
    return out, lines


# -------------------------------------------------------------- orchestrate
def diagnose(latest=None, health=None, base_ref=None, write=True):
    inp = load_inputs(latest)
    results = inp["results"]
    meta = _rubric_meta()
    opps, signals = [], []
    for fn in (lambda: health_signals(health),):
        o, ln = fn()
        opps += o
        signals += ln
    for suite, res in sorted(results.items()):
        opps += compliance_and_crash(suite, res)
        opps += gate_clusters(suite, res)
        opps += rubric_clusters(suite, res, meta)
    for o, ln in (gaming_signals(results), diversity_signals(results),
                  drift_signals(results, inp["pack"], inp["pack_meta"]),
                  priors_signals(inp["priors"], results), doc_only_signals(inp["coverage"]),
                  runtime_signals(results, inp["history"])):
        opps += o
        signals += ln
    # one opportunity per key (a rule failing on several suites keeps its best score)
    best = {}
    for o in opps:
        k = o["task"]["id"] if o.get("task") else o["key"]
        if k not in best or o["score"] > best[k]["score"]:
            if k in best:
                o["evidence"] = best[k]["evidence"] + o["evidence"]
            best[k] = o
        else:
            best[k]["evidence"] += o["evidence"]
    ranked = sorted(best.values(), key=lambda o: (-o["score"], o["key"]))
    base_ref = base_ref or C.git_sha() or "HEAD"
    tasks = build_tasks(ranked, base_ref)
    out = {"created": C.now_iso(), "latest": inp["latest"], "opportunities": ranked,
           "signals": signals, "tasks": tasks, "base_ref": base_ref}
    if write:
        C.write_text(C.learned("DIAGNOSIS.md"), render_diagnosis(out, inp))
        C.write_text(C.learned("TASKS.md"), render_tasks(out))
        C.write_json(C.learned("tasks.json"), {"created": out["created"],
                                               "base_ref": base_ref, "tasks": tasks})
    return out


def build_tasks(ranked, base_ref):
    prev = {t["id"]: t for t in (C.read_json(C.learned("tasks.json")) or {}).get("tasks", [])}
    tasks = []
    for o in ranked:
        t = o.get("task")
        if not t:
            continue
        t = dict(t)
        t.update({"score": o["score"], "evidence": o["evidence"][:6],
                  "examples": o["examples"][:3], "status": "open",
                  "first_seen": (prev.get(t["id"]) or {}).get("first_seen") or C.today(),
                  "acceptance": f"python3 -m vsp.improve verify --base {base_ref} --cand HEAD",
                  "constraints": [
                      "work on a new branch or worktree — never commit to main/master",
                      "never edit " + ", ".join(NEVER_EDIT) + " to make a check pass: "
                      "fix the maker / shot list",
                      "never edit evals/golden.jsonl, evals/holdout.jsonl, evals/scorecard.py "
                      "or vsp/rubric.py (the yardstick)",
                      "open a PR with the verify evidence; never merge your own PR"]})
        tasks.append(t)
    return tasks


def _headline_table(inp):
    L = ["| suite | runs | e2e | shippable | rubric | selection | audit | compliance | "
         "hook distinct | s/run |", "|---|---|---|---|---|---|---|---|---|---|"]
    for suite, v in ((inp["latest"] or {}).get("suites") or {}).items():
        h = v["headline"]
        L.append(f"| {suite} | {h['runs']} | {h['e2e_pass']} | {h['shippable']} | "
                 f"{h['rubric_mean']} | {h['selection_mean']} | {h['audit_mean']} | "
                 f"{h['compliance_flags']} | {h['hook_distinct']} | {h['runtime_mean_s']} |")
    return L


def render_diagnosis(out, inp):
    lt = inp["latest"] or {}
    L = ["# DIAGNOSIS — ranked improvement opportunities", "",
         f"Generated {out['created']} by `python3 -m vsp.improve diagnose` from measure "
         f"`{lt.get('stamp')}` at `{lt.get('git_sha')}`{' (dirty tree)' if lt.get('dirty') else ''}"
         f" (budget {lt.get('budget')}, seeds {lt.get('seeds')}, {lt.get('python_version')}). "
         "Scores are a transparent heuristic (share of runs × severity); compliance and a red "
         "self-test outrank everything. Tasks: `learned/TASKS.md`.", ""]
    if not lt:
        L += ["No measurement yet — run `python3 -m vsp.improve measure`.", ""]
    L += _headline_table(inp) + ["", "## Ranked opportunities", ""]
    if not out["opportunities"]:
        L.append("None — every signal is clean.")
    for i, o in enumerate(out["opportunities"], 1):
        L.append(f"{i}. **{o['title']}** — `{o['kind']}` · score {o['score']}"
                 + (f" · task `{o['task']['id']}`" if o.get("task") else ""))
        L.append(f"   - {o['summary']}")
        for e in o["evidence"][:4]:
            L.append(f"   - {e}")
        for e in o["examples"][:3]:
            L.append(f"   - e.g. {e}")
    L += ["", "## Signals checked", ""] + [f"- {s}" for s in out["signals"]] + [""]
    return "\n".join(L)


def render_tasks(out):
    L = ["# TASKS — agent-executable improvement tasks", "",
         f"Generated {out['created']} by `python3 -m vsp.improve diagnose` (ranked; "
         f"machine-readable twin: `learned/tasks.json`; `python3 -m vsp.improve delegate "
         f"<id>` hands one to Muse Code).", "",
         "Rules for every task: work on a new branch/worktree (never main); never edit "
         "`vsp/gates.py`, `vsp/rules.py` or `vsp/lexicon.py` to make a check pass — fix the "
         "generator; never touch the yardstick (`evals/golden.jsonl`, `evals/holdout.jsonl`, "
         "`evals/scorecard.py`, `vsp/rubric.py`); a task is done only when its acceptance "
         "command prints ACCEPT; open a PR with the evidence and never merge it yourself.", ""]
    if not out["tasks"]:
        L.append("No open tasks.")
    for i, t in enumerate(out["tasks"], 1):
        L += [f"## {i}. `{t['id']}` — {t['title']}", "",
              f"- **score** {t['score']} · kind `{t['kind']}` · first seen {t['first_seen']}",
              f"- **why**: {t['rationale']}"]
        for e in t["evidence"][:3]:
            L.append(f"- **evidence**: {e}")
        for e in t["examples"][:2]:
            L.append(f"- **example**: {e}")
        L.append("- **files likely involved**: " + ", ".join(f"`{f}`" for f in t["files"]))
        L.append(f"- **done when**: {t['done_when']}")
        if t.get("self_serve"):
            L.append(f"- **engine can do it**: `{t['self_serve']}`")
        L += [f"- **acceptance**: `{t['acceptance']}`", ""]
    return "\n".join(L)


def top_tasks(n=3):
    return ((C.read_json(C.learned("tasks.json")) or {}).get("tasks") or [])[:n]
