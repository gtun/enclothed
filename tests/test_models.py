# tests/test_models.py
from typing import get_args
from enclothed.models import Category, SUBCATEGORIES

def test_subcategories_cover_every_category():
    assert set(get_args(Category)) == set(SUBCATEGORIES)
