"""Content-sized beat layout — D143, the root-cause fix for D43/D55/D74/D78/D94.

The pre-2.0 maker placed beats at fixed fractions of the duration (payoff at
D*0.72, bait at D*0.85, CTA at D*0.94, a 2.0 s imperfection window...) and
never looked at the words inside them, so 609/990 baseline runs failed D43
(speech does not fit), 549 D74 (overrun), 252 D78 (gap) and 243 D94 (payoff
contract broken). This module sizes every window from its own words, at the
gate's own rate, then tiles the body from `start` to `duration`:

  1. min window = (dialogue + rehook words) / wps(delivery) + PAUSE, >= MIN_BEAT
     (rehook words count: the shot list speaks the rehook at the beat's end)
  2. the PAYOFF start p is placed inside the D7 band [0.72, 0.85]*D, as close
     to the classic 0.78*D contract as the minima allow
  3. slack goes preferentially to beats the shot list cuts internally
     (SPLITTABLE) and to beats that carry a camera move (MOVING); every other
     beat is capped at STATIC_CAP (3.5 s, the D48 threshold) when possible
  4. boundaries are rounded to 0.1 s and stay contiguous (no gaps/overlaps)

layout() never truncates copy. When the words cannot fit (sum of minima >
duration - start) it returns info["feasible"] = False plus the overflow in
seconds; the caller must trim at sentence boundaries (fit_words) or swap in a
shorter variant — D43/D74 keep failing loudly otherwise.
"""
import re

from vsp.lexicon import SLACK, SLOW_KEYS, WPS_BRISK, WPS_SLOW

PAUSE = 0.3
MIN_BEAT = 1.5
STATIC_CAP = 3.5
SPLITTABLE = {"EDUCATION BEAT", "DEMO BEAT", "EVIDENCE BEAT", "TEACHING BEAT",
              "STORY BEAT", "RITUAL BEAT"}
MOVING = {"PAYOFF", "IMPERFECTION BEAT"}
BAND = (0.72, 0.85)
TARGET = 0.78
T_RE = re.compile(r"(\d+(?:\.\d+)?)")


def wps(delivery):
    d = (delivery or "").lower()
    return WPS_SLOW if any(k in d for k in SLOW_KEYS) else WPS_BRISK


def gate_words(text):
    """The gate's tokenizer: whitespace split (an em dash is a token, D54/D114)."""
    return len((text or "").split())


def speech_seconds(beat, include_rehook=True):
    n = gate_words(beat.get("dialogue"))
    if include_rehook:
        n += gate_words(beat.get("rehook"))
    return n / wps(beat.get("delivery"))


def min_window(beat):
    s = speech_seconds(beat)
    return max(MIN_BEAT, s + PAUSE) if s else MIN_BEAT


def word_budget(seconds, delivery, rehook_words=0):
    """Max dialogue words (gate tokens) that fit `seconds` incl. PAUSE."""
    return max(0, int((seconds - PAUSE) * wps(delivery)) - rehook_words)


def parse_window(t):
    m = T_RE.findall(t or "")
    return (float(m[0]), float(m[1])) if len(m) >= 2 else (None, None)


def fmt_window(s, e):
    return f"{s:.1f}\u2013{e:.1f}s"


def fit_words(text, max_words):
    """Trim `text` to <= max_words gate tokens at a sentence boundary, then at
    a clause boundary (', ' / ' — ' / '; '). Returns None if even the first
    clause is too long — pick another variant instead (never cut mid-clause)."""
    text = (text or "").strip()
    if gate_words(text) <= max_words:
        return text
    sents = re.split(r"(?<=[.!?])\s+", text)
    out = []
    for s in sents:
        if gate_words(" ".join(out + [s])) <= max_words:
            out.append(s)
        else:
            break
    if out:
        return " ".join(out)
    first = sents[0]
    for sep in (" \u2014 ", "; ", ", "):
        if sep in first:
            head = first.split(sep)[0].strip()
            if 0 < gate_words(head) <= max_words:
                return head.rstrip(",;") + "."
    return None


def _caps(beats, mins):
    caps = []
    for b, m in zip(beats, mins):
        t = b.get("type", "")
        caps.append(float("inf") if (t in SPLITTABLE or t in MOVING)
                    else max(m, STATIC_CAP))
    return caps


def _fill(total, beats, mins, caps):
    """Distribute `total` seconds over beats: each gets >= its min, slack by
    weight (3 for SPLITTABLE/MOVING, 1 otherwise), respecting caps; slack no
    capped beat can absorb goes to the uncapped ones (or the last beat)."""
    n = len(beats)
    if n == 0:
        return []
    lens = list(mins)
    slack = total - sum(mins)
    if slack <= 1e-9:
        return lens
    w = [3.0 if (b.get("type") in SPLITTABLE or b.get("type") in MOVING)
         else 1.0 for b in beats]
    open_ = [i for i in range(n) if lens[i] < caps[i] - 1e-9]
    while slack > 1e-6 and open_:
        wsum = sum(w[i] for i in open_)
        nxt = []
        used = 0.0
        for i in open_:
            give = slack * w[i] / wsum
            room = caps[i] - lens[i]
            g = min(give, room)
            lens[i] += g
            used += g
            if lens[i] < caps[i] - 1e-9:
                nxt.append(i)
        slack -= used
        if used < 1e-9:
            break
        open_ = nxt
    if slack > 1e-6:
        lens[-1] += slack
    return lens


def layout(beats, duration, start=3.0, band=BAND, target=TARGET):
    """Assign contiguous 't' windows to body beats (narrative order kept).

    Returns (beats, info). Beats are shallow-copied with 't' set. info keys:
    feasible, overflow_s, payoff_start, payoff_end, band_ok, mins.
    """
    D = float(duration)
    beats = [dict(b) for b in beats]
    n = len(beats)
    mins = [min_window(b) for b in beats]
    caps = _caps(beats, mins)
    body = D - start
    need = sum(mins)
    info = {"feasible": need <= body + 1e-9, "overflow_s": round(max(0.0, need - body), 2),
            "payoff_start": None, "payoff_end": None, "band_ok": None,
            "mins": [round(m, 2) for m in mins]}
    k = next((i for i, b in enumerate(beats) if b.get("type") == "PAYOFF"), None)
    if not info["feasible"]:
        lens = mins                       # honour the words; D74 will fail loudly
    elif k is None:
        lens = _fill(body, beats, mins, caps)
    else:
        pre_min, post_min = sum(mins[:k]), sum(mins[k:])
        cap_pre = sum(caps[:k])
        cap_post = sum(caps[k:])
        lo = max(band[0] * D, start + pre_min)
        hi = min(band[1] * D, D - post_min)
        lo2 = max(lo, D - cap_post) if cap_post != float("inf") else lo
        hi2 = min(hi, start + cap_pre) if cap_pre != float("inf") else hi
        if lo2 <= hi2:
            lo, hi = lo2, hi2
        if lo <= hi:
            p = min(max(target * D, lo), hi)
            info["band_ok"] = True
        else:          # band unreachable: honour minima, stay near target
            p = min(max(target * D, start + pre_min), D - post_min)
            info["band_ok"] = False
        lens = _fill(p - start, beats[:k], mins[:k], caps[:k]) + \
            _fill(D - p, beats[k:], mins[k:], caps[k:])
    # contiguous, rounded boundaries
    bounds = [start]
    acc = start
    for ln in lens:
        acc += ln
        bounds.append(acc)
    r = [round(x, 1) for x in bounds]
    if info["feasible"]:
        r[-1] = round(D, 1)
    for i in range(1, len(r)):
        if r[i] <= r[i - 1]:
            r[i] = round(r[i - 1] + 0.1, 1)
    for i, b in enumerate(beats):
        b["t"] = fmt_window(r[i], r[i + 1])
    if k is not None:
        info["payoff_start"], info["payoff_end"] = r[k], r[k + 1]
        if info["band_ok"] is not None:
            info["band_ok"] = band[0] * D - 0.05 <= r[k] <= band[1] * D + 0.05
    return beats, info


def fits_gate(beat):
    """True if the beat passes the D43 gate formula (dialogue only, x1.15)."""
    s, e = parse_window(beat.get("t"))
    if s is None:
        return False
    return gate_words(beat.get("dialogue")) / wps(beat.get("delivery")) <= \
        (e - s) * SLACK


CONTRACT_RE = re.compile(r"(delivered at ~)(\d+(?:\.\d+)?)(s)")


def retime_contract(hook_stack, payoff_start):
    """Rewrite 'delivered at ~Xs' in the hook's payoff_contract (D94)."""
    out = []
    for h in hook_stack:
        h = dict(h)
        if h.get("payoff_contract") and payoff_start is not None:
            h["payoff_contract"] = CONTRACT_RE.sub(
                lambda m: f"{m.group(1)}{payoff_start:g}{m.group(3)}",
                h["payoff_contract"])
        out.append(h)
    return out


def relayout_script(script):
    """Re-time a finished script in place-safe fashion (returns a new dict):
    body beats re-laid from their words, contract re-timed. Used by the
    stage-6 repair loop (D150)."""
    s = dict(script)
    hs = list(s.get("hook_stack") or [])
    start = 3.0
    for h in hs:
        _, e = parse_window(h.get("t"))
        if e:
            start = max(start, e)
    beats, info = layout(s.get("beats") or [], s.get("duration_s") or 30,
                         start=start)
    s["beats"] = beats
    s["hook_stack"] = retime_contract(hs, info["payoff_start"])
    return s, info
