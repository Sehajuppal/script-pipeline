"""Self-test fixtures — the 17 legacy gate cases, moved verbatim from
pipeline.py (d8f8759). Each case: (name, script, want_pass, want_msgs).

New cases for new gate rules go in new_cases() (never edit or delete a
legacy case: every legacy case must keep failing with its original message).
new_cases() tuples may carry a 5th element of options (see its docstring);
unit_cases() are in-process contract checks run by vsp/selftest.py.

Label note: the legacy "gap-in-timeline" comment says "D75" — that was the
dead-air rule's number before renumbering; it is D78 in RULES.md (D75 is the
bird/animal-object pets routing rule).
"""


def legacy_cases():
    good = {
        "prompt": "test product", "niche": "beauty", "presenter": "human",
        "format": "demo", "duration_s": 10, "hook_family": "test",
        "hook_stack": [{"type": "HOOK", "dialogue": "Look at this."}],
        "caption": "Test caption. #beautytok",
        "beats": [
            {"type": "VISUAL TRIGGER", "t": "0.0-0.5s", "direction": "Split-screen.",
             "on_screen": "BEFORE | AFTER", "dialogue": "", "delivery": "", "rehook": ""},
            {"type": "VERBAL HOOK + LOCK", "t": "0.5-3.0s", "direction": "Presenter to camera.",
             "on_screen": "", "dialogue": "This is the after.", "delivery": "Brisk.",
             "rehook": "Here is what it took."},
            {"type": "DEMO BEAT", "t": "3.0-6.0s", "direction": "Hands demo the product.",
             "on_screen": "", "dialogue": "One pass and it is done.", "delivery": "Brisk.",
             "rehook": ""},
            {"type": "COMMENT BAIT", "t": "6.0-9.0s", "direction": "Presenter to camera.",
             "on_screen": "", "dialogue": "Hit follow, comment TEST and it is yours.",
             "delivery": "Brisk.", "rehook": ""},
        ],
    }
    cases = [
        ("good", good, True, []),
        ("missing-t", {**good, "beats": [{**good["beats"][1], "t": ""}]}, False, ["missing time window"]),
        ("d43-overflow", {**good, "beats": [
            {**good["beats"][1], "dialogue": " ".join(["word"] * 30)}]}, False, ["D43"]),
        ("invented-price", {**good, "beats": [
            {**good["beats"][1], "dialogue": "Only $20 today."}]}, False, ["D37"]),
        # D37 (gauntlet cycle 18): the gate scanned beats only — "$39" in the
        # caption sailed through. Caption ships to the viewer, so a price
        # there is fabricated copy too.
        ("invented-price-caption", {**good,
            "caption": "Test caption. Only $39 today. #beautytok"}, False, ["D37"]),
        ("stage-direction", {**good, "beats": [
            {**good["beats"][2], "dialogue": "Show the product up close on camera, folks."}]},
         False, ["D44"]),
        # D58 (gauntlet cycle 4): "zoom in" in a spoken line is a camera
        # command, not presenter language — the old verb list let it pass.
        ("zoom-in-spoken", {**good, "beats": [
            {**good["beats"][2], "dialogue": "Watch as I zoom in on the detail, it is incredible."}]},
         False, ["D44"]),
        # D58 (gauntlet cycle 5): "push in" (dolly-in) is the same class —
        # "The camera pushes in." passed the zoom-repaired verb list.
        ("push-in-spoken", {**good, "beats": [
            {**good["beats"][2], "dialogue": "Confession: first swipe, I fumbled it. The camera pushes in."}]},
         False, ["D44"]),
        # D58 (gauntlet cycle 12): the screen matched "on camera," (comma)
        # but not "on camera." (period) — seed 811's payoff spoke the period
        # form and passed. Bare "on camera" (no punctuation) stays allowed:
        # content, not direction ("birds on camera every single morning").
        ("on-camera-period-spoken", {**good, "beats": [
            {**good["beats"][2], "dialogue": "Test result: before and after, side by side, on camera."}]},
         False, ["D44"]),
        # gauntlet cycle 16: parenthetical performer directions sail past the
        # STAGE_VERBS word list — "(smiling)" in a spoken line is a staging
        # note, not spoken copy. Parens/brackets in dialogue are always
        # voice-pass notes, never dialogue.
        ("parenthetical-stage-direction", {**good, "beats": [
            {**good["beats"][2], "dialogue": "Day 30 verdict: deeper sleep, no 3pm crash. (smiling)"}]},
         False, ["D44"]),
        ("overlapping-windows", {**good, "beats": [
            {**good["beats"][0]},
            {**good["beats"][1]},
            {**good["beats"][2], "t": "3.0-8.0s"},
            {**good["beats"][3], "t": "6.0-9.0s"}]}, False, ["D55"]),
        ("over-budget-timeline", {**good, "beats": [
            {**good["beats"][0]},
            {**good["beats"][1]},
            {**good["beats"][2], "t": "3.0-8.0s"},
            {**good["beats"][3], "t": "8.0-13.5s"}]}, False, ["D74"]),
        # D75: 2.0s dead-air hole between hook and demo — dialogue fits its own
        # window, so only the gap check may fire.
        ("gap-in-timeline", {**good, "beats": [
            {**good["beats"][0]},
            {**good["beats"][1]},
            {**good["beats"][2], "t": "5.0-8.0s"},
            {**good["beats"][3], "t": "8.0-10.0s",
             "dialogue": "Hit follow, comment TEST."}]}, False, ["D78"]),
        # D94 (gauntlet cycle 6): the de-overlap pass pushed the PAYOFF beat
        # late while the hook still promises "delivered at ~7.8s" — nothing
        # else fails on this fixture, so the case is D94-pure.
        ("payoff-contract-broken", {
            **good,
            "duration_s": 10,
            "hook_stack": [{"type": "VERBAL HOOK + LOCK",
                            "dialogue": "Look at this.",
                            "payoff_contract": "Viewer is promised a specific "
                                               "payoff, delivered at ~7.8s — "
                                               "never frontloaded."}],
            "beats": [
                {**good["beats"][0]},
                {**good["beats"][1]},
                {**good["beats"][2], "t": "3.0-8.5s"},
                {"type": "PAYOFF", "t": "8.5-9.5s",
                 "dialogue": "Here it is.", "delivery": "Brisk.", "rehook": ""},
            ]}, False, ["D94"]),
        # D103 (gauntlet cycle 8): a 14-word sentence parked in on_screen is a
        # caption in disguise, not display text (playbook §4). The cap is
        # egregious-case (12 words), so "BEFORE | AFTER" still passes clean.
        ("on-screen-paragraph", {**good, "beats": [
            {**good["beats"][0]},
            {**good["beats"][1], "on_screen": "The exact words the presenter "
                                              "says while the result shines in "
                                              "full light today"},
            {**good["beats"][2]},
            {**good["beats"][3]}]}, False, ["D103"]),
        # D111 (gauntlet cycle 11): a demo beat that numbers a single test
        # ("Test 1: ..." spoken + "TEST 1" displayed) with no "Test 2"
        # anywhere is a dangling ordinal — the template prefixes it even for
        # single-test demos. The isolated dialogue is word-budget-safe so only
        # the numbering check fires.
        ("dangling-test-number", {**good, "beats": [
            {**good["beats"][0]},
            {**good["beats"][1]},
            {**good["beats"][2], "dialogue": "Test 1: one pass. Done.",
             "on_screen": "TEST 1"},
            {**good["beats"][3]}]}, False, ["D111"]),
        # D111 control: a script that genuinely numbers two tests passes —
        # the check is about the dangling ordinal, not numbering per se.
        ("numbered-tests-pair", {**good, "beats": [
            {**good["beats"][0]},
            {**good["beats"][1]},
            {**good["beats"][2], "dialogue": "Test 1: this. Test 2: that. "
                                              "Done."},
            {**good["beats"][3]}]}, True, []),
    ]
    return good, cases


AI_DISCLOSURE = ('Disclosure (G6/Q7): on-screen small "AI persona" label from '
                 'FRAME 0, separate element from hook text, top safe zone.')


def good_ai(good):
    """The good fixture on the AI lane: presenter ai + disclosure field +
    caption AI line (D138). Must pass both gates."""
    return {**good, "presenter": "ai", "disclosure": AI_DISCLOSURE,
            "caption": "Test caption.\nmade with an AI persona\n#beautytok"}


def _with_beat(good, i, **kw):
    beats = [dict(b) for b in good["beats"]]
    beats[i] = {**beats[i], **kw}
    return beats


def new_cases(good):
    """Cases for gate rules added in pipeline v2 (RULES.md §66).

    Tuple: (name, script, want_pass, want_msgs[, opts]). opts (optional):
      "only": every failure message in the report must start with this id
              (the case isolates one rule)
      "env":  per-case environment overrides; a None value UNSETS the var
              (e.g. {"VSP_FIXTURE_OK": None} runs gate 2 like production)
    Every new error rule has at least one failing case whose expected message
    contains the rule id, plus pass controls for its allow-paths.
    """
    ai = good_ai(good)
    b = good["beats"]
    cta = {"type": "CTA", "t": "9.0-10.0s", "direction": "Presenter to camera.",
           "on_screen": "", "dialogue": "Part 2 soon.", "delivery": "Brisk.",
           "rehook": ""}
    return [
        # --- AI lane: the good fixture on presenter=ai passes both gates
        ("ai-presenter-good", ai, True, []),
        # D136: social proof the prompt never supplied
        ("d136-unsourced-social-proof", {**good, "beats": _with_beat(
            good, 2, dialogue="Sold out twice. One pass, done.")},
         False, ["D136:"], {"only": "D136"}),
        # D136 allow-path: the prompt supplies the claim
        ("d136-prompt-supplied-proof", {**good,
            "prompt": "test product that sold out twice",
            "beats": _with_beat(good, 2, dialogue="Sold out twice. One pass, done.")},
         True, []),
        # D137: AI persona claims to have used the product
        ("d137-ai-lived-experience", {**ai, "beats": _with_beat(
            ai, 2, dialogue="I tried it for a week. Done.")},
         False, ["D137:"], {"only": "D137"}),
        # D138: presenter=ai without the disclosure field
        ("d138-ai-no-disclosure-field", {k: v for k, v in ai.items()
                                         if k != "disclosure"},
         False, ["D138:"], {"only": "D138"}),
        # D138: presenter=ai without a caption AI line
        ("d138-ai-no-caption-line", {**ai, "caption": "Test caption. #beautytok"},
         False, ["D138:"], {"only": "D138"}),
        # D139: generic engagement bait (the keyword CTA in the fixture is fine)
        ("d139-engagement-bait", {**good, "beats": _with_beat(
            good, 2, dialogue="Tag a friend who needs this.")},
         False, ["D139:"], {"only": "D139"}),
        # D140: more than 5 hashtags
        ("d140-too-many-hashtags", {**good, "caption":
            "Test caption. #beautytok #hairtok #makeuptok #grwm #glowup #lashes"},
         False, ["D140:"], {"only": "D140"}),
        # D140: generic-only hashtags
        ("d140-generic-only-hashtags", {**good,
                                        "caption": "Test caption. #fyp #viral"},
         False, ["D140:"], {"only": "D140"}),
        # D141: guarantee claim the prompt never made
        ("d141-absolute-claim", {**good, "beats": _with_beat(
            good, 2, dialogue="Guaranteed. One pass and done.")},
         False, ["D141:"], {"only": "D141"}),
        # D141 allow-path: the prompt makes the claim
        ("d141-prompt-supplied-claim", {**good,
            "prompt": "test product with a lifetime guarantee",
            "beats": _with_beat(good, 2, dialogue="Guaranteed. One pass and done.")},
         True, []),
        # D144: the D109 refill fragment ("NOBODY MENTIONS FLAW")
        ("d144-overlay-fragment", {**good, "beats": _with_beat(
            good, 0, on_screen="NOBODY MENTIONS FLAW")},
         False, ["D144:"], {"only": "D144"}),
        # D144 (+D17): frame-0 overlay over 3 words
        ("d144-overlay-too-long", {**good, "beats": _with_beat(
            good, 0, on_screen="LOOK AT THIS ONE NOW")},
         False, ["D144:"], {"only": "D144"}),
        # D31: a raw {slot} reached spoken copy
        ("d31-raw-template-slot", {**good, "beats": _with_beat(
            good, 2, dialogue="One pass and {category} is done.")},
         False, ["D31:"], {"only": "D31"}),
        # D73: a 10-word verbal hook (whitespace tokens, like pick_hook)
        ("d73-verbal-hook-over-8", {**good, "hook_stack": [
            {"type": "HOOK", "dialogue":
             "Look at this: one pass, one week, zero regrets, honestly."}]},
         False, ["D73:"], {"only": "D73"}),
        # D93: the same re-hook twice
        ("d93-repeated-rehook", {**good, "beats": _with_beat(
            good, 2, rehook="Here is what it took.")},
         False, ["D93:"], {"only": "D93"}),
        # D146: part-2 CTA with no series_plan
        ("d146-unplanned-part2", {**good, "beats": [dict(x) for x in b] + [cta]},
         False, ["D146:"], {"only": "D146"}),
        # D146 control: the same CTA backed by a series_plan passes
        ("d146-part2-with-series-plan", {**good,
            "beats": [dict(x) for x in b] + [cta],
            "series_plan": {"part": 1, "next": "the week-two test"}},
         True, []),
        # D142 is a WARNING: a fast on-screen card never fails the gate
        ("d142-fast-onscreen-warns-only", {**good, "beats": _with_beat(
            good, 2, on_screen="RESULT AFTER ONE SINGLE PASS: MEASURED, "
                               "TIMED AND REPEATED TWICE")},
         True, []),
        # D151: production gate 2 (no VSP_FIXTURE_OK) rejects FIXTURE reels
        ("d151-fixture-reels-rejected", good, False, ["D151:"],
         {"only": "D151", "env": {"VSP_FIXTURE_OK": None}}),
    ]


# ------------------------------------------------------------ unit checks
# In-process checks for contracts a pipeline run cannot reach (e.g. a brief
# make_shotlist never emits). Each returns a list of problems ([] = ok).

def _unit_registry_shape():
    from vsp import gates, rules
    probs = []
    seen = set()
    for r in rules.REGISTRY:
        if r.stage not in rules.STAGES or r.severity not in rules.SEVERITIES:
            probs.append(f"{r.id}: bad stage/severity {r.stage}/{r.severity}")
        if (r.stage, r.id) in seen:
            probs.append(f"{r.id}: duplicate id in stage {r.stage}")
        seen.add((r.stage, r.id))
        if not callable(r.check):
            probs.append(f"{r.id}: check not callable")
    if [r.check.legacy for r in rules.LEGACY_SCRIPT_RULES] != list(gates.LEGACY_GATE1):
        probs.append("gate-1 legacy rules are not the legacy checks in legacy order")
    if [r.check.legacy for r in rules.LEGACY_BUNDLE_RULES] != list(gates.LEGACY_GATE2):
        probs.append("gate-2 legacy rules are not the legacy checks in legacy order")
    for stage in rules.STAGES:
        ids = [r.id for r in rules.rules_for(stage)]
        n = len(rules.LEGACY_IDS[stage])
        if tuple(ids[:n]) != rules.LEGACY_IDS[stage]:
            probs.append(f"{stage}: legacy rules must run first")
    if gates.REGISTRY is not rules.REGISTRY:
        probs.append("vsp.gates.REGISTRY is not vsp.rules.REGISTRY")
    return probs


def _unit_deliverable_in_sync():
    import make_shotlist
    from vsp import gates
    if make_shotlist.DELIVERABLE != gates.DELIVERABLE_BLOCK:
        return ["make_shotlist.DELIVERABLE differs from the gate's canonical "
                "copy — the DELIVERABLE block is sacred"]
    return []


def _unit_deliverable_strengthened():
    import make_shotlist
    from vsp import gates
    good, _ = legacy_cases()
    bundle, _, _ = make_shotlist.build_bundle(good, refs=[
        "- https://www.instagram.com/reel/UNIT-1/ (@unit, 1 likes) — unit"])
    probs = []
    if "DELIVERABLE block missing/altered" in gates.gate2(bundle, good):
        probs.append("intact DELIVERABLE block rejected")
    tampered = bundle.replace("no trims, no pre-cutting",
                              "light trims ok, no pre-cutting")
    if "DELIVERABLE block missing/altered" not in gates.gate2(tampered, good):
        probs.append("altered DELIVERABLE tail passed gate 2")
    return probs


def _unit_d138_brief_label():
    import make_shotlist
    from vsp import gates
    good, _ = legacy_cases()
    ai = good_ai(good)
    refs = ["- https://www.instagram.com/reel/UNIT-1/ (@unit, 1 likes) — unit"]
    bundle, _, _ = make_shotlist.build_bundle(ai, refs=refs)
    probs = []
    if gates.gate2(bundle, ai):
        probs.append(f"AI brief with the label failed gate 2: {gates.gate2(bundle, ai)}")
    stripped = "\n".join(ln for ln in bundle.split("\n")
                         if '"AI persona" label' not in ln)
    errs = gates.gate2(stripped, ai)
    if errs != ["D138: AI-persona label instruction missing from brief"]:
        probs.append(f"label-less AI brief: expected only the D138 message, got {errs}")
    if gates.gate2(stripped, good):   # human presenter: no label required
        probs.append("human brief without an AI label failed gate 2")
    return probs


def _unit_warn_never_fails():
    from vsp import gates
    good, _ = legacy_cases()
    s = {**good, "beats": _with_beat(good, 2, on_screen=(
        "RESULT AFTER ONE SINGLE PASS: MEASURED, TIMED AND REPEATED TWICE"))}
    f = gates.gate1_findings(s)
    probs = []
    if not any(x["rule"] == "D142" and x["severity"] == "warn" for x in f):
        probs.append("D142 warning not reported by gate1_findings")
    if gates.gate1(s):
        probs.append(f"a warning failed gate 1: {gates.gate1(s)}")
    return probs


def _unit_legacy_first():
    from vsp import gates
    good, _ = legacy_cases()
    s = {**good, "beats": _with_beat(good, 2, dialogue=(
        "Sold out twice. " + " ".join(["word"] * 12)))}
    msgs = gates.gate1(s)
    if not (msgs and msgs[0].startswith("D43") and msgs[-1].startswith("D136")):
        return [f"legacy messages must precede v2 messages, got {msgs}"]
    return []


def _unit_check_crash_fails_closed():
    from vsp import rules
    bad = {"prompt": "x", "hook_stack": "not-a-list", "beats": [{"t": 5}],
           "caption": 7, "niche": "x"}
    try:
        f = rules.evaluate("script", bad)
    except Exception as e:  # noqa: BLE001
        return [f"evaluate raised on a malformed script: {e!r}"]
    if not any(x["severity"] == "error" for x in f):
        return ["malformed script produced no error finding"]
    return []


def unit_cases():
    return [("registry-shape", _unit_registry_shape),
            ("deliverable-block-in-sync", _unit_deliverable_in_sync),
            ("deliverable-check-strengthened", _unit_deliverable_strengthened),
            ("d138-brief-label-instruction", _unit_d138_brief_label),
            ("d142-warning-never-fails", _unit_warn_never_fails),
            ("legacy-messages-first", _unit_legacy_first),
            ("crashing-check-fails-closed", _unit_check_crash_fails_closed)]


def all_cases():
    good, cases = legacy_cases()
    return good, cases + new_cases(good)
