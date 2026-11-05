"""Fixed terms in each language, and telling the LLM which language to write in."""
import json
from typing import get_args

import pytest
from fastapi.testclient import TestClient

from enclothed import api, config, db, i18n, intake, llm, responses
from enclothed import outfit as outfit_module
from enclothed.auth import signed_in_user
from enclothed.models import (
    ALL_SUBCATEGORIES, Category, Color, Fit, FORMALITY_LABELS, LANGUAGE_NAMES, Language, OutfitResult, Sheen, User,
    WARMTH_LABELS,
)

TRANSLATED = [language for language in get_args(Language) if language != "en-US"]
GROUPS = {
    "colors": set(get_args(Color)),
    "categories": set(get_args(Category)),
    "subcategories": ALL_SUBCATEGORIES,
    "fits": set(get_args(Fit)),
    "sheens": set(get_args(Sheen)),
    "formality": {str(value) for value in FORMALITY_LABELS},
    "warmth": {str(value) for value in WARMTH_LABELS},
}


# --- the lookups ---------------------------------------------------------------------
@pytest.mark.parametrize("language", TRANSLATED)
@pytest.mark.parametrize("group", GROUPS)
def test_every_term_is_translated_and_none_are_left_over(language, group):
    """Adding a color or subcategory fails here until both languages have it."""
    assert set(i18n.terms(language)[group]) == GROUPS[group]


@pytest.mark.parametrize("language", TRANSLATED)
def test_no_translation_is_blank_or_still_english(language):
    terms = i18n.terms(language)
    for group, words in terms.items():
        for english, word in words.items():
            assert word.strip(), f"{group}: {english}"
            assert word != english, f"{group}: {english}"


@pytest.mark.parametrize("group", ["colors", "subcategories"])
@pytest.mark.parametrize("language", TRANSLATED)
def test_two_terms_never_share_a_word(language, group):
    """Two values with one label couldn't be told apart in an edit menu."""
    words = list(i18n.terms(language)[group].values())
    assert len(words) == len(set(words))


def test_every_language_has_a_name_and_english_has_no_lookup():
    assert set(LANGUAGE_NAMES) == set(get_args(Language))
    assert i18n.terms("en-US") == {}


# --- /api/options --------------------------------------------------------------------
def test_english_options_are_unchanged():
    options = responses.get_options("en-US")
    assert options.category_labels == options.subcategory_labels == options.color_labels == {}
    assert next(f.label for f in options.fits if f.value == "slim") == "slim (close to the body)"
    assert options.formality[0].label == "casual"


@pytest.mark.parametrize("language", TRANSLATED)
def test_translated_options_keep_english_values(language):
    options = responses.get_options(language)
    assert [f.value for f in options.fits] == list(get_args(Fit))
    assert options.subcategories == responses.get_options("en-US").subcategories
    assert options.color_labels["black"] == i18n.terms(language)["colors"]["black"]
    assert options.fits[0].label == i18n.terms(language)["fits"]["slim"]
    assert options.warmth[0].label == i18n.terms(language)["warmth"]["1"]


def test_options_list_the_languages_to_choose_from():
    assert [(l.value, l.label) for l in responses.get_options().languages] == list(LANGUAGE_NAMES.items())


# --- prompts -------------------------------------------------------------------------
def test_english_prompts_are_unchanged():
    assert llm.tag_system_prompt("en-US") == llm.TAG_SYSTEM_PROMPT
    assert llm.outfit_system_prompt("en-US") == llm.OUTFIT_SYSTEM_PROMPT


@pytest.mark.parametrize("language", TRANSLATED)
def test_tagging_prompt_names_the_translated_fields_and_keeps_fixed_values_english(language):
    prompt = llm.tag_system_prompt(language)
    assert prompt.startswith(llm.TAG_SYSTEM_PROMPT)
    assert llm.LANGUAGE_DESCRIPTIONS[language] in prompt
    for field in ["styling_notes", "style_tags", "pattern", "country_of_origin", "materials"]:
        assert field in prompt.split("Language:")[1].split("\n")[1]
    assert "exact English values" in prompt


@pytest.mark.parametrize("language", TRANSLATED)
def test_outfit_prompt_names_every_written_field(language):
    rule = llm.outfit_system_prompt(language).split("Language:")[1].split("\n")[1]
    for field in ["aesthetic", "explanation", "styling_advice", "missing"]:
        assert field in rule
    assert llm.LANGUAGE_DESCRIPTIONS[language] in rule


@pytest.mark.parametrize("language", TRANSLATED)
def test_prompts_carry_the_same_words_as_the_labels(language):
    word = i18n.terms(language)["subcategories"]["varsity jacket"]
    assert f"varsity jacket = {word}" in llm.outfit_system_prompt(language)
    assert f"varsity jacket = {word}" in llm.tag_system_prompt(language)


def test_every_translated_language_has_a_description():
    assert set(llm.LANGUAGE_DESCRIPTIONS) == set(TRANSLATED)


# --- the API -------------------------------------------------------------------------
@pytest.fixture
def client(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    db.init_db(path, config.SCHEMA_PATH, config.MIGRATIONS_DIR)
    bob_id = db.insert_user(path, "bob", "bob@example.com")
    assert bob_id == 2
    monkeypatch.setattr(api, "DB_PATH", path)
    monkeypatch.setattr(config, "DB_PATH", path)
    monkeypatch.setattr(api, "OUTFIT_LOG_PATH", tmp_path / "outfit_log.jsonl")
    api.app.dependency_overrides[signed_in_user] = lambda: db.select_user(path, 1)
    yield TestClient(api.app)
    api.app.dependency_overrides.clear()


def test_language_is_saved_and_shows_in_profile_and_options(client):
    assert client.put("/api/language", json={"language": "zh-TW"}).status_code == 204
    assert client.get("/api/profile").json()["language"] == "zh-TW"
    assert client.get("/api/options").json()["color_labels"]["black"] == "黑色"


def test_unknown_language_is_rejected(client):
    assert client.put("/api/language", json={"language": "fr-FR"}).status_code == 422
    assert client.get("/api/profile").json()["language"] == "en-US"


def test_viewing_as_someone_uses_and_changes_their_language(client):
    db.set_language(api.DB_PATH, 2, "ja-JP")
    client.put("/api/act-as", json={"user_id": 2})
    assert client.get("/api/profile").json()["language"] == "ja-JP"
    assert client.get("/api/options").json()["color_labels"]["black"] == "ブラック"

    client.put("/api/language", json={"language": "zh-TW"})
    assert db.select_user(api.DB_PATH, 2).language == "zh-TW"
    assert db.select_user(api.DB_PATH, 1).language == "en-US"


def test_suggestions_are_written_in_the_wardrobe_owners_language(client, monkeypatch):
    seen = {}
    def fake_recommend(_client, context, language):
        seen["language"] = language
        return OutfitResult(outfits=[]), None
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(outfit_module, "recommend_outfits", fake_recommend)
    db.set_language(api.DB_PATH, 2, "zh-TW")
    client.put("/api/act-as", json={"user_id": 2})
    client.post("/api/outfits/suggestions", json={"details": "dinner"})
    assert seen["language"] == "zh-TW"


def test_tagging_passes_the_language_to_the_llm(tmp_path, monkeypatch):
    staged = tmp_path / "front.jpg"
    staged.write_bytes(b"x")
    seen = {}
    def fake_tag(client, photo_paths, prompt_message, language):
        seen["language"] = language
        raise llm.UnusableResponse("stop here", llm.TokenUsage(model="m", input_tokens=0, output_tokens=0))
    monkeypatch.setattr(intake, "tag_garment", fake_tag)
    with pytest.raises(llm.UnusableResponse):
        intake.add_garment(2, [str(staged)], tmp_path / "db", tmp_path, tmp_path, tmp_path / "log.jsonl", None, False, language="ja-JP")
    assert seen["language"] == "ja-JP"


def test_locale_files_are_utf8_json():
    for path in config.LOCALES_DIR.glob("*.json"):
        assert set(json.loads(path.read_text(encoding="utf-8"))) == set(GROUPS)
