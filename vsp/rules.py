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
    # a split-screen label pair ("DAY 1 | DAY 7", D25/D135) is two labels,
    # not a phrase — lexicon.overlay_is_clean caps each side at 2 words
    if n > 3 and "|" not in ov:
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


# ------------------------------------------- v2.1 gate-1 rules (RULES §68)
# Each rule validates ONLY what is present: silent when its key (or, for
# D158, a matching phrase) is absent, so legacy fixtures and --script-json
# inputs keep their exact outcomes (docs/CREATIVE-PLAN.md §0.2). Messages:
# "<id>: <what>" — one per distinct problem, capped at MAX_MSGS per rule.
MAX_MSGS = 6
LETTERS = "ABCDEFGHIJ"
HV_TEXT_FIELDS = ("verbal", "overlay", "visual", "audio", "caption_line")
HV_VIEWER_FIELDS = ("verbal", "overlay", "caption_line")
AI_TOGGLES = {"tiktok": "is_aigc", "instagram": "is_ai_generated",
              "youtube_shorts": "containsSyntheticMedia"}
HASHTAG_CAPS = {"tiktok": 5, "instagram": 5, "youtube_shorts": 15}
CAPTION_CAPS = {"tiktok": 2200, "instagram": 2200}    # DISC-06 hard limits
YT_TITLE_MAX, YT_DESC_MAX_BYTES, COVER_MAX_WORDS = 100, 5000, 5
WPM_RANGE = (140, 200)
MAX_STATIC_S = 3.5
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
GRADES = ("P", "S", "M", "A")
HUMORS = ("none", "light", "high")
AI_MUSIC = re.compile(r"\bAI[- ](?:generated )?(?:music|track|song|soundtrack|beat)s?\b|"
                      r"\bgenerated (?:music|track|song)s?\b|\bsuno\b|\budio\b", re.I)
NEGATION = re.compile(r"\b(?:no|never|not|don'?t|do not|avoid|without|nor|isn'?t)\b",
                      re.I)
SYNTH_VOICE = re.compile(r"\b(?:synthetic|AI[- ]generated|AI voice|generated voice|"
                         r"text[- ]to[- ]speech|TTS|voice clone|cloned voice|"
                         r"synthesi[sz]ed)\b", re.I)
DISCLOSED = re.compile(r"\bdisclos\w*", re.I)
HUMAN_CLAIM = re.compile(r"\b(?:human voice(?: only)?|human read|real (?:human|person)|"
                         r"a real person|actual person|not (?:an? )?AI|not synthetic|"
                         r"100% human|recorded by a human)\b", re.I)


def _norm_ws(s):
    return " ".join(_txt(s).split())


def _first3(text):
    return tuple(L.norm(text).split()[:3])


def _negated(text, start, span=28):
    """True when a negation word sits just before `start` in `text`."""
    return bool(NEGATION.search(text[max(0, start - span):start]))


def _affirmed(rx, text):
    """First match of rx in text that is not negated (per line) or None."""
    for ln in (text or "").splitlines():
        for m in rx.finditer(ln):
            if not _negated(ln, m.start()):
                return m
    return None


def _prompt_claim_keys(prompt):
    return {_claim_key(m.group(0)) for m in L.ABSOLUTE.finditer(prompt or "")}


def claim_screens(text, ctx, ai=None):
    """The primary-hook screens (D37, D136, D139, D141, D158, D31 braces,
    + D137 when ai) applied to one viewer-facing string -> ['D37 price
    '$25'', ...] (rule id + excerpt), in that order."""
    t = _txt(text)
    prompt = ctx["prompt"]
    out = []
    if not t.strip():
        return out
    if "{" in t or "}" in t:
        out.append("D31 raw {slot}")
    m = L.PRICE.search(t) or re.search(r"\$\d+", t)
    if m and not L.price_in(prompt):
        out.append(f"D37 price {_q(m.group(0), 20)}")
    for rx in L.SOCIAL_PROOF:
        m = rx.search(t)
        if m and not rx.search(prompt):
            out.append(f"D136 social proof {_q(m.group(0), 30)}")
            break
    m = L.GENERIC_BAIT.search(t)
    if m:
        out.append(f"D139 bait {_q(m.group(0), 30)}")
    allowed = _prompt_claim_keys(prompt)
    for m in L.ABSOLUTE.finditer(t):
        if _claim_key(m.group(0)) not in allowed:
            out.append(f"D141 absolute {_q(m.group(0), 30)}")
            break
    for pid, cls, hit in L.offer_urgency_hits(t, prompt):
        out.append(f"D158 {cls} {_q(hit, 30)}")
        break
    if ai is None:
        ai = ctx.get("presenter") == "ai"
    if ai:
        m = L.first_match(L.AI_FIRST_PERSON, t)
        if m:
            out.append(f"D137 lived experience {_q(m.group(0), 30)}")
    return out


def _cap(msgs, rid):
    if len(msgs) > MAX_MSGS:
        msgs = msgs[:MAX_MSGS - 1] + [f"{rid}: +{len(msgs) - MAX_MSGS + 1} more "
                                      f"problem(s) of the same kind"]
    return msgs


def _overlay_words(ov):
    return len(L.norm(ov).split())


def check_d154(script, bundle_text, ctx):
    """D154 (§1.2): hook_variants integrity. Silent when the key is absent."""
    from vsp import creative_vocab as CV
    hv = script.get("hook_variants")
    if hv is None:
        return []
    if not isinstance(hv, list):
        return [f"D154: hook_variants is a {type(hv).__name__}, not a list of "
                f"variants"]
    out = []
    n = len(hv)
    if not 3 <= n <= 5:
        out.append(f"D154: {n} hook variant(s) — the contract is 3–5 (variant "
                   f"A = the script's hook + 2–4 alternates)")
    vs = [v for v in hv if isinstance(v, dict)]
    if len(vs) != n:
        out.append(f"D154: {n - len(vs)} hook variant(s) are not objects")
    if not vs:
        return out
    ids = [_txt(v.get("id")) for v in vs]
    if ids != list(LETTERS[:len(vs)]):
        out.append(f"D154: variant ids {ids} — must be unique and lettered "
                   f"A, B, C… in order")
    prim = [i for i, v in enumerate(vs) if v.get("is_primary") is True]
    if prim != [0] or any(v.get("is_primary") not in (None, False, True)
                          for v in vs):
        out.append(f"D154: is_primary on {[ids[i] for i in prim] or 'no variant'}"
                   f" — exactly one primary, and it is variant A")
    a = vs[0]
    hook, it0 = verbal_hook(script), frame0_item(script)
    f0 = _txt(it0.get("on_screen")) if it0 else ""
    if _norm_ws(a.get("verbal")) != _norm_ws(hook):
        out.append(f"D154: variant A verbal {_q(a.get('verbal'), 50)} != the "
                   f"script's VERBAL HOOK {_q(hook, 50)}")
    if _norm_ws(a.get("overlay")) != _norm_ws(f0):
        out.append(f"D154: variant A overlay {_q(a.get('overlay'), 30)} != the "
                   f"VISUAL TRIGGER on_screen {_q(f0, 30)}")
    vts = [_txt(v.get("visual_type")) for v in vs]
    bad_vt = [x for x in vts if x not in CV.VISUAL_TYPES]
    if bad_vt:
        out.append(f"D154: unknown visual_type {bad_vt} (creative_vocab.VISUAL_TYPES)")
    dup_vt = sorted({x for x in vts if vts.count(x) > 1})
    if dup_vt:
        out.append(f"D154: visual_type repeated across variants {dup_vt} — "
                   f"openings that share a frame-0 visual are one creative")
    arcs = [_txt(v.get("archetype")) for v in vs]
    bad_a = [x for x in arcs if x not in CV.HOOK_ARCHETYPES]
    if bad_a:
        out.append(f"D154: unknown archetype {bad_a} (creative_vocab.HOOK_ARCHETYPES)")
    if len(vs) >= 4 and len(set(arcs)) < 3:
        out.append(f"D154: {len(set(arcs))} distinct archetype(s) across "
                   f"{len(vs)} variants — need at least 3")
    f3 = [_first3(v.get("verbal")) for v in vs]
    dup3 = sorted({" ".join(x) for x in f3 if x and f3.count(x) > 1})
    if dup3:
        out.append(f"D154: variants share their first three words {dup3}")
    ai = ctx["presenter"] == "ai"
    for v, vid in zip(vs, ids):
        tag = f"variant {vid or '?'}"
        verbal, ov = _txt(v.get("verbal")).strip(), _txt(v.get("overlay")).strip()
        nw = len(verbal.split())
        if not verbal or nw > 8:
            out.append(f"D154: {tag} verbal is {nw} words (1–8): {_q(verbal, 60)}")
        if ov:
            if _overlay_words(ov) > 3 and "|" not in ov:
                out.append(f"D154: {tag} overlay {_q(ov, 40)} is "
                           f"{_overlay_words(ov)} words (<= 3)")
            else:
                ok, why = L.overlay_is_clean(ov, verbal)
                if not ok:
                    out.append(f"D154: {tag} overlay {_q(ov, 40)} is {why} "
                               f"{_q(verbal, 50)}")
        for k in HV_TEXT_FIELDS:
            t = _txt(v.get(k))
            if k not in HV_VIEWER_FIELDS:
                if "{" in t or "}" in t:
                    out.append(f"D154: {tag} {k} carries a raw {{slot}}")
                continue
            hits = claim_screens(t, ctx, ai=ai)
            if hits:
                out.append(f"D154: {tag} {k} {_q(t, 50)} fails the hook "
                           f"screens ({', '.join(hits)})")
        flags = CV.HOOK_ARCHETYPES.get(_txt(v.get("archetype"))) or {}
        if ai and flags.get("human_only"):
            out.append(f"D154: {tag} archetype {v.get('archetype')!r} is "
                       f"human-only — an AI presenter has no lived story (D137)")
        need = [(flags.get("requires_price"), L.price_in, "a price (D37)"),
                (flags.get("requires_proof"), L.proof_in, "proof (D136)"),
                (flags.get("requires_offer"), L.offer_in, "an offer (D158)")]
        for req, fn, what in need:
            if req and not fn(ctx["prompt"]):
                out.append(f"D154: {tag} archetype {v.get('archetype')!r} "
                           f"needs {what} and the prompt supplies none")
    return _cap(out, "D154")


def _line1(text):
    for ln in _txt(text).splitlines():
        if ln.strip():
            return ln.strip()
    return ""


def _tags(text):
    return [t.lower() for t in HASHTAG.findall(_txt(text))]


def _link_names(groups):
    from vsp.creative_vocab import LINK_GROUPS
    return "/".join(repr(LINK_GROUPS[i][0]) for i in sorted(groups)) or "none"


def _platform_texts(name, entry):
    """(field, text) for the viewer-facing strings of one platform entry."""
    keys = {"youtube_shorts": ("title", "description")}.get(
        name, ("caption", "description_line"))
    return [(k, _txt(entry.get(k))) for k in keys if _txt(entry.get(k)).strip()]


def check_d155(script, bundle_text, ctx):
    """D155 (§1.3): discovery packaging integrity. Silent when absent."""
    from vsp.creative_vocab import link_groups_in
    d = script.get("discovery")
    if d is None:
        return []
    if not isinstance(d, dict):
        return [f"D155: discovery is a {type(d).__name__}, not an object"]
    out = []
    kw = d.get("primary_keyword")
    if kw is not None and not (isinstance(kw, str) and kw.strip()):
        out.append("D155: primary_keyword is empty — nothing to place")
        kw = None
    ai = ctx["presenter"] == "ai"
    cap_groups = link_groups_in(_txt(script.get("caption")))
    plats = d.get("platforms")
    if plats is not None and not isinstance(plats, dict):
        out.append(f"D155: platforms is a {type(plats).__name__}, not an object")
        plats = None
    for name, entry in (plats or {}).items():
        if not isinstance(entry, dict):
            out.append(f"D155: platforms.{name} is not an object")
            continue
        texts = _platform_texts(name, entry)
        tags = entry.get("hashtags")
        if tags is not None and not (isinstance(tags, list)
                                     and all(isinstance(t, str) for t in tags)):
            out.append(f"D155: {name} hashtags is not a list of strings")
            tags = []
        bad = [t for t in tags or [] if not HASHTAG.fullmatch(t.strip())]
        if bad:
            out.append(f"D155: {name} hashtags {bad[:3]} are not '#tag' strings")
        every = {t.strip().lstrip("#").lower() for t in tags or [] if t.strip()}
        for _, t in texts:
            every |= set(_tags(t))
        cap = HASHTAG_CAPS.get(name)
        if cap and len(every) > cap:
            out.append(f"D155: {name} carries {len(every)} distinct hashtags "
                       f"(max {cap})")
        if every and all(t in L.GENERIC_TAGS for t in every):
            out.append(f"D155: {name} hashtags are generic-only "
                       f"({' '.join('#' + t for t in sorted(every))}) (D140)")
        for field, t in texts:
            hits = claim_screens(t, ctx, ai=ai)
            if hits:
                out.append(f"D155: {name} {field} fails the caption screens "
                           f"({', '.join(hits)})")
            groups = link_groups_in(t)
            if len(groups) > 1 or not groups <= cap_groups:
                out.append(f"D155: {name} {field} names a CTA destination the "
                           f"script caption does not (D46: "
                           f"{_link_names(groups)} vs caption "
                           f"{_link_names(cap_groups)})")
        if name in CAPTION_CAPS:
            cap_txt = _txt(entry.get("caption"))
            n16 = len(cap_txt.encode("utf-16-le")) // 2
            if n16 > CAPTION_CAPS[name]:
                out.append(f"D155: {name} caption is {n16} characters (max "
                           f"{CAPTION_CAPS[name]})")
        if name == "youtube_shorts":
            title = _txt(entry.get("title"))
            angle = "<" in title or ">" in title
            if len(title) > YT_TITLE_MAX or angle:
                out.append(f"D155: youtube_shorts title {_q(title, 40)} is "
                           f"{len(title)} chars{' with < or >' if angle else ''}"
                           f" (<= {YT_TITLE_MAX}, no < >)")
            nb = len(_txt(entry.get("description")).encode("utf-8"))
            if nb > YT_DESC_MAX_BYTES:
                out.append(f"D155: youtube_shorts description is {nb} UTF-8 "
                           f"bytes (max {YT_DESC_MAX_BYTES})")
        disc_field = "description" if name == "youtube_shorts" else "caption"
        body = _txt(entry.get(disc_field))
        if ai and body.strip() and not L.has_ai_disclosure_line(body):
            out.append(f"D155: presenter=ai but the {name} {disc_field} has no "
                       f"AI disclosure line (D138)")
        tog = entry.get("toggles")
        if ai and isinstance(tog, dict) and name in AI_TOGGLES \
                and AI_TOGGLES[name] in tog and tog[AI_TOGGLES[name]] is not True:
            out.append(f"D155: presenter=ai but {name} toggles."
                       f"{AI_TOGGLES[name]} is {tog[AI_TOGGLES[name]]!r} (must be true)")
        if kw:
            where = [("title", _txt(entry.get("title")))] \
                if name == "youtube_shorts" else \
                [("caption line 1", _line1(entry.get("caption")))]
            for field, t in where:
                if t and not L.keyword_in(t, kw):
                    out.append(f"D155: primary keyword {_q(kw, 30)} missing "
                               f"from the {name} {field} {_q(t, 50)}")
    cover = d.get("cover")
    if isinstance(cover, dict):
        ct = _txt(cover.get("text"))
        if len(ct.split()) > COVER_MAX_WORDS:
            out.append(f"D155: cover text {_q(ct, 40)} is {len(ct.split())} "
                       f"words (<= {COVER_MAX_WORDS})")
        hits = claim_screens(ct, ctx, ai=ai)
        if hits:
            out.append(f"D155: cover text fails the screens ({', '.join(hits)})")
        fs = cover.get("frame_s")
        dur = script.get("duration_s") or 30
        if fs is not None and not (isinstance(fs, (int, float))
                                   and not isinstance(fs, bool)
                                   and 0 <= fs <= float(dur)):
            out.append(f"D155: cover frame_s {fs!r} is outside the video "
                       f"(0–{dur}s)")
    elif cover is not None:
        out.append("D155: cover is not an object")
    return _cap(out, "D155")


def _sized_wpm(it):
    """The rate the maker sized this item's window for (D43/D143): 150 wpm
    when its delivery carries a SLOW_KEY, else 180."""
    return 60.0 * G.words_per_sec(_txt(it.get("delivery")))


def _pair(v, lo=None, hi=None):
    """[a, b] numbers with a <= b (and within [lo, hi]) -> (a, b) or None."""
    if not (isinstance(v, (list, tuple)) and len(v) == 2 and all(
            isinstance(x, (int, float)) and not isinstance(x, bool) for x in v)):
        return None
    a, b = float(v[0]), float(v[1])
    if a > b or (lo is not None and a < lo) or (hi is not None and b > hi):
        return None
    return a, b


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_d156(script, bundle_text, ctx):
    """D156: direction integrity (ids, pacing, music lane, AI voice, energy
    curve). Silent when script['direction'] is absent."""
    from vsp import creative_vocab as CV
    d = script.get("direction")
    if d is None:
        return []
    if not isinstance(d, dict):
        return [f"D156: direction is a {type(d).__name__}, not an object"]
    out = []
    if "schema_version" in d and d.get("schema_version") != 1:
        out.append(f"D156: schema_version {d.get('schema_version')!r} (want 1)")
    if "vibe" in d and d.get("vibe") not in CV.VIBES:
        out.append(f"D156: vibe {d.get('vibe')!r} is not a creative_vocab.VIBES id")
    sv = d.get("secondary_vibe")
    if sv is not None and (sv not in CV.VIBES or sv == d.get("vibe")):
        out.append(f"D156: secondary_vibe {sv!r} is not a second VIBES id")
    tone = d.get("tone")
    if tone is not None:
        if not isinstance(tone, dict):
            out.append("D156: tone is not an object")
        else:
            if "voice" in tone and tone.get("voice") not in CV.TONES:
                out.append(f"D156: tone.voice {tone.get('voice')!r} is not a "
                           f"creative_vocab.TONES id")
            al = tone.get("allowed")
            if al is not None and not (isinstance(al, list)
                                       and all(x in CV.TONES for x in al)):
                out.append(f"D156: tone.allowed {al!r} holds non-TONES ids")
            if "humor" in tone and tone.get("humor") not in HUMORS:
                out.append(f"D156: tone.humor {tone.get('humor')!r} (none|light|high)")
    if "energy" in d and not (_num(d.get("energy")) and 1 <= d["energy"] <= 5):
        out.append(f"D156: energy {d.get('energy')!r} is not 1–5")
    pac = d.get("pacing")
    if pac is not None:
        if not isinstance(pac, dict):
            out.append("D156: pacing is not an object")
            pac = {}
        if "target_wpm" in pac:
            w = _pair(pac.get("target_wpm"), *WPM_RANGE)
            if w is None:
                out.append(f"D156: pacing.target_wpm {pac.get('target_wpm')!r} "
                           f"— need [lo, hi] within {WPM_RANGE[0]}–{WPM_RANGE[1]} wpm")
            else:
                sized = [(_sized_wpm(it), _type(it)) for it in items(script)
                         if _txt(it.get("dialogue")).strip()]
                if sized:
                    need, typ = max(sized)
                    if w[1] < need:
                        out.append(f"D156: pacing.target_wpm tops out at "
                                   f"{w[1]:g} wpm but {typ} was sized for "
                                   f"{need:g} wpm — pacing never asks for speech "
                                   f"slower than the beat was sized for")
        if "max_static_s" in pac:
            ms = pac.get("max_static_s")
            if not (_num(ms) and 0 < ms <= MAX_STATIC_S):
                out.append(f"D156: pacing.max_static_s {ms!r} — must be "
                           f"<= {MAX_STATIC_S} (D48)")
        for k in ("avg_shot_s", "cuts_per_10s"):
            if k in pac and (_pair(pac.get(k)) is None or _pair(pac.get(k))[0] <= 0):
                out.append(f"D156: pacing.{k} {pac.get(k)!r} is not a positive "
                           f"[lo, hi] pair")
        if "pattern_interrupt_s" in pac and not (
                _num(pac.get("pattern_interrupt_s")) and pac["pattern_interrupt_s"] > 0):
            out.append(f"D156: pacing.pattern_interrupt_s "
                       f"{pac.get('pattern_interrupt_s')!r} is not a positive number")
    curve = d.get("energy_curve")
    if curve is not None:
        its = items(script)
        if not isinstance(curve, list) or len(curve) != len(its):
            out.append(f"D156: energy_curve has "
                       f"{len(curve) if isinstance(curve, list) else 'no'} "
                       f"entries for {len(its)} hook_stack + beats items — one "
                       f"per item, script order")
        else:
            for i, (e, it) in enumerate(zip(curve, its)):
                if not isinstance(e, dict):
                    out.append(f"D156: energy_curve[{i}] is not an object")
                    continue
                if _txt(e.get("type")).strip().upper() != _type(it):
                    out.append(f"D156: energy_curve[{i}] type "
                               f"{_q(e.get('type'), 30)} != item {_q(_type(it), 30)}"
                               f" (script order)")
                if not (_num(e.get("energy")) and 1 <= e["energy"] <= 5):
                    out.append(f"D156: energy_curve[{i}] energy "
                               f"{e.get('energy')!r} is not 1–5")
                (es, ee), (s, x) = G.parse_t(_txt(e.get("t"))), window(it)
                if None not in (es, s) and (abs(es - s) > 0.05 or abs(ee - x) > 0.05):
                    out.append(f"D156: energy_curve[{i}] t {_q(e.get('t'), 20)} "
                               f"!= item t {_q(it.get('t'), 20)}")
    mus = d.get("music")
    if mus is not None:
        if not isinstance(mus, dict):
            out.append("D156: music is not an object")
        else:
            if mus.get("in_master") is not False:
                out.append(f"D156: music.in_master is {mus.get('in_master')!r} — "
                           f"music is added at upload from the platform's "
                           f"commercial library, never baked into the master")
            lic = mus.get("licensing")
            miss = [p for p in CV.PLATFORMS
                    if not (isinstance(lic, dict) and isinstance(lic.get(p), dict)
                            and _txt(lic[p].get("library")).strip())]
            if miss:
                out.append(f"D156: music.licensing lacks a library for {miss} — "
                           f"one commercial lane per platform")
            tt = lic.get("tiktok") if isinstance(lic, dict) else None
            if isinstance(tt, dict):
                m = _affirmed(AI_MUSIC, _txt(tt.get("library")) + "\n"
                              + _txt(tt.get("note")))
                if m:
                    out.append(f"D156: music.licensing.tiktok names AI music "
                               f"({_q(m.group(0), 20)}) — no AI music on TikTok "
                               f"commercial content")
            if "bpm" in mus and _pair(mus.get("bpm"), 30, 250) is None:
                out.append(f"D156: music.bpm {mus.get('bpm')!r} is not a "
                           f"[lo, hi] pair in 30–250")
            if "vo_ducking_db" in mus and not (_num(mus.get("vo_ducking_db"))
                                               and mus["vo_ducking_db"] <= 0):
                out.append(f"D156: music.vo_ducking_db {mus.get('vo_ducking_db')!r}"
                           f" must be <= 0 dB")
    look = d.get("look")
    if isinstance(look, dict) and look.get("palette_hex") is not None:
        ph = look.get("palette_hex")
        bad = [x for x in ph if not HEX.match(_txt(x))] if isinstance(ph, list) else [ph]
        if bad:
            out.append(f"D156: look.palette_hex {bad[:3]} are not #RRGGBB")
    cam = d.get("camera")
    if isinstance(cam, dict) and cam.get("movement") is not None:
        mv = cam.get("movement")
        bad = [x for x in mv if x not in CV.CAMERA_MOVES] if isinstance(mv, list) else [mv]
        if bad:
            out.append(f"D156: camera.movement {bad[:3]} are not CAMERA_MOVES ids")
    ts = d.get("text_style")
    if isinstance(ts, dict) and "max_words_per_card" in ts and not (
            _num(ts.get("max_words_per_card")) and 1 <= ts["max_words_per_card"] <= 3):
        out.append(f"D156: text_style.max_words_per_card "
                   f"{ts.get('max_words_per_card')!r} — cards carry <= 3 words (D17)")
    ev = d.get("evidence")
    if isinstance(ev, list):
        bad = [e.get("grade") for e in ev if isinstance(e, dict)
               and e.get("grade") not in GRADES]
        if bad:
            out.append(f"D156: evidence grades {bad[:3]} (P|S|M|A)")
    voice = d.get("voice")
    if voice is not None:
        if not isinstance(voice, dict):
            out.append("D156: voice is not an object")
        else:
            vp = voice.get("presenter")
            if vp is not None and vp != ctx["presenter"]:
                out.append(f"D156: voice.presenter {vp!r} != the script's "
                           f"presenter {ctx['presenter']!r}")
            spec = _txt(voice.get("spec"))
            if ctx["presenter"] == "ai":
                probs = []
                if not SYNTH_VOICE.search(spec):
                    probs.append("names no synthetic voice")
                if not DISCLOSED.search(spec):
                    probs.append("never says it is disclosed")
                m = _affirmed(HUMAN_CLAIM, spec)
                if m:
                    probs.append(f"claims a human voice ({_q(m.group(0), 20)})")
                if probs:
                    out.append(f"D156: presenter=ai but voice.spec "
                               f"{', '.join(probs)} — an AI voice is a disclosed "
                               f"synthetic voice that never claims to be human")
    return _cap(out, "D156")


def check_d158(script, bundle_text, ctx):
    """D158: no fake urgency, scarcity or offers in viewer text (+ caption)
    unless the prompt supplies it (lexicon.offer_in allow-path)."""
    hits = []
    for pid, cls, m in L.offer_urgency_hits(ctx["viewer_text"], ctx["prompt"]):
        h = f"{cls} {_q(m, 30)}"
        if h not in hits:
            hits.append(h)
    if hits:
        return [f"D158: fake urgency/scarcity/offer in viewer text "
                f"({', '.join(hits[:3])}) — the prompt supplies no such offer "
                f"(FTC dark patterns: false limited-time, low-stock and discount "
                f"claims)"]
    return []


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

V21_SCRIPT_RULES = (
    # ---- gate 1, pipeline v2.1 creative layer (RULES.md §68) — silent when
    # the key / phrase is absent (docs/CREATIVE-PLAN.md §0.2)
    Rule("D154", "hook_variants integrity (3-5, A = the script hook, distinct "
         "visual types / first 3 words, every variant passes the hook screens)",
         _S, _E, "RULES.md §68 D154; docs/CREATIVE-PLAN.md §1.2; Meta "
         "same-opening = same creative; TikTok 3-5 creatives", check_d154),
    Rule("D155", "discovery packaging integrity (hashtag caps, YouTube limits, "
         "caption screens, one CTA destination, AI disclosure, keyword in line 1)",
         _S, _E, "RULES.md §68 D155; docs/CREATIVE-PLAN.md §1.3; "
         "discovery-seo PLATFORM_PACKAGING / DISC-03,04,06,08,09", check_d155),
    Rule("D156", "direction integrity (ids, 140-200 wpm never slower than the "
         "beat sizing, max_static_s <= 3.5, music not in master + 3 licensing "
         "lanes, AI voice disclosed, one energy_curve entry per item)", _S, _E,
         "RULES.md §68 D156; docs/CREATIVE-PLAN.md §1.1; vibe-tone-music §3, §4",
         check_d156),
    Rule("D158", "no fake urgency, scarcity or offers unless the prompt "
         "supplies them", _S, _E, "RULES.md §68 D158; FTC dark-patterns report "
         "(2022); hooks-deep-dive RISKY_PHRASES UR-01..04", check_d158),
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

REGISTRY = (LEGACY_SCRIPT_RULES + V2_SCRIPT_RULES + V21_SCRIPT_RULES
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
