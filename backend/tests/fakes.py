"""Test doubles shared by several test modules."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from app.services.summarizer import ArticleInput, ArticleSummary


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


@dataclass
class Slow:
    """A scripted result that takes `seconds` of (fake) time, like a request timing out."""

    seconds: float
    result: Any


class FakeSummarizer:
    """Plays back scripted results: "all" (summarize every article), a list of ids
    to summarize, an exception to raise, or any of these wrapped in Slow."""

    def __init__(self, model: str, clock: FakeClock, results: Sequence[Any] = ()) -> None:
        self.model = model
        self.clock = clock
        self.results = list(results)
        self.batches: list[list[int]] = []

    def summarize(self, articles: Sequence[ArticleInput]) -> dict[int, ArticleSummary]:
        ids = [article.id for article in articles]
        self.batches.append(ids)
        result = self.results.pop(0) if self.results else "all"
        if isinstance(result, Slow):
            self.clock.now += timedelta(seconds=result.seconds)
            result = result.result
        if isinstance(result, Exception):
            raise result
        chosen = ids if result == "all" else result
        return {
            i: ArticleSummary(
                article_id=i, title_tr=f"Başlık {i}", summary_tr="Özet.", key_points=["Nokta"]
            )
            for i in chosen
        }
