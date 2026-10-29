"""Check that every RSS source in sources.yaml is reachable and parseable.

Usage (from backend/):
    uv run python -m scripts.check_sources
"""

import sys
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from app.seed import load_sources
from app.services.fetcher import create_http_client, download_feed, entry_date, parse_feed

TITLE_WIDTH = 60


@dataclass
class CheckResult:
    name: str
    ok: bool
    item_count: int | None = None
    latest_date: datetime | None = None
    latest_title: str | None = None
    error: str | None = None


def check_source(client: httpx.Client, name: str, url: str) -> CheckResult:
    try:
        response = download_feed(client, url)
    except httpx.HTTPStatusError as exc:
        return CheckResult(name, ok=False, error=f"HTTP {exc.response.status_code}")
    except httpx.HTTPError as exc:
        return CheckResult(name, ok=False, error=f"{type(exc).__name__}: {exc}")

    feed = parse_feed(response)
    if not feed.entries:
        # "bozo" is set when the XML is malformed; only fatal if nothing could be parsed.
        reason = f"Invalid feed: {feed.bozo_exception}" if feed.bozo else "Feed has no items"
        return CheckResult(name, ok=False, item_count=0, error=reason)

    # Feeds are not guaranteed to be sorted, so pick the newest entry explicitly.
    oldest = datetime.min.replace(tzinfo=UTC)
    latest = max(feed.entries, key=lambda entry: entry_date(entry) or oldest)
    return CheckResult(
        name,
        ok=True,
        item_count=len(feed.entries),
        latest_date=entry_date(latest),
        latest_title=latest.get("title", "(untitled)"),
    )


def truncate(text: str, width: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1] + "…"


def print_table(results: list[CheckResult]) -> None:
    headers = ("Source", "OK", "Items", "Latest (UTC)", "Latest title / error")
    rows = [
        (
            result.name,
            "✓" if result.ok else "✗",
            str(result.item_count) if result.item_count is not None else "-",
            result.latest_date.strftime("%Y-%m-%d %H:%M") if result.latest_date else "-",
            truncate(result.latest_title if result.ok else result.error or "", TITLE_WIDTH),
        )
        for result in results
    ]
    widths = [max(len(row[i]) for row in (headers, *rows)) for i in range(len(headers))]

    def format_row(row: tuple[str, ...]) -> str:
        return "  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True))

    print(format_row(headers))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print(format_row(row))


def main() -> int:
    results: list[CheckResult] = []

    with create_http_client() as client:
        for source in load_sources():
            print(f"Checking {source['name']}...", file=sys.stderr)
            try:
                results.append(check_source(client, source["name"], source["url"]))
            except Exception as exc:  # keep going no matter what a single source does
                results.append(
                    CheckResult(source["name"], ok=False, error=f"{type(exc).__name__}: {exc}")
                )

    print()
    print_table(results)
    ok_count = sum(result.ok for result in results)
    print(f"\n{ok_count}/{len(results)} sources OK")
    return 0 if ok_count == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
