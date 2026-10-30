from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import Article, Feed, SummaryStatus


@pytest.fixture
def data(session: Session) -> dict[str, int]:
    """Two feeds with articles, plus one feed without any. Returns ids by name."""
    now = datetime.now(UTC)
    openai = Feed(name="OpenAI", url="https://openai.example.com/rss")
    verge = Feed(name="The Verge", url="https://verge.example.com/rss")
    empty = Feed(name="Empty", url="https://empty.example.com/rss")
    session.add_all([openai, verge, empty])
    session.commit()

    summarized = Article(
        feed_id=openai.id,
        guid="1",
        url="https://openai.example.com/model",
        title="A new model",
        title_tr="Yeni bir yapay zeka modeli",
        summary_tr="Model daha hızlı ve daha ucuz.",
        key_points=["Daha hızlı", "Daha ucuz"],
        content="Full extracted text that must never be returned.",
        summary_status=SummaryStatus.DONE,
        published_at=now - timedelta(hours=1),
    )
    pending = Article(
        feed_id=verge.id,
        guid="2",
        url="https://verge.example.com/chips",
        title="Chip makers race ahead",
        rss_summary="Demand for 100% AI chips keeps growing.",
        summary_status=SummaryStatus.PENDING,
        published_at=now - timedelta(hours=5),
    )
    old = Article(
        feed_id=verge.id,
        guid="3",
        url="https://verge.example.com/old",
        title="An older story",
        summary_status=SummaryStatus.SKIPPED,
        published_at=now - timedelta(hours=40),
    )
    session.add_all([summarized, pending, old])
    session.commit()

    return {
        "openai": openai.id,
        "verge": verge.id,
        "summarized": summarized.id,
        "pending": pending.id,
        "old": old.id,
    }


def titles(response) -> list[str]:
    return [item["title"] for item in response.json()["items"]]


def test_list_returns_newest_first_with_feed_names(client: TestClient, data) -> None:
    response = client.get("/api/articles")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert titles(response) == ["A new model", "Chip makers race ahead", "An older story"]
    assert body["items"][0]["feed_name"] == "OpenAI"
    assert body["items"][0]["published_at"].endswith("Z")  # UTC timestamps


def test_full_text_is_never_returned(client: TestClient, data) -> None:
    listed = client.get("/api/articles").json()["items"][0]
    detail = client.get(f"/api/articles/{data['summarized']}").json()

    assert "content" not in listed
    assert "content" not in detail


def test_filter_by_ids(client: TestClient, data) -> None:
    ids = f"{data['summarized']},{data['old']},999"

    response = client.get("/api/articles", params={"ids": ids})

    assert titles(response) == ["A new model", "An older story"]


def test_ids_filter_rejects_anything_but_numbers(client: TestClient, data) -> None:
    assert client.get("/api/articles", params={"ids": "1,x"}).status_code == 422


def test_pagination(client: TestClient, data) -> None:
    response = client.get("/api/articles", params={"page": 2, "size": 2})

    body = response.json()
    assert body["total"] == 3
    assert (body["page"], body["size"]) == (2, 2)
    assert titles(response) == ["An older story"]


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"status": "pending"}, ["Chip makers race ahead"]),
        ({"since_hours": 24}, ["A new model", "Chip makers race ahead"]),
        ({"q": "YAPAY"}, ["A new model"]),  # searches the Turkish title, case-insensitive
        ({"q": "ai chips"}, ["Chip makers race ahead"]),  # searches the RSS description
        ({"q": "100%"}, ["Chip makers race ahead"]),  # "%" is literal, not a wildcard
        ({"q": "nothing matches"}, []),
    ],
)
def test_filters(client: TestClient, data, params: dict, expected: list[str]) -> None:
    response = client.get("/api/articles", params=params)

    assert titles(response) == expected
    assert response.json()["total"] == len(expected)


def test_filter_by_feed(client: TestClient, data) -> None:
    response = client.get("/api/articles", params={"feed_id": data["verge"]})

    assert titles(response) == ["Chip makers race ahead", "An older story"]


@pytest.mark.parametrize(
    "params",
    [{"size": 101}, {"page": 0}, {"q": "a"}, {"status": "unknown"}, {"since_hours": 0}],
)
def test_invalid_params_are_rejected(client: TestClient, data, params: dict) -> None:
    assert client.get("/api/articles", params=params).status_code == 422


def test_article_detail(client: TestClient, data) -> None:
    response = client.get(f"/api/articles/{data['summarized']}")

    assert response.status_code == 200
    body = response.json()
    assert body["title_tr"] == "Yeni bir yapay zeka modeli"
    assert body["key_points"] == ["Daha hızlı", "Daha ucuz"]
    assert body["feed_name"] == "OpenAI"


def test_missing_article_returns_404(client: TestClient, data) -> None:
    response = client.get("/api/articles/9999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Article not found"}


def test_feeds_include_article_counts(client: TestClient, data) -> None:
    response = client.get("/api/feeds")

    assert response.status_code == 200
    counts = {feed["name"]: feed["article_count"] for feed in response.json()}
    assert counts == {"Empty": 0, "OpenAI": 1, "The Verge": 2}
    assert [feed["name"] for feed in response.json()] == ["Empty", "OpenAI", "The Verge"]
