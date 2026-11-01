import pytest
from fastapi.testclient import TestClient

from enclothed import api, photos
from enclothed.db import init_db, insert_garment, insert_outfits
from enclothed.models import Outfit
from enclothed.config import SCHEMA_PATH, MIGRATIONS_DIR
from enclothed.intake import TEST_GARMENT


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """A fresh test DB, and the API pointed at it instead of the real one."""
    path = tmp_path / "test.db"
    init_db(path, SCHEMA_PATH, MIGRATIONS_DIR)
    monkeypatch.setattr(api, "DB_PATH", path)
    monkeypatch.setattr(photos, "GARMENTS_DIR", tmp_path / "garments")
    return path


@pytest.fixture
def client(db_path):
    return TestClient(api.app)


@pytest.fixture
def outfit_id(db_path):
    garment_ids = [insert_garment(db_path, TEST_GARMENT) for _ in range(2)]
    outfit = Outfit(
        aesthetic="test look",
        explanation="why it works",
        garments=[{"garment_id": i} for i in garment_ids],
    )
    [new_id] = insert_outfits(db_path, [outfit], None, "dinner", "2026-11-01T00:00:00+00:00")
    return new_id


# --- PATCH /api/outfits/{id} ---------------------------------------------------------

@pytest.mark.parametrize("liked", [True, False, None])
def test_patch_liked_sets_value_and_returns_outfit(client, outfit_id, liked):
    response = client.patch(f"/api/outfits/{outfit_id}", json={"liked": liked})
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == outfit_id
    assert body["liked"] == liked
    assert len(body["garments"]) == 2


def test_patch_liked_persists(client, outfit_id):
    client.patch(f"/api/outfits/{outfit_id}", json={"liked": True})
    assert client.get(f"/api/outfits/{outfit_id}").json()["liked"] is True


def test_patch_liked_missing_outfit_is_404(client):
    response = client.patch("/api/outfits/999", json={"liked": True})
    assert response.status_code == 404


@pytest.mark.parametrize("body", [{}, {"liked": "maybe"}, {"liked": 5}])
def test_patch_liked_rejects_bad_body(client, outfit_id, body):
    response = client.patch(f"/api/outfits/{outfit_id}", json=body)
    assert response.status_code == 422
    assert client.get(f"/api/outfits/{outfit_id}").json()["liked"] is None
