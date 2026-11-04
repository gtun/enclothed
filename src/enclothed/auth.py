import logging
import os
from functools import lru_cache

import jwt
from fastapi import HTTPException, Request

from enclothed import config, db
from enclothed.models import User

logger = logging.getLogger(__name__)

TOKEN_HEADER = "Cf-Access-Jwt-Assertion"


@lru_cache
def _jwks_client(team: str) -> jwt.PyJWKClient:
    """The client that fetches Cloudflare's public keys. Built once, because it caches them."""
    return jwt.PyJWKClient(f"https://{team}.cloudflareaccess.com/cdn-cgi/access/certs")


def verify_token(token: str, team: str, aud: str) -> str | None:
    """The email in a valid Access token, or None if the token can't be trusted."""
    try:
        signing_key = _jwks_client(team).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=aud,
            issuer=f"https://{team}.cloudflareaccess.com",
        )
    except jwt.PyJWTError as error:
        logger.warning("Rejected Access token: %s", error)
        return None
    return claims.get("email")


def current_user(request: Request) -> User:
    """Who is calling. Every failure is an error, never a default user."""
    dev_username = os.getenv("ENCLOTHED_DEV_USER")
    if dev_username:
        user = db.select_user_by_username(config.DB_PATH, dev_username)
        if user is None:
            raise HTTPException(status_code=503, detail=f"ENCLOTHED_DEV_USER {dev_username!r} doesn't exist")
        return user

    team = os.getenv("ACCESS_TEAM_NAME")
    aud = os.getenv("AUD_TAG")
    if not team or not aud:
        raise HTTPException(status_code=503, detail="Sign-in isn't configured")

    token = request.headers.get(TOKEN_HEADER)
    email = verify_token(token, team, aud) if token else None
    if not email:
        raise HTTPException(status_code=401, detail="Not signed in")

    user = db.select_user_by_email(config.DB_PATH, email)
    if user is None:
        raise HTTPException(status_code=403, detail="This email doesn't have an account")
    return user
