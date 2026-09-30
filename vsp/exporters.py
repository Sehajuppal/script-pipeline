"""Stage-9 exports (D152): editor / hand-off files next to bundle.md.

    shotlist_csv(shots) -> str              RFC 4180 CSV (CRLF, minimal quoting)
    shots_json(script, shots, vo_lines) -> dict
    write_exports(outdir, script, shots, vo_lines) -> {name: path}
        captions.srt   SubRip sidecar            (vsp.captions.to_srt)
        captions.vtt   WebVTT sidecar            (vsp.captions.to_vtt)
        captions.json  Remotion Caption[] words  (vsp.captions.remotion_json)
        shotlist.csv   one row per shot/sub-shot (CapCut / Resolve shoot sheet)
        shots.json     machine-readable shot list + VO lines

The shot rows use the shot list's own rounded times (the bundle headings),
so the CSV and bundle.md always agree. v2.1 (CREATIVE-PLAN §1.4): the CSV
appends the shot plan columns (shot_type, scale, move, purpose, energy,
ai_risk, real_footage, setup — empty for shots without a plan) and
shots.json carries every shot key, including the full vsp.shotplan set. Captions are sidecars, never burned
in (DELIVERABLE: captioning is Marlowe's stage).
"""
import csv
import io
import json
import os
import re

from vsp import captions

CSV_COLUMNS = ["shot", "start_s", "end_s", "duration_s", "beat", "camera",
               "on_screen", "dialogue", "rehook", "delivery",
               # v2.1 shot plan (appended; legacy columns keep their positions)
               "shot_type", "scale", "move", "purpose", "energy", "ai_risk",
               "real_footage", "setup"]
PLAN_COLUMNS = CSV_COLUMNS[10:]


def _plan_cell(sh, key):
    v = sh.get(key)
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)
SCHEMA_VERSION = 1


def _times(sh):
    s, e = sh.get("s"), sh.get("e")
    if s is None or e is None:
        m = re.findall(r"(\d+(?:\.\d+)?)", sh.get("t", ""))
        s, e = (float(m[0]), float(m[1])) if len(m) >= 2 else (0.0, 0.0)
    # the bundle heading's rounding — CSV == shot list
    return float(f"{float(s):.1f}"), float(f"{float(e):.1f}")


def shotlist_csv(shots):
    """Shots -> CSV text (header + one row per shot/sub-shot)."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    w.writerow(CSV_COLUMNS)
    for sh in shots:
        s, e = _times(sh)
        w.writerow([sh.get("n", ""), f"{s:.1f}", f"{e:.1f}", f"{e - s:.1f}",
                    sh.get("beat", ""), sh.get("direction", ""),
                    sh.get("on_screen", ""), sh.get("dialogue", ""),
                    sh.get("rehook", ""), sh.get("delivery", "")]
                   + [_plan_cell(sh, k) for k in PLAN_COLUMNS])
    return buf.getvalue()


def slugify(prompt):
    return re.sub(r"[^a-z0-9]+", "-", (prompt or "x").lower()).strip("-") or "x"


def shots_json(script, shots, vo_lines):
    out = []
    for sh in shots:
        s, e = _times(sh)
        row = {k: v for k, v in sh.items() if k not in ("s", "e")}
        row.update({"start_s": s, "end_s": e, "duration_s": round(e - s, 1)})
        out.append(row)
    return {"schema_version": SCHEMA_VERSION, "prompt": script.get("prompt"),
            "slug": slugify(script.get("prompt")),
            "duration_s": script.get("duration_s"), "fps": captions.FPS,
            "presenter": script.get("presenter"), "format": script.get("format"),
            "niche": script.get("niche"), "shots": out,
            "vo_lines": list(vo_lines or [])}


def _write(path, text, newline=None):
    with open(path, "w", encoding="utf-8", newline=newline) as f:
        f.write(text)
    return path


def write_exports(outdir, script, shots, vo_lines, cues=None):
    """Write the five export files into outdir; returns {name: abs path}."""
    outdir = os.path.abspath(outdir)
    os.makedirs(outdir, exist_ok=True)
    if cues is None:
        cues = captions.build_cues(script, shots)
    files = {
        "captions.srt": (captions.to_srt(cues), None),
        "captions.vtt": (captions.to_vtt(cues), None),
        "captions.json": (captions.remotion_json(cues) + "\n", None),
        "shotlist.csv": (shotlist_csv(shots), ""),       # keep CRLF (RFC 4180)
        "shots.json": (json.dumps(shots_json(script, shots, vo_lines), indent=1,
                                  ensure_ascii=False) + "\n", None),
    }
    return {name: _write(os.path.join(outdir, name), text, nl)
            for name, (text, nl) in files.items()}
