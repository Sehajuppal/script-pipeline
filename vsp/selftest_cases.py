"""Self-test fixtures — the 17 legacy gate cases, moved verbatim from
pipeline.py (d8f8759). Each case: (name, script, want_pass, want_msgs).

Append new cases for new gate rules to NEW_CASES (never edit or delete a
legacy case: every legacy case must keep failing with its original message).
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


def new_cases(good):
    """Cases for gate rules added in pipeline v2 (D136+). Registered by
    vsp/rules.py owners; each must fail with its rule id in the message."""
    return []


def all_cases():
    good, cases = legacy_cases()
    return good, cases + new_cases(good)
