"""Deterministic quality rubric for a finished script (0-100).

Independent of the gates: the gates are pass/fail contracts; the rubric grades
how good a script is, using the RULES.md doctrine plus the 2025-2026 research
in /research (hook length and specificity, payoff placement, muted-viewer
readability, claims and AI-testimonial compliance, hashtag hygiene...).

Design (Rubrics-as-Rewards style):
  * every check is binary and atomic, with a tier and weight
      E = essential (3), I = important (2), O = optional (1)
  * pitfalls subtract points (slop phrases, meta leaks, repeated sentences)
  * AUDIT checks are held out of the selection score used by best-of-N, so the
    eval harness can detect a selector that games the rubric (winners should
    not score worse on audit checks than random passing candidates).

score(script) -> {"score", "selection_score", "audit_score", "checks",
                  "pitfalls", "flags"}
"""
import re

from vsp.lexicon import (ABSOLUTE, AI_FIRST_PERSON, FALLBACK_HOOK,  # noqa: F401
                         GENERIC_BAIT, GENERIC_TAGS, LABEL_WORDS, LINK_GROUPS,
                         MAX_HASHTAGS, META_LEAK, PRICE, SLOP, SOCIAL_PROOF,
                         VAGUE_HOOK, WORD_RE, overlay_is_clean)

T_RE = re.compile(r"(\d+(?:\.\d+)?)")

STOP = set("""a an the for with my of and in on to that just make sense things
thing days day every why your you how i stopped quit deleted ditched dropped
gave up tried did unfollowed this these it its is are be was were buying
make me script about video reel under best new mini portable set""".split())


def _items(s):
    return list(s.get("hook_stack") or []) + list(s.get("beats") or [])


def _win(item):
    m = T_RE.findall(item.get("t") or "")
    return (float(m[0]), float(m[1])) if len(m) >= 2 else (None, None)


def _words(text):
    return WORD_RE.findall(text or "")


def _norm(text):
    return " ".join(w.lower().strip(".'’") for w in _words(text))


def _stem(w):
    w = w.lower().strip(".'’")
    for suf in ("es", "s"):
        if len(w) > 4 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _wps(delivery):
    d = (delivery or "").lower()
    return 2.5 if any(k in d for k in ("slow down", "unhurried",
                                        "never rushed")) else 3.0


def hook_line(s):
    for h in s.get("hook_stack") or []:
        if h.get("dialogue"):
            return h["dialogue"]
    for b in s.get("beats") or []:
        if "HOOK" in (b.get("type") or "") and b.get("dialogue"):
            return b["dialogue"]
    return ""


def frame0_overlay(s):
    hs = s.get("hook_stack") or []
    if hs and hs[0].get("on_screen"):
        return hs[0]["on_screen"]
    for b in s.get("beats") or []:
        if b.get("type") == "VISUAL TRIGGER":
            return b.get("on_screen") or ""
    return ""


def prompt_anchors(prompt):
    toks = [_stem(w) for w in _words(prompt)]
    return {t for t in toks if len(t) >= 3 and t not in STOP
            and not t.replace(".", "").isdigit()}


def viewer_text(s, include_caption=True):
    parts = []
    for it in _items(s):
        for k in ("dialogue", "rehook", "on_screen"):
            if it.get(k):
                parts.append(str(it[k]))
    if include_caption and s.get("caption"):
        parts.append(s["caption"])
    return "\n".join(parts)


def spoken_text(s):
    return "\n".join(str(it.get(k)) for it in _items(s)
                     for k in ("dialogue", "rehook") if it.get(k))


# --------------------------------------------------------------- checks
def _c_hook_len(s, ctx):
    h = hook_line(s)
    n = len(_words(h))
    return (0 < n <= 8), f"{n} words: {h!r}"


def _c_hook_specific(s, ctx):
    h = hook_line(s).strip()
    if not h:
        return False, "no verbal hook"
    if FALLBACK_HOOK.match(h):
        return False, f"generic fallback hook: {h!r}"
    if VAGUE_HOOK.search(h):
        return False, f"vague hook: {h!r}"
    toks = {_stem(w) for w in _words(h)}
    anchored = bool(toks & ctx["anchors"]) or bool(re.search(r"\d", h)) \
        or bool(re.search(r"\b(?:I|my|I'm|I've)\b", h))
    return anchored, "anchored" if anchored else f"no concrete anchor: {h!r}"


def _c_timeline(s, ctx):
    dur = float(s.get("duration_s") or 30)
    wins = []
    for b in s.get("beats") or []:
        a, e = _win(b)
        if a is None:
            return False, f"beat without window: {b.get('type')}"
        wins.append((a, e, b))
    if not wins:
        return False, "no beats"
    probs = []
    for i in range(len(wins)):
        for j in range(i + 1, len(wins)):
            ov = min(wins[i][1], wins[j][1]) - max(wins[i][0], wins[j][0])
            if ov > 0.1:
                probs.append("overlap")
    ordered = sorted(wins, key=lambda w: (w[0], w[1]))
    for (a1, e1, _), (a2, e2, _) in zip(ordered, ordered[1:]):
        if a2 - e1 > 0.5:
            probs.append("gap")
    if max(e for _, e, _ in wins) > dur + 0.05:
        probs.append("overrun")
    for a, e, b in wins:
        dlg = b.get("dialogue") or ""
        if dlg and len(dlg.split()) / _wps(b.get("delivery")) > (e - a) * 1.15:
            probs.append(f"speech>window:{b.get('type')}")
    return (not probs), ", ".join(sorted(set(probs))) or "clean"


def _c_payoff_place(s, ctx):
    dur = float(s.get("duration_s") or 30)
    for b in s.get("beats") or []:
        if b.get("type") == "PAYOFF":
            a, _ = _win(b)
            if a is None:
                return False, "PAYOFF without window"
            frac = a / dur
            return 0.68 <= frac <= 0.88, f"payoff starts at {frac:.0%}"
    return False, "no PAYOFF beat"


def _c_claims(s, ctx):
    prompt = s.get("prompt") or ""
    txt = viewer_text(s)
    bad = []
    supplied = {re.sub(r"[^\d.]", "", p).rstrip(".").rstrip("0").rstrip(".")
                for p in PRICE.findall(prompt)}
    for p in PRICE.findall(txt):
        key = re.sub(r"[^\d.]", "", p).rstrip(".").rstrip("0").rstrip(".")
        if key not in supplied:
            bad.append(f"price {p!r}")
    for rx in SOCIAL_PROOF:
        m = rx.search(txt)
        if m and not rx.search(prompt):
            bad.append(f"social proof {m.group(0)!r}")
    return (not bad), "; ".join(bad) or "no invented claims"


def _c_ai_first_person(s, ctx):
    if s.get("presenter") != "ai":
        return None, "n/a (human presenter)"
    txt = viewer_text(s)
    for rx in AI_FIRST_PERSON:
        m = rx.search(txt)
        if m:
            return False, f"AI persona claims lived experience: {m.group(0)!r}"
    return True, "curator-framed"


def _c_leaks(s, ctx):
    txt = viewer_text(s)
    probs = []
    if "{" in txt or "}" in txt:
        probs.append("raw template slot")
    if re.search(r"\b(?:None|null|undefined)\b", txt):
        probs.append("null leak")
    m = re.search(r"\b([A-Za-z]+) \1\b", txt, re.I)
    if m and m.group(1).lower() not in ("that", "had", "very", "no"):
        probs.append(f"doubled word {m.group(0)!r}")
    m = re.search(r"[.!?] +[a-z]", txt)
    if m:
        probs.append(f"lowercase after sentence end {m.group(0)!r}")
    return (not probs), "; ".join(probs) or "clean"


def _c_frame0(s, ctx):
    ov = frame0_overlay(s).strip()
    if not ov:
        return False, "no frame-0 overlay"
    ok, why = overlay_is_clean(ov, hook_line(s))
    return ok, f"{why}: {ov!r}"


def _c_onscreen(s, ctx):
    probs = []
    hook_end = max([_win(h)[1] or 0.0 for h in s.get("hook_stack") or []]
                   + [3.0])
    for it in _items(s):
        os_txt = (it.get("on_screen") or "").strip()
        if not os_txt:
            continue
        n = len(os_txt.split())
        a, e = _win(it)
        if it.get("type") == "VISUAL TRIGGER" and a is not None:
            e = max(e, hook_end)  # the frame-0 card holds through the hook
        if n > 12:
            probs.append(f"{n} words on {it.get('type')}")
        elif len(os_txt) > 70:
            probs.append(f"{len(os_txt)} chars on {it.get('type')}")
        elif a is not None and e > a and len(os_txt) / (e - a) > 20:
            probs.append(f"{len(os_txt) / (e - a):.0f} cps on {it.get('type')}")
    return (not probs), "; ".join(probs) or "readable"


def _c_rehooks(s, ctx):
    rh = [_norm(b.get("rehook")) for b in s.get("beats") or [] if b.get("rehook")]
    if float(s.get("duration_s") or 30) > 15 and not rh:
        return False, "no re-hooks"
    dup = len(rh) - len(set(rh))
    return dup == 0, f"{len(rh)} re-hooks, {dup} repeated"


def _c_single_cta(s, ctx):
    low = (spoken_text(s) + "\n" + (s.get("caption") or "")).lower()
    hit = [g[0] for g in LINK_GROUPS if any(p in low for p in g)]
    return len(hit) <= 1, f"destinations: {hit or 'none'}"


def _c_speech_rate(s, ctx):
    words, secs = 0, 0.0
    for it in _items(s):
        a, e = _win(it)
        n = len(_words(it.get("dialogue"))) + len(_words(it.get("rehook")))
        if n and a is not None and e > a:
            words += n
            secs += e - a
    if not secs:
        return False, "no timed speech"
    wps = words / secs
    return 2.0 <= wps <= 3.3, f"{wps * 60:.0f} wpm"


def _c_hashtags(s, ctx):
    tags = [t.lower() for t in re.findall(r"#(\w+)", s.get("caption") or "")]
    if not 1 <= len(tags) <= MAX_HASHTAGS:
        return False, f"{len(tags)} hashtags"
    if all(t in GENERIC_TAGS for t in tags):
        return False, f"generic-only tags {tags}"
    return True, f"{len(tags)} tags"


def _c_keyword_echo(s, ctx):
    kws = re.findall(r"\bcomment\s+([A-Z][A-Z0-9]{1,})\b", spoken_text(s))
    if not kws:
        return None, "n/a (no comment keyword)"
    cap = s.get("caption") or ""
    return kws[0] in cap, f"keyword {kws[0]}"


def _c_product_early(s, ctx):
    toks = {_stem(w) for w in _words(hook_line(s) + " " + frame0_overlay(s))}
    ok = bool(toks & ctx["anchors"])
    return ok, "named in hook/overlay" if ok else "prompt noun absent from hook"


def _c_comment_bait(s, ctx):
    for b in s.get("beats") or []:
        if b.get("type") == "COMMENT BAIT":
            d = b.get("dialogue") or ""
            ok = bool(re.search(r"\bcomment\s+[A-Z]{2,}", d)) or "?" in d
            return ok, d[:60]
    return False, "no COMMENT BAIT beat"


def _c_generic_bait(s, ctx):
    m = GENERIC_BAIT.search(viewer_text(s))
    return (m is None), (f"engagement bait {m.group(0)!r}" if m else "none")


def _c_absolute(s, ctx):
    m = ABSOLUTE.search(viewer_text(s))
    return (m is None), (f"absolute claim {m.group(0)!r}" if m else "none")


def _c_ai_disclosure(s, ctx):
    if s.get("presenter") != "ai":
        return None, "n/a (human presenter)"
    disc = str(s.get("disclosure") or "")
    cap = s.get("caption") or ""
    ok = bool(re.search(r"\bAI\b", disc)) and bool(re.search(r"\bAI\b", cap))
    return ok, "label + caption line" if ok else "AI disclosure missing"


def _c_part2(s, ctx):
    for b in s.get("beats") or []:
        if b.get("type") == "CTA" and re.search(r"\bpart (?:2|two)\b",
                                                b.get("dialogue") or "", re.I):
            if not s.get("series_plan"):
                return False, "promises an unplanned part 2"
    return True, "no dangling series promise"


# (id, title, tier, weight, audit_only, fn)
CHECKS = [
    ("R01", "verbal hook <= 8 words", "E", 3, False, _c_hook_len),
    ("R02", "hook is specific (no fallback/vague)", "E", 3, False, _c_hook_specific),
    ("R03", "timeline performable (no gap/overlap/overrun/overflow)", "E", 3, False, _c_timeline),
    ("R04", "payoff lands 68-88% through", "I", 2, False, _c_payoff_place),
    ("R05", "no invented prices / social proof", "E", 3, False, _c_claims),
    ("R06", "AI persona makes no lived-experience claims", "E", 3, False, _c_ai_first_person),
    ("R07", "no template leaks / broken casing", "E", 3, False, _c_leaks),
    ("R08", "frame-0 overlay is a clean <=3-word phrase", "I", 2, False, _c_frame0),
    ("R09", "on-screen text readable (<=12 words, <=20 cps)", "I", 2, False, _c_onscreen),
    ("R10", "re-hooks present and never repeated", "I", 2, False, _c_rehooks),
    ("R11", "one link destination", "I", 2, False, _c_single_cta),
    ("R12", "speech rate 120-198 wpm", "O", 1, True, _c_speech_rate),
    ("R13", "1-5 hashtags, not generic-only", "I", 2, False, _c_hashtags),
    ("R14", "caption echoes the comment keyword", "O", 1, False, _c_keyword_echo),
    ("R15", "product/concept named in hook or overlay", "I", 2, True, _c_product_early),
    ("R16", "AI disclosure (label + caption line)", "E", 3, False, _c_ai_disclosure),
    ("R17", "comment bait is specific", "O", 1, True, _c_comment_bait),
    ("R18", "no generic engagement bait", "I", 2, False, _c_generic_bait),
    ("R19", "no absolute / guarantee claims", "I", 2, False, _c_absolute),
    ("R20", "no unplanned part-2 promise", "O", 1, False, _c_part2),
]

PITFALLS = [
    ("P1", "meta/rule leak in viewer text", lambda s: META_LEAK.search(viewer_text(s))),
    ("P2", "slop phrase", lambda s: SLOP.search(viewer_text(s))),
    ("P3", "same sentence twice", lambda s: _dup_sentence(s)),
]
PITFALL_COST = 4
AUDIT_PITFALLS = {"P2"}


def _dup_sentence(s):
    seen = set()
    for it in _items(s):
        for sent in re.split(r"(?<=[.!?])\s+", it.get("dialogue") or ""):
            n = _norm(sent)
            if len(n.split()) >= 3:
                if n in seen:
                    return n
                seen.add(n)
    return None


def score(script):
    ctx = {"anchors": prompt_anchors(script.get("prompt") or "")}
    checks = []
    for cid, title, tier, w, audit, fn in CHECKS:
        try:
            ok, detail = fn(script, ctx)
        except Exception as e:  # a rubric bug must never kill a run
            ok, detail = False, f"check error: {e!r}"
        checks.append({"id": cid, "title": title, "tier": tier, "weight": w,
                       "audit": audit, "pass": ok, "detail": detail})
    pits = []
    for pid, title, fn in PITFALLS:
        m = fn(script)
        if m:
            hit = m.group(0) if hasattr(m, "group") else str(m)
            pits.append({"id": pid, "title": title, "hit": hit,
                         "audit": pid in AUDIT_PITFALLS})

    def _agg(sel):
        num = sum(c["weight"] for c in checks if sel(c) and c["pass"])
        den = sum(c["weight"] for c in checks if sel(c) and c["pass"] is not None)
        return 100.0 * num / den if den else 0.0

    sel_pen = PITFALL_COST * sum(1 for p in pits if not p["audit"])
    all_pen = PITFALL_COST * len(pits)
    selection = max(0.0, _agg(lambda c: not c["audit"]) - sel_pen)
    audit = _agg(lambda c: c["audit"])
    overall = max(0.0, _agg(lambda c: True) - all_pen)
    flags = sorted({c["id"] for c in checks if c["pass"] is False
                    and c["id"] in ("R05", "R06", "R16", "R18", "R19")})
    return {"score": round(overall, 1), "selection_score": round(selection, 1),
            "audit_score": round(audit, 1), "checks": checks,
            "pitfalls": pits, "compliance_flags": flags}


def summary_line(result):
    failed = [c["id"] for c in result["checks"] if c["pass"] is False]
    pits = [p["id"] for p in result["pitfalls"]]
    return (f"rubric {result['score']:.0f}/100 (selection "
            f"{result['selection_score']:.0f}, audit {result['audit_score']:.0f})"
            + (f" — failed {', '.join(failed)}" if failed else "")
            + (f" — pitfalls {', '.join(pits)}" if pits else ""))


if __name__ == "__main__":
    import json
    import sys
    res = score(json.load(open(sys.argv[1])))
    print(summary_line(res))
    for c in res["checks"]:
        mark = {True: "PASS", False: "FAIL", None: "n/a "}[c["pass"]]
        print(f"  {mark} {c['id']} {c['title']}: {c['detail']}")
    for p in res["pitfalls"]:
        print(f"  PIT  {p['id']} {p['title']}: {p['hit']!r}")
