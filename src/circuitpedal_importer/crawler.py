from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from urllib.parse import urlencode

from .fetcher import Fetcher
from .models import PostRecord
from .parser import parse_post


DEFAULT_BLOG_URL = "https://effectslayouts.blogspot.com"


@dataclass(slots=True)
class FeedPost:
    title: str
    url: str
    published_at: str | None
    labels: list[str]


def _feed_url(base_url: str, start_index: int, max_results: int) -> str:
    query = urlencode(
        {
            "alt": "json",
            "start-index": start_index,
            "max-results": max_results,
        }
    )
    return f"{base_url.rstrip('/')}/feeds/posts/default?{query}"


def discover_posts(
    fetcher: Fetcher,
    *,
    base_url: str = DEFAULT_BLOG_URL,
    page_size: int = 150,
) -> Iterator[FeedPost]:
    start_index = 1

    while True:
        payload = fetcher.get_json(_feed_url(base_url, start_index, page_size))
        feed = payload.get("feed", {})
        entries = feed.get("entry", []) or []
        if not entries:
            return

        for entry in entries:
            alternate_url = None
            for link in entry.get("link", []):
                if link.get("rel") == "alternate":
                    alternate_url = link.get("href")
                    break
            if not alternate_url:
                continue

            labels = [
                category.get("term", "")
                for category in entry.get("category", [])
                if category.get("term")
            ]
            yield FeedPost(
                title=entry.get("title", {}).get("$t", ""),
                url=alternate_url,
                published_at=entry.get("published", {}).get("$t"),
                labels=labels,
            )

        if len(entries) < page_size:
            return
        start_index += len(entries)


def crawl(
    *,
    output_path: Path,
    summary_path: Path,
    cache_dir: Path,
    base_url: str = DEFAULT_BLOG_URL,
    delay_seconds: float = 1.5,
    refresh: bool = False,
    include_comments: bool = True,
    limit: int | None = None,
) -> dict[str, int]:
    fetcher = Fetcher(
        cache_dir,
        delay_seconds=delay_seconds,
        refresh=refresh,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    counts = {
        "discovered": 0,
        "written": 0,
        "verified": 0,
        "unverified": 0,
        "unknown_verification": 0,
        "with_schematic_links": 0,
        "with_comments": 0,
        "errors": 0,
    }

    seen_urls: set[str] = set()

    with output_path.open("w", encoding="utf-8") as output:
        for feed_post in discover_posts(fetcher, base_url=base_url):
            if feed_post.url in seen_urls:
                continue
            seen_urls.add(feed_post.url)
            counts["discovered"] += 1

            if limit is not None and counts["written"] >= limit:
                break

            try:
                html = fetcher.get_text(feed_post.url)
                record: PostRecord = parse_post(
                    html,
                    source_url=feed_post.url,
                    feed_title=feed_post.title,
                    feed_published_at=feed_post.published_at,
                    feed_labels=feed_post.labels,
                    include_comments=include_comments,
                )
                output.write(
                    json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True) + "\n"
                )
                output.flush()

                counts["written"] += 1
                if record.verification_status == "verified":
                    counts["verified"] += 1
                elif record.verification_status == "unverified":
                    counts["unverified"] += 1
                else:
                    counts["unknown_verification"] += 1
                if record.schematic_links:
                    counts["with_schematic_links"] += 1
                if record.comments:
                    counts["with_comments"] += 1
            except Exception as exc:  # Continue the research crawl and report failures.
                counts["errors"] += 1
                error_record = {
                    "source_url": feed_post.url,
                    "title": feed_post.title,
                    "error": f"{type(exc).__name__}: {exc}",
                }
                output.write(
                    json.dumps({"_crawl_error": error_record}, ensure_ascii=False) + "\n"
                )
                output.flush()

    summary_path.write_text(
        json.dumps(counts, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return counts
