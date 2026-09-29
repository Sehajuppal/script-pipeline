"""golden-refresh — trending products -> evals/capability.jsonl.

The capability suite is the hill-climbing set (labs-techniques §6.1): new,
trending products the pipeline has never been tuned on. `measure` scores it
next to golden and holdout; `diagnose` weighs it lower (0.8).

Sources: product noun phrases in top reels' hooks and captions — the research
pack's top_reels / fresh_hook_lines (vsp.research.load_pack) and the research
DB's reels (hook_text + caption/notes, FIXTURE reels excluded) — weighted by
mentions x log-likes. A phrase becomes a prompt only if the maker routes it
as a product, it names 2+ words, and it duplicates nothing already in
golden, holdout or capability (content-stem subset test either way).

evals/golden.jsonl and evals/holdout.jsonl are NEVER written — they are read
only to de-duplicate.
"""
import collections
import json
import math
import os
import re

from vsp.improve import common as C

HEADER = ("// capability suite (hill-climbing): trending / unseen product prompts. "
          "Appended by `python3 -m vsp.improve golden-refresh`; never tuned on; "
          "golden.jsonl and holdout.jsonl are never edited by automation.")
MOD_RE = re.compile(r"^(?:[A-Za-z][A-Za-z0-9'-]*|\d+-in-\d+)$")
_PLACES = frozenset("""bedroom bathroom kitchen closet garage garden yard patio
balcony apartment dorm gym camp beach office desk room house home car trunk
setup studio""".split())
_SKIP_MODS = frozenset("""the a an this that my your our their his her its and or
of for with to in on at by from is are was were be best new top viral trending
cheap only just very really more most every all any some one two""".split())


def capability_path(repo=None):
    return C.suite_path("capability", repo)


def _rows(path):
    try:
        return C.load_jsonl(path)
    except (OSError, ValueError):
        return []


def content_key(prompt):
    from vsp import rubric
    return frozenset(rubric.prompt_anchors(prompt))


def existing(repo=None):
    """(rows by suite, content keys of every PRODUCT prompt) over golden +
    holdout + capability."""
    by = {s: _rows(C.suite_path(s, repo)) for s in C.SUITES}
    keys = [content_key(r["prompt"]) for rows in by.values() for r in rows
            if r.get("prompt") and r.get("concept", "product") == "product"]
    return by, keys


def is_dup(key, keys):
    """Same content stems, or one product's stems contain the other's (both
    >= 2 stems: 'ring light' duplicates 'a $19 ring light')."""
    if not key:
        return True
    return any(key == k or (min(len(key), len(k)) >= 2 and (key <= k or k <= key))
               for k in keys)


def source_texts(limit=500):
    """[(text, likes, source)] from the research pack and the research DB."""
    out, notes = [], []
    try:
        from vsp import research
        pack, meta = research.load_pack()
    except Exception as e:  # noqa: BLE001
        pack, meta = None, {"errors": [repr(e)]}
    if pack:
        tops = [r for r in pack.get("top_reels") or [] if isinstance(r, dict)]
        for r in tops:
            likes = r.get("likes") or r.get("like_count") or 0
            for k in ("hook", "hook_text", "caption", "title"):
                if isinstance(r.get(k), str) and r[k].strip():
                    out.append((r[k], likes, f"pack:top_reels.{k}"))
        fresh = [r for r in pack.get("fresh_hook_lines") or [] if isinstance(r, dict)]
        for r in fresh:       # annotator descriptions ("(visual open, ...)") skipped
            if research.is_spoken_hook_line(r.get("hook")):
                out.append((r["hook"], r.get("likes") or 0, "pack:fresh_hook_lines"))
        notes.append(f"research pack: {len(tops)} top reels, {len(fresh)} fresh lines")
    else:
        notes.append("research pack: unavailable")
    try:
        from vsp import config
        con = config.connect_ro()
    except Exception:  # noqa: BLE001
        con = None
    if con is None:
        notes.append("research DB: absent")
    else:
        try:
            cols = {r[1] for r in con.execute("PRAGMA table_info(reels)")}
            cap = "caption" if "caption" in cols else "notes" if "notes" in cols else None
            q = (f"SELECT hook_text, {cap or 'NULL'}, like_count FROM reels WHERE "
                 f"(url IS NULL OR url NOT LIKE '%FIXTURE%') ORDER BY like_count DESC LIMIT ?")
            rows = con.execute(q, (limit,)).fetchall()
            for h, c, likes in rows:
                for t, k in ((h, "hook_text"), (c, cap)):
                    if isinstance(t, str) and t.strip():
                        out.append((t, likes or 0, f"db:reels.{k}"))
            notes.append(f"research DB: {len(rows)} reels (FIXTURE reels excluded)")
        except Exception as e:  # noqa: BLE001
            notes.append(f"research DB: query failed ({type(e).__name__})")
        finally:
            con.close()
    return out, notes


def extract_products(text, nouns):
    """Product noun phrases (2-4 words, head = a product noun) in text."""
    words = re.findall(r"\$\d+(?:\.\d+)?|[A-Za-z0-9][A-Za-z0-9'-]*", text or "")

    def noun(w):
        low = w.lower()
        head = low if low in nouns else low[:-1] if low.endswith("s") and low[:-1] in nouns \
            else low[:-2] if low.endswith("es") and low[:-2] in nouns else None
        return head if head and head not in _PLACES else None

    out = []
    for i, w in enumerate(words):
        if not noun(w):
            continue
        if i + 1 < len(words) and noun(words[i + 1]):
            continue          # the maximal noun phrase ends at the last noun
        j = i
        while j > 0 and i - j < 3 and MOD_RE.match(words[j - 1]) and \
                words[j - 1].lower() not in _SKIP_MODS:
            j -= 1
        phrase = [x.lower() if not x.isupper() else x for x in words[j:i + 1]]
        if len(phrase) < 2:
            continue
        price = words[j - 1] if j > 0 and words[j - 1].startswith("$") else None
        out.append(((f"a {price} " if price else "") + " ".join(phrase)).strip())
    return out


def _routes_as_product(prompt):
    try:
        from vsp.improve import evolve as E
        vsm = E.load_maker()
        return vsm.parse_prompt(prompt).get("concept", "product") == "product"
    except Exception:  # noqa: BLE001 — maker unavailable: trust the extractor
        return True


def golden_refresh(max_new=10, dry_run=False, log=None, texts=None, repo=None):
    say = log or (lambda m: None)
    from vsp.improve import evolve as E
    by, keys = existing(repo)
    try:
        vsm = E.load_maker()
        nouns = E.product_nouns(vsm, by.get("golden") or [])
    except Exception:  # noqa: BLE001
        nouns = set()
    if texts is None:
        texts, notes = source_texts()
    else:
        notes = [f"{len(texts)} supplied texts"]
    score, mentions, src = collections.Counter(), collections.Counter(), {}
    for text, likes, source in texts:
        for ph in extract_products(text, nouns):
            try:
                w = 1.0 + math.log10(1.0 + max(0.0, float(likes or 0)))
            except (TypeError, ValueError):
                w = 1.0
            score[ph] += w
            mentions[ph] += 1
            src.setdefault(ph, source)
    added, skipped = [], collections.Counter()
    for ph, s in sorted(score.items(), key=lambda kv: (-kv[1], kv[0])):
        if len(added) >= max_new:
            break
        key = content_key(ph)
        if is_dup(key, keys):
            skipped["duplicate of golden/holdout/capability"] += 1
            continue
        if not _routes_as_product(ph):
            skipped["maker does not route it as a product"] += 1
            continue
        keys.append(key)
        added.append({"id": "cap-" + C.slug(ph, 40), "prompt": ph, "concept": "product",
                      "source": src[ph], "mentions": mentions[ph], "score": round(s, 2),
                      "added": C.today()})
    path = capability_path(repo)
    if added and not dry_run:
        old = []
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                old = [ln.rstrip("\n") for ln in f if ln.strip()]
        if not old or not old[0].startswith("//"):
            old = [HEADER] + old
        C.write_text(path, "\n".join(old + [json.dumps(r, ensure_ascii=False) for r in added])
                     + "\n")
    say(f"golden-refresh: {len(added)} new capability prompt(s)")
    return {"added": added, "skipped": dict(skipped), "notes": notes,
            "candidates": len(score), "path": C.rel(path), "dry_run": dry_run,
            "sizes": {s: len(v) for s, v in by.items()}}


def render(res):
    L = [f"golden-refresh: {len(res['added'])} new prompt(s) -> {res['path']}"
         f"{' (dry run)' if res['dry_run'] else ''} · {res['candidates']} candidate phrases · "
         + " · ".join(res["notes"]),
         f"  suites now: {res['sizes']} (golden/holdout are never edited)"]
    for r in res["added"]:
        L.append(f"  + {r['id']}: {r['prompt']!r} ({r['source']}, {r['mentions']} mention(s), "
                 f"score {r['score']})")
    if res["skipped"]:
        L.append(f"  skipped: {res['skipped']}")
    if not res["added"]:
        L.append("  nothing new: no trending product phrase outside the existing suites "
                 "(no top_reels in the pack and no research DB here?)")
    return "\n".join(L)
