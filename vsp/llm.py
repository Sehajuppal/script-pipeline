"""Optional LLM layer — ADVISORY ONLY, never a gate (labs-techniques §3.2/§3.3).

Off unless configured. Stdlib urllib client. Providers:

  meta               Meta Model API (Muse Spark), OpenAI-compatible Chat
                     Completions: POST https://api.meta.ai/v1/chat/completions
                     Bearer key; body {model, messages,
                     max_completion_tokens (4000), reasoning_effort ("low")
                     [, response_format {type: json_schema, json_schema:
                     {name, schema}}]}. stop / n / logprobs / temperature are
                     never sent (Meta answers HTTP 400 on the first three and
                     wants temperature left at 1.0).
  openai-compatible  local Muse Glimmer or any OpenAI-compatible server (vLLM,
                     llama.cpp `llama-server --jinja`, Ollama):
                     POST {VSP_LLM_BASE_URL}/chat/completions, key optional,
                     body {model, messages, max_tokens [, response_format]}.
                     JSON-schema support on these servers is unverified, so a
                     400/422 on a schema request is retried once without
                     response_format (the prompt carries the schema).
  anthropic          POST https://api.anthropic.com/v1/messages
  openai             POST https://api.openai.com/v1/chat/completions
  mock               offline, deterministic (tests / --llm-judge dry runs)

Environment:
  VSP_LLM_PROVIDER   meta | openai-compatible | anthropic | openai | mock.
                     Unset: meta if a Meta key is present, then anthropic,
                     then openai. openai-compatible is never inferred.
  VSP_LLM_MODEL      required — no model name is hard-coded anywhere. Meta:
                     use a Standard-tier ID, e.g. muse-spark-1.3. IDs ending
                     in "-contributor" (muse-spark-1.3-contributor) print a
                     warning: Meta may train on contributor-tier traffic.
                     Local Glimmer: the served name, e.g. muse-glimmer.
  VSP_LLM_API_KEY    neutral key name, read FIRST by every provider: Hermes
                     Agent strips MODEL_API_KEY / META_API_KEY / OPENAI_API_KEY
                     (and GH_TOKEN) from every command it runs.
  MODEL_API_KEY, META_API_KEY   Meta key fallbacks, in that order
  ANTHROPIC_API_KEY / OPENAI_API_KEY
  VSP_LLM_BASE_URL   base URL, e.g. http://localhost:8000/v1 (required for
                     openai-compatible; optional override for meta / openai)
  VSP_LLM_URL        full endpoint override (proxy / local test server)
  VSP_LLM_TIMEOUT    seconds per request (meta + openai-compatible 120,
                     anthropic + openai 30)
  VSP_LLM_MAX_TOKENS output-token default (meta, openai-compatible, openai
                     4000; anthropic 1024). Reasoning models spend output
                     tokens on thinking: a 200-token cap returns empty text.
  VSP_LLM_REASONING_EFFORT  meta only (default "low"; "none" -> "minimal",
                     Meta rejects "none")

Retries: HTTP 429 / 503 are retried with jittered exponential backoff,
honouring Retry-After (seconds or HTTP-date; > 120 s is not waited for),
at most 4 tries in total. Timeouts and other errors are not retried.

    available(env=None) -> bool
    get_provider(env=None) -> Provider | None
    complete_text(prompt, *, system=None, max_tokens=None, env=None) -> str | None
    complete_json(prompt, schema, *, system=None, max_tokens=None, env=None)
        -> dict | None     (None: no model configured, any error, a reply that
                            is not one JSON object, or one that fails the
                            schema subset check of vsp.schema.validate)
    judge_pair(a_text, b_text, criterion) -> {"verdict": "A"|"B"|"tie"|"unknown",
                                               "votes": [...], ...}

complete_text / complete_json / judge_pair never raise. Both accept a
keyword-only provider= (tests inject MockProvider).

Bias control: both orders are judged (A/B, then B/A) and a win counts only
if it holds in both; an order-dependent verdict is a "tie", any error or
non-JSON reply makes the verdict "unknown". Replies must be one strict JSON
object {"winner": "A"|"B"|"tie", "reason": "..."}. render_candidate() gives
the canonical plain-text view (no seeds, no AI labels — provenance cues sway
judges). Nothing here raises into the pipeline.
"""
import email.utils
import inspect
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
META_BASE_URL = "https://api.meta.ai/v1"
META_URL = META_BASE_URL + "/chat/completions"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_TIMEOUT = 30.0
# pre-v2 judge cap, kept importable for old callers; judge_pair now defaults
# to the provider's own max tokens (a 200-token cap returns empty text on
# reasoning models such as Muse Spark)
DEFAULT_MAX_TOKENS = 200
VERDICTS = ("A", "B", "tie")
RECOMMENDED_META_MODEL = "muse-spark-1.3"
MAX_TRIES = 4
RETRY_STATUS = (429, 503)
BACKOFF_BASE = 1.0          # seconds; attempt k waits ~BASE * 2**(k-1)
MAX_BACKOFF = 30.0
MAX_RETRY_AFTER = 120.0     # a longer Retry-After is not waited for
# request keys the Meta Model API rejects (HTTP 400) or that we never send
META_FORBIDDEN = ("stop", "n", "logprobs", "top_logprobs", "logit_bias",
                  "temperature", "prediction", "verbosity", "modalities",
                  "audio", "web_search_options")


class LLMError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def _retry_after_seconds(value, now=None):
    """Retry-After header -> seconds (>= 0) or None (absent / unparseable)."""
    if value is None:
        return None
    v = str(value).strip()
    if not v:
        return None
    try:
        return max(0.0, float(v))
    except ValueError:
        pass
    try:
        dt = email.utils.parsedate_to_datetime(v)
    except (TypeError, ValueError, IndexError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return max(0.0, (dt - now).total_seconds())


def _join_url(base, path):
    b = (base or "").strip().rstrip("/")
    if not b:
        return None
    return b if b.endswith(path) else b + path


def _schema_name(name, schema):
    raw = name or (schema.get("title") if isinstance(schema, dict) else None) \
        or "result"
    n = re.sub(r"[^A-Za-z0-9_-]+", "_", str(raw)).strip("_")[:64]
    return n or "result"


def _messages(prompt, system=None):
    msgs = []
    if system:
        msgs.append({"role": "system", "content": str(system)})
    msgs.append({"role": "user", "content": str(prompt)})
    return msgs


class Provider:
    name = "base"
    default_url = None
    default_timeout = DEFAULT_TIMEOUT
    default_max_tokens = 1024
    supports_schema = False
    max_tries = MAX_TRIES
    retry_status = RETRY_STATUS

    def __init__(self, model, api_key=None, timeout=None, url=None,
                 max_tokens=None):
        self.model = model
        self.api_key = api_key
        self.timeout = float(timeout or self.default_timeout)
        self.url = url
        self.max_tokens = int(max_tokens or self.default_max_tokens)
        self.warnings = []
        self.sleep = time.sleep            # injectable (selfcheck)
        self.rand = random.Random().random  # jitter source, injectable
        self.last = {}                      # metadata of the last request

    def complete(self, prompt, max_tokens=None, system=None, schema=None,
                 schema_name=None):  # pragma: no cover
        raise NotImplementedError

    def endpoint(self):
        return self.url or self.default_url

    # ----------------------------------------------------------- transport
    def _backoff(self, attempt, retry_after=None):
        """Seconds to wait before try attempt+1 (None = do not retry)."""
        jitter = self.rand()
        ra = _retry_after_seconds(retry_after)
        if ra is not None:
            if ra > MAX_RETRY_AFTER:
                return None
            return ra + jitter * min(1.0, 0.1 * ra + 0.25)
        base = BACKOFF_BASE * (2 ** (attempt - 1))
        return min(MAX_BACKOFF, base * (0.5 + jitter))

    def _post(self, url, headers, body):
        data = json.dumps(body).encode("utf-8")
        self.last = {"url": url, "attempts": 0, "delays": [], "status": None}
        t0 = time.time()
        for attempt in range(1, self.max_tries + 1):
            self.last["attempts"] = attempt
            req = urllib.request.Request(url, data=data, headers=headers,
                                         method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    raw = r.read().decode("utf-8")
                    self.last["status"] = getattr(r, "status", 200)
                self.last["latency_s"] = round(time.time() - t0, 3)
                try:
                    return json.loads(raw)
                except ValueError:
                    raise LLMError(f"{self.name}: response is not JSON")
            except urllib.error.HTTPError as e:
                self.last["status"] = e.code
                detail = ""
                try:
                    detail = e.read().decode("utf-8", "replace")[:300]
                except Exception:
                    pass
                err = LLMError(f"{self.name} HTTP {e.code}: {detail}",
                               status=e.code)
                if e.code in self.retry_status and attempt < self.max_tries:
                    ra = e.headers.get("Retry-After") if e.headers else None
                    delay = self._backoff(attempt, ra)
                    if delay is not None:
                        self.last["delays"].append(round(delay, 3))
                        self.sleep(delay)
                        continue
                raise err
            except LLMError:
                raise
            except (urllib.error.URLError, OSError, ValueError) as e:
                raise LLMError(f"{self.name} request failed: {e!r}")
        raise LLMError(f"{self.name}: retries exhausted")  # pragma: no cover

    def _chat_text(self, data):
        try:
            ch = data["choices"][0]
            content = (ch.get("message") or {}).get("content")
        except (KeyError, IndexError, TypeError, AttributeError):
            raise LLMError(f"{self.name}: unexpected response shape")
        if isinstance(content, list):   # content parts
            content = "".join(p.get("text", "") for p in content
                              if isinstance(p, dict))
        self.last["finish_reason"] = ch.get("finish_reason")
        return content if isinstance(content, str) else ""


class AnthropicProvider(Provider):
    name = "anthropic"
    default_url = ANTHROPIC_URL
    default_max_tokens = 1024

    def complete(self, prompt, max_tokens=None, system=None, schema=None,
                 schema_name=None):
        body = {"model": self.model,
                "max_tokens": int(max_tokens or self.max_tokens),
                "messages": [{"role": "user", "content": str(prompt)}]}
        if system:
            body["system"] = str(system)
        data = self._post(self.endpoint(),
                          {"x-api-key": self.api_key or "",
                           "anthropic-version": ANTHROPIC_VERSION,
                           "content-type": "application/json"}, body)
        try:
            return "".join(b.get("text", "") for b in data.get("content") or []
                           if b.get("type") == "text")
        except AttributeError:
            raise LLMError("anthropic: unexpected response shape")


class OpenAIProvider(Provider):
    name = "openai"
    default_url = OPENAI_URL
    default_max_tokens = 4000
    supports_schema = True

    def build_body(self, prompt, max_tokens=None, system=None, schema=None,
                   schema_name=None):
        body = {"model": self.model, "messages": _messages(prompt, system),
                "max_completion_tokens": int(max_tokens or self.max_tokens)}
        if schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": _schema_name(schema_name, schema),
                                "schema": schema}}
        return body

    def headers(self):
        h = {"Content-Type": "application/json", "Accept": "application/json",
             "User-Agent": "vsp-llm/2"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def complete(self, prompt, max_tokens=None, system=None, schema=None,
                 schema_name=None):
        body = self.build_body(prompt, max_tokens, system, schema, schema_name)
        return self._chat_text(self._post(self.endpoint(), self.headers(), body))


class MetaProvider(OpenAIProvider):
    """Meta Model API (Muse Spark) over Chat Completions."""
    name = "meta"
    default_url = META_URL
    default_timeout = 120.0
    default_max_tokens = 4000

    def __init__(self, model, api_key=None, timeout=None, url=None,
                 max_tokens=None, reasoning_effort="low"):
        super().__init__(model, api_key, timeout=timeout, url=url,
                         max_tokens=max_tokens)
        eff = (reasoning_effort or "low").strip().lower()
        self.reasoning_effort = "minimal" if eff == "none" else eff

    def build_body(self, prompt, max_tokens=None, system=None, schema=None,
                   schema_name=None):
        body = super().build_body(prompt, max_tokens, system, schema,
                                  schema_name)
        body["reasoning_effort"] = self.reasoning_effort
        for k in META_FORBIDDEN:
            body.pop(k, None)
        return body


class OpenAICompatibleProvider(OpenAIProvider):
    """Local Muse Glimmer (vLLM / llama.cpp / Ollama) or any compatible server."""
    name = "openai-compatible"
    default_url = None
    default_timeout = 120.0
    default_max_tokens = 4000

    def build_body(self, prompt, max_tokens=None, system=None, schema=None,
                   schema_name=None):
        body = super().build_body(prompt, max_tokens, system, schema,
                                  schema_name)
        # the widely supported field name on local servers
        body["max_tokens"] = body.pop("max_completion_tokens")
        return body

    def complete(self, prompt, max_tokens=None, system=None, schema=None,
                 schema_name=None):
        url = self.endpoint()
        if not url:
            raise LLMError("openai-compatible: no VSP_LLM_BASE_URL / VSP_LLM_URL")
        body = self.build_body(prompt, max_tokens, system, schema, schema_name)
        try:
            data = self._post(url, self.headers(), body)
        except LLMError as e:
            if "response_format" in body and e.status in (400, 422, 501):
                body.pop("response_format")
                self.last["schema_fallback"] = True
                data = self._post(url, self.headers(), body)
            else:
                raise
        return self._chat_text(data)


class MockProvider(Provider):
    """Offline provider. fn(prompt) -> reply text, or a list of replies used
    in turn; default: a deterministic, order-independent judge that prefers
    the candidate with fewer words (so its wins hold in both orders).
    Every call is recorded: .calls (prompts) and .requests (prompt, system,
    schema, max_tokens)."""
    name = "mock"
    supports_schema = True

    def __init__(self, fn=None, replies=None, model="mock"):
        super().__init__(model)
        self.fn = fn
        self.replies = list(replies) if replies is not None else None
        self.calls = []
        self.requests = []

    def complete(self, prompt, max_tokens=None, system=None, schema=None,
                 schema_name=None):
        self.calls.append(prompt)
        self.requests.append({"prompt": prompt, "system": system,
                              "schema": schema, "max_tokens": max_tokens})
        if self.fn is not None:
            return self.fn(prompt)
        if self.replies is not None:
            if not self.replies:
                raise LLMError("mock: no replies left")
            return self.replies.pop(0)
        a, b = _candidates_in(prompt)
        na, nb = len(a.split()), len(b.split())
        w = "tie" if na == nb else ("A" if na < nb else "B")
        return json.dumps({"winner": w, "reason": "mock: fewer words wins"})


PROVIDERS = {"meta": MetaProvider, "openai-compatible": OpenAICompatibleProvider,
             "anthropic": AnthropicProvider, "openai": OpenAIProvider}
# primary key variable per provider (pre-v2 name, kept importable)
KEY_ENV = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY",
           "meta": "MODEL_API_KEY", "openai-compatible": "VSP_LLM_API_KEY"}
# lookup order per provider: the neutral VSP_LLM_API_KEY always comes first
KEY_ENVS = {"meta": ("VSP_LLM_API_KEY", "MODEL_API_KEY", "META_API_KEY"),
            "anthropic": ("VSP_LLM_API_KEY", "ANTHROPIC_API_KEY"),
            "openai": ("VSP_LLM_API_KEY", "OPENAI_API_KEY"),
            "openai-compatible": ("VSP_LLM_API_KEY",)}
PROVIDER_ALIASES = {"meta-ai": "meta", "muse": "meta",
                    "openai_compatible": "openai-compatible",
                    "openai-compat": "openai-compatible",
                    "local": "openai-compatible", "glimmer": "openai-compatible",
                    "vllm": "openai-compatible", "ollama": "openai-compatible",
                    "llama.cpp": "openai-compatible", "llamacpp": "openai-compatible"}
DEFAULT_TIMEOUTS = {"meta": 120.0, "openai-compatible": 120.0}
_WARNED = set()


def _env(env):
    return os.environ if env is None else env


def _key_for(prov, e):
    for name in KEY_ENVS.get(prov, ()):
        v = (e.get(name) or "").strip()
        if v:
            return v, name
    return None, None


def _resolve(env=None):
    e = _env(env)
    prov = (e.get("VSP_LLM_PROVIDER") or "").strip().lower() or None
    prov = PROVIDER_ALIASES.get(prov, prov)
    if prov is None:
        if _key_for("meta", e)[0]:
            prov = "meta"
        elif (e.get("ANTHROPIC_API_KEY") or "").strip():
            prov = "anthropic"
        elif (e.get("OPENAI_API_KEY") or "").strip():
            prov = "openai"
    key, key_env = _key_for(prov, e)
    model = (e.get("VSP_LLM_MODEL") or "").strip() or None
    try:
        timeout = float(e.get("VSP_LLM_TIMEOUT") or
                        DEFAULT_TIMEOUTS.get(prov, DEFAULT_TIMEOUT))
    except ValueError:
        timeout = DEFAULT_TIMEOUTS.get(prov, DEFAULT_TIMEOUT)
    try:
        max_tokens = int(e.get("VSP_LLM_MAX_TOKENS") or 0) or None
    except ValueError:
        max_tokens = None
    base = (e.get("VSP_LLM_BASE_URL") or "").strip() or None
    url = (e.get("VSP_LLM_URL") or "").strip() or None
    if url is None and base and prov in ("meta", "openai-compatible", "openai"):
        url = _join_url(base, "/chat/completions")
    warnings = []
    if model and "-contributor" in model.lower():
        warnings.append(
            f"VSP_LLM_MODEL={model} is a contributor-tier ID: Meta may train on "
            f"this traffic (Meta Terms 2026-09-18) — use a Standard-tier ID "
            f"such as {RECOMMENDED_META_MODEL} for rulebook prompts")
    return {"provider": prov, "model": model, "key": key, "key_env": key_env,
            "key_present": bool(key), "timeout": timeout, "url": url,
            "base_url": base, "max_tokens": max_tokens,
            "reasoning_effort": (e.get("VSP_LLM_REASONING_EFFORT") or "low"),
            "warnings": warnings}


def config_from_env(env=None):
    """Resolved configuration (never includes the key itself)."""
    c = dict(_resolve(env))
    c.pop("key", None)
    return c


def _warn_once(msgs):
    for m in msgs or ():
        if m not in _WARNED:
            _WARNED.add(m)
            try:
                print(f"vsp.llm warning: {m}", file=sys.stderr)
            except Exception:
                pass


def get_provider(env=None):
    """Configured provider or None (model is required; a key is required for
    meta / anthropic / openai; openai-compatible needs a base URL)."""
    try:
        c = _resolve(env)
        p = c["provider"]
        if p == "mock":
            return MockProvider(model=c["model"] or "mock")
        if p not in PROVIDERS or not c["model"]:
            return None
        if p == "openai-compatible":
            if not c["url"]:
                return None
        elif not c["key"]:
            return None
        kw = {"timeout": c["timeout"], "url": c["url"],
              "max_tokens": c["max_tokens"]}
        if p == "meta":
            kw["reasoning_effort"] = c["reasoning_effort"]
        prov = PROVIDERS[p](c["model"], c["key"], **kw)
        prov.warnings = list(c["warnings"])
        _warn_once(c["warnings"])
        return prov
    except Exception:
        return None


def available(env=None):
    return get_provider(env) is not None


def describe(env=None, provider=None):
    """Loggable summary: {provider, model, endpoint, key_env, warnings}."""
    try:
        if provider is not None:
            return {"provider": provider.name, "model": provider.model,
                    "endpoint": provider.endpoint(), "key_env": None,
                    "warnings": list(getattr(provider, "warnings", []))}
        c = config_from_env(env)
        return {"provider": c["provider"], "model": c["model"],
                "endpoint": c["url"], "key_env": c["key_env"],
                "warnings": c["warnings"], "available": available(env)}
    except Exception as e:  # noqa: BLE001
        return {"error": repr(e)}


# ------------------------------------------------------------ completion
JSON_INSTRUCTION = ("\n\nReply with ONLY one JSON object (no prose, no code "
                    "fence) that matches this JSON Schema:\n{schema}")
_FENCE = re.compile(r"^```[A-Za-z0-9_-]*\s*\n(.*?)\n?```$", re.S)
_THINK = re.compile(r"^\s*<think>.*?</think>\s*", re.S | re.I)


def _call(provider, prompt, max_tokens=None, system=None, schema=None,
          schema_name=None):
    """provider.complete with the v2 keywords; providers written against the
    pre-v2 complete(prompt, max_tokens) signature still work (system folded
    into the prompt, no native schema)."""
    try:
        params = inspect.signature(provider.complete).parameters
    except (TypeError, ValueError):
        params = {}
    if "system" in params or any(p.kind == p.VAR_KEYWORD
                                 for p in params.values()):
        return provider.complete(prompt, max_tokens=max_tokens, system=system,
                                 schema=schema, schema_name=schema_name)
    full = f"{system}\n\n{prompt}" if system else prompt
    if max_tokens is None:
        return provider.complete(full)
    return provider.complete(full, max_tokens)


def parse_json_reply(text):
    """The reply as one JSON value, or None. Accepts the bare object, one
    fenced ```json block, or either after a leading <think>…</think>."""
    t = _THINK.sub("", text or "", count=1).strip()
    if not t:
        return None
    try:
        return json.loads(t)
    except ValueError:
        pass
    m = _FENCE.match(t)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except ValueError:
            return None
    return None


def schema_errors(obj, schema):
    """vsp.schema's stdlib subset validator (type, required, properties,
    additionalProperties, items, enum, const, pattern, min/max...)."""
    try:
        from vsp.schema import validate
    except Exception:  # noqa: BLE001 — validator unavailable: trust the reply
        return []
    try:
        return validate(obj, schema)
    except Exception as e:  # noqa: BLE001 — a schema the subset cannot read
        return [f"schema check failed: {e!r}"]


def complete_text(prompt, *, system=None, max_tokens=None, env=None,
                  provider=None):
    """Plain completion -> text, or None (no model configured, any error, or
    an empty reply). Never raises."""
    try:
        p = provider or get_provider(env)
        if p is None:
            return None
        text = _call(p, prompt, max_tokens=max_tokens, system=system)
        text = _THINK.sub("", text or "", count=1).strip()
        return text or None
    except Exception:  # noqa: BLE001 — advisory layer never raises
        return None


def complete_json(prompt, schema, *, system=None, max_tokens=None, env=None,
                  provider=None, name=None):
    """Structured completion -> dict, or None (no model configured, any
    error, a reply that is not one JSON object, or one failing `schema`).
    Uses response_format json_schema where the provider supports it; the
    schema is also stated in the prompt. Never raises."""
    try:
        if not isinstance(schema, dict):
            return None
        p = provider or get_provider(env)
        if p is None:
            return None
        full = str(prompt) + JSON_INSTRUCTION.format(
            schema=json.dumps(schema, ensure_ascii=False, sort_keys=True))
        native = schema if getattr(p, "supports_schema", False) else None
        text = _call(p, full, max_tokens=max_tokens, system=system,
                     schema=native, schema_name=name)
        obj = parse_json_reply(text)
        if not isinstance(obj, dict):
            return None
        if schema_errors(obj, schema):
            return None
        return obj
    except Exception:  # noqa: BLE001 — advisory layer never raises
        return None


# ------------------------------------------------------------------ judge
PAIR_PROMPT = """You are a strict, skeptical judge of short-form video scripts.
Criterion: {criterion}
Compare the two candidates ONLY on that criterion. Ignore length, formatting and position.

CANDIDATE A:
<<<
{a}
>>>

CANDIDATE B:
<<<
{b}
>>>

Reply with ONLY one JSON object, no prose and no code fence:
{{"winner": "A" or "B" or "tie", "reason": "one short sentence"}}"""

VERDICT_SCHEMA = {"type": "object",
                  "properties": {"winner": {"type": "string",
                                            "enum": ["A", "B", "tie"]},
                                 "reason": {"type": "string"}},
                  "required": ["winner", "reason"],
                  "additionalProperties": False}

_CAND_RE = re.compile(r"CANDIDATE A:\n<<<\n(.*?)\n>>>\n\nCANDIDATE B:\n<<<\n(.*?)\n>>>", re.S)


def _candidates_in(prompt):
    m = _CAND_RE.search(prompt or "")
    return (m.group(1), m.group(2)) if m else ("", "")


def parse_verdict(text):
    """Strict: the whole reply must be one JSON object whose "winner" is
    A, B or tie (case-insensitive). -> ("A"|"B"|"tie", reason) or (None, why)."""
    t = (text or "").strip()
    try:
        obj = json.loads(t)
    except ValueError:
        return None, "reply is not a JSON object"
    if not isinstance(obj, dict) or not isinstance(obj.get("winner"), str):
        return None, "reply lacks a string 'winner'"
    w = obj["winner"].strip()
    w = {"a": "A", "b": "B", "tie": "tie"}.get(w.lower())
    if w is None:
        return None, f"invalid winner {obj['winner']!r}"
    return w, str(obj.get("reason") or "")[:300]


def _flip(v):
    return {"A": "B", "B": "A"}.get(v, v)


def judge_pair(a_text, b_text, criterion, provider=None, max_tokens=None,
               length_tolerance=None):
    """Pairwise verdict on `criterion`, both orders. -> {"verdict", "votes",
    "consistent", "provider", "model", "criterion"}. max_tokens=None uses the
    provider's default (4000 on meta / openai / openai-compatible). Providers
    with native structured output get the verdict schema. length_tolerance
    (e.g. 0.10) returns "unknown" when the word counts differ by more than
    that fraction (verbosity-bias control). Never raises."""
    res = {"verdict": "unknown", "votes": [], "consistent": None,
           "provider": None, "model": None, "criterion": criterion}
    try:
        provider = provider or get_provider()
        if provider is None:
            res["reason"] = "llm unavailable (set VSP_LLM_MODEL + provider key)"
            return res
        res["provider"], res["model"] = provider.name, provider.model
        if length_tolerance is not None:
            na, nb = len((a_text or "").split()), len((b_text or "").split())
            if max(na, nb) and abs(na - nb) / float(max(na, nb)) > length_tolerance:
                res["reason"] = f"length mismatch ({na} vs {nb} words)"
                return res
        native = VERDICT_SCHEMA if (getattr(provider, "supports_schema", False)
                                    and provider.name != "mock") else None
        mapped = []
        for order, first, second in (("AB", a_text, b_text), ("BA", b_text, a_text)):
            vote = {"order": order, "raw": None, "mapped": None, "reason": None,
                    "error": None}
            try:
                reply = _call(provider, PAIR_PROMPT.format(
                    criterion=criterion, a=first or "", b=second or ""),
                    max_tokens=max_tokens, schema=native, schema_name="verdict")
                v, why = parse_verdict(reply)
                vote["raw"], vote["reason"] = v, why
                if v is None:
                    vote["error"] = why
                else:
                    vote["mapped"] = v if order == "AB" else _flip(v)
            except Exception as e:  # network, timeout, provider bug
                vote["error"] = f"{type(e).__name__}: {e}"[:300]
            res["votes"].append(vote)
            mapped.append(vote["mapped"])
        if any(m is None for m in mapped):
            res["verdict"] = "unknown"
        elif mapped[0] == mapped[1]:
            res["verdict"], res["consistent"] = mapped[0], True
        else:
            res["verdict"], res["consistent"] = "tie", False   # position bias
        return res
    except Exception as e:
        res["verdict"], res["reason"] = "unknown", f"judge error: {e!r}"[:300]
        return res


def render_candidate(script):
    """Canonical plain-text view of a script for judging: spoken lines and
    on-screen text in order, caption without the AI line — no seeds, ids,
    presenter labels or AI mentions."""
    L = []
    for it in list(script.get("hook_stack") or []) + list(script.get("beats") or []):
        parts = []
        if it.get("dialogue"):
            parts.append(str(it["dialogue"]))
        if it.get("on_screen"):
            parts.append(f"[on screen: {it['on_screen']}]")
        if it.get("rehook"):
            parts.append(str(it["rehook"]))
        if parts:
            L.append(" ".join(parts))
    cap = [ln for ln in (script.get("caption") or "").split("\n")
           if ln.strip() and not re.search(r"\bAI\b", ln)]
    if cap:
        L.append("Caption: " + " ".join(cap))
    text = "\n".join(L)
    return re.sub(r"\bAI persona\b", "presenter", text)


def judge_scripts(a, b, criterion="Which script is more likely to stop the scroll "
                  "and hold a viewer to the payoff?", **kw):
    """judge_pair over two scripts' canonical renderings (advisory)."""
    return judge_pair(render_candidate(a), render_candidate(b), criterion, **kw)
