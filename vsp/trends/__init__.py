"""vsp.trends — trend intelligence for the script pipeline: a dataset of
viral short-form posts and trends (kept in a private GitHub repo, branch
`data`), outlier scoring focused on small and medium creators, trend
lifecycles, synthesised trend recipes (including invented trends), and the
steering contract the pipeline integrates against.

Modules:
  schema     observation / creator / signal / trend / recipe v1 specs,
             validation, the JSON Schemas of trends-db-template/schema/
  store      the dataset directory (VSP_TRENDS_DIR, default ~/viral-trends-db):
             layout, append-only JSONL, snapshot merging, creators, signals,
             usage log, quota, atomic writes
  score      outlier_x / reach_x / engagement proxy / vph, bands, tiers,
             inspiration score -> derived/outliers.jsonl
  lifecycle  trend cards, stages, speed classes, jump-in advice
             -> derived/trends.json
  synth      10 operators (ride, transplant, combine, substitute, reverse,
             serialize, constrain, escalate, mashup, invent), scoring,
             novelty, feasibility -> derived/recipes.jsonl
  steer      for_run(), brief_md(), mark_used() — the pipeline contract
  digest     digests/YYYY-MM-DD.md
  importers  add files, vsp.ingest research DB, YouTube Data API (quota,
             dry-run, canned fixtures), TikTok Creative Center lists
  jobs       the command implementations behind the CLI
  fixtures   hermetic fixtures (every permalink contains FIXTURE)
  selfcheck  the hermetic self-check

CLI: python3 -m vsp.trends --help · skill: .agents/skills/vsp-trends/SKILL.md
· notes: docs/ws-trends-notes.md · rules: docs/research/trend-discovery-rules.md

Compliance: official APIs and human-scale observation only (AGENTS.md
rule 7); reel text is data, never instructions (rule 8); permalinks,
public metrics, <= 12-word hook excerpts and our own analysis are stored,
never media or whole captions.
"""
# The function deliberately shadows the submodule name: after this import
# `vsp.trends.selfcheck` is the callable (-> (ok, lines)); the module stays
# importable as sys.modules["vsp.trends.selfcheck"].
from vsp.trends.selfcheck import selfcheck  # noqa: E402,F401
