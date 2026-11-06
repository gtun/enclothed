# tests/test_models.py
import re
from typing import get_args

import pytest
from pydantic import ValidationError

from enclothed.fabrics import FABRIC_GROUPS, FABRIC_TYPES
from enclothed.models import (
    FABRIC_WEIGHT_LABELS, FabricWeight, HEM_LABELS, Hem, SHAPE_LABELS, Shape, SLEEVE_LABELS, Sleeve, STATEMENT_LABELS,
    Statement, color_traits, layer_for,
)
from enclothed.models import Category, Color, COLOR_HEX, Fit, FIT_LABELS, FORMALITY_LABELS, Garment, Sheen, SHEEN_LABELS, SUBCATEGORIES, WARMTH_LABELS

def make_top(**fields):
    return Garment(category="top", subcategory="t-shirt", primary_color="black", styling_notes="x", **fields)


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


def test_every_new_choice_has_a_label():
    assert set(SHAPE_LABELS) == set(get_args(Shape))
    assert set(HEM_LABELS) == set(get_args(Hem))
    assert set(FABRIC_WEIGHT_LABELS) == set(get_args(FabricWeight))
    assert set(SLEEVE_LABELS) == set(get_args(Sleeve))
    assert set(STATEMENT_LABELS) == set(get_args(Statement))


# --- fabrics ---------------------------------------------------------------------------

def test_the_fabric_list_is_broad_and_has_no_repeats():
    listed = [fabric for fabrics in FABRIC_GROUPS.values() for fabric in fabrics]
    assert len(listed) == len(set(listed))
    assert len(FABRIC_TYPES) >= 200
    assert "other" in FABRIC_TYPES


def test_a_listed_fabric_is_kept():
    assert make_top(fabric_type="selvedge denim").fabric_type == "selvedge denim"


def test_a_fabric_off_the_list_becomes_other():
    assert make_top(fabric_type="moon cloth").fabric_type == "other"


def test_a_blank_fabric_stays_blank():
    assert make_top().fabric_type is None


@pytest.mark.parametrize("field", ["shape", "hem", "fabric_weight", "sleeve", "statement"])
def test_the_other_attributes_only_take_listed_values(field):
    with pytest.raises(ValidationError):
        make_top(**{field: "nonsense"})


# --- worked-out values -----------------------------------------------------------------

@pytest.mark.parametrize("category, subcategory, layer", [
    ("top", "t-shirt", "base"),
    ("top", "oxford shirt", "base"),
    ("top", "crewneck sweater", "mid"),
    ("top", "cardigan", "mid"),
    ("outerwear", "fleece", "mid"),
    ("outerwear", "vest", "mid"),
    ("outerwear", "parka", "outer"),
    ("bottom", "jeans", None),
    ("shoes", "loafers", None),
])
def test_layer_comes_from_the_subcategory(category, subcategory, layer):
    assert layer_for(category, subcategory) == layer


@pytest.mark.parametrize("color, family, temperature, lightness, saturation", [
    ("black", "neutral", "neutral", "dark", "muted"),
    ("white", "neutral", "neutral", "light", "muted"),
    ("navy", "neutral", "cool", "dark", "muted"),
    ("cream", "neutral", "warm", "light", "muted"),
    ("red", "color", "warm", "medium", "vivid"),
    ("teal", "color", "cool", "dark", "medium"),
    ("gold", "metallic", "warm", "medium", "vivid"),
])
def test_color_traits_come_from_the_hex(color, family, temperature, lightness, saturation):
    assert color_traits(color) == {"family": family, "temperature": temperature, "lightness": lightness, "saturation": saturation}


def test_every_color_has_traits():
    for color in get_args(Color):
        assert set(color_traits(color)) == {"family", "temperature", "lightness", "saturation"}
