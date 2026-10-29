"""Extract the full text of new articles and decide which ones need a summary."""

import logging
import time
from collections import Counter

import httpx
import trafilatura
from sqlmodel import Session, col, select

from app.config import settings
from app.models import Article, SummaryStatus

logger = logging.getLogger(__name__)

# Pause between page downloads so we do not hammer a site with many articles in one feed.
REQUEST_DELAY_SECONDS = 1.0


def extract_text(client: httpx.Client, url: str) -> str | None:
    """Download a page and return its main text, or None if nothing usable was found."""
    response = client.get(url)
    response.raise_for_status()
    return trafilatura.extract(
        response.text,
        url=url,
        include_comments=False,
        include_tables=False,
        favor_precision=True,  # prefer missing a paragraph over including menus or ads
    )


def process_article(
    client: httpx.Client, session: Session, article: Article, min_chars: int
) -> None:
    text = None
    try:
        text = extract_text(client, article.url)
    except httpx.HTTPStatusError as exc:  # 404, 405 (bot protection), paywall...
        logger.info("Extraction failed for %s: HTTP %s", article.url, exc.response.status_code)
    except Exception as exc:  # timeout, parse error...: fall back to the RSS summary
        logger.info("Extraction failed for %s: %s: %s", article.url, type(exc).__name__, exc)

    # Keep the longest text we have: the extracted page, the full text embedded in the
    # feed (stored in `content` at fetch time) or the short RSS description.
    candidates = [t for t in (text, article.content, article.rss_summary) if t]
    article.content = max(candidates, key=len, default=None)
    article.content_length = len(article.content or "")
    article.summary_status = (
        SummaryStatus.PENDING if article.content_length >= min_chars else SummaryStatus.SKIPPED
    )
    session.add(article)
    session.commit()  # per article, so an interruption does not lose finished work


def process_new_articles(
    client: httpx.Client,
    session: Session,
    limit: int = 50,
    delay: float = REQUEST_DELAY_SECONDS,
    min_chars: int | None = None,
) -> Counter[SummaryStatus]:
    """Extract text for up to `limit` new articles, oldest first. Returns counts per new status."""
    min_chars = min_chars if min_chars is not None else settings.summary_min_chars
    articles = session.exec(
        select(Article)
        .where(Article.summary_status == SummaryStatus.NEW)
        .order_by(col(Article.published_at))
        .limit(limit)
    ).all()

    counts: Counter[SummaryStatus] = Counter()
    for index, article in enumerate(articles):
        if index and delay:
            time.sleep(delay)
        process_article(client, session, article, min_chars)
        counts[article.summary_status] += 1
    return counts
