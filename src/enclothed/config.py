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
INSIGHTS_LOG_PATH = DATA_DIR / "insights_log.jsonl"
PREFERENCES_LOG_PATH = DATA_DIR / "preferences_log.jsonl"
WEIGH_LOG_PATH = DATA_DIR / "weigh_log.jsonl"
BACKUPS_DIR = PROJECT_ROOT / "backups"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"
PUBLIC_DIR = PROJECT_ROOT / "public"
LOCALES_DIR = PKG_DIR / "locales"

DEFAULT_USER_ID = 1
CLAUDE_MODEL = "claude-sonnet-5-5"
TEST_CLAUDE_MODEL = "claude-haiku-5-5"
MAX_LLM_ATTEMPTS = 2
TAG_TOKEN_CAP = 2048
MEND_TOKEN_CAP = 2048
DRAFT_MAX_AGE_SECONDS = 24 * 60 * 60   # a garment left in review this long is cleaned up
MEND_MAX_PHOTO_BYTES = 4 * 1024 * 1024   # the API refuses images over 5 MB, and base64 adds a third
OUTFIT_TOKEN_CAP = 8192
MIN_OUTFIT_COUNT = 1
MAX_OUTFIT_COUNT = 5        # each outfit adds output tokens and latency under OUTFIT_TOKEN_CAP
DEFAULT_OUTFIT_COUNT = 3
WEIGH_OUTFIT_COUNT = 3       # outfits built around a garment being weighed, one per tier
WEIGH_SIMILAR_LIMIT = 5      # owned garments shortlisted for the "already own it?" check
DESCRIBE_TOKEN_CAP = 1024     # a name and two or three sentences

INSIGHTS_VALUE_SIZE_LIMIT = 10_000_000
INSIGHTS_SIZE_FUSE_LIMIT = 400_000
INSIGHTS_TIME_LIMIT = 2
INSIGHTS_TOKEN_CAP = 8192
INSIGHTS_MAX_TURNS = 6

THUMB_SIZE = (600, 800)          # longest edges of a thumbnail, in pixels
UPLOAD_MAX_SIDE = 2000           # uploaded photos are resized so the longest side is at most this
UPLOAD_MAX_PHOTOS = 10
UPLOAD_MAX_BYTES = 40 * 1024 * 1024
MANUAL_OUTFIT_REQUEST = "Put together myself"
PREFERENCES_MAX_CHARS = 4000
PREFERENCES_TOKEN_CAP = 1024

# The shared demo wardrobe (demo.py). 8:00 UTC is 3 or 4 AM in New York. The limit counts input and
# output tokens since the last reset; at Sonnet prices, 200,000 is roughly $0.50 to $1 a day.
DEMO_USERNAME = "demo"
DEMO_TEMPLATE_DIR = DATA_DIR / "demo-template"
DEMO_OUTFIT_REQUEST = "Sample outfit"
DEMO_PER_CATEGORY = 5
DEMO_MAX_OUTFITS = 8
DEMO_RESET_HOUR_UTC = 8
DEMO_DAILY_TOKEN_LIMIT = 200_000

# Dollars per million tokens, for the usage page's estimates. cache_write is the 5-minute rate, the
# only cache this app uses. Haiku's prices are for prompts up to 100,000 tokens. Update these when
# Anthropic's prices change, and add any new model: a model missing here shows tokens but no cost.
# https://platform.claude.com/docs/en/about-claude/pricing
MODEL_PRICES = {
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00, "cache_write": 2.50, "cache_read": 0.10},
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50, "cache_write": 0.125, "cache_read": 0.01},
}
