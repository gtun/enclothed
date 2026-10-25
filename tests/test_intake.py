# tests/test_intake.py
from pathlib import Path

import pytest

from enclothed.intake import photo_filenames, add_garment
from enclothed.models import PhotoTag

# Paths don't need to exist: photo_filenames only reads .name and .suffix.
RUN = Path("data/intake/20261018-062504")


def staged(*names: str) -> list[Path]:
    return [RUN / n for n in names]


def tags(*roles: str) -> list[PhotoTag]:
    """Tags in index order: tags("front", "label") -> index 0 front, index 1 label."""
    return [PhotoTag(index=i, role=r) for i, r in enumerate(roles)]


def test_roles_numbered_per_role_in_photo_order():
    # The real run from 2026-10-18: six URL photos
    paths = staged(*(f"url_{i}.jpg" for i in range(6)))
    tagged = tags("front", "back", "label", "detail", "label", "label")

    assert photo_filenames(paths, tagged) == [
        "front_00.jpg", "back_00.jpg", "label_00.jpg",
        "detail_00.jpg", "label_01.jpg", "label_02.jpg",
    ]


def test_shuffled_tags_still_match_the_right_photo():
    # Claude may list tags in any order; each name must follow its tag's index.
    paths = staged("a.jpg", "b.jpg", "c.jpg")
    tagged = [
        PhotoTag(index=2, role="label"),
        PhotoTag(index=0, role="front"),
        PhotoTag(index=1, role="back"),
    ]

    assert photo_filenames(paths, tagged) == ["front_00.jpg", "back_00.jpg", "label_00.jpg"]


def test_multiple_fronts_are_numbered():
    paths = staged("a.jpg", "b.jpg", "c.jpg")
    tagged = tags("front", "front", "back")

    assert photo_filenames(paths, tagged) == ["front_00.jpg", "front_01.jpg", "back_00.jpg"]


def test_each_photo_keeps_its_own_extension():
    paths = staged("a.jpg", "b.png", "c.webp")
    tagged = tags("front", "label", "label")

    assert photo_filenames(paths, tagged) == ["front_00.jpg", "label_00.png", "label_01.webp"]


@pytest.mark.parametrize(
    "indexes",
    [
        [0, 1, 1],  # duplicate (and 2 missing)
        [0, 2],     # missing 1
        [0, 1, 5],  # out of range
        [],         # no tags at all (test mode with photos)
    ],
    ids=["duplicate", "missing", "out_of_range", "no_tags"],
)
def test_invalid_tags_fall_back_to_original_names(indexes):
    paths = staged("a.jpg", "b.jpg", "c.jpg")
    tagged = [PhotoTag(index=i, role="other") for i in indexes]

    assert photo_filenames(paths, tagged) == ["a.jpg", "b.jpg", "c.jpg"]


def test_no_photos_and_no_tags():
    # `add -t` with no photos
    assert photo_filenames([], []) == []

def test_invalid_photo_filepath(tmp_path):
    intake = tmp_path / "intake"
    intake.mkdir()

    photos = ["tests/fixtures/20261017_120645.jpg","test/fixtures/nonexistent.jpg"]

    with pytest.raises(FileNotFoundError):
        add_garment(
            photos,
            tmp_path / "wardrobe.db",
            tmp_path / "garments",
            intake,
            tmp_path / "tagging_log.jsonl",
            None,
            True,
        )

    assert list(intake.iterdir()) == []
