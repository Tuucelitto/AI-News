import secrets
from collections.abc import Iterator
from typing import Annotated

import httpx
from fastapi import Depends, Header, HTTPException, status
from sqlmodel import Session

from app.config import settings
from app.db import get_session
from app.services.fetcher import create_http_client

# Declaring `session: SessionDep` in an endpoint gives it a DB session for the request.
SessionDep = Annotated[Session, Depends(get_session)]


def get_http_client() -> Iterator[httpx.Client]:
    with create_http_client() as client:
        yield client


# A dependency (instead of creating the client inline) so tests can swap in a mock transport.
HttpClientDep = Annotated[httpx.Client, Depends(get_http_client)]


def require_admin(x_admin_key: Annotated[str | None, Header()] = None) -> None:
    """Protects write endpoints. Reading stays public."""
    if not settings.admin_api_key:
        # Fail closed: a forgotten key must not leave the write endpoints open.
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Write endpoints are disabled: ADMIN_API_KEY is not set"
        )
    # compare_digest takes the same time however many characters match,
    # so the key cannot be guessed by measuring response times.
    if x_admin_key is None or not secrets.compare_digest(
        x_admin_key.encode(), settings.admin_api_key.encode()
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing X-Admin-Key header")


AdminDep = Depends(require_admin)
