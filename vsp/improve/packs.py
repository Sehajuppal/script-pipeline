"""Hook packs: the WS-INT loader contract, pack IO, and an A/B-only loader
emulation for makers that predate the loader.

Contract (the maker's loader, WS-INT): learned/hook_packs/*.json load in
sorted name order; a pack loads only with "status": "approved" and
"schema_version": 1 and a non-empty "id"; a template joins HOOKS[family]
only if the family already exists in viral_script_maker.HOOKS, it is a
one-line string of <= 120 chars, and every {slot} is a plain slot that some
built-in HOOKS template already uses (computed from HOOKS at runtime);
templates are whitespace-normalised and deduplicated. VSP_NO_HOOK_PACKS=1
disables loading. evolve emits only templates that satisfy this contract.

    hook_slots(hooks) -> frozenset          {slot} names used by HOOKS
    template_problem(t, known) -> str|None  why the loader would skip t
    validate_pack(pack, hooks) -> [str]     structural + per-template problems
    load_into(hooks, dirpath=None)          the loader contract, in place
    native_loader(maker_path) -> bool       does the maker load packs itself?
    inject_shim(maker_path)                 A/B copies only: emulate the loader
"""
import json
import os
import re

from vsp.improve import common as C

PACK_SCHEMA = 1
MAX_CHARS = 120
STATUSES = ("proposed", "approved", "rejected")
SLOT_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
PACK_NAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d+)\.json$")
NATIVE_MARKERS = ("load_hook_packs", "hook_packs_dir", "VSP_NO_HOOK_PACKS")
SHIM_MARK = "# --- vsp.improve A/B shim"
SHIM = '''
# --- vsp.improve A/B shim (temporary A/B copy ONLY, never committed) -------
# This maker predates the hook-pack loader, so the improvement engine emulates
# the WS-INT loader contract here to make the A/B measure the pack: approved
# packs only, known families, known {slots}, <= 120 chars, one line, deduped;
# VSP_NO_HOOK_PACKS=1 disables it.
if os.environ.get("VSP_NO_HOOK_PACKS") != "1":
    try:
        from vsp.improve import packs as _vsp_improve_packs
        _vsp_improve_packs.load_into(HOOKS)
    except Exception:
        pass
'''


def normalize(t):
    return " ".join(str(t).split())


def hook_slots(hooks):
    return frozenset(s for lines in hooks.values() for t in lines
                     if isinstance(t, str) for s in SLOT_RE.findall(t))


def template_problem(t, known):
    """Why the maker's loader would skip template t, or None (usable).
    Mirrors viral_script_maker.hook_template_problem (WS-INT)."""
    if not isinstance(t, str) or not t.strip():
        return "not a non-empty string"
    if "\n" in t or "\r" in t:
        return "contains a newline"
    if len(t) > MAX_CHARS:
        return f"{len(t)} chars > {MAX_CHARS}"
    unknown = sorted(set(SLOT_RE.findall(t)) - set(known))
    if unknown:
        return "unknown slot(s) " + ", ".join("{%s}" % s for s in unknown)
    rest = SLOT_RE.sub("", t)
    if "{" in rest or "}" in rest:
        return "stray brace or non-plain {field}"
    return None


def validate_pack(pack, hooks, known=None):
    """-> list of problems ([] = every template would load)."""
    known = hook_slots(hooks) if known is None else known
    probs = []
    if not isinstance(pack, dict):
        return ["pack is not a JSON object"]
    if pack.get("schema_version") != PACK_SCHEMA:
        probs.append(f"schema_version {pack.get('schema_version')!r} != {PACK_SCHEMA}")
    if not isinstance(pack.get("id"), str) or not pack.get("id", "").strip():
        probs.append("no id")
    if pack.get("status") not in STATUSES:
        probs.append(f"status {pack.get('status')!r} not in {STATUSES}")
    fams = pack.get("families")
    if not isinstance(fams, dict) or not fams:
        return probs + ["'families' is not a non-empty object"]
    for fam in sorted(fams):
        if fam not in hooks:
            probs.append(f"unknown family {fam!r}")
            continue
        if not isinstance(fams[fam], list):
            probs.append(f"{fam}: templates are not a list")
            continue
        for t in fams[fam]:
            why = template_problem(t, known)
            if why:
                probs.append(f"{fam}: {str(t)[:60]!r}: {why}")
            elif normalize(t) != t:
                probs.append(f"{fam}: {t[:60]!r}: not whitespace-normalised")
    return probs


def templates_of(pack):
    """[(family, template)] in pack order."""
    out = []
    for fam, lines in sorted((pack.get("families") or {}).items()):
        for t in lines if isinstance(lines, list) else []:
            if isinstance(t, str):
                out.append((fam, t))
    return out


def load_into(hooks, dirpath=None, known=None, status="approved"):
    """The loader contract, applied in place to `hooks`.
    -> (loaded ids, {family: [added]}, warnings). Never raises."""
    loaded, added, warns = [], {}, []
    try:
        dirpath = dirpath or C.hook_packs_dir()
        known = hook_slots(hooks) if known is None else known
        if not os.path.isdir(dirpath):
            return loaded, added, warns
        names = sorted(n for n in os.listdir(dirpath) if n.endswith(".json"))
    except Exception as e:  # noqa: BLE001
        return loaded, added, [f"directory: {e!r}"]
    seen = {normalize(t) for lines in hooks.values() for t in lines
            if isinstance(t, str)}
    for name in names:
        try:
            with open(os.path.join(dirpath, name), encoding="utf-8") as f:
                pack = json.load(f)
            if not isinstance(pack, dict) or pack.get("status") != status:
                continue
            if pack.get("schema_version") != PACK_SCHEMA:
                warns.append(f"{name}: schema_version mismatch")
                continue
            pid = pack.get("id")
            if not isinstance(pid, str) or not pid.strip() or pid in loaded:
                warns.append(f"{name}: missing or duplicate id")
                continue
            n_add = 0
            fams = pack.get("families") if isinstance(pack.get("families"), dict) else {}
            for fam in sorted(k for k in fams if isinstance(k, str)):
                if fam not in hooks or not isinstance(fams[fam], list):
                    warns.append(f"{name}: family {fam!r} skipped")
                    continue
                for t in fams[fam]:
                    why = template_problem(t, known)
                    if why:
                        warns.append(f"{name}: {fam}: {why}")
                        continue
                    norm = normalize(t)
                    if norm in seen:
                        continue
                    seen.add(norm)
                    hooks[fam].append(norm)
                    added.setdefault(fam, []).append(norm)
                    n_add += 1
            if n_add:
                loaded.append(pid)
        except Exception as e:  # noqa: BLE001 — a bad pack never breaks a run
            warns.append(f"{name}: {type(e).__name__}: {e}")
    return loaded, added, warns


def list_packs(dirpath=None, status=None):
    """[(path, pack)] sorted by file name; status filters when given."""
    d = dirpath or C.hook_packs_dir()
    out = []
    try:
        names = sorted(n for n in os.listdir(d) if n.endswith(".json"))
    except OSError:
        return out
    for n in names:
        p = os.path.join(d, n)
        pack = C.read_json(p)
        if isinstance(pack, dict) and (status is None or pack.get("status") == status):
            out.append((p, pack))
    return out


def next_pack_path(dirpath=None, date=None):
    """learned/hook_packs/<date>-<nn>.json and its id <date>-evolve-<nn>."""
    d = dirpath or C.hook_packs_dir()
    date = date or C.today()
    n = 0
    try:
        for name in os.listdir(d):
            m = PACK_NAME_RE.match(name)
            if m and m.group(1) == date:
                n = max(n, int(m.group(2)))
    except OSError:
        pass
    n += 1
    return os.path.join(d, f"{date}-{n:02d}.json"), f"{date}-evolve-{n:02d}"


def set_status(path, status, promote_evidence=None):
    pack = C.read_json(path)
    if not isinstance(pack, dict):
        raise C.ImproveError(f"not a pack: {path}")
    if status not in STATUSES:
        raise C.ImproveError(f"bad status {status!r}")
    pack["status"] = status
    prov = pack.setdefault("provenance", {})
    ev = prov.setdefault("evidence", {})
    if promote_evidence is not None:
        ev["promote"] = promote_evidence
    C.write_json(path, pack)
    return pack


def resolve_pack(ref):
    """A pack path, file name or id -> absolute path (or None)."""
    if not ref:
        return None
    if os.path.isfile(ref):
        return os.path.abspath(ref)
    d = C.hook_packs_dir()
    cand = os.path.join(d, ref if ref.endswith(".json") else ref + ".json")
    if os.path.isfile(cand):
        return cand
    for p, pack in list_packs(d):
        if pack.get("id") == ref:
            return p
    return None


# ----------------------------------------------------- A/B loader emulation
def native_loader(maker_path):
    try:
        with open(maker_path, encoding="utf-8") as f:
            src = f.read()
    except OSError:
        return False
    return any(m in src for m in NATIVE_MARKERS)


def inject_shim(maker_path):
    """Insert SHIM into a TEMPORARY copy of viral_script_maker.py (right
    after the HOOKS table, where the WS-INT loader lives). Refuses to touch
    the real repo's maker. -> True if injected."""
    real = os.path.realpath(os.path.join(C.REPO, "viral_script_maker.py"))
    if os.path.realpath(maker_path) == real:
        raise C.ImproveError("inject_shim refuses to edit the repo's own maker")
    with open(maker_path, encoding="utf-8") as f:
        src = f.read()
    if SHIM_MARK in src:
        return False
    anchor = "\nNICHE_KEYWORDS = {"
    if anchor in src:
        src = src.replace(anchor, "\n" + SHIM + anchor, 1)
    elif "\nif __name__ == \"__main__\":" in src:
        src = src.replace("\nif __name__ == \"__main__\":",
                          "\n" + SHIM + "\nif __name__ == \"__main__\":", 1)
    else:
        src += "\n" + SHIM
    with open(maker_path, "w", encoding="utf-8") as f:
        f.write(src)
    return True
