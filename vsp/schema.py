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
hook_source / series_plan). Validator subset: type (incl. type lists),
required, properties, additionalProperties, items, enum, const, pattern,
minItems, maxItems, minLength, minimum, maximum, $ref (local "#/$defs/..").
Schema-valid is not gate-valid: the gates still own the semantics.
"""
import json
import os
import re
import sys

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
    },
    "$defs": {
        "hook_item": {"type": "object", "required": ["type"],
                      "properties": _ITEM_PROPS},
        "beat": {"type": "object", "required": ["t", "type"],
                 "properties": _ITEM_PROPS},
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
