# backend/app/auth.py

import hmac

from fastapi import Header, HTTPException, status

from .config import get_settings

# A short token is treated as not configured at all, so a weak value can't
# accidentally open the write endpoints.
MIN_ADMIN_TOKEN_LENGTH = 32


def require_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    """Gate for every endpoint that writes to the database (ingest, prune).
    Fails closed: if ADMIN_TOKEN isn't configured on the server, the write
    endpoints are disabled outright rather than left open."""
    expected = get_settings().admin_token
    if not expected or len(expected) < MIN_ADMIN_TOKEN_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Write endpoints are disabled: ADMIN_TOKEN is not configured on the server",
        )
    if not x_admin_token or not hmac.compare_digest(x_admin_token.encode(), expected.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-Admin-Token header",
        )
