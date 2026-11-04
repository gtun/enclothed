import time
from contextlib import closing
import sqlite3
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from enclothed import api, auth, config
from enclothed.auth import TOKEN_HEADER
from enclothed.db import init_db

CLOUDFLARE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
FORGED_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
TEAM = "testteam"
AUD = "test-aud-tag"
ISSUER = f"https://{TEAM}.cloudflareaccess.com"
OWNER_EMAIL = "owner@example.com"


def make_token(key=CLOUDFLARE_KEY, algorithm="RS256", **changes) -> str:
    claims = {"email": OWNER_EMAIL, "aud": [AUD], "iss": ISSUER, "exp": int(time.time()) + 60}
    claims.update(changes)
    claims = {name: value for name, value in claims.items() if value is not None}
    return jwt.encode(claims, key, algorithm=algorithm, headers={"kid": "test-key"})


@pytest.fixture
def client(tmp_path, monkeypatch):
    """The real auth path. Only the fetch of Cloudflare's public keys is replaced."""
    path = tmp_path / "test.db"
    init_db(path, config.SCHEMA_PATH, config.MIGRATIONS_DIR)
    with closing(sqlite3.connect(path)) as conn:
        with conn:
            conn.execute("UPDATE users SET email = ? WHERE id = 1", (OWNER_EMAIL,))
    monkeypatch.setattr(config, "DB_PATH", path)
    monkeypatch.setattr(api, "DB_PATH", path)
    monkeypatch.delenv("ENCLOTHED_DEV_USER", raising=False)
    monkeypatch.setenv("ACCESS_TEAM_NAME", TEAM)
    monkeypatch.setenv("AUD_TAG", AUD)
    signing_key = SimpleNamespace(key=CLOUDFLARE_KEY.public_key())
    fetcher = SimpleNamespace(get_signing_key_from_jwt=lambda token: signing_key)
    monkeypatch.setattr(auth, "_jwks_client", lambda team: fetcher)
    return TestClient(api.app)


def profile(client, token=None):
    headers = {TOKEN_HEADER: token} if token else {}
    return client.get("/api/profile", headers=headers)


def test_valid_token_signs_in(client):
    response = profile(client, make_token())
    assert response.status_code == 200
    assert response.json() == {"name": "owner"}


@pytest.mark.parametrize("email", ["OWNER@Example.com", "owner@example.com"])
def test_email_case_doesnt_matter(client, email):
    assert profile(client, make_token(email=email)).status_code == 200


def test_stored_email_case_doesnt_matter(client):
    with closing(sqlite3.connect(config.DB_PATH)) as conn:
        with conn:
            conn.execute("UPDATE users SET email = 'Owner@Example.COM' WHERE id = 1")
    assert profile(client, make_token()).status_code == 200


def test_no_token_is_401(client):
    assert profile(client).status_code == 401


def test_garbage_token_is_401(client):
    assert profile(client, "not-a-token").status_code == 401


@pytest.mark.parametrize("token", [
    pytest.param(lambda: make_token(key=FORGED_KEY), id="forged signature"),
    pytest.param(lambda: make_token(aud=["another-app"]), id="wrong audience"),
    pytest.param(lambda: make_token(aud=None), id="no audience"),
    pytest.param(lambda: make_token(iss="https://evil.example.com"), id="wrong issuer"),
    pytest.param(lambda: make_token(iss=None), id="no issuer"),
    pytest.param(lambda: make_token(exp=int(time.time()) - 60), id="expired"),
    pytest.param(lambda: make_token(email=None), id="no email"),
    pytest.param(lambda: make_token(key="a-shared-secret-long-enough-for-hs256", algorithm="HS256"), id="wrong algorithm"),
])
def test_untrusted_token_is_401(client, token):
    assert profile(client, token()).status_code == 401


def test_key_fetch_failure_is_401_not_500(client, monkeypatch):
    def unreachable(token):
        raise jwt.PyJWKClientConnectionError("no network")
    monkeypatch.setattr(auth, "_jwks_client", lambda team: SimpleNamespace(get_signing_key_from_jwt=unreachable))
    assert profile(client, make_token()).status_code == 401


def test_valid_token_without_an_account_is_403(client):
    assert profile(client, make_token(email="stranger@example.com")).status_code == 403


@pytest.mark.parametrize("name", ["ACCESS_TEAM_NAME", "AUD_TAG"])
def test_missing_config_is_503_even_with_a_good_token(client, monkeypatch, name):
    monkeypatch.delenv(name)
    assert profile(client, make_token()).status_code == 503


def test_dev_user_needs_no_token(client, monkeypatch):
    monkeypatch.setenv("ENCLOTHED_DEV_USER", "owner")
    assert profile(client).json() == {"name": "owner"}


def test_unknown_dev_user_is_503_not_a_default(client, monkeypatch):
    monkeypatch.setenv("ENCLOTHED_DEV_USER", "nobody")
    assert profile(client).status_code == 503


def api_routes():
    for route in api.app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api"):
            for method in route.methods:
                yield method, route.path


def test_there_are_api_routes_to_check():
    assert len(list(api_routes())) >= 15


@pytest.mark.parametrize("method, path", list(api_routes()))
def test_every_api_route_needs_sign_in(client, method, path):
    url = path.replace("{garment_id}", "1").replace("{outfit_id}", "1")
    assert client.request(method, url).status_code == 401
