# Lab techniques for upgrading the viral-script pipeline (2025–2026)

*Research brief, 2026-09-28. Scope: a deterministic offline core plus an optional LLM layer. I only read the pipeline files; nothing was modified.*

**Bottom line.** Labs converge on four things: fixed workflows with programmatic gates, many cheap candidates filtered by verifiers, rubrics broken into binary checks, and eval suites plus traces that make every change measurable. We already have the hardest part: fail-loud gates over 135 dated rules. The gaps:
- **No selection.** The maker produces one candidate per seed.
- **No machine-readable rubric.** The rules live in prose and scattered `if` statements.
- **No input router.**
- **No reproducibility across days.** There is one shared RNG stream, the research pack isn't pinned, and no manifest is written.

## 1. Workflow architecture

**1.1 Workflows first; add routing.**
- *What the sources say:* [Anthropic](https://www.anthropic.com/engineering/building-effective-agents) separates workflows (fixed code paths) from agents (the model directs itself) and recommends the simplest option that works. Its patterns are gated prompt chaining, routing, parallelization (sectioning or voting), orchestrator-workers, and evaluator-optimizer. Google's ADK guide covers the same set, including generator-critic and refinement loops with iteration caps ([Google, Dec 2025](https://developers.googleblog.com/developers-guide-to-multi-agent-patterns-in-adk/); [Google Cloud](https://cloud.google.com/architecture/choose-design-pattern-agentic-ai-system)).
- *Why it matters:* we're already a gated chain, but routing is missing. The input-side niche/fit classifier was never built, and niche bleed keeps recurring (D107, D121).
- *Do:* add a stage-0 `route(prompt) -> {niche, concept, category, fit, confidence, votes}`.
  - Three deterministic classifiers vote: a keyword lexicon, the pack's niche map, and the nearest viral.db niche.
  - If all three disagree or fit is low, exit as "unroutable" instead of defaulting.
  - Downstream code reads the route and never re-infers the niche.

**1.2 Evaluator-optimizer (the 2026 form).**
- *What the sources say:* Anthropic's March 2026 harness study found models grade their own work too leniently ([Anthropic](https://www.anthropic.com/engineering/harness-design-long-running-apps)). What helped was a separate, skeptical evaluator; criteria that make taste gradable; a hard threshold per criterion; and few-shot score breakdowns to limit drift. The best output was sometimes a middle iteration, not the last.
- *Why it matters:* this is our judge loop, which currently runs by hand across cycles.
- *Do:* add `repair_loop(script, max_iter=3)`.
  - Gates emit structured failures: `rule_id, beat, measured, limit`.
  - Each rule maps to a deterministic repair: D43 drops the lowest-priority clause or re-times the beat; D103 truncates at a noun phrase; D44 strips the parenthetical.
  - Re-gate after each repair and keep the best-scoring version.
  - If a hard gate still fails, fail loudly. Never edit a gate to make a script pass.

**1.3 Guardrails as tripwires.**
- *What the sources say:* [OpenAI](https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/) recommends layered guardrails: classifiers; blocklist, regex and length rules; output validation; and human review for high-risk steps. The [Agents SDK](https://github.com/openai/openai-agents-python/blob/main/docs/guardrails.md) has input, output and tool guardrails whose tripwires halt the run. Its blocking mode guarantees the expensive step never starts.
- *Why it matters:* our gates only check output.
- *Do:*
  - **Blocking input guardrail:** parse the prompt, extract any price, and flag regulated or claims-bearing categories.
  - **Research-pack guardrail:** the pack must be schema-valid and ≤48 hours old, and its hash is logged. Otherwise refuse, or require an explicit `--no-research`.

**1.4 Multi-agent: optional layer only.**
- *What the sources say:* [Anthropic's](https://www.anthropic.com/engineering/multi-agent-research-system) orchestrator-worker Research system beat a single agent by 90.2% on its internal eval. It cost about 15× the tokens of a chat and suits breadth-first work, with subagents passing back references to stored artifacts. A [2026 Anthropic note](https://www.anthropic.com/research/multiagent-systems) finds agents cooperate best as typed tool calls with a separate arbiter.
- *Do:* keep the generator deterministic. If LLMs arrive, use this shape for `research_bridge.py`: parallel reel-dissection workers produce typed JSON, and an arbiter merges it.

## 2. Test-time compute

**2.1 Best-of-N with verifiers, and its ceiling.**
- *What the sources say:* compute spent on sampling plus verification pays off most when allocated by prompt difficulty; that was over 4× more efficient than naive best-of-N ([Snell et al.](https://arxiv.org/abs/2408.03314)). Imperfect verifiers cap what resampling can achieve ([Stroebl et al., ICLR 2026](https://arxiv.org/abs/2411.17501)). Verifier-guided search can even trail plain sampling at large N ([2502.00271](https://arxiv.org/abs/2502.00271)).
- *Why it matters:* today a rejection is a dead end, and a pass isn't necessarily the best script available.
- *Do:*
  1. Derive sub-seeds as `sha256(f"{seed}:{i}")` and build N=8 candidates.
  2. Run a cheapest-first cascade: schema → claims/D37 → stage verbs → timing → Gate 1 → shot list → Gate 2 → rubric.
  3. Keep the top scorer. If fewer than 2 pass or the top two nearly tie, extend to N=16.
  4. Log all candidates.
  5. Hold ~10% of checks out as audit-only. If winners do worse on them than random passing candidates, the rubric is being gamed.

**2.2 Pairwise tournaments, Bradley–Terry and Elo.**
- *What the sources say:*
  - In a knockout tournament, each pair is compared K times and the winner advances. The chance of a wrong winner provably shrinks as N and K grow ([Chen et al.](https://arxiv.org/abs/2411.19477); pairwise reward-model variant: [PairJudge RM](https://arxiv.org/abs/2501.13007)).
  - LLM judges' preferences aren't transitive, so a round-robin plus a Bradley–Terry fit (or Swiss pairing) ranks more reliably ([Xu et al., ICML 2025](https://arxiv.org/abs/2502.14074)).
  - EQ-Bench's creative-writing benchmark scores with a rubric first, then runs pairwise matchups with win margins through Glicko-2 ([EQ-Bench](https://github.com/EQ-bench/creative-writing-bench)).
- *Caveat:* with a deterministic scalar score, a tournament just reproduces the top score. Pairwise adds signal only for relative criteria or noisy judges.
- *Do:*
  1. Take the rubric's top 4.
  2. Run a round-robin: 6 pairs, each in both orders. Judge hook specificity against the rival, novelty against recent hooks, and optionally LLM or human preference.
  3. Fit Bradley–Terry with the MM algorithm (about 20 lines). Break ties by seed hash.

**2.3 Self-consistency.**
- *What the sources say:* take a majority vote over sampled answers ([Wang et al.](https://arxiv.org/abs/2203.11171)). For free text, pick the most consistent candidate ([USC](https://arxiv.org/abs/2311.17311)).
- *Do:* vote wherever a discrete decision exists, such as the route, the hook family, and "is this a claim?". Flag any decision that flips across sub-seeds.

**2.4 Self-Refine and Reflexion.**
- *What the sources say:* Self-Refine loops draft → feedback → revise ([Madaan et al.](https://arxiv.org/abs/2303.17651)). Reflexion keeps verbal lessons in memory ([Shinn et al.](https://arxiv.org/abs/2303.11366)). Without external feedback, self-correction often fails ([Huang et al.](https://arxiv.org/abs/2310.01798)). A 2026 ablation found reflection must be grounded in concrete failures; scores alone or abstract critique did little ([MAGE](https://arxiv.org/abs/2607.11944)).
- *Why it matters:* our gate messages are exactly that kind of grounded feedback.
- *Do:*
  - Feed gate messages to the repair loop and to any LLM rewrite.
  - Implement Reflexion as an offline failure ledger, counted by rule × niche × template ID.
  - Compile the ledger into a versioned `priors.json` that down-weights repeat offenders. It is read-only at runtime.

## 3. Rubrics and LLM-as-judge

**3.1 Rubrics and checklists.**
- *What the sources say:*
  - Rubrics-as-Rewards tags each criterion Essential, Important, Optional or Pitfall (negative weight). It aggregates either as a normalized weighted sum of binary checks or holistically through a judge. It beat Likert-scale judge rewards by up to 31% on HealthBench ([RaR](https://arxiv.org/abs/2507.17746)).
  - Checklists graded by AI judges plus verifier programs improved every benchmark tested ([RLCF](https://arxiv.org/abs/2507.18624)).
  - OpenAI grades with rubrics too: HealthBench uses physician-written ones and PaperBench uses hierarchical ones ([HealthBench](https://openai.com/index/healthbench/); [PaperBench](https://arxiv.org/abs/2504.01848)).
  - A 2026 study shows rubric optimization gets gamed through partially satisfied compound items and criteria that only check for presence ([2605.12474](https://arxiv.org/abs/2605.12474)).
- *Why it matters:* our D-rules already form a rubric; they just aren't machine-readable.
- *Do:*
  - Compile RULES.md into `rubric.yaml`, one entry per rule: `id, tier, weight, scope, check, fixtures`.
  - Tiers: Essential = hard gate; Important/Optional = scored; Pitfall = negative weight (slop phrases, repeated re-hooks, invented proof).
  - Score = Σw·c / Σ|w|, where each check c is 0 or 1 and w is its weight.
  - Add per-prompt checklists: a given price appears exactly once, persona constraints apply, and challenge hooks name the noun.
  - Split compound rules into atomic checks.

**3.2 Judge protocol and bias control (optional LLM layer).**
- *What the sources say:*
  - G-Eval has the judge generate its own evaluation steps, fill in a form, and weight scores by probability ([Liu et al.](https://arxiv.org/abs/2303.16634)).
  - Judges show position, verbosity and self-preference bias ([MT-Bench](https://arxiv.org/abs/2306.05685)). Controlling for length raised correlation with Chatbot Arena from 0.94 to 0.98 ([LC-AlpacaEval](https://arxiv.org/abs/2404.04475)).
  - A 2026 TMLR study found style bias (markdown vs prose) far exceeds position bias ([2604.23178](https://arxiv.org/abs/2604.23178)). Provenance cues also sway verdicts ([2509.26072](https://arxiv.org/abs/2509.26072)).
- *Do:*
  - Use pairwise judging for "which hook stops the scroll" and pointwise binary judging for rubric items.
  - Render candidates as canonical plain text, stripped of seeds and "AI" labels.
  - Run both orders and count only wins that hold in both.
  - Only compare candidates within ±10% word count of each other.
  - Allow an "unknown" verdict.

**3.3 Calibration and judge panels.**
- *What the sources say:*
  - Validate judges like classifiers: binary labels, at least 50 passes and 50 fails, a train/dev/test split, TPR and TNR, and one narrow judge per failure mode ([Husain & Shankar](https://hamel.dev/blog/posts/evals-faq/); [OpenAI](https://developers.openai.com/cookbook/examples/evaluation/building_resilient_prompts_using_an_evaluation_flywheel)). Correct pass rates for judge error ([judgy](https://github.com/ai-evals-course/judgy)).
  - Judges rarely catch bad outputs: TNR is under 25% while TPR is around 96% ([2510.11822](https://arxiv.org/abs/2510.11822)).
  - Diverse panels beat one large judge at about 1/7 the cost ([PoLL](https://arxiv.org/abs/2404.18796)). But averaging breaks when one judge fails systematically ([RoPoLL, 2026](https://arxiv.org/abs/2606.30931)).
  - The best off-the-shelf creative-writing judge agreed with humans only about 73% of the time ([LitBench](https://arxiv.org/abs/2507.00769)).
  - Anthropic found one rubric call returning 0–1 scores plus pass/fail was the most human-aligned setup for Research ([source](https://www.anthropic.com/engineering/multi-agent-research-system)). Its eval guide isolates hard dimensions and allows "Unknown" ([source](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)).
- *Do:*
  - LLM judges are advisory, never gates.
  - Label 100+ scripts with one domain expert, and measure each judge's TPR/TNR.
  - Take the median of three judges from different model families.
  - Log judge versions and agreement.

## 4. Optimization and diversity

**4.1 Prompt and program optimizers.**
- *What the sources say:*
  - DSPy's MIPROv2 bootstraps demonstrations, proposes instructions, and searches combinations with Bayesian optimization ([docs](https://github.com/stanfordnlp/dspy/blob/main/docs/docs/api/optimizers/MIPROv2.md)).
  - GEPA reflects on traces and textual feedback and keeps a Pareto set. It beat GRPO by roughly 6–10% on average with up to 35× fewer rollouts, and beat MIPROv2 by more than 10% ([GEPA](https://arxiv.org/abs/2507.19457); [DSPy](https://dspy.ai/current/api/optimizers/GEPA/overview/)).
  - TextGrad back-propagates text critiques through a pipeline ([Nature 2025](https://www.nature.com/articles/s41586-025-08661-4)). OPRO iterates on scored past attempts ([OPRO](https://arxiv.org/abs/2309.03409)). Promptbreeder also evolves its own mutation prompts ([Promptbreeder](https://arxiv.org/abs/2309.16797)).
  - With only about 30 training items, good fixed prompts beat reflective optimizers ([MAGE](https://arxiv.org/abs/2607.11944)).
- *Why it matters:* our tunable parameters are the template pools, and the gates already emit textual feedback.
- *Do:* run an offline GEPA-style loop over hook, re-hook, CTA and proof templates.
  - Mutations are deterministic (slot swap, clause reorder, lexicon substitution, trimming), plus optional LLM mutations that read gate messages.
  - Score on the golden set and keep a Pareto front per niche.
  - Winners ship by PR with a D-number and seed evidence. Nothing mutates at runtime.

**4.2 Evolution and quality-diversity.**
- *What the sources say:*
  - [AlphaEvolve](https://arxiv.org/abs/2506.13131) pairs LLM-proposed diffs with automated evaluators. It adds a cheap-first evaluation cascade, multiple scores (which also lifted the target metric), stochastic prompt templates, and a MAP-Elites/island archive. MAP-Elites keeps the best candidate in each cell of a grid of trait combinations.
  - Open versions: [OpenEvolve](https://github.com/algorithmicsuperintelligence/openevolve), and [ShinkaEvolve](https://arxiv.org/abs/2509.19349), which adds novelty rejection sampling.
  - QDAIF uses LM feedback to score both quality and diversity, and covers more of the space with good samples ([QDAIF](https://arxiv.org/abs/2310.13032)).
  - Verbalized Sampling asks the model for k options with probabilities. It raised creative-writing diversity 1.6–2.1× ([VS](https://arxiv.org/abs/2510.01171)).
- *Why it matters:* diversity without a quality floor is noise; quality-diversity search gives both.
- *Do:*
  - Build a hook MAP-Elites archive keyed by family (19) × opening device (number, question, POV, contrarian, demo-first) × length bucket. Keep the best line per cell per niche.
  - The seed picks among the top-k elites of the routed cell.
  - Reject a candidate if its trigram Jaccard with any of the last 50 shipped hooks is above 0.5.
  - Report archive coverage.

## 5. Structured outputs and guardrails

**5.1 Schemas and constrained decoding.**
- *What the sources say:* OpenAI and Anthropic enforce JSON Schema during sampling ([OpenAI](https://openai.com/index/introducing-structured-outputs-in-the-api/); [Claude](https://docs.claude.com/en/docs/build-with-claude/structured-outputs); [strict tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use)). Frameworks differ in schema coverage and output quality ([JSONSchemaBench](https://arxiv.org/abs/2501.10868)). Format instructions can degrade writing, mostly in open-weight models, so draft first and format second ([Format Tax](https://arxiv.org/abs/2604.03616)). And schema-valid does not mean semantically valid ([2607.18261](https://arxiv.org/abs/2607.18261)).
- *Why it matters:* the downstream video agent parses our output.
- *Do:*
  - Define Pydantic models for `Script`, `Beat`, `HookStack` and `Brief`.
  - Export `model_json_schema()` as the versioned contract ([Pydantic](https://docs.pydantic.dev/latest/concepts/json_schema/)).
  - LLM path: free-form draft → schema fill → gates.

**5.2 Validators and failing loudly.**
- *What the sources say:* Guardrails AI validators declare an `on_fail` action: fix, reask, filter, refrain or exception ([docs](https://guardrailsai.com/docs/concepts/validator_on_fail_actions)). Instructor re-asks the model with the validation error ([docs](https://github.com/jxnl/instructor/blob/main/docs/concepts/reask_validation.md)).
- *Do:*
  - Auto-fix only idempotent formatting, and log each fix.
  - Semantic violations raise: exit 1 plus a report.
  - The LLM path gets at most 2 re-asks, each including the gate message.

**5.3 Policy-as-code.**
- *What the sources say:* OpenAI's January 2026 governance [cookbook](https://developers.openai.com/cookbook/examples/partners/agentic_governance_guide/agentic_governance_cookbook/) keeps policies as versioned config that ships with the code. It applies them to every call, scores guardrails by precision and recall, and runs red-team inputs through the same path.
- *Do:*
  1. **Rule-coverage CI test.** Each active D-rule needs a check plus at least one failing and one passing fixture. That makes AGENT-BRIEF's definition of "patched" automatic.
  2. **Conflict test.** Build each artifact a contract mandates and assert the gates accept it. The 28-word TEST/VERDICT card fails today (D103 vs D62/D83), which forces an explicit `precedence:` field.
  3. **Claims rule.** The `proof-first` hook family fills `{proof}` with `4.9★ / 12,000+ orders / sold out twice`, with no data behind it. It's dormant, but one pack refresh away, because the live ranking picks hook families. This is D37's fabrication class, and close to what the [FTC's 2024 fake-reviews rule](https://www.ftc.gov/news-events/news/press-releases/2024/08/federal-trade-commission-announces-final-rule-banning-fake-reviews-testimonials) targets. Allow social-proof numbers only when they come from the prompt or pack. Flag this for counsel; it isn't legal advice.
  4. **AI disclosure.** For `presenter=ai`, carry a disclosure flag. TikTok requires labels on realistic AI-generated content and reads C2PA Content Credentials, which are embedded provenance metadata ([TikTok](https://newsroom.tiktok.com/more-ways-to-spot-shape-and-understand-ai-content)).

## 6. Evaluation harness

**6.1 Golden, regression and capability suites.**
- *What the sources say:*
  - Anthropic's January 2026 [guide](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents): start with 20–50 tasks drawn from real failures. Keep capability suites (hill-climbing) separate from regression suites (about 100% pass), and graduate saturated tasks. Grade outcomes with partial credit, isolate trials, read transcripts, and harden graders.
  - OpenAI's [flywheel](https://developers.openai.com/cookbook/examples/evaluation/building_resilient_prompts_using_an_evaluation_flywheel) hand-labels about 50 failures, clusters them, then wires graders into CI.
  - Husain and Shankar favor error analysis first, and a pass-all rate grouped by severity ([FAQ](https://hamel.dev/blog/posts/evals-faq/)).
- *Why it matters:* the judge loop's verdicts need a fixed yardstick.
- *Do:*
  - Create `evals/golden.jsonl` with about 40 prompts, stratified by niche × format × presenter × concept.
  - Add every seed cited in RULES.md as a regression fixture that checks properties, not exact text.
  - Merging requires 100% pass-all on regression. Capability tracks rubric score and diversity.
  - Snapshot tests: a fixed (prompt, seed, code SHA, pack hash) must produce an identical output hash. Re-approve a snapshot only with a D-number.

**6.2 Scorecards and small-sample statistics.**
- *What the sources say:* Anthropic recommends standard errors, clustering, resampling within items, paired differences, and power analysis ([blog](https://www.anthropic.com/research/statistical-approach-to-model-evals); [paper](https://arxiv.org/abs/2411.00640)). Below a few hundred items, confidence intervals based on the normal approximation (CLT) mislead, so use Bayesian or Wilson-type intervals ([ICML 2025](https://arxiv.org/abs/2503.01747); [bayes_evals](https://github.com/sambowyer/bayes_evals)). When consistency matters, report pass^k, the chance all k trials pass ([Anthropic](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)).
- *Do:* produce a `scorecard.md` for every change.
  - **Contents:** pass-all rate with a Wilson or Beta CI, failures per rule, mean rubric score, pass^5 across seeds, and diversity (distinct-2, hook-family entropy, maximum pairwise Jaccard).
  - **Comparison:** run old vs new on the same prompts × seeds. Use an exact McNemar or sign test for pass/fail flips, and a paired bootstrap clustered by prompt for score changes.
  - **Verdict:** call it "IMPROVED" only if the paired 95% CI excludes 0 and regression stays at 100%.

## 7. Observability and reproducibility

**7.1 Traces.**
- *What the sources say:* OpenTelemetry's GenAI conventions have lived in their own repo since June 2026 and are still marked "Development". They define spans for model, agent and tool calls, plus a `gen_ai.evaluation.result` event carrying a name, a score value or label, and an explanation ([spec](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-events.md); [status](https://www.truefoundry.com/blog/opentelemetry-genai-semantic-conventions)). Langfuse's SDK builds on OpenTelemetry and adds datasets, experiments and scores ([Langfuse](https://langfuse.com/changelog/2025-06-05-python-sdk-v3-generally-available)).
- *Why it matters:* Anthropic credits full tracing for diagnosing agent failures ([source](https://www.anthropic.com/engineering/multi-agent-research-system)).
- *Do:*
  - Write a `trace.jsonl` per run: one record per stage (name, timing, input/output hashes).
  - Add one record per check, shaped like an evaluation result: `name=D43, label=fail, value, explanation`.
  - This needs no new dependencies. Add an OTLP exporter or Langfuse only when the LLM layer ships, and pin the conventions version.

**7.2 Run manifest.**
- *Why it matters:* without one, "seed 811 shipped X" can't be replayed or audited.
- *Do:* write `outputs/<slug>/manifest.json` containing:
  - the git SHA and dirty flag, Python version and CLI args;
  - the seed and all sub-seeds;
  - SHA-256 of RULES.md, `research_pack.json` (plus `generated_at`), `personas.json` and the template modules;
  - the route, every candidate with its scores, gate results, auto-fixes, the selected candidate and output hashes;
  - model IDs and prompt hashes, if an LLM ran.
  
  `--replay manifest.json` re-runs and asserts identical hashes.

**7.3 Reproducibility hazards found in the code.**
- **Shared RNG stream:** one `random.Random(seed)` feeds every slot, so any new draw shifts all later ones and silently changes regression seeds. Use a separate keyed stream per slot: `Random(int.from_bytes(sha256(f"{seed}:{slot}".encode()).digest()[:8], "big"))`. Keep `--rng legacy` to replay old bundles.
- **Python version drift:** Python only guarantees the `random()` sequence across versions; `choice` and `shuffle` may change ([docs](https://docs.python.org/3/library/random.html#notes-on-reproducibility)). Pin the interpreter.
- **Process-salted hashing:** never seed from `hash()`, which is salted per process ([PYTHONHASHSEED](https://docs.python.org/3/using/cmdline.html#envvar-PYTHONHASHSEED)). Avoid iterating over sets of strings, and call `json.dumps(sort_keys=True)` before hashing.
- **Daily pack refresh:** `research_pack.json` refreshes daily, so "same seed = same script" fails across days unless the pack hash is pinned (`--pack`).

---

## Top-15 upgrades, ranked by impact ÷ effort

| # | Upgrade | Impact | Effort |
|---|---|---|---|
| 1 | Run manifest + content hashes + `--replay` (7.2) | High | Low |
| 2 | Keyed per-slot RNG; pinned interpreter and pack (7.3) | High | Low |
| 3 | Claims rule: no unsourced social-proof numerals (5.3) | High (risk) | Low |
| 4 | `rubric.yaml` with tiers/weights + rule-coverage CI (3.1, 5.3) | Very high | Medium |
| 5 | Best-of-8 via sub-seeds + evaluation cascade + adaptive N (2.1) | Very high | Low–Med |
| 6 | Golden set: regression (100% pass-all) vs capability + snapshots (6.1) | High | Medium |
| 7 | Stage-0 voting router, fail-loud on disagreement (1.1, 2.3) | High | Medium |
| 8 | Rule-conflict tests + explicit precedence (resolves D103 vs D62/D83) (5.3) | Med–High | Low |
| 9 | Rule-keyed repair loop: keep best, max 3 (1.2, 2.4) | High | Medium |
| 10 | Paired-statistics scorecard (Wilson/Bayes, McNemar, paired bootstrap) (6.2) | Medium | Low |
| 11 | Input and research-pack tripwires (1.3) | Medium | Low |
| 12 | `trace.jsonl` with evaluation-result records (7.1) | Medium | Low |
| 13 | Pydantic → JSON Schema contract (5.1) | Medium | Low–Med |
| 14 | Hook MAP-Elites archive + novelty rejection (4.2) | High | Med–High |
| 15 | Optional LLM layer: calibrated pairwise judges (median of 3, advisory) + offline GEPA-style template evolution (3.2–4.1) | High | High |

**Suggested sequencing:**
- Items 1–3 take about a day.
- Items 4–8 make selection and improvement measurable.
- Items 9–13 harden the pipeline.
- Items 14–15 come only once the golden set reliably catches regressions.

*Content was rephrased for compliance with licensing restrictions.*
