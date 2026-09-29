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
        # D138: a product name containing "AI" is not a disclosure line
        ("d138-ai-product-name-is-not-disclosure", {**ai, "caption":
            "The AI note taker, tested.\n#beautytok"},
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


ROUTE_KEYS = ("sanitized_prompt", "price", "concept", "niche", "fit",
              "category", "complexity", "votes", "agreement", "confidence",
              "recommended_presenter", "presenter_reason",
              "recommended_formats", "lane_warnings", "input_errors",
              "input_warnings")


def _unit_router_contract():
    import json
    import os
    from vsp import config
    from vsp.router import route
    prompts = []
    golden = os.path.join(config.REPO, "evals", "golden.jsonl")
    if os.path.isfile(golden):
        with open(golden, encoding="utf-8") as f:
            prompts = [json.loads(ln)["prompt"] for ln in f if ln.strip()
                       and not ln.startswith("//")]
    probs = []
    edge = [None, "", "   ", "x" * 301, "a {limited} edition bottle",
            "tiktok shop LED lamp"]
    for p in prompts + edge:
        for pres in (None, "ai"):
            try:
                r = route(p, presenter=pres, fmt="review", pack=False)
            except Exception as e:  # noqa: BLE001
                probs.append(f"route({p!r}) raised {type(e).__name__}: {e}")
                continue
            missing = [k for k in ROUTE_KEYS if k not in r]
            if missing:
                probs.append(f"route({p!r}) missing keys {missing}")
            if not 0.0 <= r.get("agreement", -1) <= 1.0 or \
                    r.get("recommended_presenter") not in ("ai", "human"):
                probs.append(f"route({p!r}) bad agreement/presenter")
    if route("", pack=False)["input_errors"] != ["empty prompt"]:
        probs.append("empty prompt not reported as an input error")
    if not route("x" * 301, pack=False)["input_errors"]:
        probs.append("301-char prompt not reported as an input error")
    r = route("a {limited} edition bottle", pack=False)
    if "{" in r["sanitized_prompt"] or not r["input_warnings"]:
        probs.append("braces not stripped with a warning")
    r = route("tiktok shop LED lamp", presenter="ai", pack=False)
    if not any("TikTok Shop" in w for w in r["lane_warnings"]):
        probs.append("TikTok Shop x AI lane warning missing")
    r = route("ergonomic office chair", pack=False)
    if r["niche"] == "beauty":
        probs.append("'chair' routed to beauty (substring hijack not outvoted)")
    return probs


def _unit_research_contract():
    import json
    import os
    import tempfile
    from datetime import datetime, timedelta, timezone
    from vsp import research as R
    probs = []
    now = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
    pack = {"generated_at": (now - timedelta(hours=50)).isoformat(),
            "sources": {}, "reels_total": 3, "schema_version": 2,
            "niche_map": {"beauty": ["fashion-beauty"]},
            "niche_hooks": {"fashion-beauty": [
                {"category": "comment-bait", "times_seen": 9},     # unmapped
                {"category": "grwm-hook", "times_seen": 5}]},
            "fresh_hook_lines": [
                {"hook": "(visual open, bathroom mirror)", "niche": "fashion-beauty"},
                {"hook": "null", "niche": "fashion-beauty"},
                {"hook": "POV: your lashes finally stayed on", "niche": "fashion-beauty"},
                {"hook": "Hood Cinema!", "niche": "comedy"}]}
    if R.validate_pack(pack):
        probs.append(f"valid v2 pack rejected: {R.validate_pack(pack)}")
    if not R.validate_pack({"generated_at": "x", "reels_total": -1}):
        probs.append("invalid pack accepted")
    if R.live_hook_family(pack, "beauty") != "transformation":
        probs.append("live_hook_family did not walk past an unmapped rank-0 "
                     "category")
    lines = [x["hook"] for x in R.niche_fresh_lines(pack, "beauty")]
    if lines != ["POV: your lashes finally stayed on"]:
        probs.append(f"niche_fresh_lines kept descriptions/off-niche lines: {lines}")
    d = tempfile.mkdtemp(prefix="vsp_unit_pack_")
    try:
        path = os.path.join(d, "pack.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(pack, f)
        got, meta = R.load_pack(path, now=now)
        if got is None or not meta["stale"] or len(meta["sha256"] or "") != 64:
            probs.append(f"load_pack meta wrong: {meta}")
        with open(path, "w", encoding="utf-8") as f:
            f.write("{not json")
        got, meta = R.load_pack(path, now=now)
        if got is not None or not meta["errors"]:
            probs.append("corrupt pack not reported")
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)
    return probs


# ------------------------------------ WS-EVAL: synthetic v2.1 bundle (gate 2)
# A complete v2.1 brief written from docs/CREATIVE-PLAN.md §1.4 (never from
# make_shotlist): every legacy gate-2 rule passes, every shot carries its
# '- Shot type:' line, the four new sections are present. Unit checks derive
# one violation per D157 / D159 / D160 clause by exact substring swaps.

UNIT_REEL = "- https://www.instagram.com/reel/UNIT-1/ (@unit, 1 likes) — unit"
V21_IDENTITY = ("a photorealistic AI woman in her late 20s with short dark hair, "
                "wearing a plain gray crewneck")


def v21_script(good, ai=False):
    s = creative_fixture(good_ai(good) if ai else good)
    if ai:
        s["persona"] = {"name": "Unit", "identity": V21_IDENTITY,
                        "voice": "natural-prosody synthetic voice, disclosed"}
    return s


def v21_bundle(s):
    """The synthetic v2.1 bundle for v21_script(good, ai)."""
    from vsp.gates import DELIVERABLE_BLOCK
    ai = s.get("presenter") == "ai"
    idn = V21_IDENTITY + ". " if ai else ""
    rf = ("- REAL FOOTAGE REQUIRED: the on-camera result proves the claim — "
          "do not generate\n" if ai else "")
    L = [
        "# Production bundle — test product",
        f"niche: beauty | presenter: {s.get('presenter')} | format: demo | "
        f"duration: 10s | hook family: transformation", "",
        "## Shot list",
        "### Shot 1 (0.0–0.5s) — VISUAL TRIGGER",
        "- Camera: Frame 0 mid-action: hands on the test product, before and after split.",
        "- Shot type: hook-hands-mid-action · CU · push-in · hook · energy 5 · AI risk high",
        "- On-screen text: BEFORE | AFTER", "",
        "### Shot 2 (0.5–3.0s) — VERBAL HOOK + LOCK",
        "- Camera: Medium close-up, presenter to camera, eye-level, handheld.",
        "- Shot type: talking-head-mcu · MCU · handheld · hook · energy 4 · AI risk med",
        '- Dialogue/VO: "This is the after."', "",
        "### Shot 3 (3.0–6.0s) — DEMO BEAT",
        "- Camera: Overhead, hands demo the test product, the result forming, slow push-in.",
        "- Shot type: overhead-hands-demo · MS · push-in · demo · energy 3 · AI risk high",
        rf + '- Dialogue/VO: "One pass and it is done."', "",
        "### Shot 4 (6.0–9.0s) — COMMENT BAIT",
        "- Camera: Presenter to camera with the product, handheld, keyword on screen.",
        "- Shot type: face-reaction-product · MCU · handheld · cta · energy 3 · AI risk med",
        '- Dialogue/VO: "Hit follow, comment TEST and it is yours."', "",
        "### Shot 5 (9.0–10.0s) — LOOP",
        "- Camera: Close-up, hands back on the test product: the frame-0 framing.",
        "- Shot type: loop-return-frame · CU · pull-out · b-roll · energy 4 · AI risk low",
        "- Loop: returns to frame 0's framing and motion.", "",
        "## Antigravity brief", "",
        "> The SHOT PROMPTS are the generation instructions, one per shot.", ""]
    if ai:
        L += ["## PRESENTER — identity lock",
              f"{V21_IDENTITY} — use this exact description in every shot "
              f"prompt that shows her face.", "",
              "## AI DISCLOSURE — frame-0 label (required)",
              'On-screen small "AI persona" label from FRAME 0, top safe zone, '
              'minimum 2 seconds, separate from hook text.', ""]
    sfx = ("Vertical phone footage. Single continuous shot, no scene cuts. "
           "No on-screen text, captions, logos or watermarks.")
    L += ["## SHOT PROMPTS (self-contained — generate each shot from its own prompt only)",
          "#### Prompt — Shot 1 (0.0–0.5s)",
          f"VISUAL PROMPT: Close-up, high angle, slow push-in: hands on the test "
          f"product mid-pass, bathroom counter, window light. {sfx}",
          "AUDIO: the real product sound.", "",
          "#### Prompt — Shot 2 (0.5–3.0s)",
          f"VISUAL PROMPT: {idn}Medium close-up, eye-level, handheld: the presenter "
          f"looks into the lens and says: this is the after. {sfx}",
          "AUDIO: voiceover for this shot, audio only.", "",
          "#### Prompt — Shot 3 (3.0–6.0s)",
          f"VISUAL PROMPT: Overhead, slow push-in: hands only, face out of frame, "
          f"one pass with the test product. {sfx}",
          "AUDIO: the real product sound.", "",
          "#### Prompt — Shot 4 (6.0–9.0s)",
          f"VISUAL PROMPT: {idn}Medium close-up, handheld: the presenter holds "
          f"the test product toward the lens and smiles. {sfx}",
          "AUDIO: voiceover for this shot, audio only.", "",
          "#### Prompt — Shot 5 (9.0–10.0s)",
          f"VISUAL PROMPT: Close-up, high angle, slow pull-out: hands on the test "
          f"product, the same framing as shot 1. {sfx}",
          "AUDIO: the real product sound.", "",
          "## ALTERNATE OPENINGS — variant cuts"]
    for v in s.get("hook_variants") or []:
        if v.get("is_primary"):
            continue
        L += [f"#### Alt opening {v['id']} (0.0–3.0s) — {v['archetype']} / "
              f"{v['visual_type']}",
              f"VISUAL PROMPT: {v['visual'].replace('Frame 0: ', '')} {sfx}",
              f"VO: {v['verbal']}", ""]
    L += [
          "## SHOOT PLAN — setups, props, B-roll",
          "- Setup 1 (bathroom counter, window key light): shots 1, 3, 5.",
          "- Setup 2 (presenter, eye-level): shots 2, 4.",
          "- Props: the test product, a towel. B-roll first while the product is clean.", "",
          "## VOICEOVER — separate audio track",
          "AUDIO ONLY. Do not render any of these words as on-screen text.",
          "[0.5-3.0s] This is the after.",
          "Voice spec: " + ("natural-prosody synthetic voice, disclosed; never "
                            "claims to be human." if ai else
                            "the creator's own voice, recorded on the day."), "",
          "## STYLE",
          "UGC demo, beauty niche. 9:16 vertical. Hard cuts. Max 3 words per card.", "",
          "## CREATIVE DIRECTION — vibe & tone",
          "- Vibe: raw-ugc — lo-fi phone footage, handheld, natural light.",
          "- Tone: warm (allowed: warm, confident, calm).",
          "- Music: none in the master. Add it at upload from each platform's "
          "commercial library: TikTok Commercial Music Library (CML), Meta Sound "
          "Collection, YouTube Audio Library.",
          "- Search the library for: upbeat acoustic, bright pop 100 bpm, happy ukulele.",
          "- No AI music on TikTok commercial content.", "",
          "## NEGATIVE PROMPT — never render",
          "Warped faces, extra fingers, garbled text, watermarks or logos.", "",
          "## Reference reels (human review — the quality bar)",
          UNIT_REEL, "",
          "## Render spec",
          '9:16 vertical, 1080x1920, 30fps, H.264 mp4. Files: test-product-master.mp4 '
          '+ test-product-words.json (word-level timings as {"words": [{"word": str, '
          '"start": float_seconds, "end": float_seconds}], "duration_s": float}).', "",
          "## Do NOT",
          "Do NOT burn in captions/subtitles (Marlowe's stage). No watermarks or logos.", "",
          "## DELIVERABLE (standing)", DELIVERABLE_BLOCK, "",
          "## POSTING & DISCOVERY",
          "- Primary keyword: test product (spoken by 3.0 s, caption line 1, #testproduct).",
          "- TikTok: Test product: one pass and it is done.", "",
          "## Caption + hashtags (post as-is)", s.get("caption", ""), ""]
    return "\n".join(L)


def _swap(text, old, new, count=1):
    if old not in text:
        raise AssertionError(f"unit fixture drift: {old[:60]!r} not in the bundle")
    return text.replace(old, new, count)


def _only_rule(bundle, script, rid):
    """[] when gate 2 fails with messages that all start with rid."""
    from vsp import gates
    errs = gates.gate2(bundle, script)
    if not errs:
        return [f"{rid}: the violation passed gate 2"]
    stray = [e for e in errs if not e.startswith(rid + ":")]
    return [f"{rid}: stray messages {stray}"] if stray else []


PAYOFF_SHOT4 = ("### Shot 4 (6.0–9.0s) — COMMENT BAIT",
                "### Shot 4 (6.0–9.0s) — PAYOFF")


def _ai_payoff_result(b):
    """Shot 4 of the AI brief becomes a product-only PAYOFF result shot
    (no face, no identity lock) without a REAL FOOTAGE line."""
    b = _swap(b, *PAYOFF_SHOT4)
    b = _swap(b, "- Camera: Presenter to camera with the product, handheld, keyword on screen.",
              "- Camera: Close-up of the finished result on the counter, slow push-in.")
    b = _swap(b, "face-reaction-product · MCU · handheld · cta",
              "result-first-reveal · MCU · push-in · payoff")
    return _swap(b, f"VISUAL PROMPT: {V21_IDENTITY}. Medium close-up, handheld: the "
                    f"presenter holds the test product toward the lens and smiles.",
                 "VISUAL PROMPT: Close-up, slow push-in: the finished result on the counter.")


def _v21_variants():
    """(name, presenter ai?, rule id, fn(bundle) -> bundle) — one violation
    per D157 / D159 / D160 clause of the synthetic v2.1 bundle."""
    S3 = "- Shot type: overhead-hands-demo · MS · push-in · demo · energy 3 · AI risk high"
    return [
        ("d157-untyped-shot", False, "D157", lambda b: _swap(b, S3 + "\n", "")),
        ("d157-bad-shot-type-field", False, "D157", lambda b: _swap(
            b, "MS · push-in · demo", "MS · zoom · demo")),
        ("d157-frame0-purpose-cta", False, "D157", lambda b: _swap(
            b, "CU · push-in · hook · energy 5", "CU · push-in · cta · energy 5")),
        ("d157-frame0-talking-head", False, "D157", lambda b: _swap(
            b, "hook-hands-mid-action · CU", "talking-head-mcu · CU")),
        ("d157-frame0-no-subject", False, "D157", lambda b: _swap(_swap(_swap(
            b, "Frame 0 mid-action: hands on the test product, before and after split.",
            "A wide establishing view of the room, hands in frame."),
            "hook-hands-mid-action · CU", "establishing-ws · CU"),
            "- On-screen text: BEFORE | AFTER", "- On-screen text: LOOK")),
        ("d157-no-human-by-3s", False, "D157", lambda b: _swap(_swap(_swap(_swap(
            b, "Frame 0 mid-action: hands on the test product, before and after split.",
            "Frame 0: the test product alone, the result shown."),
            "hook-hands-mid-action · CU", "result-first-reveal · CU"),
            "Medium close-up, presenter to camera, eye-level, handheld.",
            "Close-up of the result, slow push-in."),
            "talking-head-mcu · MCU · handheld", "feature-callout-hero · MCU · push-in")),
        ("d157-three-same-scale", False, "D157", lambda b: _swap(
            b, "overhead-hands-demo · MS", "overhead-hands-demo · MCU")),
        ("d157-long-static-shot", False, "D157", lambda b: _swap(_swap(_swap(
            b, "### Shot 3 (3.0–6.0s)", "### Shot 3 (3.0–6.6s)"),
            "### Shot 4 (6.0–9.0s)", "### Shot 4 (6.6–9.0s)"),
            "MS · push-in · demo", "MS · static · demo")),
        ("d157-ai-proof-shot-not-real-footage", True, "D157", lambda b: _swap(
            b, "- REAL FOOTAGE REQUIRED: the on-camera result proves the claim — "
               "do not generate\n", "")),
        ("d157-ai-payoff-result-not-real-footage", True, "D157", _ai_payoff_result),
        ("d157-no-loop-at-15s", False, "D157", lambda b: _swap(_swap(_swap(
            b, "loop-return-frame · CU", "end-card-hero · CU"),
            "- Loop: returns to frame 0's framing and motion.\n", ""),
            "hands back on the test product: the frame-0 framing.",
            "the test product end card.")),
        ("d157-new-section-forbidden-phrase", False, "D157", lambda b: _swap(
            b, "- Props: the test product, a towel.",
            "- Props: the FIXTURE product, a towel.")),
        ("d159-no-upload-lane", False, "D159", lambda b: _swap(
            b, "- Music: none in the master. Add it at upload from each platform's "
               "commercial library: TikTok Commercial Music Library (CML), Meta Sound "
               "Collection, YouTube Audio Library.", "- Music: a bright acoustic bed.")),
        ("d159-named-track-with-artist", False, "D159", lambda b: _swap(
            b, "- Tone: warm", '- Track: "Summer Nights" by The Examples.\n- Tone: warm')),
        ("d159-quoted-title", False, "D159", lambda b: _swap(
            b, "- Tone: warm", '- Track: "Golden Hour".\n- Tone: warm')),
        ("d159-ai-music-on-tiktok", False, "D159", lambda b: _swap(
            b, "- No AI music on TikTok commercial content.",
            "- TikTok: use an AI-generated music bed (Suno paid plan).")),
        ("d159-music-baked-into-master", False, "D159", lambda b: _swap(
            b, "- Tone: warm", "- Mix the music into the master at -12 dB.\n- Tone: warm")),
        ("d160-render-exactly", False, "D160", lambda b: _swap(
            b, "AUDIO: the real product sound.\n\n#### Prompt — Shot 2",
            "ON-SCREEN TEXT (render exactly, bold sans, high contrast): BEFORE | AFTER\n"
            "AUDIO: the real product sound.\n\n#### Prompt — Shot 2")),
        ("d160-onscreen-text-styling", False, "D160", lambda b: _swap(
            b, "one pass with the test product.",
            "one pass with the test product. Any on-screen text is bold sans, high contrast.")),
        ("d160-quoted-dialogue", False, "D160", lambda b: _swap(
            b, "looks into the lens and says: this is the after.",
            'looks into the lens: "This is the after."')),
        ("d160-identity-lock-on-product-shot", True, "D160", lambda b: _swap(
            b, "VISUAL PROMPT: Close-up, high angle, slow push-in: hands on the test "
               "product mid-pass", f"VISUAL PROMPT: {V21_IDENTITY}. Close-up, high "
               f"angle, slow push-in: hands on the test product mid-pass")),
    ]


def _unit_v21_bundle_passes():
    """The synthetic v2.1 bundles (human + AI) pass gate 2, and the parser
    sees 5 typed shots, the loop, the AI proof shot and the identity lock."""
    from vsp import gates, rules
    good, _ = legacy_cases()
    probs = []
    for ai in (False, True):
        s = v21_script(good, ai)
        b = v21_bundle(s)
        errs = gates.gate2(b, s)
        if errs:
            probs.append(f"synthetic v2.1 bundle (ai={ai}) failed gate 2: {errs}")
        blocks = rules.shot_blocks(b)
        if [x["n"] for x in blocks if x["typed"]] != ["1", "2", "3", "4", "5"]:
            probs.append(f"shot parser saw {[(x['n'], x['type_errors']) for x in blocks]}")
        if ai and (rules.identity_lock(s, b) != V21_IDENTITY
                   or not blocks[2]["real_footage"]):
            probs.append("identity lock / REAL FOOTAGE line not parsed")
        sig = [rules.shot_signals(x) for x in blocks]
        if [x["face"] for x in sig] != [False, True, False, True, False] or \
                [x["hands"] for x in sig] != [True, False, True, False, True]:
            probs.append(f"face/hands signals {sig}")
    return probs


def _unit_v21_violations():
    """Each D157 / D159 / D160 clause violation fails gate 2 with that rule
    alone (message starts with the id)."""
    good, _ = legacy_cases()
    base = {ai: (v21_script(good, ai), v21_bundle(v21_script(good, ai)))
            for ai in (False, True)}
    probs = []
    for name, ai, rid, fn in _v21_variants():
        s, b = base[ai]
        try:
            bad = fn(b)
        except AssertionError as e:
            probs.append(f"{name}: {e}")
            continue
        probs += [f"{name}: {p}" for p in _only_rule(bad, s, rid)]
    return probs


def _unit_v21_silent_on_legacy():
    """Legacy bundles (no '- Shot type:' line, no v2.1 section) keep their
    outcome: the same brief with the v2.1 lines stripped and the legacy
    'render exactly' / quoted AUDIO / identity-everywhere prompts passes gate
    2 with no D157/D159/D160 finding; the real make_shotlist brief of the
    legacy good fixture carries no v2.1 finding either unless it is a v2.1
    brief."""
    import make_shotlist
    from vsp import gates, rules
    good, _ = legacy_cases()
    probs = []
    for ai in (False, True):
        s = v21_script(good, ai)
        b = v21_bundle(s)
        keep = []
        skip = False
        for ln in b.split("\n"):
            if ln.startswith("## "):
                skip = ln[3:].upper().startswith(rules.V21_SECTIONS)
            if skip or ln.startswith(("- Shot type:", "- REAL FOOTAGE", "- Loop:")):
                continue
            keep.append(ln)
        legacy = "\n".join(keep)
        legacy = legacy.replace(
            "AUDIO: the real product sound.",
            'ON-SCREEN TEXT (render exactly, bold sans, high contrast): TEST\n'
            'AUDIO (voiceover): "One pass and it is done."')
        if ai:
            legacy = legacy.replace("VISUAL PROMPT: Close-up",
                                    f"VISUAL PROMPT: {V21_IDENTITY}. Close-up")
        f = [x for x in gates.gate2_findings(legacy, s)
             if x["rule"] in ("D157", "D159", "D160")]
        if f or gates.gate2(legacy, s):
            probs.append(f"legacy-format brief (ai={ai}): {gates.gate2(legacy, s)}")
    refs = [UNIT_REEL]
    for sc in (good, good_ai(good)):
        bundle, _, _ = make_shotlist.build_bundle(sc, refs=refs)
        if not rules.SHOT_TYPE_MARK.search(bundle) and \
                rules.section(bundle, "CREATIVE DIRECTION") is None:
            f = [x for x in gates.gate2_findings(bundle, sc)
                 if x["rule"] in ("D157", "D159", "D160")]
            if f:
                probs.append(f"legacy make_shotlist brief has v2.1 findings: {f}")
    return probs


# ------------------------------ WS-EVAL: precision corpus (false-fail probes)
# Contract-valid or ordinary wording that a heuristic must NOT fail (found
# by the semantic review of the evaluator diff), with positive controls.
D158_INNOCUOUS = ("In a hurry, one pass and it is done.",
                  "The stain is almost gone. One pass.",
                  "Dry time was 40 min, now 15 min.",
                  "Made for mornings with limited time.",
                  "Everyone is getting this step wrong.",
                  "These patches act fast. One pass.",
                  "The challenge ends in 30 days.",
                  "Take half off the ends first.",
                  "Just use the code on the lid.")
D158_FAKE = ("Hurry, only 3 left!", "Limited-time offer. One pass.",
             "Sale ends Sunday. One pass.", "Use code SAVE10 at checkout.",
             "Was $40, now $25. One pass.")
D159_OK_LINES = (
    "- AI music: allowed only for Instagram and YouTube organic posts; "
    "blocked on TikTok commercial content.",
    "- TikTok lane: Commercial Music Library; never the general Sounds "
    "library, another user's original sound or AI-generated music.",
    '- Showmanship: one "reveal pause" right before the payoff.',
    '- Text cards: bold sans, max 3 words, e.g. "BEFORE | AFTER".',
    "- Add music at upload only, never mixed into the master.",
    '- Search the library for: "upbeat acoustic".')
D160_OK_LINES = ("On-screen text is an edit overlay, never generated in-frame.",
                 "Render in 9:16 vertical with no captions or subtitles.",
                 "Generate a clean plate: no text overlay in frame.",
                 "Leave the top third clear for on-screen text in the edit.",
                 "Text on screen: none (added in the edit).")


def _unit_precision_corpus():
    """Ordinary / hygienic wording passes D154-D160; the true forms fail."""
    from vsp import gates
    good, _ = legacy_cases()
    probs = []
    for line in D158_INNOCUOUS:
        errs = gates.gate1({**good, "beats": _with_beat(good, 2, dialogue=line)})
        if errs:
            probs.append(f"D158 false fail on {line!r}: {errs}")
    for line in D158_FAKE:
        errs = gates.gate1({**good, "beats": _with_beat(good, 2, dialogue=line)})
        if not any(e.startswith("D158:") for e in errs):
            probs.append(f"D158 missed {line!r}: {errs}")
    c, cai = creative_fixture(good), creative_fixture(good_ai(good))
    for note in ("Never: general Sounds library, another user's original sound, "
                 "AI-generated music (Music Terms endorsement clause).",
                 "AI-generated music is not allowed on TikTok commercial content."):
        d = json_copy(c["direction"])
        d["music"]["licensing"]["tiktok"]["note"] = note
        if gates.gate1({**c, "direction": d}):
            probs.append(f"D156 false fail on TikTok note {note[:40]!r}")
    for spec, want in (("Natural-prosody synthetic voice, disclosed as AI; it should "
                        "sound like a real person talking to a friend.", True),
                       ("Synthetic voice, disclosed. I'm a real person.", False)):
        d = json_copy(cai["direction"])
        d["voice"]["spec"] = spec
        if (not gates.gate1({**cai, "direction": d})) != want:
            probs.append(f"D156 voice spec {spec[-30:]!r}: want pass={want}")
    for fld, obj in (("hook_variants", _hv(c, 1, verbal="Stop skipping the 20 pounds test.",
                                           overlay="")),
                     ("discovery", _dsc(c, "tiktok", caption="Test product: holds 50 "
                                        "pounds.\n#testproduct #beautytok"))):
        if gates.gate1({**c, fld: obj}):
            probs.append(f"{fld}: a weight ('pounds') read as a price")
    s = v21_script(good, False)
    b = v21_bundle(s)
    anchor = "- No AI music on TikTok commercial content."
    for ln in D159_OK_LINES:
        errs = gates.gate2(_swap(b, anchor, anchor + "\n" + ln), s)
        if errs:
            probs.append(f"D159 false fail on {ln[:40]!r}: {errs}")
    p1 = "AUDIO: the real product sound.\n\n#### Prompt — Shot 2"
    for ln in D160_OK_LINES:
        errs = gates.gate2(_swap(b, p1, ln + "\n" + p1), s)
        if errs:
            probs.append(f"D160 false fail on {ln!r}: {errs}")
    return probs


def _unit_v21_payoff_and_frame0():
    """The AI persona's own PAYOFF shot (face) needs no REAL FOOTAGE line; a
    research frame-0 shot typed 'demo' is a valid opener; a text-first
    opener carries the subject in its on-screen card."""
    from vsp import gates
    good, _ = legacy_cases()
    probs = []
    sa = v21_script(good, True)
    ba = _swap(_swap(v21_bundle(sa), *PAYOFF_SHOT4),
               "face-reaction-product · MCU · handheld · cta",
               "talking-head-product-in-hand · MCU · push-in · payoff")
    if gates.gate2(ba, sa):
        probs.append(f"persona PAYOFF shot forced to real footage: {gates.gate2(ba, sa)}")
    s = v21_script(good, False)
    b = _swap(v21_bundle(s), "hook-hands-mid-action · CU · push-in · hook",
              "product-operating-cu · CU · push-in · demo")
    if gates.gate2(b, s):
        probs.append(f"frame 0 typed 'demo' rejected: {gates.gate2(b, s)}")
    adv = {**s, "prompt": "why your hooks fail"}
    b = _swap(_swap(_swap(v21_bundle(adv),
                          "- Camera: Frame 0 mid-action: hands on the test product, "
                          "before and after split.",
                          "- Camera: Frame 0 mid-action: creator hands mid-gesture, "
                          "text overlay already up."),
                    "hook-hands-mid-action · CU · push-in · hook",
                    "text-card-over-motion · CU · push-in · hook"),
              "- On-screen text: BEFORE | AFTER", "- On-screen text: HOOKS FAIL")
    errs = [e for e in gates.gate2(b, adv) if e.startswith("D157")]
    if errs:
        probs.append(f"text-first frame 0 with the subject on the card rejected: {errs}")
    return probs


def _unit_repair_with_creative_keys():
    """Stage-6 timing relayout still repairs a script that carries a
    direction (D156 compares energy_curve count + order, not windows)."""
    import json
    import re
    import viral_script_maker as vsm
    from vsp import gates, repair
    base = json.loads(json.dumps(vsm.generate("electric milk frother", presenter="human",
                                              fmt="demo", duration=30, seed=1)))
    b = base["beats"][3]
    m = re.findall(r"\d+(?:\.\d+)?", b["t"])
    b["t"] = f"{float(m[0]) + 1.0:.1f}-{float(m[1]):.1f}s"
    probs = []
    if not gates.gate1(base):
        return ["fixture drift: the nudged window no longer fails gate 1"]
    for label, s in (("legacy", base),
                     ("with direction", {**base, "direction": creative_direction(base)})):
        s2, log, ok = repair.repair(json.loads(json.dumps(s)), gates.gate1, max_rounds=3)
        if not ok or gates.gate1(s2):
            probs.append(f"repair {label}: passed={ok} {gates.gate1(s2)[:2]}")
    return probs


# ------------------------------------------ WS-EVAL: rubric / eval / schema
LEGACY_RUBRIC = (  # R01-R20 (id, tier, weight, audit) — frozen, never edited
    ("R01", "E", 3, False), ("R02", "E", 3, False), ("R03", "E", 3, False),
    ("R04", "I", 2, False), ("R05", "E", 3, False), ("R06", "E", 3, False),
    ("R07", "E", 3, False), ("R08", "I", 2, False), ("R09", "I", 2, False),
    ("R10", "I", 2, False), ("R11", "I", 2, False), ("R12", "O", 1, True),
    ("R13", "I", 2, False), ("R14", "O", 1, False), ("R15", "I", 2, True),
    ("R16", "E", 3, False), ("R17", "O", 1, True), ("R18", "I", 2, False),
    ("R19", "I", 2, False), ("R20", "O", 1, False))
CREATIVE_AUDIT = ("R23", "R26", "R27", "R28")


def strong_creative_fixture(good):
    """The good fixture rewritten so that every R21-R28 creative check
    passes: the keyword 'test product' is spoken + on screen by 3.0 s, in
    caption line 1 and a hashtag; four strong, diverse, payoff-compatible
    openings (the evaluator's own hook scorer: A 78, B 65, C 73, D 64)."""
    hook = "Test product: the one step people skip."
    s = {**good, "hook_stack": [{"type": "HOOK", "dialogue": hook}],
         "caption": "Test product: the one step people skip.\n#testproduct #beautytok",
         "beats": [dict(b) for b in good["beats"]]}
    s["beats"][0]["on_screen"] = "TEST PRODUCT"
    s["beats"][2] = {**s["beats"][2], "type": "PAYOFF",
                     "dialogue": "Verdict: the test product works in one pass."}
    s["direction"] = creative_direction(s)
    hv = creative_variants(s)
    hv[0].update(verbal=hook, overlay="TEST PRODUCT", archetype="curiosity-gap",
                 visual_type="product-in-action", caption_line=hook.split(":")[0])
    hv[2].update(overlay="REALLY WORK", visual_type="text-first")
    s["hook_variants"] = hv
    s["discovery"] = creative_discovery(s)
    return s


def _unit_rubric_creative():
    """R01-R20 unchanged; R21-R28 fail on absent keys (R28 scores the
    script's own openings), pass on the strong fixture; R23 is audit-only
    and ignores the variants' self-reported score / features."""
    from vsp import gates, rubric
    good, _ = legacy_cases()
    probs = []
    table = {c[0]: (c[2], c[3], c[4]) for c in rubric.CHECKS}
    for cid, tier, w, audit in LEGACY_RUBRIC:
        if table.get(cid) != (tier, w, audit):
            probs.append(f"{cid} changed: {table.get(cid)}")
    ids = [c[0] for c in rubric.CHECKS]
    if ids[:20] != [x[0] for x in LEGACY_RUBRIC] or ids[20:] != [
            "R21", "R22", "R23", "R24", "R25", "R26", "R27", "R28"]:
        probs.append(f"rubric check order {ids}")
    if [c for c in CREATIVE_AUDIT if not table[c][2]] or \
            [c for c in ("R21", "R22", "R24", "R25") if table[c][2]]:
        probs.append("audit flags of R21-R28 changed")

    def res(s):
        return {c["id"]: c for c in rubric.score(s)["checks"]}

    r = res(good)
    bad = [c for c in ("R21", "R22", "R23", "R24", "R25", "R26", "R27")
           if r[c]["pass"] is not False]
    if bad or r["R28"]["pass"] is not True:
        probs.append(f"absent creative keys: {[(c, r[c]['pass']) for c in r if c >= 'R21']}")
    strong = strong_creative_fixture(good)
    if gates.gate1(strong):
        probs.append(f"strong creative fixture fails gate 1: {gates.gate1(strong)}")
    r = res(strong)
    bad = [(c, r[c]["detail"]) for c in r if c >= "R21" and r[c]["pass"] is not True]
    if bad:
        probs.append(f"strong creative fixture fails {bad}")
    weak = creative_fixture(good)
    gamed = {**weak, "hook_variants": [
        {**v, "score": 1.0, "features": {k: 1.0 for k, _, _ in rubric.FEATURE_WEIGHTS},
         "reasons": ["gamed"]} for v in weak["hook_variants"]]}
    if res(gamed)["R23"]["pass"] is not False or res(weak)["R23"]["detail"] != \
            res(gamed)["R23"]["detail"]:
        probs.append("R23 reads the variants' self-reported score/features")
    sc, feats, why = rubric.hook_score("Hey guys, you won't believe this!!",
                                       "", "text-first", "question", strong)
    if sc >= rubric.HOOK_ALT_MIN or not feats["clickbait_marker"] or \
            not feats["filler_greeting"]:
        probs.append(f"hook_score missed filler/clickbait penalties: {sc} {feats}")
    return probs


def _unit_creative_eval():
    """vsp.creative_eval on the synthetic v2.1 brief (all metrics on), on a
    legacy make_shotlist brief (zeros, no crash) and summarize([])."""
    import json
    import make_shotlist
    from vsp import creative_eval as CE
    good, _ = legacy_cases()
    probs = []
    s = v21_script(good, True)
    row = CE.evaluate_files(s, None, v21_bundle(s))
    want = {"variant_count": 4, "distinct_visual_types": 4, "shots_typed": 5,
            "shot_typed_share": 1.0, "shot_plan_pass": True, "human_by_3s": True,
            "frame0_product_result": True, "loop_ok": True,
            "real_footage_marked": True, "sections_present": 4,
            "alt_openings_match": True, "alt_prompt_problems": 0,
            "cadence_in_band": True, "vibe": "raw-ugc",
            "findings": {"D157": [], "D159": [], "D160": []}}
    got = {k: row.get(k) for k in want}
    if got != want:
        probs.append(f"v2.1 row {got} != {want}")
    # audit: variant A is before-after-split but frame 0 is hook-hands-mid-action
    swapped = CE.evaluate_files(s, None, _swap(v21_bundle(s), "hook-hands-mid-action · CU",
                                               "split-before-after · CU"))
    if row.get("frame0_visual_match") is not False or \
            swapped.get("frame0_visual_match") is not True:
        probs.append(f"frame0_visual_match {row.get('frame0_visual_match')} / "
                     f"{swapped.get('frame0_visual_match')} (want False / True)")
    bundle, _, _ = make_shotlist.build_bundle(good, refs=[UNIT_REEL])
    leg = CE.evaluate_files(good, None, bundle)
    if leg["variant_count"] or leg["keyword_placement_pass"] or \
            (not leg["shots_typed"] and leg["shot_plan_pass"]):
        probs.append(f"legacy row not zeros: {leg}")
    # malformed creative keys never crash a metric (the scorecard would
    # otherwise record the run as zeros)
    c = creative_fixture(good)
    hv = [dict(v) for v in c["hook_variants"]]
    hv[2].pop("id")
    hv[1]["id"] = 0
    hv[0]["visual_type"] = {"x": 1}
    for bad in ({**c, "hook_variants": hv}, {**c, "creative_warnings": 3},
                {**c, "direction": {"vibe": {"x": 1}, "tone": "warm"}},
                {**c, "discovery": {"primary_keyword": 7}}):
        r = CE.evaluate_files(bad, {"shots": "x"}, 42)
        if r.get("errors"):
            probs.append(f"creative_eval errors on a malformed script: {r['errors']}")
    summ = CE.summarize([row, leg, CE.evaluate_files(None, None, None)])
    json.dumps(summ)
    if summ["runs"] != 3 or summ["shot_plan_pass"]["k"] < 1 or \
            CE.summarize([])["hook_variants_per_script"] != 0.0:
        probs.append(f"summarize: {summ}")
    return probs


def _unit_schema_creative():
    """The schema's creative $defs accept the synthetic fixtures (both lanes),
    reject bad enums/consts, and their enums are creative_vocab's ids."""
    from vsp import creative_vocab as CV
    from vsp import schema
    good, _ = legacy_cases()
    probs = []
    for s in (creative_fixture(good), creative_fixture(good_ai(good)),
              strong_creative_fixture(good)):
        errs = schema.validate(s)
        if errs:
            probs.append(f"valid creative fixture rejected: {errs[:3]}")
    bad = creative_fixture(good)
    bad = {**bad, "direction": {**bad["direction"], "vibe": "grunge"},
           "hook_variants": bad["hook_variants"][:2]}
    errs = schema.validate(bad)
    if not any("vibe" in e for e in errs) or not any("minItems" in e for e in errs):
        probs.append(f"bad creative keys accepted: {errs}")
    d = schema.SCRIPT_SCHEMA["$defs"]
    if d["direction"]["properties"]["vibe"]["enum"] != list(CV.VIBES) or \
            d["hook_variant"]["properties"]["visual_type"]["enum"] != list(CV.VISUAL_TYPES) or \
            d["hook_variant"]["properties"]["archetype"]["enum"] != list(CV.HOOK_ARCHETYPES):
        probs.append("schema enums drifted from vsp/creative_vocab.py")
    try:
        with open(schema.SCHEMA_PATH, encoding="utf-8") as f:
            if f.read() != schema.schema_text():
                probs.append("schema/script.schema.json is stale (python3 -m vsp.schema --write)")
    except OSError as e:
        probs.append(f"schema file unreadable: {e}")
    return probs


def unit_cases():
    return [("registry-shape", _unit_registry_shape),
            ("router-contract", _unit_router_contract),
            ("research-pack-contract", _unit_research_contract),
            ("deliverable-block-in-sync", _unit_deliverable_in_sync),
            ("deliverable-check-strengthened", _unit_deliverable_strengthened),
            ("d138-brief-label-instruction", _unit_d138_brief_label),
            ("d142-warning-never-fails", _unit_warn_never_fails),
            ("legacy-messages-first", _unit_legacy_first),
            ("crashing-check-fails-closed", _unit_check_crash_fails_closed),
            # WS-INT (pipeline v2 integration): learned state the maker reads
            ("priors-reader-contract", _unit_priors_reader),
            ("priors-change-only-tie-breaks", _unit_priors_tiebreak_only),
            ("hook-pack-loader-contract", _unit_hook_pack_loader),
            # WS-EVAL (pipeline v2.1): gate-2 creative rules on a synthetic
            # v2.1 brief (D157 / D159 / D160)
            ("v21-bundle-passes-gate2", _unit_v21_bundle_passes),
            ("v21-gate2-violations-d157-d159-d160", _unit_v21_violations),
            ("v21-gate2-silent-on-legacy-bundles", _unit_v21_silent_on_legacy),
            ("v21-rubric-creative-checks", _unit_rubric_creative),
            ("v21-creative-eval-metrics", _unit_creative_eval),
            ("v21-schema-creative-defs", _unit_schema_creative),
            ("v21-precision-negation-corpus", _unit_precision_corpus),
            ("v21-payoff-and-frame0-openers", _unit_v21_payoff_and_frame0),
            ("v21-repair-with-creative-keys", _unit_repair_with_creative_keys)]


def all_cases():
    good, cases = legacy_cases()
    return good, cases + new_cases(good) + creative_cases(good)


# ------------------------------------------- WS-EVAL: v2.1 creative layer
# Synthetic, contract-valid creative keys (docs/CREATIVE-PLAN.md §1.1-1.3)
# for the legacy good fixture — written from the contract only, never from
# a builder's output. creative_fixture(good) passes gates 1 and 2; each
# creative_cases() failure breaks exactly one contract clause.

def creative_direction(s):
    """A valid script['direction'] for script s (energy_curve = one entry
    per hook_stack + beats item, in script order)."""
    ai = s.get("presenter") == "ai"
    items = list(s.get("hook_stack") or []) + list(s.get("beats") or [])
    lib = {"tiktok": {"library": "TikTok Commercial Music Library (CML)",
                      "note": "business account, organic + ads; TikTok only"},
           "instagram": {"library": "Meta Sound Collection",
                         "note": "royalty-free on Facebook and Instagram only"},
           "youtube_shorts": {"library": "YouTube Audio Library",
                              "note": "no Content ID claims; not the Shorts label library"}}
    return {
        "schema_version": 1, "vibe": "raw-ugc",
        "vibe_reason": "a one-take phone demo reads native", "secondary_vibe": None,
        "tone": {"voice": "warm", "allowed": ["warm", "confident", "calm"],
                 "humor": "light", "notes": "talk to one friend"},
        "energy": 3,
        "pacing": {"target_wpm": [155, 180], "avg_shot_s": [2.0, 3.5],
                   "cuts_per_10s": [3, 5], "max_static_s": 3.5,
                   "pattern_interrupt_s": 4.0},
        "energy_curve": [{"t": it.get("t", ""), "type": it.get("type"),
                          "energy": 5 if i < 2 else 3}
                         for i, it in enumerate(items)],
        "music": {"moods": ["upbeat", "bright"], "bpm": [95, 115],
                  "genres": ["acoustic pop"], "vo_ducking_db": -12,
                  "sfx": ["product click"], "in_master": False,
                  "search_queries": ["upbeat acoustic", "bright pop 100 bpm",
                                     "happy ukulele"], "licensing": lib},
        "look": {"lighting": "window key at 45 degrees", "palette_names": ["warm white"],
                 "palette_hex": ["#F5EFE6", "#2B2B2B"], "grade": "natural",
                 "set": "a bathroom counter", "wardrobe": "a plain tee"},
        "camera": {"style": "handheld phone, stabilised", "lens": "main 1x",
                   "movement": ["handheld", "push-in"]},
        "text_style": {"case": "upper", "weight": "bold",
                       "max_words_per_card": 3, "placement": "top safe zone"},
        "transitions": ["hard-cut"],
        "showmanship": "a reaction face at the payoff",
        "voice": ({"presenter": "ai", "spec": "Natural-prosody synthetic voice, "
                   "disclosed; no robotic cadence; never claims to be human."}
                  if ai else
                  {"presenter": "human", "spec": "The creator's own voice, "
                   "recorded on the day; no TTS, no voice changer."}),
        "do": ["show the product in use at frame 0"],
        "dont": ["no music in the master"],
        "evidence": [{"claim": "lo-fi native footage holds attention",
                      "grade": "M", "source": "vibe-tone-music §2.1"}]}


def creative_variants(s):
    """Valid script['hook_variants'] for the legacy good fixture: variant A
    is the script's own hook + frame-0 overlay; B-D differ in archetype,
    visual_type and first three words."""
    return [
        {"id": "A", "is_primary": True, "archetype": "transformation",
         "family": "transformation", "verbal": "Look at this.",
         "overlay": "BEFORE | AFTER", "visual_type": "before-after-split",
         "visual": "Frame 0: split screen, before left, after right.",
         "audio": "the real product sound", "caption_line": "Test caption.",
         "score": 0.7, "features": {"length_band": 0.6}, "reasons": ["label pair"]},
        {"id": "B", "is_primary": False, "archetype": "negative-command",
         "family": "negative-command", "verbal": "Stop skipping the test product step.",
         "overlay": "TEST PRODUCT STEP", "visual_type": "problem-state",
         "visual": "Frame 0: the messy counter before the pass.",
         "audio": "a hard cut on the first word",
         "caption_line": "Stop skipping the test product step.",
         "score": 0.6, "features": {}, "reasons": []},
        {"id": "C", "is_primary": False, "archetype": "question",
         "family": "curiosity-gap", "verbal": "Does the test product really work?",
         "overlay": "TEST PRODUCT", "visual_type": "product-in-action",
         "visual": "Frame 0: hands mid-pass with the test product.",
         "audio": "the real product sound",
         "caption_line": "Does the test product really work?",
         "score": 0.55, "features": {}, "reasons": []},
        {"id": "D", "is_primary": False, "archetype": "showcase",
         "family": "bold-claim", "verbal": "Watch the test product in action.",
         "overlay": "IN ACTION", "visual_type": "satisfying-macro",
         "visual": "Frame 0: extreme close-up of the texture.",
         "audio": "the real product sound, no music",
         "caption_line": "Watch the test product in action.",
         "score": 0.5, "features": {}, "reasons": []},
    ]


AI_LINE = "made with an AI persona"


def creative_discovery(s):
    """Valid script['discovery'] for the legacy good fixture (AI lane adds
    the disclosure line to every caption and sets every AI toggle)."""
    ai = s.get("presenter") == "ai"
    tail = f"\n{AI_LINE}" if ai else ""
    tags = ["#testproduct", "#beautytok"]
    return {
        "schema_version": 1, "primary_keyword": "test product",
        "secondary_keywords": ["test product review"],
        "search_intents": ["is the test product worth it"],
        "placement": {"spoken_by_s": 3.0, "on_screen_by_s": 0.5,
                      "caption_first_60": True, "hashtag": "#testproduct",
                      "cover_text": True},
        "comment_word": "TEST",
        "cover": {"frame_s": 7.5, "text": "TEST PRODUCT RESULT",
                  "safe_box": "x120-888 y420-1248", "why": "the after-state"},
        "platforms": {
            "tiktok": {"caption": "Test product: one pass and it is done." + tail
                       + "\n#testproduct #beautytok", "hashtags": tags,
                       "keywords_to_suggest": ["test product", "test product review"],
                       "toggles": {"is_aigc": ai}, "notes": ["suggest 2 keywords"]},
            "instagram": {"caption": "Test product, one pass and done." + tail
                          + "\n#testproduct #beautytok", "hashtags": tags,
                          "description_line": "Hands apply the test product in one pass.",
                          "toggles": {"is_ai_generated": ai},
                          "trial_reels": {"recommended": True,
                                          "protocol": "variants as manual trials, 24/48/72 h"},
                          "notes": []},
            "youtube_shorts": {"title": "Test product: one pass, done",
                               "description": "Test product demo in one pass." + tail
                               + "\n#testproduct #beautytok",
                               "hashtags": tags, "related_video": None,
                               "toggles": {"containsSyntheticMedia": ai}, "notes": []}},
        "posting": [{"item": "post the variants the same day", "grade": "A",
                     "source": "discovery-seo §3"}],
        "checklist": ["keyword spoken by 3.0 s"]}


def creative_fixture(good):
    """good + valid direction, hook_variants and discovery."""
    s = dict(good)
    s["direction"] = creative_direction(s)
    s["hook_variants"] = creative_variants(s)
    s["discovery"] = creative_discovery(s)
    return s


def _hv(s, i, **kw):
    hv = [dict(v) for v in s["hook_variants"]]
    hv[i] = {**hv[i], **kw}
    return hv


def _dsc(s, plat=None, **kw):
    d = json_copy(s["discovery"])
    if plat:
        d["platforms"][plat].update(kw)
    else:
        d.update(kw)
    return d


def _dir(s, **kw):
    d = json_copy(s["direction"])
    for k, v in kw.items():
        if "." in k:
            a, b = k.split(".", 1)
            d[a] = {**d[a], b: v}
        else:
            d[k] = v
    return d


def json_copy(obj):
    import json
    return json.loads(json.dumps(obj))


def creative_cases(good):
    """v2.1 gate-1 cases (RULES.md §68): one failing case per key violation
    of D154 / D155 / D156 / D158 (the message carries the id; "only" = no
    other rule fires) plus passing controls with fully valid synthetic
    creative keys on both presenter lanes."""
    c = creative_fixture(good)
    cai = creative_fixture(good_ai(good))
    hv = c["hook_variants"]

    def only(rid):
        return {"only": rid}

    cases = [
        # ---- passing controls
        ("v21-creative-good", c, True, []),
        ("v21-creative-good-ai", cai, True, []),
        ("v21-creative-3-variants-good", {**c, "hook_variants": hv[:3]}, True, []),
        ("v21-d158-prompt-supplied-offer", {**good,
            "prompt": "test product, 20% off this week",
            "beats": _with_beat(good, 2, dialogue="20% off this week. One pass.")},
         True, []),
        # ---- D154 hook_variants
        ("d154-too-few-variants", {**c, "hook_variants": hv[:2]},
         False, ["D154:"], only("D154")),
        ("d154-not-a-list", {**c, "hook_variants": {"A": hv[0]}},
         False, ["D154:"], only("D154")),
        ("d154-ids-not-lettered", {**c, "hook_variants": _hv(c, 1, id="X")},
         False, ["D154:"], only("D154")),
        ("d154-primary-not-a", {**c, "hook_variants": [
            {**hv[0], "is_primary": False}, {**hv[1], "is_primary": True}] + hv[2:]},
         False, ["D154:"], only("D154")),
        ("d154-primary-verbal-drift", {**c, "hook_variants": _hv(
            c, 0, verbal="Look at this now.")}, False, ["D154:"], only("D154")),
        ("d154-primary-overlay-drift", {**c, "hook_variants": _hv(
            c, 0, overlay="DAY 1 | DAY 7")}, False, ["D154:"], only("D154")),
        ("d154-duplicate-visual-type", {**c, "hook_variants": _hv(
            c, 2, visual_type="problem-state")}, False, ["D154:"], only("D154")),
        ("d154-unknown-visual-type", {**c, "hook_variants": _hv(
            c, 2, visual_type="talking-head")}, False, ["D154:"], only("D154")),
        ("d154-unknown-archetype", {**c, "hook_variants": _hv(
            c, 2, archetype="shock-value")}, False, ["D154:"], only("D154")),
        ("d154-two-archetypes-in-four", {**c, "hook_variants": [
            hv[0], {**hv[1], "archetype": "question"}, hv[2],
            {**hv[3], "archetype": "question"}]}, False, ["D154:"], only("D154")),
        ("d154-shared-first-three-words", {**c, "hook_variants": _hv(
            c, 2, verbal="Stop skipping the test product.", overlay="TEST PRODUCT")},
         False, ["D154:"], only("D154")),
        ("d154-variant-over-8-words", {**c, "hook_variants": _hv(
            c, 1, verbal="Stop skipping the test product step, it matters a lot.")},
         False, ["D154:"], only("D154")),
        ("d154-variant-raw-slot", {**c, "hook_variants": _hv(
            c, 1, verbal="Stop skipping the {category} step.", overlay="")},
         False, ["D154:"], only("D154")),
        ("d154-overlay-not-hook-phrase", {**c, "hook_variants": _hv(
            c, 1, overlay="SKIPPING STEP")}, False, ["D154:"], only("D154")),
        ("d154-overlay-over-3-words", {**c, "hook_variants": _hv(
            c, 1, overlay="SKIPPING THE TEST PRODUCT")}, False, ["D154:"], only("D154")),
        ("d154-variant-invented-price", {**c, "hook_variants": _hv(
            c, 2, caption_line="The $25 test product, tested.")},
         False, ["D154:", "D37"], only("D154")),
        ("d154-variant-social-proof", {**c, "hook_variants": _hv(
            c, 2, verbal="12,000+ orders cannot be wrong.", overlay="")},
         False, ["D154:", "D136"], only("D154")),
        ("d154-variant-engagement-bait", {**c, "hook_variants": _hv(
            c, 3, caption_line="Tag a friend who needs this.")},
         False, ["D154:", "D139"], only("D154")),
        ("d154-variant-absolute-claim", {**c, "hook_variants": _hv(
            c, 3, verbal="The best product ever, tested.", overlay="")},
         False, ["D154:", "D141"], only("D154")),
        ("d154-variant-fake-urgency", {**c, "hook_variants": _hv(
            c, 3, verbal="Only 3 left of the test product.", overlay="")},
         False, ["D154:", "D158"], only("D154")),
        ("d154-ai-variant-lived-experience", {**cai, "hook_variants": _hv(
            cai, 1, verbal="I tried the test product for a week.", overlay="")},
         False, ["D154:", "D137"], only("D154")),
        ("d154-ai-human-only-archetype", {**cai, "hook_variants": _hv(
            cai, 2, archetype="story-time")}, False, ["D154:"], only("D154")),
        ("d154-price-anchor-without-price", {**c, "hook_variants": _hv(
            c, 2, archetype="price-anchor")}, False, ["D154:"], only("D154")),
        ("d154-proof-first-without-proof", {**c, "hook_variants": _hv(
            c, 2, archetype="proof-first")}, False, ["D154:"], only("D154")),
        ("d154-shape-features-not-numbers", {**c, "hook_variants": _hv(
            c, 1, features={"length_band": "high"})},
         False, ["D154: shape errors"], only("D154")),
        # ---- D155 discovery
        ("d155-not-an-object", {**c, "discovery": ["test product"]},
         False, ["D155:"], only("D155")),
        ("d155-tiktok-too-many-hashtags", {**c, "discovery": _dsc(
            c, "tiktok", hashtags=["#testproduct", "#beautytok", "#skincare",
                                   "#glowup", "#makeuptok", "#grwm"])},
         False, ["D155:"], only("D155")),
        ("d155-instagram-generic-only-hashtags", {**c, "discovery": _dsc(
            c, "instagram", caption="Test product, one pass and done.\n#fyp #viral",
            hashtags=["#fyp", "#viral"])}, False, ["D155:", "D140"], only("D155")),
        ("d155-youtube-16-hashtags", {**c, "discovery": _dsc(
            c, "youtube_shorts", hashtags=["#t%d" % i for i in range(16)])},
         False, ["D155:"], only("D155")),
        ("d155-youtube-title-too-long", {**c, "discovery": _dsc(
            c, "youtube_shorts", title="Test product " + "x" * 100)},
         False, ["D155:"], only("D155")),
        ("d155-youtube-title-angle-brackets", {**c, "discovery": _dsc(
            c, "youtube_shorts", title="Test product <one pass>")},
         False, ["D155:"], only("D155")),
        ("d155-youtube-description-over-5000-bytes", {**c, "discovery": _dsc(
            c, "youtube_shorts", description="Test product. " + "é" * 2600)},
         False, ["D155:"], only("D155")),
        ("d155-caption-invented-price", {**c, "discovery": _dsc(
            c, "tiktok", caption="Test product for $19.\n#testproduct #beautytok")},
         False, ["D155:", "D37"], only("D155")),
        ("d155-caption-social-proof", {**c, "discovery": _dsc(
            c, "instagram", caption="Test product, 4.9 stars.\n#testproduct")},
         False, ["D155:", "D136"], only("D155")),
        ("d155-caption-engagement-bait", {**c, "discovery": _dsc(
            c, "tiktok", caption="Test product. Tag a friend.\n#testproduct")},
         False, ["D155:", "D139"], only("D155")),
        ("d155-title-absolute-claim", {**c, "discovery": _dsc(
            c, "youtube_shorts", title="Test product, guaranteed results")},
         False, ["D155:", "D141"], only("D155")),
        ("d155-caption-fake-urgency", {**c, "discovery": _dsc(
            c, "tiktok", caption="Test product, today only.\n#testproduct")},
         False, ["D155:", "D158"], only("D155")),
        ("d155-second-cta-destination", {**c, "discovery": _dsc(
            c, "instagram", caption="Test product, one pass. Link in bio.\n#testproduct")},
         False, ["D155:", "D46"], only("D155")),
        ("d155-ai-caption-no-disclosure", {**cai, "discovery": _dsc(
            cai, "tiktok", caption="Test product: one pass and it is done.\n#testproduct")},
         False, ["D155:", "D138"], only("D155")),
        ("d155-ai-toggle-false", {**cai, "discovery": _dsc(
            cai, "youtube_shorts", toggles={"containsSyntheticMedia": False})},
         False, ["D155:"], only("D155")),
        ("d155-keyword-not-in-caption-line-1", {**c, "discovery": _dsc(
            c, "instagram", caption="One pass and done.\nTest product.\n#testproduct")},
         False, ["D155:"], only("D155")),
        ("d155-keyword-not-in-youtube-title", {**c, "discovery": _dsc(
            c, "youtube_shorts", title="One pass, done")}, False, ["D155:"], only("D155")),
        ("d155-cover-text-over-5-words", {**c, "discovery": _dsc(
            c, cover={"frame_s": 7.5, "text": "THE TEST PRODUCT RESULT IN ONE PASS"})},
         False, ["D155:"], only("D155")),
        ("d155-cover-frame-outside-video", {**c, "discovery": _dsc(
            c, cover={"frame_s": 42.0, "text": "TEST PRODUCT"})},
         False, ["D155:"], only("D155")),
        ("d155-no-primary-keyword", {**c, "discovery": {
            k: v for k, v in c["discovery"].items() if k != "primary_keyword"}},
         False, ["D155: shape errors"], only("D155")),
        ("d155-shape-placement-hashtag", {**c, "discovery": _dsc(
            c, placement={**c["discovery"]["placement"], "hashtag": "testproduct"})},
         False, ["D155: shape errors"], only("D155")),
        # ---- D156 direction
        ("d156-not-an-object", {**c, "direction": "raw-ugc"},
         False, ["D156:"], only("D156")),
        ("d156-unknown-vibe", {**c, "direction": _dir(c, vibe="grunge")},
         False, ["D156:"], only("D156")),
        ("d156-unknown-tone", {**c, "direction": _dir(c, **{"tone.voice": "sarcastic"})},
         False, ["D156:"], only("D156")),
        ("d156-unknown-camera-move", {**c, "direction": _dir(
            c, **{"camera.movement": ["crash-zoom"]})}, False, ["D156:"], only("D156")),
        ("d156-wpm-outside-140-200", {**c, "direction": _dir(
            c, **{"pacing.target_wpm": [150, 215]})}, False, ["D156:"], only("D156")),
        ("d156-wpm-slower-than-beat-sizing", {**c, "direction": _dir(
            c, **{"pacing.target_wpm": [140, 160]})}, False, ["D156:"], only("D156")),
        ("d156-max-static-over-3-5", {**c, "direction": _dir(
            c, **{"pacing.max_static_s": 5.0})}, False, ["D156:"], only("D156")),
        ("d156-music-in-master", {**c, "direction": _dir(
            c, **{"music.in_master": True})}, False, ["D156:"], only("D156")),
        ("d156-licensing-missing-platform", {**c, "direction": _dir(
            c, **{"music.licensing": {k: v for k, v in c["direction"]["music"][
                "licensing"].items() if k != "youtube_shorts"}})},
         False, ["D156:"], only("D156")),
        ("d156-ai-music-on-tiktok", {**c, "direction": _dir(
            c, **{"music.licensing": {**c["direction"]["music"]["licensing"],
                                      "tiktok": {"library": "AI-generated music (Suno)",
                                                 "note": "paid plan"}}})},
         False, ["D156:"], only("D156")),
        ("d156-ai-voice-claims-human", {**cai, "direction": _dir(
            cai, voice={"presenter": "ai", "spec": "Conversational human read, "
                        "warm and confident."})}, False, ["D156:"], only("D156")),
        ("d156-ai-voice-not-disclosed", {**cai, "direction": _dir(
            cai, voice={"presenter": "ai", "spec": "Natural-prosody synthetic "
                        "voice, warm."})}, False, ["D156:"], only("D156")),
        ("d156-voice-presenter-mismatch", {**c, "direction": _dir(
            c, voice={"presenter": "ai", "spec": "Natural-prosody synthetic voice, "
                      "disclosed."})}, False, ["D156:"], only("D156")),
        ("d156-energy-curve-count", {**c, "direction": _dir(
            c, energy_curve=c["direction"]["energy_curve"][:-1])},
         False, ["D156:"], only("D156")),
        ("d156-energy-curve-order", {**c, "direction": _dir(
            c, energy_curve=list(reversed(c["direction"]["energy_curve"])))},
         False, ["D156:"], only("D156")),
        ("d156-energy-out-of-range", {**c, "direction": _dir(c, energy=7)},
         False, ["D156:"], only("D156")),
        ("d156-bad-palette-hex", {**c, "direction": _dir(
            c, **{"look.palette_hex": ["warm white"]})}, False, ["D156:"], only("D156")),
        ("d156-card-over-3-words", {**c, "direction": _dir(
            c, **{"text_style.max_words_per_card": 6})}, False, ["D156:"], only("D156")),
        ("d156-no-vibe", {**c, "direction": {k: v for k, v in c["direction"].items()
                                             if k != "vibe"}},
         False, ["D156: shape errors"], only("D156")),
        ("d156-shape-energy-not-integer", {**c, "direction": _dir(c, energy=3.5)},
         False, ["D156: shape errors"], only("D156")),
        # ---- D158 offer / urgency (script viewer text + caption)
        ("d158-fake-limited-time", {**good, "beats": _with_beat(
            good, 2, dialogue="Limited-time offer. One pass, done.")},
         False, ["D158:"], only("D158")),
        ("d158-fake-scarcity", {**good, "beats": _with_beat(
            good, 2, dialogue="Only 3 left. One pass, done.")},
         False, ["D158:"], only("D158")),
        ("d158-fake-discount-caption", {**good,
            "caption": "Test caption. 30% off this week. #beautytok"},
         False, ["D158:"], only("D158")),
        ("d158-offer-does-not-allow-scarcity", {**good,
            "prompt": "test product, 20% off this week",
            "beats": _with_beat(good, 2, dialogue="Only 3 left. One pass, done.")},
         False, ["D158:"], only("D158")),
    ]
    return cases


# ------------------------------------------------ WS-INT: learned-state units
# The maker's learned inputs (learned/priors.json, learned/hook_packs/*.json)
# are checked in-process against temp dirs; nothing under the repo's
# learned/ is read or written (vsp/selftest.py asserts learned/ is untouched).

def _write_json(path, obj):
    import json
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if isinstance(obj, str):
            f.write(obj)
        else:
            json.dump(obj, f)
    return path


def _unit_priors_reader():
    import os
    import random
    import shutil
    import tempfile
    from vsp import priors as P
    probs = []
    d = tempfile.mkdtemp(prefix="vsp_unit_priors_")
    try:
        p = os.path.join(d, "priors.json")
        if P.load_priors(p) is not None:
            probs.append("missing priors file did not return None")
        # unknown schema versions are rejected (v1 and v2 are the known
        # ones since pipeline v2.1 — the case used to probe with 2)
        for bad in ("{not json", "[1, 2]", '{"schema_version": 99, "families": {}}',
                    '{"schema_version": 1, "families": []}'):
            _write_json(p, bad)
            os.utime(p, None)
            if P.load_priors(p) is not None:
                probs.append(f"invalid priors accepted: {bad!r}")
        _write_json(p, {"schema_version": 1, "metric": "hook_rate",
                        "families": {"beauty": {
                            "transformation": {"alpha": 3, "beta": 2, "n": 4},
                            "broken": {"alpha": -1, "beta": 2, "n": 9}}},
                        "global": {"bold-claim": {"alpha": 5, "beta": 1, "n": 2}}})
        pri = P.load_priors(p)
        if not pri or "broken" in pri["families"].get("beauty", {}):
            probs.append(f"valid priors not normalised: {pri}")
        if P.load_priors(p) is not pri:
            probs.append("priors not cached per path+mtime")
        if P.posterior(pri, "beauty", "transformation") != (3.0, 2.0, 4):
            probs.append("posterior: niche entry not used")
        if P.posterior(pri, "home", "bold-claim") != (5.0, 1.0, 2):
            probs.append("posterior: absent niche did not fall back to global")
        if P.posterior(pri, "beauty", "bold-claim") is not None:
            probs.append("posterior: a present niche must not borrow global")
        r1, r2 = random.Random(3), random.Random(3)
        if P.thompson(pri, "home", ["bold-claim"], r1) or r1.random() != r2.random():
            probs.append("thompson drew for n < 3 (or touched the rng)")
        t = P.thompson(pri, "beauty", ["transformation"], random.Random(3))
        if set(t) != {"transformation"} or not 0 < t["transformation"]["sample"] < 1:
            probs.append(f"thompson did not sample n >= 3: {t}")
    finally:
        shutil.rmtree(d, ignore_errors=True)
    return probs


_PRI_CASES = [("a $12 LED sunrise alarm lamp", "demo", "ai", 1),
              ("portable door lock", "review", "human", 2),
              ("insulated lunch bag", "demo", "human", 3),
              ("ergonomic laptop stand", "talking-head", "ai", 1),
              ("electric milk frother", "pov-vlog", "human", 1),
              ("car trash can with lid", "transformation", "ai", 2),
              ("hair straightener brush", "demo", "human", 1),
              ("bluetooth sleep mask", "review", "ai", 3),
              ("resistance bands set", "demo", "ai", 2),
              ("car detailing brush set", "talking-head", "human", 3)]


def _unit_priors_tiebreak_only():
    """A priors file may only re-order quality-equivalent hook candidates:
    the picked hook always has the top (anchored, overlay, contract)
    quality; the same priors file gives the same scripts; no priors file
    (or no family with n >= 3) gives byte-identical scripts; every script
    the priors changed records priors_used."""
    import json
    import os
    import shutil
    import tempfile
    import viral_script_maker as vsm
    from vsp.gates import gate1
    probs = []
    d = tempfile.mkdtemp(prefix="vsp_unit_tiebreak_")
    strong = _strong_priors()
    thin = {f: dict(v, n=2) for f, v in strong.items()}
    for name, tbl in (("strong", strong), ("thin", thin)):
        _write_json(os.path.join(d, name, "priors.json"),
                    {"schema_version": 1, "metric": "hook_rate",
                     "families": {}, "global": tbl})
    os.makedirs(os.path.join(d, "none"), exist_ok=True)
    orig, seen = vsm._hook_candidates, {}

    def spy(*a, **k):
        out = orig(*a, **k)
        # the builder's own scores, before pick_hook swaps in the prior
        seen["cands"] = [dict(c, score=tuple(c["score"])) for c in out]
        return out

    def batch(learned):
        os.environ["VSP_LEARNED_DIR"] = os.path.join(d, learned)
        out = []
        for prompt, fmt, pr, sd in _PRI_CASES:
            seen.clear()
            s = json.loads(json.dumps(vsm.generate(prompt, presenter=pr, fmt=fmt,
                                                   duration=30, seed=sd)))
            s.update(vsm.learned_provenance())
            s.pop("hook_packs", None)      # repo packs are not under test here
            ok_q = True
            c = seen.get("cands")
            if c:
                hook = s["hook_stack"][1]["dialogue"]
                top = max(x["score"][:3] for x in c)
                ok_q = all(x["score"][:3] == top for x in c if x["line"] == hook)
                if any(x["score"][3] != vsm.LEARNED_NEUTRAL for x in c):
                    ok_q = False      # the builder itself must stay neutral
            out.append((s, ok_q, bool(gate1(s))))
        return out

    saved = {k: os.environ.get(k) for k in ("VSP_LEARNED_DIR", "VSP_NO_PRIORS")}
    os.environ.pop("VSP_NO_PRIORS", None)
    vsm._hook_candidates = spy
    try:
        base, thin_r, a, b = (batch("none"), batch("thin"), batch("strong"),
                              batch("strong"))
    finally:
        vsm._hook_candidates = orig
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(d, ignore_errors=True)
    if [x[0] for x in thin_r] != [x[0] for x in base]:
        probs.append("priors with n < 3 changed the output (must be neutral)")
    if any("priors_used" in x[0] for x in base + thin_r):
        probs.append("priors_used recorded without usable priors")
    if [x[0] for x in a] != [x[0] for x in b]:
        probs.append("same seed + same priors file gave different scripts")
    changed = 0
    for (sb, _, g1b), (sa, qa, g1a), case in zip(base, a, _PRI_CASES):
        if not qa:
            probs.append(f"{case[0]}: priors beat a higher-quality hook")
        if g1a and not g1b:
            probs.append(f"{case[0]}: priors introduced a gate-1 failure")
        core = {k: v for k, v in sa.items() if k != "priors_used"}
        if core != sb:
            changed += 1
            if "priors_used" not in sa:
                probs.append(f"{case[0]}: changed by priors without priors_used")
    if not changed:
        probs.append("strong priors never changed a pick (check is vacuous)")
    return probs


def _unit_hook_pack_loader():
    import copy
    import os
    import shutil
    import tempfile
    import viral_script_maker as vsm
    probs = []
    static = {f: [t for t in lines] for f, lines in vsm.HOOKS.items()}
    slots = set()
    import re
    for lines in static.values():
        for t in lines:
            slots |= set(re.findall(r"\{([A-Za-z_]\w*)\}", t))
    if set(vsm.HOOK_SLOTS) != slots:
        probs.append("HOOK_SLOTS is not the slot set of the HOOKS templates")
    d = tempfile.mkdtemp(prefix="vsp_unit_packs_")
    try:
        ok_t = "Here's the {category} test nobody runs."
        _write_json(os.path.join(d, "00-malformed.json"), "{not json")
        _write_json(os.path.join(d, "01-list.json"), "[1, 2]")
        _write_json(os.path.join(d, "02-ok.json"), {
            "schema_version": 1, "id": "unit-ok", "status": "approved",
            "families": {"curiosity-gap": [ok_t, ok_t, static["curiosity-gap"][0]],
                         "no-such-family": ["Hi {product}."]}})
        _write_json(os.path.join(d, "03-bad-templates.json"), {
            "schema_version": 1, "id": "unit-bad", "status": "approved",
            "families": {"bold-claim": [
                "Meet {brandname}, the fix.", "Two\nlines {product}.",
                "x" * 121, "Look: {product.__class__}.", "{0} and {product}.", 7]}})
        _write_json(os.path.join(d, "04-proposed.json"), {
            "schema_version": 1, "id": "unit-proposed", "status": "proposed",
            "families": {"curiosity-gap": ["Proposed {product} line."]}})
        _write_json(os.path.join(d, "05-v2.json"), {
            "schema_version": 2, "id": "unit-v2", "status": "approved",
            "families": {"curiosity-gap": ["Version two {product}."]}})
        hooks = copy.deepcopy(static)
        ids, added, warns = vsm.load_hook_packs(d, hooks=hooks, warn=False)
        if ids != ["unit-ok"]:
            probs.append(f"loaded pack ids {ids} (want ['unit-ok'])")
        if added != {"curiosity-gap": [ok_t]} or hooks["curiosity-gap"][-1] != ok_t:
            probs.append(f"valid template not appended exactly once: {added}")
        if hooks["bold-claim"] != static["bold-claim"]:
            probs.append("a rejected template reached HOOKS")
        if any("Proposed" in t or "Version two" in t for t in hooks["curiosity-gap"]):
            probs.append("a proposed / schema-v2 pack was loaded")
        text = "\n".join(warns)
        for want in ("00-malformed.json", "01-list.json", "no-such-family",
                     "unknown slot(s) {brandname}", "newline", "121 chars",
                     "non-plain", "05-v2.json"):
            if want not in text:
                probs.append(f"no warning for {want!r}")
        if vsm.load_hook_packs(os.path.join(d, "absent"), hooks={}, warn=False) != ([], {}, []):
            probs.append("an absent hook_packs dir is not a no-op")
    finally:
        shutil.rmtree(d, ignore_errors=True)
    return probs


# ------------------------------------------------------ WS-INT: end to end
# Full pipeline runs (not --script-json) inside the self-test's temp outputs
# root, fixture viral.db and an empty temp learned/ dir. Each check is
# (name, fn(h)) -> [problems]; h is vsp.selftest's harness: h.run(args,
# learned=None, env=None) runs pipeline.py, h.py(code, args=(), env=None)
# runs python (env: per-run overrides, None = unset), h.out(name) is a fresh
# temp dir path, h.learned(name) a fresh learned/ dir, h.state is shared
# between checks (run in order).

E2E_PROMPT = "portable door lock"
E2E_ARTIFACTS = ("script.json", "bundle.md", "brief.md", "validation-report.md",
                 "captions.srt", "captions.vtt", "captions.json", "shotlist.csv",
                 "shots.json", "manifest.json", "trace.jsonl", "gate-report.json")
SUMMARY_KEYS = ("prompt", "niche", "hook_family", "hook_source", "hook",
                "presenter", "format", "duration_s", "seed", "candidate_seed",
                "script_sha256")
# the pipeline --json summary (docs/ws-int-notes.md)
JSON_KEYS = ("status", "exit_code", "outdir", "artifacts", "winner", "rubric",
             "route", "warnings", "gates", "failed_stage", "stages",
             "script_summary")


def _fail_run(r):
    return [f"exit {r.returncode}\n{r.stdout[-700:]}{r.stderr[-400:]}"]


def _load(path):
    import json
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _stage_lines(stdout):
    """{stage n: status} from the report's stage lines (crash = 'CRASH')."""
    import re
    out = {}
    for n, st in re.findall(r"^stage (\d+) \([^)]+\): (OK|FAIL|SKIPPED|BYPASSED)\b",
                            stdout, re.M):
        out[int(n)] = st
    for n in re.findall(r"^STAGE (\d+) FAILED \(", stdout, re.M):
        out[int(n)] = "CRASH"
    return out


def _srt_problems(text):
    import re
    probs, prev = [], -1.0
    blocks = [b for b in text.replace("\r\n", "\n").strip().split("\n\n") if b.strip()]
    if not blocks:
        return ["captions.srt has no cues"]
    ts = re.compile(r"^(\d\d):(\d\d):(\d\d),(\d{3}) --> (\d\d):(\d\d):(\d\d),(\d{3})$")
    for i, b in enumerate(blocks, 1):
        ls = b.split("\n")
        m = ts.match(ls[1]) if len(ls) > 1 else None
        if len(ls) < 3 or ls[0].strip() != str(i) or not m:
            probs.append(f"captions.srt cue {i} is malformed: {b[:80]!r}")
            continue
        g = [int(x) for x in m.groups()]
        s = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000.0
        e = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000.0
        if not s < e or s < prev:
            probs.append(f"captions.srt cue {i}: bad times {ls[1]}")
        prev = e
    return probs


def _e2e_normal(h):
    import hashlib
    import json
    import os
    import re
    from vsp import schema, trace
    out = h.out("normal")
    r = h.run([E2E_PROMPT, "--presenter", "ai", "--out-dir", out])
    if r.returncode != 0:
        return _fail_run(r)
    probs = []
    st = _stage_lines(r.stdout)
    if sorted(st) != list(range(1, 11)):
        probs.append(f"stage lines present: {sorted(st)}")
    # a clean run: nothing FAILed or crashed; repair only runs when no
    # candidate passed (research may be SKIPPED if the pack is unusable)
    bad = {n: s for n, s in st.items()
           if s != "OK" and not (n == 6 and s == "SKIPPED")
           and not (n == 2 and s == "SKIPPED")}
    if bad:
        probs.append(f"stage statuses not clean: {bad}")
    for want in ("gate 1 (script): PASS", "gate 2 (brief): PASS", "\nwarnings:"):
        if want not in r.stdout:
            probs.append(f"report lacks {want.strip()!r}")
    if not re.search(r"^stage 3 \(generate\): OK — 8 candidate\(s\) \(seeds 701, ",
                     r.stdout, re.M):
        probs.append("stage 3 line: default best-of-8 must start at the raw seed 701")
    missing = [f for f in E2E_ARTIFACTS if not os.path.isfile(os.path.join(out, f))]
    if missing:
        probs.append(f"missing artifacts: {missing}")
        return probs
    with open(os.path.join(out, "script.json"), "rb") as f:
        raw = f.read()
    errs = schema.validate(json.loads(raw.decode("utf-8")))
    if errs:
        probs.append(f"script.json schema errors: {errs[:3]}")
    with open(os.path.join(out, "captions.srt"), encoding="utf-8") as f:
        probs += _srt_problems(f.read())
    with open(os.path.join(out, "manifest.json"), encoding="utf-8") as f:
        m = json.load(f)
    ss = m.get("script_summary") or {}
    if tuple(k for k in SUMMARY_KEYS if k not in ss):
        probs.append(f"manifest script_summary lacks {[k for k in SUMMARY_KEYS if k not in ss]}")
    sha = hashlib.sha256(raw).hexdigest()
    if ss.get("script_sha256") != sha or (m.get("outputs") or {}).get("script.json") != sha:
        probs.append("script_summary.script_sha256 / outputs hash != script.json")
    if (ss.get("prompt"), ss.get("seed"), ss.get("presenter")) != (E2E_PROMPT, 701, "ai"):
        probs.append(f"script_summary identity wrong: {ss}")
    with open(os.path.join(out, "gate-report.json"), encoding="utf-8") as f:
        gr = json.load(f)
    if gr.get("status") != "pass" or gr.get("exit_code") != 0:
        probs.append(f"gate-report.json status {gr.get('status')}/{gr.get('exit_code')}")
    # D149: candidate 0 is the raw seed; the manifest records every sub-seed
    seeds = (m.get("seeds") or {}).get("candidates") or []
    cands = gr.get("candidates") or []
    if (len(seeds) != 8 or seeds[0] != 701 or len(cands) != 8
            or [c.get("seed") for c in cands] != seeds):
        probs.append(f"candidate seeds wrong: manifest {seeds[:3]}…, "
                     f"gate-report {[c.get('seed') for c in cands][:3]}…")
    if (gr.get("selected") or {}).get("via") != "selection":
        probs.append(f"winner not chosen by selection: {gr.get('selected')}")
    if not any(x.get("type") == "span" for x in trace.read(os.path.join(out, "trace.jsonl"))):
        probs.append("trace.jsonl has no spans")
    h.state["normal"] = out
    return probs


def _e2e_parity(h):
    """--candidates 1 == viral_script_maker.generate(prompt, seed=701)."""
    import json
    import os
    out = h.out("parity")
    r = h.run([E2E_PROMPT, "--presenter", "ai", "--candidates", "1", "--out-dir", out])
    if r.returncode != 0:
        return _fail_run(r)
    code = ("import json, sys; sys.path.insert(0, %r); import viral_script_maker as v; "
            "sys.stdout.write(json.dumps(v.generate(%r, seed=701)))" % (h.repo, E2E_PROMPT))
    d = h.py(code)
    if d.returncode != 0:
        return [f"direct maker run failed: {d.stderr[-400:]}"]
    direct = json.loads(d.stdout)
    with open(os.path.join(out, "script.json"), encoding="utf-8") as f:
        piped = json.load(f)
    h.state["parity_script"] = piped
    probs = []
    if direct != piped:
        diff = sorted(k for k in set(direct) | set(piped) if direct.get(k) != piped.get(k))
        probs.append(f"--candidates 1 script differs from generate(seed=701): keys {diff}")
    seeds = (_load(os.path.join(out, "manifest.json")).get("seeds") or {})
    if seeds.get("root") != 701 or seeds.get("candidates") != [701]:
        probs.append(f"--candidates 1 manifest seeds {seeds} (want root 701, [701])")
    return probs


def _e2e_replay(h):
    import json
    import os
    if "normal" not in h.state:
        return ["no manifest (e2e-normal-run failed)"]
    man = os.path.join(h.state["normal"], "manifest.json")
    r = h.run(["--replay", man])
    if r.returncode != 0 or "replay: OK" not in r.stdout:
        return _fail_run(r)
    r = h.run(["--replay", man, "--json"])
    try:
        d = json.loads(r.stdout)
    except ValueError as e:
        return [f"--replay --json stdout is not one JSON document: {e}: {r.stdout[:200]!r}"]
    rep = d.get("replay") or {}
    if (r.returncode, d.get("status"), d.get("exit_code")) != (0, "reproduced", 0) \
            or not rep.get("expected_sha256") \
            or rep.get("expected_sha256") != rep.get("actual_sha256"):
        return [f"--replay --json: exit {r.returncode}, status {d.get('status')}, "
                f"sha {rep.get('expected_sha256')} -> {rep.get('actual_sha256')}"]
    # the verdict must reproduce too: same script.json, different exit code
    # (e.g. a gate that now answers differently) is a MISMATCH
    m = _load(man)
    m["exit_code"], m["status"] = 1, "gate1_fail"
    tampered = _write_json(os.path.join(h.out("replay-verdict"), "manifest.json"), m)
    r = h.run(["--replay", tampered])
    if r.returncode != 1 or "replay: MISMATCH" not in r.stdout \
            or "the recorded run exited 1" not in r.stdout:
        return ["a replay whose exit code differs from the recorded one was not a "
                "MISMATCH: " + _fail_run(r)[0]]
    return []


def _e2e_input_errors(h):
    """Stage 1 guardrails reject bad input loudly (STAGE 1 FAILED, status
    input_error, report + manifest + trace + gate-report, nothing else); an
    unknown --persona is an input error (the maker would silently swap in
    the house persona), a display-name/case variant resolves to its key."""
    import os
    probs = []
    for tag, args, want in (
            ("blank", ["   "], "STAGE 1 FAILED (route): empty prompt"),
            ("persona", [E2E_PROMPT, "--presenter", "ai", "--persona", "nobody"],
             "STAGE 1 FAILED (route): unknown --persona 'nobody'")):
        out = h.out("input-" + tag)
        r = h.run(args + ["--out-dir", out])
        if r.returncode != 1 or want not in r.stdout:
            probs.append(f"{tag}: want exit 1 + {want!r}: " + _fail_run(r)[0])
            continue
        left = sorted(os.listdir(out))
        if left != ["gate-report.json", "manifest.json", "trace.jsonl",
                    "validation-report.md"]:
            probs.append(f"{tag}: input error left {left}")
            continue
        gr = _load(os.path.join(out, "gate-report.json"))
        if (gr.get("status"), (gr.get("failed_stage") or {}).get("n")) != ("input_error", 1):
            probs.append(f"{tag}: gate-report status {gr.get('status')}, "
                         f"failed_stage {gr.get('failed_stage')}")
    if "normal" in h.state:
        out = h.out("input-persona-case")
        r = h.run([E2E_PROMPT, "--presenter", "ai", "--persona", " MAYA ", "--out-dir", out])
        if r.returncode != 0:
            return probs + ["--persona ' MAYA ': " + _fail_run(r)[0]]
        with open(os.path.join(out, "script.json"), "rb") as f:
            a = f.read()
        with open(os.path.join(h.state["normal"], "script.json"), "rb") as f:
            b = f.read()
        if a != b:
            probs.append("--persona ' MAYA ' did not resolve to the house persona 'maya'")
    return probs


def _e2e_json(h):
    import json
    out = h.out("json")
    r = h.run([E2E_PROMPT, "--presenter", "ai", "--out-dir", out, "--json"])
    try:
        d = json.loads(r.stdout)
    except ValueError as e:
        return [f"--json stdout is not one JSON document: {e}: {r.stdout[:200]!r}"]
    probs = []
    for k in JSON_KEYS:
        if k not in d:
            probs.append(f"--json summary lacks {k!r}")
    if d.get("status") != "pass" or d.get("exit_code") != r.returncode or r.returncode:
        probs.append(f"--json status {d.get('status')} exit {d.get('exit_code')}/{r.returncode}")
    if "# Validation report" in r.stdout:
        probs.append("--json also printed the report text")
    if d.get("artifacts") != list(E2E_ARTIFACTS):
        probs.append(f"--json artifacts {d.get('artifacts')} (want all {len(E2E_ARTIFACTS)})")
    stages = d.get("stages") or []
    if len(stages) != 10 or not all(isinstance(s, str) for s in stages):
        probs.append(f"--json stages: {stages}")
    ss = d.get("script_summary") or {}
    if [k for k in SUMMARY_KEYS if k not in ss]:
        probs.append(f"--json script_summary lacks {[k for k in SUMMARY_KEYS if k not in ss]}")
    if (d.get("winner") or {}).get("seed") != ss.get("candidate_seed") or d.get("failed_stage"):
        probs.append(f"--json winner {d.get('winner')} / failed_stage {d.get('failed_stage')}")
    return probs


def _e2e_malformed_pack(h):
    """A malformed pack is skipped with a warning; the output is unchanged."""
    import json
    import os
    learned = h.learned("malformed")
    _write_json(os.path.join(learned, "hook_packs", "00-bad.json"), "{not json")
    _write_json(os.path.join(learned, "hook_packs", "01-list.json"), "[1]")
    out = h.out("malformed")
    r = h.run([E2E_PROMPT, "--presenter", "ai", "--candidates", "1", "--out-dir", out],
              learned=learned)
    if r.returncode != 0:
        return _fail_run(r)
    probs = []
    if "00-bad.json" not in r.stderr or "learned: hook pack 00-bad.json" not in r.stdout:
        probs.append("malformed pack not reported (stderr + warnings section)")
    with open(os.path.join(out, "script.json"), encoding="utf-8") as f:
        s = json.load(f)
    if "parity_script" in h.state and s != h.state["parity_script"]:
        probs.append("a malformed hook pack changed the script")
    if "hook_packs" in s:
        probs.append(f"script records hook_packs {s['hook_packs']} from bad packs")
    return probs


def _e2e_hook_pack_slots(h):
    """Only the approved, known-slot pack loads; its id is recorded. An
    approved pack whose template uses an unknown {slot} is rejected: the
    template never reaches HOOKS, the pack id is never recorded, and the
    rejection is on stderr and in the report's warnings section."""
    import json
    import os
    import re
    learned = h.learned("packs")
    hp = os.path.join(learned, "hook_packs")
    _write_json(os.path.join(hp, "a-ok.json"), {
        "schema_version": 1, "id": "selftest-approved", "status": "approved",
        "families": {"curiosity-gap": ["Here's the {category} test nobody runs."]}})
    _write_json(os.path.join(hp, "b-slot.json"), {
        "schema_version": 1, "id": "selftest-unknown-slot", "status": "approved",
        "families": {"curiosity-gap": ["Meet {brandname}, the fix."]}})
    _write_json(os.path.join(hp, "c-proposed.json"), {
        "schema_version": 1, "id": "selftest-proposed", "status": "proposed",
        "families": {"curiosity-gap": ["The {category} nobody tested."]}})
    out = h.out("packs")
    r = h.run([E2E_PROMPT, "--presenter", "ai", "--candidates", "1", "--out-dir", out],
              learned=learned)
    if r.returncode != 0:
        return _fail_run(r)
    probs = []
    with open(os.path.join(out, "script.json"), encoding="utf-8") as f:
        raw = f.read()
    s = json.loads(raw)
    if s.get("hook_packs") != ["selftest-approved"]:
        probs.append(f"script hook_packs {s.get('hook_packs')} (want ['selftest-approved'])")
    if "brandname" in raw:
        probs.append("the unknown {brandname} slot reached script.json")
    if "unknown slot(s) {brandname}" not in r.stderr:
        probs.append("unknown-slot template not rejected with a stderr warning")
    if not re.search(r"^- learned: hook pack b-slot\.json: .*unknown slot\(s\) \{brandname\}",
                     r.stdout, re.M):
        probs.append("unknown-slot rejection missing from the report's warnings section")
    with open(os.path.join(out, "manifest.json"), encoding="utf-8") as f:
        m = json.load(f)
    hp = (m.get("learned") or {}).get("hook_packs") or {}
    if hp.get("loaded") != ["selftest-approved"]:
        probs.append("manifest learned.hook_packs.loaded is wrong")
    if sorted(hp.get("files") or {}) != ["a-ok.json", "b-slot.json", "c-proposed.json"] \
            or not all(hp["files"].values()):
        probs.append(f"manifest learned.hook_packs.files not hashed: {hp.get('files')}")
    return probs


def _strong_priors():
    """A global priors table with n >= 3 for every hook family (so every
    quality tie across families is steered)."""
    import viral_script_maker as vsm
    fams = sorted(set(vsm.HOOKS) | {"challenge", "listicle"})
    ab = [(40, 8), (8, 40), (22, 20), (30, 12), (12, 30), (18, 18)]
    return {f: {"alpha": ab[i % len(ab)][0], "beta": ab[i % len(ab)][1], "n": 50}
            for i, f in enumerate(fams)}


def _e2e_priors(h):
    """Priors through the real CLI: the pick is steered (priors_used), the
    same priors file gives byte-identical script.json in separate processes
    with different hash seeds, the manifest pins the file's sha256,
    --replay reproduces it (the recorded VSP_LEARNED_DIR is pinned), and
    VSP_NO_PRIORS=1 restores the no-priors output byte for byte."""
    import hashlib
    import os
    learned = h.learned("priors")
    pri = _write_json(os.path.join(learned, "priors.json"),
                      {"schema_version": 1, "metric": "hook_rate",
                       "families": {}, "global": _strong_priors()})
    with open(pri, "rb") as f:
        pri_sha = hashlib.sha256(f.read()).hexdigest()
    raws, outs = [], []
    for hs in ("0", "1"):
        out = h.out("priors-hashseed-" + hs)
        r = h.run([E2E_PROMPT, "--presenter", "ai", "--out-dir", out],
                  learned=learned, env={"PYTHONHASHSEED": hs})
        if r.returncode != 0:
            return _fail_run(r)
        with open(os.path.join(out, "script.json"), "rb") as f:
            raws.append(f.read())
        outs.append(out)
    probs = []
    if raws[0] != raws[1]:
        probs.append("same seed + same priors file gave different script.json "
                     "across processes (PYTHONHASHSEED 0 vs 1)")
    import json
    s = json.loads(raws[0].decode("utf-8"))
    if "priors_used" not in s:
        probs.append("priors never steered the pick (check is vacuous)")
    lp = (_load(os.path.join(outs[0], "manifest.json")).get("learned") or {}).get("priors") or {}
    if lp.get("sha256") != pri_sha or not lp.get("valid") or lp.get("disabled"):
        probs.append(f"manifest learned.priors does not pin the file: {lp}")
    r = h.run(["--replay", os.path.join(outs[0], "manifest.json")])
    if r.returncode != 0 or "replay: OK" not in r.stdout:
        probs.append("--replay of a priors-steered run did not reproduce it: "
                     + _fail_run(r)[0])
    if "normal" in h.state:
        out = h.out("priors-off")
        r = h.run([E2E_PROMPT, "--presenter", "ai", "--out-dir", out],
                  learned=learned, env={"VSP_NO_PRIORS": "1"})
        if r.returncode != 0:
            return probs + _fail_run(r)
        with open(os.path.join(out, "script.json"), "rb") as f:
            off = f.read()
        with open(os.path.join(h.state["normal"], "script.json"), "rb") as f:
            base = f.read()
        if off != base:
            probs.append("VSP_NO_PRIORS=1 output != the no-priors run's script.json")
    return probs


# A child that runs pipeline.main() with viral_script_maker.generate wrapped
# to inject one defect into EVERY candidate: argv = repo, mode, pipeline args.
# "repairable": a parenthetical staging note in a spoken line (D44, which
# vsp.repair strips); "unrepairable": an invented price in the caption (D37,
# never repaired).
_INJECT_CODE = r"""
import sys
repo, mode = sys.argv[1], sys.argv[2]
sys.path.insert(0, repo)
import viral_script_maker as vsm
_generate = vsm.generate
def generate(*a, **k):
    s = _generate(*a, **k)
    if mode == "repairable":
        b = next(b for b in s["beats"][2:] if b.get("dialogue"))
        b["dialogue"] = "(smiling) " + b["dialogue"]
    else:
        s["caption"] = s["caption"] + " Only $19."
    return s
vsm.generate = generate
import pipeline
sys.argv = ["pipeline.py"] + sys.argv[3:]
pipeline.main()
"""


def _e2e_repair(h):
    """Stage 6: nothing passes gate 1 -> the rule-keyed repair fixes the
    best failing candidate -> the run ships with every artifact."""
    import os
    out = h.out("repair")
    r = h.py(_INJECT_CODE, args=(h.repo, "repairable", E2E_PROMPT, "--presenter", "ai",
                                 "--candidates", "3", "--out-dir", out))
    if r.returncode != 0:
        return _fail_run(r)
    probs = []
    st = _stage_lines(r.stdout)
    if (st.get(4), st.get(5), st.get(6), st.get(9)) != ("FAIL", "FAIL", "OK", "OK"):
        probs.append(f"stage 4/5/6/9 statuses {st.get(4)}/{st.get(5)}/{st.get(6)}/{st.get(9)} "
                     "(want FAIL/FAIL/OK/OK)")
    if "gate 1 (script): PASS" not in r.stdout or "[D44]" not in r.stdout:
        probs.append("report lacks the repaired gate-1 PASS / the [D44] repair")
    missing = [f for f in E2E_ARTIFACTS if not os.path.isfile(os.path.join(out, f))]
    if missing:
        return probs + [f"missing artifacts after repair: {missing}"]
    gr = _load(os.path.join(out, "gate-report.json"))
    reps = gr.get("repairs") or []
    if (gr.get("selected") or {}).get("via") != "repair" or not reps \
            or not reps[-1].get("passed") or "D44" not in (reps[-1].get("rules") or []):
        probs.append(f"gate-report selected/repairs wrong: {gr.get('selected')} {reps}")
    with open(os.path.join(out, "script.json"), encoding="utf-8") as f:
        if "(smiling)" in f.read():
            probs.append("the repaired script.json still carries the staging note")
    return probs


def _e2e_loud_failure(h):
    """An unrepairable gate-1 failure fails loudly: exit 1, the later stages
    SKIPPED, report + script + manifest + trace + gate-report written, and
    every stale bundle/brief/export from an earlier run removed; --json
    reports the same failure."""
    import json
    import os
    import re
    out = h.out("loud-failure")
    os.makedirs(out)
    stale = ("bundle.md", "brief.md", "captions.srt", "captions.vtt", "captions.json",
             "shotlist.csv", "shots.json")
    for f in stale:
        with open(os.path.join(out, f), "w", encoding="utf-8") as fh:
            fh.write("stale from an earlier run\n")
    args = (h.repo, "unrepairable", E2E_PROMPT, "--presenter", "ai", "--candidates", "2",
            "--out-dir", out)
    r = h.py(_INJECT_CODE, args=args)
    probs = []
    if r.returncode != 1:
        return _fail_run(r)
    st = _stage_lines(r.stdout)
    want = {4: "FAIL", 5: "FAIL", 6: "FAIL", 7: "SKIPPED", 8: "SKIPPED", 9: "SKIPPED",
            10: "OK"}
    if any(st.get(n) != s for n, s in want.items()):
        probs.append(f"stage statuses {st} (want {want} for 4-10)")
    if not re.search(r"^gate 1 \(script\): FAIL — D37: ", r.stdout, re.M):
        probs.append("report lacks the legacy 'gate 1 (script): FAIL — D37: …' line")
    left = sorted(os.listdir(out))
    if left != sorted(["script.json", "validation-report.md", "manifest.json",
                       "trace.jsonl", "gate-report.json"]):
        probs.append(f"failing run left {left}")
    gr = _load(os.path.join(out, "gate-report.json"))
    m = _load(os.path.join(out, "manifest.json"))
    if (gr.get("status"), gr.get("exit_code"), (gr.get("failed_stage") or {}).get("n"),
            (gr.get("selected") or {}).get("via")) != ("gate1_fail", 1, 4, "best_failing"):
        probs.append(f"gate-report status/exit/failed_stage/via: {gr.get('status')}/"
                     f"{gr.get('exit_code')}/{gr.get('failed_stage')}/{gr.get('selected')}")
    if (m.get("status"), m.get("exit_code")) != ("gate1_fail", 1) \
            or not (m.get("outputs") or {}).get("script.json"):
        probs.append(f"manifest status/exit {m.get('status')}/{m.get('exit_code')}")
    out2 = h.out("loud-failure-json")
    r = h.py(_INJECT_CODE, args=args[:-1] + (out2, "--json"))
    try:
        d = json.loads(r.stdout)
    except ValueError as e:
        return probs + [f"--json on a failing run is not one JSON document: {e}: "
                        f"{r.stdout[:200]!r}"]
    if (r.returncode, d.get("status"), d.get("exit_code"), d.get("failed_stage")) != \
            (1, "gate1_fail", 1, "gate 1"):
        probs.append(f"--json failure: exit {r.returncode}, {d.get('status')}/"
                     f"{d.get('exit_code')}/{d.get('failed_stage')}")
    if not any(str(x).startswith("D37") for x in (d.get("gates") or {}).get("gate1") or []):
        probs.append(f"--json gates.gate1 lacks D37: {d.get('gates')}")
    return probs


# ---------------------------------------- WS-EVAL: v2.1 creative modules e2e
CREATIVE_MODULES = (("vsp.direction", "direction"),
                    ("vsp.hooks", "hook_variants"),
                    ("vsp.discovery", "discovery"))
CREATIVE_PROMPTS = ("portable door lock", "electric milk frother", "silk pillowcase")
_CREATIVE_GEN_CODE = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
import viral_script_maker as vsm
out = []
for prompt in json.loads(sys.argv[2]):
    for pr in ("human", "ai"):
        for fmt, du in (("demo", 30), ("review", 15)):
            for sd in (1, 2):
                s = vsm.generate(prompt, presenter=pr, fmt=fmt, duration=du, seed=sd)
                out.append([[prompt, pr, fmt, du, sd], json.loads(json.dumps(s))])
sys.stdout.write("\n@@CREATIVE@@" + json.dumps(out))
"""


def _e2e_creative_keys(h):
    """When vsp.direction / vsp.hooks / vsp.discovery exist (find_spec),
    every generated script carries their keys, passes D154-D156 and has no
    creative_warnings — both the normal CLI run's script.json and a direct
    maker matrix (3 prompts x 2 presenters x demo/30 s + review/15 s x 2
    seeds) in a hermetic child. Skipped (noted) when none exists."""
    import importlib.util
    import json
    import os
    from vsp import rules
    present = []
    for mod, key in CREATIVE_MODULES:
        try:
            spec = importlib.util.find_spec(mod)
        except (ImportError, ValueError):
            spec = None
        if spec is not None:
            present.append((mod, key))
    if not present:
        h.state.setdefault("notes", []).append(
            "e2e-creative-keys skipped (no vsp.direction/hooks/discovery)")
        return []
    r = h.py(_CREATIVE_GEN_CODE, args=(h.repo, json.dumps(list(CREATIVE_PROMPTS))))
    blob = r.stdout.rsplit("@@CREATIVE@@", 1)
    if r.returncode != 0 or len(blob) != 2:
        return [f"creative matrix child failed: exit {r.returncode}\n"
                f"{r.stdout[-300:]}{r.stderr[-500:]}"]
    scripts = json.loads(blob[1])
    if "normal" in h.state:
        scripts.append([["normal CLI run"], _load(os.path.join(h.state["normal"],
                                                                "script.json"))])
    probs = []
    for meta, s in scripts:
        tag = " ".join(str(x) for x in meta)
        miss = [key for _, key in present if key not in s]
        if miss:
            probs.append(f"{tag}: no {miss} although "
                         f"{[m for m, k in present if k in miss]} exist")
        if s.get("creative_warnings"):
            probs.append(f"{tag}: creative_warnings {s['creative_warnings'][:2]}")
        ctx = rules.build_ctx(s)
        for fn in (rules.check_d154, rules.check_d155, rules.check_d156,
                   rules.check_d158):
            msgs = fn(s, None, ctx)
            if msgs:
                probs.append(f"{tag}: {msgs[:2]}")
    h.state.setdefault("notes", []).append(
        f"e2e-creative-keys: {len(scripts)} scripts x {[m for m, _ in present]}")
    return probs[:12] + ([f"+{len(probs) - 12} more"] if len(probs) > 12 else [])


def e2e_checks():
    return [("e2e-normal-run", _e2e_normal),
            ("e2e-candidates-1-seed-parity", _e2e_parity),
            ("e2e-replay-reproduces", _e2e_replay),
            ("e2e-json-summary", _e2e_json),
            ("e2e-malformed-hook-pack-ignored", _e2e_malformed_pack),
            ("e2e-hook-pack-unknown-slot-rejected", _e2e_hook_pack_slots),
            ("e2e-priors-deterministic", _e2e_priors),
            ("e2e-repair-stage-6", _e2e_repair),
            ("e2e-failing-run-is-loud", _e2e_loud_failure),
            ("e2e-stage-1-input-errors", _e2e_input_errors),
            # WS-EVAL (pipeline v2.1): skipped until the modules exist
            ("e2e-creative-keys", _e2e_creative_keys)]


# modules other workstreams own; each may expose selfcheck() -> (ok, lines)
# (v2.1: the creative-layer modules, run when present like the v2 ones)
OPTIONAL_SELFCHECKS = ("vsp.ingest", "vsp.feedback", "vsp.improve",
                       "vsp.direction", "vsp.hooks", "vsp.discovery", "vsp.shotplan")
