"""vsp.feedback — the closed performance-feedback loop: YOUR posted reels ->
Instagram insight snapshots -> labels -> learned/priors.json (read by the
maker's hook-family choice) + learned/PERFORMANCE.md.

    python3 -m vsp.feedback link --media-id ID --manifest PATH [--trial] [--variant B]
    python3 -m vsp.feedback link --auto [--search DIR ...]
    python3 -m vsp.feedback pull [--no-link]
    python3 -m vsp.feedback learn
    python3 -m vsp.feedback report
    python3 -m vsp.feedback variants [--slug S | --sha SHA8] [--json]
    python3 -m vsp.feedback status | selfcheck

THE CAPTION TAG. Put `#vsp-<first 8 hex chars of script_sha256>` anywhere in
the posted reel's caption, e.g. `#vsp-0a1b2c3d`. script_sha256 is the
sha256 of the run's script.json bytes (manifest.json -> script_summary ->
script_sha256, also manifest outputs["script.json"]). `python3 -m vsp.ingest
own` stores the tag as reels.script_slug ('vsp-0a1b2c3d'); `link --auto`
finds the manifest.json whose script_sha256 starts with those 8 characters
(under outputs/, VSP_FEEDBACK_SEARCH or --search) and links the two.
Instagram only treats `#vsp` as the hashtag; the suffix is parsed from the
raw caption and stripped from research hooks. No tag (or a trial the
caption cannot carry)? `link --media-id ID --manifest PATH [--trial]`.
Trial Reels have no read-side flag (research doc §4), so --trial records it.

What a link stores (posts table): the manifest's script_summary (prompt,
niche, hook_family, hook_source, hook, presenter, format, duration_s, seed,
candidate_seed, script_sha256); without a script_summary the script.json
next to the manifest is read (its sha256 = script_sha256).

VARIANTS (pipeline v2.1, docs/CREATIVE-PLAN.md §1.5). An alternate opening
posted on its own (e.g. a Trial Reel) is `hook_variants[*]` of the script.
The tag may carry its letter, `#vsp-<sha8>B`; without a tag, `link --auto`
matches the CAPTION FINGERPRINT: the posted caption's first line with words
(NFKC, lowercase, hashtags / @mentions / URLs / emoji / punctuation
stripped, spaces collapsed) against every candidate script's caption first
line (and its Instagram discovery caption) = the primary variant A, and each
`hook_variants[*].caption_line` = that variant. Candidates: manifest.json
under outputs/ + VSP_FEEDBACK_SEARCH + --search, script.json next to it,
manifest `created` (else its mtime) before the post and at most 60 days
earlier (FP_WINDOW_DAYS). Exact match or token Jaccard >= 0.8
(FP_MIN_JACCARD); the best match wins deterministically: exact, then higher
Jaccard, then the newest run, then script sha, variant order, path. A
tagged post without a letter takes its variant from the fingerprint within
that script, else the primary (the master cut opens with variant A). The
link also stores variant_id and, from script.json, that variant's archetype
+ visual_type, direction.vibe, direction.tone.voice and
discovery.primary_keyword (NULL for scripts without them).

`variants`: for every script with >= 2 posted variants that have snapshots,
hold = views x (1 - skip rate) (percent/fraction as in learn), posterior
Beta(1 + holds, 1 + skips) per variant, P(best) + expected loss from
VARIANT_POLICY["draws"] seeded Monte Carlo draws, the VARIANT_POLICY stop
rule (docs/research/hooks-deep-dive.md §3.6) -> winner found / keep testing
/ inconclusive + a concrete action -> learned/VARIANTS.md.

pull: for every own reel (vsp.ingest `own` registers them), one lifetime
insights snapshot per checkpoint of about 24 h, 48 h, 7 d and 28 d
(CHECKPOINTS; a snapshot taken at age a satisfies the largest checkpoint
<= a, so an hourly cron takes exactly one per checkpoint; missed ones are
not back-filled because Instagram only reports lifetime totals). Empty
insights (the up-to-48 h lag) store nothing; deleted media is marked for
`python3 -m vsp.ingest purge`.

learn — labels per own reel, from its latest snapshot at >= 24 h:
    hook_rate   = 1 - reels_skip_rate   (percent vs fraction normalised per
                                         account: any value > 1 => percent)
    watch_ratio = avg_watch_ms / 1000 / duration_s   (linked posts only)
    share_rate  = shares / reach,  save_rate = saves / reach
    composite   = mean of the within-account z-scores of the labels above
                  (over the last WINDOW=60 labelled posts; a label with no
                  spread scores 0)
    success     = composite >= the median composite of those posts
Beta-Bernoulli per (maker niche, hook family) with prior Beta(1, 1):
alpha = 1 + successes, beta = 1 + failures, n = posts; `global` pools the
niches per family. learned/priors.json follows learned/README.md exactly
(schema_version 1, updated_at, metric "composite", families, global).
Priors v2: the same labels and Beta(1, 1) per (niche, key) + global for the
vsp.priors SECTIONS archetype / visual_type / vibe / tone (posts whose key
is known and a creative_vocab id) under "sections"; schema_version is 2
when any section has data, else the file is exactly v1 (old readers keep
working).
Paths: config.learned_dir() / config.priors_path() (VSP_LEARNED_DIR).
"""
import argparse
import hashlib
import json
import math
import os
import random
import re
import statistics
import sys
import unicodedata
from datetime import timedelta

from vsp import config

CHECKPOINTS = (24, 48, 168, 672)          # hours: ~24 h, 48 h, 7 d, 28 d
WINDOW = 60
METRIC = "composite"
LABELS = ("hook_rate", "watch_ratio", "share_rate", "save_rate")
SUMMARY_KEYS = ("prompt", "niche", "hook_family", "hook_source", "hook", "presenter",
                "format", "duration_s", "seed", "candidate_seed", "script_sha256")
INSIGHT_COLUMNS = {"views": "views", "reach": "reach", "likes": "likes",
                   "comments": "comments", "shares": "shares", "saved": "saves",
                   "reposts": "reposts", "ig_reels_avg_watch_time": "avg_watch_ms",
                   "ig_reels_video_view_total_time": "total_watch_ms",
                   "reels_skip_rate": "skip_rate"}
_SHA = re.compile(r"^[0-9a-f]{64}$")
_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv"}
# v2.1 creative layer (docs/CREATIVE-PLAN.md §1.5, §1.6)
CREATIVE_COLUMNS = ("variant_id", "hook_archetype", "visual_type", "vibe", "tone",
                    "primary_keyword")                       # posts columns
SUMMARY_CREATIVE_KEYS = ("vibe", "tone", "hook_archetype", "visual_type",
                         "variant_ids", "primary_keyword")    # manifest §1.6
VARIANT_TAG = re.compile(r"#vsp-([0-9a-fA-F]{8})([A-Za-z])?(?!\w)")
FP_WINDOW_DAYS = 60          # a fingerprint only matches runs <= 60 days before the post
FP_MIN_JACCARD = 0.8         # ... exactly, or with token Jaccard >= 0.8


class LinkError(ValueError):
    pass


def _util():
    from vsp.ingest import util
    return util


def tag_for(sha256):
    return "vsp-" + str(sha256)[:8].lower()


# ------------------------------------------------- variant tag + fingerprint
def parse_tag(caption):
    """'#vsp-<sha8>[<variant letter>]' anywhere in a caption -> ('vsp-<sha8>',
    'B' | None); (None, None) without a tag. The 9th character is the variant
    letter (uppercased), so '#vsp-0a1b2c3dB' is script 0a1b2c3d, variant B."""
    m = VARIANT_TAG.search(caption) if isinstance(caption, str) else None
    if not m:
        return None, None
    return "vsp-" + m.group(1).lower(), (m.group(2).upper() if m.group(2) else None)


_FP_URL = re.compile(r"(?i)\b(?:https?://|www\.)\S+")
_FP_HASHTAG = re.compile(r"#vsp-\w+|#(?!\d+\b)\w+")      # "#1 mistake" keeps its 1
_FP_MENTION = re.compile(r"(?<![\w.@])@[\w.]*\w")
_FP_APOSTROPHE = re.compile(r"(?<=\w)['\u2019\u02bc](?=\w)")   # don't -> dont


def fingerprint(text):
    """Caption fingerprint (module doc): the first line with words left after
    NFKC + lowercasing and stripping hashtags (#vsp-... included), @mentions,
    URLs, emoji and punctuation, spaces collapsed. '' when nothing is left."""
    if not isinstance(text, str):
        return ""
    t = unicodedata.normalize("NFKC", text).replace("\r\n", "\n").replace("\r", "\n")
    for line in t.split("\n"):
        line = _FP_MENTION.sub(" ", _FP_HASHTAG.sub(" ", _FP_URL.sub(" ", line)))
        out = []
        for ch in _FP_APOSTROPHE.sub("", line).casefold():
            cat = unicodedata.category(ch)[0]
            if cat in "LN":
                out.append(ch)
            elif cat != "M":             # marks (variation selectors, keycaps) vanish
                out.append(" ")          # emoji, punctuation, symbols, ZWJ -> space
        fp = " ".join("".join(out).split())
        if fp:
            return fp
    return ""


def jaccard(a, b):
    """Token Jaccard of two fingerprints (0.0 when either is empty)."""
    sa, sb = set(str(a).split()), set(str(b).split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _dig(obj, *keys):
    for k in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(k)
    return obj


def _clean_id(v, limit=80):
    if isinstance(v, str):
        v = " ".join(v.split())
        if v:
            return v[:limit]
    return None


def load_script(manifest_path):
    """The script.json next to a manifest (or in a run folder) -> dict or
    None. Never raises."""
    try:
        mp = os.path.abspath(manifest_path)
        d = mp if os.path.isdir(mp) else os.path.dirname(mp)
        with open(os.path.join(d, "script.json"), encoding="utf-8") as f:
            s = json.load(f)
        return s if isinstance(s, dict) else None
    except (OSError, ValueError, TypeError, RecursionError):
        return None


def hook_variants(script):
    """[(ID, variant dict)] from script["hook_variants"] (ids uppercased,
    first occurrence wins, script order)."""
    out, seen = [], set()
    hv = script.get("hook_variants") if isinstance(script, dict) else None
    for v in hv if isinstance(hv, list) else []:
        vid = _clean_id(v.get("id"), 8) if isinstance(v, dict) else None
        if vid and vid.upper() not in seen:
            seen.add(vid.upper())
            out.append((vid.upper(), v))
    return out


def primary_variant(script):
    """The is_primary variant's id, else "A" (contract: variant A is primary)."""
    for vid, v in hook_variants(script):
        if v.get("is_primary") is True:
            return vid
    return "A"


def caption_fingerprints(script):
    """[(variant_id, fingerprint, tokens)] a posted caption can match: the
    script caption's first line and the Instagram discovery caption's first
    line (the primary variant), then each hook_variants[*].caption_line."""
    if not isinstance(script, dict):
        return []
    prim = primary_variant(script)
    raw = [(prim, script.get("caption")),
           (prim, _dig(script, "discovery", "platforms", "instagram", "caption"))]
    raw += [(vid, v.get("caption_line")) for vid, v in hook_variants(script)]
    out, seen = [], set()
    for vid, text in raw:
        fp = fingerprint(text)
        if fp and (vid, fp) not in seen:
            seen.add((vid, fp))
            out.append((vid, fp, frozenset(fp.split())))
    return out


def _fp_score(fp, cand_fp, cand_tokens, min_jaccard=FP_MIN_JACCARD):
    """-> (exact, jaccard) when the fingerprints match (exact, or token
    Jaccard >= min_jaccard), else None."""
    if not fp or not cand_fp:
        return None
    if fp == cand_fp:
        return True, 1.0
    toks = set(fp.split())
    union = len(toks | cand_tokens)
    j = len(toks & cand_tokens) / union if union else 0.0
    return (False, j) if j >= min_jaccard - 1e-9 else None


def match_in_script(caption, script):
    """Best variant of ONE script for a posted caption -> (variant_id,
    exact, jaccard) or None (no time window: the script is already known)."""
    fp = fingerprint(caption)
    best = None
    for order, (vid, cfp, ctoks) in enumerate(caption_fingerprints(script)):
        sc = _fp_score(fp, cfp, ctoks)
        if sc is not None:
            key = (not sc[0], -sc[1], order)
            if best is None or key < best[0]:
                best = (key, (vid, sc[0], sc[1]))
    return best[1] if best else None


def resolve_variant(script, sha256, caption=None, explicit=None):
    """Which opening a post used -> (variant_id | None, how). how: explicit
    (--variant / a fingerprint match across scripts) > tag (this script's
    #vsp-<sha8><letter>) > fingerprint (within this script) > primary (a
    v2.1 script's master cut opens with its primary variant) > None."""
    if explicit:
        return str(explicit).strip().upper(), "explicit"
    tag, letter = parse_tag(caption)
    if letter and tag == tag_for(sha256):
        return letter, "tag"
    m = match_in_script(caption, script) if caption else None
    if m:
        return m[0], "fingerprint"
    if hook_variants(script):
        return primary_variant(script), "primary"
    return None, None


def script_creative(script, variant_id=None, summary=None):
    """{hook_archetype, visual_type, vibe, tone, primary_keyword} for a posts
    row. script.json first: the matched variant's archetype + visual_type,
    direction.vibe, direction.tone.voice, discovery.primary_keyword; then the
    manifest script_summary's §1.6 fields (their archetype / visual type are
    the primary's, so they only fill the primary). Unknown -> None."""
    s = script if isinstance(script, dict) else {}
    var = dict(hook_variants(s)).get(variant_id) if variant_id else None
    tone = _dig(s, "direction", "tone")
    out = {"hook_archetype": _clean_id(var.get("archetype")) if var else None,
           "visual_type": _clean_id(var.get("visual_type")) if var else None,
           "vibe": _clean_id(_dig(s, "direction", "vibe")),
           "tone": _clean_id(tone.get("voice") if isinstance(tone, dict) else tone),
           "primary_keyword": _clean_id(_dig(s, "discovery", "primary_keyword"), 120)}
    ss = (summary or {}).get("creative") if isinstance(summary, dict) else None
    if isinstance(ss, dict):
        t = ss.get("tone")
        fb = {"vibe": ss.get("vibe"), "primary_keyword": ss.get("primary_keyword"),
              "tone": t.get("voice") if isinstance(t, dict) else t}
        if variant_id is not None and variant_id == primary_variant(s) and var is None:
            fb.update(hook_archetype=ss.get("hook_archetype"),
                      visual_type=ss.get("visual_type"))
        for k, v in fb.items():
            if out.get(k) is None:
                out[k] = _clean_id(v, 120 if k == "primary_keyword" else 80)
    return out


# ------------------------------------------------------------------ link
def load_summary(manifest_path):
    """-> the script summary for a run (see module doc). Raises LinkError."""
    mp = os.path.abspath(manifest_path)
    if os.path.isdir(mp):
        mp = os.path.join(mp, "manifest.json")
    if not os.path.isfile(mp):
        raise LinkError(f"manifest not found: {mp}")
    try:
        with open(mp, encoding="utf-8") as f:
            man = json.load(f)
    except (OSError, ValueError) as e:
        raise LinkError(f"manifest {mp} is not valid JSON: {e}")
    if not isinstance(man, dict):
        raise LinkError(f"manifest {mp} must be a JSON object")
    ss = man.get("script_summary")
    if isinstance(ss, dict) and ss.get("script_sha256"):
        out = {k: ss.get(k) for k in SUMMARY_KEYS}
        out["from"] = "script_summary"
        out["creative"] = {k: ss[k] for k in SUMMARY_CREATIVE_KEYS
                           if ss.get(k) is not None}
    else:
        sp = os.path.join(os.path.dirname(mp), "script.json")
        if not os.path.isfile(sp):
            raise LinkError(f"{mp} has no script_summary and there is no script.json "
                            f"next to it")
        with open(sp, "rb") as f:
            raw = f.read()
        try:
            s = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as e:
            raise LinkError(f"{sp} is not valid JSON: {e}")
        hook = None
        try:
            from vsp.rubric import hook_line
            hook = hook_line(s) or None
        except Exception:  # noqa: BLE001 — rubric optional here
            for h in s.get("hook_stack") or []:
                if isinstance(h, dict) and h.get("dialogue"):
                    hook = h["dialogue"]
                    break
        seeds = man.get("seeds") if isinstance(man.get("seeds"), dict) else {}
        args = man.get("args") if isinstance(man.get("args"), dict) else {}
        sel = man.get("selected") if isinstance(man.get("selected"), dict) else {}
        out = {"prompt": s.get("prompt"), "niche": s.get("niche"),
               "hook_family": s.get("hook_family"), "hook_source": s.get("hook_source"),
               "hook": hook, "presenter": s.get("presenter"), "format": s.get("format"),
               "duration_s": s.get("duration_s"),
               "seed": s.get("seed", seeds.get("root", args.get("seed"))),
               "candidate_seed": sel.get("seed"),
               "script_sha256": hashlib.sha256(raw).hexdigest(), "from": "script.json",
               "creative": {}}
    out["created"] = man.get("created") if isinstance(man.get("created"), str) else None
    sha = str(out.get("script_sha256") or "").lower()
    if not _SHA.match(sha):
        raise LinkError(f"{mp}: script_sha256 {out.get('script_sha256')!r} is not a "
                        f"sha256 hex digest")
    out["script_sha256"] = sha
    try:
        out["duration_s"] = float(out["duration_s"]) if out.get("duration_s") is not None \
            else None
    except (TypeError, ValueError):
        out["duration_s"] = None
    for k in ("seed", "candidate_seed"):
        try:
            out[k] = int(out[k]) if out.get(k) is not None else None
        except (TypeError, ValueError):
            out[k] = None
    out["manifest_path"] = mp
    out["slug"] = os.path.basename(os.path.dirname(mp))
    out["tag"] = tag_for(sha)
    return out


def link(con, media_id, manifest_path, trial=False, now=None, summary=None,
         variant=None, script=None, variant_from=None):
    """Link one posted reel to the run that produced it and to the opening
    it used (resolve_variant: `variant` > the caption's #vsp-<sha8><letter>
    > its fingerprint within the script > the primary; a re-link without
    new evidence keeps the stored variant). -> posts row dict (+
    "variant_from": how the variant was decided)."""
    from vsp.ingest.db import table_columns
    u = _util()
    mid = str(media_id or "").strip()
    if not re.fullmatch(r"[0-9]{5,25}", mid):
        raise LinkError(f"--media-id {media_id!r} must be the numeric Instagram media id "
                        f"(GET /{{ig-user-id}}/media, or `python3 -m vsp.ingest own`)")
    if variant is not None and not re.fullmatch(r"[A-Za-z]", str(variant).strip()):
        raise LinkError(f"--variant {variant!r} must be one letter: A = the primary "
                        f"opening, B, C … = the script's hook_variants ids")
    s = summary or load_summary(manifest_path)
    sc = script if script is not None else load_script(s.get("manifest_path")
                                                       or manifest_path)
    now_ts = u.sql_ts(u.parse_ts(now) or u.utcnow())
    reel = con.execute("SELECT url, posted_at, is_own, caption FROM reels WHERE platform="
                       "'instagram' AND media_id=?", (mid,)).fetchone()
    if reel is not None and not reel["is_own"]:
        raise LinkError(f"media {mid} is in the research DB as someone else's reel "
                        f"(is_own=0) — only your own reels can be linked")
    have = set(table_columns(con, "posts"))
    old = con.execute("SELECT * FROM posts WHERE media_id=?", (mid,)).fetchone()
    vid, how = resolve_variant(sc, s["script_sha256"], reel["caption"] if reel else None,
                               variant)
    if variant is not None and variant_from:
        how = variant_from
    if (old is not None and how in ("primary", None) and "variant_id" in old.keys()
            and old["variant_id"] and old["script_sha256"] == s["script_sha256"]):
        vid, how = old["variant_id"], "kept"
    row = {"media_id": mid, "permalink": reel["url"] if reel else None,
           "posted_at": reel["posted_at"] if reel else None,
           "script_sha256": s["script_sha256"], "slug": s.get("slug"),
           "prompt": s.get("prompt"), "niche": s.get("niche"),
           "hook_family": s.get("hook_family"), "hook_source": s.get("hook_source"),
           "presenter": s.get("presenter"), "format": s.get("format"),
           "duration_s": s.get("duration_s"), "seed": s.get("seed"),
           "manifest_path": s.get("manifest_path"), "is_trial": 1 if trial else 0,
           "linked_at": now_ts, "hook": s.get("hook"),
           "candidate_seed": s.get("candidate_seed"), "variant_id": vid}
    row.update(script_creative(sc, vid, s))
    row = {k: v for k, v in row.items() if k in have}     # a legacy posts table
    if old is not None:
        row["is_trial"] = 1 if (trial or old["is_trial"]) else 0
        sets = ", ".join(f"{k}=?" for k in row if k != "media_id")
        con.execute(f"UPDATE posts SET {sets} WHERE media_id=?",
                    [v for k, v in row.items() if k != "media_id"] + [mid])
    else:
        cols = list(row)
        con.execute(f"INSERT INTO posts({', '.join(cols)}) VALUES "
                    f"({', '.join('?' for _ in cols)})", [row[c] for c in cols])
    if reel is not None:
        con.execute("UPDATE reels SET script_slug=?, is_trial=MAX(COALESCE(is_trial, 0), ?) "
                    "WHERE platform='instagram' AND media_id=?",
                    (s["tag"], row["is_trial"], mid))
    con.commit()
    return dict(row, variant_from=how)


def search_roots(extra=None, env=None):
    e = os.environ if env is None else env
    roots = [config.outputs_dir()]
    roots += [p for p in (e.get("VSP_FEEDBACK_SEARCH") or "").split(os.pathsep) if p]
    roots += list(extra or [])
    out = []
    for r in roots:
        a = os.path.abspath(os.path.expanduser(r))
        if a not in out and os.path.isdir(a):
            out.append(a)
    return out


def index_manifests(roots, max_files=20000):
    """{sha8: {script_sha256: [(mtime, manifest_path)]}} for every readable
    manifest.json under `roots`."""
    idx, seen = {}, 0
    for root in roots:
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d not in _SKIP_DIRS]
            if "manifest.json" not in fns:
                continue
            seen += 1
            if seen > max_files:
                return idx
            mp = os.path.join(dp, "manifest.json")
            try:
                s = load_summary(mp)
            except LinkError:
                continue
            idx.setdefault(s["script_sha256"][:8], {}).setdefault(
                s["script_sha256"], []).append((os.path.getmtime(mp), mp))
    return idx


def fingerprint_index(roots, max_files=20000):
    """Fingerprint candidates: every manifest.json under `roots` whose
    script.json yields caption fingerprints -> [{"manifest", "summary",
    "script", "created" (aware UTC: manifest `created`, else its mtime),
    "fps": [(variant_id, fingerprint, tokens)]}], sorted by (created, path)."""
    u = _util()
    out, seen = [], 0
    for root in roots:
        for dp, dns, fns in os.walk(root):
            dns[:] = sorted(d for d in dns if d not in _SKIP_DIRS)
            if "manifest.json" not in fns:
                continue
            seen += 1
            if seen > max_files:
                return sorted(out, key=lambda c: (c["created"], c["manifest"]))
            mp = os.path.join(dp, "manifest.json")
            try:
                s = load_summary(mp)
            except LinkError:
                continue
            sc = load_script(mp)
            fps = caption_fingerprints(sc)
            created = u.parse_ts(s.get("created"))
            if created is None:
                try:
                    created = u.parse_ts(os.path.getmtime(mp))
                except OSError:
                    created = None
            if fps and created is not None:
                out.append({"manifest": mp, "summary": s, "script": sc,
                            "created": created, "fps": fps})
    out.sort(key=lambda c: (c["created"], c["manifest"]))
    return out


def match_caption(caption, posted_at, index, window_days=FP_WINDOW_DAYS,
                  min_jaccard=FP_MIN_JACCARD):
    """Best fingerprint match of a posted caption among `index` runs created
    before `posted_at` and at most `window_days` earlier -> ({"candidate",
    "variant_id", "exact", "jaccard", "ties"}, None) or (None, reason).
    Ranking: exact > higher Jaccard > newer run > script sha > variant order >
    path; "ties" counts other scripts with the same (exact, Jaccard)."""
    u = _util()
    fp = fingerprint(caption)
    if not fp:
        return None, "no caption text"
    posted = u.parse_ts(posted_at)
    if posted is None:
        return None, "no posted_at"
    lo = posted - timedelta(days=window_days)
    hits = []
    for c in index:
        if not (lo <= c["created"] < posted):
            continue
        for order, (vid, cfp, ctoks) in enumerate(c["fps"]):
            sc = _fp_score(fp, cfp, ctoks, min_jaccard)
            if sc is not None:
                hits.append(((not sc[0], -round(sc[1], 12), -c["created"].timestamp(),
                              c["summary"]["script_sha256"], order, c["manifest"]),
                             c, vid, sc))
    if not hits:
        return None, "no fingerprint match"
    hits.sort(key=lambda h: h[0])
    key, c, vid, (exact, j) = hits[0]
    ties = {h[1]["summary"]["script_sha256"] for h in hits if h[0][:2] == key[:2]}
    return {"candidate": c, "variant_id": vid, "exact": exact, "jaccard": j,
            "ties": len(ties) - 1}, None


def link_auto(con, roots=None, now=None):
    """Link own reels to the runs (and variants) that made them: the
    caption's #vsp-<sha8>[<letter>] tag, else its caption fingerprint (see
    module doc). Report keys of v2.0 are unchanged; linked entries add
    variant_id + by ("tag" | "fingerprint"); "fingerprint" sums up the
    untagged reels that were tried."""
    rows = con.execute(
        "SELECT r.media_id, r.caption, r.script_slug, r.posted_at FROM reels r WHERE "
        "r.is_own = 1 AND r.platform = 'instagram' AND r.media_id IS NOT NULL AND NOT "
        "EXISTS (SELECT 1 FROM posts p WHERE p.media_id = r.media_id) "
        "ORDER BY r.posted_at, r.media_id").fetchall()
    rep = {"candidates": len(rows), "linked": [], "untagged": 0, "unmatched": [],
           "ambiguous": [], "roots": list(roots or []),
           "fingerprint": {"tried": 0, "linked": 0, "not_linked": {}}}
    todo, loose = [], []
    for r in rows:
        tag, letter = parse_tag(r["caption"])
        if not tag and r["script_slug"]:
            tag = str(r["script_slug"]).lower()
        if not tag:
            rep["untagged"] += 1
            loose.append(r)
            continue
        todo.append((r["media_id"], tag, letter))
    if todo:
        idx = index_manifests(rep["roots"])
        for mid, tag, letter in todo:
            cands = idx.get(tag[4:12], {})
            if not cands:
                rep["unmatched"].append({"media_id": mid, "tag": tag})
                continue
            if len(cands) > 1:
                rep["ambiguous"].append({"media_id": mid, "tag": tag,
                                         "scripts": sorted(cands)})
                continue
            (sha, paths), = cands.items()
            mp = max(paths)[1]                  # the newest run of that script
            row = link(con, mid, mp, now=now)
            rep["linked"].append({"media_id": mid, "tag": tag, "manifest": mp,
                                  "niche": row["niche"], "hook_family": row["hook_family"],
                                  "variant_id": row.get("variant_id"), "by": "tag",
                                  "variant_from": row.get("variant_from")})
    if loose:
        fidx = fingerprint_index(rep["roots"])
        fpr = rep["fingerprint"]
        for r in loose:
            fpr["tried"] += 1
            m, why = match_caption(r["caption"], r["posted_at"], fidx)
            if m is None:
                fpr["not_linked"][why] = fpr["not_linked"].get(why, 0) + 1
                continue
            c = m["candidate"]
            row = link(con, r["media_id"], c["manifest"], now=now, summary=c["summary"],
                       variant=m["variant_id"], script=c["script"],
                       variant_from="fingerprint")
            fpr["linked"] += 1
            rep["linked"].append({"media_id": r["media_id"], "tag": c["summary"]["tag"],
                                  "manifest": c["manifest"], "niche": row["niche"],
                                  "hook_family": row["hook_family"],
                                  "variant_id": row.get("variant_id"), "by": "fingerprint",
                                  "exact": m["exact"], "jaccard": round(m["jaccard"], 4),
                                  "ties": m["ties"]})
    return rep


# ------------------------------------------------------------------ pull
def bucket(age_h):
    """Largest checkpoint <= age_h (None below the first)."""
    got = [c for c in CHECKPOINTS if age_h is not None and age_h >= c]
    return got[-1] if got else None


def pull(con, client, now=None, link_first=True, roots=None, log=None):
    """Insight snapshots for own reels at the due checkpoints -> reel_metrics."""
    from vsp.ingest.graph import GraphError, RateLimited
    u = _util()
    log = log or (lambda m: None)
    now_dt = u.parse_ts(now) or u.utcnow()
    now_ts = u.sql_ts(now_dt)
    rep = {"job": "pull", "at": now_ts, "snapshots": 0, "due": 0, "skipped": {},
           "vanished": [], "errors": [], "stopped": None, "calls0": client.calls}
    if link_first:
        rep["link"] = link_auto(con, roots=roots if roots is not None else search_roots(),
                                now=now_dt)

    def skip(why):
        rep["skipped"][why] = rep["skipped"].get(why, 0) + 1
    rows = con.execute("SELECT media_id, posted_at FROM reels WHERE is_own = 1 AND "
                       "platform = 'instagram' AND media_id IS NOT NULL AND "
                       "purge_after IS NULL ORDER BY posted_at DESC").fetchall()
    for r in rows:
        mid = r["media_id"]
        age = u.hours_between(now_dt, r["posted_at"])
        due = bucket(age)
        if due is None:
            skip("younger than 24 h" if age is not None else "no posted_at")
            continue
        have = {bucket(a[0]) for a in con.execute(
            "SELECT age_h FROM reel_metrics WHERE media_id=?", (mid,))}
        if due in have:
            skip("checkpoint already captured")
            continue
        rep["due"] += 1
        try:
            ins = client.media_insights(mid)
        except RateLimited as e:
            rep["stopped"] = f"rate_limited: {e}"
            break
        except GraphError as e:
            if e.not_found:
                con.execute("UPDATE reels SET purge_after=? WHERE platform='instagram' "
                            "AND media_id=?", (now_ts, mid))
                rep["vanished"].append(mid)
                continue
            if e.token_problem or e.permission_problem:
                rep["stopped"] = f"{'token' if e.token_problem else 'permission'}: {e}"
                break
            rep["errors"].append(f"{mid}: {e}")
            continue
        if not ins:
            skip("no data yet (insights lag up to 48 h)")
            continue
        vals = {col: ins.get(name) for name, col in INSIGHT_COLUMNS.items()}
        con.execute(
            "INSERT OR REPLACE INTO reel_metrics(media_id, captured_at, age_h, views, "
            "reach, likes, comments, shares, saves, reposts, avg_watch_ms, "
            "total_watch_ms, skip_rate, source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (mid, now_ts, int(age), vals["views"], vals["reach"], vals["likes"],
             vals["comments"], vals["shares"], vals["saves"], vals["reposts"],
             vals["avg_watch_ms"], vals["total_watch_ms"], vals["skip_rate"], "api"))
        con.execute("UPDATE reels SET views=COALESCE(?, views), like_count=COALESCE(?, "
                    "like_count), comments=COALESCE(?, comments), shares=COALESCE(?, "
                    "shares), saves=COALESCE(?, saves) WHERE platform='instagram' AND "
                    "media_id=?", (vals["views"], vals["likes"], vals["comments"],
                                   vals["shares"], vals["saves"], mid))
        rep["snapshots"] += 1
        log(f"{mid}: snapshot at {int(age)} h (checkpoint {due} h)")
    con.execute("UPDATE posts SET permalink=(SELECT url FROM reels WHERE reels.media_id="
                "posts.media_id AND reels.platform='instagram'), posted_at=(SELECT "
                "posted_at FROM reels WHERE reels.media_id=posts.media_id AND "
                "reels.platform='instagram') WHERE (permalink IS NULL OR posted_at IS "
                "NULL) AND EXISTS (SELECT 1 FROM reels WHERE reels.media_id="
                "posts.media_id)")
    con.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('last_run:pull', ?)",
                (now_ts,))
    con.commit()
    rep["api_calls"] = client.calls - rep.pop("calls0")
    if client.dropped_metrics:
        rep["dropped_metrics"] = sorted(client.dropped_metrics)
    return rep


# ---------------------------------------------------------------- labels
def _ratio(a, b):
    if a is None or b in (None, 0):
        return None
    try:
        return float(a) / float(b)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _snapshots(con):
    """media_id -> its latest reel_metrics row at >= 24 h (or of unknown age)."""
    snaps = {}
    for s in con.execute("SELECT * FROM reel_metrics WHERE age_h IS NULL OR age_h >= 24 "
                         "ORDER BY media_id, age_h, captured_at"):
        snaps[s["media_id"]] = s                        # keeps the latest per media
    return snaps


def _skip_scale(snaps):
    """100.0 when the account's skip rates are percents (any value > 1), else
    1.0 — one rule for learn and variants."""
    skips = [s["skip_rate"] for s in snaps.values() if s["skip_rate"] is not None]
    return 100.0 if any(float(v) > 1.0 for v in skips) else 1.0


def _posts_select(con, cols, alias="p"):
    """'p.col, …' for posts columns, 'NULL AS col' for ones a legacy posts
    table lacks (a connection opened without migrating)."""
    from vsp.ingest.db import table_columns
    have = set(table_columns(con, "posts"))
    return ", ".join(f"{alias}.{c}" if c in have else f"NULL AS {c}" for c in cols)


def labels(con, window=WINDOW):
    """Per-post labels (module doc). -> {"posts": [...newest first], "median",
    "window", "skip_scale", "stats", "pending": {...}}. Posts also carry the
    v2.1 columns (variant_id, hook_archetype, visual_type, vibe, tone,
    primary_keyword) and script_sha256 (None when unknown)."""
    rows = con.execute(
        "SELECT r.media_id, r.url, r.posted_at, r.hook_text, r.is_trial AS reel_trial, "
        "p.niche, p.hook_family, p.hook_source, p.hook, p.duration_s, p.is_trial, "
        "p.presenter, p.format, p.slug, p.media_id AS linked, p.script_sha256, "
        + _posts_select(con, CREATIVE_COLUMNS) + " FROM reels r LEFT JOIN "
        "posts p ON p.media_id = r.media_id WHERE r.is_own = 1 AND r.platform = "
        "'instagram' AND r.media_id IS NOT NULL AND r.purge_after IS NULL "
        "ORDER BY r.posted_at DESC, r.media_id DESC").fetchall()
    snaps = _snapshots(con)
    scale = _skip_scale(snaps)
    posts, pending = [], {"no snapshot >= 24 h": 0}
    for r in rows:
        s = snaps.get(r["media_id"])
        if s is None:
            pending["no snapshot >= 24 h"] += 1
            continue
        hr = None
        if s["skip_rate"] is not None:
            hr = min(1.0, max(0.0, 1.0 - float(s["skip_rate"]) / scale))
        wr = _ratio(_ratio(s["avg_watch_ms"], 1000.0), r["duration_s"])
        if wr is not None:
            wr = min(wr, 3.0)                           # replays: cap outliers
        p = {"media_id": r["media_id"], "url": r["url"], "posted_at": r["posted_at"],
             "niche": r["niche"], "hook_family": r["hook_family"],
             "hook_source": r["hook_source"], "hook": r["hook"] or r["hook_text"],
             "presenter": r["presenter"], "format": r["format"], "slug": r["slug"],
             "linked": r["linked"] is not None,
             "trial": bool(r["is_trial"] or r["reel_trial"]),
             "age_h": s["age_h"], "views": s["views"], "reach": s["reach"],
             "hook_rate": hr, "watch_ratio": wr,
             "share_rate": _ratio(s["shares"], s["reach"]),
             "save_rate": _ratio(s["saves"], s["reach"]),
             "script_sha256": r["script_sha256"]}
        p.update({c: r[c] for c in CREATIVE_COLUMNS})
        if all(p[k] is None for k in LABELS):
            pending["snapshot without usable metrics"] = \
                pending.get("snapshot without usable metrics", 0) + 1
            continue
        posts.append(p)
    posts = posts[:window]
    stats = {}
    for k in LABELS:
        xs = [p[k] for p in posts if p[k] is not None]
        mu = statistics.mean(xs) if xs else None
        sd = statistics.pstdev(xs) if len(xs) >= 2 else 0.0
        stats[k] = {"n": len(xs), "mean": mu, "sd": sd}
    for p in posts:
        zs = []
        for k in LABELS:
            if p[k] is None:
                continue
            sd = stats[k]["sd"]
            zs.append((p[k] - stats[k]["mean"]) / sd if sd and sd > 1e-12 else 0.0)
            p["z_" + k] = zs[-1]
        p["composite"] = sum(zs) / len(zs)
    med = statistics.median([p["composite"] for p in posts]) if posts else None
    for p in posts:
        p["success"] = bool(p["composite"] >= med - 1e-12)
    return {"posts": posts, "median": med, "window": window,
            "skip_scale": "percent" if scale == 100.0 else "fraction",
            "stats": stats, "pending": pending}


def posteriors(lab):
    """-> (families {niche: {family: {alpha, beta, n}}}, global {family: ...})"""
    from vsp.ingest.settings import MAKER_NICHES
    from vsp.research import maker_hook_families
    fams = set(maker_hook_families())
    per, glob = {}, {}
    for p in lab["posts"]:
        n, f = p.get("niche"), p.get("hook_family")
        if not p["linked"] or n not in MAKER_NICHES or f not in fams:
            continue
        for tbl in (per.setdefault(n, {}), glob):
            e = tbl.setdefault(f, {"alpha": 1.0, "beta": 1.0, "n": 0})
            e["alpha" if p["success"] else "beta"] += 1.0
            e["n"] += 1
    return ({n: dict(sorted(t.items())) for n, t in sorted(per.items())},
            dict(sorted(glob.items())))


# priors v2 sections (vsp.priors.SECTIONS, same order) -> the posts column
SECTION_COLUMNS = {"archetype": "hook_archetype", "visual_type": "visual_type",
                   "vibe": "vibe", "tone": "tone"}
SECTIONS = tuple(SECTION_COLUMNS)


def section_vocab():
    """{section: frozenset(valid ids)} from vsp.creative_vocab (an empty set
    accepts any id, should the vocabulary module be absent)."""
    try:
        from vsp import creative_vocab as V
    except ImportError:
        return {s: frozenset() for s in SECTIONS}
    return {"archetype": frozenset(V.HOOK_ARCHETYPES),
            "visual_type": frozenset(V.VISUAL_TYPES),
            "vibe": frozenset(V.VIBES), "tone": frozenset(V.TONES)}


def section_posteriors(lab):
    """-> {section: {"by_niche": {niche: {key: {alpha, beta, n}}}, "global":
    {key: {...}}}} for SECTIONS: the families rule (linked post, maker niche,
    Beta(1, 1) + wins / losses of the same success label) over the posts
    whose key is known and a creative_vocab id."""
    from vsp.ingest.settings import MAKER_NICHES
    vocab = section_vocab()
    out = {}
    for sec, col in SECTION_COLUMNS.items():
        per, glob = {}, {}
        for p in lab["posts"]:
            n, k = p.get("niche"), p.get(col)
            if (not p["linked"] or n not in MAKER_NICHES or not isinstance(k, str) or not k
                    or (vocab[sec] and k not in vocab[sec])):
                continue
            for tbl in (per.setdefault(n, {}), glob):
                e = tbl.setdefault(k, {"alpha": 1.0, "beta": 1.0, "n": 0})
                e["alpha" if p["success"] else "beta"] += 1.0
                e["n"] += 1
        out[sec] = {"by_niche": {n: dict(sorted(t.items())) for n, t in sorted(per.items())},
                    "global": dict(sorted(glob.items()))}
    return out


def validate_priors(obj):
    """learned/README.md schema v1 or v2 -> list of problems ([] = valid).
    v2 = v1 + "sections": every SECTIONS name -> {"by_niche": {niche: {key:
    entry}}, "global": {key: entry}}, entries as in v1."""
    errs = []
    if not isinstance(obj, dict):
        return ["priors must be a JSON object"]
    ver = obj.get("schema_version")
    want = {"schema_version", "updated_at", "metric", "families", "global"}
    if ver == 2 and not isinstance(ver, bool):
        want = want | {"sections"}
    if set(obj) != want:
        errs.append(f"top-level keys {sorted(obj)} != {sorted(want)}")
    if isinstance(ver, bool) or ver not in (1, 2):
        errs.append("schema_version must be 1 or 2")
    if _util().parse_ts(obj.get("updated_at")) is None:
        errs.append("updated_at must be an ISO timestamp")
    if not isinstance(obj.get("metric"), str) or not obj.get("metric"):
        errs.append("metric must be a non-empty string")

    def entry(where, e):
        if not isinstance(e, dict) or set(e) != {"alpha", "beta", "n"}:
            errs.append(f"{where} must be {{alpha, beta, n}}")
            return
        a, b, n = e["alpha"], e["beta"], e["n"]
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                   and math.isfinite(v) for v in (a, b)) or a <= 0 or b <= 0:
            errs.append(f"{where}: alpha/beta must be positive numbers")
        if not isinstance(n, int) or isinstance(n, bool) or n < 0:
            errs.append(f"{where}: n must be a non-negative integer")
        elif abs((a + b - 2.0) - n) > 1e-9:
            errs.append(f"{where}: alpha + beta - 2 != n (prior Beta(1,1))")
    fams = obj.get("families")
    if not isinstance(fams, dict):
        errs.append("families must be an object")
    else:
        for niche, tbl in fams.items():
            if not isinstance(tbl, dict):
                errs.append(f"families[{niche!r}] must be an object")
                continue
            for fam, e in tbl.items():
                entry(f"families[{niche!r}][{fam!r}]", e)
    glob = obj.get("global")
    if not isinstance(glob, dict):
        errs.append("global must be an object")
    else:
        for fam, e in glob.items():
            entry(f"global[{fam!r}]", e)
    if "sections" in want:
        secs = obj.get("sections")
        if not isinstance(secs, dict) or set(secs) != set(SECTIONS):
            errs.append(f"sections must be an object with exactly {list(SECTIONS)}")
            secs = secs if isinstance(secs, dict) else {}
        for sec, body in secs.items():
            if not isinstance(body, dict) or set(body) != {"by_niche", "global"}:
                errs.append(f"sections[{sec!r}] must be {{by_niche, global}}")
                continue
            by, g = body["by_niche"], body["global"]
            if not isinstance(by, dict) or not isinstance(g, dict):
                errs.append(f"sections[{sec!r}]: by_niche and global must be objects")
                continue
            for niche, tbl in by.items():
                if not isinstance(tbl, dict):
                    errs.append(f"sections[{sec!r}].by_niche[{niche!r}] must be an object")
                    continue
                for key, e in tbl.items():
                    entry(f"sections[{sec!r}].by_niche[{niche!r}][{key!r}]", e)
            for key, e in g.items():
                entry(f"sections[{sec!r}].global[{key!r}]", e)
    return errs


def _write_atomic(path, text):
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def learn(con, now=None, path=None, window=WINDOW):
    """labels -> posteriors -> learned/priors.json. -> report. schema_version
    2 (v1 + "sections") as soon as any section has data; otherwise the file
    is exactly v1, so readers that only know v1 keep working."""
    u = _util()
    now_dt = u.parse_ts(now) or u.utcnow()
    lab = labels(con, window=window)
    fams, glob = posteriors(lab)
    secs = section_posteriors(lab)
    pri = {"schema_version": 1, "updated_at": u.iso_ts(now_dt), "metric": METRIC,
           "families": fams, "global": glob}
    if any(body["global"] for body in secs.values()):
        pri["schema_version"] = 2
        pri["sections"] = secs
    errs = validate_priors(pri)
    if errs:                      # never write a file the maker would reject
        raise ValueError("priors failed validation: " + "; ".join(errs))
    p = path or config.priors_path()
    if not lab["posts"] and os.path.isfile(p):
        # no labelled posts (wrong DB? insights not pulled yet?): keep the last
        # good priors instead of resetting the maker to neutral
        return {"job": "learn", "priors": p, "kept": True, "labelled": 0, "linked": 0,
                "median_composite": None, "skip_scale": lab["skip_scale"],
                "families": {}, "global": {}, "pending": lab["pending"],
                "schema_version": None, "sections": {}}
    _write_atomic(p, json.dumps(pri, indent=1, sort_keys=False) + "\n")
    con.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('last_run:learn', ?)",
                (u.sql_ts(now_dt),))
    con.commit()
    return {"job": "learn", "priors": p, "labelled": len(lab["posts"]),
            "linked": sum(1 for x in lab["posts"] if x["linked"]),
            "median_composite": lab["median"], "skip_scale": lab["skip_scale"],
            "families": {n: {f: e["n"] for f, e in t.items()} for n, t in fams.items()},
            "global": {f: e["n"] for f, e in glob.items()}, "pending": lab["pending"],
            "schema_version": pri["schema_version"],
            "sections": {s: {k: e["n"] for k, e in b["global"].items()}
                         for s, b in secs.items() if b["global"]}}


# ---------------------------------------------------------------- report
def _betacf(a, b, x):
    tiny, eps = 1e-300, 3e-14
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 301):
        m2 = 2 * m
        for aa in (m * (b - m) * x / ((qam + m2) * (a + m2)),
                   -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))):
            d = 1.0 + aa * d
            d = 1.0 / (d if abs(d) > tiny else tiny)
            c = 1.0 + aa / c
            c = c if abs(c) > tiny else tiny
            h *= d * c
        if abs(d * c - 1.0) < eps:
            break
    return h


def beta_cdf(x, a, b):
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbt = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
           + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(lbt) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbt) * _betacf(b, a, 1.0 - x) / b


def beta_ppf(q, a, b):
    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if beta_cdf(mid, a, b) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def interval90(a, b):
    return beta_ppf(0.05, a, b), beta_ppf(0.95, a, b)


def _pct(v, digits=0):
    return "—" if v is None else f"{100.0 * v:.{digits}f}%"


def _verdict(e, min_n=3):
    mean = e["alpha"] / (e["alpha"] + e["beta"])
    if e["n"] < min_n:
        return "too early", mean
    lo, hi = interval90(e["alpha"], e["beta"])
    if mean >= 0.6 and lo > 0.3:
        return "working", mean
    if mean <= 0.4 and hi < 0.7:
        return "not working", mean
    return "mixed", mean


def report(con, now=None, path=None, window=WINDOW):
    """-> (path, text) of learned/PERFORMANCE.md."""
    u = _util()
    now_dt = u.parse_ts(now) or u.utcnow()
    lab = labels(con, window=window)
    fams, glob = posteriors(lab)
    posts = lab["posts"]
    L = ["# PERFORMANCE — what is working for this account", "",
         f"Updated {u.sql_ts(now_dt)} UTC by `python3 -m vsp.feedback report`. "
         f"{len(posts)} labelled own reels (last {window}), "
         f"{sum(1 for p in posts if p['linked'])} linked to a script. A post is a "
         f"**success** when its composite score (mean within-account z-score of hook "
         f"rate = 1 − skip rate, watch ratio, share rate, save rate) is at or above the "
         f"account median"
         + (f" ({lab['median']:+.2f})." if lab["median"] is not None else ".")
         + " Posteriors are Beta(1 + wins, 1 + losses); the maker only lets families "
           "with n ≥ 3 steer its hook choice.", ""]
    L += ["## Niche × hook family", ""]
    if fams:
        L += ["| niche | hook family | n | wins | posterior mean | ~90% interval | verdict |",
              "|---|---|---:|---:|---:|---|---|"]
        for niche, tbl in fams.items():
            for fam, e in sorted(tbl.items(), key=lambda kv: -kv[1]["alpha"] /
                                 (kv[1]["alpha"] + kv[1]["beta"])):
                lo, hi = interval90(e["alpha"], e["beta"])
                v, mean = _verdict(e)
                L.append(f"| {niche} | {fam} | {e['n']} | {int(e['alpha'] - 1)} | "
                         f"{_pct(mean)} | {_pct(lo)}–{_pct(hi)} | {v} |")
    else:
        L.append("_No linked, labelled posts yet._ Tag captions with `#vsp-<sha8>` "
                 "(see below), run `python3 -m vsp.ingest own` and "
                 "`python3 -m vsp.feedback pull`, and wait ≥ 24 h.")
    L += ["", "## All niches (global)", ""]
    if glob:
        L += ["| hook family | n | posterior mean | ~90% interval | verdict |",
              "|---|---:|---:|---|---|"]
        for fam, e in sorted(glob.items(), key=lambda kv: -kv[1]["alpha"] /
                             (kv[1]["alpha"] + kv[1]["beta"])):
            lo, hi = interval90(e["alpha"], e["beta"])
            v, mean = _verdict(e)
            L.append(f"| {fam} | {e['n']} | {_pct(mean)} | {_pct(lo)}–{_pct(hi)} | {v} |")
    else:
        L.append("_Nothing yet._")

    def line(p):
        who = " / ".join(x for x in (p.get("niche"), p.get("hook_family")) if x) or \
            "unlinked"
        hook = (p.get("hook") or "").strip()
        return (f"- {p.get('url') or p['media_id']} — {who}"
                + (f" — “{hook[:90]}”" if hook else "")
                + f" — composite {p['composite']:+.2f} (hook rate {_pct(p['hook_rate'])}, "
                  f"watch {_pct(p['watch_ratio'])}, shares {_pct(p['share_rate'], 1)}, "
                  f"saves {_pct(p['save_rate'], 1)}"
                + (", trial" if p.get("trial") else "") + ")")
    ranked = sorted(posts, key=lambda p: -p["composite"])
    k = min(3, max(1, len(ranked) // 2)) if ranked else 0
    L += ["", "## Best posts", ""] + ([line(p) for p in ranked[:k]] or ["_None yet._"])
    L += ["", "## Worst posts", ""] + ([line(p) for p in ranked[::-1][:k]]
                                       if len(ranked) > 1 else ["_None yet._"])
    L += ["", "## What's working", ""] + _plain_english(lab, fams, glob)
    acct = _account_lines(con, posts, now_dt)
    if acct:
        L += ["", "## Follows by posting day (account insights)", ""] + acct
    pend = dict(lab["pending"])
    unlinked = con.execute("SELECT COUNT(*) FROM reels r WHERE r.is_own = 1 AND "
                           "r.purge_after IS NULL AND NOT EXISTS (SELECT 1 FROM posts p "
                           "WHERE p.media_id = r.media_id)").fetchone()[0]
    L += ["", "## Pending", "",
          f"- {unlinked} own reels are not linked to a script (no `#vsp-` tag, or no "
          f"matching manifest.json) — they count toward the account median only.",
          f"- {pend.get('no snapshot >= 24 h', 0)} own reels have no insights snapshot "
          f"at ≥ 24 h yet."]
    L += ["", "## How the loop works", "",
          "1. Post the reel with `#vsp-<first 8 hex of script_sha256>` in the caption "
          "(manifest.json → script_summary.script_sha256), or link it by hand: "
          "`python3 -m vsp.feedback link --media-id ID --manifest outputs/<slug>/"
          "manifest.json [--trial]`.",
          "2. Hourly: `python3 -m vsp.ingest own && python3 -m vsp.feedback pull` "
          "(snapshots at ~24 h, 48 h, 7 d, 28 d).",
          "3. Daily: `python3 -m vsp.feedback learn && python3 -m vsp.feedback report` "
          "→ learned/priors.json + this file."]
    text = "\n".join(L) + "\n"
    p = path or os.path.join(config.learned_dir(), "PERFORMANCE.md")
    _write_atomic(p, text)
    return p, text


def _plain_english(lab, fams, glob):
    out = []
    posts = lab["posts"]
    if len(posts) < 2:
        return ["- Not enough labelled posts yet to say anything (need ≥ 2; the maker "
                "needs ≥ 3 per family before priors steer it)."]
    for niche, tbl in fams.items():
        judged = [(fam, e) + _verdict(e) for fam, e in tbl.items()]
        good = sorted([j for j in judged if j[2] == "working"], key=lambda j: -j[3])
        bad = sorted([j for j in judged if j[2] == "not working"], key=lambda j: j[3])
        for fam, e, _, mean in good[:2]:
            out.append(f"- In **{niche}**, **{fam}** hooks beat your median "
                       f"{int(e['alpha'] - 1)} of {e['n']} times (posterior {_pct(mean)})"
                       f" — keep using them.")
        for fam, e, _, mean in bad[:1]:
            out.append(f"- In **{niche}**, **{fam}** hooks underperform ("
                       f"{int(e['alpha'] - 1)} of {e['n']} above median, posterior "
                       f"{_pct(mean)}) — try another family.")
        early = [j for j in judged if j[2] == "too early"]
        if early and not good and not bad:
            best = max(early, key=lambda j: j[3])
            out.append(f"- In **{niche}**, too early to call: the best early signal is "
                       f"**{best[0]}** ({int(best[1]['alpha'] - 1)} of {best[1]['n']}); "
                       f"post ≥ 3 per family.")
    if glob:
        fam, e = max(glob.items(), key=lambda kv: kv[1]["alpha"] / (kv[1]["alpha"] +
                                                                    kv[1]["beta"]))
        out.append(f"- Across niches, **{fam}** leads ({int(e['alpha'] - 1)} of {e['n']} "
                   f"above median).")
    wins = [p for p in posts if p["success"]]
    rest = [p for p in posts if not p["success"]]
    names = {"hook_rate": "hook rate (1 − 3-second skip rate)",
             "watch_ratio": "watch ratio (avg watch ÷ duration)",
             "share_rate": "share rate", "save_rate": "save rate"}
    diffs = []
    for k in LABELS:
        sd = lab["stats"][k]["sd"]
        a = [p[k] for p in wins if p[k] is not None]
        b = [p[k] for p in rest if p[k] is not None]
        if a and b and sd:
            diffs.append(((statistics.mean(a) - statistics.mean(b)) / sd, k,
                          statistics.mean(a), statistics.mean(b)))
    if diffs:
        d, k, a, b = max(diffs)
        digits = 1 if k in ("share_rate", "save_rate") else 0
        out.append(f"- The biggest gap between your winners and the rest is "
                   f"{names[k]}: {_pct(a, digits)} vs {_pct(b, digits)}.")
    st = lab["stats"]["hook_rate"]
    if st["n"]:
        out.append(f"- Average hook rate across the last {len(posts)} posts: "
                   f"{_pct(st['mean'])} of viewers stay past 3 seconds.")
    trials = [p for p in posts if p.get("trial")]
    if trials:
        tw = sum(1 for p in trials if p["success"])
        out.append(f"- Trial Reels: {tw} of {len(trials)} beat the median (trials reach "
                   f"non-followers first, so compare them with care).")
    return out or ["- No clear pattern yet."]


def _account_lines(con, posts, now_dt):
    since = (now_dt - timedelta(days=14)).strftime("%Y-%m-%d")
    rows = con.execute("SELECT date, breakdown, value FROM account_metrics WHERE metric="
                       "'follows_and_unfollows' AND date >= ? ORDER BY date DESC",
                       (since,)).fetchall()
    if not rows:
        return []
    by_day = {}
    for r in rows:
        by_day.setdefault(r["date"], {})[r["breakdown"] or "total"] = r["value"]
    out = []
    for day, v in sorted(by_day.items(), reverse=True)[:7]:
        todays = [p for p in posts if str(p.get("posted_at") or "")[:10] == day]
        total = v.get("total")
        out.append(f"- {day}: {total if total is not None else '?'} follows "
                   f"(followers {v.get('follower', '?')}, non-followers "
                   f"{v.get('non_follower', '?')}) — {len(todays)} post(s) that day"
                   + (": " + ", ".join((p.get("hook_family") or "unlinked")
                                       for p in todays) if todays else ""))
    return out


def status(con, now=None):
    u = _util()
    now_dt = u.parse_ts(now) or u.utcnow()
    one = lambda q, a=(): con.execute(q, a).fetchone()[0]  # noqa: E731
    due = 0
    for r in con.execute("SELECT media_id, posted_at FROM reels WHERE is_own = 1 AND "
                         "purge_after IS NULL AND media_id IS NOT NULL"):
        b = bucket(u.hours_between(now_dt, r["posted_at"]))
        if b is not None and b not in {bucket(a[0]) for a in con.execute(
                "SELECT age_h FROM reel_metrics WHERE media_id=?", (r["media_id"],))}:
            due += 1
    pri = config.priors_path()
    info = None
    if os.path.isfile(pri):
        try:
            with open(pri, encoding="utf-8") as f:
                obj = json.load(f)
            info = {"path": pri, "updated_at": obj.get("updated_at"),
                    "niches": len(obj.get("families") or {}),
                    "global_families": len(obj.get("global") or {}),
                    "valid": not validate_priors(obj)}
        except (OSError, ValueError):
            info = {"path": pri, "valid": False}
    return {"own_reels": one("SELECT COUNT(*) FROM reels WHERE is_own = 1"),
            "own_tagged": one("SELECT COUNT(*) FROM reels WHERE is_own = 1 AND "
                              "script_slug IS NOT NULL"),
            "linked": one("SELECT COUNT(*) FROM posts"),
            "trials": one("SELECT COUNT(*) FROM posts WHERE is_trial = 1"),
            "snapshots": one("SELECT COUNT(*) FROM reel_metrics"),
            "checkpoints_due": due,
            "vanished": one("SELECT COUNT(*) FROM reels WHERE is_own = 1 AND "
                            "purge_after IS NOT NULL"),
            "last_runs": {k.split(":", 1)[1]: v for k, v in con.execute(
                "SELECT key, value FROM meta WHERE key IN ('last_run:pull', "
                "'last_run:learn', 'last_run:own')")},
            "priors": info,
            "performance_md": os.path.join(config.learned_dir(), "PERFORMANCE.md")
            if os.path.isfile(os.path.join(config.learned_dir(), "PERFORMANCE.md"))
            else None}


# --------------------------------------------------------------- selfcheck
LEARN_FIXTURES = os.path.join(config.REPO, "tests", "fixtures", "learn")
_V20_POSTS_DDL = (  # the posts table as pipeline v2.0 created it (hook + candidate_seed)
    "CREATE TABLE posts(media_id TEXT PRIMARY KEY, permalink TEXT, posted_at TEXT, "
    "script_sha256 TEXT, slug TEXT, prompt TEXT, niche TEXT, hook_family TEXT, "
    "hook_source TEXT, presenter TEXT, format TEXT, duration_s REAL, seed INTEGER, "
    "manifest_path TEXT, is_trial INTEGER DEFAULT 0, linked_at TEXT, hook TEXT, "
    "candidate_seed INTEGER)")


def selfcheck():
    """Hermetic self-check -> (ok, lines): the v2.0 loop
    (vsp.ingest.checks.run_feedback: temp DB via VSP_VIRAL_DB, temp learned
    dir via VSP_LEARNED_DIR, canned Graph API responses from tests/fixtures/ig,
    network disabled) + selfcheck_v21() (variant linking, priors v2,
    variants, report sections, determinism) on tests/fixtures/learn. The
    caller's env is restored."""
    from vsp.ingest.checks import run_feedback
    ok1, lines1 = run_feedback()
    ok2, lines2 = selfcheck_v21()
    return ok1 and ok2, list(lines1) + list(lines2)


class _Checker:
    def __init__(self, title):
        self.title, self.lines, self.ok = title, [], True

    def check(self, name, cond, detail=""):
        cond = bool(cond)
        self.lines.append(f"{'PASS' if cond else 'FAIL'} {name}"
                          + (f" — {detail}" if detail not in ("", None) else ""))
        self.ok = self.ok and cond
        return cond

    def step(self, name, fn, *a):
        import traceback
        try:
            return fn(*a)
        except Exception as e:  # noqa: BLE001 — a crash is a failure, never fatal
            tb = traceback.format_exc().strip().splitlines()[-3:]
            self.check(name, False, f"crashed: {type(e).__name__}: {e} | "
                       + " | ".join(t.strip() for t in tb))
            return None

    def result(self):
        n_fail = sum(1 for x in self.lines if x.startswith("FAIL"))
        self.lines.append(f"{self.title}: {len(self.lines) - n_fail} passed, "
                          f"{n_fail} failed")
        return self.ok, list(self.lines)


def selfcheck_v21():
    """-> (ok, lines) for the v2.1 layer, hermetic (vsp.fixtures.
    hermetic_ingest_env): synthetic manifests + the contract-shaped
    script.json fixtures in tests/fixtures/learn, a temp research DB."""
    from vsp.fixtures import hermetic_ingest_env
    C = _Checker("vsp.feedback v2.1 selfcheck (variants, fingerprints, priors v2)")
    repo_learned = os.path.join(config.REPO, "learned")
    before = sorted(os.listdir(repo_learned)) if os.path.isdir(repo_learned) else []
    try:
        with hermetic_ingest_env("vsp_feedback_v21_") as ctx:
            for k in ("VSP_FEEDBACK_SEARCH", "VSP_NO_PRIORS"):
                os.environ.pop(k, None)
            C.step("tag + fingerprint units", _sc_units, C)
            C.step("migration on a legacy DB", _sc_migration, C, ctx)
            sc = C.step("scenario", _sc_build, C, ctx)
            if sc:
                try:
                    for name, fn in (("link", _sc_link), ("learn", _sc_learn)):
                        C.step(name, fn, C, ctx, sc)
                finally:
                    sc["con"].close()
    except Exception as e:  # noqa: BLE001
        C.check("v2.1 selfcheck harness", False, f"{type(e).__name__}: {e}")
    C.check("hermetic: repo learned/ untouched",
            (sorted(os.listdir(repo_learned)) if os.path.isdir(repo_learned) else [])
            == before)
    return C.result()


def _sc_units(C):
    C.check("tag: #vsp-<sha8><letter> -> variant, #vsp-<sha8> -> none; glued / short "
            "tags rejected",
            parse_tag("x #vsp-0A1b2c3dB y") == ("vsp-0a1b2c3d", "B") and
            parse_tag("#vsp-0a1b2c3d #fyp") == ("vsp-0a1b2c3d", None) and
            parse_tag("#vsp-0a1b2c3de.") == ("vsp-0a1b2c3d", "E") and
            parse_tag("#vsp-0a1b2c3dxy") == (None, None) and
            parse_tag("#vsp-0a1b2c3") == (None, None) and parse_tag(None) == (None, None))
    fp = fingerprint("🔥🔥\n#ad #vsp-0a1b2c3dB\nDon’t buy a FROTHER… until you see "
                     "this! 👀 @brand.co https://x.co/a #milkfrother")
    C.check("fingerprint: first line with words; NFKC + lowercase; hashtags, #vsp "
            "tag, @mentions, URLs, emoji, punctuation stripped",
            fp == "dont buy a frother until you see this" and
            fingerprint("#1 mistake: 𝐓𝐡𝐞 foam👩‍🍳") == "1 mistake the foam" and
            fingerprint("#only #tags 🔥") == "" and fingerprint(None) == "", repr(fp))
    a = fingerprint("This sunset lamp turns any bedroom into golden hour.")
    ta = frozenset(a.split())
    C.check("jaccard edges: 8/10 = 0.8 accepted, 8/11 rejected, reordered = 1.0 but "
            "not exact",
            _fp_score(fingerprint("This sunset lamp turns any room into golden hour"),
                      a, ta) == (False, 0.8) and
            _fp_score(fingerprint("This sunset lamp turns any room into a golden hour"),
                      a, ta) is None and _fp_score(a, a, ta) == (True, 1.0) and
            _fp_score("golden hour into any bedroom turns lamp sunset this", a, ta)
            == (False, 1.0) and abs(jaccard(a, "this sunset lamp") - 1 / 3) < 1e-12)


def _sc_migration(C, ctx):
    import sqlite3
    from vsp.fixtures import build_fixture_db
    from vsp.ingest import db as idb
    p = os.path.join(ctx.tmp, "legacy-v20.db")
    build_fixture_db(p)                      # research-agent tables ...
    raw = sqlite3.connect(p)                 # ... + a v2.0 posts table with a row
    raw.execute(_V20_POSTS_DDL)
    raw.execute("INSERT INTO posts(media_id, niche, hook_family, script_sha256, "
                "is_trial) VALUES ('17900000000009001', 'home', 'bold-claim', ?, 1)",
                ("ab" * 32,))
    raw.commit()
    raw.close()
    con = idb.connect(p)
    try:
        acts = set(con.migration_actions)
        row = con.execute("SELECT * FROM posts WHERE media_id='17900000000009001'"
                          ).fetchone()
        C.check("migration: a v2.0 posts table gains variant_id, hook_archetype, "
                "visual_type, vibe, tone, primary_keyword; old rows keep their values",
                {f"posts +{c}" for c in CREATIVE_COLUMNS} <= acts and row is not None
                and row["hook_family"] == "bold-claim" and row["is_trial"] == 1 and
                all(row[c] is None for c in CREATIVE_COLUMNS),
                sorted(a for a in acts if a.startswith("posts")))
        C.check("migration: idempotent, ingest schema_version unchanged",
                idb.migrate(con) == [] and idb.schema_version(con) == idb.SCHEMA_VERSION)
    finally:
        con.close()


def _sc_build(C, ctx):
    """Runs (manifest + script.json) and own reels + snapshots from
    tests/fixtures/learn/scenario.json -> scenario dict (holds the open DB)."""
    from vsp.ingest import db as idb
    u = _util()
    with open(os.path.join(LEARN_FIXTURES, "scenario.json"), encoding="utf-8") as f:
        scn = json.load(f)
    search = os.path.join(ctx.tmp, "search")
    os.environ["VSP_FEEDBACK_SEARCH"] = search
    runs = {}
    for m in scn["manifests"]:
        with open(os.path.join(LEARN_FIXTURES, m["script"]), encoding="utf-8") as f:
            script = json.load(f)
        script.update(m.get("patch") or {})
        raw = (json.dumps(script, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
        where, name = m["dir"].split("/", 1)
        d = os.path.join(ctx.outputs if where == "outputs" else search, name)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "script.json"), "wb") as f:
            f.write(raw)
        sha = hashlib.sha256(raw).hexdigest()
        summ = {k: script.get(k) for k in ("prompt", "niche", "hook_family", "hook_source",
                                           "presenter", "format", "duration_s")}
        summ.update(hook=next((h.get("dialogue") for h in script.get("hook_stack") or []
                               if isinstance(h, dict) and h.get("dialogue")), None),
                    seed=script.get("seed", 701), candidate_seed=9001, script_sha256=sha)
        hv = hook_variants(script)
        if hv:                                   # the integrator's §1.6 fields
            prim = dict(hv)[primary_variant(script)]
            summ.update(vibe=_dig(script, "direction", "vibe"),
                        tone=_dig(script, "direction", "tone", "voice"),
                        hook_archetype=prim.get("archetype"),
                        visual_type=prim.get("visual_type"),
                        variant_ids=[v for v, _ in hv],
                        primary_keyword=_dig(script, "discovery", "primary_keyword"))
        man = {"schema_version": 1, "created": m["created"],
               "seeds": {"root": 701, "candidates": [701]}, "args": {"seed": 701},
               "outputs": {"script.json": sha}, "script_summary": summ}
        with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(man, f, indent=1)
        runs[name] = {"dir": d, "manifest": os.path.join(d, "manifest.json"),
                      "sha": sha, "script": script}
    now = scn["now"]
    con = idb.connect(ctx.db, create=True)
    reels = {}
    for r in scn["reels"]:
        cap = re.sub(r"\{sha8:([\w-]+)\}", lambda mm: runs[mm.group(1)]["sha"][:8],
                     r["caption"])
        con.execute("INSERT INTO reels(platform, media_id, url, caption, posted_at, "
                    "is_own, is_trial, media_type, media_product_type, source, "
                    "analyzed_at) VALUES ('instagram', ?, ?, ?, ?, 1, 0, 'VIDEO', "
                    "'REELS', 'ig_own', ?)",
                    (r["media_id"], f"https://www.instagram.com/reel/FIXTUREv21{r['key']}/",
                     cap, r["posted_at"], now))
        s = r.get("snapshot")
        if s:
            at = u.sql_ts(u.parse_ts(r["posted_at"]) + timedelta(hours=s["age_h"]))
            con.execute("INSERT INTO reel_metrics(media_id, captured_at, age_h, views, "
                        "reach, shares, saves, avg_watch_ms, skip_rate, source) VALUES "
                        "(?,?,?,?,?,?,?,?,?,?)",
                        (r["media_id"], at, s["age_h"], s["views"], s["reach"],
                         s["shares"], s["saves"], s["avg_watch_ms"], s["skip_rate"],
                         "fixture"))
        reels[r["key"]] = dict(r, caption=cap)
    con.commit()
    C.check("scenario: 6 runs (3 identical-caption frother runs, 1 under "
            "VSP_FEEDBACK_SEARCH, 1 legacy v2.0 script) + 13 own reels",
            len(runs) == 6 and len(reels) == 13 and
            len({x["sha"] for x in runs.values()}) == 6)
    return {"now": now, "runs": runs, "reels": reels, "con": con}


def _sc_link(C, ctx, sc):
    con, runs, reels, now = sc["con"], sc["runs"], sc["reels"], sc["now"]
    rep = link_auto(con, roots=search_roots(), now=now)
    by = {x["media_id"]: x for x in rep["linked"]}
    bad = []
    for key, r in reels.items():
        e, x = r["expect"], by.get(r["media_id"])
        if e["by"] is None:
            if x is not None:
                bad.append(f"{key} linked")
            continue
        ok = (x is not None and x["by"] == e["by"] and x["variant_id"] == e["variant"]
              and x["manifest"] == runs[e["run"]]["manifest"]
              and all(x.get(k) == e[k] for k in ("exact", "jaccard", "ties",
                                                   "variant_from") if k in e))
        if not ok:
            bad.append(f"{key}: {x and {k: x.get(k) for k in ('by', 'variant_id', 'exact', 'jaccard', 'ties', 'variant_from')}}")  # noqa: E501
    C.check("link --auto: every scenario reel links (or not) as expected — tags with "
            "and without a letter, fingerprints to variants A/B/C", not bad, "; ".join(bad))
    fpr = rep["fingerprint"]
    C.check("link --auto: report — 13 unlinked, 5 tagged, 8 fingerprint tries, 6 "
            "linked, 2 without a match; v2.0 keys kept",
            rep["candidates"] == 13 and rep["untagged"] == 8 and fpr["tried"] == 8 and
            fpr["linked"] == 6 and fpr["not_linked"] == {"no fingerprint match": 2} and
            not rep["unmatched"] and not rep["ambiguous"] and len(rep["linked"]) == 11,
            json.dumps(fpr))
    mid = {k: r["media_id"] for k, r in reels.items()}
    C.check("fingerprint window: a run created after the post is never used (FE -> "
            "the older run; FB not -> the 09-27 re-run); 59 days links, 62 days doesn't",
            by[mid["FE"]]["manifest"] == runs["electric-milk-frother-old"]["manifest"]
            and by[mid["FB"]]["manifest"] == runs["electric-milk-frother"]["manifest"]
            and mid["G1"] in by and mid["G2"] not in by)
    C.check("fingerprint Jaccard: 0.8 links (LA), 0.73 doesn't (LX); the best of "
            "equal matches is the newest run (FB ties 1 older identical run)",
            by[mid["LA"]]["jaccard"] == 0.8 and not by[mid["LA"]]["exact"] and
            mid["LX"] not in by and by[mid["FB"]]["ties"] == 1)
    rows = {r["media_id"]: dict(r) for r in con.execute("SELECT * FROM posts")}
    want = {"FB": ("B", "proof-first", "result-reveal", "clean-aesthetic", "confident",
                   "milk frother"),
            "LA": ("A", "bold-claim", "result-reveal", "cozy-calm", "warm", "sunset lamp"),
            "PC": ("C", "pov", "pov-hands", "clean-aesthetic", "calm", "silk pillowcase"),
            "G1": ("A", None, None, None, None, None),
            "G3": (None, None, None, None, None, None)}
    got = {k: tuple(rows[mid[k]][c] for c in CREATIVE_COLUMNS) for k in want}
    C.check("link: posts gets variant_id + that variant's archetype / visual_type, "
            "direction vibe + tone.voice, discovery keyword; legacy scripts -> NULL; "
            "hook_family unchanged",
            got == want and rows[mid["FB"]]["hook_family"] == "curiosity-gap" and
            rows[mid["PC"]]["niche"] == "beauty", json.dumps(got)[:200])
    for k in ("FB", "FC", "LA", "LB"):          # mark the trials (no read-side flag)
        run = next(n for n, x in runs.items() if x["manifest"] == by[mid[k]]["manifest"])
        link(con, mid[k], runs[run]["manifest"], trial=True, now=now)
    after = {r["media_id"]: (r["variant_id"], r["is_trial"]) for r in con.execute(
        "SELECT media_id, variant_id, is_trial FROM posts")}
    C.check("link --trial re-link keeps each variant (tag / fingerprint re-read)",
            [after[mid[k]] for k in ("FB", "FC", "LA", "LB")] ==
            [("B", 1), ("C", 1), ("A", 1), ("B", 1)])
    try:
        link(con, mid["LX"], runs["sunset-lamp"]["manifest"], variant="BB")
        refused = False
    except LinkError:
        refused = True
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = main(["--json", "link", "--media-id", mid["LX"], "--manifest",
                     runs["sunset-lamp"]["manifest"], "--variant", "c"])
    try:
        out = json.loads(buf.getvalue())
    except ValueError:
        out = {}
    C.check("cli: link --variant C (explicit) stores C's archetype + visual type; a "
            "bad --variant is refused",
            refused and code == 0 and out.get("variant_id") == "C" and
            out.get("hook_archetype") == "question" and
            out.get("visual_type") == "text-first" and
            out.get("variant_from") == "explicit", str(out)[:160])
    con.execute("DELETE FROM posts WHERE media_id=?", (mid["LX"],))   # back to the
    con.execute("UPDATE reels SET script_slug=NULL WHERE media_id=?", (mid["LX"],))
    con.commit()                                                     # scenario
    C.check("unit: script_creative falls back to the manifest's §1.6 fields for the "
            "primary only", script_creative(None, "A", {"creative": {
                "vibe": "raw-ugc", "tone": "deadpan", "hook_archetype": "question",
                "visual_type": "text-first", "primary_keyword": "desk lamp"}}) == {
                "hook_archetype": "question", "visual_type": "text-first",
                "vibe": "raw-ugc", "tone": "deadpan", "primary_keyword": "desk lamp"}
            and script_creative(None, "B", {"creative": {"hook_archetype": "question",
                                                         "vibe": "raw-ugc"}})
            == {"hook_archetype": None, "visual_type": None, "vibe": "raw-ugc",
                "tone": None, "primary_keyword": None})


def _sc_learn(C, ctx, sc):
    from vsp.ingest import db as idb
    from vsp.ingest.settings import MAKER_NICHES
    con, now = sc["con"], sc["now"]
    rep = learn(con, now=now)
    with open(config.priors_path(), "rb") as f:
        raw = f.read()
    pri = json.loads(raw.decode("utf-8"))
    C.check("learn: priors schema_version 2 = the v1 keys + sections {archetype, "
            "visual_type, vibe, tone} × {by_niche, global}; validates",
            pri["schema_version"] == 2 and rep["schema_version"] == 2 and
            list(pri) == ["schema_version", "updated_at", "metric", "families", "global",
                          "sections"] and list(pri["sections"]) == list(SECTIONS) and
            not validate_priors(pri), "; ".join(validate_priors(pri))[:160])
    lab = labels(con)
    wins = sorted(k for k, r in sc["reels"].items() for p in lab["posts"]
                  if p["media_id"] == r["media_id"] and p["success"])
    exp = {s: {} for s in SECTIONS}                 # independent re-aggregation
    for p in lab["posts"]:
        for s, col in SECTION_COLUMNS.items():
            if p["linked"] and p["niche"] in MAKER_NICHES and p[col]:
                for t in (exp[s].setdefault(("n", p["niche"]), {}),
                          exp[s].setdefault(("g",), {})):
                    e = t.setdefault(p[col], [1.0, 1.0, 0])
                    e[0 if p["success"] else 1] += 1.0
                    e[2] += 1
    got = {s: {("g",): {k: [e["alpha"], e["beta"], e["n"]]
                        for k, e in b["global"].items()},
               **{("n", n): {k: [e["alpha"], e["beta"], e["n"]] for k, e in t.items()}
                  for n, t in b["by_niche"].items()}} for s, b in pri["sections"].items()}
    C.check("learn: each section is Beta(1 + wins, 1 + losses) per (niche, key) + "
            "global over posts whose key is known (the 2 legacy posts count nowhere)",
            wins == ["FB", "LB", "PA", "PB", "PC"] and got == exp and
            pri["sections"]["vibe"]["global"]["clean-aesthetic"] ==
            {"alpha": 5.0, "beta": 3.0, "n": 6} and
            sum(e["n"] for e in pri["sections"]["archetype"]["global"].values()) == 8,
            f"wins {wins}")
    fam = pri["families"]
    C.check("learn: v1 families/global keep their meaning (legacy posts included)",
            fam["home"]["curiosity-gap"]["n"] == 3 and
            fam["home"]["negative-command"]["n"] == 2 and
            fam["beauty"]["transformation"] == {"alpha": 4.0, "beta": 1.0, "n": 3} and
            sum(e["n"] for e in pri["global"].values()) == 10, json.dumps(fam)[:160])
    from vsp import priors as P
    lp = P.load_priors(config.priors_path())
    C.check("learn: round-trip through vsp.priors — load_priors v2, mean_for niche "
            "table then global, None below n = 3, posterior_for('family') = v1",
            lp is not None and lp["schema_version"] == 2 and tuple(P.SECTIONS) == SECTIONS
            and P.mean_for(lp, "vibe", "home", "clean-aesthetic") == 2 / 5
            and P.mean_for(lp, "vibe", "beauty", "clean-aesthetic") == 4 / 5
            and P.mean_for(lp, "vibe", "fitness", "clean-aesthetic") == 5 / 8
            and P.mean_for(lp, "tone", "home", "warm") is None
            and P.mean_for(lp, "tone", "beauty", "calm") == 4 / 5
            and P.mean_for(lp, "archetype", "home", "transformation", min_n=1) == 2 / 3
            and P.posterior_for(lp, "visual_type", "home", "result-reveal") ==
            (2.0, 2.0, 2) and P.posterior_for(lp, "family", "home", "curiosity-gap")
            == (2.0, 3.0, 3) and P.posterior_for(lp, "archetype", "home", "nope") is None)
    C.check("learn: CLI summary carries the schema version + section counts",
            rep["sections"]["vibe"] == {"clean-aesthetic": 6, "cozy-calm": 2} and
            rep["sections"]["tone"] == {"calm": 3, "confident": 3, "warm": 2})
    empty = idb.connect(os.path.join(ctx.tmp, "empty-v21.db"), create=True)
    try:
        kept = learn(empty, now=now)
    finally:
        empty.close()
    with open(config.priors_path(), "rb") as f:
        C.check("learn: a DB without labelled posts keeps the last good v2 priors",
                kept.get("kept") and f.read() == raw)
    bad = json.loads(raw.decode("utf-8"))
    bad["sections"]["tone"]["global"]["calm"]["n"] = 7
    del bad["sections"]["vibe"]
    errs = validate_priors(bad)
    C.check("validate_priors v2: missing section and alpha + beta - 2 != n flagged",
            any("exactly" in e for e in errs) and any("calm" in e and "!= n" in e
                                                      for e in errs), "; ".join(errs)[:160])


# --------------------------------------------------------------------- CLI
def _parser():
    ap = argparse.ArgumentParser(
        prog="python3 -m vsp.feedback",
        description="Closed performance-feedback loop over YOUR posted reels.",
        epilog="caption tag: #vsp-<first 8 hex chars of script_sha256> "
               "(manifest.json -> script_summary.script_sha256). Hermes cron: hourly "
               "`python3 -m vsp.ingest own && python3 -m vsp.feedback pull`; daily "
               "`python3 -m vsp.feedback learn && python3 -m vsp.feedback report`. "
               "Docs: docs/ws-data-notes.md")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--db", help="research DB path (sets VSP_VIRAL_DB)")
    sub = ap.add_subparsers(dest="cmd", metavar="command")
    p = sub.add_parser("link", help="link posted reels to the runs that made them")
    p.add_argument("--media-id")
    p.add_argument("--manifest", help="outputs/<slug>/manifest.json (or its folder)")
    p.add_argument("--trial", action="store_true", help="it was posted as a Trial Reel")
    p.add_argument("--variant", metavar="ID",
                   help="the opening that was posted (A = primary, B, C … = "
                        "hook_variants ids); default: the caption's #vsp-<sha8><letter> "
                        "tag or fingerprint, else the primary")
    p.add_argument("--auto", action="store_true",
                   help="match own-media captions by #vsp-<sha8>[<letter>] tag, else "
                        "by caption fingerprint (first line vs script/variant captions)")
    p.add_argument("--search", action="append", default=[],
                   help="extra folder to search for manifest.json (repeatable)")
    p = sub.add_parser("pull", help="insight snapshots at ~24h/48h/7d/28d")
    p.add_argument("--no-link", action="store_true", help="skip `link --auto` first")
    p.add_argument("--search", action="append", default=[])
    sub.add_parser("learn", help="labels -> learned/priors.json")
    sub.add_parser("report", help="learned/PERFORMANCE.md")
    sub.add_parser("status")
    sub.add_parser("selfcheck")
    return ap


def _out(obj, as_json, text):
    print(json.dumps(obj, indent=1, default=str, ensure_ascii=False) if as_json else text)


def main(argv=None):
    if config.REPO not in sys.path:
        sys.path.insert(0, config.REPO)
    ap = _parser()
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help()
        return 2
    if a.db:
        os.environ["VSP_VIRAL_DB"] = os.path.abspath(a.db)
    if a.cmd == "selfcheck":
        ok, lines = selfcheck()
        _out({"ok": ok, "lines": lines}, a.json,
             "\n".join(lines) + "\nvsp.feedback selfcheck: " + ("OK" if ok else "FAILED"))
        return 0 if ok else 1
    from vsp.ingest import db as idb
    try:
        con = idb.connect()
    except (idb.DBMissing, idb.MigrationError) as e:
        print(str(e), file=sys.stderr)
        return 2
    try:
        if a.cmd == "link":
            if a.auto:
                rep = link_auto(con, roots=search_roots(a.search))
                fpr = rep["fingerprint"]
                _out(rep, a.json, f"linked {len(rep['linked'])} of {rep['candidates']} "
                     f"unlinked own reels; untagged {rep['untagged']}, no manifest for "
                     f"{[u['tag'] for u in rep['unmatched']]}, ambiguous "
                     f"{len(rep['ambiguous'])}; searched {rep['roots']}\n"
                     f"caption fingerprint: linked {fpr['linked']} of {fpr['tried']} "
                     f"untagged; not linked {fpr['not_linked']}; variants "
                     + (", ".join(f"{x['media_id']}={x['variant_id']}"
                                  for x in rep["linked"] if x.get("variant_id"))
                        or "none"))
                return 0
            if not (a.media_id and a.manifest):
                print("link needs --media-id ID --manifest PATH (or --auto)",
                      file=sys.stderr)
                return 2
            try:
                row = link(con, a.media_id, a.manifest, trial=a.trial, variant=a.variant)
            except LinkError as e:
                print(f"link refused: {e}", file=sys.stderr)
                return 2
            _out(row, a.json, f"linked {row['media_id']} -> {row['manifest_path']} "
                 f"({row['niche']} / {row['hook_family']}, tag vsp-"
                 f"{row['script_sha256'][:8]}{', trial' if row['is_trial'] else ''}"
                 + (f", variant {row['variant_id']} ({row.get('variant_from')})"
                    if row.get("variant_id") else "") + ")")
            return 0
        if a.cmd == "pull":
            from vsp.ingest import jobs
            from vsp.ingest import settings as S
            from vsp.ingest.graph import NotConfigured
            try:
                cfg = S.load(required=False)
            except S.ConfigError:
                cfg = dict(S.DEFAULTS)
            try:
                client = jobs.make_client(con, cfg,
                                          log=lambda m: print(m, file=sys.stderr))
            except NotConfigured as e:
                print(str(e), file=sys.stderr)
                return 2
            rep = pull(con, client, link_first=not a.no_link,
                       roots=search_roots(a.search),
                       log=None if a.json else (lambda m: print(m, file=sys.stderr)))
            _out(rep, a.json, f"{rep['snapshots']} snapshots ({rep['due']} due, "
                 f"{rep['api_calls']} API calls); skipped {rep['skipped']}; vanished "
                 f"{rep['vanished']}; errors {rep['errors']}"
                 + (f"; linked {len(rep['link']['linked'])}" if rep.get("link") else "")
                 + (f"\nSTOPPED: {rep['stopped']}" if rep["stopped"] else ""))
            st = rep["stopped"] or ""
            return 3 if st.startswith("rate_limited") else (2 if st else 0)
        if a.cmd == "learn":
            rep = learn(con)
            if rep.get("kept"):
                _out(rep, a.json, f"kept {rep['priors']}: no labelled posts in this DB "
                     f"({rep['pending']}) — run `python3 -m vsp.feedback pull` first")
                return 0
            _out(rep, a.json, f"wrote {rep['priors']}: {rep['labelled']} labelled posts "
                 f"({rep['linked']} linked), median composite {rep['median_composite']}, "
                 f"families {rep['families']}; schema v{rep['schema_version']}"
                 + (f", sections {rep['sections']}" if rep["sections"] else
                    " (no post carries a v2.1 archetype / visual type / vibe / tone yet)"))
            return 0
        if a.cmd == "report":
            p, text = report(con)
            _out({"path": p}, a.json, f"wrote {p}\n\n{text}")
            return 0
        if a.cmd == "status":
            rep = status(con)
            _out(rep, a.json, json.dumps(rep, indent=1, default=str))
            return 0
    finally:
        con.close()
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
