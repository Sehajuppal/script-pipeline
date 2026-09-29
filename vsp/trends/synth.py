"""Trend synthesis: recipes that turn trend cards and outlier posts into
script directions in OUR vocabulary (vsp.creative_vocab ids, vsp.router
formats).

    synthesize(doc, observations, rows, niches, lanes, k, invent, now,
               memory=(), existing=()) -> [recipe]      ids assigned
    candidates(op, ctx, niche) -> [candidate]           one operator
    finalize(cand, ctx, lane, memory) -> recipe | None  (None = infeasible)
    novelty(tokens, memory), tokens_of(recipe), fingerprint(recipe)

Operators (each recipe carries a one-line rationale):
  ride        a rising/emerging trend in our niche: keep 2 of its 4
              elements (message, hashtags, sonic identity, visual
              narrative), change 2 (TikTok Trend Digest)
  transplant  a format winning (median >= 3x) in another niche, moved to ours
  combine     format of trend A + hook archetype / emotion of trend B
  substitute  a small/medium creator's >= 5x post: same structure, our subject
  reverse     flip the expected payoff (result first, contrarian turn)
  serialize   a series / day-counter
  constrain   one rule: one take, 10 seconds, or no talking
  escalate    raise the stakes: a filmed torture test
  mashup      visual narrative of A + the sonic pattern of B (licensed audio)
  invent      an original trend: a conventional high-evidence format + an
              atypical participation mechanic + a high-arousal emotional core
              + a named signature (Uzzi 2013, Hekkert MAYA, Boden,
              Fauconnier & Turner), with a personalisation slot, a
              hypothesis and a Trial Reels test plan

score = evidence x velocity x novelty x feasibility, each in [0, 1]:
  evidence    1 - exp(-sum of the supporting posts' inspiration scores) —
              inspiration already weights small/medium creators up
  velocity    stage weight: emerging 1.0, rising 0.9, peak 0.6, steady 0.5,
              saturated 0.25, declining 0.1 (invented: its format's stage)
  novelty     1 - max token-Jaccard similarity to recipes already used
              (usage/used.jsonl) and to recipes picked earlier in this batch
  feasibility replicability x production cost x presenter lane (a
              needs-real-person recipe is infeasible for presenter=ai) x
              licensed-audio adaptation (a trending sound is only usable as
              a pattern over licensed music) x niche fit
Selection is greedy per (niche, lane) with novelty recomputed after each
pick and at most MAX_PER_OPERATOR recipes per operator, so a batch is
diverse. Everything is sorted explicitly: output never depends on
PYTHONHASHSEED or dict order.
"""
import hashlib
import json
import math
import re

from vsp import creative_vocab as CV
from vsp.trends import lifecycle as L
from vsp.trends import schema as S

EVIDENCE_SCALE = 1.0
MAX_PER_OPERATOR = 3
MAX_CARDS_PER_OP = 6
TRANSPLANT_MIN_MULTIPLE = 3.0
SUBSTITUTE_MIN_MULTIPLE = 5.0
TRANSPLANT_FIT = 0.8
FOREIGN_FIT = 0.85
ADVICE_NICHES = ("finance", "education", "commentary")
REPLICABILITY_FLOOR = 0.4
COST_FACTOR = {"low": 1.0, "med": 0.8, "high": 0.5}
UNKNOWN_COST_FACTOR = 0.85
LICENSED_AUDIO_FACTOR = 0.9
MIN_SCORE = 1e-4
HIGH_AROUSAL = ("awe", "humor", "surprise", "outrage", "fear", "tension")

ELEMENTS = ("message", "hashtags", "sonic identity", "visual narrative")
KEEP_BY_KIND = {"sound": ("message", "visual narrative"),
                "format": ("visual narrative", "message"),
                "tag": ("hashtags", "visual narrative"),
                "topic": ("message", "hashtags")}
KEEP_TEXT = {
    "message": "the message pattern (what the hook promises and how it pays off)",
    "hashtags": "the trend hashtag",
    "sonic identity": "the sound's pattern (tempo, drop timing) over a licensed track",
    "visual narrative": "the visual narrative (frame 0, beat order, reveal timing)",
}
CHANGE_TEXT = {
    "message": "the message: our subject, our words, our keyword",
    "hashtags": "the hashtags: our own niche keyword tags (at most 5 on Instagram)",
    "sonic identity": "the sonic identity: a licensed track with a similar tempo and "
                      "drop, never the original sound",
    "visual narrative": "the visual narrative: our own footage, setting and framing",
}
COMMON_ORIGINALITY = (
    "Our own footage and words: no reposts or re-uploads (Instagram removes repost-"
    "heavy accounts from recommendations; TikTok 2026 makes unoriginal content "
    "ineligible for For You)",
    "Nothing copied verbatim: no caption, overlay text or voiceover lifted from the "
    "examples",
)

EMOTION_VIBE = {"awe": "cinematic-premium", "humor": "playful-comedic",
                "surprise": "before-after-reveal", "relatable": "raw-ugc",
                "aspirational": "clean-aesthetic", "curiosity": "expert-trust",
                "satisfaction": "asmr-satisfying", "nostalgia": "cozy-calm",
                "outrage": "hype-energy", "fear": "expert-trust", "tension": "hype-energy"}
EMOTION_ARCHETYPE = {"awe": "showcase", "humor": "pov", "surprise": "curiosity-gap",
                     "relatable": "pov", "aspirational": "transformation",
                     "curiosity": "curiosity-gap", "satisfaction": "showcase",
                     "nostalgia": "question", "outrage": "contrarian-reframe",
                     "fear": "problem-agitate", "tension": "challenge"}
FORMAT_RULES = (
    (r"before-after|transformation|glow-up|makeover|then-now|after-reveal", "transformation"),
    (r"review|-vs-|versus|test|rating|ranking|tier-list|worth-it|honest", "review"),
    (r"pov|day-in|vlog|day-\d|day-n|grwm|get-ready|routine|diary|morning|night", "pov-vlog"),
    (r"tips|things|mistakes|regret|story|rant|explain|myth|advice|hot-take|truth|"
     r"lesson|reasons|facts", "talking-head"),
    (r"demo|hack|how-to|asmr|unboxing|tutorial|satisfying|restock|setup|cleaning|"
     r"recipe|build", "demo"),
)
VISUAL_FORMAT = {"before-after-split": "transformation", "result-reveal": "transformation",
                 "comparison": "review", "pov-hands": "pov-vlog", "day-counter": "pov-vlog",
                 "face-reaction": "talking-head", "text-first": "talking-head",
                 "product-in-action": "demo", "satisfying-macro": "demo",
                 "unboxing": "demo", "problem-state": "demo"}
ARCHETYPE_FORMAT = {"transformation": "transformation", "comparison": "review",
                    "pov": "pov-vlog", "day-counter": "pov-vlog", "challenge": "pov-vlog",
                    "story-time": "talking-head", "confession": "talking-head",
                    "contrarian-reframe": "talking-head", "listicle": "talking-head",
                    "question": "talking-head", "showcase": "demo", "proof-first": "demo"}
FORMAT_ARCHETYPE = {"transformation": "transformation", "pov-vlog": "pov",
                    "review": "comparison", "demo": "showcase",
                    "talking-head": "curiosity-gap", None: "curiosity-gap"}
DEFAULT_BEATS = {"demo": ("hook", "problem", "product in action", "result", "cta"),
                 "transformation": ("before", "process", "after reveal", "cta"),
                 "review": ("claim", "test", "verdict", "cta"),
                 "pov-vlog": ("pov setup", "the moment", "payoff", "cta"),
                 "talking-head": ("hook", "point 1", "point 2", "payoff", "cta"),
                 None: ("hook", "setup", "payoff", "cta")}
ARCHETYPE_TEXT = {"curiosity-gap": "tease the reveal without giving it away",
                  "listicle": "a number plus the promise", "day-counter": "the Day N marker",
                  "question": "the question itself", "comparison": "A vs B",
                  "transformation": "the before-state in 3 words",
                  "negative-command": "the 'stop doing X' line",
                  "contrarian-reframe": "the belief being flipped",
                  "challenge": "the rule of the challenge", "pov": "the POV line",
                  "bold-claim": "the claim, no hedging", "showcase": "what it is, in 3 words"}
PARTICIPATION_NOTE = {
    "duet": "Leave a 2-second gap after the setup so others can duet their version",
    "stitch": "End on an open question card that others can stitch their answer to",
    "template": "Make one element swappable (the slot) so others can reuse the template",
    "challenge": "Name the challenge and one simple rule anyone can repeat",
    "comment_prompt": "Close with one comment prompt: a single keyword viewers type",
}
CONSTRAINTS = (("one take", "one continuous take, no cuts"),
               ("10 seconds", "the whole idea in about 10 seconds"),
               ("no talking", "no talking: text cards and natural product sound only"))
NICHE_SUBJECT = {"beauty": "product or routine step", "gadgets": "gadget",
                 "tools": "tool", "home": "home fix", "pets": "pet's favourite thing",
                 "food": "recipe", "fitness": "move or routine", "wellness": "wind-down step",
                 "automotive": "car fix", "outdoors": "gear", "finance": "money habit",
                 "education": "study trick", "commentary": "take"}
MECHANIC_SLOT = {
    "comment_prompt": "the one-word verdict viewers comment",
    "template": "one swappable item: your own {subject}",
    "stitch": "a 2-second question card others stitch with their answer",
    "duet": "a split screen with one half left for the duet",
    "challenge": "one rule anyone can repeat in 10 seconds",
}
DEFAULT_MECHANICS = ("comment_prompt", "template", "stitch", "challenge", "duet")
# Invented-trend signatures: graphic / sound devices an AI or a human
# presenter can both carry (no real person needed).
SIGNATURES = (
    ("Receipt Stamp", "a red RECEIPT stamp slams onto the result frame"),
    ("Honest Meter", "an on-screen meter fills while the test runs"),
    ("Two-Beat Sting", "our own two-note sound sting right before the verdict"),
    ("Freeze Tell", "a 1-second freeze with a circle on the detail that proves it"),
    ("Snap Swap", "a hard cut on a snap sound swaps before and after"),
    ("Pocket Frame", "the whole test happens inside one fixed close-up frame"),
    ("Countdown Card", "a 3-2-1 text card counts down to the reveal"),
    ("Verdict Word", "the last beat is one on-screen word, the same every episode"),
)
AI_D137_RISK = ("AI presenter: frame any counter or test as a product log, never "
                "lived experience (D137)")
_LINK_SAFE = ((re.compile(r"(?i)link\s+in\s+(?:the\s+)?bio"), "bio link"),
              (re.compile(r"(?i)link\s+list"), "list of links"),
              (re.compile(r"(?i)(?:check\s+)?(?:in\s+)?your\s+dms"), "direct messages"),
              (re.compile(r"(?i)tap\s+the\s+link"), "the link"))


# ------------------------------------------------------------ text helpers
def safe_text(text, limit=400):
    """Prompt-safe, bundle-safe text: control characters, braces and angle
    brackets removed (vsp.ingest.util.clean_text), D46 link phrases
    neutralised, the BUNDLE_FORBIDDEN phrases dropped, capped."""
    from vsp.ingest.util import clean_text
    t = clean_text(text or "", limit=None) or ""
    for rx, rep in _LINK_SAFE:
        t = rx.sub(rep, t)
    for bad in CV.BUNDLE_FORBIDDEN:
        if bad != "FIXTURE":
            t = t.replace(bad, "")
    t = " ".join(t.split())
    return t[:limit].rstrip()


def words_of(slug_or_text):
    return re.sub(r"[-_.]+", " ", str(slug_or_text or "")).strip()


def nearest_duration(seconds):
    if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or seconds <= 0:
        return None
    return min(S.DURATIONS, key=lambda d: (abs(d - seconds), d))


def map_format(format_key, frame0=None, archetype=None):
    """A vsp.router FORMATS id from the evidence, or None."""
    fk = format_key or ""
    for rx, fmt in FORMAT_RULES:
        if fk and re.search(rx, fk):
            return fmt
    if frame0 in VISUAL_FORMAT:
        return VISUAL_FORMAT[frame0]
    return ARCHETYPE_FORMAT.get(archetype)


def _uniq(seq):
    out = []
    for x in seq:
        if x and x not in out:
            out.append(x)
    return out


def archetypes_for(first, profile, fmt):
    """Ordered, vocab-valid, never-empty hook archetype list."""
    cand = list(first or []) + [profile.get("archetype")] + list(profile.get("archetypes") or [])
    cand.append(EMOTION_ARCHETYPE.get(profile.get("emotion")))
    out = [a for a in _uniq(cand) if a in CV.HOOK_ARCHETYPES]
    if not out:
        out = [FORMAT_ARCHETYPE.get(fmt, "curiosity-gap")]
    return out[:4]


# --------------------------------------------------------------- notes
def beats_note(profile, fmt, extra=None, override=None):
    beats = list(override or profile.get("beats") or DEFAULT_BEATS.get(fmt, DEFAULT_BEATS[None]))
    bits = [" \u2192 ".join(words_of(b) for b in beats)]
    if profile.get("payoff_reveal"):
        bits.append("hold the payoff for the last 2 seconds")
    if profile.get("loop"):
        bits.append("the last frame matches frame 0 so it loops")
    cps = profile.get("cuts_per_10s")
    if isinstance(cps, (int, float)) and cps > 0:
        bits.append(f"about {int(round(cps))} cuts per 10 s")
    if extra:
        bits.append(extra)
    return safe_text("; ".join(bits))


def audio_note(profile, sound_label=None):
    at = profile.get("audio_type")
    title = profile.get("sound_title")
    name = f" ({sound_label or words_of(title)})" if (sound_label or title) else ""
    if at == "trending_sound":
        t = (f"The examples ride a trending sound{name}: recreate its tempo and drop "
             f"with a licensed track from the platform library; never the original "
             f"track in commercial posts")
    elif at == "original_sound":
        t = (f"The examples use a creator's original sound{name}: do not reuse it in "
             f"commercial posts; use our own sound or a licensed track")
    elif at == "original_voiceover":
        t = "Voiceover-led: our own voiceover, a licensed music bed under it"
    elif at == "licensed_music":
        t = "A licensed music bed from the platform's commercial library, added at upload"
    elif at == "none":
        t = "No music in the examples: natural product sound, optional licensed bed"
    else:
        t = ("Licensed music only (platform library, added at upload); never another "
             "creator's original sound in commercial posts")
    return safe_text(t)


def text_note(archetypes, extra=None):
    hint = ARCHETYPE_TEXT.get(archetypes[0] if archetypes else None)
    t = "Frame-0 overlay: at most 8 words, our own words, keyword first"
    if hint:
        t += f"; pattern: {hint}"
    if extra:
        t += f"; {extra}"
    return safe_text(t)


def participation_note(profile, override=None):
    p = override or profile.get("participation")
    t = PARTICIPATION_NOTE.get(p, "No participation mechanic in the examples; optional: "
                                  "one comment prompt")
    if profile.get("cta") == "comment_keyword":
        t += "; the examples close with a keyword-comment CTA"
    elif profile.get("cta") == "link_in_bio":
        t += "; the examples send viewers to a bio link: keep the script's own CTA only"
    return safe_text(t)


def keep_change(kind):
    keep = KEEP_BY_KIND.get(kind, KEEP_BY_KIND["format"])
    change = [e for e in ELEMENTS if e not in keep]
    return ([f"Keep: {KEEP_TEXT[keep[0]]}; and {KEEP_TEXT[keep[1]]}",
             f"Change: {CHANGE_TEXT[change[0]]}; and {CHANGE_TEXT[change[1]]}"])


# ------------------------------------------------------------- context
class Ctx:
    """Everything the operators read, indexed once."""

    def __init__(self, doc, observations, rows, now):
        self.now = now
        self.today = S.utc(now).strftime("%Y-%m-%d")
        self.cards = list(doc.get("trends") or [])
        self.obs = {o["obs_id"]: o for o in observations}
        self.rows = {r["obs_id"]: r for r in rows}
        self.obs_by_key = {}
        for o in observations:
            for k in o.get("trend_keys") or []:
                self.obs_by_key.setdefault(k, []).append(o["obs_id"])
        self.card_by_key = {c["key"]: c for c in self.cards}
        self.observed_tags = sorted({k.split(":", 1)[1] for o in observations
                                     for k in o.get("trend_keys") or []
                                     if k.startswith("tag:")})
        self.reps = self._representatives()

    def _representatives(self):
        """One card per trend: keys whose posts overlap (card["related"]) are
        the same trend's elements; the format card represents them, then
        sound, topic, tag."""
        prio = {"format": 0, "sound": 1, "topic": 2, "tag": 3}
        kept = []
        for c in sorted(self.cards, key=lambda c: (prio.get(c["kind"], 4), -self.heat(c),
                                                   c["key"])):
            if any(c["key"] in (k.get("related") or []) or k["key"] in (c.get("related") or [])
                   for k in kept):
                continue
            kept.append(c)
        return sorted(kept, key=lambda c: c["key"])

    def same_trend(self, a, b):
        return a["key"] == b["key"] or a["key"] in (b.get("related") or []) or \
            b["key"] in (a.get("related") or [])

    def heat(self, card):
        return L.velocity(card["stage"]) * (card.get("evidence_score") or 0.0)

    def usable(self, card):
        return card["stage"] not in ("saturated", "declining") or card.get("evergreen")

    def ranked(self, cards):
        return sorted(cards, key=lambda c: (-self.heat(c), c["key"]))

    def local(self, niche):
        return [c for c in self.reps if niche in (c.get("niches") or [])]

    def foreign(self, niche):
        return [c for c in self.reps if niche not in (c.get("niches") or [])]


def _card_stats(card):
    mx = card.get("median_outlier_x") or card.get("median_multiple")
    sm = card.get("small_medium_share")
    bits = [f"{card['creators_7d']} creators this week vs {card['creators_prev7d']} last "
            f"week (x{card['growth']:g})"]
    if mx:
        bits.append(f"median {mx:g}x")
    if sm is not None:
        bits.append(f"{int(round(sm * 100))}% small/medium creators")
    return ", ".join(bits)


def _cand(ctx, op, niche, cards, title, rationale, prof, **kw):
    """One operator candidate (scored later by finalize())."""
    fmt = kw.pop("fmt", None) or map_format(prof.get("format_key"), prof.get("frame0_visual"),
                                            prof.get("archetype"))
    arch = archetypes_for(kw.pop("archetypes", None), prof, fmt)
    related = []
    for x in cards:
        related += list(x.get("related") or [])
    keys = _uniq([x["key"] for x in cards] + list(kw.pop("keys", [])))
    c = {"operator": op, "niche": niche, "keys": keys,
         "related": [k for k in _uniq(related) if k not in keys],
         "stage": kw.pop("stage", cards[0]["stage"] if cards else "outlier"),
         "speed": kw.pop("speed", cards[0]["speed"] if cards else None),
         "title": safe_text(title, 160), "rationale": safe_text(rationale, 320),
         "profile": prof, "archetypes": arch,
         "frame0": kw.pop("frame0", prof.get("frame0_visual")),
         "vibe": kw.pop("vibe", prof.get("vibe") or EMOTION_VIBE.get(prof.get("emotion"))),
         "format": fmt, "duration": kw.pop("duration", nearest_duration(prof.get("duration_s"))),
         "velocity": kw.pop("velocity", max([L.velocity(x["stage"]) for x in cards] or [0.5])),
         "fit": kw.pop("fit", 1.0), "groups": [list(g) for g in kw.pop("groups", [])],
         "needs_real_person": bool(kw.pop("needs_real_person", prof.get("needs_real_person"))),
         "trending_sound": bool(kw.pop("trending_sound",
                                       prof.get("audio_type") == "trending_sound")),
         "invent": kw.pop("invent", None), "risk": list(kw.pop("risk", []))}
    c["beats_note"] = kw.pop("beats_note", None) or beats_note(prof, fmt)
    c["audio_note"] = kw.pop("audio_note", None) or audio_note(prof)
    c["text_note"] = kw.pop("text_note", None) or text_note(arch)
    c["participation_note"] = kw.pop("participation_note", None) or participation_note(prof)
    c["originality"] = [safe_text(x, 220) for x in
                        list(kw.pop("originality", [])) + list(COMMON_ORIGINALITY)][:8]
    if kw:
        raise TypeError(f"unknown candidate fields {sorted(kw)}")
    c["groups"] = [list(ctx.obs_by_key.get(x["key"], [])) for x in cards] + c["groups"]
    return c


def _fit(card, niche, foreign_fit=FOREIGN_FIT):
    return 1.0 if niche in (card.get("niches") or []) else foreign_fit


# ------------------------------------------------------------- operators
def op_ride(ctx, niche):
    out = []
    for c in ctx.ranked([c for c in ctx.local(niche) if c["stage"] in ("emerging", "rising")]):
        prof = c["profile"]
        out.append(_cand(
            ctx, "ride", niche, [c], f"Ride {c['label']} ({c['stage']}) in {niche}",
            f"{c['stage'].capitalize()} in {niche}: {_card_stats(c)}.", prof,
            originality=keep_change(c["kind"])))
    return out[:MAX_CARDS_PER_OP]


def op_transplant(ctx, niche):
    out = []
    pool = [c for c in ctx.foreign(niche) if ctx.usable(c) and c["stage"] != "declining"
            and (c["kind"] == "format" or c["profile"].get("format_key"))
            and (c.get("median_multiple") or 0) >= TRANSPLANT_MIN_MULTIPLE]
    for c in ctx.ranked(pool):
        src = ", ".join(c.get("niches") or ["other niches"])
        out.append(_cand(
            ctx, "transplant", niche, [c], f"Transplant the {c['label']} from {src} to {niche}",
            f"Winning in {src} ({_card_stats(c)}); not yet used in {niche}.", c["profile"],
            fit=TRANSPLANT_FIT,
            originality=["Keep: " + KEEP_TEXT["visual narrative"] + "; and " +
                         KEEP_TEXT["sonic identity"],
                         "Change: " + CHANGE_TEXT["message"] + "; and " +
                         CHANGE_TEXT["hashtags"]]))
    return out[:MAX_CARDS_PER_OP]


def op_combine(ctx, niche):
    usable = [c for c in ctx.reps if ctx.usable(c)]
    fmt_cards = ctx.ranked([c for c in usable if c["kind"] == "format" or
                            c["profile"].get("format_key")])[:4]
    hook_cards = ctx.ranked([c for c in usable if c["profile"].get("archetype") or
                             c["profile"].get("emotion")])[:4]
    out = []
    for a in fmt_cards:
        for b in hook_cards:
            if ctx.same_trend(a, b):
                continue
            pa, pb = a["profile"], b["profile"]
            if (pb.get("archetype") or None) == (pa.get("archetype") or None) and \
                    pb.get("emotion") == pa.get("emotion"):
                continue
            prof = dict(pa, emotion=pb.get("emotion") or pa.get("emotion"))
            arch = [pb.get("archetype")] if pb.get("archetype") else \
                [EMOTION_ARCHETYPE.get(pb.get("emotion"))]
            vibe = EMOTION_VIBE.get(pb.get("emotion")) or pa.get("vibe")
            hook_label = words_of(pb.get("archetype") or pb.get("emotion"))
            fit = _fit(a, niche)
            out.append(_cand(
            ctx,     "combine", niche, [a, b], f"{a['label']} with a {hook_label} hook",
                f"Format of {a['label']} ({a['stage']}) + the hook of {b['label']} "
                f"({b['stage']}): conventional structure, atypical opening.", prof,
                archetypes=arch, vibe=vibe, fit=fit,
                velocity=(L.velocity(a["stage"]) + L.velocity(b["stage"])) / 2.0,
                originality=[f"Keep: {KEEP_TEXT['visual narrative']} of {a['label']}; and "
                             f"the hook type of {b['label']}",
                             "Change: " + CHANGE_TEXT["sonic identity"] + "; and " +
                             CHANGE_TEXT["hashtags"]]))
    return sorted(out, key=lambda c: (-c["velocity"] * c["fit"], c["keys"]))[:MAX_CARDS_PER_OP]


def op_substitute(ctx, niche):
    rows = [r for r in ctx.rows.values() if r["status"] == "scored" and
            (r.get("multiple") or 0) >= SUBSTITUTE_MIN_MULTIPLE and r["obs_id"] in ctx.obs]
    rows.sort(key=lambda r: (0 if r.get("small_medium") else 1,
                             0 if r.get("niche") == niche else 1,
                             -r["inspiration_score"], r["obs_id"]))
    out = []
    for r in rows[:MAX_CARDS_PER_OP]:
        o = ctx.obs[r["obs_id"]]
        prof = L.profile([o], {o["obs_id"]: r["inspiration_score"]})
        cards = sorted([ctx.card_by_key[k] for k in o.get("trend_keys") or []
                        if k in ctx.card_by_key],
                       key=lambda c: (-L.velocity(c["stage"]), c["key"]))
        stage = cards[0]["stage"] if cards else "outlier"
        speed = cards[0]["speed"] if cards else None
        fk = o.get("format_key")
        who = f"a {r.get('tier') or 'small'} creator's"
        what = words_of(fk) + " post" if fk else "post"
        obs_ids = [o["obs_id"]] + [x for x in ctx.obs_by_key.get("format:" + fk, [])
                                   if x != o["obs_id"]] if fk else [o["obs_id"]]
        out.append(_cand(
            ctx, "substitute", niche, [], f"Substitute: {who} {r['multiple']:g}x {what}, "
                                     f"our {niche} subject",
            f"{r['band'].capitalize()} post ({r['multiple']:g}x, basis {r['basis']}) by a "
            f"{r.get('tier') or 'unknown-tier'} creator: the format won, not the audience.",
            prof, keys=(cards and [c["key"] for c in cards[:3]]) or
            list(o.get("trend_keys") or [])[:3], stage=stage, speed=speed,
            velocity=L.velocity(stage) if cards else L.velocity("steady"),
            fit=1.0 if o.get("niche") == niche else TRANSPLANT_FIT, groups=[obs_ids],
            originality=["Keep: the structure (beat order, frame-0 type, payoff timing) "
                         "and the hook type",
                         "Change: the subject (ours), the words, the sound (licensed) and "
                         "the hashtags"]))
    return out


def _eligible(ctx, niche):
    pool = [c for c in ctx.reps if ctx.usable(c)]
    return sorted(pool, key=lambda c: (0 if niche in (c.get("niches") or []) else 1,
                                       -ctx.heat(c), c["key"]))


def op_reverse(ctx, niche):
    out = []
    for c in _eligible(ctx, niche):
        p = c["profile"]
        if not (p.get("payoff_reveal") or p.get("archetype") in (
                "transformation", "proof-first", "curiosity-gap") or
                p.get("frame0_visual") in ("result-reveal", "before-after-split")):
            continue
        out.append(_cand(
            ctx, "reverse", niche, [c], f"Reverse the payoff of the {c['label']}",
            f"{c['label']} ({c['stage']}) sets up an expected payoff; flipping it keeps the "
            f"structure and breaks the pattern viewers predict.", p,
            archetypes=["contrarian-reframe", "negative-command"], frame0="result-reveal",
            fit=_fit(c, niche),
            beats_note=beats_note(p, None, override=(
                "open on the payoff", "rewind: the expected way", "the flip: why the "
                "expected answer is wrong", "our proof", "cta")),
            originality=["Keep: " + KEEP_TEXT["visual narrative"],
                         "Change: the payoff (flipped), the words, the sound (licensed) and "
                         "the hashtags"]))
        if len(out) >= 3:
            break
    return out


def op_serialize(ctx, niche):
    out = []
    for c in _eligible(ctx, niche):
        p = c["profile"]
        r = p.get("replicability")
        if p.get("series") or (r is not None and r < 3):
            continue
        out.append(_cand(
            ctx, "serialize", niche, [c], f"Series: {c['label']}, one episode a day",
            f"{c['label']} is replicable ({r if r is not None else 'n/a'}/5) and not yet a "
            f"series: a day counter turns one hit into a returning audience.", p,
            archetypes=["day-counter", "challenge"], frame0="day-counter", fmt="pov-vlog",
            fit=_fit(c, niche), risk=[AI_D137_RISK],
            beats_note=beats_note(p, "pov-vlog", override=(
                "day or part N marker", "today's attempt", "one visible result",
                "cliffhanger for the next episode"), extra="same beat order every episode"),
            participation_note=safe_text(
                "End each episode with the next episode's question; ask viewers to "
                "comment one keyword for what to test next"),
            originality=["Keep: " + KEEP_TEXT["visual narrative"],
                         "Change: the frame becomes an episode counter; our subject, words, "
                         "licensed sound and hashtags"]))
        if len(out) >= 3:
            break
    return out


def op_constrain(ctx, niche):
    out = []
    for i, c in enumerate(_eligible(ctx, niche)[:3]):
        p = c["profile"]
        cps, dur = p.get("cuts_per_10s"), p.get("duration_s")
        if isinstance(cps, (int, float)) and cps >= 4:
            name, desc = CONSTRAINTS[0]
        elif isinstance(dur, (int, float)) and dur >= 25:
            name, desc = CONSTRAINTS[1]
        elif p.get("audio_type") == "original_voiceover":
            name, desc = CONSTRAINTS[2]
        else:
            name, desc = CONSTRAINTS[i % len(CONSTRAINTS)]
        kw = {}
        if name == "10 seconds":
            kw["duration"] = 15
        if name == "no talking":
            kw["frame0"] = "text-first"
        out.append(_cand(
            ctx, "constrain", niche, [c], f"{c['label']}, but {name}",
            f"A visible rule ({desc}) makes the familiar {c['label']} feel new and easy "
            f"to copy.", p, fit=_fit(c, niche),
            beats_note=beats_note(p, None, extra="constraint: " + desc),
            originality=["Keep: " + KEEP_TEXT["message"],
                         f"Change: add the rule ({desc}); our footage, words, licensed "
                         f"sound and hashtags"], **kw))
    return out


def op_escalate(ctx, niche):
    out = []
    for c in _eligible(ctx, niche):
        p = c["profile"]
        fmt = map_format(p.get("format_key"), p.get("frame0_visual"), p.get("archetype"))
        if not (p.get("frame0_visual") in ("product-in-action", "comparison", "problem-state",
                                           "pov-hands") or fmt in ("demo", "review") or
                p.get("archetype") in ("proof-first", "comparison", "challenge", "bold-claim")):
            continue
        fit = _fit(c, niche) * (0.8 if niche in ADVICE_NICHES else 1.0)
        out.append(_cand(
            ctx, "escalate", niche, [c], f"Escalate the {c['label']}: a torture test",
            f"{c['label']} ({c['stage']}) shows the product working; raising the stakes "
            f"each beat adds tension (high-arousal content spreads).", p,
            archetypes=["challenge", "bold-claim", "comparison"], frame0="product-in-action",
            fmt="demo", fit=fit,
            beats_note=beats_note(p, "demo", override=(
                "normal use", "harder", "the extreme test", "verdict on camera, pass or fail")),
            risk=["real footage required: film every test, never generate it (D136)",
                  "no invented results, ratings or guarantees (D141)",
                  "safety: no dangerous stunts"],
            originality=["Keep: " + KEEP_TEXT["message"],
                         "Change: the stakes (each beat harder), our product, words, "
                         "licensed sound and hashtags"]))
        if len(out) >= 3:
            break
    return out


def op_mashup(ctx, niche):
    sounds = ctx.ranked([c for c in ctx.cards if ctx.usable(c) and c["kind"] == "sound"])[:3]
    visuals = ctx.ranked([c for c in ctx.reps if ctx.usable(c) and c["kind"] != "sound" and
                          (c["kind"] == "format" or c["profile"].get("format_key"))])[:3]
    out = []
    for a in visuals:
        for b in sounds:
            if ctx.same_trend(a, b):
                continue
            pa = a["profile"]
            prof = dict(pa, audio_type="trending_sound",
                        sound_title=b["profile"].get("sound_title"))
            label = b["label"]
            out.append(_cand(
            ctx,     "mashup", niche, [a, b], f"{a['label']} visuals on the rhythm of {label}",
                f"Visual narrative of {a['label']} ({a['stage']}) + the sonic pattern of "
                f"{label} ({b['stage']}), rebuilt on licensed audio.", prof,
                vibe=pa.get("vibe") or EMOTION_VIBE.get(b["profile"].get("emotion")),
                fit=_fit(a, niche), trending_sound=True,
                velocity=(L.velocity(a["stage"]) + L.velocity(b["stage"])) / 2.0,
                audio_note=safe_text(
                    f"Borrow the rhythm of {label} (tempo, the drop on the reveal) with a "
                    f"licensed track from the platform library; never its original audio "
                    f"in commercial posts"),
                originality=[f"Keep: {KEEP_TEXT['visual narrative']} of {a['label']}; and "
                             f"{KEEP_TEXT['sonic identity']} of {label}",
                             "Change: " + CHANGE_TEXT["message"] + "; and " +
                             CHANGE_TEXT["hashtags"]]))
    return out[:MAX_CARDS_PER_OP]


def _weighted_counts(ctx, fn):
    counts = {}
    for oid in sorted(ctx.obs):
        v = fn(ctx.obs[oid])
        if v is None:
            continue
        r = ctx.rows.get(oid)
        counts[v] = counts.get(v, 0.0) + (r["inspiration_score"] if r else 0.0) + 1e-3
    return counts


def _sig_pick(seed, n):
    return int(hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8], 16) % n


def op_invent(ctx, niche, n=3):
    formats = _weighted_counts(ctx, lambda o: o.get("format_key"))
    if not formats:
        return []
    mech = _weighted_counts(ctx, lambda o: o.get("participation")
                            if o.get("participation") not in (None, "none") else None)
    emos = _weighted_counts(ctx, lambda o: o.get("emotion")
                            if o.get("emotion") not in (None, "other") else None)
    local = {o.get("format_key") for o in ctx.obs.values() if o.get("niche") == niche}
    fmt_rank = sorted(formats, key=lambda f: (-formats[f] * (1.5 if f in local else 1.0), f))
    out, used_sigs = [], set()
    for i in range(n):
        fk = fmt_rank[i % len(fmt_rank)]
        fobs = [o for o in ctx.obs.values() if o.get("format_key") == fk]
        co = {}
        for o in fobs:
            if o.get("participation") not in (None, "none"):
                co[o["participation"]] = co.get(o["participation"], 0) + 1
        mechs = sorted(mech, key=lambda m: (co.get(m, 0) / float(max(1, len(fobs))),
                                            -mech[m], m)) or list(DEFAULT_MECHANICS)
        mechanic = mechs[(i // max(1, len(fmt_rank))) % len(mechs)]
        dom = L.profile(fobs, {}).get("emotion")
        emo_rank = sorted(emos, key=lambda e: (0 if e in HIGH_AROUSAL else 1,
                                               1 if e == dom else 0, -emos[e], e))
        emotion = emo_rank[i % len(emo_rank)] if emo_rank else "surprise"
        seed = f"{ctx.today}:{niche}:{i}:{fk}:{mechanic}:{emotion}"
        j = _sig_pick(seed, len(SIGNATURES))
        while SIGNATURES[j][0] in used_sigs and len(used_sigs) < len(SIGNATURES):
            j = (j + 1) % len(SIGNATURES)
        used_sigs.add(SIGNATURES[j][0])
        sig_name, marker = SIGNATURES[j]
        tag = "#" + re.sub(r"[^a-z0-9]", "", (sig_name + niche).lower())
        if tag[1:] in ctx.observed_tags:
            tag += "test"
        subject = NICHE_SUBJECT.get(niche, "product")
        slot = MECHANIC_SLOT.get(mechanic, MECHANIC_SLOT["template"]).format(subject=subject)
        card = ctx.card_by_key.get("format:" + fk)
        prof = dict(card["profile"]) if card else L.profile(fobs, {})
        prof["emotion"] = emotion
        prof["participation"] = mechanic
        fmt = map_format(fk, prof.get("frame0_visual"), prof.get("archetype"))
        flabel = words_of(fk)
        hypothesis = (f"A {flabel} post with a {words_of(mechanic)} mechanic and a {emotion} "
                      f"core, marked by the {sig_name}, beats our median post on shares per "
                      f"reach within 72 h: the format is familiar (MAYA), the mechanic is "
                      f"the atypical element (Uzzi), and the named signature plus the slot "
                      f"make it easy to imitate.")
        test_plan = [
            "Post as a Trial Reel (shown to non-followers first) with 3 alternate "
            "openings from hooks.md; the alternates differ only in the first 3 seconds",
            "Measure at 24, 48 and 72 h: reels_skip_rate (the hook), shares and saves per "
            "reach, comments that use the signature word or hashtag",
            "Graduate if 2 of 3 openings beat the account median on shares per reach; "
            "otherwise stop and record the result",
            f"If it graduates: 2 more episodes within 7 days with the same {sig_name} and "
            f"slot, inviting others to use the slot and {tag}",
        ]
        fmt_ids = sorted(o["obs_id"] for o in fobs)
        mech_ids = sorted(o["obs_id"] for o in ctx.obs.values()
                          if o.get("participation") == mechanic)
        inv = {"signature": {"name": sig_name, "marker": marker, "hashtag": tag},
               "slot": safe_text(f"[your {subject}] + [{slot}]", 200),
               "hypothesis": safe_text(hypothesis),
               "test_plan": [safe_text(t, 240) for t in test_plan],
               "elements": {"participation": mechanic, "format_key": fk, "emotion": emotion,
                            "signature": sig_name}}
        out.append(_cand(
            ctx, "invent", niche, [card] if card else [],
            f"Invented: the {sig_name} ({flabel} x {words_of(mechanic)}, {emotion})",
            f"Blend of high-scoring elements: {flabel} (format evidence {formats[fk]:.2f}), "
            f"{words_of(mechanic)} (atypical for this format), a {emotion} core.",
            prof, keys=["format:" + fk] if not card else [], stage="invented",
            speed=None, velocity=L.velocity(card["stage"]) if card else 0.5,
            fit=1.0 if (card and niche in (card.get("niches") or [])) else FOREIGN_FIT,
            groups=([] if card else [fmt_ids]) + ([mech_ids] if mech_ids else []),
            invent=inv,
            archetypes=[EMOTION_ARCHETYPE.get(emotion)], fmt=fmt,
            vibe=EMOTION_VIBE.get(emotion) or prof.get("vibe"),
            beats_note=beats_note(prof, fmt, extra=f"signature beat: {marker}"),
            audio_note=safe_text("Give it a sonic signature we own: a 2-3 second original "
                                 "sting or voice tag (no copyrighted track), a licensed "
                                 "library track as the bed"),
            participation_note=safe_text(PARTICIPATION_NOTE.get(mechanic, "") +
                                         f"; the slot: {slot}"),
            text_note=text_note([EMOTION_ARCHETYPE.get(emotion) or "curiosity-gap"],
                                extra=f"show {tag} on the last frame"),
            trending_sound=False,
            risk=["unproven: an invented trend; test as Trial Reels before scaling",
                  "needs 2-3 episodes to seed imitation"],
            originality=[f"Ours: the {sig_name} ({marker}) and the hashtag {tag}",
                         "Ours: the slot, the words and the sonic sting; the format is "
                         "common, the mechanic + signature combination is new"]))
    return out


OPERATOR_FUNCS = (("ride", op_ride), ("transplant", op_transplant), ("combine", op_combine),
                  ("substitute", op_substitute), ("reverse", op_reverse),
                  ("serialize", op_serialize), ("constrain", op_constrain),
                  ("escalate", op_escalate), ("mashup", op_mashup))


def candidates(op, ctx, niche, n_invent=3):
    """Candidates of one operator for one niche."""
    if op == "invent":
        return op_invent(ctx, niche, n_invent)
    return dict(OPERATOR_FUNCS)[op](ctx, niche)


# --------------------------------------------------------------- scoring
def tokens_of(rec):
    """Novelty tokens of a candidate, or the stored `tokens` of a recipe:
    primary trend keys (not the related ones), operator, niche, the first
    two hook archetypes, frame 0, format, vibe, invent elements."""
    if isinstance(rec.get("tokens"), list) and rec["tokens"]:
        return set(rec["tokens"])
    t = set(rec.get("keys") or rec.get("trend_keys") or [])
    t.add("op:" + str(rec.get("operator")))
    t.add("niche:" + str(rec.get("niche")))
    arch = rec.get("archetypes") or rec.get("hook_archetypes") or []
    t |= {"arch:" + a for a in arch[:2]}
    for k, pre in (("frame0", "v0:"), ("frame0_visual_type", "v0:"), ("format", "fmt:"),
                   ("vibe", "vibe:")):
        if rec.get(k):
            t.add(pre + str(rec[k]))
    inv = rec.get("invent")
    if isinstance(inv, dict) and inv.get("elements"):
        e = inv["elements"]
        t |= {"sig:" + (S.slug(e.get("signature") or "") or ""),
              "part:" + str(e.get("participation")), "emo:" + str(e.get("emotion")),
              "fk:" + str(e.get("format_key"))}
    return t


def jaccard(a, b):
    if not a and not b:
        return 0.0
    return len(a & b) / float(len(a | b))


def novelty(tokens, memory):
    """1 - max Jaccard similarity to any token set in memory (1.0 if empty)."""
    if not memory:
        return 1.0
    return round(1.0 - max(jaccard(tokens, m) for m in memory), 4)


def feasibility(cand, lane):
    """-> (factor in [0, 1], risks). 0 = infeasible for this presenter lane."""
    p = cand["profile"]
    risks = []
    if cand["needs_real_person"]:
        if lane == "ai":
            return 0.0, ["needs a real person (dance, face reaction or real-person "
                         "challenge): infeasible for an AI presenter"]
        risks.append("needs a real person on camera")
    r = p.get("replicability")
    rf = REPLICABILITY_FLOOR + (1.0 - REPLICABILITY_FLOOR) * ((r - 1) / 4.0) \
        if isinstance(r, (int, float)) else 0.7
    cf = COST_FACTOR.get(p.get("production_cost"), UNKNOWN_COST_FACTOR)
    if p.get("production_cost") == "high":
        risks.append("high production cost")
    af = 1.0
    if cand["trending_sound"]:
        af = LICENSED_AUDIO_FACTOR
        risks.append("needs licensed audio: recreate the sound's pattern with a licensed "
                     "track; never the original sound in commercial posts")
    return round(max(0.0, min(1.0, rf * cf * af * cand["fit"])), 4), risks


def evidence_of(cand, ctx):
    """1 - exp(-inspiration sum); a multi-trend candidate uses the mean of
    its groups' sums (combining two trends must not double the evidence).
    -> (evidence, supporting obs ids)."""
    groups = [sorted(set(g)) for g in cand["groups"] if g]
    ids = sorted({i for g in groups for i in g})
    if not groups:
        return 0.0, ids
    sums = [sum(ctx.rows[i]["inspiration_score"] for i in g if i in ctx.rows) for g in groups]
    total = sum(sums) / float(len(sums))
    return round(1.0 - math.exp(-total / EVIDENCE_SCALE), 4), ids


def evidence_items(ids, ctx, limit=5):
    rows = [ctx.rows[i] for i in ids if i in ctx.rows and ctx.rows[i].get("permalink")]
    rows.sort(key=lambda r: (0 if r.get("small_medium") else 1, -r["inspiration_score"],
                             r["obs_id"]))
    return [{"permalink": r["permalink"], "platform": r["platform"], "tier": r.get("tier"),
             "outlier_x": r.get("outlier_x"), "band": r.get("band")} for r in rows[:limit]]


def fingerprint(rec):
    inv = rec.get("invent") or {}
    body = {"op": rec.get("operator"), "niche": rec.get("niche"),
            "keys": sorted(rec.get("keys") or rec.get("trend_keys") or []),
            "arch": list(rec.get("archetypes") or rec.get("hook_archetypes") or []),
            "v0": rec.get("frame0") or rec.get("frame0_visual_type"),
            "fmt": rec.get("format"), "vibe": rec.get("vibe"),
            "sig": ((inv.get("signature") or {}).get("name") if inv else None)}
    return hashlib.sha1(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _static(cand, ctx, lane):
    """The lane-dependent but memory-independent parts, or None if infeasible."""
    feas, frisks = feasibility(cand, lane)
    if feas <= 0.0:
        return None
    ev, ids = evidence_of(cand, ctx)
    return {"feasibility": feas, "risks": frisks, "evidence": ev, "ids": ids,
            "velocity": round(max(0.0, min(1.0, cand["velocity"])), 4),
            "tokens": tokens_of(cand), "fingerprint": fingerprint(cand)}


def finalize(cand, ctx, lane, memory, static=None):
    """Candidate -> recipe dict for one lane, or None when infeasible."""
    st = static or _static(cand, ctx, lane)
    if st is None:
        return None
    feas, ev, vel = st["feasibility"], st["evidence"], st["velocity"]
    ids = st["ids"]
    nov = novelty(st["tokens"], memory)
    score = round(ev * vel * nov * feas, 4)
    risks = list(cand["risk"]) + st["risks"]
    if cand["stage"] in ("saturated", "declining"):
        risks.append(f"{cand['stage']} trend: only as an evergreen format with a fresh angle")
    if cand["stage"] == "peak":
        risks.append("at peak: needs a twist to stand out")
    if not cand["needs_real_person"] and AI_D137_RISK not in risks and \
            any(a in ("day-counter", "challenge") for a in cand["archetypes"]):
        risks.append(AI_D137_RISK)
    rec = {
        "schema_version": S.SCHEMA_VERSION, "recipe_id": None, "date": ctx.today,
        "created_at": S.iso(ctx.now), "operator": cand["operator"],
        "title": cand["title"], "rationale": cand["rationale"], "niche": cand["niche"],
        "lanes": ["human"] if cand["needs_real_person"] else ["ai", "human"],
        "trend_keys": [k for k in cand["keys"] + cand["related"]
                       if S.norm_trend_key(k) == k][:10],
        "tokens": sorted(st["tokens"]),
        "stage": cand["stage"], "speed": cand["speed"], "score": score,
        "score_parts": {"evidence": ev, "velocity": vel, "novelty": nov, "feasibility": feas},
        "hook_archetypes": cand["archetypes"], "frame0_visual_type": cand["frame0"],
        "vibe": cand["vibe"], "format": cand["format"], "duration_s": cand["duration"],
        "beats_note": cand["beats_note"], "audio_note": cand["audio_note"],
        "text_note": cand["text_note"], "participation_note": cand["participation_note"],
        "originality": cand["originality"], "evidence": evidence_items(ids, ctx),
        "risk": [safe_text(r, 220) for r in _uniq(risks)][:10],
        "needs_real_person": cand["needs_real_person"], "fingerprint": st["fingerprint"],
        "invent": cand["invent"], "used": False, "used_at": None, "script_sha": None,
    }
    return rec


def select(cands, ctx, lane, k, memory):
    """Greedy top-k with novelty recomputed against memory + the picks so
    far; at most MAX_PER_OPERATOR per operator."""
    pool = []
    for c in cands:
        st = _static(c, ctx, lane)
        if st is not None:
            pool.append((st["fingerprint"], c, st))
    pool.sort(key=lambda t: t[0])
    picked, mem, per_op = [], list(memory), {}
    while pool and len(picked) < k:
        best = None
        for i, (fp, c, st) in enumerate(pool):
            if per_op.get(c["operator"], 0) >= MAX_PER_OPERATOR:
                continue
            score = st["evidence"] * st["velocity"] * st["feasibility"] * \
                novelty(st["tokens"], mem)
            if score < MIN_SCORE:
                continue
            key = (-round(score, 4), fp)
            if best is None or key < best[0]:
                best = (key, i)
        if best is None:
            break
        _, c, st = pool.pop(best[1])
        picked.append(finalize(c, ctx, lane, mem, static=st))
        per_op[c["operator"]] = per_op.get(c["operator"], 0) + 1
        mem.append(st["tokens"])
    return picked


def synthesize(doc, observations, rows, niches, lanes=("ai", "human"), k=10, invent=3,
               now=None, memory=(), existing=()):
    """-> new recipes (ids assigned) for every niche x lane. `memory` = token
    sets of used recipes; `existing` = recipes already in the file (ids are
    reused for identical recipes of the same date)."""
    now = now or S.now_utc()
    ctx = Ctx(doc, observations, rows, now)
    batch = {}
    for niche in sorted(set(niches)):
        cands = []
        for op, _fn in OPERATOR_FUNCS:
            cands += candidates(op, ctx, niche)
        inv = candidates("invent", ctx, niche, n_invent=invent) if invent else []
        for lane in sorted(set(lanes)):
            chosen = select(cands, ctx, lane, k, memory)
            mem = list(memory) + [tokens_of(r) for r in chosen]
            chosen += select(inv, ctx, lane, invent, mem)
            for r in chosen:
                old = batch.get(r["fingerprint"])
                if old is None or r["score"] > old["score"]:
                    batch[r["fingerprint"]] = r
    return assign_ids(sorted(batch.values(), key=lambda r: (r["niche"], -r["score"],
                                                            r["fingerprint"])),
                      ctx.today, existing)


def assign_ids(recipes, day, existing=()):
    """rcp-YYYYMMDD-NN: reuse the id of an identical recipe (same date and
    fingerprint), else the next free number of that date."""
    tag = day.replace("-", "")
    taken, by_fp = set(), {}
    for r in existing or []:
        rid = r.get("recipe_id") or ""
        if rid.startswith(f"rcp-{tag}-"):
            taken.add(int(rid.rsplit("-", 1)[1]))
            if not r.get("used"):
                by_fp.setdefault(r.get("fingerprint"), rid)
    nxt = 1
    for r in recipes:
        rid = by_fp.pop(r["fingerprint"], None)
        if rid is None:
            while nxt in taken:
                nxt += 1
            rid = f"rcp-{tag}-{nxt:02d}"
            taken.add(nxt)
        r["recipe_id"] = rid
    return sorted(recipes, key=lambda r: r["recipe_id"])
