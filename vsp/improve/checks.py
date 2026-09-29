"""Hermetic self-check of the improvement engine: selfcheck() -> (ok, lines)
(re-exported as vsp.improve.selfcheck; CLI: python3 -m vsp.improve selfcheck).

No network (a stub HTTP server on 127.0.0.1 stands in for the Meta Model
API; MockProvider for complete_json), no writes to the repo (learned state
goes to a temp VSP_LEARNED_DIR, packs to a temp dir), no research DB
(VSP_VIRAL_DB -> a missing temp path), no real LLM (every provider injected).

Checks:
  llm-meta-http        request shape (path, Bearer key, model, messages,
                       max_completion_tokens 4000, reasoning_effort, json_schema
                       response_format, no forbidden keys), 429 -> 503 -> 200
                       retries with Retry-After honoured, Retry-After > 120 s not
                       waited for, openai-compatible schema fallback on HTTP 400
  llm-complete-json    MockProvider: bare / fenced / <think> JSON accepted;
                       prose, arrays, schema violations, errors -> None
  packs-contract       the loader contract (status, schema, families, known
                       slots, <= 120 chars, one line, dedupe)
  evolve-slot-safe     a tiny evolve run: every template obeys the contract,
                       renders <= 8 words and the pack file validates; LLM
                       proposals that break the contract are discarded
  evolve-no-holdout    evolve never opens evals/holdout.jsonl (recorded), and
                       the guard raises if anything inside evolve tries to
  decide-synthetic     ACCEPT/REJECT on synthetic scorecards: every rule
                       (R1-R11) fires on its own regression and only then
  promote-flow         promote on synthetic A/B results: approved / rejected
                       status, provenance evidence, LEDGER entries
  verify-flow          verify wiring on synthetic trees + stubbed A/B: guard
                       findings REJECT, a clean candidate ACCEPTs
  weakening-guard      snapshot compare: removed registry entries, severity
                       downgrades, lost regex alternatives, allow-list growth,
                       loosened limits, dropped self-test cases, removed
                       D136-D141 all found; an identical tree is clean
  refresh-dedupe       golden-refresh never writes golden/holdout and
                       de-duplicates trending phrases
"""
import contextlib
import copy
import http.server
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import traceback

from vsp.improve import common as C


# ------------------------------------------------------------- helpers
@contextlib.contextmanager
def _env(**kw):
    old = {k: os.environ.get(k) for k in kw}
    for k, v in kw.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@contextlib.contextmanager
def _patch(obj, name, value):
    old = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield
    finally:
        setattr(obj, name, old)


class _Stub:
    """Scripted localhost HTTP server: each POST pops (status, headers, body)."""

    def __init__(self):
        self.requests, self.script = [], []
        stub = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(n)
                try:
                    body = json.loads(raw)
                except ValueError:
                    body = None
                stub.requests.append({"path": self.path, "headers": dict(self.headers),
                                      "body": body})
                code, hdrs, payload = stub.script.pop(0) if stub.script else \
                    (200, {}, _chat({"ok": True}))
                data = json.dumps(payload).encode()
                self.send_response(code)
                for k, v in hdrs.items():
                    self.send_header(k, v)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}/v1"

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


def _chat(obj):
    return {"choices": [{"message": {"role": "assistant", "content": json.dumps(obj)},
                         "finish_reason": "stop"}]}


# ---------------------------------------------------------------- checks
SCHEMA = {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]}


def check_llm_meta_http():
    from vsp import llm
    probs = []
    stub = _Stub()
    try:
        with _env(NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost",
                  HTTP_PROXY=None, http_proxy=None, HTTPS_PROXY=None, https_proxy=None,
                  ALL_PROXY=None, all_proxy=None):
            env = {"VSP_LLM_API_KEY": "k-neutral", "MODEL_API_KEY": "k-model",
                   "VSP_LLM_MODEL": "muse-spark-1.3", "VSP_LLM_BASE_URL": stub.base}
            p = llm.get_provider(env)
            if p is None or p.name != "meta":
                return [f"meta provider not resolved from env: {p!r}"]
            delays = []
            p.sleep = delays.append
            p.rand = lambda: 0.0
            stub.script[:] = [(429, {"Retry-After": "2"}, {"error": "rate"}),
                              (503, {}, {"error": "busy"}), (200, {}, _chat({"x": 7}))]
            got = llm.complete_json("hello", SCHEMA, system="sys", provider=p, name="probe")
            if got != {"x": 7}:
                probs.append(f"complete_json after retries -> {got!r}")
            if p.last.get("attempts") != 3:
                probs.append(f"attempts {p.last.get('attempts')} != 3")
            if len(delays) != 2 or abs(delays[0] - 2.0) > 1e-6 or abs(delays[1] - 1.0) > 1e-6:
                probs.append(f"backoff delays {delays} != [2.0 (Retry-After), 1.0]")
            req = stub.requests[-1]
            b = req["body"] or {}
            if req["path"] != "/v1/chat/completions":
                probs.append(f"path {req['path']}")
            auth = {k.lower(): v for k, v in req["headers"].items()}.get("authorization")
            if auth != "Bearer k-neutral":
                probs.append(f"Authorization {auth!r} (VSP_LLM_API_KEY must win)")
            if b.get("model") != "muse-spark-1.3" or b.get("max_completion_tokens") != 4000 \
                    or b.get("reasoning_effort") != "low":
                probs.append(f"body model/max_completion_tokens/reasoning_effort: "
                             f"{b.get('model')}/{b.get('max_completion_tokens')}/"
                             f"{b.get('reasoning_effort')}")
            msgs = b.get("messages") or []
            if [m.get("role") for m in msgs] != ["system", "user"]:
                probs.append(f"messages roles {[m.get('role') for m in msgs]}")
            rf = b.get("response_format") or {}
            if rf.get("type") != "json_schema" or (rf.get("json_schema") or {}).get("schema") \
                    != SCHEMA or (rf.get("json_schema") or {}).get("name") != "probe":
                probs.append(f"response_format {rf!r}")
            bad = [k for k in llm.META_FORBIDDEN if k in b]
            if bad:
                probs.append(f"forbidden keys sent: {bad}")
            # a Retry-After beyond MAX_RETRY_AFTER is not waited for
            delays.clear()
            stub.script[:] = [(429, {"Retry-After": "600"}, {"error": "rate"})]
            if llm.complete_json("hi", SCHEMA, provider=p) is not None or delays:
                probs.append("Retry-After 600 s should give up at once (None, no sleep)")
            # openai-compatible: HTTP 400 on the schema request -> retried without it
            q = llm.get_provider({"VSP_LLM_PROVIDER": "openai-compatible",
                                  "VSP_LLM_MODEL": "muse-glimmer", "VSP_LLM_BASE_URL": stub.base})
            q.sleep = lambda s: None
            stub.script[:] = [(400, {}, {"error": "response_format unsupported"}),
                              (200, {}, _chat({"x": 1}))]
            n0 = len(stub.requests)
            if llm.complete_json("hi", SCHEMA, provider=q) != {"x": 1}:
                probs.append("openai-compatible schema fallback failed")
            r1, r2 = stub.requests[n0:n0 + 2] if len(stub.requests) >= n0 + 2 else (None, None)
            if not r1 or "response_format" not in r1["body"] or "response_format" in r2["body"] \
                    or r2["body"].get("max_tokens") != 4000:
                probs.append("openai-compatible: first request must carry response_format, "
                             "the retry must not; max_tokens 4000")
            # unconfigured -> None, never raises
            if llm.complete_json("x", SCHEMA, env={}) is not None or \
                    llm.complete_text("x", env={}) is not None:
                probs.append("unconfigured complete_* must return None")
    finally:
        stub.close()
    return probs


def check_llm_complete_json():
    from vsp import llm
    probs = []
    m = llm.MockProvider(replies=['{"x": 3}', "```json\n{\"x\": 4}\n```",
                                  "<think>hmm</think>{\"x\": 5}", "not json", "[1, 2]",
                                  '{"x": "three"}'])
    got = [llm.complete_json("p", SCHEMA, provider=m) for _ in range(7)]
    want = [{"x": 3}, {"x": 4}, {"x": 5}, None, None, None, None]
    if got != want:
        probs.append(f"MockProvider sequence -> {got} (want {want})")
    if not m.requests or m.requests[0]["schema"] != SCHEMA:
        probs.append("MockProvider did not receive the native schema")
    boom = llm.MockProvider(fn=lambda p: (_ for _ in ()).throw(RuntimeError("x")))
    if llm.complete_json("p", SCHEMA, provider=boom) is not None:
        probs.append("a provider exception must give None")
    return probs


def check_packs_contract():
    from vsp.improve import packs as P
    probs = []
    hooks = {"curiosity-gap": ["Nobody mentions {product}."],
             "bold-claim": ["Most {category_pl} fail.", "One {category} to rule."]}
    known = P.hook_slots(hooks)
    cases = {"Ok for {product}.": None, "bad {nope}": "unknown slot",
             "x" * 121: "chars", "a\nb": "newline", "brace {product": "stray brace",
             "{product.name}": "stray brace", "": "not a non-empty"}
    for t, want in cases.items():
        why = P.template_problem(t, known)
        if (why is None) != (want is None) or (want and want not in (why or "")):
            probs.append(f"template_problem({t[:20]!r}) -> {why!r} (want {want!r})")
    d = tempfile.mkdtemp(prefix="vsp-sc-packs-")
    try:
        C.write_json(os.path.join(d, "2026-01-01-01.json"), {
            "schema_version": 1, "id": "a", "status": "approved",
            "families": {"curiosity-gap": ["The {category} test.", "bad {nope}",
                                           "Nobody mentions {product}."],
                         "unknown-family": ["x {product}."]}})
        C.write_json(os.path.join(d, "2026-01-01-02.json"), {
            "schema_version": 1, "id": "b", "status": "proposed",
            "families": {"bold-claim": ["Never {product}."]}})
        C.write_json(os.path.join(d, "2026-01-01-03.json"), {
            "schema_version": 2, "id": "c", "status": "approved",
            "families": {"bold-claim": ["V2 {product}."]}})
        h = copy.deepcopy(hooks)
        ids, added, warns = P.load_into(h, d)
        if ids != ["a"] or added != {"curiosity-gap": ["The {category} test."]}:
            probs.append(f"load_into -> ids {ids}, added {added}")
        if not any("unknown family" in w or "skipped" in w for w in warns):
            probs.append(f"unknown family not warned: {warns}")
        path, pid = P.next_pack_path(d, date="2026-01-01")
        if not path.endswith("2026-01-01-04.json") or pid != "2026-01-01-evolve-04":
            probs.append(f"next_pack_path -> {path}, {pid}")
    finally:
        shutil.rmtree(d, ignore_errors=True)
    return probs


def _tiny_rows():
    from vsp.improve import evolve as E
    rows = E.golden_rows()
    want = ("door-lock", "bands", "serum", "car-trash")
    return [r for r in rows if r.get("id") in want] or \
        [r for r in rows if r.get("concept") == "product"][:4]


def check_evolve_slot_safe():
    from vsp import llm
    from vsp.improve import evolve as E
    from vsp.improve import packs as P
    probs = []
    d = tempfile.mkdtemp(prefix="vsp-sc-evolve-")
    try:
        vsm = E.load_maker()
        hooks, known, _ = E.effective_hooks(vsm)
        replies = [json.dumps({"templates": [
            {"family": "curiosity-gap", "template": "The {category} detail everyone skips.",
             "rationale": "thin curiosity pools"},
            {"family": "curiosity-gap", "template": "Nobody tells you about {brand}.",
             "rationale": "unknown slot"},
            {"family": "made-up-family", "template": "The {category} fix.", "rationale": "x"},
            {"family": "bold-claim", "template": "{product} is guaranteed to work.",
             "rationale": "absolute claim"},
            {"family": "curiosity-gap", "template": "Two lines\n{product}", "rationale": "nl"},
            {"family": "curiosity-gap", "template": "x" * 130 + " {product}.",
             "rationale": "too long"}]})]
        mock = llm.MockProvider(replies=replies * 3)
        res = E.evolve(budget="small", use_llm="on", seed=1, write=True, provider=mock,
                       rows=_tiny_rows(), pack_dir=d,
                       limits={"prompts": 4, "generations": 1, "per_gen": 60,
                               "screen_ctx": 20, "llm_calls": 1, "pack_max": 5})
        if not mock.calls:
            probs.append("LLM reflective mutation was not called with --llm on")
        else:
            pr = mock.calls[0]
            for need in ("FAILED", "thin", "{product}", "Return JSON"):
                if need not in pr:
                    probs.append(f"LLM prompt lacks {need!r}")
        allt = [e["template"] for e in res["archive"]["elites"]] + \
            [e["template"] for e in res["pack"]]
        for t in allt:
            why = P.template_problem(t, known)
            if why:
                probs.append(f"elite {t!r}: {why}")
        for bad in ("{brand}", "guaranteed", "\n", "x" * 130):
            if any(bad in t for t in allt):
                probs.append(f"an invalid LLM template survived ({bad!r})")
        for e in res["pack"]:
            for s in e.get("samples") or []:
                if len(s["line"].split()) > 8 or "{" in s["line"]:
                    probs.append(f"render {s['line']!r} breaks D73/D31")
        if res["verdict"] == "proposed":
            pack = C.read_json(res["path"])
            vp = P.validate_pack(pack, hooks, known)
            if vp:
                probs.append(f"written pack invalid: {vp[:3]}")
            if pack.get("status") != "proposed":
                probs.append(f"new pack status {pack.get('status')!r} != proposed")
            if (pack.get("provenance") or {}).get("evidence", {}).get("holdout_read") is not False:
                probs.append("pack evidence lacks holdout_read: false")
        elif not res["archive"]["elites"]:
            probs.append(f"tiny evolve found no elites ({res['why']})")
        if res["llm"].get("returned", 0) < 6:
            probs.append(f"LLM templates not all parsed: {res['llm']}")
    finally:
        shutil.rmtree(d, ignore_errors=True)
    return probs


def check_evolve_no_holdout():
    import builtins
    from vsp.improve import evolve as E
    probs = []
    opened = []
    real = builtins.open

    def spy(file, *a, **k):
        try:
            opened.append(os.fspath(file))
        except TypeError:
            pass
        return real(file, *a, **k)

    with _patch(builtins, "open", spy):
        E.evolve(budget="small", use_llm="off", seed=2, write=False, rows=None,
                 limits={"prompts": 2, "generations": 1, "per_gen": 20, "screen_ctx": 10,
                         "pack_max": 2})
    hits = [p for p in opened if os.path.basename(p) == C.HOLDOUT_NAME]
    if hits:
        probs.append(f"evolve opened the holdout: {hits}")
    if not any(os.path.basename(p) == C.GOLDEN_NAME for p in opened):
        probs.append("spy saw no golden read (spy not effective?)")
    # the guard itself: anything inside evolve that reaches for holdout raises
    holdout = C.suite_path("holdout")
    orig = C.suite_path
    try:
        C.suite_path = lambda suite, repo=None: holdout
        try:
            E.evolve(budget="small", use_llm="off", write=False,
                     limits={"prompts": 1, "generations": 0})
            probs.append("evolve read a golden path that is the holdout without raising")
        except E.HoldoutRead:
            pass
    finally:
        C.suite_path = orig
    with E.holdout_guard(record=[]) as rec:
        try:
            with open(holdout, encoding="utf-8") as f:
                f.read(1)
            probs.append("holdout_guard did not block open()")
        except E.HoldoutRead:
            pass
    if not rec:
        probs.append("holdout_guard did not record the attempt")
    return probs


# ------------------------------------------------ synthetic scorecards
def _card(n_prompts=6, fail=(), rubric=100.0, audit=100.0, comp=(), hook="h{i}",
          distinct=None, distinct2=None, drop=()):
    runs = []
    for i in range(n_prompts):
        for fmt in ("demo", "review"):
            key = f"p{i}|{fmt}|human|1"
            if key in drop:
                continue
            r = {"key": key, "id": f"p{i}", "format": fmt, "presenter": "human", "seed": 1,
                 "status": "gate1_fail" if key in fail else "pass",
                 "rubric": rubric, "rubric_selection": rubric, "rubric_audit": audit,
                 "compliance_flags": list(comp) if i == 0 and fmt == "demo" else [],
                 "hook": hook.format(i=i, fmt=fmt)}
            runs.append(r)
    n = len(runs)
    k = sum(1 for r in runs if r["status"] == "pass")
    ship = sum(1 for r in runs if r["status"] == "pass" and r["rubric"] >= 75
               and not r["compliance_flags"])
    hooks = [r["hook"] for r in runs]
    cf = {}
    for r in runs:
        for f in r["compliance_flags"]:
            cf[f] = cf.get(f, 0) + 1
    return {"summary": {
        "runs": n, "e2e_pass": {"k": k, "rate": round(k / n, 4)},
        "shippable": {"k": ship, "rate": round(ship / n, 4)},
        "rubric": {"mean": round(sum(r["rubric"] for r in runs) / n, 1),
                   "audit_mean": round(sum(r["rubric_audit"] for r in runs) / n, 1),
                   "selection_mean": rubric},
        "compliance_flag_counts": cf,
        "hooks": {"distinct_ratio": distinct if distinct is not None else
                  round(len(set(hooks)) / n, 4), "distinct2": distinct2 or 0.2}},
        "runs": runs}


def _stats(base, cand, hbase=None, hcand=None):
    from vsp.improve import decide as D
    return {"golden": D.paired(base, cand),
            "holdout": D.paired(hbase or base, hcand or cand)}


def check_decide_synthetic():
    from vsp.improve import decide as D
    probs = []
    if D.mcnemar_exact(0, 0) != 1.0 or abs(D.mcnemar_exact(5, 0) - 0.0625) > 1e-9:
        probs.append("mcnemar_exact wrong")
    base = _card(hook="same")
    many_fail = {f"p{i}|{f}|human|1" for i in range(6) for f in ("demo", "review")}
    cases = [
        ("identical", base, base, {}, None, True, "ACCEPT", None),
        ("e2e regression", base, _card(fail=many_fail, hook="same"), {}, None, True,
         "REJECT", "R1-e2e"),
        ("rubric drop", base, _card(rubric=90.0, audit=100.0, hook="same"), {}, None, True,
         "REJECT", "R3-rubric-ci"),
        ("audit drop", base, _card(audit=98.0, hook="same"), {}, None, True, "REJECT",
         "R4-audit"),
        ("compliance flag", base, _card(comp=("R05",), hook="same"), {}, None, True,
         "REJECT", "R6-compliance"),
        ("self-test red", base, base, {}, None, False, "REJECT", "R7-selftest"),
        ("guard finding", base, base, {"guard": ["rules.REGISTRY lost D139 (script)"]},
         None, True, "REJECT", "R9-guard"),
        ("missing runs", base, _card(hook="same", drop={"p0|demo|human|1"}), {}, None, True,
         "REJECT", "R8-coverage"),
    ]
    for name, b, c, kw, _x, st_ok, want, rule in cases:
        dec = D.decide(_stats(b, c), st_ok, guard_findings=kw.get("guard"))
        if dec["verdict"] != want or (rule and not any(rule in r for r in dec["reasons"])):
            probs.append(f"{name}: {dec['verdict']} {dec['reasons'][:2]} (want {want} {rule})")
    # holdout lower while golden is flat
    hb = _card(rubric=100.0, hook="same")
    hc = _card(rubric=99.8, audit=100.0, hook="same")
    dec = D.decide(_stats(base, base, hb, hc), True)
    if not any("R5-not-lower" in r for r in dec["reasons"]):
        probs.append(f"holdout-lower not caught: {dec['reasons']}")
    # promote extras: vacuous pack, diversity drop, the expected win
    div_base = _card(hook="h{i}", distinct=0.30)
    dec = D.decide(_stats(div_base, div_base), True, require_change=True,
                   require_diversity=True)
    if not any("R10-non-vacuous" in r for r in dec["reasons"]):
        probs.append("vacuous pack not rejected")
    lower = _card(hook="x{i}", distinct=0.25)
    dec = D.decide(_stats(div_base, lower), True, require_change=True, require_diversity=True)
    if not any("R11-diversity" in r for r in dec["reasons"]):
        probs.append(f"diversity drop not rejected: {dec['reasons']}")
    win = _card(hook="w{i}-{fmt}", distinct=0.40)
    dec = D.decide(_stats(div_base, win), True, require_change=True, require_diversity=True)
    if dec["verdict"] != "ACCEPT":
        probs.append(f"diversity win with no quality loss rejected: {dec['reasons']}")
    return probs


def _fake_ab(base, cand, hbase=None, hcand=None, st_ok=True):
    from vsp.improve import decide as D
    hbase, hcand = hbase or base, hcand or cand

    def run_ab(*a, **k):
        return {"stats": {"golden": D.paired(base, cand), "holdout": D.paired(hbase, hcand)},
                "selftest": {"ok": st_ok, "runs": [{"python": "stub", "version": "stub",
                                                    "rc": 0 if st_ok else 1}]},
                "results": {"base": {"golden": base, "holdout": hbase},
                            "cand": {"golden": cand, "holdout": hcand}},
                "seeds": "1", "raw": {}, "compare": {}}
    return run_ab


def check_promote_flow():
    from vsp.improve import abtest as A
    from vsp.improve import ledger
    from vsp.improve import packs as P
    from vsp.improve import promote as PR
    probs = []
    d = tempfile.mkdtemp(prefix="vsp-sc-learned-")
    try:
        with _env(VSP_LEARNED_DIR=d):
            os.makedirs(C.hook_packs_dir(), exist_ok=True)
            good = {"schema_version": 1, "id": "sc-good", "status": "proposed",
                    "families": {"curiosity-gap": ["Nobody warns you about {product}."]},
                    "provenance": {"source": "selfcheck"}}
            bad = dict(good, id="sc-bad")
            gp = C.write_json(os.path.join(C.hook_packs_dir(), "2026-01-01-01.json"), good)
            bp = C.write_json(os.path.join(C.hook_packs_dir(), "2026-01-01-02.json"), bad)
            base = _card(hook="h{i}", distinct=0.30)
            win = _card(hook="w{i}-{fmt}", distinct=0.40)
            worse = _card(hook="w{i}-{fmt}", distinct=0.40, rubric=92.0)
            stub_trees = lambda *a, **k: (tempfile.mkdtemp(prefix="vsp-sc-t-"), "b", "c", "stub")
            with _patch(PR, "prepare_trees", stub_trees), _patch(A, "run_ab", _fake_ab(base, win)):
                r1 = PR.promote(gp, budget="small")
            with _patch(PR, "prepare_trees", stub_trees), _patch(A, "run_ab", _fake_ab(base, worse)):
                r2 = PR.promote(bp, budget="small")
            s1 = (C.read_json(gp) or {}).get("status")
            s2 = (C.read_json(bp) or {}).get("status")
            if r1["verdict"] != "ACCEPT" or s1 != "approved":
                probs.append(f"good pack: {r1['verdict']} / {s1} {r1['decision']['reasons'][:2]}")
            if r2["verdict"] != "REJECT" or s2 != "rejected":
                probs.append(f"regressing pack: {r2['verdict']} / {s2}")
            ev = ((C.read_json(gp) or {}).get("provenance") or {}).get("evidence", {})
            if (ev.get("promote") or {}).get("verdict") != "ACCEPT" or \
                    not (ev.get("promote") or {}).get("diversity"):
                probs.append("approved pack lacks promote evidence + diversity")
            kinds = [(e["kind"], e["subject"], e["verdict"]) for e in ledger.entries()]
            if ("promote", "sc-good", "ACCEPT") not in kinds or \
                    ("promote", "sc-bad", "REJECT") not in kinds:
                probs.append(f"ledger entries {kinds}")
            ids, _added, _w = P.load_into({"curiosity-gap": [], "bold-claim": []},
                                          C.hook_packs_dir(), known={"product"})
            if ids != ["sc-good"]:
                probs.append(f"only the approved pack may load: {ids}")
            try:
                PR.promote(gp)
                probs.append("promoting an approved pack must refuse")
            except C.ImproveError:
                pass
    finally:
        shutil.rmtree(d, ignore_errors=True)
    return probs


def check_verify_flow():
    from vsp.improve import abtest as A
    from vsp.improve import guard as G
    from vsp.improve import verify as V
    probs = []
    d = tempfile.mkdtemp(prefix="vsp-sc-learned-")
    try:
        with _env(VSP_LEARNED_DIR=d):
            def fake_mat(ref, dest, repo=None):
                os.makedirs(dest, exist_ok=True)
                return {"kind": "dir", "ref": ref, "path": dest, "sha": ref[:7], "dirty": False}
            base = _card(hook="same")
            ev_clean = {"guarded_changed": [], "yardstick_changed": [], "findings": [],
                        "registry": {"base": 1, "cand": 1},
                        "selftest_cases": {"base": 1, "cand": 1, "legacy_base": 1,
                                           "legacy_cand": 1}}
            with _patch(V, "materialize", fake_mat), _patch(A, "run_ab", _fake_ab(base, base)), \
                    _patch(G, "check", lambda b, c, python=None: ([], ev_clean)):
                ok = V.verify("base0000", "cand0000", budget="small")
            weak = dict(ev_clean, findings=["lexicon.ABSOLUTE no longer matches 'miracle'"],
                        guarded_changed=["vsp/lexicon.py"])
            with _patch(V, "materialize", fake_mat), _patch(A, "run_ab", _fake_ab(base, base)), \
                    _patch(G, "check", lambda b, c, python=None: (weak["findings"], weak)):
                bad = V.verify("base0000", "cand1111", budget="small")
            if ok["verdict"] != "ACCEPT":
                probs.append(f"clean verify: {ok['decision']['reasons']}")
            if bad["verdict"] != "REJECT" or not any("R9-guard" in r
                                                      for r in bad["decision"]["reasons"]):
                probs.append(f"weakening not rejected: {bad['decision']['reasons']}")
            for r in (ok, bad):
                for p in r.get("evidence") or []:
                    if not os.path.isfile(p if os.path.isabs(p) else os.path.join(C.REPO, p)):
                        probs.append(f"missing evidence file {p}")
    finally:
        shutil.rmtree(d, ignore_errors=True)
    return probs


def check_weakening_guard():
    from vsp.improve import guard as G
    probs = []
    snap = G.snapshot(C.REPO)
    if snap.get("errors"):
        return [f"snapshot errors on this tree: {snap['errors']}"]
    if G.compare(snap, snap):
        probs.append(f"identical snapshots produced findings: {G.compare(snap, snap)[:3]}")
    if not G.regex_samples(r"\b(?:miracle|cures?)\b", 2):
        probs.append("regex_samples produced nothing")

    def mutated(fn):
        s = copy.deepcopy(snap)
        fn(s)
        return G.compare(snap, s)

    def drop_rule(s):
        s["registry"] = [r for r in s["registry"] if r["id"] != "D141"]

    def downgrade(s):
        for r in s["registry"]:
            if r["id"] == "D139":
                r["severity"] = "warn"

    def lose_alt(s):
        it = s["lexicon"]["ABSOLUTE"]
        it["pattern"] = it["pattern"].replace(r"\bmiracle\b|", "")

    def lose_list_item(s):
        s["lexicon"]["SOCIAL_PROOF"]["items"] = s["lexicon"]["SOCIAL_PROOF"]["items"][:-1]

    def allow_grow(s):
        s["lexicon"]["LABEL_WORDS"]["items"].append("lamp")

    def limit_up(s):
        s["lexicon"]["MAX_HASHTAGS"]["value"] = 30

    def drop_case(s):
        s["selftest"]["legacy"] -= 1
        s["selftest"]["legacy_cases"] = s["selftest"]["legacy_cases"][1:]
        s["selftest"]["all"] -= 1

    def drop_check(s):
        s["gates"]["checks"] = s["gates"]["checks"][1:]

    for name, fn, needle in (("removed registry entry", drop_rule, "lost D141"),
                             ("compliance rule removed", drop_rule, "compliance rules missing"),
                             ("severity downgrade", downgrade, "downgraded"),
                             ("lost regex alternative", lose_alt, "miracle"),
                             ("lost pattern in a list", lose_list_item, "SOCIAL_PROOF"),
                             ("allow-list growth", allow_grow, "LABEL_WORDS"),
                             ("loosened limit", limit_up, "MAX_HASHTAGS"),
                             ("dropped legacy self-test case", drop_case, "legacy cases dropped"),
                             ("removed gate check", drop_check, "gates lost checks")):
        f = mutated(fn)
        if not any(needle in x for x in f):
            probs.append(f"{name}: not found ({f[:2]})")
    return probs


def check_refresh_dedupe():
    from vsp.improve import refresh as R
    probs = []
    before = {s: C.sha256_file(C.suite_path(s)) for s in ("golden", "holdout")}
    texts = [("This $15 sunrise lamp changed my mornings", 100000, "t"),
             ("the heated eye mask everyone wants", 90000, "t"),
             ("Nobody talks about this rechargeable desk fan", 50000, "t")]
    d = tempfile.mkdtemp(prefix="vsp-sc-refresh-")
    try:
        res = R.golden_refresh(max_new=5, dry_run=True, texts=texts)
        got = [r["prompt"] for r in res["added"]]
        if "rechargeable desk fan" not in got:
            probs.append(f"trending phrase not proposed: {got}")
        if any("sunrise lamp" in g or "eye mask" in g for g in got):
            probs.append(f"golden/holdout duplicates proposed: {got}")
    finally:
        shutil.rmtree(d, ignore_errors=True)
    after = {s: C.sha256_file(C.suite_path(s)) for s in ("golden", "holdout")}
    if before != after:
        probs.append("golden/holdout changed during golden-refresh")
    return probs


CHECKS = (("llm-meta-http", check_llm_meta_http),
          ("llm-complete-json", check_llm_complete_json),
          ("packs-contract", check_packs_contract),
          ("decide-synthetic", check_decide_synthetic),
          ("weakening-guard", check_weakening_guard),
          ("promote-flow", check_promote_flow),
          ("verify-flow", check_verify_flow),
          ("refresh-dedupe", check_refresh_dedupe),
          ("evolve-no-holdout", check_evolve_no_holdout),
          ("evolve-slot-safe", check_evolve_slot_safe))


def selfcheck(verbose=False, only=None):
    """-> (ok, lines). Hermetic; restores every env var and patch it touches."""
    lines, ok = [], True
    t_all = time.time()
    tmp = tempfile.mkdtemp(prefix="vsp-improve-selfcheck-")
    repo_learned = C.learned_dir()
    snap_before = _tree_digest(os.path.join(C.REPO, "learned"))
    scrub = {k: None for k in ("VSP_LLM_PROVIDER", "VSP_LLM_MODEL", "VSP_LLM_API_KEY",
                               "MODEL_API_KEY", "META_API_KEY", "ANTHROPIC_API_KEY",
                               "OPENAI_API_KEY", "VSP_LLM_URL", "VSP_LLM_BASE_URL",
                               "VSP_NO_HOOK_PACKS")}
    try:
        with _env(VSP_LEARNED_DIR=os.path.join(tmp, "learned"),
                  VSP_VIRAL_DB=os.path.join(tmp, "absent", "viral.db"),
                  VSP_IMPROVE_TMP=os.path.join(tmp, "work"), **scrub):
            os.makedirs(C.hook_packs_dir(), exist_ok=True)
            for name, fn in CHECKS:
                if only and name not in only:
                    continue
                t0 = time.time()
                try:
                    probs = fn() or []
                except Exception as e:  # noqa: BLE001 — a crashing check fails
                    probs = [f"crashed: {type(e).__name__}: {e}"] + (
                        [traceback.format_exc()[-600:]] if verbose else [])
                dt = time.time() - t0
                if probs:
                    ok = False
                    lines.append(f"FAIL {name} ({dt:.1f}s)")
                    lines += [f"     - {p}" for p in probs[:8]]
                else:
                    lines.append(f"ok   {name} ({dt:.1f}s)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if _tree_digest(os.path.join(C.REPO, "learned")) != snap_before:
        ok = False
        lines.append("FAIL hermeticity: the repo's learned/ changed during selfcheck")
    if C.learned_dir() != repo_learned:
        ok = False
        lines.append("FAIL hermeticity: VSP_LEARNED_DIR not restored")
    lines.append(f"vsp.improve selfcheck: {'OK' if ok else 'FAILED'} — "
                 f"{sum(1 for x in lines if x.startswith('ok '))} checks passed in "
                 f"{time.time() - t_all:.1f}s on Python {sys.version.split()[0]} "
                 f"(hermetic: stub HTTP on 127.0.0.1, MockProvider, temp learned/)")
    return ok, lines


def _tree_digest(root):
    import hashlib
    h = hashlib.sha256()
    if not os.path.isdir(root):
        return "absent"
    for dp, dns, fns in sorted(os.walk(root)):
        dns.sort()
        for fn in sorted(fns):
            p = os.path.join(dp, fn)
            h.update(os.path.relpath(p, root).encode())
            try:
                with open(p, "rb") as f:
                    h.update(hashlib.sha256(f.read()).digest())
            except OSError:
                pass
    return h.hexdigest()


if __name__ == "__main__":
    good, out = selfcheck(verbose="-v" in sys.argv)
    print("\n".join(out))
    sys.exit(0 if good else 1)
