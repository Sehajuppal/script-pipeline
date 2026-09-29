"""Declarative gate-rule registry (pipeline v2 — RULES.md §66).

    Rule(id, title, stage, severity, source, check, covers=())

  id        RULES.md id ("D136") or a stable name for pre-numbering checks
            ("REQ-KEYS"). Unique per stage (D138 exists in both stages).
  stage     "script" (gate 1) | "bundle" (gate 2)
  severity  "error" (fails the gate) | "warn" (reported, never fails)
  source    where the rule comes from (RULES.md entry + evidence)
  check     check(script, bundle_text, ctx) -> list[str] of messages
            (bundle_text is None for script-stage rules)
  covers    every RULES.md id the rule enforces (defaults to (id,)); read by
            tools/rule_coverage.py to classify rules as GATE-enforced

REGISTRY order IS the evaluation order and therefore the message order:
the legacy checks first, exactly in their d8f8759 order (vsp/gates.py keeps
their code), then the v2 rules. Each v2 message starts with "<id>:" so
evals/scorecard.rule_id() and the repair loop can key on it.

A check that raises is reported as an ERROR finding for its rule ("failing
closed") — a crashing check can never turn into a silent pass.
"""
import re
from collections import namedtuple

from vsp import config
from vsp import gates as G
from vsp import lexicon as L

Rule = namedtuple("Rule", "id title stage severity source check covers")
Rule.__new__.__defaults__ = ((),)

STAGES = ("script", "bundle")
SEVERITIES = ("error", "warn")


# ------------------------------------------------------------------ helpers
def _txt(v):
    if v is None:
        return ""
    return v if isinstance(v, str) else str(v)


def items(script):
    """hook_stack + beats, dict items only, hook_stack first."""
    out = []
    for key in ("hook_stack", "beats"):
        v = script.get(key)
        if isinstance(v, list):
            out.extend(it for it in v if isinstance(it, dict))
    return out


VIEWER_FIELDS = ("dialogue", "rehook", "on_screen")


def viewer_fields(script):
    """(label, text) for every viewer-facing string: dialogue, rehook and
    on_screen of hook_stack + beats, then the caption."""
    out = []
    for it in items(script):
        for k in VIEWER_FIELDS:
            t = _txt(it.get(k))
            if t.strip():
                out.append((f"{_txt(it.get('type')) or '?'} {k}", t))
    cap = _txt(script.get("caption"))
    if cap.strip():
        out.append(("caption", cap))
    return out


def viewer_text(script):
    return "\n".join(t for _, t in viewer_fields(script))


def _type(it):
    return _txt(it.get("type")).strip().upper()


def is_verbal_hook(it):
    t = _type(it)
    return "VERBAL HOOK" in t or t == "HOOK"


def verbal_hook_items(script):
    return [it for it in items(script) if is_verbal_hook(it)]


def verbal_hook(script):
    """The spoken hook line: first verbal-hook item with dialogue (hook_stack
    first) — the same line vsp.rubric.hook_line() reads for maker scripts."""
    for it in verbal_hook_items(script):
        d = _txt(it.get("dialogue")).strip()
        if d:
            return d
    for it in items(script):
        d = _txt(it.get("dialogue")).strip()
        if "HOOK" in _type(it) and d:
            return d
    return ""


def frame0_item(script):
    """The frame-0 overlay carrier: the VISUAL TRIGGER in the hook stack,
    else hook_stack[0] when it carries on_screen (vsp.rubric.frame0_overlay),
    else the first VISUAL TRIGGER beat (legacy fixture shape)."""
    hs = [it for it in (script.get("hook_stack") or []) if isinstance(it, dict)]
    for it in hs:
        if _type(it) == "VISUAL TRIGGER":
            return it
    if hs and _txt(hs[0].get("on_screen")).strip():
        return hs[0]
    for it in script.get("beats") or []:
        if isinstance(it, dict) and _type(it) == "VISUAL TRIGGER":
            return it
    return None


def window(it):
    s, e = G.parse_t(_txt(it.get("t")))
    return s, e


def build_ctx(script, bundle_text=None):
    prompt = _txt(script.get("prompt"))
    return {"prompt": prompt, "prompt_low": prompt.lower(),
            "presenter": _txt(script.get("presenter")).strip().lower(),
            "viewer_text": viewer_text(script),
            "fixture_ok": config.fixture_ok()}


def _q(s, n=70):
    """Short quoted excerpt for a message. '; ' is the report's message
    separator (pipeline.py joins with it, evals/scorecard.py splits on it),
    so it never appears inside an excerpt."""
    s = " ".join(_txt(s).split()).replace("; ", ", ")
    return repr(s if len(s) <= n else s[:n - 1] + "…")


# ------------------------------------------------------- v2 gate-1 rules
def check_d136(script, bundle_text, ctx):
    """D136: no unsourced social proof unless the prompt supplies it."""
    hits = []
    for rx in L.SOCIAL_PROOF:
        m = rx.search(ctx["viewer_text"])
        if m and not rx.search(ctx["prompt"]):
            hits.append(_q(m.group(0), 30))
    if hits:
        return [f"D136: unsourced social proof in viewer text ({', '.join(hits)})"
                f" — the prompt supplies no such claim (FTC 16 CFR 465, D37 class)"]
    return []


def check_d137(script, bundle_text, ctx):
    """D137: an AI persona never claims lived experience."""
    if ctx["presenter"] != "ai":
        return []
    hits = []
    for rx in L.AI_FIRST_PERSON:
        m = rx.search(ctx["viewer_text"])
        if m:
            hits.append(_q(m.group(0), 30))
    if hits:
        return [f"D137: AI persona claims lived experience ({', '.join(hits)})"
                f" — an AI presenter never used the product (FTC 16 CFR 465.2),"
                f" frame it as a curator"]
    return []


AI_WORD = L.AI_WORD                    # shared with the rubric
DISCLOSURE_CUE = L.AI_DISCLOSURE_CUE


def check_d138(script, bundle_text, ctx):
    """D138 (gate 1): presenter=ai carries a disclosure field naming the AI
    and a caption disclosure line."""
    if ctx["presenter"] != "ai":
        return []
    out = []
    disc = _txt(script.get("disclosure")).strip()
    if not disc or not AI_WORD.search(disc):
        out.append("D138: presenter=ai but the script's 'disclosure' field is "
                   "missing or never names the AI persona — the frame-0 label "
                   "has no source")
    if not L.has_ai_disclosure_line(_txt(script.get("caption"))):
        out.append("D138: presenter=ai but the caption has no AI disclosure line "
                   "(e.g. 'made with an AI persona') — EU AI Act Art. 50 / NY "
                   "synthetic-performer law")
    return out


def check_d139(script, bundle_text, ctx):
    """D139: no generic engagement bait (keyword->DM CTA is not bait)."""
    hits = []
    for m in L.GENERIC_BAIT.finditer(ctx["viewer_text"]):
        h = _q(m.group(0), 30)
        if h not in hits:
            hits.append(h)
    if hits:
        return [f"D139: generic engagement bait ({', '.join(hits[:3])}) — "
                f"Meta/Instagram demote explicit like/tag/share asks — use the "
                f"keyword-to-DM comment CTA (B4a)"]
    return []


HASHTAG = re.compile(r"#(\w*[A-Za-z_]\w*)")


def check_d140(script, bundle_text, ctx):
    """D140: 1-5 hashtags, not generic-only."""
    tags = [t.lower() for t in HASHTAG.findall(_txt(script.get("caption")))]
    if not 1 <= len(tags) <= L.MAX_HASHTAGS:
        return [f"D140: {len(tags)} hashtags in the caption — need 1–"
                f"{L.MAX_HASHTAGS} (Instagram cap since Dec 2025)"]
    if all(t in L.GENERIC_TAGS for t in tags):
        return [f"D140: generic-only hashtags ({' '.join('#' + t for t in tags)})"
                f" — no niche signal, tag the niche community"]
    return []


def _claim_key(text):
    t = " ".join(text.lower().split())
    for stem, key in (("guarantee", "guarantee"), ("cure", "cure"),
                      ("best", "best ever"), ("risk", "risk-free"),
                      ("number one", "#1"), ("#1", "#1")):
        if t.startswith(stem):
            return key
    return t


def check_d141(script, bundle_text, ctx):
    """D141: no absolute/guarantee claims unless the prompt makes them."""
    allowed = {_claim_key(m.group(0)) for m in L.ABSOLUTE.finditer(ctx["prompt"])}
    hits = []
    for m in L.ABSOLUTE.finditer(ctx["viewer_text"]):
        h = _q(m.group(0), 30)
        if _claim_key(m.group(0)) not in allowed and h not in hits:
            hits.append(h)
    if hits:
        return [f"D141: absolute/guarantee claim ({', '.join(hits[:3])}) not "
                f"supplied by the prompt — TikTok ad/Shop policy bans '#1', "
                f"'guaranteed', 'cure'-class claims"]
    return []


def check_d144(script, bundle_text, ctx):
    """D144 (+D17): the frame-0 overlay is <=3 words and a contiguous phrase
    of the verbal hook or a label form. Silent when there is no overlay."""
    it = frame0_item(script)
    ov = _txt(it.get("on_screen")).strip() if it else ""
    if not ov:
        return []
    n = len(L.norm(ov).split())
    if n > 3:
        return [f"D144: frame-0 overlay {_q(ov, 40)} is {n} words — the "
                f"overlay is <=3 words (D17)"]
    hook = verbal_hook(script)
    ok, why = L.overlay_is_clean(ov, hook)
    if not ok:
        return [f"D144: frame-0 overlay {_q(ov, 40)} is {why} {_q(hook, 60)}"
                f" — use a contiguous <=3-word hook phrase or a label form (D17)"]
    return []


def check_d31(script, bundle_text, ctx):
    """D31: no raw {template slot} in viewer text."""
    where = []
    for label, t in viewer_fields(script):
        idx = [i for i in (t.find("{"), t.find("}")) if i >= 0]
        if idx:
            i = min(idx)
            where.append(f"{label} {_q(t[max(0, i - 20):i + 25], 50)}")
    if where:
        more = f", +{len(where) - 1} more" if len(where) > 1 else ""
        return [f"D31: raw template slot in viewer text ({where[0]}{more}) — "
                f"a {{slot}} never reaches the viewer"]
    return []


def check_d73(script, bundle_text, ctx):
    """D73: the verbal hook is <=8 words. Counted exactly like the maker's
    D61/D73 filters in pick_hook: whitespace tokens (len(line.split())), so
    a standalone em dash counts, as it does in the maker (D54 note)."""
    out = []
    for it in verbal_hook_items(script):
        dlg = _txt(it.get("dialogue")).strip()
        n = len(dlg.split())
        if n > 8:
            out.append(f"D73: verbal hook is {n} words (> 8) on {_type(it)}: "
                       f"{_q(dlg, 80)} — the whole line lands in the "
                       f"0.5–3.0s window")
    return out


def check_d93(script, bundle_text, ctx):
    """D93: the same re-hook (normalized) never appears twice."""
    seen, dups = set(), []
    for it in items(script):
        k = L.norm(_txt(it.get("rehook")))
        if not k:
            continue
        if k in seen and k not in dups:
            dups.append(k)
        seen.add(k)
    return [f"D93: re-hook repeated within one script: {_q(k, 80)}"
            for k in dups]


def _has_series_plan(script):
    plan = script.get("series_plan")
    if isinstance(plan, str):
        return bool(plan.strip())
    return bool(plan)


def check_d146(script, bundle_text, ctx):
    """D146: a CTA promising a part 2 needs script['series_plan']."""
    if _has_series_plan(script):
        return []
    for it in items(script):
        if not re.search(r"\bCTA\b", _type(it)):
            continue
        for k in VIEWER_FIELDS:
            t = _txt(it.get(k))
            if L.PART2.search(t):
                return [f"D146: CTA promises a part 2 ({_q(t, 60)}) but the "
                        f"script has no series_plan — an unplanned series "
                        f"promise is a broken contract"]
    return []


def check_d142(script, bundle_text, ctx):
    """D142 (warn): on-screen text <=20 chars/s over its display window. The
    frame-0 overlay is displayed from 0 s to the end of the verbal hook
    (at least 3.0 s)."""
    f0 = frame0_item(script)
    ends = [window(it)[1] for it in verbal_hook_items(script)]
    hook_end = max([e for e in ends if e is not None] + [3.0])
    out = []
    for it in items(script):
        ov = _txt(it.get("on_screen")).strip()
        if not ov:
            continue
        if it is f0:
            a, e = 0.0, hook_end
        else:
            a, e = window(it)
            if a is None or e is None or e <= a:
                continue
        cps = len(ov) / (e - a)
        if cps > 20:
            out.append(f"D142: on_screen reads at {cps:.0f} chars/s (> 20) on "
                       f"{_type(it)} ({len(ov)} chars in {e - a:.1f}s): "
                       f"{_q(ov, 40)}")
    return out


# ------------------------------------------------------- v2 gate-2 rules
AI_LABEL_INSTRUCTION = re.compile(
    r"[\"\u201c]AI persona[\"\u201d]\s+label\b[^\n]{0,60}?\bframe[\s-]*0\b",
    re.I)


def check_d138_brief(script, bundle_text, ctx):
    """D138 (gate 2): presenter=ai brief carries the frame-0 label order."""
    if ctx["presenter"] != "ai":
        return []
    if not AI_LABEL_INSTRUCTION.search(bundle_text or ""):
        return ["D138: AI-persona label instruction missing from brief"]
    return []


URL = re.compile(r"https?://[^\s)>\]\"']+")


def check_d151(script, bundle_text, ctx):
    """D151: FIXTURE reference reels never ship (VSP_FIXTURE_OK=1 = tests)."""
    if ctx["fixture_ok"]:
        return []
    bad = [u for u in URL.findall(bundle_text or "") if "FIXTURE" in u]
    if bad:
        return [f"D151: {len(bad)} FIXTURE reference reel(s) in the brief "
                f"(e.g. {bad[0]}) — hermetic test data is not a quality bar "
                f"(VSP_FIXTURE_OK=1 is for self-test/evals only)"]
    return []


# ------------------------------------------------------------- registry
def _legacy1(fn):
    def check(script, bundle_text, ctx):
        return fn(script)
    check.legacy = fn   # traceable: the self-test asserts the legacy order
    check.__doc__ = f"legacy vsp.gates.{fn.__name__}"
    return check


def _legacy2(fn):
    def check(script, bundle_text, ctx):
        return fn(bundle_text, script)
    check.legacy = fn
    check.__doc__ = f"legacy vsp.gates.{fn.__name__}"
    return check


_S, _B, _E, _W = "script", "bundle", "error", "warn"

LEGACY_SCRIPT_RULES = (
    # ---- gate 1, legacy (d8f8759 order — message order is contract) ----
    Rule("REQ-KEYS", "required keys present (prompt, hook_stack, beats, "
         "caption, niche)", _S, _E, "pipeline.py gate1 (pre-numbering)",
         _legacy1(G.g1_required_keys)),
    Rule("MIN-BEATS", ">= 3 beats", _S, _E, "pipeline.py gate1 (pre-numbering)",
         _legacy1(G.g1_min_beats)),
    Rule("D37", "no invented prices (beats + caption; prompt = allow-path)",
         _S, _E, "RULES.md §24 D37 (cycle 12) + §61 D132 (gauntlet 18)",
         _legacy1(G.g1_d37_price), ("D37", "D132")),
    Rule("TAG-MISMATCH", "hashtag/niche mismatch (MISMATCH stems vs prompt)",
         _S, _E, "pipeline.py gate1 (pre-numbering; D107 context)",
         _legacy1(G.g1_tag_mismatch)),
    Rule("D43", "dialogue fits its beat window (and every beat has one)",
         _S, _E, "RULES.md §25 D43 (seed-701 audit)",
         _legacy1(G.g1_d43_windows)),
    Rule("D44", "no stage directions / parenthetical notes in spoken lines",
         _S, _E, "RULES.md §25 D44 + §29 D58 (gauntlets 4/5/12) + §55 D126",
         _legacy1(G.g1_d44_stage_directions), ("D44", "D58", "D126")),
    Rule("D55", "beat windows never overlap", _S, _E,
         "RULES.md §28 D55 (gauntlet 1, seed 800)", _legacy1(G.g1_d55_overlap)),
    Rule("D74", "beats end within duration_s", _S, _E,
         "RULES.md D74 (gauntlet 2, seed 801)", _legacy1(G.g1_d74_budget)),
    Rule("D78", "no dead-air gap > 0.5 s between beats", _S, _E,
         "RULES.md D78 (gauntlet 3, seed 802)", _legacy1(G.g1_d78_gaps)),
    Rule("D94", "PAYOFF lands where the hook's contract promised", _S, _E,
         "RULES.md §43 D94 (gauntlet 6, seed 805)",
         _legacy1(G.g1_d94_contract)),
    Rule("D103", "on_screen is display text (<= 12 words)", _S, _E,
         "RULES.md §46 D103 (gauntlet 8, seed 807)",
         _legacy1(G.g1_d103_onscreen)),
    Rule("D111", "no dangling 'Test 1' without 'Test 2'", _S, _E,
         "RULES.md §50 D111 (gauntlet 11, seed 810)",
         _legacy1(G.g1_d111_test_numbering)),
)

V2_SCRIPT_RULES = (
    # ---- gate 1, pipeline v2 (RULES.md §66) ----
    Rule("D136", "no unsourced social proof", _S, _E,
         "RULES.md §66 D136; FTC 16 CFR 465 (consumer-review rule)",
         check_d136),
    Rule("D137", "AI persona never claims lived experience", _S, _E,
         "RULES.md §66 D137; FTC 16 CFR 465.2", check_d137),
    Rule("D138", "AI disclosure: disclosure field + caption line", _S, _E,
         "RULES.md §66 D138; EU AI Act Art. 50, NY synthetic-performer law, "
         "platform AIGC labels", check_d138),
    Rule("D139", "no generic engagement bait", _S, _E,
         "RULES.md §66 D139; Meta engagement-bait guidelines, Instagram "
         "recommendation eligibility", check_d139),
    Rule("D140", "1-5 hashtags, not generic-only", _S, _E,
         "RULES.md §66 D140; Instagram 5-hashtag cap (Dec 2025)", check_d140),
    Rule("D141", "no absolute/guarantee claims unless in the prompt", _S, _E,
         "RULES.md §66 D141; TikTok ad policy (misleading/false content), "
         "TikTok Shop content policy 2026-05-22", check_d141),
    Rule("D144", "frame-0 overlay: <=3-word contiguous hook phrase or label",
         _S, _E, "RULES.md §66 D144; §10 D17/D17b (frame-0 <=3 words) made "
         "gate-enforced", check_d144, ("D144", "D17")),
    Rule("D31", "no raw {template slot} in viewer text", _S, _E,
         "RULES.md D31 (cycle 11), gate-enforced per §66", check_d31),
    Rule("D73", "verbal hook <= 8 words (maker's pick_hook count)", _S, _E,
         "RULES.md §34 D73 (cycle 18), gate-enforced per §66", check_d73),
    Rule("D93", "no repeated re-hook within a script", _S, _E,
         "RULES.md D93, gate-enforced per §66", check_d93),
    Rule("D146", "part-2 CTA needs a series_plan", _S, _E,
         "RULES.md §66 D146 (D89 part-2 CTA class)", check_d146),
    Rule("D142", "on-screen text <= 20 chars/s over its window", _S, _W,
         "RULES.md §66 D142 (PROPOSED); Netflix timed-text 20 cps", check_d142),
)

LEGACY_BUNDLE_RULES = (
    # ---- gate 2, legacy (d8f8759 order) ----
    Rule("DELIVERABLE", "DELIVERABLE block present verbatim (strengthened: "
         "full block)", _B, _E, "AGENT-BRIEF non-negotiable #4; "
         "make_shotlist.DELIVERABLE", _legacy2(G.g2_deliverable)),
    Rule("RENDER-9x16", "9:16 render spec", _B, _E, "pipeline.py gate2",
         _legacy2(G.g2_render_spec)),
    Rule("WORDS-JSON", "words.json requested", _B, _E, "pipeline.py gate2",
         _legacy2(G.g2_words_json_requested)),
    Rule("DO-NOT", "Do-NOT list present", _B, _E, "pipeline.py gate2",
         _legacy2(G.g2_do_not)),
    Rule("WORDS-SCHEMA", "words.json schema present", _B, _E,
         "pipeline.py gate2", _legacy2(G.g2_words_schema)),
    Rule("REF-REELS", ">= 1 reference reel", _B, _E, "pipeline.py gate2",
         _legacy2(G.g2_reference_reels)),
    Rule("D43-BUNDLE", "no D43 WARNING in the bundle", _B, _E,
         "RULES.md §25 D43", _legacy2(G.g2_d43_warnings), ("D43",)),
    Rule("D36", "'same body' only for body transformations", _B, _E,
         "RULES.md §23 D36 (seed 701)", _legacy2(G.g2_d36_same_body)),
    Rule("B4a", "comment bait asks follow before the keyword", _B, _E,
         "RULES.md §23 B4a (seed 701, Ramonov)",
         _legacy2(G.g2_b4a_follow_first)),
    Rule("D46", "one link destination", _B, _E, "RULES.md §25 D46",
         _legacy2(G.g2_d46_link_ctas)),
    Rule("SHOT-DRIFT", "shot timeline within 15% of duration", _B, _E,
         "pipeline.py gate2", _legacy2(G.g2_shot_drift)),
    Rule("D48", "long shots carry internal cuts/camera moves", _B, _E,
         "RULES.md §27 D48", _legacy2(G.g2_d48_internal_cuts)),
    Rule("D47", "no 3+ consecutive talking-head shots", _B, _E,
         "RULES.md §27 D47 (shot scale)", _legacy2(G.g2_d47_shot_scale)),
)

V2_BUNDLE_RULES = (
    # ---- gate 2, pipeline v2 ----
    Rule("D138", "AI-persona frame-0 label instruction in the brief", _B, _E,
         "RULES.md §66 D138; make_shotlist persona fidelity block",
         check_d138_brief),
    Rule("D151", "no FIXTURE reference reels unless VSP_FIXTURE_OK=1", _B, _E,
         "RULES.md §66 D151; vsp/fixtures.py", check_d151),
)

REGISTRY = (LEGACY_SCRIPT_RULES + V2_SCRIPT_RULES
            + LEGACY_BUNDLE_RULES + V2_BUNDLE_RULES)

LEGACY_IDS = {"script": tuple(r.id for r in LEGACY_SCRIPT_RULES),
              "bundle": tuple(r.id for r in LEGACY_BUNDLE_RULES)}


def rules_for(stage):
    return [r for r in REGISTRY if r.stage == stage]


def covers(rule):
    return tuple(rule.covers) or (rule.id,)


def evaluate(stage, script, bundle_text=None, ctx=None):
    """Run every rule of `stage` in registry order -> findings."""
    if stage not in STAGES:
        raise ValueError(f"unknown stage {stage!r}")
    try:
        ctx = ctx or build_ctx(script, bundle_text)
    except Exception as e:  # malformed script: legacy checks still run
        ctx = {"prompt": "", "prompt_low": "", "presenter": "",
               "viewer_text": "", "fixture_ok": config.fixture_ok(),
               "ctx_error": repr(e)}
    out = []
    for r in rules_for(stage):
        try:
            msgs = r.check(script, bundle_text, ctx) or []
        except Exception as e:  # fail closed, loudly
            out.append({"rule": r.id, "severity": "error",
                        "message": f"{r.id}: check crashed "
                                   f"({type(e).__name__}: {e}) — failing closed"})
            continue
        legacy = hasattr(r.check, "legacy")
        for m in msgs:
            if not legacy:   # '; ' is the report separator (never in v2 text)
                m = m.replace("; ", ", ")
            out.append({"rule": r.id, "severity": r.severity, "message": m})
    return out


def registry_table():
    """[(id, stage, severity, title, source, covers)] for docs/reports."""
    return [(r.id, r.stage, r.severity, r.title, r.source, covers(r))
            for r in REGISTRY]
