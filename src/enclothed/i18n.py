"""Fixed terms in other languages. The database and the LLM always use the English value;
these are only what a person sees. Each file in locales/ has the same groups:
colors, categories, subcategories, fits, sheens, formality, warmth."""
import json
from functools import lru_cache

from enclothed import config
from enclothed.models import DEFAULT_LANGUAGE, Language


@lru_cache
def terms(language: Language) -> dict[str, dict[str, str]]:
    """Every translated term for a language, by group. English has none: its terms are the values."""
    if language == DEFAULT_LANGUAGE:
        return {}
    return json.loads((config.LOCALES_DIR / f"{language}.json").read_text(encoding="utf-8"))
