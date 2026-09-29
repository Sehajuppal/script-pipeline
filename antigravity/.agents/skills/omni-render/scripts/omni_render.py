#!/usr/bin/env python3
"""omni_render.py - render the generated shots of a render.json with Gemini
Omni (Interactions API). Stdlib only, Python 3.9+.

  omni_render.py --job jobs/<slug> --validate
  omni_render.py --job jobs/<slug> --pass draft [--shot 2 --shot 3a] [--dry-run]
  omni_render.py --job jobs/<slug> --pass final
  omni_render.py --job jobs/<slug> --shot 3a --edit "Make the glow warmer."
  omni_render.py --job jobs/<slug> --shot 3a --use-fallback

Reads DIR/render.json and DIR/refs/<ref id>.{png,jpg,jpeg,webp,heic,heif};
writes DIR/clips/shot-<n>-<pass>-a<attempt>.mp4 and appends one line per call
to DIR/render_log.jsonl (interaction id, model, seed, duration, cost, status).
The key comes from GEMINI_API_KEY in the environment only (never a .env
file). --dry-run and --validate are offline and need no key.
"""
import argparse
import base64
import datetime
import json
import os
import re
import shutil
import socket
import sys
import time
import urllib.error
import urllib.request

API = "https://generativelanguage.googleapis.com/v1beta"
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".webp": "image/webp", ".heic": "image/heic", ".heif": "image/heif"}
PER_S = {"360p": 0.034, "720p": 0.101, "1080p": 0.152, "4k": 0.304}
MAX_IMAGE_BYTES = 20 * 1024 * 1024
BACKOFF_S = (5, 15, 45, 90)
POLL_S, POLL_MAX_S = 10, 1800
TIMEOUT_S = 900


class ApiError(Exception):
    def __init__(self, code, msg):
        Exception.__init__(self, f"HTTP {code}: {msg}")
        self.code, self.msg = code, msg


def die(msg, code=1):
    print(f"omni_render: {msg}", file=sys.stderr)
    sys.exit(code)


def load_job(job):
    path = os.path.join(job, "render.json")
    try:
        with open(path, encoding="utf-8") as f:
            r = json.load(f)
    except (OSError, ValueError) as e:
        die(f"cannot read {path}: {e}", 2)
    if r.get("schema_version") != 1 or not isinstance(r.get("shots"), list):
        die(f"{path} is not a schema_version 1 render.json", 2)
    return r


def ref_file(job, ref):
    for ext in MIME:
        p = os.path.join(job, "refs", ref + ext)
        if os.path.isfile(p):
            return p
    return None


def read_log(job):
    out = []
    try:
        with open(os.path.join(job, "render_log.jsonl"), encoding="utf-8") as f:
            for ln in f:
                if ln.strip():
                    try:
                        out.append(json.loads(ln))
                    except ValueError:
                        pass
    except OSError:
        pass
    return out


def append_log(job, entry):
    with open(os.path.join(job, "render_log.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def generated(r):
    return [s for s in r["shots"] if s.get("gen_duration_s")]


def select(r, wanted):
    shots = generated(r)
    if not wanted:
        return shots
    keys = [w.strip() for x in wanted for w in x.split(",") if w.strip()]
    by_n = {str(s["n"]): s for s in r["shots"]}
    missing = [k for k in keys if k not in by_n]
    if missing:
        die(f"no shot(s) {', '.join(missing)} in render.json", 2)
    out = [by_n[k] for k in keys]
    bad = [str(s["n"]) for s in out if not s.get("gen_duration_s")]
    if bad:
        die(f"shot(s) {', '.join(bad)} are not generated (mode real/edit/reuse of real): "
            "film or edit them, never generate", 2)
    return out


def spent(log):
    return round(sum(float(e.get("cost_usd_est") or 0) for e in log
                     if e.get("status") == "ok"), 4)


def attempts(log, n, pas):
    return sum(1 for e in log if str(e.get("shot")) == str(n) and e.get("pass") == pas
               and e.get("status") in ("ok", "failed"))


def last_ok(log, n, pas):
    ok = [e for e in log if str(e.get("shot")) == str(n) and e.get("pass") == pas
          and e.get("status") == "ok" and e.get("interaction_id")]
    return ok[-1] if ok else None


# ------------------------------------------------------------ requests
def images_for(job, inputs, full, missing):
    """Distinct input refs in order -> Interactions image items."""
    items, seen = [], []
    for it in inputs or []:
        ref = it.get("ref")
        if ref in seen:
            continue
        seen.append(ref)
        path = ref_file(job, ref)
        if path is None:
            missing.append(ref)
            items.append({"type": "image", "data": f"<missing refs/{ref}.png>",
                          "mime_type": "image/png"})
            continue
        mime = MIME[os.path.splitext(path)[1].lower()]
        if full:
            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode("ascii")
        else:
            data = f"<base64 {os.path.getsize(path)} bytes of {os.path.relpath(path, job)}>"
        items.append({"type": "image", "data": data, "mime_type": mime})
    return items


def clip_seconds(shot, variant):
    """Clip length in whole seconds (the fallback may differ from the shot)."""
    fb = shot.get("ai_fallback") or {}
    if variant == "fallback" and fb.get("gen_duration_s"):
        return int(fb["gen_duration_s"])
    return int(shot["gen_duration_s"])


def body_for(job, r, shot, pas, variant, seed, edit=None, prev_id=None, full=True,
             missing=None, background=False):
    """One Interactions request body (research §1.10 shape)."""
    cfg = r["passes"][pas]
    src = shot["ai_fallback"] if variant == "fallback" else shot
    rf = {"type": "video", "aspect_ratio": r["format"]["aspect_ratio"],
          "resolution": cfg["resolution"], "delivery": cfg.get("delivery", "inline")}
    if edit:
        text = edit.strip()
        if "keep everything else the same" not in text.lower():
            text = text.rstrip(". ") + ". Keep everything else the same."
        body = {"model": r["model"]["id"], "previous_interaction_id": prev_id,
                "input": [{"type": "text", "text": text}], "response_format": rf,
                "generation_config": {"video_config": {"task": "edit"}},
                "store": bool(cfg.get("store", True))}
    else:
        rf["duration"] = f"{clip_seconds(shot, variant)}s"
        items = images_for(job, src.get("inputs"), full, missing if missing is not None else [])
        gc = {"video_config": {"task": src["task"]}}
        if seed is not None:
            gc["seed"] = int(seed)
        body = {"model": r["model"]["id"], "input": items + [{"type": "text", "text": src["prompt"]}],
                "response_format": rf, "generation_config": gc,
                "store": bool(cfg.get("store", True))}
    if background:
        body["background"] = True
        body["store"] = True
    return body


def http(method, url, key, body=None, timeout=TIMEOUT_S, raw=False):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"x-goog-api-key": key,
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read()
    except urllib.error.HTTPError as e:
        raise ApiError(e.code, e.read().decode("utf-8", "replace")[:2000])
    return payload if raw else json.loads(payload.decode("utf-8"))


def post_retry(url, key, body, note):
    """POST with backoff on 429/5xx/network errors; once without the seed
    when the API rejects it (Omni seed support is unverified). The seed
    retry does not use up a backoff step."""
    k = 0
    while True:
        try:
            return http("POST", url, key, body)
        except ApiError as e:
            gc = body.get("generation_config") or {}
            if e.code == 400 and "seed" in gc and "seed" in e.msg.lower():
                gc.pop("seed")
                note["seed_dropped"] = True
                print("  seed rejected: retrying once without it", file=sys.stderr)
                continue
            if (e.code == 429 or e.code >= 500) and k < len(BACKOFF_S):
                print(f"  HTTP {e.code}; retry in {BACKOFF_S[k]} s", file=sys.stderr)
                time.sleep(BACKOFF_S[k])
                k += 1
                continue
            raise
        except (urllib.error.URLError, socket.timeout, ConnectionError) as e:
            if k < len(BACKOFF_S):
                print(f"  network error {e}; retry in {BACKOFF_S[k]} s", file=sys.stderr)
                time.sleep(BACKOFF_S[k])
                k += 1
                continue
            raise ApiError(0, str(e))


def poll_interaction(iid, key):
    t0 = time.time()
    while time.time() - t0 < POLL_MAX_S:
        resp = http("GET", f"{API}/interactions/{iid}", key)
        st = str(resp.get("status") or "").lower()
        if st in ("completed", "failed", "cancelled", "canceled", "incomplete"):
            return resp
        time.sleep(POLL_S)
    raise ApiError(0, f"interaction {iid} still running after {POLL_MAX_S} s")


def find_video(resp):
    """steps[] -> model_output -> content video (data or uri); tolerant of an
    SDK-style output_video field."""
    for step in resp.get("steps") or []:
        if step.get("type") == "model_output":
            for c in step.get("content") or []:
                if c.get("type") == "video" and (c.get("data") or c.get("uri")):
                    return c
    ov = resp.get("output_video")
    if isinstance(ov, dict) and (ov.get("data") or ov.get("uri")):
        return ov
    return None


def download(uri, key, dest):
    """Files API URI -> wait until ACTIVE -> download with the key."""
    m = re.search(r"files/([^/:?]+)", uri)
    if m:
        t0 = time.time()
        while time.time() - t0 < POLL_MAX_S:
            try:
                meta = http("GET", f"{API}/files/{m.group(1)}", key)
            except ApiError:
                break
            st = str(meta.get("state") or "ACTIVE").upper()
            if st == "ACTIVE":
                break
            if st == "FAILED":
                raise ApiError(0, f"file {m.group(1)} FAILED")
            time.sleep(5)
    url = uri if uri.startswith("http") else f"{API}/{uri.lstrip('/')}"
    if ":download" not in url and m:
        url = f"{API}/files/{m.group(1)}:download?alt=media"
    if ":download" in url and "alt=media" not in url:
        url += ("&" if "?" in url else "?") + "alt=media"
    req = urllib.request.Request(url, headers={"x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp, open(dest, "wb") as f:
        shutil.copyfileobj(resp, f)


# ------------------------------------------------------------ validate
def validate(job, r, need_key):
    errs, warns = [], []
    ref_ids = {x.get("id"): x for x in r.get("refs") or []}
    for s in generated(r):
        n = s["n"]
        if not s.get("prompt") or s.get("task") not in ("text_to_video", "image_to_video",
                                                          "reference_to_video"):
            errs.append(f"shot {n}: prompt or task missing")
        g = s.get("gen_duration_s")
        if not isinstance(g, int) or not 3 <= g <= 10:
            errs.append(f"shot {n}: gen_duration_s {g!r} is not an integer 3-10")
        for src, ins in (("", s.get("inputs")), ("fallback ", (s.get("ai_fallback") or {}).get("inputs"))):
            for it in ins or []:
                ref = it.get("ref")
                if ref not in ref_ids:
                    errs.append(f"shot {n}: {src}input {ref} not in refs[]")
                    continue
                p = ref_file(job, ref)
                if p is None:
                    (warns if src else errs).append(f"shot {n}: {src}ref {ref} missing: "
                                                    f"{ref_ids[ref].get('how', '')[:120]}")
                elif os.path.getsize(p) > MAX_IMAGE_BYTES:
                    errs.append(f"{p}: larger than 20 MB")
    for x in r.get("refs") or []:
        if x.get("kind") == "presenter" and not x.get("synthetic"):
            errs.append("the presenter sheet must be a synthetic adult, never a real person")
    real = [s["n"] for s in r["shots"] if s.get("mode") == "real"]
    if need_key and not os.environ.get("GEMINI_API_KEY"):
        errs.append("GEMINI_API_KEY is not set in the environment")
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            warns.append(f"{tool} not on PATH (assemble and QA need it)")
    if r.get("audio", {}).get("vo_source") == "cartesia" and \
            not os.path.isfile(os.path.join(job, "voice_plan.json")):
        warns.append("voice_plan.json missing: the VO comes first")
    b = r.get("budget_usd") or {}
    print(f"job {r.get('slug')}: {len(generated(r))} Omni clip(s), "
          f"{b.get('generated_s')} s; estimate ${b.get('estimate')} (draft ${b.get('draft')} "
          f"+ final ${b.get('final')}), cap ${b.get('cap')}; film for real: "
          f"{', '.join(real) or 'none'}")
    for w in warns:
        print(f"WARN {w}")
    for e in errs:
        print(f"ERROR {e}")
    print("validate: " + ("ok" if not errs else f"{len(errs)} error(s)"))
    return not errs


# ------------------------------------------------------------ main
def now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def run_shot(job, r, shot, a, key, log):
    pas = a.pass_
    n = str(shot["n"])
    variant = "edit" if a.edit else ("fallback" if a.use_fallback else "primary")
    cfg = r["passes"][pas]
    k = attempts(log, n, pas) + 1
    if not a.dry_run and not a.edit and last_ok(log, n, pas) and not a.redo and variant == "primary":
        print(f"shot {n}: {pas} clip exists (use --redo for another take)")
        return True
    if not a.dry_run and k > int(cfg.get("max_attempts", 3)) and not a.force:
        print(f"shot {n}: {pas} attempts used up ({k - 1}); use --use-fallback or --force",
              file=sys.stderr)
        return False
    gen = clip_seconds(shot, variant)
    cost = round(gen * PER_S[cfg["resolution"]], 4)
    cap = float((r.get("budget_usd") or {}).get("cap") or 0)
    if not a.dry_run and cap and spent(log) + cost > cap + 1e-9 and not a.force_budget:
        print(f"shot {n}: budget cap ${cap} would be exceeded (spent ${spent(log)}); stop and "
              "report, or --force-budget", file=sys.stderr)
        return False
    prev = last_ok(log, n, pas) if a.edit else None
    if a.edit and not prev and not a.dry_run:
        print(f"shot {n}: no {pas} interaction to edit yet", file=sys.stderr)
        return False
    missing = []
    body = body_for(job, r, shot, pas, variant, r.get("seed"), edit=a.edit,
                    prev_id=(prev or {}).get("interaction_id", "<previous_interaction_id>"),
                    full=a.full or not a.dry_run, missing=missing, background=a.background)
    url = f"{API}/interactions"
    if a.dry_run:
        print(json.dumps({"shot": n, "pass": pas, "attempt": k, "variant": variant,
                          "method": "POST", "url": url,
                          "headers": {"x-goog-api-key": "$GEMINI_API_KEY",
                                      "Content-Type": "application/json"},
                          "cost_usd_est": cost, "missing_refs": missing, "body": body},
                         ensure_ascii=False))
        return True
    if missing:
        print(f"shot {n}: missing refs {', '.join(missing)} (run --validate)", file=sys.stderr)
        return False
    os.makedirs(os.path.join(job, "clips"), exist_ok=True)
    dest = os.path.join(job, "clips", f"shot-{n}-{pas}-a{k}.mp4")
    note = {"seed_dropped": False}
    entry = {"ts": now(), "shot": n, "pass": pas, "attempt": k, "variant": variant,
             "model": r["model"]["id"], "resolution": cfg["resolution"], "duration_s": gen,
             "task": (body.get("generation_config") or {}).get("video_config", {}).get("task"),
             "previous_interaction_id": body.get("previous_interaction_id")}
    print(f"shot {n}: {pas} attempt {k} ({variant}, {gen} s at {cfg['resolution']}) ...")
    try:
        resp = post_retry(url, key, body, note)
        if body.get("background") and str(resp.get("status", "")).lower() != "completed":
            resp = poll_interaction(resp["id"], key)
        entry["interaction_id"] = resp.get("id")
        entry["usage"] = resp.get("usage")
        vid = find_video(resp)
        if vid is None:
            raise ApiError(0, f"no video in the response (status {resp.get('status')})")
        if vid.get("data"):
            with open(dest, "wb") as f:
                f.write(base64.b64decode(vid["data"]))
        else:
            download(vid["uri"], key, dest)
        entry.update(status="ok", file=os.path.relpath(dest, job), cost_usd_est=cost)
    except (ApiError, OSError, ValueError, KeyError) as e:
        entry.update(status="failed", error=str(e)[:600], cost_usd_est=0)
    gc = body.get("generation_config") or {}
    entry["seed"] = gc.get("seed")
    entry["seed_dropped"] = note["seed_dropped"]
    append_log(job, entry)
    print(f"shot {n}: {entry['status']}" + (f" -> {entry.get('file')}" if entry.get("file")
                                            else f": {entry.get('error')}"))
    return entry["status"] == "ok"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render render.json shots with Gemini Omni "
                                 "(Interactions API). Offline with --dry-run/--validate.")
    ap.add_argument("--job", required=True, help="job dir with render.json and refs/")
    ap.add_argument("--pass", dest="pass_", choices=("draft", "final"), default="draft")
    ap.add_argument("--shot", action="append", default=[], help="shot n (repeat or comma list)")
    ap.add_argument("--dry-run", action="store_true", help="print request JSON lines, no calls")
    ap.add_argument("--full", action="store_true", help="dry run: inline the real base64")
    ap.add_argument("--validate", action="store_true", help="pre-flight checks only")
    ap.add_argument("--edit", default=None, help="edit turn on the last ok take of --shot")
    ap.add_argument("--use-fallback", action="store_true", help="render the shot's ai_fallback")
    ap.add_argument("--redo", action="store_true", help="another take even if one is ok")
    ap.add_argument("--background", action="store_true", help="background: true, then poll")
    ap.add_argument("--force", action="store_true", help="ignore max_attempts")
    ap.add_argument("--force-budget", action="store_true", help="ignore the budget cap")
    a = ap.parse_args(argv)
    r = load_job(a.job)
    if a.validate:
        return 0 if validate(a.job, r, need_key=not a.dry_run) else 1
    if (a.edit or a.use_fallback) and len(a.shot) != 1:
        die("--edit and --use-fallback take exactly one --shot", 2)
    shots = select(r, a.shot)
    key = os.environ.get("GEMINI_API_KEY", "")
    if not a.dry_run and not key:
        die("GEMINI_API_KEY is not set (environment only; .env files are not read)", 2)
    log = read_log(a.job)
    ok = True
    for s in shots:
        ok = run_shot(a.job, r, s, a, key, log) and ok
        if not a.dry_run:
            log = read_log(a.job)
    if not a.dry_run:
        print(f"spent so far: ${spent(log)} of cap ${(r.get('budget_usd') or {}).get('cap')}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
