"""Script JSON contract (D152) — JSON Schema draft 2020-12 + a stdlib
subset validator.

    SCRIPT_SCHEMA            the schema (dict); committed as
                             schema/script.schema.json
    validate(obj) -> [str]   "$.beats[2].t: '3-5' does not match ..." errors

    python3 -m vsp.schema --write     regenerate schema/script.schema.json
    python3 -m vsp.schema --check     exit 1 if the committed file drifted
    python3 -m vsp.schema a.json ...  validate files

The schema describes what viral_script_maker.generate() emits (additional
properties are allowed — the maker may add keys, D145/D146 added
hook_source / series_plan; pipeline v2.1 adds the optional creative keys
direction / hook_variants / discovery / creative_warnings, $defs with enums
from vsp/creative_vocab.py). Validator subset: type (incl. type lists),
required, properties, additionalProperties, items, enum, const, pattern,
minItems, maxItems, minLength, maxLength, minimum, maximum, $ref (local
"#/$defs/.."). Schema-valid is not gate-valid: the gates still own the
semantics.
"""
import json
import os
import re
import sys

from vsp import creative_vocab as _CV

SCHEMA_ID = "urn:vsp:schema:script:1"
WINDOW_PATTERN = r"^\d+(?:\.\d+)?\s*[\u2013-]\s*\d+(?:\.\d+)?\s*s$"
FORMATS = ["demo", "talking-head", "pov-vlog", "transformation", "review"]
_TEXT = {"type": "string"}

_ITEM_PROPS = {
    "t": {"type": "string", "pattern": WINDOW_PATTERN,
          "description": "time window 'S–Es' (en dash or hyphen), seconds"},
    "type": {"type": "string", "minLength": 1,
             "description": "beat type, e.g. VISUAL TRIGGER, EDUCATION BEAT, PAYOFF"},
    "dialogue": _TEXT, "rehook": _TEXT, "on_screen": _TEXT, "delivery": _TEXT,
    "direction": _TEXT, "shot_direction": _TEXT, "note": _TEXT,
    "payoff_contract": _TEXT, "match_cut": _TEXT,
}

# ---- pipeline v2.1 creative keys (docs/CREATIVE-PLAN.md §1.1-1.3): all
# optional, enums from vsp/creative_vocab.py, additional properties allowed.
# The gates (D154-D156) own the cross-field semantics; the schema pins shape.
_STRS = {"type": "array", "items": _TEXT}
_NUM = {"type": "number"}
_BOOL = {"type": "boolean"}
_ENERGY = {"type": "integer", "minimum": 1, "maximum": 5}
_GRADE = {"enum": ["P", "S", "M", "A"]}
_TAG = {"type": "string", "pattern": r"^#\w+$"}


def _pair(lo=None, hi=None):
    item = {"type": "number"}
    if lo is not None:
        item["minimum"] = lo
    if hi is not None:
        item["maximum"] = hi
    return {"type": "array", "minItems": 2, "maxItems": 2, "items": item}


def _tags(n):
    return {"type": "array", "maxItems": n, "items": _TAG}


DIRECTION_SCHEMA = {
    "type": "object", "required": ["vibe"],
    "description": "§1.1 vsp.direction.direct() — vibe, tone, pacing, music "
                   "lane, look, camera, voice (gate D156)",
    "properties": {
        "schema_version": {"const": 1},
        "vibe": {"enum": list(_CV.VIBES)},
        "vibe_reason": _TEXT,
        "secondary_vibe": {"enum": list(_CV.VIBES) + [None]},
        "tone": {"type": "object", "properties": {
            "voice": {"enum": list(_CV.TONES)},
            "allowed": {"type": "array", "items": {"enum": list(_CV.TONES)}},
            "humor": {"enum": ["none", "light", "high"]}, "notes": _TEXT}},
        "energy": _ENERGY,
        "pacing": {"type": "object", "properties": {
            "target_wpm": _pair(140, 200), "avg_shot_s": _pair(0),
            "cuts_per_10s": _pair(0),
            "max_static_s": {"type": "number", "minimum": 0, "maximum": 3.5},
            "pattern_interrupt_s": {"type": "number", "minimum": 0}}},
        "energy_curve": {"type": "array", "items": {
            "type": "object", "required": ["type", "energy"],
            "properties": {"t": _TEXT, "type": _TEXT, "energy": _ENERGY}}},
        "music": {"type": "object", "properties": {
            "moods": _STRS, "bpm": _pair(30, 250), "genres": _STRS,
            "vo_ducking_db": {"type": "number", "maximum": 0}, "sfx": _STRS,
            "in_master": {"const": False,
                          "description": "music is added at upload (D156)"},
            "search_queries": _STRS,
            "licensing": {"type": "object", "properties": {
                p: {"type": "object", "properties": {"library": _TEXT,
                                                     "note": _TEXT}}
                for p in _CV.PLATFORMS}}}},
        "look": {"type": "object", "properties": {
            "lighting": _TEXT, "palette_names": _STRS,
            "palette_hex": {"type": "array", "items": {
                "type": "string", "pattern": "^#[0-9A-Fa-f]{6}$"}},
            "grade": _TEXT, "set": _TEXT, "wardrobe": _TEXT}},
        "camera": {"type": "object", "properties": {
            "style": _TEXT, "lens": _TEXT,
            "movement": {"type": "array", "items": {"enum": list(_CV.CAMERA_MOVES)}}}},
        "text_style": {"type": "object", "properties": {
            "case": _TEXT, "weight": _TEXT,
            "max_words_per_card": {"type": "integer", "minimum": 1, "maximum": 3},
            "placement": _TEXT}},
        "transitions": _STRS, "showmanship": _TEXT,
        "voice": {"type": "object", "properties": {
            "presenter": {"enum": ["ai", "human"]}, "spec": _TEXT}},
        "do": _STRS, "dont": _STRS,
        "evidence": {"type": "array", "items": {"type": "object", "properties": {
            "claim": _TEXT, "grade": _GRADE, "source": _TEXT}}},
    },
}

HOOK_VARIANT_SCHEMA = {
    "type": "object", "required": ["id", "archetype", "verbal", "visual_type"],
    "description": "§1.2 one alternate opening; variant A = the script's hook",
    "properties": {
        "id": {"type": "string", "pattern": "^[A-J]$"},
        "is_primary": _BOOL,
        "archetype": {"enum": list(_CV.HOOK_ARCHETYPES)},
        "family": _TEXT,
        "verbal": {"type": "string", "minLength": 1},
        "overlay": _TEXT,
        "visual_type": {"enum": list(_CV.VISUAL_TYPES)},
        "visual": _TEXT, "audio": _TEXT, "caption_line": _TEXT,
        "score": _NUM,
        "features": {"type": "object", "additionalProperties": _NUM},
        "reasons": _STRS,
    },
}

_TOGGLES = {p: {"type": "object", "properties": {k: _BOOL}} for p, k in (
    ("tiktok", "is_aigc"), ("instagram", "is_ai_generated"),
    ("youtube_shorts", "containsSyntheticMedia"))}

DISCOVERY_SCHEMA = {
    "type": "object", "required": ["primary_keyword"],
    "description": "§1.3 vsp.discovery.build() — keywords, placement, cover, "
                   "per-platform packaging (gates D155, rubric D161)",
    "properties": {
        "schema_version": {"const": 1},
        "primary_keyword": {"type": "string", "minLength": 1},
        "secondary_keywords": _STRS, "search_intents": _STRS,
        "placement": {"type": "object", "properties": {
            "spoken_by_s": _NUM, "on_screen_by_s": _NUM,
            "caption_first_60": _BOOL, "hashtag": _TAG, "cover_text": _BOOL}},
        "comment_word": _TEXT,
        "cover": {"type": "object", "properties": {
            "frame_s": {"type": "number", "minimum": 0}, "text": _TEXT,
            "safe_box": _TEXT, "why": _TEXT}},
        "platforms": {"type": "object", "properties": {
            "tiktok": {"type": "object", "properties": {
                "caption": _TEXT, "hashtags": _tags(5),
                "keywords_to_suggest": _STRS, "toggles": _TOGGLES["tiktok"],
                "notes": _STRS}},
            "instagram": {"type": "object", "properties": {
                "caption": _TEXT, "hashtags": _tags(5), "description_line": _TEXT,
                "toggles": _TOGGLES["instagram"],
                "trial_reels": {"type": "object", "properties": {
                    "recommended": _BOOL, "protocol": _TEXT}},
                "notes": _STRS}},
            "youtube_shorts": {"type": "object", "properties": {
                "title": {"type": "string", "maxLength": 100},
                "description": _TEXT, "hashtags": _tags(15),
                "related_video": {"type": ["string", "null"]},
                "toggles": _TOGGLES["youtube_shorts"], "notes": _STRS}}}},
        "posting": {"type": "array", "items": {"type": "object", "properties": {
            "item": _TEXT, "grade": {"enum": ["P", "S", "M", "A", "myth"]},
            "source": _TEXT}}},
        "checklist": _STRS,
    },
}

SCRIPT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": SCHEMA_ID,
    "title": "viral_script_maker script",
    "description": "Output of viral_script_maker.generate() — the script.json "
                   "every pipeline run ships (D152). Additional properties "
                   "are allowed.",
    "type": "object",
    "required": ["prompt", "presenter", "format", "duration_s", "niche",
                 "hook_stack", "beats", "caption"],
    "properties": {
        "prompt": {"type": "string", "minLength": 1},
        "presenter": {"enum": ["ai", "human"]},
        "format": {"enum": FORMATS},
        "duration_s": {"type": "number", "minimum": 5, "maximum": 180},
        "niche": {"type": "string", "minLength": 1},
        "fit": _TEXT,
        "hook_family": _TEXT,
        "hook_source": {"enum": ["template", "fallback", "pinned"],
                        "description": "D145: what actually rendered"},
        "fit_warning": {"type": ["string", "null"]},
        "persona": {"type": ["object", "null"],
                    "properties": {"name": _TEXT, "identity": _TEXT,
                                   "voice": _TEXT, "styling_rule": _TEXT}},
        "hook_stack": {"type": "array", "minItems": 1,
                       "items": {"$ref": "#/$defs/hook_item"}},
        "beats": {"type": "array", "minItems": 3,
                  "items": {"$ref": "#/$defs/beat"}},
        "caption": {"type": "string", "minLength": 1},
        "research_notes": {"type": "array", "items": _TEXT},
        "disclosure": _TEXT,
        "delivery_note": _TEXT,
        "series_plan": {"type": "object",
                        "description": "D146: backs a part-2 CTA"},
        "seed": {"type": ["integer", "null"]},
        "direction": {"$ref": "#/$defs/direction"},
        "hook_variants": {"type": "array", "minItems": 3, "maxItems": 5,
                          "items": {"$ref": "#/$defs/hook_variant"},
                          "description": "§1.2 (gate D154)"},
        "discovery": {"$ref": "#/$defs/discovery"},
        "creative_warnings": {"type": "array", "items": _TEXT,
                              "description": "vsp.creative.enrich module "
                                             "errors (a run must carry none)"},
    },
    "$defs": {
        "hook_item": {"type": "object", "required": ["type"],
                      "properties": _ITEM_PROPS},
        "beat": {"type": "object", "required": ["t", "type"],
                 "properties": _ITEM_PROPS},
        "direction": DIRECTION_SCHEMA,
        "hook_variant": HOOK_VARIANT_SCHEMA,
        "discovery": DISCOVERY_SCHEMA,
    },
}

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(REPO, "schema", "script.schema.json")

_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "integer": lambda v: (isinstance(v, int) and not isinstance(v, bool)) or
    (isinstance(v, float) and v.is_integer()),
}


def _resolve(ref, root):
    if not ref.startswith("#/"):
        raise ValueError(f"only local $ref supported: {ref}")
    node = root
    for part in ref[2:].split("/"):
        node = node[part.replace("~1", "/").replace("~0", "~")]
    return node


def _short(v):
    s = json.dumps(v, ensure_ascii=False)
    return s if len(s) <= 60 else s[:57] + "..."


def _check(v, sch, path, root, errs):
    if "$ref" in sch:
        _check(v, _resolve(sch["$ref"], root), path, root, errs)
    if "type" in sch:
        types = sch["type"] if isinstance(sch["type"], list) else [sch["type"]]
        if not any(_TYPES[t](v) for t in types):
            errs.append(f"{path}: expected {' or '.join(types)}, got {_short(v)}")
            return
    if "enum" in sch and v not in sch["enum"]:
        errs.append(f"{path}: {_short(v)} is not one of {sch['enum']}")
    if "const" in sch and v != sch["const"]:
        errs.append(f"{path}: {_short(v)} != const {_short(sch['const'])}")
    if isinstance(v, str):
        if "minLength" in sch and len(v) < sch["minLength"]:
            errs.append(f"{path}: shorter than {sch['minLength']} character(s)")
        if "maxLength" in sch and len(v) > sch["maxLength"]:
            errs.append(f"{path}: longer than {sch['maxLength']} character(s)")
        if "pattern" in sch and not re.search(sch["pattern"], v):
            errs.append(f"{path}: {_short(v)} does not match {sch['pattern']}")
    if _TYPES["number"](v):
        if "minimum" in sch and v < sch["minimum"]:
            errs.append(f"{path}: {v} < minimum {sch['minimum']}")
        if "maximum" in sch and v > sch["maximum"]:
            errs.append(f"{path}: {v} > maximum {sch['maximum']}")
    if isinstance(v, list):
        if "minItems" in sch and len(v) < sch["minItems"]:
            errs.append(f"{path}: {len(v)} item(s) < minItems {sch['minItems']}")
        if "maxItems" in sch and len(v) > sch["maxItems"]:
            errs.append(f"{path}: {len(v)} item(s) > maxItems {sch['maxItems']}")
        if isinstance(sch.get("items"), dict):
            for i, x in enumerate(v):
                _check(x, sch["items"], f"{path}[{i}]", root, errs)
    if isinstance(v, dict):
        for k in sch.get("required", []):
            if k not in v:
                errs.append(f"{path}: missing required property '{k}'")
        props = sch.get("properties", {})
        for k, x in v.items():
            if k in props:
                _check(x, props[k], f"{path}.{k}", root, errs)
            else:
                ap = sch.get("additionalProperties", True)
                if ap is False:
                    errs.append(f"{path}: additional property '{k}' not allowed")
                elif isinstance(ap, dict):
                    _check(x, ap, f"{path}.{k}", root, errs)


def validate(obj, schema=None):
    """-> list of error strings (empty = valid)."""
    sch = SCRIPT_SCHEMA if schema is None else schema
    errs = []
    _check(obj, sch, "$", sch, errs)
    return errs


def schema_text():
    return json.dumps(SCRIPT_SCHEMA, indent=2, ensure_ascii=False) + "\n"


def load_schema(path=SCHEMA_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_schema(path=SCHEMA_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(schema_text())
    return path


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--write" in argv:
        print(f"wrote {write_schema()}")
        return 0
    if "--check" in argv:
        try:
            with open(SCHEMA_PATH, encoding="utf-8") as f:
                ok = f.read() == schema_text()
        except OSError:
            ok = False
        print("schema/script.schema.json is " + ("up to date" if ok else
              "STALE — run python3 -m vsp.schema --write"))
        return 0 if ok else 1
    if not argv:
        print(__doc__.strip().split("\n\n")[1])
        return 2
    bad = 0
    for p in argv:
        with open(p, encoding="utf-8") as f:
            errs = validate(json.load(f))
        bad += bool(errs)
        print(f"{p}: {'valid' if not errs else 'INVALID'}")
        for e in errs:
            print(f"  {e}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
