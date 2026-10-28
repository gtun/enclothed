from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
PKG_DIR = Path(__file__).resolve().parent
DB_PATH = DATA_DIR / "wardrobe.db"
GARMENTS_DIR = DATA_DIR / "garments"
INTAKE_DIR = DATA_DIR / "intake"
SCHEMA_PATH = PKG_DIR / "schema.sql"
TAGGING_LOG_PATH = DATA_DIR / "tagging_log.jsonl"
OUTFIT_LOG_PATH = DATA_DIR / "outfit_log.jsonl"
BACKUPS_DIR = PROJECT_ROOT / "backups"
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"

CLAUDE_MODEL = "claude-sonnet-5-5"
TEST_CLAUDE_MODEL = "claude-haiku-5-5"
MAX_LLM_ATTEMPTS = 2
TAG_TOKEN_CAP = 2048
OUTFIT_TOKEN_CAP = 8192
MIN_OUTFIT_SUGGESTIONS = 2
MAX_OUTFIT_SUGGESTIONS = 4
