from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "wardrobe.db"

CLAUDE_MODEL = "claude-sonnet-5-5"
TEST_CLAUDE_MODEL = "claude-haiku-5-5"
ADD_GARMENT_MAX_TAG_ATTEMPTS = 2