"""Optional LLM judge — ADVISORY ONLY, never a gate (labs-techniques §3.2/§3.3).

Off unless configured. Stdlib urllib client, two providers:

  anthropic  POST https://api.anthropic.com/v1/messages
             headers x-api-key, anthropic-version: 2023-06-01, content-type
             body {model, max_tokens, messages}
  openai     POST https://api.openai.com/v1/chat/completions (Bearer auth)
             body {model, messages, max_completion_tokens}
  mock       offline, deterministic (tests / --llm-judge dry runs)

Environment:
  VSP_LLM_MODEL      required — no model name is hard-coded anywhere
  VSP_LLM_PROVIDER   anthropic | openai | mock (default: inferred from the key
                     that is set, anthropic first)
  ANTHROPIC_API_KEY / OPENAI_API_KEY
  VSP_LLM_TIMEOUT    seconds per request (default 30)
  VSP_LLM_URL        optional endpoint override (proxy / local test server)

    available() -> bool
    judge_pair(a_text, b_text, criterion) -> {"verdict": "A"|"B"|"tie"|"unknown",
                                               "votes": [...], ...}

Bias control: both orders are judged (A/B, then B/A) and a win counts only
if it holds in both; an order-dependent verdict is a "tie", any error or
non-JSON reply makes the verdict "unknown". Replies must be one strict JSON
object {"winner": "A"|"B"|"tie", "reason": "..."}. render_candidate() gives
the canonical plain-text view (no seeds, no AI labels — provenance cues sway
judges). Nothing here raises into the pipeline.
"""
import json
import os
import re
import urllib.error
import urllib.request

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_TOKENS = 200
VERDICTS = ("A", "B", "tie")


class LLMError(Exception):
    pass


class Provider:
    name = "base"

    def __init__(self, model, api_key=None, timeout=DEFAULT_TIMEOUT, url=None):
        self.model = model
        self.api_key = api_key
        self.timeout = float(timeout or DEFAULT_TIMEOUT)
        self.url = url

    def complete(self, prompt, max_tokens=DEFAULT_MAX_TOKENS):  # pragma: no cover
        raise NotImplementedError

    def _post(self, url, headers, body):
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                     headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            raise LLMError(f"{self.name} HTTP {e.code}: {detail}")
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise LLMError(f"{self.name} request failed: {e!r}")


class AnthropicProvider(Provider):
    name = "anthropic"

    def complete(self, prompt, max_tokens=DEFAULT_MAX_TOKENS):
        data = self._post(self.url or ANTHROPIC_URL,
                          {"x-api-key": self.api_key or "",
                           "anthropic-version": ANTHROPIC_VERSION,
                           "content-type": "application/json"},
                          {"model": self.model, "max_tokens": int(max_tokens),
                           "messages": [{"role": "user", "content": prompt}]})
        try:
            return "".join(b.get("text", "") for b in data.get("content") or []
                           if b.get("type") == "text")
        except AttributeError:
            raise LLMError("anthropic: unexpected response shape")


class OpenAIProvider(Provider):
    name = "openai"

    def complete(self, prompt, max_tokens=DEFAULT_MAX_TOKENS):
        data = self._post(self.url or OPENAI_URL,
                          {"Authorization": f"Bearer {self.api_key or ''}",
                           "Content-Type": "application/json"},
                          {"model": self.model,
                           "messages": [{"role": "user", "content": prompt}],
                           "max_completion_tokens": int(max_tokens)})
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise LLMError("openai: unexpected response shape")


class MockProvider(Provider):
    """Offline provider. fn(prompt) -> reply text, or a list of replies used
    in turn; default: a deterministic, order-independent judge that prefers
    the candidate with fewer words (so its wins hold in both orders)."""
    name = "mock"

    def __init__(self, fn=None, replies=None, model="mock"):
        super().__init__(model)
        self.fn = fn
        self.replies = list(replies) if replies is not None else None
        self.calls = []

    def complete(self, prompt, max_tokens=DEFAULT_MAX_TOKENS):
        self.calls.append(prompt)
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


PROVIDERS = {"anthropic": AnthropicProvider, "openai": OpenAIProvider}
KEY_ENV = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}


def _env(env):
    return os.environ if env is None else env


def config_from_env(env=None):
    e = _env(env)
    prov = (e.get("VSP_LLM_PROVIDER") or "").strip().lower() or None
    if prov is None:
        prov = next((p for p in ("anthropic", "openai") if e.get(KEY_ENV[p])), None)
    try:
        timeout = float(e.get("VSP_LLM_TIMEOUT") or DEFAULT_TIMEOUT)
    except ValueError:
        timeout = DEFAULT_TIMEOUT
    return {"provider": prov, "model": (e.get("VSP_LLM_MODEL") or "").strip() or None,
            "key_present": bool(prov in KEY_ENV and e.get(KEY_ENV[prov])),
            "timeout": timeout, "url": e.get("VSP_LLM_URL") or None}


def get_provider(env=None):
    """Configured provider or None (model is required; key required for the
    network providers)."""
    try:
        c = config_from_env(env)
        if c["provider"] == "mock":
            return MockProvider(model=c["model"] or "mock")
        if not c["model"] or c["provider"] not in PROVIDERS or not c["key_present"]:
            return None
        return PROVIDERS[c["provider"]](c["model"], _env(env).get(KEY_ENV[c["provider"]]),
                                        timeout=c["timeout"], url=c["url"])
    except Exception:
        return None


def available(env=None):
    return get_provider(env) is not None


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


def judge_pair(a_text, b_text, criterion, provider=None, max_tokens=DEFAULT_MAX_TOKENS,
               length_tolerance=None):
    """Pairwise verdict on `criterion`, both orders. -> {"verdict", "votes",
    "consistent", "provider", "model", "criterion"}. length_tolerance (e.g.
    0.10) returns "unknown" when the word counts differ by more than that
    fraction (verbosity-bias control). Never raises."""
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
        mapped = []
        for order, first, second in (("AB", a_text, b_text), ("BA", b_text, a_text)):
            vote = {"order": order, "raw": None, "mapped": None, "reason": None,
                    "error": None}
            try:
                reply = provider.complete(PAIR_PROMPT.format(
                    criterion=criterion, a=first or "", b=second or ""), max_tokens)
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
