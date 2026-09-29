# WS-INT notes — the 10-stage orchestrator (`pipeline.py`)

Branch `ws/int`. Owner: integration. Stdlib only; runs on Python 3.9 and 3.12.
Rules: RULES.md D147–D153. Plan: `docs/UPGRADE-PLAN.md` §2.

## 1. Stages

One `Run` object executes the stages in order. `finish()` is the only exit
point: it writes `validation-report.md`, `gate-report.json`, `manifest.json`
and `trace.jsonl` on **every** run, pass or fail.

| # | name | what happens | module(s) | statuses |
|---|---|---|---|---|
| 1 | route | input guardrails + 3-voter router (maker / lexicon / research). Input errors, including an unknown `--persona`, stop the run as `STAGE 1 FAILED`, status `input_error`. `--strict-route` fails when agreement < 2/3. | `vsp/router.py` | OK · FAIL · crash |
| 2 | research | pack loaded (before stage 1, because the router's research voter reads it), validated, sha256-pinned. A stale pack (> 48 h) only warns; `--require-fresh-research` fails on stale or missing. | `vsp/research.py` | OK · SKIPPED · FAIL |
| 3 | generate | N candidates (`--candidates`, default 8) from `vsp.seeding.candidate_seeds(seed, N)`. Candidate 0 is the raw `--seed`. A crashing candidate is a warning; the stage fails only if every candidate crashes. | `viral_script_maker.generate`, `vsp/select.py` | OK · crash |
| 4 | gate 1 | every candidate goes through `vsp.select.gate_cascade` (gate 1 → shot list → gate 2, cheapest first) | `vsp/gates.py`, `vsp/select.py` | OK (≥ 1 passes gate 1) · FAIL |
| 5 | select | the best rubric `selection_score` among cascade passes (ties go to the lowest index; audit-only checks never select). `--llm-judge` is advisory only. | `vsp/rubric.py`, `vsp/select.py`, `vsp/llm.py` | OK · FAIL (nothing passed) |
| 6 | repair | runs only when nothing passed: `vsp.repair.repair` on each `best_failing` candidate in order, ≤ 3 rounds each, stopping at the first that passes. If none passes, the best failing candidate (fewest failures) is reported. | `vsp/repair.py` | SKIPPED · OK · FAIL |
| — | *gate 1 line* | gate 1 on the chosen script (`script.json` is written first). This legacy line is the gate-1 verdict. | `vsp/gates.py` | PASS · FAIL |
| 7 | shot list | `make_shotlist.build_bundle` → `bundle.md`, `brief.md` | `make_shotlist.py` | OK · crash |
| 8 | gate 2 | brief gate, then the legacy gate-2 line | `vsp/gates.py` | OK · FAIL |
| 9 | export | JSON-Schema check, then captions (SRT/VTT/Remotion JSON), `shotlist.csv`, `shots.json`. Passing runs only (D152). | `vsp/schema.py`, `vsp/captions.py`, `vsp/exporters.py` | OK · FAIL · crash |
| 10 | manifest | `gate-report.json`, `manifest.json`, `trace.jsonl`. Its line is written **before** the manifest, because the report is hashed into it. | `vsp/manifest.py`, `vsp/trace.py` | OK · crash |

With `--script-json FILE`, stages 3–6 are `BYPASSED — finished JSON supplied`.
The legacy gate-1 line is then the verdict, and `failed_stage` is 4 if it fails.
Before a run, every file in `ARTIFACTS` is deleted from the out-dir, so a
failing run never leaves a stale bundle or export behind.

Run status (`gate-report.json`, `manifest.json`, `--json`): `pass` ·
`gate1_fail` · `gate2_fail` · `input_error` · `crash` (an exception, or all
candidates crashed) · `fail` (any other stop, e.g. stage 1 `--strict-route`,
stage 2 `--require-fresh-research`, stage 9 schema). The exit code is 0 only
for `pass`. Usage errors are argparse exit 2 with no report: no prompt, an
empty-string prompt `""`, `--duration` outside 5–180, `--candidates` outside
1–64.

## 2. Report format (`validation-report.md`; stdout unless `--json`)

```
# Validation report — <prompt>
seed <seed> | <presenter> | <format> | <duration>s        (--script-json: seed <script.seed|n/a> | … | <duration_s>s)

stage N (<name>): OK|FAIL|SKIPPED|BYPASSED[ — <detail>]      one per stage, in execution order
STAGE N FAILED (<name>): <message>                            crash / input error (replaces that stage's line)
  <last 500 chars of the traceback, indented>                 exceptions only
gate 1 (script): PASS | FAIL — <m1>; <m2>; …                  after stage 6, legacy text verbatim
gate 2 (brief): PASS | FAIL — <m1>; <m2>; …                   after stage 8, legacy text verbatim
stage 10 (manifest): OK — manifest.json, trace.jsonl, gate-report.json (written after this report)

warnings: none            | warnings:\n- <source>: <message>   (≤ 20 per source per call, then "(+N more)")
```

Once a run stops, each stage it never reached gets `stage N (<name>): SKIPPED —
<reason>`, appended in number order before stage 10. The reason is `stage N
failed`, `gate 1 failed` or `gate 2 failed`. If the manifest write fails, the
stage-10 line is rewritten as `STAGE 10 FAILED (manifest): manifest/trace write
failed` plus the traceback, and the run exits 1 with status `crash`. Warning
sources are `route`, `research`, `learned`, `generate`, `gate 1`, `gate 2` and
`captions`. `evals/scorecard.py` parses the two gate lines and `STAGE 1/2
FAILED`.

Stage details:
- 1: `OK — <concept>/<niche> fit=<fit> complexity=<c> agreement=<a> -> presenter <p> (<formats>)`; strict mode fails with `FAIL — --strict-route: router agreement 0.50 < 0.67 (…)`.
- 2: `OK — research_pack.json sha256 <12 hex>, <age> h old[ (STALE)], <n> reels`. `SKIPPED` gives the `--no-research` reason or `no usable research pack (<err>) — frozen rulebook`. `FAIL — --require-fresh-research: …`.
- 3: `OK — <n> candidate(s) (seeds s0, s1, s2, s3, …); <k> crashed`
- 4: `<p>/<n> candidate(s) pass gate 1; <c>/<n> pass the cascade (gate 1 → shot list → gate 2)[; failing: <rule> ×<k>, …]`. The top 4 rule labels count cascade messages, so gate-2 messages are included.
- 5: `OK — <p>/<n> candidates passed; winner #<i> (seed <s>, selection <x>); <d> near-duplicate hooks[; llm-judge (advisory): <verdict|status>]`, or `FAIL — 0/<n> candidates passed; repair order [<first 5>]`.
- 6: `SKIPPED — candidate #<i> passed; nothing to repair`, `OK — candidate #<i> (seed <s>) repaired in <r> round(s), <a> action(s) [<rules>]; <t> candidate(s) tried`, or `FAIL — <t> candidate(s) tried, none passes; reporting #<i> (seed <s>, <f> failure(s) left)`.
- 7: `OK — <n> shot(s), <v> VO line(s) → bundle.md, brief.md` · 8: `<e> error(s), <w> warning(s)`
- 9: `OK — captions.json, captions.srt, captions.vtt, shotlist.csv, shots.json; schema valid; <n> cue(s), caption lint <w> warning(s)`, or `FAIL — schema: <e1>; …`.

Example (hermetic, `"portable door lock" --presenter ai --format review --duration 5`):

```
stage 3 (generate): OK — 8 candidate(s) (seeds 701, 984336173, 1911171281, 181501679, …); 0 crashed
stage 4 (gate 1): FAIL — 0/8 candidate(s) pass gate 1; 0/8 pass the cascade (gate 1 → shot list → gate 2); failing: D74 ×8
stage 5 (select): FAIL — 0/8 candidates passed; repair order [0, 1, 2, 3, 4]
stage 6 (repair): FAIL — 8 candidate(s) tried, none passes; reporting #0 (seed 701, 1 failure(s) left)
gate 1 (script): FAIL — D74: beats run to 8.6s but duration is 5s — timeline exceeds budget
stage 7 (shot list): SKIPPED — gate 1 failed
stage 8 (gate 2): SKIPPED — gate 1 failed
stage 9 (export): SKIPPED — gate 1 failed
stage 10 (manifest): OK — manifest.json, trace.jsonl, gate-report.json (written after this report)
```

## 3. CLI

| flag | default | effect |
|---|---|---|
| `prompt` (positional) | — | the product prompt. Use `--` before a prompt that starts with `-`. |
| `--presenter ai\|human` | human | |
| `--format` | demo | demo · talking-head · pov-vlog · transformation · review |
| `--duration N` | 30 | 5–180 s. Below 12 s some formats fail D74 loudly (§6). |
| `--seed N` | 701 | root seed; candidate 0 uses it unchanged |
| `--persona NAME` | maya (ai) | must match a `personas.json` key or display name (case-insensitive), otherwise it is a stage-1 input error. Ignored, with a warning, for `--presenter human`. |
| `--no-research` | off | stage 2 SKIPPED; frozen-rulebook maker output |
| `--out-dir DIR` | `outputs/<slug>/` | (`--script-json`: `outputs/<slug>-json-check/`); refuses to overwrite the input file (D79, exit 2) |
| `--script-json FILE` | — | gates only (stages 3–6 BYPASSED); the input is never rewritten |
| `--candidates N` | 8 | 1–64. `1` gives the pre-2.0 output of `generate(prompt, seed)`. |
| `--replay MANIFEST` | — | re-runs the recorded args with the recorded `ENV_KEYS` pinned (`VSP_VIRAL_DB`, `VSP_FIXTURE_OK`, `VSP_RESEARCH_PACK`, `VSP_LEARNED_DIR`, `VSP_NO_HOOK_PACKS`, `VSP_NO_PRIORS`, `VSP_DOSSIER_DIR`; recorded null = unset; a recorded `VSP_VIRAL_DB`/`VSP_LEARNED_DIR` that no longer exists warns and keeps the current value) and the recorded research pack. Exit 0 only if the script.json sha256 **and** the exit code reproduce. Warns on code, pack, RULES, personas and learned-state drift. |
| `--strict-route` | off | stage 1 fails on a split router vote |
| `--require-fresh-research` | off | stage 2 fails on a stale or unusable pack |
| `--llm-judge` | off | advisory pairwise verdict on the top 2 passing candidates, recorded in the manifest and gate-report; never changes the winner or exit code. Unconfigured gives `{"status": "unavailable"}`. |
| `--json` | off | stdout is one JSON document (§4). The report is still written to `validation-report.md`. |
| `--self-test` | — | the hermetic self-test (§7) |

## 4. `--json` schema

```
{"status":       "pass|gate1_fail|gate2_fail|input_error|crash|fail",
 "exit_code":    int,                      # == the process exit code
 "outdir":       str,                      # absolute
 "artifacts":    [str],                    # files present, in ARTIFACTS order
 "winner":       null | {"index": int, "seed": int, "via": "selection|repair|best_failing"},
 "rubric":       null | {"score", "selection_score", "audit_score", "compliance_flags"},
 "route":        null | str,               # router summary line ("route: …")
 "warnings":     [str],                    # "<source>: <message>"
 "gates":        {"gate1": null | [str], "gate2": null | [str]},   # null = not run
 "failed_stage": null | str,               # stage name, e.g. "gate 1"
 "stages":       ["<n> <name>: <STATUS>"], # always 10 entries
 "script_summary": null | {…}}             # §5
```

`winner` is null for `--script-json` runs and for runs that stop before stage
5. `--replay M --json` prints `{"status": "reproduced|mismatch", "exit_code":
0|1, "replay": {manifest, cmd, returncode, expected_sha256, actual_sha256,
outputs {file: {expected, actual, match}}, warnings, error, out_dir,
stdout_tail, stderr_tail}}`.

## 5. Artifacts, manifest, gate report

`ARTIFACTS` = script.json, bundle.md, brief.md, validation-report.md,
captions.srt, captions.vtt, captions.json, shotlist.csv, shots.json,
manifest.json, trace.jsonl, gate-report.json.
- A passing run writes all 12.
- A gate-1 failure writes 5: report, script, manifest, trace, gate-report.
- A gate-2 failure adds bundle.md and brief.md.
- A stage 1–3 stop writes 4 (no script.json).

`manifest.json` holds the `vsp.manifest` keys (schema_version, git, python,
argv, args, seeds {root, candidates}, inputs {research_pack, rules, personas,
schema, code sha256s}, route, research, candidates, selected, repairs, gates,
outputs {file: sha256}, timings_ms). The pipeline adds `exit_code`, `status`,
`stages`, `script_summary`, `rubric`, `learned`, `env` (the `ENV_KEYS`),
`llm_judge` and `warnings`.

`script_summary` (also in `--json`) is null when no script.json was written:

| field | value |
|---|---|
| prompt, niche, hook_family, hook_source, presenter, format, duration_s | from script.json |
| hook | `vsp.rubric.hook_line(script)`, the spoken verbal hook |
| seed | the root `--seed` (`--script-json`: the script's own `seed`, usually null) |
| candidate_seed | the sub-seed of the selected / repaired / best-failing candidate (equals seed for candidate 0) |
| script_sha256 | sha256 of the written script.json bytes (equals `outputs["script.json"]`) |

`learned` = `{dir, priors {path, exists, sha256, valid, disabled}, hook_packs
{dir, files {name: sha256}, loaded [ids], disabled}}`.

`gate-report.json` = `{schema_version: 1, prompt, status, exit_code,
failed_stage {n, name} | null, stages [{n, name, status, detail, crash?,
input_error?}], gate1/gate2 {result PASS|FAIL|null, errors, warnings},
selected, candidates [{index, seed, passed, rank, error, gate1, rubric,
hook}], repairs [{candidate, seed, passed, error, rounds, rules}], llm_judge,
warnings, rubric}`.

## 6. How the maker consumes learned state

Both inputs live under `$VSP_LEARNED_DIR` (default `<repo>/learned/`,
`vsp.config`).

**Priors** (`priors.json`, read by `vsp/priors.py`, used in `pick_hook`):
- Schema v1 only. A missing, unreadable, non-JSON or wrong-schema file is
  ignored; an invalid file also adds the warning `learned: priors.json is not
  a valid schema-v1 priors file — ignored`. Entries with alpha/beta ≤ 0,
  non-finite values or a non-integer n are dropped. The file is cached per
  (path, mtime, size, inode). `VSP_NO_PRIORS=1` disables it.
- Posterior: the niche's table when the niche key is present, else `global`.
  There is no per-family mix of the two.
- Candidate hooks score as `(anchored, overlay focus, format contract, prior,
  niche preference)`, so quality always wins. `prior` is NEUTRAL (0.5) unless
  a family has n ≥ 3; then it is one `betavariate(alpha, beta)` draw from the
  hook rng, in sorted family order.
- Draws happen only in the template branch (never for pinned routine/practice
  hooks or the fallback), and only when the quality-tied top spans ≥ 2
  families. Without a priors file, or without evidence, the rng is untouched
  and the output is byte-identical.
- Provenance: `script.json.priors_used = {family: {alpha, beta, n}}` whenever
  a draw steered the pick. The manifest pins the file's sha256.
- Deterministic: the same seed and file give the same bytes across processes
  and `PYTHONHASHSEED` values (the random streams are only guaranteed per
  Python version).

**Hook packs** (`hook_packs/*.json`, loaded once at maker import, in sorted
file-name order; `VSP_NO_HOOK_PACKS=1` disables):
- A pack loads only if it has `"status": "approved"`, `"schema_version": 1`
  and a non-empty unique `id`. `proposed` and `rejected` packs are skipped
  silently; any other defect is skipped with a warning.
- A template joins `HOOKS[family]` only if the family already exists and the
  template is a one-line string of ≤ 120 chars whose `{slots}` all appear in
  `HOOK_SLOTS` (the slot set of the built-in templates, computed at import).
  Stray braces and positional or attribute fields are rejected. Templates are
  whitespace-normalised, and duplicates are skipped silently.
- Accepted templates then face the built-in screens: the 8-word budget, the
  gate lexicon, D144 overlay, D137 AI lane and D37/D136 slot rules.
- A pack that adds 0 templates is not loaded ("approved pack 'x' added no
  templates"), so an approved pack whose templates use unknown slots is
  rejected. Rejections go to stderr (`viral_script_maker: hook pack …`) and
  to the report (`learned: hook pack …`).
- Provenance: `script.json.hook_packs = [loaded ids]` whenever ≥ 1 pack is
  loaded. That is the pool the hook was drawn from, not necessarily the
  template that rendered. The manifest `learned.hook_packs` hashes every pack
  file.

**Live research** (`vsp/research.py` helpers): `pick_hook` prefers
`live_hook_family(pack, niche, presenter)`. That is the first mappable family
in the niche's whole ranked list, across the research niches the maker niche
maps to; never `proof-first`, and never story-time/identity-reveal for an AI
presenter. `research_notes` cites `niche_fresh_lines(pack, niche, 3)` and
omits the line when there are none. `--no-research`, or no usable pack, gives
the frozen rulebook.

## 7. Self-test (`python3 pipeline.py --self-test`)

Hermetic setup: temp `VSP_OUTPUTS`, fixture viral.db, `VSP_FIXTURE_OK=1` and
an empty temp `VSP_LEARNED_DIR`. It asserts that the repo's `outputs/` and
`learned/` trees are byte-identical afterwards. Contents:
- 38 gate cases (legacy cases untouched).
- 12 unit checks. WS-INT added three: the priors reader, priors change only
  tie-breaks, and the hook-pack loader.
- no-clobber.
- 10 e2e CLI checks:
  - normal run: clean statuses, 12 artifacts, schema-valid script, valid SRT, `script_summary` + hashes, candidate 0 = seed 701
  - `--candidates 1` equals `generate(prompt, seed=701)`
  - `--replay` OK, `--replay --json`, and a changed recorded exit code gives MISMATCH
  - the `--json` schema
  - a malformed hook pack is ignored and reported
  - an approved pack with an unknown slot is rejected (never rendered, reported)
  - priors through the CLI: steered, byte-identical across hash seeds, sha pinned, replay reproduces, `VSP_NO_PRIORS=1` byte-identical
  - stage-6 repair (injected D44)
  - a loud failure (injected D37): exit 1, stages 7–9 SKIPPED, stale exports removed, `--json`
  - stage-1 input errors (blank prompt, unknown persona, `status input_error`)
- Optional selfchecks: `vsp.ingest`, `vsp.feedback` and `vsp.improve` are
  found with `importlib.util.find_spec` and each runs in a child process.
  `selfcheck() -> (ok, lines)` must return ok. An absent module, or one
  without `selfcheck()`, is only noted.

Runtime is about 6.5 s on 3.9 and on 3.12. Mutation test: 9 injected
regressions (stale artifacts kept, unsorted Thompson order, `--json` printing
the report, replay not pinning env, repair skipped, `VSP_NO_PRIORS` ignored,
candidate 0 not the raw seed, unknown slots allowed, pack warnings dropped).
All 9 were caught.

## 8. Measured (commit 4fa228f)

Real-CLI scorecard (`evals/scorecard.py run --workers 12`, 8 CPUs; `--duration
30 --out-dir` passed automatically; default `--candidates 8`):

| suite | runs | crash | e2e | shippable | rubric mean (sel / audit) | s/run | artifacts |
|---|---|---|---|---|---|---|---|
| golden, py3.9 | 990 | 0 | 100.0% (CI 99.6–100) | 100.0% | 99.9 (99.9 / 99.9) | 0.545 | 990/990 each |
| holdout, py3.9 | 1050 | 0 | 100.0% (CI 99.6–100) | 100.0% | 99.9 (99.8 / 100.0) | 0.545 | 1050/1050 each |
| golden, py3.12 | 990 | 0 | 100.0% | 100.0% | 99.9 | 0.511 | 990/990 each |
| holdout, py3.12 | 1050 | 0 | 100.0% | 100.0% | 99.9 | 0.500 | 1050/1050 each |

- Gate 1 passed 100% on every suite, with 0 gate failures, 0 compliance flags
  and a 0% fallback-hook rate.
- Rubric check misses: R12 ×2 on each suite. R14 (the caption does not echo
  the comment keyword) ×30 golden, all from `morning-routine`, and ×60
  holdout, from `h-gym-routine` and `h-night`. This is maker caption code, not
  WS-INT's; it is audit/quality only and never a gate.
- 3.12 vs 3.9: the same hook on 2040/2040 runs and 0 status flips.
- The s/run figure is measured under 12-way load.
- `artifacts` counts the scorecard's 6 tracked files. A `--keep` deep scan of
  all 2040 runs found 12/12 artifacts on every run, 0 candidate errors, and
  all 8 candidates passing the cascade on every run. So stage 6 never ran in
  the scorecard; the self-test covers it.
- `--script-json` round trip: 240 sampled scorecard scripts, 240/240 pass.

Single-run wall time (sequential, hermetic, median of 15 after a warm-up;
`"portable door lock" --presenter ai`, 30 s demo):

| python | `--help` (startup + imports) | `--candidates 1` | `--candidates 8` | `--candidates 16` | stage 3–5 ms (1 / 8 / 16) |
|---|---|---|---|---|---|
| 3.9.25 | 0.048 s | 0.114 s | 0.171 s | 0.243 s | 16.7 / 73.0 / 140.9 |
| 3.12.14 | 0.051 s | 0.106 s | 0.162 s | 0.215 s | 14.8 / 66.7 / 121.7 |

- Each extra candidate costs about 8 ms. Route takes about 13–17 ms; gate 1,
  shot list, gate 2 and export together take about 6 ms.
- Second prompt ("I stopped buying coffee for 30 days", human talking-head,
  45 s): 0.112 / 0.150 / 0.191 s on 3.9 and 0.103 / 0.136 / 0.170 s on 3.12.
- The pyenv `python3.12` shim adds about 60 ms per launch, so the table uses
  `/usr/bin/python3.12`.

Duration sweep (5 prompts × 5 formats × 2 presenters): 5 s 0/50, 8 s 21/50,
10 s 42/50, 12–180 s 50/50. Every failure is a loud D74, and there were 0
crashes.

## 9. Deviations and decisions

1. Stage 4 gates candidates through the full cascade, not gate 1 alone, so a
   candidate that would fail gate 2 never wins. The final gate-1 verdict on the
   chosen script is the legacy line.
2. Repair walks every `best_failing` candidate (≤ 3 rounds each) instead of
   repairing only the top one. The stage-5 line lists the first 5.
3. An unknown `--persona` is an input error. The maker falls back silently to
   `maya` (or to no persona for `_` keys), which would put the wrong face, or
   none, on an AI script. A case or display-name variant resolves to its key,
   and the output is byte-identical to the default.
4. Stage-1 input errors report status `input_error`, not `crash`. The line is
   still `STAGE 1 FAILED (route): …`, which `evals/scorecard.py` counts as a
   crash.
5. `--replay` also requires the recorded exit code: the same script under a
   gate that now answers differently is a MISMATCH. A deterministic failing
   run replays as `reproduced`. A `--require-fresh-research` run cannot be
   replayed once the pack is more than 48 h old.
6. `""` is an argparse usage error (exit 2, no report). A whitespace-only
   prompt goes through stage 1 as `input_error`.
7. Out of WS-INT scope, reported only: R14 misses on routine prompts, and
   `--duration` ≤ 10 s failing D74 for some formats (maker/timing).
