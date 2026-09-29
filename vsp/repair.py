"""Stage 6 — rule-keyed deterministic repair loop (D150).

    repair(script, gate_fn, max_rounds=3) -> (script, log, passed)

Only deterministic, rule-keyed edits (no free-form rewriting, no gate edits —
labs-techniques §1.2/§5.2: auto-fix idempotent issues, log every fix, fail
loudly otherwise). Each round applies every repair keyed by the rules that
are currently failing, re-gates, and keeps the best version seen (fewest gate
failures; ties keep the earlier version):

  D43/D55/D74/D78/D94 (+ "missing time window")  vsp.timing.relayout_script —
      windows re-sized from their own words and tiled 3.0 s → duration, the
      payoff contract re-timed (D143). When the words cannot fit, the longest
      line of the most over-budget beat is trimmed at a sentence/clause
      boundary with vsp.timing.fit_words (never mid-clause) and the layout is
      re-run; a rehook that has no clause boundary is dropped as a last resort.
  D103   on_screen > 12 tokens compressed at a "·" / "—" / "," boundary.
  D142   (if the gate emits it) on_screen over 20 cps compressed the same way.
  D44    parenthetical path only: "(...)" / "[...]" stripped from spoken lines.
         The stage-verb path is NOT repaired (a spoken camera command needs a
         human rewrite, not a deletion).
  D93    a duplicate rehook is blanked (the later copy).
  D111   "Test 1" → "Test" in single-test scripts.

Anything else (D37 prices, D136+ claims, hashtags, ...) is not repairable
here and keeps failing loudly. Every action is logged as
{round, rule, target, action}.
"""
import copy
import json
import math
import re

from vsp import timing

RULE_RE = re.compile(r"^\s*(D\d+[a-z]?|B4a)\b")
TIMING_RULES = ("D43", "D55", "D74", "D78", "D94")
PAREN_RE = re.compile(r"\s*(?:\([^()]{1,80}\)|\[[^\[\]]{1,80}\])")
TEST1_RE = re.compile(r"\b(test)\s+1\b", re.I)
ON_SCREEN_MAX = 12          # D103 cap (gate: > 12 whitespace tokens fails)
CPS_MAX = 20.0              # D142 / rubric R09 reading-speed ceiling
OS_SEPS = (" \u00b7 ", " \u2014 ", ", ")     # "·", "—", "," boundaries
_WEAK_TAIL = {"a", "an", "the", "and", "or", "but", "of", "to", "for", "with",
              "in", "on", "at", "by", "from", "vs", "vs."}


# ------------------------------------------------------------ gate output
def rule_of(msg):
    """Rule id of one gate message (string or {rule, message} finding)."""
    if isinstance(msg, dict):
        r = msg.get("rule")
        return r if r else rule_of(msg.get("message") or "")
    m = RULE_RE.match(msg or "")
    if m:
        return m.group(1)
    if "missing time window" in (msg or ""):
        return "D43"
    return None


def _text(msg):
    return msg.get("message", "") if isinstance(msg, dict) else str(msg)


def _errors(result):
    """Normalise gate output: drop warning/info findings, keep errors."""
    out = []
    for m in result or []:
        if isinstance(m, dict) and str(m.get("severity", "error")).lower() in (
                "warning", "warn", "info", "note"):
            continue
        out.append(m)
    return out


def _gate(gate_fn, script):
    return _errors(gate_fn(script))


# ---------------------------------------------------------------- helpers
def _items(s):
    return list(s.get("beats") or []) + list(s.get("hook_stack") or [])


def _norm(text):
    return " ".join(re.sub(r"[^a-z0-9']+", " ", (text or "").lower()).split())


def _clean_spaces(text):
    t = re.sub(r"\s+", " ", text or "").strip()
    t = re.sub(r"\s+([.,!?;:])", r"\1", t)
    t = re.sub(r"([.,!?;:]){2,}", lambda m: m.group(0)[-1], t)
    return t.strip()


def _label(beats, i, field):
    return f"beats[{i}].{field} ({beats[i].get('type', '?')})"


def _trigrams(text):
    w = _norm(text).split()
    if len(w) < 3:
        return {tuple(w)} if w else set()
    return {tuple(w[i:i + 3]) for i in range(len(w) - 2)}


def _jaccard(a, b):
    A, B = _trigrams(a), _trigrams(b)
    return len(A & B) / len(A | B) if (A or B) else 0.0


# ------------------------------------------------------------ text repairs
def strip_parentheticals(script):
    """D44 (parenthetical path): drop '(...)' / '[...]' from spoken lines."""
    s = copy.deepcopy(script)
    acts = []
    for key in ("hook_stack", "beats"):
        for i, b in enumerate(s.get(key) or []):
            for f in ("dialogue", "rehook"):
                t = b.get(f)
                if t and PAREN_RE.search(t):
                    new = _clean_spaces(PAREN_RE.sub("", t))
                    acts.append({"rule": "D44", "target": f"{key}[{i}].{f} "
                                 f"({b.get('type', '?')})",
                                 "action": f"stripped staging note(s) "
                                 f"{PAREN_RE.findall(t)!r}"})
                    b[f] = new
    return s, acts


def blank_duplicate_rehooks(script):
    """D93: a repeated re-hook spends two open loops on one promise — blank
    the later copy (exact match first, then same promise after ':'/'—',
    then word-trigram Jaccard >= 0.5)."""
    s = copy.deepcopy(script)
    beats = s.get("beats") or []
    acts = []

    def promise(t):
        parts = re.split(r":|\u2014| - ", t or "", maxsplit=1)
        return _norm(parts[1] if len(parts) > 1 else parts[0])

    for how, key in (("exact", _norm), ("same promise", promise)):
        seen = {}
        for i, b in enumerate(beats):
            rh = b.get("rehook")
            if not rh:
                continue
            k = key(rh)
            if k and k in seen:
                b["rehook"] = ""
                acts.append({"rule": "D93", "target": _label(beats, i, "rehook"),
                             "action": f"blanked duplicate re-hook ({how} of "
                             f"beats[{seen[k]}])"})
            elif k:
                seen[k] = i
        if acts:
            return s, acts
    idx = [i for i, b in enumerate(beats) if b.get("rehook")]
    best = None
    for x in range(len(idx)):
        for y in range(x + 1, len(idx)):
            j = _jaccard(beats[idx[x]]["rehook"], beats[idx[y]]["rehook"])
            if j >= 0.5 and (best is None or j > best[0]):
                best = (j, idx[x], idx[y])
    if best:
        j, a, b = best
        beats[b]["rehook"] = ""
        acts.append({"rule": "D93", "target": _label(beats, b, "rehook"),
                     "action": f"blanked near-duplicate re-hook (trigram "
                     f"Jaccard {j:.2f} vs beats[{a}])"})
    return s, acts


_D36_SUBJECTS = [   # RULES.md D36: name the actual transformation subject
    (r"\b(?:hair|wax|pomade|shampoo|conditioner|straightener|curler|dryer)\b", "hair"),
    (r"\b(?:skin|serum|cream|moisturizer|cleanser|toner|acne|spf|sunscreen)\b", "skin"),
    (r"\b(?:lash|lashes|eyelash|eyelashes|mascara)\b", "lashes"),
    (r"\b(?:teeth|whitening|toothbrush|smile)\b", "smile"),
    (r"\b(?:room|apartment|bedroom|closet|home|kitchen|house|desk|office|shelf|drawer)\b", "room"),
    (r"\b(?:car|truck|trunk|dashboard)\b", "car"),
    (r"\b(?:dog|puppy)\b", "dog"),
    (r"\b(?:cat|kitten)\b", "cat"),
]
SAME_BODY_RE = re.compile(r"\b(same)\s+body\b", re.I)


def d36_subject(script):
    low = (script.get("prompt") or "").lower()
    for pat, noun in _D36_SUBJECTS:
        if re.search(pat, low):
            return noun
    return "angle"          # "Same angle, same light" is true of any split


def name_transformation_subject(script):
    """D36 (gate 2): 'same body' on a non-body transformation — the evidence
    line names the real subject ("same hair, same light"), or the neutral
    "same angle" when the prompt names none. Body prompts are untouched."""
    s = copy.deepcopy(script)
    acts = []
    if "body" in (s.get("prompt") or "").lower():
        return s, acts
    noun = d36_subject(s)
    for key in ("hook_stack", "beats"):
        for i, b in enumerate(s.get(key) or []):
            for f in ("dialogue", "rehook", "on_screen"):
                t = b.get(f)
                if t and SAME_BODY_RE.search(t):
                    b[f] = SAME_BODY_RE.sub(lambda m: f"{m.group(1)} {noun}", t)
                    acts.append({"rule": "D36", "target": f"{key}[{i}].{f} "
                                 f"({b.get('type', '?')})",
                                 "action": f"'same body' -> 'same {noun}'"})
    return s, acts


def fix_single_test_numbering(script):
    """D111: 'Test 1' with no 'Test 2' → drop the dangling ordinal."""
    s = copy.deepcopy(script)
    acts = []
    beats = s.get("beats") or []
    txt = " ".join((b.get("dialogue") or "") + " " + (b.get("on_screen") or "")
                   for b in beats)
    if not TEST1_RE.search(txt) or re.search(r"\btest\s+2\b", txt, re.I):
        return s, acts
    for i, b in enumerate(beats):
        for f in ("dialogue", "on_screen"):
            t = b.get(f)
            if t and TEST1_RE.search(t):
                b[f] = _clean_spaces(TEST1_RE.sub(lambda m: m.group(1), t))
                acts.append({"rule": "D111", "target": _label(beats, i, f),
                             "action": "'Test 1' -> 'Test' (single-test script)"})
    return s, acts


def compress_on_screen(text, max_tokens=ON_SCREEN_MAX, max_chars=None):
    """Longest prefix of `text` that ends at a '·' / '—' / ',' boundary and
    has <= max_tokens whitespace tokens (and <= max_chars characters when
    given). Falls back to a word cut that never ends on an article or
    preposition. Returns the text unchanged if it already fits."""
    t = (text or "").strip()

    def ok(x):
        return len(x.split()) <= max_tokens and (max_chars is None
                                                  or len(x) <= max_chars)
    if ok(t):
        return t
    cuts = sorted({m.start() for sep in OS_SEPS
                   for m in re.finditer(re.escape(sep), t)}, reverse=True)
    for c in cuts:
        head = t[:c].rstrip(" ,\u00b7\u2014;:")
        if head and ok(head):
            return head
    words = t.split()
    n = min(len(words), max_tokens)
    while n > 1:
        head = " ".join(words[:n]).rstrip(" ,\u00b7\u2014;:")
        if ok(head) and words[n - 1].lower().strip(",.;:") not in _WEAK_TAIL:
            return head
        n -= 1
    return words[0] if words else ""


def _window(item):
    s, e = timing.parse_window(item.get("t"))
    return (s, e) if s is not None and e > s else (None, None)


def compress_paragraph_cards(script, cps=False):
    """D103 (token cap) and, when cps=True, D142 (<= 20 cps over the window)."""
    s = copy.deepcopy(script)
    acts = []
    hook_end = max([_window(h)[1] or 0.0 for h in s.get("hook_stack") or []]
                   + [3.0])
    for key in ("beats", "hook_stack"):
        for i, b in enumerate(s.get(key) or []):
            os_txt = (b.get("on_screen") or "").strip()
            if not os_txt:
                continue
            max_chars = None
            if cps:
                a, e = _window(b)
                if a is None:
                    continue
                if b.get("type") == "VISUAL TRIGGER":
                    e = max(e, hook_end)
                max_chars = int(CPS_MAX * (e - a))
            new = compress_on_screen(os_txt, ON_SCREEN_MAX, max_chars)
            if new != os_txt:
                b["on_screen"] = new
                acts.append({"rule": "D142" if cps else "D103",
                             "target": f"{key}[{i}].on_screen ({b.get('type', '?')})",
                             "action": f"compressed {len(os_txt.split())} -> "
                             f"{len(new.split())} tokens: {new!r}"})
    return s, acts


# ---------------------------------------------------------- timing repairs
def _water_cap(mins, body):
    """Cap c with sum(min(m, c)) == body (water-filling); beats above c are
    the over-budget ones, their excess is m - c."""
    ms = sorted(mins)
    rest, n = body, len(ms)
    for i, m in enumerate(ms):
        c = rest / (n - i)
        if m > c:
            return c
        rest -= m
    return float("inf")


MIN_TRIM_WORDS = 4   # a trim that leaves a 1-3 word stub ("Okay.") is worse
#                      than dropping the line's tail elsewhere


def _sentences(text):
    return [x for x in re.split(r"(?<=[.!?])\s+", (text or "").strip()) if x]


def _fit_at_least(text, target, n, sentence_only):
    """Least-aggressive boundary trim with <= target words if possible,
    else the closest boundary trim that still removes words (the loop
    re-lays and trims again). Never returns a stub under MIN_TRIM_WORDS."""
    for t in range(max(1, target), n):
        new = timing.fit_words(text, t)
        if new is None:
            continue
        k = timing.gate_words(new)
        if k >= n or k < MIN_TRIM_WORDS:
            continue
        is_sentence_cut = new in (" ".join(_sentences(text)[:j])
                                  for j in range(1, len(_sentences(text))))
        if sentence_only != is_sentence_cut:
            continue
        return new
    return None


def _trim_once(script, info):
    """Trim one over-budget line. Priority: (1) longest dialogue trimmed at a
    sentence boundary, (2) longest dialogue trimmed at a clause boundary,
    (3) longest re-hook dropped (re-hooks are one sentence whose value is the
    event after the colon — a clause stub like "Okay." is garbage).
    Over-budget = above the water-filling cap that would make the minima fit.
    Returns (script, action) or (script, None) when nothing can be trimmed."""
    s = copy.deepcopy(script)
    beats = s.get("beats") or []
    mins = info.get("mins") or [timing.min_window(b) for b in beats]
    start = 3.0
    for h in s.get("hook_stack") or []:
        _, e = timing.parse_window(h.get("t"))
        if e:
            start = max(start, e)
    body = float(s.get("duration_s") or 30) - start
    cap = _water_cap(mins, body)
    over = [(m - cap, i) for i, m in enumerate(mins) if m - cap > 1e-9]
    if not over:
        over = [(m, i) for i, m in enumerate(mins)]
    excess = {i: ex for ex, i in over}
    dlg = sorted(((-timing.gate_words(beats[i].get("dialogue")), i)
                  for _, i in over if timing.gate_words(beats[i].get("dialogue"))))
    for sentence_only in (True, False):
        for neg_n, i in dlg:
            b, n = beats[i], -neg_n
            cut = int(math.ceil(excess[i] * timing.wps(b.get("delivery"))))
            new = _fit_at_least(b["dialogue"], max(1, n - max(1, cut)), n,
                                sentence_only)
            if new is None:
                continue
            b["dialogue"] = new
            how = "sentence" if sentence_only else "clause"
            return s, {"rule": "D43+D74", "target": _label(beats, i, "dialogue"),
                       "action": f"trimmed {n} -> {timing.gate_words(new)} words "
                       f"at a {how} boundary (fit_words): {new!r}"}
    rh = sorted((-timing.gate_words(beats[i].get("rehook")), i) for _, i in over
                if timing.gate_words(beats[i].get("rehook")))
    if not rh:   # nothing left on the over-budget beats: any re-hook
        rh = sorted((-timing.gate_words(b.get("rehook")), i)
                    for i, b in enumerate(beats) if timing.gate_words(b.get("rehook")))
    if rh:
        i = rh[0][1]
        old = beats[i]["rehook"]
        beats[i]["rehook"] = ""
        return s, {"rule": "D43+D74", "target": _label(beats, i, "rehook"),
                   "action": f"dropped re-hook ({timing.gate_words(old)} words "
                   f"over budget): {old!r}"}
    return s, None


def _brings_back_d44(cand, cur):
    """Never restore words the D44 screen would flag (a trim that happened to
    remove a spoken stage direction must not be undone)."""
    try:
        from vsp.gates import STAGE_VERBS
    except Exception:
        STAGE_VERBS = []
    c, k = (cand or "").lower(), (cur or "").lower()
    if any(v in c and v not in k for v in STAGE_VERBS):
        return True
    return bool(PAREN_RE.search(cand or "")) and not PAREN_RE.search(cur or "")


def _restore(s, originals, acts):
    """Least-destructive pass: greedy trims overshoot (a whole sentence goes
    at a time), so once the layout is feasible, give words back — each
    trimmed line (latest first) regains the longest boundary-aligned prefix of
    its original that keeps the layout feasible."""
    for (i, f), orig in reversed(list(originals.items())):
        beats = s["beats"]
        cur = beats[i].get(f) or ""
        n_orig, n_cur = timing.gate_words(orig), timing.gate_words(cur)
        # a re-hook comes back whole or not at all (a clause stub is garbage)
        lo = n_orig - 1 if f == "rehook" else n_cur
        for t in range(n_orig, lo, -1):
            cand = timing.fit_words(orig, t) if t < n_orig else orig
            if not cand or timing.gate_words(cand) <= n_cur or \
                    (0 < timing.gate_words(cand) < MIN_TRIM_WORDS) or \
                    _brings_back_d44(cand, cur):
                continue
            trial = copy.deepcopy(s)
            trial["beats"][i][f] = cand
            laid, info = timing.relayout_script(trial)
            if info["feasible"]:
                acts.append({"rule": "D43+D74", "target": _label(beats, i, f),
                             "action": f"restored {n_cur} -> "
                             f"{timing.gate_words(cand)} words (still fits): {cand!r}"})
                s = laid
                break
    return s


def retime(script, rules=TIMING_RULES, max_trims=24):
    """relayout_script + trims until the layout is feasible (then the
    restore pass gives back whatever the greedy trims over-cut)."""
    tag = "+".join(r for r in TIMING_RULES if r in rules) or "D43"
    s, info = timing.relayout_script(script)
    acts = [{"rule": tag, "target": "beats[*].t + payoff_contract",
             "action": "relayout_script: windows sized to their words, tiled "
             f"to {s.get('duration_s')}s, payoff at "
             f"{info.get('payoff_start')}s (feasible={info['feasible']}, "
             f"overflow {info['overflow_s']}s)"}]
    originals = {}
    for _ in range(max_trims):
        if info["feasible"]:
            break
        before = copy.deepcopy(s)
        s2, act = _trim_once(s, info)
        if act is None:
            break
        for i, (b0, b1) in enumerate(zip(before.get("beats") or [], s2.get("beats") or [])):
            for f in ("dialogue", "rehook"):
                if (b0.get(f) or "") != (b1.get(f) or "") and (i, f) not in originals:
                    originals[(i, f)] = b0.get(f) or ""
        acts.append(act)
        s, info = timing.relayout_script(s2)
    if info["feasible"] and originals:
        s = _restore(s, originals, acts)
        s, info = timing.relayout_script(s)
    if len(acts) > 1:
        acts.append({"rule": tag, "target": "beats[*].t + payoff_contract",
                     "action": f"relayout after trims (feasible={info['feasible']}, "
                     f"overflow {info['overflow_s']}s, payoff at "
                     f"{info.get('payoff_start')}s)"})
    return s, acts


# ------------------------------------------------------------------ loop
def _apply(script, fails):
    rules = {rule_of(m) for m in fails}
    s = script
    acts = []
    if "D44" in rules and any("parenthetical" in _text(m) for m in fails
                              if rule_of(m) == "D44"):
        s, a = strip_parentheticals(s)
        acts += a
    if "D93" in rules:
        s, a = blank_duplicate_rehooks(s)
        acts += a
    if "D111" in rules:
        s, a = fix_single_test_numbering(s)
        acts += a
    if "D36" in rules:
        s, a = name_transformation_subject(s)
        acts += a
    if rules & set(TIMING_RULES):
        s, a = retime(s, rules)
        acts += a
    if "D103" in rules:
        s, a = compress_paragraph_cards(s)
        acts += a
    if "D142" in rules:
        s, a = compress_paragraph_cards(s, cps=True)
        acts += a
    return s, acts


def repair(script, gate_fn, max_rounds=3):
    """-> (best_script, log, passed). Never raises for a repair bug: the
    failing action is logged and the best version so far is returned."""
    best = json.loads(json.dumps(script))
    log = []
    try:
        best_fails = _gate(gate_fn, best)
    except Exception as e:  # a gate crash is not repairable
        log.append({"round": 0, "rule": "gate", "target": "gate",
                    "action": f"gate error: {e!r}"})
        return best, log, False
    if not best_fails:
        return best, log, True
    cur, cur_fails = best, best_fails
    for rnd in range(1, max_rounds + 1):
        try:
            new, acts = _apply(cur, cur_fails)
        except Exception as e:  # never let a repair bug kill the run
            log.append({"round": rnd, "rule": "repair", "target": "script",
                        "action": f"repair error: {e!r}"})
            break
        if not acts:
            log.append({"round": rnd, "rule": "none", "target": "script",
                        "action": "no deterministic repair applies to: " +
                        ", ".join(sorted({rule_of(m) or "?" for m in cur_fails}))})
            break
        for a in acts:
            log.append(dict(round=rnd, **a))
        # v2.1 D154: variant A is the script's own opening — it follows any
        # repair of the hook stack before the regate
        try:
            from vsp import creative as _cr
            synced = _cr.resync(new)
        except Exception as e:  # noqa: BLE001 — logged, the regate decides
            synced = [f"error: {e!r}"]
        if synced:
            log.append({"round": rnd, "rule": "sync", "target": "hook_variants[A]",
                        "action": "re-synced to the repaired hook: " + ", ".join(synced)})
        new_fails = _gate(gate_fn, new)
        log.append({"round": rnd, "rule": "regate", "target": "gate",
                    "action": f"{len(cur_fails)} -> {len(new_fails)} failure(s)"
                    + (": " + "; ".join(_text(m)[:80] for m in new_fails[:4])
                       if new_fails else "")})
        cur, cur_fails = new, new_fails
        if len(new_fails) < len(best_fails):
            best, best_fails = new, new_fails
        if not new_fails:
            break
    return best, log, not best_fails


if __name__ == "__main__":  # python3 -m vsp.repair script.json
    import sys
    from vsp.gates import gate1
    src = json.load(open(sys.argv[1], encoding="utf-8"))
    out, lg, ok = repair(src, gate1)
    for a in lg:
        print(f"[round {a['round']}] {a['rule']} {a['target']}: {a['action']}")
    print("PASS" if ok else "FAIL: " + "; ".join(gate1(out)))
