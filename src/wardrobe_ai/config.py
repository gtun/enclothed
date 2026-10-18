from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
PKG_DIR = Path(__file__).resolve().parent
DB_PATH = DATA_DIR / "wardrobe.db"
GARMENTS_DIR = DATA_DIR / "garments"
INTAKE_DIR = DATA_DIR / "intake"
SCHEMA_PATH = PKG_DIR / "schema.sql"
TAGGING_LOG_PATH = DATA_DIR / "tagging_log.jsonl"
BACKUPS_DIR = PROJECT_ROOT / "backups"

CLAUDE_MODEL = "claude-sonnet-5-5"
TEST_CLAUDE_MODEL = "claude-haiku-5-5"
MAX_LLM_ATTEMPTS = 2