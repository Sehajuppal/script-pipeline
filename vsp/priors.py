"""Learned performance priors — the maker's reader for learned/priors.json.

    load_priors(path=None) -> dict | None
        The normalised priors (schema v1, learned/README.md), or None when
        the file is missing, unreadable, not JSON or not schema v1. Never
        raises. Cached per (path, mtime, size): the maker calls this once per
        hook pick, so an unchanged file is parsed once per process.
    posterior(priors, niche, family) -> (alpha, beta, n) | None
        The niche's own table when the niche is present, else `global`
        (the README contract: "falls back to global when the niche is
        absent"). None when no entry exists.
    thompson(priors, niche, families, rng, min_n=MIN_N) -> {family: {...}}
        One Beta(alpha, beta) draw per family with n >= min_n, drawn from
        `rng` in sorted family order (deterministic for the same rng state
        and the same file). Families below min_n are absent: the caller
        scores them NEUTRAL.

Normalised shape: {"schema_version": 1, "metric", "updated_at",
"families": {niche: {family: {"alpha", "beta", "n"}}}, "global": {family:
{...}}, "source": {"path", "sha256"}}. Entries with a non-positive or
non-finite alpha/beta, or a negative/non-integral n, are dropped (the rest
of the file still loads).

Written by `python3 -m vsp.feedback learn` (not here: this module only
reads). VSP_NO_PRIORS=1 disables loading (A/B runs). Stdlib only; Python
>= 3.9.
"""
import hashlib
import json
import math
import os

from vsp import config

SCHEMA_VERSION = 1
MIN_N = 3            # a family needs >= 3 observations before it can steer
NEUTRAL = 0.5        # the score of a family without enough evidence

_CACHE = {}          # abs path -> ((mtime_ns, size, ino), priors | None)


def _num(v):
    return (isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(v))


def _entry(e):
    """{alpha, beta, n} -> normalised copy, or None when unusable."""
    if not isinstance(e, dict):
        return None
    a, b, n = e.get("alpha"), e.get("beta"), e.get("n", 0)
    if not (_num(a) and _num(b) and a > 0 and b > 0):
        return None
    if not _num(n) or n < 0 or float(n) != int(n):
        return None
    return {"alpha": float(a), "beta": float(b), "n": int(n)}


def _table(t):
    out = {}
    if not isinstance(t, dict):
        return out
    for fam, e in t.items():
        ne = _entry(e)
        if isinstance(fam, str) and fam and ne is not None:
            out[fam] = ne
    return out


def normalise(raw):
    """Parsed JSON -> normalised priors dict, or None if not schema v1."""
    if not isinstance(raw, dict) or raw.get("schema_version") != SCHEMA_VERSION:
        return None
    fams = raw.get("families", {})
    glob = raw.get("global", {})
    if not isinstance(fams, dict) or not isinstance(glob, dict):
        return None
    return {"schema_version": SCHEMA_VERSION,
            "metric": raw.get("metric") if isinstance(raw.get("metric"), str) else None,
            "updated_at": raw.get("updated_at")
            if isinstance(raw.get("updated_at"), str) else None,
            "families": {n: _table(t) for n, t in fams.items()
                         if isinstance(n, str) and isinstance(t, dict)},
            "global": _table(glob)}


def disabled():
    return os.environ.get("VSP_NO_PRIORS") == "1"


def load_priors(path=None):
    """-> normalised priors or None. Never raises."""
    try:
        if path is None and disabled():
            return None
        p = os.path.abspath(path or config.priors_path())
        try:
            st = os.stat(p)
        except OSError:
            _CACHE.pop(p, None)
            return None
        key = (getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)), st.st_size,
               st.st_ino)
        hit = _CACHE.get(p)
        if hit is not None and hit[0] == key:
            return hit[1]
        try:
            with open(p, "rb") as f:
                raw = f.read()
            pri = normalise(json.loads(raw.decode("utf-8")))
        except (OSError, UnicodeDecodeError, ValueError, RecursionError):
            pri = None
        if pri is not None:
            pri["source"] = {"path": p,
                             "sha256": hashlib.sha256(raw).hexdigest()}
        _CACHE[p] = (key, pri)
        return pri
    except Exception:  # noqa: BLE001 — the maker must never die on priors
        return None


def posterior(priors, niche, family):
    """-> (alpha, beta, n) | None. The niche's table if the niche is present
    in priors["families"], else priors["global"]."""
    if not isinstance(priors, dict):
        return None
    fams = priors.get("families") or {}
    tbl = fams.get(niche) if isinstance(fams, dict) else None
    if not isinstance(tbl, dict):
        tbl = priors.get("global") or {}
    e = _entry(tbl.get(family)) if isinstance(tbl, dict) else None
    if e is None:
        return None
    return e["alpha"], e["beta"], e["n"]


def thompson(priors, niche, families, rng, min_n=MIN_N):
    """{family: {"sample", "alpha", "beta", "n"}} — one rng.betavariate draw
    per family (sorted) whose posterior has n >= min_n. No priors or no
    qualifying family -> {} and the rng is not touched."""
    out = {}
    if not priors:
        return out
    for fam in sorted({f for f in families if isinstance(f, str)}):
        post = posterior(priors, niche, fam)
        if post is None or post[2] < min_n:
            continue
        a, b, n = post
        out[fam] = {"sample": rng.betavariate(a, b), "alpha": a, "beta": b,
                    "n": n}
    return out


def info(path=None):
    """{path, exists, sha256, valid} for the manifest (never raises)."""
    p = os.path.abspath(path or config.priors_path())
    out = {"path": p, "exists": os.path.isfile(p), "sha256": None,
           "valid": False, "disabled": path is None and disabled()}
    if out["exists"]:
        try:
            with open(p, "rb") as f:
                out["sha256"] = hashlib.sha256(f.read()).hexdigest()
        except OSError:
            pass
        out["valid"] = load_priors(p) is not None
    return out
