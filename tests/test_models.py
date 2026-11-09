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


# --- Claude's side of the tagging contract (2026-11-08: "Schema is too complex") ------------
from pydantic import create_model

from enclothed.models import (
    MENDABLE_FIELDS, ImprovedPreferences, OutfitDescription, OutfitResult, TaggedGarment, TaggingReply, UNKNOWN, WeighResult,
)


def schema_cost(model) -> tuple[int, int]:
    """(optional fields, "value or nothing" fields) across the whole schema, as the API counts them."""
    optional = unions = 0

    def walk(node):
        nonlocal optional, unions
        if isinstance(node, dict):
            required = set(node.get("required", []))
            for name, prop in node.get("properties", {}).items():
                optional += name not in required
                unions += "anyOf" in prop or isinstance(prop.get("type"), list)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(model.model_json_schema())
    return optional, unions


def test_tagged_garment_has_exactly_the_fields_claude_sees_on_garment():
    # A new Garment field must be added to TaggedGarment too, or tagging silently stops filling it
    assert set(TaggedGarment.model_fields) == set(Garment.model_json_schema()["properties"])


@pytest.mark.parametrize("field", ["fit", "sheen", "shape", "hem", "fabric_weight", "sleeve", "statement"])
def test_tagged_choices_are_garments_plus_unknown(field):
    garment_choices = set(get_args(get_args(Garment.model_fields[field].annotation)[0]))
    assert set(get_args(TaggedGarment.model_fields[field].annotation)) == garment_choices | {UNKNOWN}


def test_tagging_and_mend_schemas_have_no_optional_fields():
    every_blank = create_model("BlankFields", **{f: (TaggedGarment.model_fields[f].annotation, TaggedGarment.model_fields[f]) for f in MENDABLE_FIELDS})
    assert schema_cost(TaggingReply) == (0, 0)
    assert schema_cost(every_blank) == (0, 0)


@pytest.mark.parametrize("model", [OutfitResult, WeighResult, OutfitDescription, ImprovedPreferences])
def test_other_llm_schemas_stay_well_under_the_api_limits(model):
    # The API's published limits are 24 optional and 16 union fields, and it can refuse below both.
    # TaggingResult failed at 19 and 15, so keep the rest far from there.
    optional, unions = schema_cost(model)
    assert optional <= 8 and unions <= 8
