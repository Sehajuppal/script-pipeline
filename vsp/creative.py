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


def resync(script):
    """After a repair edits the hook stack (D142/D103 card compression, a
    staging note, a trim), variant A — the script's own opening — follows
    it: verbal and caption_line = the VERBAL HOOK dialogue, overlay = the
    VISUAL TRIGGER card (D154). Re-scores A when it changed. Mutates the
    script; returns the changed fields ([] = already in sync, or no
    variants)."""
    hv = script.get("hook_variants") if isinstance(script, dict) else None
    if not isinstance(hv, list) or not hv:
        return []
    try:
        from vsp import hooks as H
    except Exception:  # noqa: BLE001 — no hooks module, nothing to sync
        return []
    vt_item, vh_item = H._hook_items(script)
    if vt_item is None or vh_item is None:
        return []
    dv = [v for v in hv if isinstance(v, dict)]
    A = next((v for v in dv if v.get("is_primary")), dv[0] if dv else None)
    if A is None:
        return []
    verbal = " ".join(str(vh_item.get("dialogue") or "").split())
    overlay = str(vt_item.get("on_screen") or "")
    changed = []
    if A.get("verbal") != verbal:
        A["verbal"] = verbal
        changed.append("verbal")
    if A.get("caption_line") != verbal:
        A["caption_line"] = verbal
        changed.append("caption_line")
    if A.get("overlay") != overlay:
        A["overlay"] = overlay
        changed.append("overlay")
    if changed:
        try:
            others = [v.get("verbal") for v in dv if v is not A]
            s, feats, reasons = H.score_hook(verbal, overlay, A.get("visual_type"), script,
                                             archetype=A.get("archetype"), others=others)
            A["score"], A["features"], A["reasons"] = s, feats, reasons
        except Exception:  # noqa: BLE001 — the stored score stays; D154 is what gates
            pass
    return changed
