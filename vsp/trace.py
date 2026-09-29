"""trace.jsonl — one JSON object per line, every run (D153).

Shaped after the OpenTelemetry GenAI semantic conventions (status
"Development"; names pinned here so a later OTLP/Langfuse exporter can map
1:1 — labs-techniques §7.1):

  span   {"type": "span", "trace_id", "span_id", "parent_span_id", "name",
          "start", "end", "duration_ms", "status": "ok"|"error",
          "error.type"?, "error.message"?, "attributes": {...}}
  event  {"type": "event", "trace_id", "span_id", "name", "time",
          "attributes": {...}}
  eval   an event named "gen_ai.evaluation.result" whose attributes are
         gen_ai.evaluation.name / gen_ai.evaluation.score.label /
         gen_ai.evaluation.score.value / gen_ai.evaluation.explanation
         (one per gate check, rubric score, judge verdict ...)

    tr = Trace(os.path.join(outdir, "trace.jsonl"))
    with tr.span("stage.generate", candidates=8) as sp:
        ...
        sp.set(winner=3)
    tr.eval_result("D43", "fail", explanation="~4.1s speech in 3.0s window")
    tr.close()

Records are buffered and written on flush()/close() (the first write
truncates the file, later writes append). Stdlib only; never raises from
tracing calls into the pipeline (bad attribute values are str()-ed).
"""
import datetime as _dt
import json
import os
import secrets
import time

EVAL_EVENT = "gen_ai.evaluation.result"
EVAL_NAME = "gen_ai.evaluation.name"
EVAL_LABEL = "gen_ai.evaluation.score.label"
EVAL_VALUE = "gen_ai.evaluation.score.value"
EVAL_EXPLANATION = "gen_ai.evaluation.explanation"


def _now_iso():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _clean(attrs):
    out = {}
    for k, v in (attrs or {}).items():
        if v is None or isinstance(v, (bool, int, float, str)):
            out[str(k)] = v
        elif isinstance(v, (list, tuple)):
            out[str(k)] = [x if isinstance(x, (bool, int, float, str)) or x is None
                           else str(x) for x in v]
        elif isinstance(v, dict):
            out[str(k)] = json.loads(json.dumps(v, default=str))
        else:
            out[str(k)] = str(v)
    return out


class Span:
    """Context manager returned by Trace.span(). Status is "ok" unless the
    block raised (then "error" + error.type/error.message; the exception
    propagates — tracing never swallows pipeline errors)."""

    def __init__(self, trace, name, attrs):
        self.trace = trace
        self.name = name
        self.attributes = _clean(attrs)
        self.span_id = secrets.token_hex(8)
        self.parent_span_id = None
        self.start = None
        self._t0 = None
        self.status = "ok"
        self.error = None
        self.ended = False

    def set(self, **attrs):
        self.attributes.update(_clean(attrs))
        return self

    def set_attribute(self, key, value):
        return self.set(**{key: value})

    def __enter__(self):
        self.parent_span_id = self.trace._stack[-1].span_id if self.trace._stack else None
        self.start = _now_iso()
        self._t0 = time.perf_counter()
        self.trace._stack.append(self)
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.status = "error"
            self.error = (exc_type.__name__, str(exc)[:500])
        self.end()
        return False

    def end(self, status=None):
        if self.ended:
            return
        self.ended = True
        if status:
            self.status = status
        if self in self.trace._stack:
            # pop this span (and anything left open above it)
            while self.trace._stack:
                top = self.trace._stack.pop()
                if top is self:
                    break
        rec = {"type": "span", "trace_id": self.trace.trace_id,
               "span_id": self.span_id, "parent_span_id": self.parent_span_id,
               "name": self.name, "start": self.start or _now_iso(), "end": _now_iso(),
               "duration_ms": round((time.perf_counter() - (self._t0 or time.perf_counter()))
                                    * 1000.0, 3),
               "status": self.status, "attributes": self.attributes}
        if self.error:
            rec["error.type"], rec["error.message"] = self.error
        self.trace._emit(rec)


class Trace:
    def __init__(self, path=None, trace_id=None, **resource):
        self.path = path
        self.trace_id = trace_id or secrets.token_hex(16)
        self.resource = _clean(resource) if resource else {}
        self.pending = []
        self.records = []          # everything emitted (kept for summaries)
        self._stack = []
        self._written = False
        self.closed = False

    # ------------------------------------------------------------ api
    def span(self, name, **attrs):
        return Span(self, name, attrs)

    def event(self, name, **attrs):
        sp = self._stack[-1].span_id if self._stack else None
        rec = {"type": "event", "trace_id": self.trace_id, "span_id": sp,
               "name": name, "time": _now_iso(), "attributes": _clean(attrs)}
        self._emit(rec)
        return rec

    def eval_result(self, name, label, score=None, explanation=None, **attrs):
        """One OTel GenAI evaluation-result event (a gate check, a rubric
        score, an LLM-judge verdict ...)."""
        a = {EVAL_NAME: str(name), EVAL_LABEL: None if label is None else str(label)}
        if score is not None:
            try:
                a[EVAL_VALUE] = float(score)
            except (TypeError, ValueError):
                a[EVAL_VALUE] = None
        if explanation is not None:
            a[EVAL_EXPLANATION] = str(explanation)[:2000]
        a.update(attrs)
        return self.event(EVAL_EVENT, **a)

    def gate_results(self, stage, messages, rules=None):
        """Convenience: one eval_result per failing gate message plus a
        stage-level pass/fail result. `rules` maps message -> rule id."""
        import re
        msgs = list(messages or [])
        for m in msgs:
            text = m.get("message", str(m)) if isinstance(m, dict) else str(m)
            rid = (m.get("rule") if isinstance(m, dict) else None) or \
                (rules or {}).get(text) or \
                (re.match(r"\s*(D\d+[a-z]?|B4a)\b", text) or [None, None])[1] or "legacy"
            self.eval_result(rid, "fail", explanation=text, **{"vsp.stage": stage})
        self.eval_result(stage, "pass" if not msgs else "fail",
                         score=float(len(msgs)),
                         explanation=f"{len(msgs)} failure(s)", **{"vsp.stage": stage})

    def timings_ms(self, top_level_only=True):
        """{span name: total duration_ms} — feeds manifest["timings_ms"]."""
        out = {}
        for r in self.records:
            if r["type"] != "span" or (top_level_only and r["parent_span_id"]):
                continue
            out[r["name"]] = round(out.get(r["name"], 0.0) + r["duration_ms"], 3)
        return out

    # --------------------------------------------------------- output
    def _emit(self, rec):
        self.pending.append(rec)
        self.records.append(rec)

    def flush(self):
        """Write pending records. The first write truncates the file (and
        leads with a {"type": "resource"} line when resource attrs were
        given); an empty trace still creates the file (D153: every run)."""
        if not self.path:
            self.pending = []
            return None
        if self._written and not self.pending:
            return self.path
        d = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(d, exist_ok=True)
        with open(self.path, "a" if self._written else "w", encoding="utf-8") as f:
            if not self._written and self.resource:
                f.write(json.dumps({"type": "resource", "trace_id": self.trace_id,
                                    "attributes": self.resource},
                                   ensure_ascii=False, default=str) + "\n")
            for rec in self.pending:
                f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        self._written = True
        self.pending = []
        return self.path

    def close(self):
        """End any span left open (status "error", unfinished=true), flush."""
        if self.closed:
            return self.path
        while self._stack:
            sp = self._stack[-1]
            sp.set(unfinished=True)
            sp.end(status="error")
        self.closed = True
        return self.flush()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


def read(path):
    """Parse a trace.jsonl back into a list of records."""
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]
