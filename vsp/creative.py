"""Creative layer (pipeline v2.1): enrich a generated script with
  direction      vibe, tone, pacing, music, look, camera (vsp.direction.direct)
  hook_variants  3-5 alternate openings with distinct archetypes and frame-0
                 visuals, variant A = the script's own hook (vsp.hooks.variants)
  discovery      search keywords + per-platform packaging (vsp.discovery.build)

Called once at the end of viral_script_maker.generate(). Each module is
optional (absent = key not added, output byte-identical to v2.0). Additive
keys only; a module that raises never kills generation — the error is
recorded in script["creative_warnings"] and the self-test fails on any
warning, so bugs still surface loudly.
"""
import importlib
import importlib.util

STEPS = (
    ("direction", "vsp.direction", "direct"),
    ("hook_variants", "vsp.hooks", "variants"),
    ("discovery", "vsp.discovery", "build"),
)


def _load(modname, fn):
    try:
        if importlib.util.find_spec(modname) is None:
            return None
        return getattr(importlib.import_module(modname), fn, None)
    except Exception:  # noqa: BLE001 — an unimportable module is a warning
        return None


def enrich(script, ctx=None, seed=None, maker=None):
    """Mutates and returns `script`. ctx = the maker's parse context (after
    build_beats), seed = the generation seed, maker = the maker module object
    (so helpers never re-import viral_script_maker when it runs as __main__)."""
    warnings = []
    for key, modname, fn in STEPS:
        f = _load(modname, fn)
        if f is None:
            continue
        try:
            val = f(script, ctx=ctx, seed=seed, maker=maker)
        except Exception as e:  # noqa: BLE001
            warnings.append(f"{modname}.{fn}: {type(e).__name__}: {e}")
            continue
        if val is not None:
            script[key] = val
    if warnings:
        script["creative_warnings"] = warnings
    return script
