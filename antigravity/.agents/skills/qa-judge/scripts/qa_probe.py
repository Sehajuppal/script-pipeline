#!/usr/bin/env python3
"""qa_probe.py - the automatable QA gate checks (render.json qa_gate, stage
"probe") on Omni clips and the master, via ffprobe/ffmpeg; plus the
Gemini-judge prompt for the judge stage. Stdlib only, Python 3.9+.

  qa_probe.py --job jobs/<slug> --pass final [--shot 2]   latest ok clip per shot
  qa_probe.py --job jobs/<slug> --master                  deliverables/<slug>-master.mp4
  qa_probe.py --clip FILE [--window-out 3.0] [--fps 24]   one file
  qa_probe.py --job jobs/<slug> --judge-prompt --shot 2   print the judge prompt
  qa_probe.py --job jobs/<slug> --stills --pass final     first/middle/last stills

Checks: aspect 9:16 within 1%, fps, duration >= window_out_s, an audio
stream, no letterbox (cropdetect), zero scene cuts (select gt(scene,0.4)),
duplicate-frame ratio (mpdecimate). Prints one JSON report per file.
Exit: 0 all pass, 1 a check failed, 3 skipped (ffprobe/ffmpeg not on PATH).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter

ASPECT, ASPECT_TOL = 9 / 16.0, 0.01
SCENE = 0.4
DUP_MAX_CLIP = 0.2
WOBBLE_RUN = 2          # 12 fps -> runs of 1, 8 fps -> runs of 2
BAR_PX = 8

JUDGE = """You are the QA judge for one AI-generated shot of a vertical 9:16 short video.
You get stills (first, middle, last) and the clip. Compare them with the references.

Shot {n} ({shot_type}, {scale} {angle}, {move}); needs: {needs}.
Presenter reference (same person in every face shot): {presenter}
Product reference (must match the product photos): {product}
Planned action: {action}

Score each item 1-5 (5 = flawless, 4 = shippable, 3 or less = fails) and name every defect:
1. identity: the same presenter as the reference sheet - face, hair, glasses, skin, outfit. {id_note}
2. product: the product matches its photos - shape, colour, size, finish; no invented logo,
   brand name or label text.
3. hands: five fingers per hand, no fused or extra fingers, plausible grip and contact. {hand_note}
4. morphing: no melting, warping, flicker or detaching parts; objects stay the same object.
5. text: no legible text, captions, subtitles, logos or watermarks anywhere in frame{label_note}.
6. cuts: one continuous shot - no scene cut, no jump, no second angle.
7. safe box: the key action sits inside x 120-888 and y 288-1248 of the 1080x1920 frame.
8. realism: phone-footage look, natural skin texture, one plausible light source, no CGI sheen.
9. action: the planned action happens once, already in motion at the first frame.

Answer with JSON only:
{{"identity": n, "product": n, "hands": n, "morphing": n, "text": n, "cuts": n,
 "safe_box": n, "realism": n, "action": n, "defects": ["..."],
 "verdict": "pass" | "edit" | "regenerate" | "fallback",
 "edit_instruction": "one short fix ending with: Keep everything else the same."}}
Use n = null for an item that does not apply to this shot. Verdict rules: pass when every
applicable item is >= 4; edit for one local fix (a colour, an object, a small artefact);
regenerate for identity, hands, cuts or morphing failures; fallback after the last attempt."""


def have_tools():
    return shutil.which("ffprobe") is not None and shutil.which("ffmpeg") is not None


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=600)


def ratio(txt):
    m = re.match(r"^\s*(\d+)(?:/(\d+))?\s*$", str(txt or ""))
    if not m:
        return None
    den = float(m.group(2) or 1)
    return float(m.group(1)) / den if den else None


def probe(path):
    r = run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path])
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:300] or "ffprobe failed")
    return json.loads(r.stdout or "{}")


def scene_cuts(path):
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-an", "-vf",
             f"select='gt(scene,{SCENE})',showinfo", "-f", "null", "-"])
    return len(re.findall(r"pts_time:", r.stderr))


def letterbox(path, w, h):
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-an", "-vf",
             "cropdetect=24:2:0", "-frames:v", "72", "-f", "null", "-"])
    crops = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", r.stderr)
    if not crops:
        return False, None
    cw, ch, cx, cy = (int(x) for x in Counter(crops).most_common(1)[0][0])
    bars_v = cy > BAR_PX and abs((h - ch - cy) - cy) <= BAR_PX + 2
    bars_h = cx > BAR_PX and abs((w - cw - cx) - cx) <= BAR_PX + 2
    return bars_v or bars_h, f"{cw}x{ch}+{cx}+{cy}"


def dup_ratio(path):
    """Share of frames that repeat in short runs (the 8-12 fps wobble: keep,
    drop, keep, drop ...). Long runs are a static shot, not a wobble."""
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-loglevel", "debug", "-i", path, "-an",
             "-vf", "mpdecimate", "-f", "null", "-"])
    seq = re.findall(r"\b(keep|drop) pts:", r.stderr)
    if not seq:
        return None
    runs, cur = [], 0
    for x in seq:
        if x == "drop":
            cur += 1
        elif cur:
            runs.append(cur)
            cur = 0
    if cur:
        runs.append(cur)
    short = sum(n for n in runs if n <= WOBBLE_RUN)
    return round(short / float(len(seq)), 3)


def check_file(path, fps, min_s, master=False, cuts=True):
    out = {"file": path, "checks": []}

    def add(cid, ok, value, threshold):
        out["checks"].append({"id": cid, "ok": bool(ok), "value": value, "threshold": threshold})
    info = probe(path)
    vs = [s for s in info.get("streams") or [] if s.get("codec_type") == "video"]
    aus = [s for s in info.get("streams") or [] if s.get("codec_type") == "audio"]
    if not vs:
        add("video_stream", False, 0, 1)
        out["ok"] = False
        return out
    v = vs[0]
    w, h = int(v.get("width") or 0), int(v.get("height") or 0)
    sar = ratio(str(v.get("sample_aspect_ratio") or "1/1").replace(":", "/")) or 1.0
    asp = (w * sar) / float(h) if h else 0.0
    add("aspect", abs(asp - ASPECT) <= ASPECT * ASPECT_TOL, round(asp, 4), "9:16 +/-1%")
    fr = ratio(v.get("avg_frame_rate")) or ratio(v.get("r_frame_rate"))
    add("fps", fr is not None and abs(fr - fps) <= 0.5, fr and round(fr, 3), fps)
    dur = float((info.get("format") or {}).get("duration") or v.get("duration") or 0)
    add("duration", dur + 1e-3 >= min_s, round(dur, 3), f">= {min_s}")
    add("audio_stream", bool(aus), len(aus), ">= 1")
    lb, crop = letterbox(path, w, h)
    add("letterbox", not lb, crop, f"no bars > {BAR_PX} px")
    if cuts:
        n = scene_cuts(path)
        add("scene_cuts", n == 0, n, f"0 at scene > {SCENE}")
    if master:
        add("size", (w, h) == (1080, 1920), f"{w}x{h}", "1080x1920")
    else:                        # the master duplicates frames by design (24 -> 30)
        dr = dup_ratio(path)
        add("dup_frames", dr is None or dr <= DUP_MAX_CLIP, dr, f"<= {DUP_MAX_CLIP}")
    out["ok"] = all(c["ok"] for c in out["checks"])
    return out


def load(job):
    with open(os.path.join(job, "render.json"), encoding="utf-8") as f:
        return json.load(f)


def latest_clip(job, n, pas):
    best = None
    try:
        with open(os.path.join(job, "render_log.jsonl"), encoding="utf-8") as f:
            for ln in f:
                try:
                    e = json.loads(ln)
                except ValueError:
                    continue
                if str(e.get("shot")) == str(n) and e.get("pass") == pas and \
                        e.get("status") == "ok" and e.get("file"):
                    best = os.path.join(job, e["file"])
    except OSError:
        pass
    return best


def judge_prompt(r, shot):
    idt = r.get("identity") or {}
    needs = shot.get("needs") or []
    body = re.sub(r"^\[#[^\]]*\]\s*(\[#[^\]]*\]\s*)?", "", shot.get("prompt") or "")
    act = re.sub(r"\s*<[A-Z_0-9]+>", "", re.split(r"\. ", body)[0])
    return JUDGE.format(
        n=shot.get("n"), shot_type=shot.get("shot_type"), scale=shot.get("scale"),
        angle=shot.get("angle"), move=shot.get("move"), needs=", ".join(needs) or "none",
        presenter=idt.get("presenter_text") if "face" in needs else "not in this shot",
        product=(idt.get("product_text") or "none") if {"product", "props"} & set(needs)
        else "not in this shot", action=act,
        id_note="" if "face" in needs else "(no face in this shot: score null unless a face appears, then 1)",
        hand_note="" if "hands" in needs else "(no hands planned: any hand that appears must still pass)",
        label_note=" except the real label photographed in the first frame"
        if shot.get("shot_type") == "label-detail-ecu" else "")


def stills(job, shot, clip):
    os.makedirs(os.path.join(job, "clips", "stills"), exist_ok=True)
    w_in, w_out = float(shot.get("window_in_s") or 0.5), float(shot.get("window_out_s") or 1.0)
    outs = []
    for tag, t in (("first", w_in), ("mid", (w_in + w_out) / 2), ("last", max(w_in, w_out - 0.05))):
        dest = os.path.join(job, "clips", "stills", f"{os.path.basename(clip)[:-4]}-{tag}.jpg")
        run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", clip,
             "-frames:v", "1", "-q:v", "2", dest])
        outs.append(dest)
    return outs


def main(argv=None):
    ap = argparse.ArgumentParser(description="Probe Omni clips / the master against the QA "
                                 "gate (ffprobe/ffmpeg) and print the Gemini-judge prompt.")
    ap.add_argument("--job", help="job dir with render.json")
    ap.add_argument("--pass", dest="pass_", choices=("draft", "final"), default="final")
    ap.add_argument("--shot", action="append", default=[], help="shot n (repeat or comma list)")
    ap.add_argument("--master", action="store_true", help="probe deliverables/<slug>-master.mp4")
    ap.add_argument("--clip", help="probe one file")
    ap.add_argument("--window-out", type=float, default=0.0, help="--clip: minimum duration")
    ap.add_argument("--fps", type=float, default=24.0, help="--clip: expected fps")
    ap.add_argument("--judge-prompt", action="store_true", help="print the judge prompt (offline)")
    ap.add_argument("--stills", action="store_true", help="extract first/middle/last stills")
    a = ap.parse_args(argv)
    if not a.job and not a.clip:
        ap.error("--job or --clip is required")
    r = load(a.job) if a.job else None
    want = [x for v in a.shot for x in v.split(",") if x]
    shots = [s for s in (r or {}).get("shots", []) if s.get("gen_duration_s")
             and (not want or str(s["n"]) in want)]
    if a.judge_prompt:
        if not shots:
            ap.error("--judge-prompt needs --job and a generated --shot")
        for s in shots:
            print(f"### shot {s['n']}\n" + judge_prompt(r, s) + "\n")
        return 0
    if not have_tools():
        print(json.dumps({"status": "skipped", "reason": "ffprobe/ffmpeg not on PATH; install "
                          "ffmpeg or allow command(ffmpeg) and command(ffprobe)"}))
        return 3
    reports = []
    if a.clip:
        reports.append(check_file(a.clip, a.fps, a.window_out))
    elif a.master:
        p = os.path.join(a.job, "deliverables", (r.get("deliverables") or {}).get("master", ""))
        if not os.path.isfile(p):
            print(json.dumps({"status": "error", "reason": f"no master at {p}"}))
            return 1
        reports.append(check_file(p, r["format"]["master"]["fps"],
                                  float(r.get("duration_s") or 0) - 0.05, master=True, cuts=False))
    else:
        for s in shots:
            clip = latest_clip(a.job, s["n"], a.pass_)
            if not clip or not os.path.isfile(clip):
                reports.append({"shot": s["n"], "ok": False, "error": f"no ok {a.pass_} clip"})
                continue
            rep = check_file(clip, r["format"]["source_fps"], float(s["window_out_s"]))
            rep["shot"] = s["n"]
            if a.stills:
                rep["stills"] = stills(a.job, s, clip)
            reports.append(rep)
    for rep in reports:
        print(json.dumps(rep, ensure_ascii=False))
    return 0 if all(x.get("ok") for x in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
