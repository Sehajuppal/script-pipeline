# WS-IMPROVE — the self-improvement engine (`vsp.improve`)

An operating agent (Hermes on Muse) runs `python3 -m vsp.improve cycle` on a
schedule. Each cycle measures the pipeline, finds what to fix, evolves hook
templates, and A/B tests them. Every decision is written to
`learned/LEDGER.md`. Stdlib only; Python 3.9 and 3.12.

## Commands

| command | what it does |
|---|---|
| `measure [--budget small\|full]` | Scorecards golden + holdout (+ capability). Writes `learned/evals/latest.json` and `history.jsonl`; raw JSON goes to `learned/evals/results/` (git-ignored). |
| `diagnose` | Writes ranked opportunities and tasks to `learned/DIAGNOSIS.md`, `TASKS.md` and `tasks.json`. |
| `evolve [--budget] [--llm auto\|on\|off] [--seed N] [--dry-run]` | Runs a MAP-Elites-lite hook search. Writes `learned/hook_packs/<date>-<nn>.json` with status `proposed`. |
| `promote PACK [--budget] [--loader auto\|native\|emulate]` | Runs a full-scorecard A/B of one pack, sets it to `approved` or `rejected`, and appends to `LEDGER.md`. |
| `verify --base REF --cand REF [--budget]` | Prints ACCEPT or REJECT. Evidence goes to `learned/verify/<run>/` and `LEDGER.md`. `--cand .` means the working tree. |
| `golden-refresh [--max-new N] [--dry-run]` | Adds trending products to `evals/capability.jsonl`. |
| `delegate TASK_ID` | Hands a task to `muse exec --json` on a fresh branch, then runs `verify`. If `muse` is absent, it prints instructions for Hermes. |
| `cycle [--budget small\|full] [--llm]` | Runs health → measure → diagnose → evolve → promote → ledger. Prints a summary and the top 3 tasks. |
| `selfcheck [-v]` | Hermetic checks. The same code is `vsp.improve.selfcheck() -> (ok, lines)`. |

Budgets:

- **small**: seed 1 everywhere; evolve uses 10 golden product prompts.
- **full**: seeds 1,2,3; evolve uses all 25 product prompts.

Exit codes:

- 0: OK or ACCEPT.
- 1: REJECT, or a halted cycle.
- 2: usage error.

Environment variables:

- `VSP_LEARNED_DIR` moves the engine's state. Children under test never inherit it.
- `VSP_IMPROVE_TMP` sets the temp root.
- `VSP_MUSE_BIN` and `VSP_MUSE_MAX_STEPS` configure `delegate`.
- `VSP_LLM_*` configure the LLM; see `vsp/llm.py`. The Meta provider reads `VSP_LLM_API_KEY` first, because Hermes strips `MODEL_API_KEY`.

Hermes schedule:

```sh
hermes -p vsp cron create "every day at 6am" "Run python3 -m vsp.improve cycle --budget small in /abs/script-pipeline; report learned/CYCLE.md; for the top task run python3 -m vsp.improve delegate <id>; open a PR only on ACCEPT; never merge it." --workdir /abs/script-pipeline --name vsp-improve
```

## evolve

**Seeds**

- The maker's `HOOKS`, plus any approved packs.
- Hooks mined from the research pack (`fresh_hook_lines`, `top_reels`) and from the research DB (`reels.hook_text` by likes).
- Mined hooks are used only from product niches. They are templatized: the first product noun phrase becomes `{product}`, `{category}` or `{category_pl}`. A family is assigned only when a cue matches.

**Mutations** (deterministic, seeded)

- Opener swap and tail swap inside interchangeable phrase groups (`PHRASE_GROUPS`). The groups are mined from the HOOKS openers and tails, plus the tactics in short-form-virality §1. Openers from mined hooks join at run time.
- Slot swap: `{product}` ↔ `the {category}`. It never produces `this {category}`, because the head noun can be plural.
- Clause reorder, but only when the second sentence has no anaphora.
- Trimming: fillers, and codas that carry no claim. It never trims an "until you see this" turn.
- Optional LLM reflective step (`vsp.llm.complete_json`). The prompt contains the contract, the thin spots, the failing renders with their gate/rubric messages, and top-reel hooks. The reply is `{"templates":[{family, template, rationale}]}`.

**Fitness**

Each candidate is rendered over (sample prompts × 5 formats × 2 presenters) using the maker's own code, read-only: `parse_prompt`, `_hook_nouns`, `_render_hook_line`, `humanize_dialogue`, `overlay_truncate` and `_hook_candidates`.

Hard checks, in any context where the template renders:

- D73: ≤ 8 words.
- D31: no braces.
- D37: no invented prices.
- D136, D137 (AI presenter only), D139 and D141, all via `vsp.lexicon`.
- D144: `overlay_is_clean`.
- R01 and R07.

Soft checks: R02 specificity, R15 product named, P2 slop, and a frame-0 card that doesn't end on a verb or quantifier.

The score:

```
fitness = quality × (0.6 + 0.4·novelty) × gain
```

`gain` is the expected number of extra distinct hooks per context over 3 seeds, when the template joins the maker's top-scored tie pool. It is normalized so that 1 means every context goes from a one-template pool to a two-template pool. A template that outscores every existing line collapses that pool, so its gain is negative and it is excluded.

**Archive**

- Cells are keyed by (family, opening device, length bucket).
- A candidate is rejected if its trigram Jaccard similarity to any existing template or elite is above 0.5.
- Evaluation is cheap-first: template screens, then a stratified context sample, then the full sample.

**Pack and preview**

- Templates are chosen by greedy marginal gain. Pool sizes are updated after each pick, and a slot-normalized re-wording of an existing line is skipped.
- An offline preview then runs `generate()` + gate 1 + rubric in-process on the same golden sample, with and without the pack.
- The pack is written only if the preview shows more distinct hooks, no new gate-1 failures and no rubric drop.
- evolve never reads `evals/holdout.jsonl`: `holdout_guard()` wraps `open`/`io.open`/`os.open` and raises `HoldoutRead`.

### Sample result: the real cycle's pack `2026-09-29-evolve-01`

Budget small, seed 60929, 100 contexts. Baseline: 27 contexts had a single-template pool; expected distinct hooks per context was 1.81.

| family | template | fitness | gain | quality | novelty | reach | operator | sample render / card |
|---|---|---|---|---|---|---|---|---|
| bold-claim | `Day {ndays} with the {category}. Zero failures.` | 0.1106 | 0.1164 | 1.00 | 0.88 | 0.260 | slot_swap | "Day 7 with the resistance bands. Zero failures." / RESISTANCE BANDS |
| curiosity-gap | `The {category}. Worth it?` | 0.1054 | 0.1054 | 1.00 | 1.00 | 0.120 | slot_swap | "The water bottle. Worth it?" / WATER BOTTLE |
| curiosity-gap | `{product}: the honest verdict.` | 0.1054 | 0.1054 | 1.00 | 1.00 | 0.120 | tail_swap | "The limited edition water bottle: the honest verdict." / WATER BOTTLE |
| curiosity-gap | `I lived with the {category} for {ndays} days.` | 0.0588 | 0.0645 | 1.00 | 0.78 | 0.210 | slot_swap | "I lived with the bottle for 7 days." (human only) / BOTTLE |
| bold-claim | `Most {category_pl} fail. Not this one.` | 0.0539 | 0.0586 | 0.97 | 0.86 | 0.150 | tail_swap | "Most resistance bands fail. Not this one." / MOST RESISTANCE BANDS |
| transformation | `{product}. Here's the after.` | 0.0528 | 0.0586 | 1.00 | 0.75 | 0.150 | tail_swap | "The smart bird feeder. Here's the after." / SMART BIRD FEEDER |
| transformation | `This is the after with {product}.` | 0.0493 | 0.0586 | 1.00 | 0.60 | 0.150 | opener_swap | "This is the after with the bird feeder." / BIRD FEEDER |
| transformation | `{product} after {ndays} days. Worth it?` | 0.0402 | 0.0454 | 1.00 | 0.71 | 0.060 | tail_swap | "The bird feeder after 7 days. Worth it?" (review) / BIRD FEEDER |

Offline preview over 300 golden product runs: distinct hooks went from 0.28 to 0.33, with 0 gate-1 failures and rubric 100 in both runs.

A full-budget dry run (`evolve --budget full`, 250 contexts, 19 s) builds on top of the approved pack. It proposed 9 more templates, for example `Nobody warns you about {product}.` and `I almost sent back {product}.`. Its preview went from 0.336 to 0.405 distinct.

## promote

- **base**: a temp copy of the repo with production as it is. The engine's other approved packs stay, and the pack under test is removed.
- **cand**: the same copy, plus the pack with status `approved`.
- Both copies get the loader shim when the maker has no native loader (`packs.inject_shim`). The shim goes into the temp copies only.

Both copies are scored with one yardstick (`abtest.run_ab`): the base's `evals/scorecard.py`, rubric and suites. The candidate's self-test runs on python3.9 and python3.12.

ACCEPT requires all of the following:

| rule | condition |
|---|---|
| R1 / R2 | No significant e2e or shippable regression: flips down ≤ flips up, or exact McNemar p > 0.05 |
| R3 | Rubric Δ 95% CI lower bound ≥ −0.5 |
| R4 | Audit-only mean drops by no more than 0.5 |
| R5 | Holdout e2e, shippable and rubric are not lower |
| R6 | Zero compliance flags |
| R7 | Self-test green |
| R8 | Full paired coverage |
| R10 | The pack changed at least 1 hook |
| R11 | Hook distinct ratio is not lower on golden or holdout |

The evidence always includes distinct ratio, distinct-2 and per-cell seed diversity. It is written to `learned/promote/<id>/{evidence.json, evidence.md, golden-compare.md, holdout-compare.md}` and into the pack's provenance.

## verify

1. Creates temp `git worktree add --detach` trees. If `.git` is read-only (Muse's sandbox), it uses `git archive` instead.
2. Runs the weakening guard.
3. Runs the candidate's self-test on 3.9 and 3.12.
4. Runs scorecards golden + holdout on both trees with the base's yardstick, then `scorecard.py compare`.
5. Applies the same rules plus R9 (guard). Diversity is reported but is not a rule here.
6. Always removes the worktrees.

The guard (`vsp/improve/guard.py`) snapshots each tree in a child process that imports that tree's modules. It REJECTs if any of these are true:

- A REGISTRY entry was removed, downgraded from error, or lost covers; or LEGACY_IDS order changed.
- D136–D141 are missing at severity error. This check always runs.
- A lexicon, gates or rules regex no longer matches a string that the base pattern matched. The test strings come from each pattern's own syntax tree, with case variants and a probe corpus.
- A deny-set lost a member, an allow-set (`LABEL_WORDS`) gained one, or a limit (`MAX_HASHTAGS`, `WPS_*`, `SLACK`) grew.
- A `g1_`/`g2_` check was removed, or the LEGACY_GATE order changed.
- The legacy self-test case count dropped, a legacy tuple changed, or any case or unit check was removed.
- Any yardstick file changed (golden, holdout, `scorecard.py`, `rubric.py`).

Real run: `verify --base 333f695 --cand HEAD --budget small` gave ACCEPT in 43 s, with 0 guard findings and self-test green on both Pythons.

## golden-refresh and the capability suite

- **Sources**: product noun phrases (2–4 words, product head noun, place nouns excluded) from top reels' hooks and captions in the research pack or DB. FIXTURE reels are excluded. Phrases are weighted by mentions × log-likes.
- **Filters**: the maker must route the phrase as a product, and it is de-duplicated against every product prompt in golden, holdout and capability. A phrase counts as a duplicate if its content stems are equal to another prompt's, or if one set contains the other (both ≥ 2 stems).
- It never writes golden or holdout.
- **Seed**: `evals/capability.jsonl` holds 22 unseen products: prices, prompt-supplied proof, hook-noun traps such as "the glow" or "the head filter", and plural heads. At seed 1 all 220 runs pass e2e, and hooks are 58% distinct.
- In this sandbox the pack has no `top_reels` and there is no DB, so a real refresh adds 0 prompts. The extractor is exercised by `selfcheck`.

## delegate

**When `muse` is found** (PATH or `VSP_MUSE_BIN`):

1. Creates branch `improve/<task>-<stamp>` and a temp worktree.
2. Runs `muse exec --json --disable-approval "<task, evidence, constraints, acceptance command>"`. `META_API_KEY` is filled from `VSP_LLM_API_KEY` if missing.
3. The engine commits the changes, excluding outputs/, because Muse keeps `.git` read-only.
4. Runs `verify --base <start> --cand <branch>`.
5. Records the task status and a LEDGER entry. It never pushes.

A stub-`muse` rehearsal in a scratch clone reached ACCEPT in 39 s.

**Without `muse`**: prints the task plus numbered steps (worktree, implement, self-test, commit, verify, PR on ACCEPT).

## cycle — the real offline run

`python3.9 -m vsp.improve cycle --budget small --llm off` took 73 s. The committed record is `learned/CYCLE.md`, the last `LEDGER.md` entry and `learned/promote/2026-09-29-evolve-01/`.

- **health**: self-test green on 3.9 and 3.12. Research pack is 16 h old. No packs yet. The maker has no loader on this branch.
- **measure**:

  | suite | runs | e2e | shippable | rubric | audit | compliance | hooks distinct |
  |---|---|---|---|---|---|---|---|
  | golden | 330 | 1.0 | 1.0 | 99.9 | 100 | 0 | 0.4455 |
  | holdout | 350 | 1.0 | 1.0 | 99.9 | 100 | 0 | 0.4857 |
  | capability | 220 | 1.0 | 1.0 | 100 | 100 | 0 | 0.58 |

- **diagnose**: 15 tasks.
- **evolve**: 8 templates; preview distinct went from 0.28 to 0.33; the holdout was never opened.
- **promote**: ACCEPT, and the pack is now approved.

  | suite | hook distinct | distinct-2 | hooks changed |
  |---|---|---|---|
  | golden | 0.4455 → 0.4758 | 0.1648 → 0.1641 | 95/330 |
  | holdout | 0.4857 → 0.5086 | 0.1583 → 0.1667 | 83/350 |

  e2e, shippable, rubric and audit were flat, with 0 compliance flags.
- **Top 3 tasks**:
  1. T-HOOK-DIVERSITY
  2. T-DRIFT-FAMILIES (follow the live family ranking, D148)
  3. T-RUBRIC-R14 (routine captions)

## selfcheck (hermetic, about 4 s)

| check | what it covers |
|---|---|
| `llm-meta-http` | Stub HTTP server on 127.0.0.1: path, Bearer `VSP_LLM_API_KEY`, `max_completion_tokens` 4000, `reasoning_effort`, `json_schema` `response_format`, no forbidden keys; 429 → 503 → 200 with Retry-After honoured; Retry-After over 120 s gives up; openai-compatible 400 falls back to no schema |
| `llm-complete-json` | MockProvider replies |
| `packs-contract` | The pack loader contract |
| `decide-synthetic` | Each of R1–R11 fires on its own regression, and a pure diversity win ACCEPTs |
| `weakening-guard` | The guard catches 9 kinds of weakening |
| `promote-flow`, `verify-flow` | Stubbed A/B, status, evidence and ledger |
| `refresh-dedupe` | golden-refresh de-duplication |
| `evolve-no-holdout` | A spy confirms the holdout is never opened, and the guard raises if something tries |
| `evolve-slot-safe` | Tiny run; invalid LLM proposals (unknown slot, unknown family, absolute claim, over 120 chars) are discarded; the written pack validates |

The self-test's optional-selfcheck harness calls it in a child process. It never writes to the repo's `learned/`.

## Guardrails

- **Automation never edits gate or rule code to pass.** `verify`'s guard rejects any weakening of `vsp/gates.py`, `vsp/rules.py`, `vsp/lexicon.py` or the self-test, and any removal of D136–D141. Tasks tell agents to fix the generator instead.
- **Never pushes to main, never merges its own PRs.** `delegate` works only on `improve/*` branches. The engine commits there and nowhere else. A human or Hermes opens the PR on ACCEPT and never merges it.
- **Everything goes through verify.** Code changes go through `verify`; hook packs go through `promote`, which runs the same statistics and rules on the full golden + holdout scorecard. Nothing mutates at runtime; the maker loads only approved packs.
- **Holdout and audit-only checks detect gaming.** Holdout prompts are never used for tuning (`holdout_guard`) but always gate promotion (R5). Audit-only rubric checks never select (R4). The yardstick is frozen for automation.
- **The LLM is advisory, never a gate.** It only proposes templates, which are screened and scored like any other and then A/B tested. It is off unless configured, and `complete_json` never raises.
- **Everything goes into `learned/LEDGER.md`.** Every promote, verify, delegate and cycle is logged with its verdict, the failing rules and the evidence paths.

## Known limits

- This branch's maker has no native pack loader. promote measures packs through the temp-copy shim, and an approved pack takes effect in production once WS-INT's loader (`load_hook_packs`) is merged. Until then, `measure` on this branch does not reflect approved packs.
- The LLM path was exercised only with MockProvider and the stub server; no key is available here.
- Mining found 0 product hooks here: the pack's fresh lines are comedy and there is no DB.
