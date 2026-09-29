"""vsp.ingest — compliant ingestion of the LATEST Instagram Reels into the
research DB (viral.db), per docs/research/instagram-data-access.md.

Official routes only (Instagram API with Facebook Login for Business, Graph
API version pinned, default v26.0): Hashtag Search (30 unique hashtags per
rolling 7 days, enforced locally before any call), Business Discovery on a
benchmark watchlist, the account's own media + insights. Legitimate exports
(your own, official-API vendors) come in through the importer, tagged by
source; vendor:* rows are flagged because scraped data may violate
Instagram's Terms (research doc §7). media_url is never persisted.

Modules:
  db          RW connection, idempotent migrations, meta/schema_version
  graph       Graph API client (injectable transport), hashtag budget,
              usage-header backoff, retries, permission-naming errors
  normalize   API items -> reels rows, caption hooks, upsert
  importers   JSON/CSV exports -> reels rows (validated, deduped)
  classify    hook_category / hook family / pattern (+ aggregates)
  transcribe  optional first-3.5 s ASR (Muse Voice Transcribe)
  settings    config/ingest.json (template config/ingest.example.json)
  jobs        the runnable jobs behind the CLI
  checks      the hermetic selfcheck

CLI: python3 -m vsp.ingest --help
"""
from vsp.ingest.db import SCHEMA_VERSION  # noqa: F401


def selfcheck():
    """Hermetic self-check -> (ok: bool, lines: list[str]). Temp DB via
    VSP_VIRAL_DB, temp learned dir via VSP_LEARNED_DIR, canned Graph API
    responses from tests/fixtures/ig/, network disabled. Restores the
    caller's environment."""
    from vsp.ingest.checks import run
    return run()
