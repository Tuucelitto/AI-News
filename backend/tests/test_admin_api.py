import re
from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.api.deps import get_http_client
from app.config import settings
from app.main import app
from app.models import Article, Feed, SummaryStatus
from tests.fakes import recent_rss

ADMIN = {"X-Admin-Key": "test-admin-key"}  # set in conftest.py
NEW_FEED_URL = "https://news.example.com/rss"


def serve(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/rss":
        return httpx.Response(200, text=recent_rss("Example News", "https://news.example.com/a"))
    if request.url.path == "/page.html":
        return httpx.Response(200, text="<html><body><p>Just a web page</p></body></html>")
    return httpx.Response(404)  # article pages: extraction falls back to the RSS teaser


@pytest.fixture(autouse=True)
def mock_http() -> Iterator[None]:
    # Endpoints that download feeds get a client that never touches the network.
    app.dependency_overrides[get_http_client] = lambda: httpx.Client(
        transport=httpx.MockTransport(serve)
    )
    yield
    app.dependency_overrides.pop(get_http_client, None)


@pytest.fixture
def feed(session: Session) -> Feed:
    feed = Feed(name="Example", url=NEW_FEED_URL)
    session.add(feed)
    session.commit()
    session.add(Article(feed_id=feed.id, guid="1", url="https://news.example.com/old", title="Old"))
    session.commit()
    return feed


# --- Authentication ---------------------------------------------------------------


def test_every_write_endpoint_requires_the_admin_key(client: TestClient) -> None:
    """Guards against adding a write endpoint and forgetting the protection.
    Checks behavior (calls every write endpoint without a key) instead of FastAPI internals."""
    write_methods = {"post", "put", "patch", "delete"}
    endpoints = [
        (method, re.sub(r"\{[^}]+\}", "1", path))  # fill path parameters like {feed_id}
        for path, operations in app.openapi()["paths"].items()
        for method in operations
        if method in write_methods
    ]

    assert len(endpoints) >= 5, endpoints
    for method, path in endpoints:
        response = client.request(method.upper(), path, json={})
        assert response.status_code == 401, f"{method.upper()} {path} is not protected"


@pytest.mark.parametrize("headers", [{}, {"X-Admin-Key": "wrong"}])
def test_missing_or_wrong_key_is_rejected(client: TestClient, feed: Feed, headers) -> None:
    response = client.delete(f"/api/feeds/{feed.id}", headers=headers)

    assert response.status_code == 401
    assert client.get("/api/feeds").json()[0]["name"] == "Example"  # nothing deleted


def test_write_endpoints_are_closed_without_a_configured_key(
    client: TestClient, feed: Feed, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "admin_api_key", "")

    response = client.delete(f"/api/feeds/{feed.id}", headers={"X-Admin-Key": ""})

    assert response.status_code == 403


def test_reading_needs_no_key(client: TestClient, feed: Feed) -> None:
    assert client.get("/api/feeds").status_code == 200


# --- Feeds ------------------------------------------------------------------------


def test_create_feed_uses_feed_title_as_default_name(client: TestClient) -> None:
    response = client.post("/api/feeds", json={"url": NEW_FEED_URL}, headers=ADMIN)

    assert response.status_code == 201
    body = response.json()
    assert (body["name"], body["url"]) == ("Example News", NEW_FEED_URL)
    assert body["site_url"] == "https://news.example.com"
    assert body["article_count"] == 0


def test_create_feed_with_custom_name(client: TestClient) -> None:
    response = client.post(
        "/api/feeds", json={"url": NEW_FEED_URL, "name": "My feed"}, headers=ADMIN
    )

    assert response.json()["name"] == "My feed"


def test_duplicate_feed_is_rejected(client: TestClient, feed: Feed) -> None:
    response = client.post("/api/feeds", json={"url": NEW_FEED_URL}, headers=ADMIN)

    assert response.status_code == 409


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("https://news.example.com/page.html", "not a valid RSS/Atom feed"),
        ("https://news.example.com/missing", "HTTP 404"),
    ],
)
def test_url_that_is_not_a_feed_is_rejected(client: TestClient, url: str, message: str) -> None:
    response = client.post("/api/feeds", json={"url": url}, headers=ADMIN)

    assert response.status_code == 422
    assert message in response.json()["detail"]


def test_invalid_url_is_rejected(client: TestClient) -> None:
    response = client.post("/api/feeds", json={"url": "not a url"}, headers=ADMIN)

    assert response.status_code == 422


def test_update_feed(client: TestClient, feed: Feed) -> None:
    response = client.patch(
        f"/api/feeds/{feed.id}", json={"name": "Renamed", "is_active": False}, headers=ADMIN
    )

    assert response.status_code == 200
    assert (response.json()["name"], response.json()["is_active"]) == ("Renamed", False)


def test_partial_update_keeps_other_fields(client: TestClient, feed: Feed) -> None:
    response = client.patch(f"/api/feeds/{feed.id}", json={"is_active": False}, headers=ADMIN)

    assert response.json()["name"] == "Example"


def test_delete_feed_deletes_its_articles(client: TestClient, session: Session, feed: Feed) -> None:
    response = client.delete(f"/api/feeds/{feed.id}", headers=ADMIN)

    assert response.status_code == 204
    assert session.exec(select(Article)).all() == []


@pytest.mark.parametrize(
    ("method", "path"),
    [("patch", "/api/feeds/999"), ("delete", "/api/feeds/999"), ("post", "/api/feeds/999/refresh")],
)
def test_unknown_feed_returns_404(client: TestClient, method: str, path: str) -> None:
    kwargs = {"json": {"name": "x"}} if method == "patch" else {}

    response = getattr(client, method)(path, headers=ADMIN, **kwargs)

    assert response.status_code == 404


def test_refresh_fetches_and_extracts_only_that_feed(
    client: TestClient, session: Session, feed: Feed
) -> None:
    other = Feed(name="Other", url="https://other.example.com/rss")
    session.add(other)
    session.commit()
    untouched = Article(feed_id=other.id, guid="o", url="https://other.example.com/o", title="O")
    session.add(untouched)
    session.commit()

    response = client.post(f"/api/feeds/{feed.id}/refresh", headers=ADMIN)

    assert response.status_code == 200
    assert response.json() == {
        "new_articles": 1,
        "not_modified": False,
        "error": None,
        "queued_for_summary": 0,
        "skipped": 2,  # the new article and the old one of this feed; both have short text
    }
    session.refresh(untouched)
    assert untouched.summary_status == SummaryStatus.NEW


# --- Articles -----------------------------------------------------------------------


def test_resummarize_puts_article_back_in_queue(
    client: TestClient, session: Session, feed: Feed
) -> None:
    article = session.exec(select(Article)).one()
    article.summary_status = SummaryStatus.FAILED
    article.summary_attempts = 5
    article.summary_error = "Prompt blocked"
    session.commit()

    response = client.post(f"/api/articles/{article.id}/resummarize", headers=ADMIN)

    assert response.status_code == 200
    assert response.json()["summary_status"] == "pending"
    session.refresh(article)
    assert (article.summary_attempts, article.summary_error) == (0, None)


@pytest.mark.parametrize("status", [SummaryStatus.PENDING, SummaryStatus.PROCESSING])
def test_resummarize_rejects_articles_already_in_queue(
    client: TestClient, session: Session, feed: Feed, status: SummaryStatus
) -> None:
    article = session.exec(select(Article)).one()
    article.summary_status = status
    session.commit()

    response = client.post(f"/api/articles/{article.id}/resummarize", headers=ADMIN)

    assert response.status_code == 409


def test_resummarize_unknown_article_returns_404(client: TestClient) -> None:
    assert client.post("/api/articles/999/resummarize", headers=ADMIN).status_code == 404


# --- CORS ---------------------------------------------------------------------------


def test_cors_allows_the_frontend_origin_and_admin_header(client: TestClient) -> None:
    response = client.options(
        "/api/feeds",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-Admin-Key",
        },
    )

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
