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
MIMIC_LOG_PATH = DATA_DIR / "mimic_log.jsonl"
REWORK_LOG_PATH = DATA_DIR / "rework_log.jsonl"   # image calls, which log image_usage, not usage
REWORKS_DIR = DATA_DIR / "reworks"   # Rework's edited images, <id>.jpg, kept apart from garment photos
LOOKS_DIR = DATA_DIR / "looks"          # photos of looks to recreate (mimic), one folder per look
# Copies of a share link's photos, one folder per link. Under thumbs/ because the NAS backup skips it: shares
# last a few days, and the pull never deletes, so they would pile up there forever.
SHARES_DIR = THUMBS_DIR / "shares"
BACKUPS_DIR = PROJECT_ROOT / "backups"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"
PUBLIC_DIR = PROJECT_ROOT / "public"
LOCALES_DIR = PKG_DIR / "locales"

DEFAULT_USER_ID = 1
# Which LLM provider runs every AI feature: a key of MODELS_BY_PROVIDER. ENCLOTHED_LLM_PROVIDER in .env overrides it.
# Only llm.py reads either one (llm.active_provider), at each call, because .env loads after this file is imported.
LLM_PROVIDER = "anthropic"
# Which model each AI feature uses, for each provider. Every provider lists the same features. Within a provider the
# features share one API, so switching a feature is a change to its line.
# Thinking counts toward max_tokens, so ANTHROPIC_THINKING_ALLOWANCE is added to the feature's token cap below on the
# models that think at length first. Opus and Fable always do. Haiku 5.5 does too: tagging on it used 1,400-2,000 output
# tokens and cut off at the 2,048 cap on 3 of 12 garments (eval-tags, 21 Nov 2026). Opus and Fable are also slower, and
# the site's proxy gives up on a request after 100 seconds.
# Weigh and mimic's matching step use "outfits": they share the cached wardrobe only while they're on the same model.
ANTHROPIC_MODELS: dict[str, str] = {
    "tag": "claude-sonnet-5-5",          # reading photos and labels into a garment record. Opus 5.5 matched no more
                                         # saved fields (97 of 132 against 101) at twice the cost (eval-tags, 21 Nov 2026)
    "mend": "claude-haiku-5-5",          # filling a garment's blank fields from its photos, a narrower job than tag
    "outfits": "claude-sonnet-5-5",      # outfit suggestions, weigh, and matching a look to the wardrobe (mimic)
    "look": "claude-sonnet-5-5",         # reading a photographed look into its pieces (mimic)
    "describe": "claude-haiku-5-5",      # a name and "why it works" for an outfit you put together
    "preferences": "claude-haiku-5-5",   # tidying your style notes
    "insights": "claude-opus-5-5",       # "Ask your wardrobe": writes SQL over several steps, so accuracy matters
}
ANTHROPIC_THINKING_MODELS = {"claude-opus-5-5", "claude-fable-5-2", "claude-haiku-5-5"}
ANTHROPIC_THINKING_ALLOWANCE = 8_000   # keeps insights' cap near 16,000, which a non-streaming request stays under
# GPT-6.1 Terra is OpenAI's recommended model for visual work, so the photo features stay on it. The short text
# features use GPT-6 Luna, as Claude uses Haiku, and insights uses GPT-6.1 Sol, as Claude uses its bigger model.
OPENAI_MODELS: dict[str, str] = {
    "tag": "gpt-6.1-terra",
    "mend": "gpt-6.1-terra",
    "outfits": "gpt-6.1-terra",
    "look": "gpt-6.1-terra",
    "describe": "gpt-6-luna",
    "preferences": "gpt-6-luna",
    "insights": "gpt-6.1-sol",
}
# How the page names each provider and model, in the admin's LLM picker (hold L and click an AI button).
PROVIDER_NAMES = {"anthropic": "Claude", "openai": "OpenAI"}
MODEL_NAMES = {
    "claude-opus-5-5": "Claude Opus 5.5", "claude-sonnet-5-5": "Claude Sonnet 5.5", "claude-haiku-5-5": "Claude Haiku 5.5",
    "gpt-6.1-sol": "GPT-6.1 Sol", "gpt-6.1-terra": "GPT-6.1 Terra", "gpt-6-luna": "GPT-6 Luna",
}
MODELS_BY_PROVIDER: dict[str, dict[str, str]] = {
    "anthropic": ANTHROPIC_MODELS,
    "openai": OPENAI_MODELS,
}
# How hard OpenAI reasons for each feature. Reading photos and writing SQL get "high"; picking outfits from a listed
# wardrobe gets "medium", which halved Terra's output tokens with no validation problems (eval-outfits, 21 Nov 2026);
# a name and a sentence or two, or tidied notes, need little thought.
OPENAI_REASONING_EFFORT: dict[str, str] = {
    "tag": "high",
    "mend": "high",
    "outfits": "medium",
    "look": "high",
    "describe": "low",
    "preferences": "low",
    "insights": "high",
}
# On OpenAI, reasoning tokens count toward max_output_tokens, so this is added to a feature's token cap below.
# OpenAI suggests reserving 25,000 for reasoning and output when starting out; tune it from the logged reasoning tokens.
OPENAI_REASONING_ALLOWANCE = 25_000
# "high" keeps a photo's full size up to 2048 px a side on the models the docs list sizes for, and uploads are at most
# UPLOAD_MAX_SIDE. The docs don't list Terra's sizes or say whether it accepts "original".
OPENAI_IMAGE_DETAIL = "high"
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
LOOK_TAG_TOKEN_CAP = 4096     # every piece in a look, each with about as many fields as a garment
MIMIC_MAX_OUTFITS = 2         # recreations of a look: the closest, and a second only when it's about as close
MIMIC_SHORTLIST_LIMIT = 3     # owned garments suggested per piece of a look, as a hint for the matching step

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
SHARE_LIFETIME_DAYS = 3          # a share link works for this long, then its copy is deleted; extending resets it to this
SHARE_MAX_LIFETIME_DAYS = 12     # however often it's extended, a link ends this long after it was made
SHARE_PHOTO_SIDE = 1600          # longest side of a shared photo; its thumbnail uses THUMB_SIZE
DEMO_SHARE_LIMIT = 15            # most live share links the shared demo can have at once
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
DEMO_DAILY_REWORK_LIMIT = 3   # image calls are priced per image (about 2.5 cents), so they're counted apart from tokens

# Dollars per million tokens, for the usage page's estimates. cache_write is Anthropic's 5-minute rate, the
# only cache this app asks for, and OpenAI's default 30-minute rate. Haiku's prices are for prompts up to 100,000 tokens. Update these when
# Anthropic's prices change, and add any new model: a model missing here shows tokens but no cost.
# https://platform.claude.com/docs/en/about-claude/pricing
MODEL_PRICES = {
    "claude-opus-5-5": {"input": 4.00, "output": 20.00, "cache_write": 5.00, "cache_read": 0.20},
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00, "cache_write": 2.50, "cache_read": 0.10},
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50, "cache_write": 0.125, "cache_read": 0.01},
    # https://developers.openai.com/api/docs/pricing, standard tier, prompts up to 272,000 tokens
    "gpt-6.1-sol": {"input": 2.00, "output": 10.00, "cache_write": 2.50, "cache_read": 0.10},
    "gpt-6.1-terra": {"input": 1.00, "output": 5.00, "cache_write": 1.25, "cache_read": 0.05},
    "gpt-6-luna": {"input": 0.10, "output": 0.50, "cache_write": 0.125, "cache_read": 0.01},
}

# Rework (#74): an image model edits a garment's photo from an instruction such as "make it bright blue". Claude makes
# no images, so this is OpenAI whatever LLM_PROVIDER says. 2.5 Sunburst looked as good as 2.6 Flare at half the cost
# (eval-previews, 23 Nov 2026). OpenAI recommends GPT-Image-2.5 Sunburst "where editing
# precision matters most"; 2.6 Sunburst ("image editing workflows") and 2.6 Flare ("fast iteration") cost the same.
PREVIEW_MODEL = "gpt-image-2.5-sunburst"
PREVIEW_QUALITY = "medium"   # low, medium, high, xhigh, max or auto: higher costs more output tokens
# Dollars per million tokens. Image models price text and image input apart, so MODEL_PRICES can't hold them.
# https://developers.openai.com/api/docs/models/gpt-image-2.5-sunburst (and the 2.6 pages), standard tier, 23 Nov 2026.
# Cached input is cheaper, but OpenAI applies no cache to direct Images API edits, so it isn't listed.
IMAGE_MODEL_PRICES = {
    model: {"text_input": 5.00, "image_input": 8.00, "output": 30.00}
    for model in ("gpt-image-2.5-sunburst", "gpt-image-2.6-sunburst", "gpt-image-2.6-flare")
}
