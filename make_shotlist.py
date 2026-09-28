#!/usr/bin/env python3
"""make_shotlist.py — turn a viral_script_maker JSON into a shot list + Antigravity brief.

Standing rule (2026-09-27, user order): every script made for use ships as a
bundle — script JSON + shot list + Antigravity prompt. This generator makes
that automatic.

Usage:
    python3 make_shotlist.py script.json [--out bundle.md]

Reads the maker JSON, maps each beat to a shot (camera/framing/action/
on-screen text/VO/delivery), enforces the B4a keyword-CTA template
(follow -> keyword -> payload), and emits the Antigravity brief per the
standing template (DELIVERABLE block verbatim).
"""
import json, re, sys, os

BEAT_SHOT_DIRECTION = {
    "VISUAL TRIGGER": "Frame-0 composition, static or micro push-in. High contrast, readable with sound off.",
    "VERBAL HOOK + LOCK": "Medium close-up, direct to camera, eye-level. Brisk and confident.",
    "IMPERFECTION BEAT": "Same framing, slightly looser — faint handheld feel. Candid, unpolished read.",
    "EDUCATION BEAT": "Product macro / B-roll over VO, or presenter with prop in hand. Unhurried, warm.",
    "DEMO BEAT": "Over-shoulder or mirror POV, mid-action framing. Presenter does the thing live, no fakes.",
    "EVIDENCE BEAT": "Timestamped split-screen / side-by-side. Same subject, same light. Slow — let the result land.",
    "PAYOFF": "Presenter to camera, product in hand. Slow push-in through the beat — the camera leans in as the proof lands. Slow down. No scripted laugh.",
    "COMMENT BAIT": "On-screen keyword text + presenter CTA to camera.",
    "CTA": "Brisk close-up. 160-180 wpm. Clean end card beat.",
}

DELIVERABLE = (
    "Render the FULL video as one long uncut master: everything you generated,\n"
    "no trims, no pre-cutting, no tightening. Deliver that long master as the\n"
    "deliverable. Marlowe cuts the 2-3 variants from it on the variant stage.\n"
    "If there is a voiceover, also send words.json (word-level timings).\n"
    "Captioning and variant cuts are Marlowe's stages \u2014 do not pre-apply them."
)

RENDER_SPEC = (
    "9:16 vertical, 1080x1920, 30fps, H.264 mp4. "
    "Files: <slug>-master.mp4 + <slug>-words.json (word-level timings as "
    '{"words": [{"word": str, "start": float_seconds, "end": float_seconds}], '
    '"duration_s": float}).'
)

DO_NOT = (
    "Do NOT burn in captions/subtitles (Marlowe's stage). No watermarks or logos. "
    "No stock-footage look \u2014 shoot it like real UGC. No robotic TTS \u2014 human voice only. "
    "No letterbox/pillarbox. No pre-cutting or tightening (see DELIVERABLE)."
)

NICHE_VIEWER = {
    "beauty": "women 18-34 into hair/makeup routines",
    "fitness": "adults 20-40 starting or restarting training",
    "pets": "pet owners 20-45",
    "kitchen": "home cooks 22-45",
    "tech": "gadget buyers 18-40",
    "fashion": "style-conscious 16-34",
}

# D64 (2026-09-27): model-followable brief assets. The identity lock is the
# highest-leverage piece — without it the video model invents a new person per
# shot. One locked description per (presenter, niche); used VERBATIM in every
# shot prompt. Product/setting/style maps are concrete-visual, never brand
# claims (D37: no invented branding).
PRESENTER_IDENTITY = {
    ("human", "beauty"): "a woman in her late 20s with medium-length dark brown hair worn down, natural makeup, wearing a casual beige knit top",
    ("human", "fitness"): "a man in his early 30s with an athletic build and short dark hair, wearing a plain black t-shirt",
    ("human", "kitchen"): "a woman in her mid-30s with shoulder-length brown hair tied back, light makeup, wearing a plain sage-green t-shirt",
    ("human", "pets"): "a woman in her late 20s with a blonde ponytail and light makeup, wearing a plain white t-shirt",
    ("human", "tech"): "a man in his late 20s with short black hair and glasses, wearing a plain navy hoodie",
    ("human", "fashion"): "a woman in her mid-20s with long dark wavy hair, natural makeup, wearing a simple black top",
    ("human", "generic"): "a woman in her early 30s with shoulder-length brown hair, light makeup, wearing a plain white t-shirt",
    ("ai", "beauty"): "a photorealistic AI woman in her mid-20s with long black hair, dewy natural makeup, wearing a soft pink cardigan",
    ("ai", "fitness"): "a photorealistic AI man in his early 30s, athletic build, short dark hair, wearing a plain gray athletic shirt",
    ("ai", "generic"): "a photorealistic AI woman in her late 20s with dark hair tied back, natural look, wearing a plain gray crewneck",
}
PRODUCT_LOOK = {
    "wax": "a small twist-up solid hair-wax stick in a matte nude-beige tube about 10 cm long, cap on",
    "lamp": "a compact dome-shaped sunrise lamp in matte white about 15 cm wide, glowing warm",
    "projector": "a compact mini projector, matte dark-gray rounded box about 12 cm wide with a front lens",
    "fan": "a small portable neck fan, matte white U-shaped band that sits around the neck",
    "trash": "a small car trash can with a lid, matte black cylinder about 18 cm tall",
    "frother": "a handheld electric milk frother, slim matte-black wand about 20 cm long with a steel whisk head",
    "generic": "the product from the concept, plain and unbranded, true to its real-world shape and size",
}
NICHE_SETTING = {
    # niche -> (setting, light)
    "beauty": ("bathroom vanity with a large mirror", "soft natural window light from the left"),
    "fitness": ("a bright home gym corner", "bright daylight"),
    "kitchen": ("a clean modern kitchen counter", "bright daylight"),
    "pets": ("a cozy living room", "soft natural daylight"),
    "tech": ("a tidy modern desk setup", "soft daylight with a warm desk lamp glow"),
    "fashion": ("a bright bedroom with a full-length mirror", "soft natural window light"),
    "generic": ("a clean modern home interior", "soft natural daylight"),
}
NICHE_STYLE_NOTES = {
    "beauty": ["Maximum-contrast before/after is the genre's currency — make the transformation unmistakable.",
               "Motion toward the camera reads as confidence; stillness reads as ad."],
    "fitness": ["Sweat and effort are the proof — never shoot the workout looking fresh."],
    "kitchen": ["Steam, sizzle, and close-up texture carry the genre — shoot the food, not the cook."],
    "generic": ["Fast cold open, proof before pitch — the first frame must work with sound off."],
}
SHOT_CAMERA = {
    "VISUAL TRIGGER": "Camera: static frame with a micro push-in.",
    "VERBAL HOOK + LOCK": "Camera: medium close-up, eye-level, static.",
    "IMPERFECTION BEAT": "Camera: faint handheld feel, slightly loose framing.",
    "EDUCATION BEAT": "Camera: slow drift over the detail.",
    "DEMO BEAT": "Camera: over-shoulder, follows the action.",
    "EVIDENCE BEAT": "Camera: locked-off, identical framing.",
    "PAYOFF": "Camera: slow push-in through the beat.",
    "COMMENT BAIT": "Camera: slow push-in toward the phone.",
    "CTA": "Camera: brisk close-up, static.",
    "REJECTION HISTORY": "Camera: medium close-up, static.",
}

def shot_visual_prompt(sh, identity, product_desc, setting, light):
    """D64: one self-contained visual prompt per shot — no cross-shot references."""
    beat = sh["beat"].replace(" (cont.)", "")
    detail = re.sub(r"\s*\(VO continues\)", "", sh.get("direction", "")).strip().rstrip(".")
    # D64: strip cross-shot references the model cannot resolve ("same framing"
    # points at a shot it never saw — each prompt must stand alone)
    detail = re.sub(r"(?i)^same framing,\s*", "", detail)
    camera = SHOT_CAMERA.get(beat, "Camera: static.")
    return (f"{identity}. {detail}. Setting: {setting}. Light: {light}. {camera} "
            f"Photorealistic, 9:16 vertical. Any on-screen text is bold sans, high contrast.")

def niche_references(niche, k=3):
    """Top-k reels by likes in this niche: url + one-line why. Anchors the quality bar."""
    try:
        import sqlite3
        db = sqlite3.connect(os.path.expanduser("~/workspace/viral-research/viral.db"))
        rows = db.execute(
            "SELECT url, username, like_count, substr(notes,1,110) FROM reels "
            "WHERE niche LIKE ? AND url IS NOT NULL AND url != '' "
            "ORDER BY like_count DESC LIMIT ?", ("%"+niche+"%", k)).fetchall()
        db.close()
        out = []
        for url, user, likes, notes in rows:
            out.append(f"- {url} (@{user}, {likes or 0:,} likes) — {(notes or '').strip()}")
        if not out:
            # fallback: niche absent from the DB (e.g. gadgets) — anchor on the
            # top reels overall rather than shipping unanchored
            db = sqlite3.connect(os.path.expanduser("~/workspace/viral-research/viral.db"))
            rows = db.execute(
                "SELECT url, username, like_count, substr(notes,1,110) FROM reels "
                "WHERE url IS NOT NULL AND url != '' "
                "ORDER BY like_count DESC LIMIT ?", (k,)).fetchall()
            db.close()
            for url, user, likes, notes in rows:
                out.append(f"- {url} (@{user}, {likes or 0:,} likes) — {(notes or '').strip()}")
        return out
    except Exception:
        return []

def parse_t(t):
    m = re.findall(r"(\d+(?:\.\d+)?)", t or "")
    return (float(m[0]), float(m[1])) if len(m) >= 2 else (0.0, 0.0)

def main():
    src = sys.argv[1]
    d = json.load(open(src))
    items = []
    for h in d.get("hook_stack", []) or []:
        items.append(("HOOK", h.get("type", ""), h))
    for b in d.get("beats", []) or []:
        items.append(("BEAT", b.get("type", ""), b))

    # sort by start time; clamp overlaps into a clean sequence
    items.sort(key=lambda x: parse_t(x[2].get("t", ""))[0])
    shots, vo_lines, cursor = [], [], 0.0
    for kind, btype, it in items:
        s, e = parse_t(it.get("t", ""))
        s = max(s, cursor); e = max(e, s + 0.5); cursor = e
        dialogue = it.get("dialogue", "").strip()
        # hook beats often lack a time window: size it to fit the dialogue
        # (a fixed 0.5s default crams e.g. "Look at this." into an unperformable window)
        if dialogue:
            e = max(e, s + len(dialogue.split()) / 3.0 + 0.3); cursor = e
        direction = BEAT_SHOT_DIRECTION.get(btype, "Presenter to camera.")
        on_screen = it.get("on_screen", "").strip()
        delivery = it.get("delivery", "").strip()
        rehook = it.get("rehook", "").strip()
        # B4a enforcement: keyword CTA must open with the follow ask
        if btype == "COMMENT BAIT" and dialogue and "follow" not in dialogue.lower():
            kw = re.search(r'[Cc]omment\s+([A-Z]+)', dialogue)
            kw = kw.group(1) if kw else "LINK"
            dialogue = f"Hit follow, comment {kw}, and I\u2019ll send it to you. " + dialogue
            it = dict(it, dialogue=dialogue)
        if dialogue:
            # D43: dialogue-time fit sanity check — brisk ~2.5 wps, slow ~2.0 wps
            slow = any(k in (delivery or "").lower() for k in ("slow down", "unhurried", "never rushed"))
            wps = 2.5 if slow else 3.0
            need = len(dialogue.split()) / wps
            have = e - s
            flag = f"  <-- D43 WARNING: ~{need:.1f}s of speech in a {have:.1f}s window" if need > have * 1.15 else ""
            vo_lines.append(f"[{s:.1f}-{e:.1f}s] {dialogue}{flag}")
        if rehook:
            # D44: re-hooks are spoken transitions — they belong in the transcript
            vo_lines.append(f"[{e:.1f}s] (spoken transition) {rehook}")
        shots.append({
            "n": len(shots) + 1, "t": f"{s:.1f}\u2013{e:.1f}s",
            "s": s, "e": e,
            "beat": btype, "direction": it.get("shot_direction", it.get("direction", direction)),
            "on_screen": on_screen, "dialogue": dialogue,
            "delivery": delivery, "rehook": rehook,
            "match_cut": it.get("match_cut", "").strip(),
        })

    # D48: auto-split long static shots into sub-shots with framing rotation
    SUBSHOT_FRAMING = [
        "tight macro detail — product texture/label in frame",
        "mid-action — hands + product doing the thing",
        "presenter cutaway — reaction/nod, keeps a human face in the edit",
    ]
    SPLITTABLE = ("EDUCATION BEAT", "DEMO BEAT", "EVIDENCE BEAT")
    final_shots = []
    for sh in shots:
        dur = sh["e"] - sh["s"]
        if sh["beat"] in SPLITTABLE and dur > 3.5:
            k = max(2, round(dur / 2.0))
            step = dur / k
            for i in range(k):
                ss, se = sh["s"] + i * step, sh["s"] + (i + 1) * step
                final_shots.append({
                    "n": f"{sh['n']}{chr(97 + i)}",
                    "t": f"{ss:.1f}\u2013{se:.1f}s",
                    "beat": sh["beat"] + (" (cont.)" if i else ""),
                    "direction": SUBSHOT_FRAMING[i % len(SUBSHOT_FRAMING)] + " (VO continues)",
                    "on_screen": sh["on_screen"] if i == 0 else "",
                    "dialogue": sh["dialogue"] if i == 0 else "",
                    "delivery": "", "rehook": "",
                    "match_cut": sh["match_cut"] if i == k - 1 else "",
                })
        else:
            final_shots.append(sh)
    shots = final_shots

    slug = re.sub(r"[^a-z0-9]+", "-", d.get("prompt", "script").lower()).strip("-")
    out = sys.argv[2] if len(sys.argv) > 2 else f"outputs/{slug}-bundle.md"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

    # D64: model-followable brief assets — computed once, reused verbatim.
    # Persona-loop x pipeline (2026-09-28): the script's locked persona identity
    # wins over the per-niche map — ONE face across every video (Q2/F10: drift
    # triggers eerie rejection; F9: same-face repetition builds liking).
    _persona = d.get("persona") or {}
    if d.get("presenter") == "ai" and _persona.get("identity"):
        presenter_identity = _persona["identity"]
    else:
        presenter_identity = PRESENTER_IDENTITY.get(
            (d.get("presenter", "human"), d.get("niche", "")),
            PRESENTER_IDENTITY[("human", "generic")])
    prompt_low = (d.get("prompt", "") + " " + d.get("niche", "")).lower()
    product_desc = next((v for k, v in PRODUCT_LOOK.items() if k in prompt_low),
                        PRODUCT_LOOK["generic"])
    setting_desc, light_desc = NICHE_SETTING.get(d.get("niche", ""), NICHE_SETTING["generic"])
    style_notes = NICHE_STYLE_NOTES.get(d.get("niche", ""), NICHE_STYLE_NOTES["generic"])

    L = []
    L.append(f"# Production bundle — {d.get('prompt')}")
    L.append(f"niche: {d.get('niche')} | presenter: {d.get('presenter')} | format: {d.get('format')} | "
             f"duration: {d.get('duration_s')}s | hook family: {d.get('hook_family')}")
    L.append("")
    L.append("## Shot list")
    for sh in shots:
        L.append(f"### Shot {sh['n']} ({sh['t']}) — {sh['beat']}")
        L.append(f"- Camera: {sh['direction']}")
        if sh["on_screen"]: L.append(f"- On-screen text: {sh['on_screen']}")
        if sh["dialogue"]: L.append(f"- Dialogue/VO: \"{sh['dialogue']}\"")
        if sh["delivery"]: L.append(f"- Delivery: {sh['delivery']}")
        if sh["rehook"]: L.append(f"- Re-hook into next: \"{sh['rehook']}\"")
        if sh["match_cut"]: L.append(f"- Match-cut: {sh['match_cut']}")
        L.append("")
    L.append("## Antigravity brief")
    L.append("")
    # D64 (2026-09-27, user verdict: "the video model did not follow the script
    # because it was too bad of a prompt"): the old brief was a production
    # document, not a generatable prompt — no identity lock (the model invented
    # a new person every shot), cross-shot references it cannot resolve ("same
    # framing"), workflow instructions mixed with generation instructions, and
    # asks it cannot fulfill (watch reference URLs, pick trending sounds, emit
    # words.json from audio it didn't synthesize). The brief is now structured
    # as MODEL PROMPTS FIRST: a locked presenter identity repeated verbatim in
    # every shot, one self-contained visual prompt per shot (subject + action +
    # setting + light + camera — no cross-references), a concrete product block,
    # a negative prompt, and the voiceover isolated as a separate audio track.
    # Everything the pipeline does (not the model) lives under WORKFLOW.
    L.append("> HOW TO READ THIS BRIEF: the SHOT PROMPTS are your generation")
    L.append("> instructions — one self-contained prompt per shot. The VOICEOVER is")
    L.append("> a separate audio track, never on-screen text. Everything under")
    L.append("> WORKFLOW is for the production pipeline, not for generation.")
    L.append("")
    L.append("## PRESENTER — identity lock")
    L.append(f"{presenter_identity} — use this exact description in every shot "
             "prompt below. Same person, same hair, same outfit in ALL shots. "
             "Never redesign the presenter between shots.")
    L.append("")
    if d.get("presenter") == "ai":
        # Persona-loop x pipeline (2026-09-28): fidelity rules distilled from the
        # AI-persona persuasion dossier — the video model must not "improve" her.
        _pname = (_persona.get("name") or "the AI persona")
        L.append("## PERSONA — fidelity rules (do not redesign her)")
        L.append(f"- {_pname} is a recurring character. Render the identity above EXACTLY in every shot of THIS video and keep her recognizably identical across videos in the series — face, hair, outfit, age. Identity drift reads as fake and triggers rejection (dossier Q2/F10).")
        L.append("- Neutral, non-sexualized presentation — natural look, modest plain clothing as described. Sexualized styling damages brand attitude and purchase intent (dossier Q1/F6).")
        L.append("- Casting is neutral by design: attractiveness has no direct effect on purchase intent — credibility and product fit do the work (dossier Q1/F2). Do not beautify, glam up, or youth-shift her beyond the description.")
        L.append("- On-screen small \"AI persona\" label from FRAME 0, top safe zone, minimum 2 seconds, separate from hook text. Disclosure costs nothing on reach and omission costs trust (dossier Q7/F130).")
        L.append("- Funnel note: AI personas convert indirectly — this video's job is loyal-core building (follow, community, familiarity), not hard-sell. Keep the CTA warm, never pressuring (dossier Q10/F56, F49).")
        L.append("")
    L.append("## PRODUCT")
    L.append(f"{product_desc}. Match this exactly in every shot it appears in. "
             "Do not invent logos, brand names, or label text — plain unbranded packaging.")
    L.append("")
    L.append("## SHOT PROMPTS (self-contained — generate each shot from its own prompt only)")
    for sh in shots:
        L.append(f"#### Prompt — Shot {sh['n']} ({sh['t']})")
        L.append(f"VISUAL PROMPT: {shot_visual_prompt(sh, presenter_identity, product_desc, setting_desc, light_desc)}")
        if sh["on_screen"]:
            L.append(f"ON-SCREEN TEXT (render exactly, bold sans, high contrast): {sh['on_screen']}")
        if sh["dialogue"]:
            L.append(f"AUDIO (voiceover for this shot — audio only, never on-screen text): \"{sh['dialogue']}\"")
            if sh["delivery"]:
                L.append(f"DELIVERY: {sh['delivery']}")
        else:
            L.append("AUDIO: no dialogue — visuals only (voiceover continues from previous shot if mid-sentence).")
        if sh["rehook"]:
            L.append(f"SPOKEN TRANSITION into next shot (audio only): \"{sh['rehook']}\"")
        if sh["match_cut"]:
            L.append(f"EDIT NOTE: {sh['match_cut']}")
        L.append("")
    L.append("## VOICEOVER — separate audio track")
    L.append("AUDIO ONLY. Do not render any of these words as on-screen text, captions, "
             "or graphics. This is the spoken track laid over the shots above.")
    L.extend(vo_lines)
    L.append("")
    L.append("Voice spec: cast a conversational human read — like a real person talking "
             "to a friend, never an ad read. Female voice (default casting — swap as needed), "
             "warm and confident, never pressuring. Vary pace naturally: unhurried on trust "
             "beats, brisk 160–180 wpm on the CTA. Light natural imperfections welcome "
             "(breath, pace shifts, emphasis). Never monotone, never a polished commercial "
             "delivery. No scripted laughs/sighs.")
    L.append("")
    L.append("## STYLE")
    L.append(f"{d.get('presenter', 'human').capitalize()} UGC {d.get('format')}, {d.get('niche')} niche. 9:16 vertical. {setting_desc}. {light_desc}. "
             f"Imperfection welcome (flaws in the BEFORE, faint handheld in candid beats) — "
             f"polish kills trust in this format. "
             f"Transitions: hard cuts by default; match-cut on transformation beats. "
             f"On-screen graphic text (labels like BEFORE/AFTER, TEST 1): bold sans, high contrast, max 3 words per card. "
             f"Safe zones: keep graphic text and key action clear of the top 250px, bottom 320px (IG UI overlays), and the right rail. "
             f"Product accuracy: match the PRODUCT block above exactly — no invented branding. "
             f"Audio: voiceover clean and forward; neutral upbeat background music bed low underneath, ducked under speech.")
    for sn in style_notes:
        L.append(f"- {sn}")
    L.append("")
    L.append("## NEGATIVE PROMPT — never render")
    L.append("Warped faces, extra fingers or limbs, melted hands, garbled / misspelled / merged "
             "text, watermarks or logos, burned-in captions or subtitles, letterbox or pillarbox bars, "
             "plastic CGI skin, stock-photo stiffness. If any on-screen text cannot be rendered cleanly, "
             "drop the text and keep the shot — never ship garbled text.")
    L.append("")
    L.append("## Reference reels (human review — the quality bar)")
    L.append("The style notes above are distilled from these; the URLs are for human review, "
             "not for the model.")
    refs = niche_references(d.get("niche", ""))
    L.extend(refs if refs else ["- (no references found for this niche)"])
    L.append("")
    L.append("## Render spec")
    L.append(RENDER_SPEC)
    L.append("")
    L.append("## Do NOT")
    L.append(DO_NOT + " Do NOT render voiceover words as on-screen text.")
    L.append("")
    L.append("## Fallbacks")
    L.append("If any shot can't be rendered as specified, use the simpler version — never silently drop the beat. "
             "Shot 8 fallback: presenter holds phone showing a DM notification close-up, points at it. "
             "If on-screen phone/UI text renders garbled, use the fallback with the notification visible but no readable text required. "
             "Any product-macro fallback: clean product hero on a neutral surface, slow push-in.")
    L.append("")
    L.append("## WORKFLOW (production pipeline — not generation instructions)")
    L.append("Send a draft for review before the final render.")
    L.append("")
    L.append("Variant note: the cold-open cut uses Shots 1-2 as its opening — keep them self-contained. "
             "(Marlowe's variant stage.)")
    L.append("")
    L.append("## DELIVERABLE (standing)")
    L.append(DELIVERABLE)
    L.append("")
    L.append("words.json: if your pipeline synthesizes the voiceover, export word-level timings as "
             "<slug>-words.json; otherwise omit it — Marlowe's caption stage aligns separately.")
    L.append("")
    L.append("## Caption + hashtags (post as-is)")
    L.append(d.get("caption", ""))
    bundle = "\n".join(L)
    open(out, "w").write(bundle)
    print(f"wrote {out} ({len(shots)} shots)")
    print("=" * 60)
    print(bundle)

if __name__ == "__main__":
    main()
