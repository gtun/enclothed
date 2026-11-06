"""Drafts wait for review, and old ones get cleaned up."""
import os
import time

from enclothed import config, drafts, intake
from enclothed.intake import TEST_GARMENT
from enclothed.models import PhotoTag, TaggingResult


def make_old(folder):
    old = time.time() - config.DRAFT_MAX_AGE_SECONDS - 60
    os.utime(folder, (old, old))


def test_old_drafts_are_removed_and_recent_ones_kept(tmp_path):
    old = tmp_path / "1" / ("a" * 32)
    recent = tmp_path / "1" / ("b" * 32)
    old.mkdir(parents=True)
    recent.mkdir()
    make_old(old)

    drafts.remove_old_drafts(tmp_path)

    assert not old.exists()
    assert recent.exists()


def test_starting_a_draft_clears_old_ones(tmp_path, monkeypatch):
    def fake_tag(client, paths, prompt, language, preferences):
        return TaggingResult(garment=TEST_GARMENT, photos=[PhotoTag(index=0, role="front")]), None
    monkeypatch.setattr(intake, "tag_garment", fake_tag)
    old = tmp_path / "drafts" / "1" / ("a" * 32)
    old.mkdir(parents=True)
    make_old(old)
    photo = tmp_path / "00.jpg"
    photo.write_bytes(b"x")

    draft = drafts.create_draft(tmp_path / "drafts", 1, [photo], tmp_path / "log.jsonl", None, None, None, "en-US", None)

    assert not old.exists()
    assert (tmp_path / "drafts" / "1" / draft.id / "00.jpg").exists()


def test_a_draft_belongs_to_one_user(tmp_path):
    folder = tmp_path / "1" / ("a" * 32)
    folder.mkdir(parents=True)
    (folder / drafts.DRAFT_FILE).write_text("{}")
    assert drafts.discard_draft(tmp_path, 2, "a" * 32) is False
    assert folder.exists()


def test_a_path_is_never_a_draft_id(tmp_path):
    assert drafts.discard_draft(tmp_path, 1, "../..") is False
