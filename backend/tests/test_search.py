from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import Article, Feed, SummaryStatus
from app.search import search_fold


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("İnsan", "insan"),
        ("ISIK", "isik"),
        ("ışık", "isik"),
        ("AI chips", "ai chips"),  # English capital I is not turned into Turkish ı
        ("Özet, şirket, güçlü, çağ", "ozet, sirket, guclu, cag"),
        ("Gemini 4 Carbon", "gemini 4 carbon"),
        (None, None),
    ],
)
def test_search_fold(text: str | None, expected: str | None) -> None:
    assert search_fold(text) == expected


@pytest.fixture
def articles(session: Session) -> None:
    feed = Feed(name="Example", url="https://example.com/rss")
    session.add(feed)
    session.commit()
    rows = [
        ("İnsan gibi düşünen yapay zekâ", "Şirket yeni modelini tanıttı."),
        ("AI chips are getting cheaper", None),
        ("Intel unveils a new processor", None),
    ]
    session.add_all(
        Article(
            feed_id=feed.id,
            guid=str(i),
            url=f"https://example.com/{i}",
            title=f"Original {i}",
            title_tr=title_tr,
            summary_tr=summary_tr,
            summary_status=SummaryStatus.DONE,
            published_at=datetime(2026, 10, 29, 10 + i, tzinfo=UTC),
        )
        for i, (title_tr, summary_tr) in enumerate(rows)
    )
    session.commit()


@pytest.mark.parametrize(
    ("query", "expected_titles"),
    [
        ("insan", ["İnsan gibi düşünen yapay zekâ"]),  # lowercase finds Turkish capital İ
        ("İNSAN", ["İnsan gibi düşünen yapay zekâ"]),
        ("dusunen", ["İnsan gibi düşünen yapay zekâ"]),  # no Turkish keyboard needed
        ("şirket", ["İnsan gibi düşünen yapay zekâ"]),  # searches the summary too
        ("ai", ["AI chips are getting cheaper"]),  # English "AI" still matches "ai"
        ("intel", ["Intel unveils a new processor"]),
    ],
)
def test_search_is_turkish_and_english_friendly(
    client: TestClient, articles, query: str, expected_titles: list[str]
) -> None:
    response = client.get("/api/articles", params={"q": query})

    titles = sorted(item["title_tr"] for item in response.json()["items"])
    assert titles == sorted(expected_titles)
