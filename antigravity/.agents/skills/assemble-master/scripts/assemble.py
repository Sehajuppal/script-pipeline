#!/usr/bin/env python3
"""assemble.py - build deliverables/<slug>-master.mp4 from a render job:
each shot trimmed to its window, conformed 24->30 fps by frame duplication
(the fps=30 filter, never minterpolate), scaled and cropped to 1080x1920
(crop, never letterbox), concatenated in shot order; VO + ambience + SFX
mixed and normalised to -14 LUFS / -1 dBTP (two-pass loudnorm); H.264 30 fps
+ AAC 48 kHz. Music never goes in. Stdlib only, Python 3.9+.

  assemble.py --job jobs/<slug> [--pass final] [--dry-run] [--allow-placeholders]
  assemble.py --job jobs/<slug> --pass draft      -> deliverables/<slug>-draft.mp4 (540x960)
  assemble.py --job jobs/<slug> --contact-sheet   -> deliverables/contact_sheet.jpg

Sources per shot: selects.json {"<n>": "clips/..."} wins; lip-synced shots use
lipsync/shot-<n>.mp4; generated shots the latest ok clip of the pass in
render_log.jsonl (trimmed from window_in_s); filmed shots real/shot-<n>.mp4
(+ optional real/shot-<n>.json {"in_s": 1.2}); edit shots edit/shot-<n>.mp4
(a jump-cut punch-in falls back to a 1.3x crop of the previous take); a
reuse shot its own real/ file or shot 1's source. SFX: sfx/track.wav (full
timeline) or sfx/shot-<n>.wav (at the shot start). VO: vo/<slug>-vo.wav.
Exit 0 ok, 1 failure or missing source, 2 usage, 3 ffmpeg not on PATH.
"""
import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys

VF = "fps={fps},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"
LOUD = "loudnorm=I=-14:TP=-1:LRA=11"
AUDIO_EXT = (".wav", ".mp3", ".m4a", ".aac", ".flac")


def q(cmd):
    return " ".join(shlex.quote(str(c)) for c in cmd)


def load(job):
    p = os.path.join(job, "render.json")
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        print(f"assemble: cannot read {p}: {e}", file=sys.stderr)
        sys.exit(2)


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def latest_ok(job, n, pas):
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


def has_audio(path, dry):
    if dry or not shutil.which("ffprobe"):
        return True
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                        "stream=index", "-of", "csv=p=0", path], capture_output=True, text=True)
    return bool(r.stdout.strip())


def sources(job, r, pas):
    """-> (segments, missing shot numbers)."""
    sel = read_json(os.path.join(job, "selects.json"), {})
    segs, missing, by_n = [], [], {}
    for s in r["shots"]:
        n = str(s["n"])
        dur = round(float(s["window"][1]) - float(s["window"][0]), 3)
        seg = {"n": n, "start": s["window"][0], "dur": dur, "src": None, "in_s": 0.0,
               "punch": False, "audio": s.get("native_audio") or "keep_ambience", "kind": s["mode"]}
        lip = os.path.join(job, "lipsync", f"shot-{n}.mp4")
        real = os.path.join(job, "real", f"shot-{n}.mp4")
        gen_in = float(s.get("window_in_s") or 0.5)
        if n in sel:
            seg["src"] = os.path.join(job, sel[n])
            seg["in_s"] = gen_in if s.get("gen_duration_s") else 0.0
        elif (s.get("lipsync") or {}).get("required") and os.path.isfile(lip):
            seg.update(src=lip, in_s=gen_in if s.get("gen_duration_s") else 0.0)
        elif s.get("gen_duration_s"):
            seg.update(src=latest_ok(job, n, pas), in_s=gen_in)
        elif os.path.isfile(real):
            meta = read_json(os.path.join(job, "real", f"shot-{n}.json"), {})
            seg.update(src=real, in_s=float(meta.get("in_s") or 0.0))
        elif s["mode"] == "reuse" and s.get("reuse_of") in by_n:
            src = by_n[s["reuse_of"]]
            seg.update(src=src["src"], in_s=src["in_s"])
        elif s["mode"] == "edit":
            ed = os.path.join(job, "edit", f"shot-{n}.mp4")
            if os.path.isfile(ed):
                seg["src"] = ed
            elif s.get("shot_type") == "jump-cut-punch-in" and segs and segs[-1]["src"]:
                p = segs[-1]
                seg.update(src=p["src"], in_s=p["in_s"] + p["dur"], punch=True)
        if not seg["src"] or not (os.path.isfile(seg["src"]) or seg["src"].startswith("<")):
            missing.append(n)
            seg["src"] = None
        segs.append(seg)
        by_n[n] = seg
    return segs, missing


def seg_cmds(k, seg, tmp, w, h, fps, amb_db, dry):
    v, a = os.path.join(tmp, f"v{k:03d}.mp4"), os.path.join(tmp, f"a{k:03d}.wav")
    d = f"{seg['dur']:.3f}"
    base = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    enc = ["-r", str(fps), "-c:v", "libx264", "-preset", "medium", "-crf", "17",
           "-pix_fmt", "yuv420p"]
    silence = base + ["-f", "lavfi", "-t", d, "-i", "anullsrc=r=48000:cl=mono",
                      "-c:a", "pcm_s16le", a]
    if seg["src"] is None:
        vc = base + ["-f", "lavfi", "-i", f"color=c=0x808080:s={w}x{h}:r={fps}:d={d}"] + enc + [v]
        return v, a, [vc, silence]
    vf = VF.format(fps=fps, w=w, h=h)
    if seg["punch"]:
        vf = "crop=iw/1.3:ih/1.3," + vf
    vc = base + ["-ss", f"{seg['in_s']:.3f}", "-t", d, "-i", seg["src"], "-an", "-vf", vf] + enc + [v]
    if seg["audio"] == "keep_ambience" and has_audio(seg["src"], dry):
        ac = base + ["-ss", f"{seg['in_s']:.3f}", "-t", d, "-i", seg["src"], "-vn", "-af",
                     f"volume={amb_db}dB,apad", "-t", d, "-ar", "48000", "-ac", "1",
                     "-c:a", "pcm_s16le", a]
    else:
        ac = silence
    return v, a, [vc, ac]


def mix_graph(n_inputs, sfx_delays):
    """[0] ambience bed, [1] VO (optional), then SFX inputs with delays."""
    parts, labels = [], []
    for i in range(n_inputs):
        lab = f"m{i}"
        chain = "aformat=sample_rates=48000:channel_layouts=mono"
        if i in sfx_delays:
            chain += f",adelay={int(round(sfx_delays[i] * 1000))}"
        parts.append(f"[{i}:a]{chain}[{lab}]")
        labels.append(f"[{lab}]")
    parts.append("".join(labels) + f"amix=inputs={n_inputs}:duration=first:normalize=0[mix]")
    return ";".join(parts)


def measured(stderr):
    m = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", stderr or "")
    return json.loads(m[-1]) if m else None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Assemble the uncut master (windows, 24->30 by "
                                 "frame duplication, crop to 1080x1920, VO + ambience + SFX, "
                                 "-14 LUFS / -1 dBTP, no music).")
    ap.add_argument("--job", required=True, help="job dir with render.json")
    ap.add_argument("--pass", dest="pass_", choices=("draft", "final"), default="final")
    ap.add_argument("--dry-run", action="store_true", help="print the ffmpeg commands only")
    ap.add_argument("--allow-placeholders", action="store_true",
                    help="grey slate for a missing source (listed in the report)")
    ap.add_argument("--contact-sheet", action="store_true", help="middle frame of each clip, tiled")
    a = ap.parse_args(argv)
    r = load(a.job)
    slug = r.get("slug") or "master"
    fin = a.pass_ == "final"
    w, h = (1080, 1920) if fin else (540, 960)
    fps = int((r.get("format") or {}).get("master", {}).get("fps") or 30)
    amb_db = int(((r.get("audio") or {}).get("mix") or {}).get("ambience_db", -12))
    if not a.dry_run and not shutil.which("ffmpeg"):
        print("assemble: ffmpeg not on PATH (allow command(ffmpeg))", file=sys.stderr)
        return 3
    out_dir = os.path.join(a.job, "deliverables")
    tmp = os.path.join(a.job, "build", a.pass_)
    segs, missing = sources(a.job, r, a.pass_)
    if a.contact_sheet:
        clips = [s for s in segs if s["src"] and s["kind"] in ("ai", "reuse")]
        cmds = [["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss",
                 f"{s['in_s'] + s['dur'] / 2:.3f}", "-i", s["src"], "-frames:v", "1", "-vf",
                 "scale=270:480", os.path.join(tmp, f"thumb_{k + 1:03d}.png")]
                for k, s in enumerate(clips)]
        rows = max(1, (len(clips) + 5) // 6)
        cmds.append(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-framerate", "1",
                     "-i", os.path.join(tmp, "thumb_%03d.png"), "-vf", f"tile=6x{rows}",
                     "-frames:v", "1", os.path.join(out_dir, "contact_sheet.jpg")])
        return execute(cmds, a.dry_run, tmp, out_dir)
    if missing and not a.allow_placeholders:
        msg = f"no source for shot(s) {', '.join(missing)}: render, film (real/shot-<n>.mp4) or " \
              "pass --allow-placeholders for a review cut; never drop a beat"
        if not a.dry_run:
            print(f"assemble: {msg}", file=sys.stderr)
            return 1
        print(f"# WARN {msg}")
        for s in segs:
            if s["src"] is None:
                s["src"] = f"<missing source for shot {s['n']}>"
    cmds, vlist, alist = [], [], []
    for k, s in enumerate(segs):
        v, au, cs = seg_cmds(k, s, tmp, w, h, fps, amb_db, a.dry_run)
        cmds += cs
        vlist.append(v)
        alist.append(au)
    vtxt, atxt = os.path.join(tmp, "video.txt"), os.path.join(tmp, "audio.txt")
    video, bed = os.path.join(tmp, "video.mp4"), os.path.join(tmp, "ambience.wav")
    base = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    cmds.append(base + ["-f", "concat", "-safe", "0", "-i", vtxt, "-c", "copy", video])
    cmds.append(base + ["-f", "concat", "-safe", "0", "-i", atxt, "-c:a", "pcm_s16le", bed])
    inputs, delays = [bed], {}
    vo = os.path.join(a.job, "vo", (r.get("audio") or {}).get("vo_file") or f"{slug}-vo.wav")
    if os.path.isfile(vo) or a.dry_run and (r.get("audio") or {}).get("vo_file"):
        inputs.append(vo)
    sfx_dir = os.path.join(a.job, "sfx")
    track = os.path.join(sfx_dir, "track.wav")
    if os.path.isfile(track):
        inputs.append(track)
    else:
        for s in segs:
            for ext in AUDIO_EXT:
                p = os.path.join(sfx_dir, f"shot-{s['n']}{ext}")
                if os.path.isfile(p):
                    delays[len(inputs)] = float(s["start"])
                    inputs.append(p)
                    break
    graph = mix_graph(len(inputs), delays)
    ins = []
    for p in inputs:
        ins += ["-i", p]
    dur = f"{float(r.get('duration_s') or 0):.3f}"
    mixwav = os.path.join(tmp, "mix.wav")
    cmds.append(["ffmpeg", "-hide_banner", "-nostats"] + ins + ["-filter_complex",
                 graph + f";[mix]{LOUD}:print_format=json[out]", "-map", "[out]", "-f", "null", "-"])
    cmds.append(base + ins + ["-filter_complex", graph + f";[mix]{LOUD}:measured_I=<I>:"
                              "measured_TP=<TP>:measured_LRA=<LRA>:measured_thresh=<THRESH>:"
                              "offset=<OFFSET>:linear=true[out]", "-map", "[out]", "-ar", "48000",
                              "-ac", "1", "-c:a", "pcm_s16le", mixwav])
    name = f"{slug}-master.mp4" if fin else f"{slug}-draft.mp4"
    cmds.append(base + ["-i", video, "-i", mixwav, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", dur,
                        "-movflags", "+faststart", os.path.join(out_dir, name)])
    lists = {vtxt: vlist, atxt: alist}
    report = {"master": name, "pass": a.pass_, "size": f"{w}x{h}", "fps": fps,
              "segments": [{k: s[k] for k in ("n", "kind", "src", "in_s", "dur", "audio", "punch")}
                           for s in segs],
              "placeholders": missing, "inputs": inputs, "music": False}
    return execute(cmds, a.dry_run, tmp, out_dir, lists, report, a.job, slug)


def execute(cmds, dry, tmp, out_dir, lists=None, report=None, job=None, slug=None):
    if dry:
        for c in cmds:
            print(q(c))
        return 0
    os.makedirs(tmp, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    for path, files in (lists or {}).items():
        with open(path, "w", encoding="utf-8") as f:
            f.write("".join(f"file '{os.path.abspath(x)}'\n" for x in files))
    meas = None
    for c in cmds:
        c = list(c)
        if meas and any("measured_I=<I>" in str(x) for x in c):
            c = [str(x).replace("<I>", str(meas["input_i"])).replace("<TP>", str(meas["input_tp"]))
                 .replace("<LRA>", str(meas["input_lra"])).replace("<THRESH>", str(meas["input_thresh"]))
                 .replace("<OFFSET>", str(meas["target_offset"])) for x in c]
        elif any("measured_I=<I>" in str(x) for x in c):
            c = [re.sub(r":measured_I=<I>.*:linear=true", "", str(x)) for x in c]
        p = subprocess.run(c, capture_output=True, text=True)
        if "print_format=json" in " ".join(map(str, c)):
            meas = measured(p.stderr)
            continue
        if p.returncode != 0:
            print(f"assemble: failed: {q(c)}\n{p.stderr[-800:]}", file=sys.stderr)
            return 1
    if report is not None:
        words = os.path.join(job, f"{slug}-words.json")
        if os.path.isfile(words):
            shutil.copy(words, os.path.join(out_dir, os.path.basename(words)))
        report["loudnorm_measured"] = meas
        with open(os.path.join(out_dir, "assemble_report.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, indent=1)
        print(f"wrote {os.path.join(out_dir, report['master'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
