"""Caption cues from the script's spoken text (D152): SRT, WebVTT, Remotion
Caption JSON, and a lint pass.

    cues = build_cues(script, shots=None)
    to_srt(cues) / to_vtt(cues) / to_remotion(cues) / lint(cues)

Sidecar rules for 9:16 (docs/research/oss-pipelines.md §3 — Netflix / BBC /
DCMP): <= 2 lines x <= 32 chars per line, 0.83-7.0 s per cue, reading speed
target <= 17 cps (lint warns > 20), >= 2 frames between cues at 30 fps
(gaps under 12 frames are chained to exactly 2), breaks after punctuation /
before conjunctions, never between an article and its noun.

Timing source: "estimate". The spoken timeline is the shot list's (shots
follow the script windows; make_shotlist.build_shots is used when `shots`
is not given): per beat, dialogue then rehook, words at the gate's own rate
(3.0 words/s, 2.5 when the delivery says slow down / unhurried / never
rushed) — dialogue from the window start, the rehook landing at the window
end (the shot list speaks it as the transition into the next beat). Word
timings inside a line are uniform. Marlowe's caption stage re-aligns to the
real audio (DELIVERABLE: captioning is Marlowe's stage — these files are
sidecars, never burned in).
"""
import json
import re

FPS = 30
MAX_LINES = 2
MAX_CHARS = 32
MIN_DUR = 0.83
MAX_DUR = 7.0
TARGET_CPS = 17.0
WARN_CPS = 20.0
MIN_GAP = 2.0 / FPS
CHAIN_GAP = 12.0 / FPS
LINGER = 0.5
TIMING_SOURCE = "estimate"
SLOW_KEYS = ("slow down", "unhurried", "never rushed")

ARTICLES = {"a", "an", "the"}
# words that must not end a line/cue (the noun/verb they govern follows)
STICKY = ARTICLES | {"my", "your", "his", "her", "its", "our", "their", "this",
                     "that", "these", "those", "to", "of", "in", "on", "at",
                     "for", "with", "by", "from", "and", "or", "but", "no",
                     "every", "each", "one", "two", "three"}
CONJ = {"and", "but", "or", "so", "because", "then", "when", "while", "if",
        "which", "who", "that"}
_SENT_END = re.compile(r"[.!?\u2026][\"'\u201d\u2019)]*$")
_CLAUSE_END = re.compile(r"[,;:\u2014\u2013][\"'\u201d\u2019)]*$")
_DASH = {"\u2014", "\u2013", "-", "--"}


def _wps(delivery):
    return 2.5 if any(k in (delivery or "").lower() for k in SLOW_KEYS) else 3.0


def _bare(w):
    return re.sub(r"[^\w']", "", (w or "").lower())


# ------------------------------------------------------------ timeline
def _groups_from_shots(shots):
    """Shot list -> per-beat groups (sub-shots merged): window, beat,
    dialogue, rehook, delivery."""
    out, idx = [], {}
    for sh in shots or []:
        g = sh.get("group", sh.get("n"))
        s, e = sh.get("s"), sh.get("e")
        if s is None or e is None:
            m = re.findall(r"(\d+(?:\.\d+)?)", sh.get("t", ""))
            if len(m) < 2:
                continue
            s, e = float(m[0]), float(m[1])
        if g not in idx:
            idx[g] = len(out)
            out.append({"s": float(s), "e": float(e),
                        "beat": (sh.get("beat") or "").replace(" (cont.)", ""),
                        "dialogue": "", "rehook": "", "delivery": ""})
        grp = out[idx[g]]
        grp["s"], grp["e"] = min(grp["s"], float(s)), max(grp["e"], float(e))
        if sh.get("dialogue") and not grp["dialogue"]:
            grp["dialogue"] = sh["dialogue"]
            grp["delivery"] = sh.get("delivery") or ""
        if sh.get("rehook"):
            grp["rehook"] = sh["rehook"]
    return sorted(out, key=lambda x: x["s"])


def _groups_from_script(script):
    try:
        import make_shotlist
        shots, _ = make_shotlist.build_shots(script)
        return _groups_from_shots(shots)
    except Exception:
        out = []
        for it in list(script.get("hook_stack") or []) + list(script.get("beats") or []):
            m = re.findall(r"(\d+(?:\.\d+)?)", it.get("t") or "")
            if len(m) >= 2 and float(m[1]) > float(m[0]):
                out.append({"s": float(m[0]), "e": float(m[1]),
                            "beat": it.get("type", ""),
                            "dialogue": it.get("dialogue") or "",
                            "rehook": it.get("rehook") or "",
                            "delivery": it.get("delivery") or ""})
        return sorted(out, key=lambda x: x["s"])


def _segments(groups):
    """Spoken segments with uniform word timings: (beat, source, words)
    where words = [(token, start, end), ...]."""
    segs = []
    for g in groups:
        s, e = g["s"], g["e"]
        win = max(0.0, e - s)
        rate = _wps(g["delivery"])
        d = (g["dialogue"] or "").split()
        r = (g["rehook"] or "").split()
        nd, nr = len(d) / rate, len(r) / rate
        if nd + nr > win and nd + nr > 0:
            f = win / (nd + nr)
            nd, nr = nd * f, nr * f
        if d:
            segs.append((g["beat"], "dialogue", _uniform(d, s, s + nd)))
        if r:
            segs.append((g["beat"], "rehook", _uniform(r, e - nr, e)))
    return segs


def _uniform(tokens, a, b):
    step = (b - a) / len(tokens)
    return [(t, a + i * step, a + (i + 1) * step) for i, t in enumerate(tokens)]


# ------------------------------------------------------------ layout
def break_lines(tokens, max_chars=MAX_CHARS, max_lines=MAX_LINES):
    """Best <= max_lines line split of `tokens` (each line <= max_chars), or
    None. Prefers breaks after punctuation / before conjunctions, balanced
    lines, and never leaves an article (or other sticky word) at a line end."""
    text = " ".join(tokens)
    if len(text) <= max_chars:
        return [text]
    if max_lines < 2:
        return None
    best, best_score = None, None
    for k in range(1, len(tokens)):
        l1, l2 = " ".join(tokens[:k]), " ".join(tokens[k:])
        if len(l1) > max_chars or len(l2) > max_chars:
            continue
        last = _bare(tokens[k - 1])
        if last in ARTICLES or tokens[k] in _DASH:
            continue
        score = -abs(len(l1) - len(l2)) / 6.0
        if _SENT_END.search(tokens[k - 1]):
            score += 8
        elif _CLAUSE_END.search(tokens[k - 1]):
            score += 6
        elif _bare(tokens[k]) in CONJ:
            score += 2
        if last in STICKY:
            score -= 6
        if best_score is None or score > best_score:
            best, best_score = [l1, l2], score
    return best


def _fits(tokens):
    return break_lines(tokens) is not None


def _cue_cost(words, toks, i, j, lines):
    """Cost of one cue words[i:j]: a flat per-cue cost (fewer, fuller cues),
    short / fast cues, and where the cue ends (sentence < clause <
    before a conjunction < mid-phrase; never after an article)."""
    n = len(words)
    dur = words[j - 1][2] - words[i][1]
    chars = len(" ".join(toks[i:j]))
    cost = 10.0
    if dur < MIN_DUR:
        cost += 6 + 12 * (MIN_DUR - dur) / MIN_DUR
    cps = chars / max(dur, 1e-6)
    cost += 6 if cps > WARN_CPS else 2 if cps > TARGET_CPS else 0
    last = toks[j - 1]
    if j == n or _SENT_END.search(last):
        pass
    elif _CLAUSE_END.search(last):
        cost += 2
    elif _bare(toks[j]) in CONJ:
        cost += 4
    else:
        cost += 8
    if j < n and _bare(last) in ARTICLES:
        cost += 40
    elif j < n and _bare(last) in STICKY:
        cost += 10
    return cost


def _chunk(words):
    """Split one segment's timed words into cue-sized runs — minimum-cost
    segmentation (DP over break points; every cue fits 2 x 32 chars and
    <= 7 s of speech)."""
    toks = [w[0] for w in words]
    n = len(words)
    best = [0.0] + [float("inf")] * n
    back = [0] * (n + 1)
    for j in range(1, n + 1):
        for i in range(j - 1, -1, -1):
            if words[j - 1][2] - words[i][1] > MAX_DUR and j - i > 1:
                break
            lines = break_lines(toks[i:j])
            if lines is None:
                if j - i > 1:
                    break
                cost = 50.0             # a single over-long token: forced cue
            else:
                cost = _cue_cost(words, toks, i, j, lines)
            if best[i] + cost < best[j]:
                best[j], back[j] = best[i] + cost, i
    out, j = [], n
    while j > 0:
        i = back[j]
        out.append(words[i:j])
        j = i
    return out[::-1]


def build_cues(script, shots=None):
    """Script (+ optional shot list) -> list of cue dicts:
    {index, start, end, text, lines, beat, source, words:[{word,start,end}]}.
    Times in seconds (float); text is lines joined by newline."""
    groups = _groups_from_shots(shots) if shots else _groups_from_script(script)
    cues = []
    for beat, source, words in _segments(groups):
        for run in _chunk(words):
            toks = [w[0] for w in run]
            lines = break_lines(toks) or [" ".join(toks)]
            cues.append({"start": run[0][1], "end": run[-1][2], "speech_end": run[-1][2],
                         "lines": lines, "text": "\n".join(lines), "beat": beat,
                         "source": source,
                         "words": [{"word": w, "start": round(a, 3), "end": round(b, 3)}
                                   for w, a, b in run]})
    cues.sort(key=lambda c: (c["start"], c["end"]))
    _retime(cues, groups)
    for i, c in enumerate(cues, 1):
        c["index"] = i
        c["start"], c["end"] = round(c["start"], 3), round(c["end"], 3)
        c.pop("speech_end", None)
    return cues


LEAD = 0.5          # a cue may appear up to 15 frames before its speech (DCMP)


def _cps(c):
    return len(" ".join(c["lines"])) / max(1e-6, c["end"] - c["start"])


def _balance(cues):
    """Back-to-back cues (gap < 12 frames): when either runs over the 17 cps
    target, slide the shared boundary (<= 0.5 s, each side keeps >= 0.83 s)
    toward equal reading speed — the dense cue borrows display time from
    its lighter neighbour instead of flashing by."""
    for i in range(len(cues) - 1):
        a, b = cues[i], cues[i + 1]
        if b["start"] - a["end"] >= CHAIN_GAP or max(_cps(a), _cps(b)) <= TARGET_CPS:
            continue
        ca, cb = len(" ".join(a["lines"])), len(" ".join(b["lines"]))
        t = (a["end"] + b["start"]) / 2.0
        t_eq = a["start"] + (b["end"] - a["start"]) * ca / float(ca + cb)
        t_new = min(max(t_eq, t - LEAD, a["start"] + MIN_DUR), t + LEAD, b["end"] - MIN_DUR)
        if abs(t_new - t) < 1e-3:
            continue
        a["end"], b["start"] = t_new - MIN_GAP / 2.0, t_new + MIN_GAP / 2.0


def _retime(cues, groups):
    """Reading-time relief then hygiene: linger up to 0.5 s after the last
    word, lead up to 0.5 s before the first when the cue is still under
    0.83 s or over the 17 cps target (only into free time — never over a
    neighbour), cap at 7 s, chain gaps under 12 frames to exactly 2 frames."""
    end_all = max([g["e"] for g in groups] + [c["end"] for c in cues] + [0.0])
    for i, c in enumerate(cues):
        nxt = cues[i + 1]["start"] if i + 1 < len(cues) else end_all
        prev_end = cues[i - 1]["end"] if i else 0.0
        c["end"] = max(c["end"], min(c["end"] + LINGER, nxt - MIN_GAP))
        chars = len(" ".join(c["lines"]))
        want = max(MIN_DUR, chars / TARGET_CPS)
        short = want - (c["end"] - c["start"])
        if short > 0:
            early = min(LEAD, short, c["start"] - (prev_end + MIN_GAP))
            if early > 0:
                c["start"] -= early
        if c["end"] - c["start"] > MAX_DUR:
            c["end"] = c["start"] + MAX_DUR
    _balance(cues)
    for i in range(len(cues) - 1):
        a, b = cues[i], cues[i + 1]
        gap = b["start"] - a["end"]
        if gap < CHAIN_GAP:
            a["end"] = b["start"] - MIN_GAP
            if a["end"] - a["start"] < 0.3:      # never collapse a cue
                a["end"] = a["start"] + 0.3
                b["start"] = max(b["start"], a["end"] + MIN_GAP)


# ------------------------------------------------------------ formats
def _ts(t, sep):
    ms = int(round(max(0.0, t) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def to_srt(cues):
    """SubRip: index, HH:MM:SS,mmm --> HH:MM:SS,mmm, text, blank line."""
    out = []
    for i, c in enumerate(cues, 1):
        out += [str(i), f"{_ts(c['start'], ',')} --> {_ts(c['end'], ',')}", c["text"], ""]
    return "\n".join(out)


def to_vtt(cues):
    """WebVTT: WEBVTT header, a NOTE with the timing source, HH:MM:SS.mmm."""
    out = ["WEBVTT", "",
           f"NOTE timing_source={TIMING_SOURCE} (words at the script's delivery rate; "
           "re-align to the rendered audio)", ""]
    for i, c in enumerate(cues, 1):
        out += [str(i), f"{_ts(c['start'], '.')} --> {_ts(c['end'], '.')}",
                c["text"].replace("-->", "\u2192"), ""]
    return "\n".join(out)


def to_remotion(cues):
    """Remotion @remotion/captions Caption[] at word level: {text, startMs,
    endMs, timestampMs, confidence}. Estimated uniform timings (timestampMs =
    word midpoint, confidence null — no recognizer ran); a space precedes
    every word after the first; pageBreakAfter marks each cue's last word so
    createTikTokStyleCaptions() pages follow the cue boundaries."""
    out = []
    for c in cues:
        ws = c.get("words") or []
        for k, w in enumerate(ws):
            a = int(round(w["start"] * 1000))
            b = max(a + 1, int(round(w["end"] * 1000)))
            cap = {"text": (" " if out else "") + w["word"], "startMs": a, "endMs": b,
                   "timestampMs": (a + b) // 2, "confidence": None}
            if k == len(ws) - 1:
                cap["pageBreakAfter"] = True
            out.append(cap)
    return out


def remotion_json(cues, indent=1):
    """captions.json payload: {timing_source, fps, captions: Caption[]}."""
    return json.dumps({"timing_source": TIMING_SOURCE, "fps": FPS,
                       "format": "@remotion/captions Caption[]",
                       "captions": to_remotion(cues)}, indent=indent, ensure_ascii=False)


# ------------------------------------------------------------ lint
def lint(cues):
    """-> list of warning strings, each 'cue N: <kind> ...'. Kinds: empty,
    lines, line-length, article-split, duration, cps, order, overlap, gap."""
    warns = []
    for i, c in enumerate(cues):
        n = c.get("index", i + 1)
        lines = c.get("lines") or (c.get("text") or "").split("\n")
        dur = c["end"] - c["start"]
        if not "".join(lines).strip():
            warns.append(f"cue {n}: empty text")
        if len(lines) > MAX_LINES:
            warns.append(f"cue {n}: lines {len(lines)} > {MAX_LINES}")
        for k, ln in enumerate(lines, 1):
            if len(ln) > MAX_CHARS:
                warns.append(f"cue {n}: line-length line {k} is {len(ln)} chars > {MAX_CHARS}")
        for a, b in zip(lines, lines[1:]):
            last = _bare(a.split()[-1]) if a.split() else ""
            if last in ARTICLES:
                warns.append(f"cue {n}: article-split '{a.split()[-1]} | {b.split()[0]}'")
        if dur < MIN_DUR - 1e-3:
            warns.append(f"cue {n}: duration {dur:.2f}s < {MIN_DUR}s")
        if dur > MAX_DUR + 1e-3:
            warns.append(f"cue {n}: duration {dur:.2f}s > {MAX_DUR}s")
        chars = len(" ".join(lines))
        if dur > 0 and chars / dur > WARN_CPS:
            warns.append(f"cue {n}: cps {chars / dur:.1f} > {WARN_CPS:g}")
        if i + 1 < len(cues):
            nx = cues[i + 1]
            if nx["start"] < c["start"]:
                warns.append(f"cue {n}: order next cue starts earlier")
            gap = nx["start"] - c["end"]
            if gap < -1e-6:
                warns.append(f"cue {n}: overlap {-gap * 1000:.0f}ms with next cue")
            elif gap < MIN_GAP - 1e-3:
                warns.append(f"cue {n}: gap {gap * 1000:.0f}ms < 2 frames "
                             f"({MIN_GAP * 1000:.0f}ms)")
    return warns


def stats(cues):
    """Summary numbers for reports/manifests."""
    if not cues:
        return {"cues": 0}
    cps = [len(" ".join(c["lines"])) / max(1e-6, c["end"] - c["start"]) for c in cues]
    return {"cues": len(cues), "timing_source": TIMING_SOURCE,
            "max_cps": round(max(cps), 1), "mean_cps": round(sum(cps) / len(cps), 1),
            "over_target_cps": sum(1 for x in cps if x > TARGET_CPS),
            "warnings": len(lint(cues))}
