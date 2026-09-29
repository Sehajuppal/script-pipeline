"""Optional first-seconds transcription with Muse Voice Transcribe
(docs/research/agent-runtime.md §B3/§C3) — OFF unless configured.

    status(cfg=None, env=None) -> {"enabled", "key_env", "ffmpeg", "ready",
                                   "reason"}
    extract_clip(src, dst, seconds=3.5, runner=None) -> dst
        ffmpeg: first `seconds` of `src` -> WAV, mono, 16-bit PCM, 16 kHz
    transcribe_wav(wav_bytes, key, session_id, transport=None, ...) -> dict
        multipart POST https://api.meta.ai/v1/asr/transcribe?sessionId=...
        parts: `request` (application/json) {"mode": "ENDPOINTING", "model":
        "muse-voice-transcribe-1.0", "audioEncoding": "WAV"[, "keywords"]}
        and `audio` (audio/wav)
    transcribe_source(src, media_id, key, ...) -> {"text", "hook",
        "session_id", "audio_ms"}          temp WAV always deleted
    run(con, candidates, cfg=None, env=None, ...) -> report
        candidates: [(media_id, src, kind)] with kind "media_url" (a URL the
        Graph API returned in THIS run — held in memory only) or
        "own_render" (a local render of one of YOUR reels, is_own=1)
    own_render_candidates(con, limit=20) -> candidates for linked own reels
        (video files next to the linked manifest.json)

What may be processed: only your own renders, or items whose media_url the
API returned (licensed-music reels have none; their caption stays the hook
source). Nothing else is ever downloaded. What is kept: the transcript TEXT
(reels.transcript, capped) and a hook line from the first turn
(hook_source 'asr' / 'own_render'); the audio clip is deleted in a finally
block, and media / media_url are never stored.

Enabling: config/ingest.json "transcribe": {"enabled": true} (or env
VSP_TRANSCRIBE=1; VSP_TRANSCRIBE=0 forces it off), an API key in
VSP_ASR_API_KEY (falls back to VSP_LLM_API_KEY; Hermes strips MODEL_API_KEY,
so it is not read), and ffmpeg on PATH (or VSP_FFMPEG). Anything missing ->
a graceful no-op with the reason in the report. VSP_ASR_URL overrides the
endpoint (proxies / tests). Every HTTP call goes through the injectable
`transport(method, url, headers, body, timeout) -> Response` (the same
contract as vsp.ingest.graph); ffmpeg runs through an injectable `runner`.
"""
import json
import os
import random
import re
import secrets
import shutil
import subprocess
import tempfile
import time
import wave

from vsp.ingest.util import clean_text, hook_from_transcript

ASR_URL = "https://api.meta.ai/v1/asr/transcribe"
MODEL = "muse-voice-transcribe-1.0"
ENV_KEY, ENV_KEY_FALLBACK = "VSP_ASR_API_KEY", "VSP_LLM_API_KEY"
SAMPLE_RATE, CHANNELS, SAMPLE_WIDTH = 16000, 1, 2
MAX_WAV_BYTES = 32 * 1024 * 1024          # API limit per request
TRANSCRIPT_MAX = 4000
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".webm", ".mkv")
_TRUE, _FALSE = ("1", "true", "yes", "on"), ("0", "false", "no", "off")


class TranscribeError(RuntimeError):
    pass


# ------------------------------------------------------------------ config
def api_key(env=None):
    """-> (key, env var name) or (None, None)."""
    e = os.environ if env is None else env
    for name in (ENV_KEY, ENV_KEY_FALLBACK):
        v = (e.get(name) or "").strip()
        if v:
            return v, name
    return None, None


def ffmpeg_path(env=None):
    e = os.environ if env is None else env
    p = (e.get("VSP_FFMPEG") or "").strip()
    if p:
        return p if os.path.isfile(p) and os.access(p, os.X_OK) else None
    return shutil.which("ffmpeg")


def enabled(cfg=None, env=None):
    e = os.environ if env is None else env
    flag = str(e.get("VSP_TRANSCRIBE", "")).strip().lower()
    if flag in _TRUE:
        return True
    if flag in _FALSE:
        return False
    return bool(((cfg or {}).get("transcribe") or {}).get("enabled"))


def settings(cfg=None):
    t = dict((cfg or {}).get("transcribe") or {})
    return {"seconds": float(t.get("seconds", 3.5) or 3.5),
            "max_per_run": int(t.get("max_per_run", 20) or 0),
            "keywords": [str(k)[:50] for k in (t.get("keywords") or [])][:20],
            "language": t.get("language") or None,
            "sources": list(t.get("sources") or ("own_render", "media_url"))}


def status(cfg=None, env=None, ffmpeg=None):
    """Why transcription would (not) run — no I/O besides PATH lookup."""
    on = enabled(cfg, env)
    key, key_env = api_key(env)
    ff = ffmpeg if ffmpeg is not None else ffmpeg_path(env)
    reason = None
    if not on:
        reason = ('disabled (set "transcribe": {"enabled": true} in '
                  'config/ingest.json or VSP_TRANSCRIBE=1)')
    elif not key:
        reason = f"no API key ({ENV_KEY}, falling back to {ENV_KEY_FALLBACK})"
    elif not ff:
        reason = "ffmpeg not found (install it or set VSP_FFMPEG)"
    return {"enabled": on, "key_env": key_env, "ffmpeg": ff or None,
            "ready": reason is None, "reason": reason}


# ------------------------------------------------------------------ ffmpeg
def _default_runner(cmd, timeout):
    return subprocess.run(cmd, capture_output=True, timeout=timeout)


def ffmpeg_cmd(src, dst, seconds=3.5, ffmpeg="ffmpeg"):
    """`-t` before `-i` limits what is READ from the input (a URL is only
    partially fetched)."""
    return [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            "-t", f"{float(seconds):g}", "-i", src, "-vn",
            "-ac", str(CHANNELS), "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le",
            "-map_metadata", "-1", "-f", "wav", dst]


def check_wav(path):
    """-> duration ms; TranscribeError unless mono 16-bit PCM 16 kHz."""
    try:
        with wave.open(path, "rb") as w:
            ch, sw, fr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), \
                w.getnframes()
    except (OSError, EOFError, wave.Error) as e:
        raise TranscribeError(f"ffmpeg output is not a WAV file: {e}")
    if (ch, sw, fr) != (CHANNELS, SAMPLE_WIDTH, SAMPLE_RATE):
        raise TranscribeError(f"WAV must be mono 16-bit 16 kHz, got {ch} ch, "
                              f"{8 * sw}-bit, {fr} Hz")
    if os.path.getsize(path) > MAX_WAV_BYTES:
        raise TranscribeError("WAV exceeds the 32 MB request limit")
    return int(round(1000.0 * n / fr)) if fr else 0


def extract_clip(src, dst, seconds=3.5, runner=None, ffmpeg=None, timeout=90):
    runner = runner or _default_runner
    cmd = ffmpeg_cmd(src, dst, seconds, ffmpeg or ffmpeg_path() or "ffmpeg")
    try:
        r = runner(cmd, timeout)
    except (OSError, subprocess.SubprocessError) as e:
        raise TranscribeError(f"ffmpeg failed to run: {type(e).__name__}")
    if getattr(r, "returncode", 1) != 0 or not os.path.isfile(dst):
        err = getattr(r, "stderr", b"") or b""
        if isinstance(err, bytes):
            err = err.decode("utf-8", "replace")
        # never echo the source (a signed CDN URL) back into logs
        err = re.sub(r"https?://\S+", "<url>", err)
        raise TranscribeError(f"ffmpeg exit {getattr(r, 'returncode', '?')}: "
                              f"{' '.join(err.split())[-200:]}")
    return dst


# ------------------------------------------------------------------ HTTP
def multipart(parts, boundary=None):
    """parts: [(name, filename | None, content_type, bytes)] ->
    (body, content_type header)."""
    b = boundary or ("vsp" + secrets.token_hex(12))
    out = []
    for name, filename, ctype, data in parts:
        disp = f'Content-Disposition: form-data; name="{name}"'
        if filename:
            disp += f'; filename="{filename}"'
        out += [f"--{b}\r\n{disp}\r\nContent-Type: {ctype}\r\n\r\n".encode("utf-8"),
                data, b"\r\n"]
    out.append(f"--{b}--\r\n".encode("utf-8"))
    return b"".join(out), f"multipart/form-data; boundary={b}"


def request_json(keywords=None, language=None):
    req = {"mode": "ENDPOINTING", "model": MODEL, "audioEncoding": "WAV"}
    if keywords:
        req["keywords"] = list(keywords)
    if language:
        req["languageBias"] = language
    return req


def session_id(media_id):
    base = re.sub(r"[^A-Za-z0-9_-]", "", str(media_id or "x"))[:40] or "x"
    return f"vsp-{base}-{secrets.token_hex(4)}"


def _endpoint(env=None):
    e = os.environ if env is None else env
    return (e.get("VSP_ASR_URL") or "").strip() or ASR_URL


def transcribe_wav(wav_bytes, key, sid, transport=None, keywords=None, language=None,
                   env=None, timeout=90.0, max_retries=2, sleep=None, rng=None):
    """POST one WAV -> parsed JSON dict. Retries 429/5xx with jitter
    (Retry-After honoured). Errors never contain the key."""
    if not key:
        raise TranscribeError("no API key")
    from vsp.ingest.graph import TransportError, urllib_transport
    transport = transport or urllib_transport
    sleep = sleep or time.sleep
    rng = rng or random.Random()
    body, ctype = multipart([
        ("request", None, "application/json",
         json.dumps(request_json(keywords, language)).encode("utf-8")),
        ("audio", "clip.wav", "audio/wav", wav_bytes)])
    url = _endpoint(env) + "?" + "sessionId=" + sid
    headers = {"Authorization": f"Bearer {key}", "Content-Type": ctype,
               "Accept": "application/json", "User-Agent": "vsp-ingest/1"}
    attempt = 0
    while True:
        try:
            resp = transport("POST", url, headers, body, timeout)
        except TransportError as e:
            if attempt < max_retries:
                sleep(rng.uniform(0, 2.0 * 2 ** attempt))
                attempt += 1
                continue
            raise TranscribeError(f"network error: {str(e).split(':')[0]}")
        status = int(resp.status)
        try:
            data = json.loads((resp.body or b"{}").decode("utf-8") or "{}")
        except (UnicodeDecodeError, ValueError):
            data = None
        if 200 <= status < 300 and isinstance(data, dict):
            return data
        if (status == 429 or status >= 500) and attempt < max_retries:
            ra = (resp.headers or {}).get("retry-after")
            try:
                delay = min(60.0, float(ra)) if ra else rng.uniform(0, 2.0 * 2 ** attempt)
            except ValueError:
                delay = rng.uniform(0, 2.0 * 2 ** attempt)
            sleep(delay)
            attempt += 1
            continue
        msg = ""
        if isinstance(data, dict):
            err = data.get("error")
            msg = (err.get("message") if isinstance(err, dict) else err) or \
                data.get("message") or ""
        hint = {401: "check VSP_ASR_API_KEY", 403: "key lacks ASR access",
                413: "clip too large"}.get(status, "")
        raise TranscribeError(f"ASR HTTP {status}"
                              + (f": {clean_text(str(msg), limit=160)}" if msg else "")
                              + (f" ({hint})" if hint else ""))


def parse_result(data):
    """-> (full transcript text, first-turn text)."""
    turns = [t for t in (data or {}).get("turns") or [] if isinstance(t, dict)]
    full = (data or {}).get("transcript")
    if not isinstance(full, str) or not full.strip():
        full = " ".join(str(t.get("transcript") or "") for t in turns)
    first = next((str(t.get("transcript")) for t in turns
                  if isinstance(t.get("transcript"), str) and t["transcript"].strip()),
                 full)
    return clean_text(full, limit=TRANSCRIPT_MAX) or "", clean_text(first) or ""


def transcribe_source(src, media_id, key, transport=None, runner=None, seconds=3.5,
                      keywords=None, language=None, env=None, sleep=None, ffmpeg=None):
    """Clip -> ASR -> text. The temp directory (the only copy of the audio)
    is removed whatever happens."""
    tmp = tempfile.mkdtemp(prefix="vsp_asr_")
    try:
        wav = extract_clip(src, os.path.join(tmp, "clip.wav"), seconds, runner=runner,
                           ffmpeg=ffmpeg)
        audio_ms = check_wav(wav)
        with open(wav, "rb") as f:
            data = f.read()
        sid = session_id(media_id)
        res = transcribe_wav(data, key, sid, transport=transport, keywords=keywords,
                             language=language, env=env, sleep=sleep)
        text, first = parse_result(res)
        return {"text": text, "hook": hook_from_transcript(first) if first else None,
                "session_id": sid, "audio_ms": audio_ms,
                "api_audio_ms": res.get("audioDurationMs"), "tmp": tmp}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------- run
def own_render_candidates(con, limit=20):
    """[(media_id, path, 'own_render')] for linked own reels without a
    transcript: the newest video file next to the linked manifest."""
    out = []
    try:
        rows = con.execute(
            "SELECT p.media_id, p.manifest_path FROM posts p JOIN reels r ON "
            "r.media_id = p.media_id AND r.platform = 'instagram' WHERE r.is_own = 1 "
            "AND r.transcript IS NULL AND p.manifest_path IS NOT NULL "
            "ORDER BY p.posted_at DESC").fetchall()
    except Exception:  # noqa: BLE001 — posts table absent on a legacy DB
        return out
    for mid, mpath in rows:
        d = os.path.dirname(os.path.abspath(mpath))
        try:
            vids = [os.path.join(d, f) for f in os.listdir(d)
                    if f.lower().endswith(VIDEO_EXT)]
        except OSError:
            continue
        if vids:
            out.append((mid, max(vids, key=os.path.getmtime), "own_render"))
        if len(out) >= limit:
            break
    return out


def _allowed(con, media_id, src, kind):
    row = con.execute("SELECT is_own, transcript FROM reels WHERE media_id=?",
                      (media_id,)).fetchone()
    if row is None:
        return "unknown media id"
    if row[1] is not None:
        return "already transcribed"
    if kind == "own_render":
        if not row[0]:
            return "own_render for a reel that is not yours"
        if not os.path.isfile(src):
            return "render file not found"
        return None
    if kind == "media_url":
        if not re.match(r"^https://", str(src or "")):
            return "media_url must be an https URL returned by the API"
        return None
    return f"unsupported source kind {kind!r}"


def run(con, candidates, cfg=None, env=None, transport=None, runner=None, sleep=None,
        log=None, ffmpeg=None):
    """Transcribe permitted candidates; store text + hook. -> report."""
    log = log or (lambda msg: None)
    st = status(cfg, env, ffmpeg=ffmpeg)
    rep = {"candidates": len(candidates or []), "transcribed": 0, "no_speech": 0,
           "errors": [], "skipped": {}, "status": st, "sessions": []}
    if not candidates:
        return rep
    if not st["ready"]:
        rep["skipped"]["not ready: " + st["reason"]] = len(candidates)
        return rep
    s = settings(cfg)
    key, _ = api_key(env)
    done = 0
    for media_id, src, kind in candidates:
        if kind not in s["sources"]:
            rep["skipped"][f"{kind} not in transcribe.sources"] = \
                rep["skipped"].get(f"{kind} not in transcribe.sources", 0) + 1
            continue
        why = _allowed(con, media_id, src, kind)
        if why:
            rep["skipped"][why] = rep["skipped"].get(why, 0) + 1
            continue
        if done >= s["max_per_run"]:
            rep["skipped"]["max_per_run reached"] = \
                rep["skipped"].get("max_per_run reached", 0) + 1
            continue
        done += 1
        try:
            res = transcribe_source(src, media_id, key, transport=transport,
                                    runner=runner, seconds=s["seconds"],
                                    keywords=s["keywords"], language=s["language"],
                                    env=env, sleep=sleep, ffmpeg=st["ffmpeg"])
        except TranscribeError as e:
            rep["errors"].append(f"{media_id}: {e}")
            log(f"transcribe {media_id}: {e}")
            continue
        rep["sessions"].append(res["session_id"])
        if not res["text"]:
            rep["no_speech"] += 1
            con.execute("UPDATE reels SET transcript='' WHERE media_id=?", (media_id,))
            continue
        hook_src = "own_render" if kind == "own_render" else "asr"
        cur = con.execute("SELECT hook_source FROM reels WHERE media_id=?",
                          (media_id,)).fetchone()
        curated = bool(cur and cur[0] == "curated")    # the research agent's line wins
        if res["hook"] and not curated:
            con.execute(
                "UPDATE reels SET transcript=?, hook_text=?, hook_source=?, "
                "hook_category=NULL, hook_family=NULL, classified_by=NULL, "
                "pattern_id=CASE WHEN classified_by IS NOT NULL THEN NULL "
                "ELSE pattern_id END WHERE media_id=?",
                (res["text"], res["hook"], hook_src, media_id))
        else:
            con.execute("UPDATE reels SET transcript=? WHERE media_id=?",
                        (res["text"], media_id))
        rep["transcribed"] += 1
    con.commit()
    return rep
