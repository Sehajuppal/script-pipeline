# SO-3 Delivery & Selection — notes (branch `ws/delivery`, from `a87fab6`)

## Results

All numbers come from `tools/smoke_delivery.py`, run hermetically (a fixture viral.db and `VSP_FIXTURE_OK=1`). The matrix is evals/golden.jsonl × 5 formats × 2 presenters × seeds 1–3 = 990 scripts. Scripts are generated in-process with the current (pre-SO-1) maker and foundation gates. Python 3.9.25 and 3.12.14 give identical numbers.

| metric | result |
|---|---|
| raw gate-1 pass (baseline maker) | 15/990 = 1.5% |
| `repair(script, gate1)` → gate-1 pass | **926/990 = 93.5%** (left: D44 stage verbs 38, TAG-MISMATCH 30, D74 4) |
| gate-2 pass on those gate-1 passes | **837/926 = 90.4%** (baseline shot list on the same scripts: 610/926 = 65.9%) |
| gate-2 failures caused by the shot list (D47/D48/D43-warning/drift/D46/boilerplate) | **0/926 = 0.0%** (baseline shot list: 316 failing scripts — D48 ×371 msgs, D47 ×90, plus the same D36 ×89) |
| the only gate-2 failure left | D36 ×89: "same body" in the **maker's** transformation EVIDENCE dialogue |
| gate-2 pass after the stage-8 repair `repair(s, select.gate_cascade)` | **926/926 = 100%** |
| recommended stage 3–9 flow (select N=8 over gate_cascade → repair → bundle → gate 2), seed 701, 330 cells | **316/330 = 95.8%** end-to-end (5 won by selection, 311 by repair; left: TAG-MISMATCH 10, D44 4 — every candidate carries them) |
| caption lint | scripts with ≥1 warning: 19/926 = 2.1%; cues: 64/9326 = 0.7%; all `cps > 20` on inherently dense lines |
| schema validation failures | **0/990** raw maker outputs, 0/990 after repair; all 17 self-test fixtures validate except the legacy bad ones (<3 beats / empty t) |
| manifest replay (real `pipeline.py` runs) | **3/3** script.json sha256 reproduced, plus mismatch/missing-manifest negative checks |
| export round-trip (`write_exports` → parse back) | 25/25 |
| other durations (seed 1, 330 cells each) | 20/45/60/90 s: 0 shot-list gate-2 failures, D36 only. 15 s: nothing repairs. |
| historical `outputs/*/script.json` | the 4 gate-1 passes all pass gate 2 |

The target was "gate 2 ≥ 98% on gate-1 passes". Measured literally (`repair(s, gate1)` then gate 2), the result is 90.4%. The whole 9.6% shortfall is D36 maker content, which make_shotlist must not rewrite: the bundle has to render the script verbatim, and gate 2 is right to reject it. The failure goes away once any one of these holds:

- SO-1 fixes the EVIDENCE template.
- The pipeline selects and repairs over `select.gate_cascade`. That gives 100%, and it is the recommended wiring below.
- The contract team lifts D36 into gate 1.

Self-test was green on 3.9 and 3.12 at every commit.

## Commits (oldest first)

| sha | commit |
|---|---|
| 09ba363 | vsp/repair: rule-keyed deterministic repair loop (D150) |
| 679a761 | make_shotlist: D47/D48 shot grammar, exact windows, D64 brief fixes, D138 label |
| 50dff7c | vsp/trace + vsp/select: trace.jsonl (D153) and best-of-N selection (D149) |
| d816b1d | vsp/captions + vsp/exporters (D152) + tools/smoke_delivery.py |
| 33c9e75 | vsp/schema + schema/script.schema.json (D152) |
| a60f1c7 | vsp/manifest: run manifest + replay (D153) |
| 270a036 | vsp/llm: optional advisory LLM judge |
| a503cbd | make_shotlist: showcase keeps product framing; a maker direction leads a split |
| ff5259c | tools/smoke_delivery: flow section |
| adc7768 | make_shotlist: capitalise the default persona name |
| (this) | docs/ws-delivery-notes.md |

**Files touched.**
- Modified: `make_shotlist.py`.
- New: `vsp/{repair,select,trace,captions,exporters,schema,manifest,llm}.py`, `schema/script.schema.json`, `tools/smoke_delivery.py`, and this file.
- Nothing outside SO-3 ownership was edited.

## Public APIs

**make_shotlist.py.** The CLI is unchanged. The DELIVERABLE, RENDER_SPEC and DO_NOT constants are byte-identical, and DELIVERABLE is emitted under `## DELIVERABLE (standing)`.
- `build_shots(d) -> (shots, vo_lines)`. Each shot has these keys: `n, group, t, s, e, beat, direction, camera, explicit, on_screen, staging, dialogue, delivery, rehook, match_cut`.
- `render_bundle(d, shots, vo_lines, refs=None) -> str`
- `build_bundle(d, refs=None) -> (bundle, shots, vo_lines)`
- Helpers: `presenter_identity(d)`, `product_description(d)`, `product_phrase(prompt)`, `niche_setting(d)`, `niche_style_notes(d)`, `clean_meta(text)`, `split_on_screen(text) -> (display, notes)`, `shot_visual_prompt(sh, identity, product_desc, setting, light)`, `niche_references(niche, k=3, db_path=None)`, `slugify(prompt)`, `parse_t(t)`.

**vsp/repair.py.**
- `repair(script, gate_fn, max_rounds=3) -> (script, log, passed)`. Each log entry is `{round, rule, target, action}`. After each round a `regate` entry records the before→after failure counts.
- Building blocks: `retime(script, rules, max_trims=24)`, `compress_on_screen(text, max_tokens=12, max_chars=None)`, `compress_paragraph_cards(script, cps=False)`, `strip_parentheticals`, `blank_duplicate_rehooks`, `fix_single_test_numbering`, `name_transformation_subject`, `d36_subject`, `rule_of(msg)`.
- `gate_fn` may return strings or `{rule, severity, message}` findings. Warning, info and note findings are ignored.

**vsp/select.py.**
- `run(gen_fn, seed, n, gate_fn=None, score_fn=None, dup_threshold=0.5, trace=None)` returns `{winner, script, seeds, candidates, best_failing, scripts}`.
- Each candidate record: `{index, seed, error, gate1, passed, rubric{score, selection_score, audit_score}, hook, rank, duplicate_of, hook_jaccard}`.
- `gate_cascade(script, refs=None)` runs gate 1, then the shot list, then gate 2.
- Helpers: `summary(result)`, `jaccard(a, b)`, `trigrams(text)`, `hook_of(script)`.
- Call it with keyword arguments. The upgrade plan lists the order as `(gen_fn, n, seed)`; the SO-3 brief lists `(gen_fn, seed, n)`. The latter is implemented.

**vsp/captions.py.**
- `build_cues(script, shots=None)` returns a list of `{index, start, end, text, lines, beat, source, words[{word,start,end}]}`.
- Output and checks: `to_srt(cues)`, `to_vtt(cues)`, `to_remotion(cues)` (a list of Caption), `remotion_json(cues)`, `lint(cues) -> [str]`, `stats(cues)`, `break_lines(tokens, max_chars=32, max_lines=2)`.
- Constants: FPS 30, MAX_LINES 2, MAX_CHARS 32, MIN_DUR 0.83, MAX_DUR 7.0, TARGET_CPS 17, WARN_CPS 20, TIMING_SOURCE "estimate".

**vsp/exporters.py.** `shotlist_csv(shots) -> str`, `shots_json(script, shots, vo_lines) -> dict`, `write_exports(outdir, script, shots, vo_lines, cues=None) -> {name: path}`.

**vsp/schema.py.** `SCRIPT_SCHEMA`, `validate(obj, schema=None) -> [str]`, `schema_text()`, `load_schema()`, `write_schema()`. CLI: `python3 -m vsp.schema --write | --check | FILE...`.

**vsp/manifest.py.**
- Hashing: `canonical_json(obj)`, `sha256_{bytes,text,json,file}`.
- Inputs: `git_info(repo)`, `code_hashes(repo)`, `research_pack_info(path)`, `output_hashes(outdir, exclude=("manifest.json","trace.jsonl"))`.
- `build_manifest(**parts)`, `write_manifest(outdir, m, name="manifest.json")`, `load_manifest(path)`.
- Replay: `replay_argv(m)`, `replay(manifest_path, python=sys.executable, pipeline=None, keep=False, timeout=600, repo=None) -> (ok, details)`, `replay_report(ok, details)`. CLI: `python3 -m vsp.manifest --replay FILE`.

**vsp/trace.py.**
- `Trace(path=None, trace_id=None, **resource)` has `.span(name, **attrs)`, a context manager that returns a `Span` with `.set(**attrs)` and `.end()`.
- Other Trace methods: `.event(name, **attrs)`, `.eval_result(name, label, score=None, explanation=None, **attrs)`, `.gate_results(stage, messages)`, `.timings_ms()`, `.flush()`, `.close()`.
- Module function: `read(path)`.

**vsp/llm.py.**
- `available(env=None)`, `get_provider(env=None)`, `config_from_env(env=None)`.
- `judge_pair(a_text, b_text, criterion, provider=None, max_tokens=200, length_tolerance=None) -> {verdict, votes, consistent, provider, model, criterion}`.
- `judge_scripts(a, b, criterion=..., **kw)`, `render_candidate(script)`, `parse_verdict(text)`.
- Providers: `AnthropicProvider`, `OpenAIProvider`, `MockProvider(fn=None, replies=None)`. Errors raise `LLMError`.

## Design decisions

- **Shots are the timeline of record.**
  - A valid script window is used exactly. An item without a window is sized at the cursor from its dialogue plus rehook words, and pushes later windows only if they would overlap by more than 0.1 s. That only happens with legacy fixtures and never with maker output.
  - B4a runs before sizing and picks the longest follow-prefix that still fits an exact window, so it can no longer cause a D43 WARNING.
- **D48.**
  - These beats are split once they run over 3.5 s: EDUCATION, DEMO, EVIDENCE, TEACHING, STORY, RITUAL, REJECTION and COMMENT BAIT. IMPERFECTION already carries handheld movement, so it is split only above 5 s.
  - Sub-shots are about 2.5 s each (always ≤ 3.1 s) and cycle through beat-native framings.
  - Sub-shot a keeps the delivery, the on-screen text and any maker-supplied direction. The last sub-shot keeps the rehook and match-cut; the old code dropped the rehook.
  - The hook, PAYOFF and CTA are never split. They get a camera move instead.
  - This matches `vsp/timing.py`: SPLITTABLE beats absorb slack and MOVING beats carry a move.
- **D47.**
  - A rotation pass checks gate 2's own predicate on the rendered block lines. On a third consecutive talking head it reframes that shot to a beat-native alternate: the bait becomes a phone close-up, the payoff a low-angle hero shot, the hook a medium-wide. Otherwise it uses a rotating cutaway (product close-up, hands, reaction).
  - The bait now plays medium-wide, so payoff, bait and CTA are three different scales.
- **D64 brief.**
  - AI identity without a persona falls back to `(ai, niche)`, then `(ai, generic)`.
  - The maker's niches are keyed directly or through an alias (gadgets→tech, food/tools→kitchen), and product words override the setting (a desk lamp is shot on a desk, a tire inflator in the car).
  - PRODUCT_LOOK is an ordered word-boundary list. Anything unmatched gets a description derived from the prompt, with no price and no claims. Concept prompts get "props", never "product in hand".
  - Rule ids and meta sentences are stripped from directions and deliveries.
  - Production notes such as "(split-screen, timestamped)" are lifted out of the render-exactly on-screen text and moved into the visual prompt as `Staging:`.
  - The voice follows the persona voice and the identity's gender. Fallback and cold-open shot numbers come from the actual shots. RENDER_SPEC and the words.json line use the real slug.
  - AI briefs always carry an `## AI DISCLOSURE — frame-0 label (required)` block with the exact line `On-screen small "AI persona" label from FRAME 0, top safe zone, minimum 2 seconds, separate from hook text.` (D138). The fidelity block keeps its own copy.
- **Repair.**
  - When the text cannot fit the duration, the order of trims is: sentence-boundary trims of the longest dialogue, then clause trims (never leaving a stub under 4 words), then dropping re-hooks (a clause stub like "Okay." is worse).
  - A restore pass then gives back words the greedy trims over-cut, but never restores a D44 stage verb.
  - D36 is keyed like every other rule. "Same body" becomes the subject named in the prompt (hair / skin / lashes / room / car / dog / cat), else "same angle".
- **Selection.** `gate_cascade` makes candidates that would fail gate 2 lose selection; this is the cheapest-first cascade from labs-techniques §2.1. Duplicate marking is informational only, because the winner can never be a duplicate. Audit checks never select.
- **Captions.**
  - Timing comes from the shot-list timeline. Dialogue starts at the window start; the rehook ends at the window end.
  - Cues come from a minimum-cost DP segmentation.
  - Reading-time relief: a cue may linger or lead into free time by up to 0.5 s, and back-to-back cues can slide their shared boundary to balance cps.
  - Gaps are chained to 2 frames.
  - `captions.json` is `{timing_source, fps, format, captions: Caption[]}`, and `confidence` is null because no recognizer ran.
- **Manifest/replay.** Replay rebuilds the CLI from `manifest["args"]` (argparse dests), falling back to `argv`. It pins the recorded research pack, reruns into a temp `--out-dir`, and compares the script.json sha256. Input drift (pack, RULES, personas, code, Python version) is reported as warnings.

## Known limitations and hand-offs

- **SO-1 (maker content).**
  - D36: the EVIDENCE template says "Same body, same light" for non-body products (89 gate-2 failures). It should name the subject, as RULES D36 says.
  - D44: TEACHING says "show the …" and PAYOFF says "…, on camera." (38 unrepairable).
  - Niche routing: "office chair" contains "hair" and routes to beauty, causing the tag mismatch (30).
  - At 15 s nothing fits: six beats' minimum windows exceed the 12 s body, so budget-aware banks are needed.
  - Hooks barely vary across sub-seeds ("Nobody mentions the lock flaw." ×8), so best-of-N marks near-duplicates.
- **Repair is lossy on the old maker.** It made about 3.3k sentence/clause trims and about 1.7k rehook drops over 990 scripts. With the content-sized maker it should rarely trigger. 4/990 still overflow D74 by 0.3–1.6 s, where the only cut left would leave a stub.
- **Rule message formats.** D93 and D142 repairs key on rule ids. D93 finds duplicates itself (exact match, then same promise, then trigram Jaccard ≥ 0.5). D142 compresses on-screen text to ≤ 20 cps over its window. Both assume the contract team's messages start with `D93:` / `D142:` (or come as structured findings).
- **Captions are estimates.** The remaining cps > 20 cues are dense script lines, for example the routine IMPERFECTION beat, where the maker's fixed 2.5 s window leaves its rehook uncounted. Remotion `confidence` is null.
- **D47 follows the gate's predicate.** The gate only counts "to camera" before the first "on-screen", so semantic scale variety depends on the beat grammar above, not on the check.
- **Schema validator.** It is a subset (no anyOf/oneOf/format/uniqueItems). The schema allows additional properties, and schema-valid does not mean gate-valid.
- **Replay** assumes store_true-style flags (argparse dest→flag), so `BooleanOptionalAction` False values are dropped. The manifest's `code` hashes cover top-level `*.py` and `vsp/**/*.py`; the schema file is hashed separately.
- **LLM judge** was tested with MockProvider and local HTTP stubs of both APIs, but never against the live APIs. There are no retries or backoff, and it is advisory only.

## Wiring for the integrator (`pipeline.py`)

Keep every legacy line (`gate 1 (script): …`, `gate 2 (brief): …`) and the order of the gate messages. Three constraints:

- **Never repair `--script-json` input.** The self-test's bad fixtures must keep failing with their original messages, and validation stays read-only (D79).
- **Never schema-check before gate 1.** Schema errors would pre-empt the legacy messages.
- **Add the new artifacts to `ARTIFACTS`:** `captions.srt`, `captions.vtt`, `captions.json`, `shotlist.csv`, `shots.json`, `manifest.json`, `trace.jsonl`, `gate-report.json`. That way a failing run never leaves stale exports.

```python
import vsp, make_shotlist
from vsp import (select as vsel, repair as vrep, captions, exporters,
                 schema as vschema, manifest as vman, trace as vtrace, rubric)

args_record = dict(vars(a))              # right after parse_args, before any mutation
if a.replay:                             # --replay manifest.json
    ok, det = vman.replay(a.replay); print(vman.replay_report(ok, det)); sys.exit(0 if ok else 1)
tr = vtrace.Trace(os.path.join(outdir, "trace.jsonl"),
                  **{"service.name": "viral-script-pipeline", "service.version": vsp.__version__})
sel, repairs, selected, g1, g2 = None, [], None, None, None

# stage 3 GENERATE + 4 GATE 1 + 5 SELECT (skipped for --script-json)
def gen_fn(seed):
    return vsm.generate(a.prompt, presenter=a.presenter, fmt=a.format, duration=a.duration,
                        seed=seed, use_research=not a.no_research, persona=a.persona)
with tr.span("stage.generate_select", candidates=a.candidates):
    sel = vsel.run(gen_fn, seed=a.seed, n=a.candidates, gate_fn=vsel.gate_cascade,
                   score_fn=rubric.score, trace=tr)
report.append(vsel.summary(sel))
script = sel["script"]
if sel["winner"] is not None:
    selected = {"index": sel["winner"], "seed": sel["seeds"][sel["winner"]], "via": "selection"}

# stage 6 REPAIR — only when nothing passed; try best_failing in order, <= 3 rounds each
if script is None:
    if not sel["best_failing"]:          # every candidate crashed -> STAGE 1 FAILED (as today)
        ...
    with tr.span("stage.repair"):
        best, best_n = None, None
        for idx in sel["best_failing"]:
            s2, log, ok = vrep.repair(sel["scripts"][idx], vsel.gate_cascade, max_rounds=3)
            repairs.append({"candidate": idx, "passed": ok, "log": log})
            n_fail = len(vsel.gate_cascade(s2))
            if best is None or n_fail < best_n:
                best, best_n = s2, n_fail
            if ok:
                selected = {"index": idx, "seed": sel["seeds"][idx], "via": "repair"}
                break
        script = best                    # still failing -> gate 1 / gate 2 below fail loudly
# write script.json; GATE 1 exactly as today (g1 = gate1(script)); tr.gate_results("gate1", g1)

# stage 7 SHOT LIST (unchanged call; headings unchanged, brief.md split unchanged)
bundle_text, shots, vo_lines = make_shotlist.build_bundle(script)
# GATE 2 exactly as today (g2 = gate2(bundle_text, script)); tr.gate_results("gate2", g2)

# stage 9 EXPORT — only when both gates passed (D152)
errs = vschema.validate(script)
if errs:
    report.append("stage 9 (export): FAIL — schema: " + "; ".join(errs[:5])); finish(1)
cues = captions.build_cues(script, shots)
paths = exporters.write_exports(outdir, script, shots, vo_lines, cues=cues)
lint = captions.lint(cues)
report.append(f"stage 9 (export): OK — {', '.join(sorted(paths))}; caption lint "
              f"{len(lint)} warning(s)")          # lint is advisory, never a failure

# stage 10 MANIFEST + TRACE — every run, pass or fail: put this inside finish(code),
# AFTER validation-report.md is written (the manifest hashes it)
m = vman.build_manifest(argv=sys.argv[1:], args=args_record, seed=a.seed,
                        candidate_seeds=sel["seeds"] if sel else [],
                        research_pack=config.research_pack_path(), route=route, research=pack_meta,
                        candidates=sel["candidates"] if sel else [], selected=selected,
                        repairs=repairs, gates={"gate1": g1, "gate2": g2},
                        outdir=outdir, timings_ms=tr.timings_ms(), exit_code=code)
vman.write_manifest(outdir, m)
tr.close()
```

**Optional pieces.**
- `--llm-judge`: take the top two passing candidates by `rank` and call `vsp.llm.judge_scripts(s_a, s_b)` when `vsp.llm.available()`. Record the result with `tr.eval_result("llm.pairwise", res["verdict"], explanation=...)` and in the manifest. It must never change the winner or a gate.
- The committed schema can be drift-checked in CI with `python3 -m vsp.schema --check`.
