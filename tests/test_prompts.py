import ast
from typing import get_args

import pytest

from enclothed import i18n, prompts
from enclothed.models import DEFAULT_LANGUAGE, Language

TRANSLATED = [language for language in get_args(Language) if language != DEFAULT_LANGUAGE]

# Each per-language prompt, and the English prompt it adds to.
PROMPTS = {
    "tag": (prompts.tag_system_prompt, prompts.TAG_SYSTEM_PROMPT),
    "look": (prompts.look_tag_system_prompt, prompts.LOOK_TAG_SYSTEM_PROMPT),
    "outfits": (prompts.outfit_system_prompt, prompts.OUTFIT_SYSTEM_PROMPT),
    "describe": (prompts.describe_system_prompt, prompts.DESCRIBE_SYSTEM_PROMPT),
    "insights": (prompts.insights_system_prompt, prompts.INSIGHTS_SYSTEM_PROMPT),
}


@pytest.mark.parametrize("name", PROMPTS)
def test_english_gets_the_prompt_as_written(name):
    build, english = PROMPTS[name]
    assert build(DEFAULT_LANGUAGE) == english


@pytest.mark.parametrize("language", TRANSLATED)
@pytest.mark.parametrize("name", PROMPTS)
def test_another_language_adds_its_section_after_the_english_prompt(name, language):
    build, english = PROMPTS[name]
    prompt = build(language)
    assert prompt.startswith(english)
    section = prompt[len(english):]
    assert "Language:" in section
    assert prompts.LANGUAGE_DESCRIPTIONS[language] in section
    word = i18n.terms(language)["subcategories"]["varsity jacket"]
    assert f"varsity jacket = {word}" in section


def test_prompts_is_text_only():
    """The calls, and anything provider-specific, stay in llm.py."""
    tree = ast.parse(open(prompts.__file__, encoding="utf-8").read())
    imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imported |= {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not imported & {"anthropic", "openai", "enclothed.llm"}
