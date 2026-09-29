"""Gate 1 (script) and gate 2 (brief) — moved verbatim from pipeline.py.

pipeline.py re-exports gate1/gate2 so existing callers keep working. The
checks and their messages are byte-identical to d8f8759 (the self-test
matches on message substrings). New registry rules (vsp/rules.py) are
appended AFTER the legacy checks so legacy message order never changes.
Never weaken a check here to make a script pass — fix the maker.
"""
import json
import re

# hashtag stems that belong to a different niche than the product suggests
MISMATCH = [("skincare", "hair"), ("hair", "skin"), ("makeup", "hair"),
            ("fitness", "beauty"), ("cooking", "beauty")]
STAGE_VERBS = ["cut to", "pan to", "b-roll", "on camera,", "on camera.",
               "show the", "show a",
               "zoom in", "zoom out", "zooming in", "zooming out",
               "push in", "pushes in", "pushing in"]  # D58: camera
# commands (zoom in/out, push in included) are stage directions when spoken,
# never presenter language — gauntlet cycle 4 fooled the old list with
# "Watch as I zoom in on the detail"; cycle 5 fooled the zoom-repaired list
# with "The camera pushes in." (push-in = dolly-in camera move).
# Gauntlet cycle 12: "on camera." (period) slipped past the comma-only entry —
# seed 811's payoff spoke "Test result: before and after, side by side, on
# camera." while the gate flagged only the demo beat's "on camera,". The
# screen is punctuation-robust on the adverbial forms now; bare "on camera"
# (no trailing punctuation) stays out — it would false-positive on content
# ("birds on camera every single morning", the feeder's camera feed).
# commands (zoom in/out, push in included) are stage directions when spoken,
# never presenter language — gauntlet cycle 4 fooled the old list with
# "Watch as I zoom in on the detail"; cycle 5 fooled the zoom-repaired list
# with "The camera pushes in." (push-in = dolly-in camera move).
# "hold on [X]" is D58-spec'd but left out: broad-substring matching would
# false-positive on presenter filler ("Hold on, let me tell you").
# link-payload phrases grouped by destination — 2+ GROUPS hit = competing CTAs
LINK_GROUPS = [
    ["link in bio"],
    ["link list", "in your dms", "check your dms"],
    ["tap the link"],
]


def words_per_sec(delivery):
    slow = any(k in (delivery or "").lower()
               for k in ("slow down", "unhurried", "never rushed"))
    return 2.5 if slow else 3.0


def parse_t(t):
    m = re.findall(r"(\d+(?:\.\d+)?)", t or "")
    return (float(m[0]), float(m[1])) if len(m) >= 2 else (None, None)


def gate1(script):
    fails = []
    for k in ("prompt", "hook_stack", "beats", "caption", "niche"):
        if not script.get(k):
            fails.append(f"missing/empty required key: {k}")
    if len(script.get("beats", [])) < 3:
        fails.append("fewer than 3 beats")
    prompt = script.get("prompt", "").lower()
    # D37: no invented prices — D132 (gauntlet cycle 18: caption was unscanned —
    # "$39" in the caption sailed through. Caption ships to the viewer, so a
    # price there is fabricated copy, same as in dialogue.) D132: scan covers
    # beats + caption; prompt carries the D37 allow-path.
    scanned = json.dumps(script.get("beats",)) + " " + script.get("caption", "")
    if re.search(r"\$\d+", scanned) and not re.search(r"\$\d+", prompt):
        fails.append("D37: price in beats/caption but none in prompt — price invented")
    # hashtag/niche mismatch
    tags = re.findall(r"#(\w+)", script.get("caption", "").lower())
    for tag in tags:
        for wrong, cue in MISMATCH:
            if wrong in tag and cue in prompt:
                fails.append(f"hashtag/niche mismatch: #{tag} on '{prompt}'")
    # D43 pre-check on beat windows (missing t is a failure, not a skip)
    for b in script.get("beats", []):
        if not b.get("t"):
            fails.append(f"missing time window on {b.get('type', '?')} — D43 cannot be checked")
            continue
        s, e = parse_t(b.get("t", ""))
        dlg = b.get("dialogue", "")
        if s is not None and dlg:
            need = len(dlg.split()) / words_per_sec(b.get("delivery", ""))
            if need > (e - s) * 1.15:
                fails.append(f"D43: {b.get('type')}: ~{need:.1f}s speech in {e-s:.1f}s window")
    # D44 pre-check: no stage directions in dialogue/rehooks
    for b in script.get("beats", []) + script.get("hook_stack", []):
        txt = (b.get("dialogue", "") + " " + b.get("rehook", "")).lower()
        for v in STAGE_VERBS:
            if v in txt:
                fails.append(f"D44: stage direction in spoken line ({b.get('type')}): '{v}'")
                break
        # D126 (gauntlet cycle 16): the verb list misses parenthetical performer
        # directions — "(smiling)" in a spoken line is a staging note for the
        # voice pass, never spoken copy. Anything in parens/brackets inside
        # dialogue/rehooks is a direction, not dialogue.
        pm = re.search(r"\([^()]{1,80}\)|\[[^\[\]]{1,80}\]", txt)
        if pm:
            fails.append(f"D44: parenthetical staging note in spoken line "
                         f"({b.get('type')}): '{pm.group(0)}'")
    # D55: beat time windows must not overlap — the shot list owns one window
    # per beat, so an overlap leaves 2.6s of timeline with two owners
    wins = []
    for b in script.get("beats", []):
        s, e = parse_t(b.get("t", ""))
        if s is not None:
            wins.append((s, e, b.get("type", "?")))
    for i in range(len(wins)):
        for j in range(i + 1, len(wins)):
            ov = min(wins[i][1], wins[j][1]) - max(wins[i][0], wins[j][0])
            if ov > 0.1:
                fails.append(f"D55: beat windows overlap ({wins[i][2]} and {wins[j][2]} "
                             f"share ~{ov:.1f}s)")
    # D74: beats must fit the duration budget — the last beat may not end past
    # duration_s. An overrun pushes the payoff past D7's 72–85% placement band
    # and breaks the hook's payoff_contract time (seed 801: hook promised the
    # payoff at ~23.4s but beats ran to 35.0s on a 30s video).
    dur = script.get("duration_s", 30)
    if wins:
        last_end = max(e for _, e, _ in wins)
        if last_end > dur:
            fails.append(f"D74: beats run to {last_end:.1f}s but duration is {dur}s "
                         f"— timeline exceeds budget")
    # D78: beats must tile the spoken timeline — no dead-air gaps. D55 covers
    # overlaps and D74 covers overruns, but a hole between two beats (seed 802:
    # 1.2s of nothing between DEMO 20.4s and PAYOFF 21.6s) leaves timeline with
    # no owner: the shot list must invent coverage. Scope is internal gaps only:
    # the 0–3.0s hook region belongs to the hook stack and the tail after the
    # last beat belongs to the brief's outro hold (proven-legit: hair-wax-stick
    # tiles 3.0–29.0s on a 30s video and passes clean).
    ordered = sorted(wins, key=lambda w: (w[0], w[1]))
    for (s1, e1, t1), (s2, e2, t2) in zip(ordered, ordered[1:]):
        gap = s2 - e1
        if gap > 0.5:
            fails.append(f"D78: dead-air gap (~{gap:.1f}s) between {t1} and {t2} "
                         f"({e1:.1f}s–{s2:.1f}s) — no beat owns that timeline")
    # D94: the hook's payoff_contract names a delivery time — the PAYOFF beat
    # must actually land there. The D65 de-overlap pass shifts beats forward
    # in time to fix D55 overlaps but never re-times the contract (seed 805:
    # hook promises the transformation result "delivered at ~23.4s" while the
    # PAYOFF beat was pushed to 24.6–28.5s — the hook lies). Parse
    # "delivered at ~<t>s"; the PAYOFF window must contain t (±0.5s for the
    # "~"). Silent when the contract or the PAYOFF beat is absent.
    promised = None
    for h in script.get("hook_stack", []):
        m = re.search(r"delivered at ~(\d+(?:\.\d+)?)s",
                      h.get("payoff_contract", "") or "")
        if m:
            promised = float(m.group(1))
            break
    if promised is not None:
        for b in script.get("beats", []):
            if b.get("type") == "PAYOFF":
                ps, pe = parse_t(b.get("t", ""))
                if ps is not None and not (ps - 0.5 <= promised <= pe + 0.5):
                    fails.append(f"D94: hook promises payoff at ~{promised:g}s "
                                 f"but PAYOFF beat runs {ps:.1f}–{pe:.1f}s "
                                 f"— contract broken")
                break
    # D103: on_screen is display text, not a notes field — a sentence-length
    # block in on_screen (seed 807: the PAYOFF beat carried a 33-word
    # caption-style sentence) cannot be read in a ≤3s shot and is a caption
    # in disguise (playbook §4: ≤3-word on-screen text). The cap is
    # egregious-case only (>12 words) so legit label pairs ("BEFORE | AFTER",
    # "DAY 1 | TODAY (split-screen, timestamped)") pass with headroom — the
    # strict §4 rule itself stays out of gate remit per the cycles 3/5/7
    # false-positive call.
    for b in script.get("beats", []) + script.get("hook_stack", []):
        os_txt = (b.get("on_screen") or "").strip()
        if len(os_txt.split()) > 12:
            fails.append(f"D103: on_screen is a paragraph ({len(os_txt.split())} words, "
                         f"{b.get('type')}): '{os_txt[:60]}...' — display text, not notes")
    # D111: no dangling test numbering — the demo template prefixes "Test 1"
    # (dialogue and/or on_screen "TEST 1") even for single-test demos. A
    # numbered test with no Test 2 leaves the viewer waiting for a continuation
    # that never comes; drop the number or add the second test (seed 810: the
    # seed-810 pov-vlog script voices "Test 1: ..." and shows "TEST 1" with no
    # "Test 2" anywhere; 5 rotation scripts now ship the pattern — it crossed
    # the cycle-9 "second instance" watch threshold). Silent when the script
    # genuinely numbers multiple tests. Scope is the beats' spoken/display
    # text; "1 test" / "test: ..." do not match the ordinal form.
    beat_text = " ".join((b.get("dialogue", "") or "") + " " +
                         (b.get("on_screen", "") or "")
                         for b in script.get("beats", []))
    if re.search(r"\btest\s+1\b", beat_text, re.I) \
            and not re.search(r"\btest\s+2\b", beat_text, re.I):
        fails.append("D111: 'Test 1' with no 'Test 2' — dangling test numbering "
                     "in a single-test script")
    return fails


def gate2(bundle_text, script):
    fails = []
    if "Render the FULL video as one long uncut master" not in bundle_text:
        fails.append("DELIVERABLE block missing/altered")
    if "9:16" not in bundle_text:
        fails.append("no 9:16 render spec")
    if "words.json" not in bundle_text:
        fails.append("words.json not requested")
    if "## Do NOT" not in bundle_text and "no burned" not in bundle_text.lower():
        fails.append("Do-NOT list missing from brief")
    if '"words"' not in bundle_text and "'words'" not in bundle_text:
        fails.append("words.json schema missing")
    if bundle_text.count("instagram.com/reel/") < 1:
        fails.append("no reference reels — quality bar unanchored")
    if "D43 WARNING" in bundle_text:
        fails.append("D43 warnings present in bundle — unperformable dialogue shipped")
    prompt = script.get("prompt", "").lower()
    # D36
    if "same body" in bundle_text.lower() and "body" not in prompt:
        fails.append("D36: 'same body' used for a non-body transformation")
    # B4a: follow before keyword in comment-bait dialogue
    for b in script.get("beats", []):
        if b.get("type") == "COMMENT BAIT":
            d = b.get("dialogue", "").lower()
            if "comment" in d and ("follow" not in d or d.index("follow") > d.index("comment")):
                fails.append("B4a: comment-bait lacks follow-before-keyword")
    # D46: competing link CTAs — phrases from 2+ payload groups is a failure
    # ("link list" + "in your DMs" is one payload, not competing)
    low = bundle_text.lower()
    groups_hit = [g for g in LINK_GROUPS if any(p in low for p in g)]
    if len(groups_hit) >= 2:
        fails.append(f"D46: competing link CTAs ({len(groups_hit)} payload destinations)")
    # duration arithmetic (sub-shot numbering like 4a/4b supported)
    shot_re = re.compile(r"### Shot (\d+[a-z]?) \((\d+(?:\.\d+)?)[\u2013-](\d+(?:\.\d+)?)s\)")
    blocks = re.findall(r"### Shot \d+[a-z]? \([^)]+\) \u2014 ([^\n]+)\n((?:- [^\n]+\n?)+)", bundle_text)
    shots = shot_re.findall(bundle_text)
    if shots:
        total = max(float(e) for _, _, e in shots)
        dur = script.get("duration_s", 30)
        if abs(total - dur) / dur > 0.15:
            fails.append(f"shot timeline ({total:.1f}s) drifts >15% from duration ({dur}s)")
    # D48: no long static shots without internal cuts
    MOVE_KW = ("push-in", "push in", "pan", "tilt", "dolly", "handheld", "tracking", "move")
    for num, s, e in shots:
        if float(e) - float(s) > 3.5 and not re.search(r"[a-z]$", num):
            blk = re.search(r"### Shot %s \([^)]+\)[^\n]*\n((?:- [^\n]+\n?)+)" % re.escape(num), bundle_text)
            body = blk.group(1).lower() if blk else ""
            if not any(k in body for k in MOVE_KW):
                fails.append(f"D48: shot {num} is {float(e)-float(s):.1f}s with no internal cuts/camera move")
    # D47: no 3+ consecutive same-scale talking-head shots
    run = 0
    for beat, body in blocks:
        if "to camera" in body.lower().split("on-screen")[0]:
            run += 1
            if run >= 3:
                fails.append("D47: 3+ consecutive talking-head shots — scale never changes")
                break
        else:
            run = 0
    return fails
