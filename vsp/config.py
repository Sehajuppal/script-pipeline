"""Paths and environment — one resolver for every module (CLI > env > default).

Env vars (all optional):
  VSP_VIRAL_DB        research DB (default ~/workspace/viral-research/viral.db)
  VSP_RESEARCH_PACK   research pack JSON (default <repo>/research_pack.json)
  VSP_DOSSIER_DIR     dossier directory (default
                      ~/workspace/goals/neuro-ad-research-program/files)
  VSP_OUTPUTS         outputs root (default <repo>/outputs)
  VSP_FIXTURE_OK=1    allow FIXTURE reference reels (self-test / evals only)
"""
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_DB = "~/workspace/viral-research/viral.db"
DEFAULT_DOSSIER_DIR = "~/workspace/goals/neuro-ad-research-program/files"
DOSSIER_FILES = {
    "ugc": "ugc-persuasion-dossier.md",
    "persona": "ai-persona-persuasion-dossier.md",
}


def viral_db_path():
    return os.path.expanduser(os.environ.get("VSP_VIRAL_DB") or DEFAULT_DB)


def research_pack_path():
    return os.environ.get("VSP_RESEARCH_PACK") or os.path.join(
        REPO, "research_pack.json")


def dossier_paths():
    d = os.path.expanduser(os.environ.get("VSP_DOSSIER_DIR")
                           or DEFAULT_DOSSIER_DIR)
    return {k: os.path.join(d, f) for k, f in DOSSIER_FILES.items()}


def outputs_dir():
    return os.environ.get("VSP_OUTPUTS") or os.path.join(REPO, "outputs")


def personas_path():
    return os.path.join(REPO, "personas.json")


def rules_path():
    return os.path.join(REPO, "RULES.md")


def fixture_ok():
    return os.environ.get("VSP_FIXTURE_OK") == "1"


def db_readable(path=None):
    """True only if the DB file exists and is non-empty. Never creates it
    (sqlite3.connect on a missing path would create an empty file)."""
    p = path or viral_db_path()
    return os.path.isfile(p) and os.path.getsize(p) > 0


def connect_ro(path=None):
    """Read-only SQLite connection, or None if the DB is absent."""
    import sqlite3
    p = path or viral_db_path()
    if not db_readable(p):
        return None
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
