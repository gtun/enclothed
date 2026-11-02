# tests/test_models.py
import re
from typing import get_args
from enclothed.models import Category, Color, COLOR_HEX, Fit, FIT_LABELS, FORMALITY_LABELS, Garment, Sheen, SHEEN_LABELS, SUBCATEGORIES, WARMTH_LABELS

def test_subcategories_cover_every_category():
    assert set(get_args(Category)) == set(SUBCATEGORIES)


# --- display data for the front end ---------------------------------------------------

def test_every_color_has_a_hex():
    assert set(COLOR_HEX) == set(get_args(Color))


def test_every_hex_is_a_six_digit_color():
    bad = {name: value for name, value in COLOR_HEX.items() if not re.fullmatch(r"#[0-9a-f]{6}", value)}
    assert not bad


def _bounds(field_name):
    metadata = Garment.model_fields[field_name].metadata
    lower = next(m.ge for m in metadata if hasattr(m, "ge"))
    upper = next(m.le for m in metadata if hasattr(m, "le"))
    return lower, upper


def test_formality_labels_cover_the_allowed_range():
    lower, upper = _bounds("formality")
    assert sorted(FORMALITY_LABELS) == list(range(lower, upper + 1))


def test_warmth_labels_cover_the_allowed_range():
    lower, upper = _bounds("warmth")
    assert sorted(WARMTH_LABELS) == list(range(lower, upper + 1))


def test_every_fit_has_a_label():
    assert set(FIT_LABELS) == set(get_args(Fit))


def test_every_sheen_has_a_label():
    assert set(SHEEN_LABELS) == set(get_args(Sheen))
