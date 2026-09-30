"""Deterministic sub-seeds.

derive_seed(root, *path) -> int, stable across processes and Python versions
(sha256, never the per-process-salted built-in hash()). Candidate 0 of a
best-of-N run keeps the raw seed so `--candidates 1` reproduces pre-2.0
seeds exactly (D149).
"""
import hashlib


def derive_seed(root, *path):
    key = "|".join([str(root)] + [str(p) for p in path])
    return int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:8],
                          "big") % (2 ** 31)


def candidate_seeds(seed, n):
    """Seeds for n candidates: [seed, derive(seed,'cand',1), ...]."""
    base = 0 if seed is None else seed
    return [seed if seed is not None else derive_seed(base, "cand", 0)] + \
        [derive_seed(base, "cand", i) for i in range(1, max(1, n))]
