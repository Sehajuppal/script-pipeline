#!/usr/bin/env python3
"""cartesia_vo.py - voice a voice_plan.json with Cartesia Sonic over SSE:
one request per line, 48 kHz mono WAVs, the placed VO track and
<slug>-words.json. Stdlib only, Python 3.9+.

  cartesia_vo.py --job jobs/<slug> [--line L1 --line L6] [--dry-run]
  cartesia_vo.py --job jobs/<slug> --voice-id <id> [--no-emotion]
  cartesia_vo.py --job jobs/<slug> --calibrate      (speeds 0.9/1.0/1.1/1.2)

Reads DIR/voice_plan.json (+ DIR/vo/calibration.json when present). Writes
DIR/vo/<id>.wav, DIR/vo/<id>.events.json, DIR/vo/<slug>-vo.wav (the mixed
mono timeline), DIR/<slug>-words.json and DIR/vo/voice_report.json. Keys:
CARTESIA_API_KEY (and optional CARTESIA_VOICE_ID) from the environment
only. The real_voice lane is refused: the plan is a read guide for the
creator, printed instead. Exit 0 ok, 1 QA/API failure, 2 usage, 3 refused.
"""
import argparse
import array
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import wave

SPEEDS = ("0.9", "1.0", "1.1", "1.2")
HOUSE_SPEED = (0.9, 1.15)
WPM_AT_1 = 175
BACKOFF_S = (3, 10, 30)
WORD = re.compile(r"[A-Za-z0-9]+(?:['\u2019][A-Za-z]+)?")
TAG = re.compile(r"<[^<>]+>")


def die(msg, code=2):
    print(f"cartesia_vo: {msg}", file=sys.stderr)
    sys.exit(code)


def load(job):
    p = os.path.join(job, "voice_plan.json")
    try:
        with open(p, encoding="utf-8") as f:
            vp = json.load(f)
    except (OSError, ValueError) as e:
        die(f"cannot read {p}: {e}")
    if vp.get("schema_version") != 1 or not isinstance(vp.get("lines"), list):
        die(f"{p} is not a schema_version 1 voice plan")
    return vp


def read_guide(vp):
    """The real_voice lane: print what the creator records, line by line."""
    print(f"REAL VOICE lane ({vp.get('slug')}): no TTS. Record these lines yourself, "
          "on the day, at a natural pace:")
    for ln in vp["lines"]:
        w = ln.get("window") or [0, 0]
        wpm = ln.get("wpm") or {}
        print(f"[{w[0]:.1f}-{w[1]:.1f}s] {ln['id']} ({ln.get('anchor')}): {ln.get('display')}"
              f"  | {wpm.get('target')} wpm, never under {wpm.get('floor')}; tone "
              f"{ln.get('tone')}" + (f"; {ln['delivery']}" if ln.get("delivery") else ""))
    print("Marlowe's caption stage aligns the words; no words.json from this lane.")


def speed_for(target, calib):
    pts = sorted((float(k), float(v)) for k, v in (calib or {}).items() if v)
    if len(pts) < 2:
        pts = [(0.9, 0.9 * WPM_AT_1), (1.2, 1.2 * WPM_AT_1)]
    sp = None
    for (s0, w0), (s1, w1) in zip(pts, pts[1:]):
        if w0 <= target <= w1 and w1 > w0:
            sp = s0 + (s1 - s0) * (target - w0) / (w1 - w0)
            break
    if sp is None:
        (s0, w0), (s1, w1) = (pts[0], pts[1]) if target < pts[0][1] else (pts[-2], pts[-1])
        sp = s0 + (s1 - s0) * (target - w0) / (w1 - w0) if w1 != w0 else 1.0
    sp = min(HOUSE_SPEED[1], max(HOUSE_SPEED[0], sp))
    return 1.0 if abs(sp - 1.0) <= 0.05 + 1e-9 else round(sp, 2)


def calibration(job):
    p = os.path.join(job, "vo", "calibration.json")
    try:
        with open(p, encoding="utf-8") as f:
            return (json.load(f) or {}).get("calibration_wpm") or {}
    except (OSError, ValueError):
        return {}


def request_body(vp, ln, voice_id, calib, no_emotion, speed=None):
    eng = vp["engine"]
    gc = dict(ln.get("generation_config") or {})
    if speed is not None:
        gc = {"speed": speed}
    elif calib and "speed" in gc:
        gc["speed"] = speed_for(float(ln["wpm"]["target"]), calib)
    if no_emotion or not (vp.get("voice") or {}).get("emotive"):
        gc.pop("emotion", None)
    body = {"model_id": eng["model_id"], "transcript": ln["transcript"], "voice": voice_id,
            "output_format": dict(eng["output_format"]), "add_timestamps": True}
    if eng.get("locale"):
        body["locale"] = eng["locale"]
    elif eng.get("language"):
        body["language"] = eng["language"]
    if eng.get("normalization"):
        body["normalization"] = eng["normalization"]
    if eng.get("pronunciation_dict_id"):
        body["pronunciation_dict_id"] = eng["pronunciation_dict_id"]
    if gc:
        body["generation_config"] = gc
    return body


def headers(vp, key):
    return {"Authorization": f"Bearer {key}", "Cartesia-Version": vp["engine"]["api_version"],
            "Content-Type": "application/json", "Accept": "text/event-stream"}


def sse_events(resp):
    """Frames are 'data: <json>' lines separated by blank lines."""
    buf = []
    for raw in resp:
        line = raw.decode("utf-8", "replace").rstrip("\r\n")
        if not line:
            if buf:
                yield json.loads("\n".join(buf))
                buf = []
            continue
        if line.startswith("data:"):
            buf.append(line[5:].lstrip())
    if buf:
        yield json.loads("\n".join(buf))


def tts(vp, body, key):
    """-> (pcm bytes, timestamp events). Retries 429/5xx with backoff."""
    url = vp["engine"]["base_url"].rstrip("/") + vp["engine"]["endpoint"]
    data = json.dumps(body).encode("utf-8")
    for k in range(len(BACKOFF_S) + 1):
        req = urllib.request.Request(url, data=data, method="POST", headers=headers(vp, key))
        try:
            pcm, stamps = bytearray(), []
            with urllib.request.urlopen(req, timeout=300) as resp:
                for ev in sse_events(resp):
                    t = ev.get("type")
                    if t == "chunk" and ev.get("data"):
                        pcm += base64.b64decode(ev["data"])
                    elif t == "timestamps" and ev.get("word_timestamps"):
                        stamps.append(ev["word_timestamps"])
                    elif t == "error":
                        raise RuntimeError(f"Cartesia error: {ev.get('error') or ev}")
                    if t == "done" or ev.get("done") is True:
                        break
            return bytes(pcm), stamps
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")[:600]
            if (e.code == 429 or e.code >= 500) and k < len(BACKOFF_S):
                time.sleep(BACKOFF_S[k])
                continue
            raise RuntimeError(f"HTTP {e.code}: {msg}")
        except (urllib.error.URLError, TimeoutError) as e:
            if k < len(BACKOFF_S):
                time.sleep(BACKOFF_S[k])
                continue
            raise RuntimeError(str(e))
    raise RuntimeError("retries exhausted")


def words_of(stamps):
    out = []
    for wt in stamps:
        for w, s, e in zip(wt.get("words") or [], wt.get("start") or [], wt.get("end") or []):
            out.append([str(w), float(s), float(e)])
    for a, b in zip(out, out[1:]):              # start times are the weaker signal
        b[1] = max(b[1], a[2])
        b[2] = max(b[2], b[1])
    return out


def write_wav(path, pcm, rate):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)


def trim(pcm, words, rate, head_ms, tail_ms):
    """Cut to head_ms before the first word and tail_ms after the last; shift
    the word times by the same offset. -> (pcm, words, head_s)."""
    if not words:
        return pcm, words, 0.0
    total = len(pcm) // 2 / float(rate)
    a = max(0.0, words[0][1] - head_ms / 1000.0)
    b = min(total, words[-1][2] + tail_ms / 1000.0)
    i, j = int(a * rate) * 2, int(b * rate) * 2
    return pcm[i:j], [[w, s - a, e - a] for w, s, e in words], a


def place(vp, done):
    """Anchor each clip: dialogue speech starts at window start + offset, a
    rehook ends at window end - offset; never closer than the plan's gap to
    the previous line. -> {id: clip start on the master timeline}."""
    tm = vp.get("timing") or {}
    off = float(tm.get("anchor_offset_s", 0.1))
    out, prev_end = {}, None
    for ln in vp["lines"]:
        d = done.get(ln["id"])
        if not d or not d["words"]:
            continue
        w0, w1 = d["words"][0][1], d["words"][-1][2]
        win = ln["window"]
        start = (win[0] + off - w0) if ln.get("anchor") == "start" else (win[1] - off - w1)
        gap = float(ln.get("gap_before_s") or tm.get("min_gap_s", 0.3))
        if prev_end is not None and start + w0 < prev_end + gap:
            start = prev_end + gap - w0
        start = max(0.0, start)
        out[ln["id"]] = round(start, 3)
        prev_end = start + w1
    return out


def words_json(vp, done, placed, duration):
    """research §4.4: words on the master timeline, sorted, starts clamped."""
    out = []
    for ln in vp["lines"]:
        d = done.get(ln["id"])
        if not d or ln["id"] not in placed:
            continue
        for w, s, e in d["words"]:
            out.append({"word": w, "start": round(placed[ln["id"]] + s, 3),
                        "end": round(placed[ln["id"]] + e, 3)})
    out.sort(key=lambda x: x["start"])
    for a, b in zip(out, out[1:]):
        b["start"] = max(b["start"], a["end"])
        b["end"] = max(b["end"], b["start"])
    return {"words": out, "duration_s": round(duration, 3)}


def mix(done, placed, duration, rate):
    n = int(round(duration * rate))
    buf = array.array("i", [0]) * n
    for lid, start in placed.items():
        smp = array.array("h")
        smp.frombytes(done[lid]["pcm"][: len(done[lid]["pcm"]) // 2 * 2])
        if sys.byteorder == "big":
            smp.byteswap()
        o = int(round(start * rate))
        for k, v in enumerate(smp):
            if 0 <= o + k < n:
                buf[o + k] += v
    out = array.array("h", (max(-32768, min(32767, v)) for v in buf))
    if sys.byteorder == "big":
        out.byteswap()
    return out.tobytes()


def qa(vp, ln, d, placed):
    """wpm per line (words / speech time) and the window fit."""
    probs, ws = [], d["words"]
    if not ws:
        return ["no word timestamps returned"], None
    speech = max(1e-6, ws[-1][2] - ws[0][1])
    n = len(WORD.findall(TAG.sub(" ", ln["transcript"])))
    wpm = round(n / speech * 60.0, 1)
    q = vp.get("qa") or {}
    floor = float((ln.get("wpm") or {}).get("floor") or 0)
    if wpm > float(q.get("wpm_fail_above", 200)):
        probs.append(f"FAIL {wpm} wpm > {q.get('wpm_fail_above', 200)}")
    elif wpm > float(q.get("wpm_warn_above", 190)):
        probs.append(f"WARN {wpm} wpm > {q.get('wpm_warn_above', 190)}")
    if floor and wpm < floor - float(q.get("wpm_warn_below_floor_by", 10)):
        probs.append(f"WARN {wpm} wpm is more than 10 under the beat floor {floor:g}")
    if ln["id"] in placed:
        end = placed[ln["id"]] + ws[-1][2]
        if end > ln["window"][1] + 0.3:
            probs.append(f"WARN ends at {end:.2f} s, {end - ln['window'][1]:.2f} s past its "
                         "window: trim words (never time-stretch)")
    return probs, wpm


def run(a, vp, key, voice_id):
    job, eng = a.job, vp["engine"]
    rate = int(eng["output_format"]["sample_rate"])
    tm = vp.get("timing") or {}
    calib = calibration(job)
    want = [x for v in a.line for x in v.split(",") if x]
    lines = [ln for ln in vp["lines"] if not want or ln["id"] in want]
    if want and len(lines) != len(set(want)):
        die(f"unknown line id in {', '.join(want)}")
    vo = os.path.join(job, "vo")
    if not a.dry_run:
        os.makedirs(vo, exist_ok=True)
    if a.calibrate:
        aud = ((vp.get("voice") or {}).get("selection") or {}).get("audition_lines") or \
            [ln["id"] for ln in vp["lines"][:3]]
        lines = [ln for ln in vp["lines"] if ln["id"] in aud][:3]
        res = {s: [] for s in SPEEDS}
        for ln in lines:
            for s in SPEEDS:
                body = request_body(vp, ln, voice_id, None, True, speed=float(s))
                if a.dry_run:
                    print(json.dumps({"line": ln["id"], "calibrate_speed": s, "method": "POST",
                                      "url": eng["base_url"] + eng["endpoint"],
                                      "headers": headers(vp, "$CARTESIA_API_KEY"),
                                      "body": body}, ensure_ascii=False))
                    continue
                pcm, st = tts(vp, body, key)
                ws = words_of(st)
                if ws:
                    n = len(WORD.findall(ln["transcript"]))
                    res[s].append(n / max(1e-6, ws[-1][2] - ws[0][1]) * 60.0)
        if a.dry_run:
            return 0
        cal = {s: (round(sum(v) / len(v), 1) if v else None) for s, v in res.items()}
        with open(os.path.join(vo, "calibration.json"), "w", encoding="utf-8") as f:
            json.dump({"voice_id": voice_id, "model_id": eng["model_id"], "lines":
                       [ln["id"] for ln in lines], "calibration_wpm": cal}, f, indent=1)
        print("calibration wpm: " + ", ".join(f"{s}: {v}" for s, v in cal.items()))
        return 0
    done, report, bad = {}, [], False
    for ln in lines:
        body = request_body(vp, ln, voice_id, calib, a.no_emotion)
        if a.dry_run:
            print(json.dumps({"line": ln["id"], "method": "POST",
                              "url": eng["base_url"] + eng["endpoint"],
                              "headers": headers(vp, "$CARTESIA_API_KEY"), "body": body},
                             ensure_ascii=False))
            continue
        print(f"{ln['id']}: {ln['transcript']}")
        try:
            pcm, st = tts(vp, body, key)
        except RuntimeError as e:
            print(f"{ln['id']}: FAILED {e}", file=sys.stderr)
            report.append({"id": ln["id"], "status": "failed", "error": str(e)[:300]})
            bad = True
            continue
        with open(os.path.join(vo, f"{ln['id']}.events.json"), "w", encoding="utf-8") as f:
            json.dump(st, f)
        pcm2, ws, head = trim(pcm, words_of(st), rate, tm.get("trim_head_ms", 40),
                              tm.get("trim_tail_ms", 80))
        write_wav(os.path.join(vo, f"{ln['id']}.wav"), pcm2, rate)
        done[ln["id"]] = {"pcm": pcm2, "words": ws, "head": head,
                          "speed": (body.get("generation_config") or {}).get("speed")}
    if a.dry_run:
        return 0
    if want:
        print(f"rendered {len(done)} line(s); run without --line to place and mix all")
        return 1 if bad else 0
    placed = place(vp, done)
    dur = float(vp.get("duration_s") or 0) or max(
        [placed[k] + len(d["pcm"]) / 2.0 / rate for k, d in done.items()] + [1.0])
    for ln in lines:
        d = done.get(ln["id"])
        if not d:
            continue
        probs, wpm = qa(vp, ln, d, placed)
        bad = bad or any(p.startswith("FAIL") for p in probs)
        report.append({"id": ln["id"], "status": "ok", "audio_file": f"vo/{ln['id']}.wav",
                       "placed_s": placed.get(ln["id"]), "speech_s": round(
                           d["words"][-1][2] - d["words"][0][1], 3) if d["words"] else None,
                       "effective_wpm": wpm, "speed": d["speed"], "qa": probs})
        for p in probs:
            print(f"{ln['id']}: {p}")
    slug = vp.get("slug") or "vo"
    write_wav(os.path.join(vo, f"{slug}-vo.wav"), mix(done, placed, dur, rate), rate)
    wj = words_json(vp, done, placed, dur)
    with open(os.path.join(job, vp["outputs"].get("words") or f"{slug}-words.json"), "w",
              encoding="utf-8") as f:
        json.dump(wj, f, indent=1, ensure_ascii=False)
    with open(os.path.join(vo, "voice_report.json"), "w", encoding="utf-8") as f:
        json.dump({"voice_id": voice_id, "model_id": eng["model_id"], "calibrated": bool(calib),
                   "lines": report}, f, indent=1, ensure_ascii=False)
    print(f"wrote vo/{slug}-vo.wav, {vp['outputs'].get('words')}, vo/voice_report.json "
          f"({len(wj['words'])} words)")
    return 1 if bad else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Voice a voice_plan.json with Cartesia Sonic "
                                 "(SSE): per-line WAVs, the placed VO and words.json.")
    ap.add_argument("--job", required=True, help="job dir with voice_plan.json")
    ap.add_argument("--line", action="append", default=[], help="line id(s), e.g. L1 or L1,L6")
    ap.add_argument("--dry-run", action="store_true", help="print request JSON lines, no calls")
    ap.add_argument("--voice-id", default=None, help="overrides CARTESIA_VOICE_ID and the plan")
    ap.add_argument("--no-emotion", action="store_true",
                    help="drop emotion (use for voices without the Emotive tag)")
    ap.add_argument("--calibrate", action="store_true",
                    help="3 audition lines at speeds 0.9/1.0/1.1/1.2 -> vo/calibration.json")
    a = ap.parse_args(argv)
    vp = load(a.job)
    if vp.get("lane") == "real_voice" or vp.get("engine") is None:
        read_guide(vp)
        return 3
    voice_id = a.voice_id or os.environ.get("CARTESIA_VOICE_ID") or \
        (vp.get("voice") or {}).get("id")
    if vp.get("lane") == "creator_clone" and not (vp.get("voice") or {}).get("consent_ref"):
        die("creator_clone needs a consent_ref in the plan: never clone without consent", 3)
    key = os.environ.get("CARTESIA_API_KEY", "")
    if not a.dry_run:
        if not key:
            die("CARTESIA_API_KEY is not set (environment only; .env files are not read)")
        if not voice_id:
            sel = (vp.get("voice") or {}).get("selection") or {}
            die("no voice id: pick one (" + (sel.get("query") or "GET /voices") +
                ") and pass --voice-id or set CARTESIA_VOICE_ID")
    return run(a, vp, key, voice_id or "$CARTESIA_VOICE_ID")


if __name__ == "__main__":
    sys.exit(main())
