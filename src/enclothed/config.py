from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
PKG_DIR = Path(__file__).resolve().parent
DB_PATH = DATA_DIR / "enclothed.db"
GARMENTS_DIR = DATA_DIR / "garments"
THUMBS_DIR = DATA_DIR / "thumbs"
INTAKE_DIR = DATA_DIR / "intake"
SCHEMA_PATH = PKG_DIR / "schema.sql"
TAGGING_LOG_PATH = DATA_DIR / "tagging_log.jsonl"
OUTFIT_LOG_PATH = DATA_DIR / "outfit_log.jsonl"
PREFERENCES_LOG_PATH = DATA_DIR / "preferences_log.jsonl"
BACKUPS_DIR = PROJECT_ROOT / "backups"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"
PUBLIC_DIR = PROJECT_ROOT / "public"

CLAUDE_MODEL = "claude-sonnet-5-5"
TEST_CLAUDE_MODEL = "claude-haiku-5-5"
MAX_LLM_ATTEMPTS = 2
TAG_TOKEN_CAP = 2048
OUTFIT_TOKEN_CAP = 8192
MIN_OUTFIT_SUGGESTIONS = 2
MAX_OUTFIT_SUGGESTIONS = 4

THUMB_SIZE = (600, 800)          # longest edges of a thumbnail, in pixels
UPLOAD_MAX_SIDE = 2000           # uploaded photos are resized so the longest side is at most this
UPLOAD_MAX_PHOTOS = 10
UPLOAD_MAX_BYTES = 40 * 1024 * 1024
MANUAL_OUTFIT_REQUEST = "Put together myself"
PREFERENCES_MAX_CHARS = 4000
PREFERENCES_TOKEN_CAP = 1024
