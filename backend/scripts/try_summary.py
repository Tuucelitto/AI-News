"""Send one batch of pending articles to Gemini and print the Turkish summaries.

Nothing is saved to the database. Each run uses ONE request of the daily quota.

Usage (from backend/):
    uv run python -m scripts.try_summary            # oldest pending articles
    uv run python -m scripts.try_summary --ids 3 7  # specific articles
    uv run python -m scripts.try_summary --model gemini-3.5-flash-lite
"""

import argparse
import sys
import textwrap
import time

from sqlmodel import Session, col, select

from app.config import settings
from app.db import engine
from app.models import Article, SummaryStatus
from app.services.summarizer import ArticleInput, GeminiSummarizer, SummaryError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ids", type=int, nargs="+", help="article ids to summarize")
    parser.add_argument("--model", help=f"Gemini model (default: {settings.gemini_model})")
    args = parser.parse_args()

    with Session(engine) as session:
        query = select(Article)
        if args.ids:
            query = query.where(col(Article.id).in_(args.ids))
        else:
            query = (
                query.where(Article.summary_status == SummaryStatus.PENDING)
                .order_by(col(Article.published_at))
                .limit(settings.summary_batch_size)
            )
        articles = session.exec(query).all()

    if not articles:
        print("No articles found.")
        return 1

    inputs = [ArticleInput(a.id, a.title, a.content or a.rss_summary or "") for a in articles]
    summarizer = GeminiSummarizer(model=args.model)
    print(f"Sending {len(inputs)} articles to {summarizer.model} in one request...\n")

    started = time.perf_counter()
    try:
        summaries = summarizer.summarize(inputs)
    except SummaryError as exc:
        print(f"{type(exc).__name__}: {exc}")
        return 1
    elapsed = time.perf_counter() - started

    for article in articles:
        print(f"#{article.id}  {article.title}")
        result = summaries.get(article.id)
        if result is None:
            print("  (no summary returned for this article)\n")
            continue
        print(f"  {result.title_tr}")
        print(textwrap.indent(textwrap.fill(result.summary_tr, 96), "  "))
        for point in result.key_points:
            print(f"   • {point}")
        print()

    print(f"{len(summaries)}/{len(inputs)} summarized in {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
