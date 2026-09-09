from __future__ import annotations

import argparse
import json
from pathlib import Path

from .crawler import DEFAULT_BLOG_URL, crawl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="circuitpedal-importer",
        description="Build a local evidence index of guitar-effects reference sources.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    crawl_parser = subparsers.add_parser(
        "crawl",
        help="Discover and index Effects Layouts posts.",
    )
    crawl_parser.add_argument("--base-url", default=DEFAULT_BLOG_URL)
    crawl_parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/effects-layouts.jsonl"),
    )
    crawl_parser.add_argument(
        "--summary",
        type=Path,
        default=Path("data/crawl-summary.json"),
    )
    crawl_parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("cache"),
    )
    crawl_parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Minimum seconds between live HTTP requests (default: 1.5).",
    )
    crawl_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Stop after writing this many posts.",
    )
    crawl_parser.add_argument(
        "--refresh",
        action="store_true",
        help="Ignore existing cache entries and refetch.",
    )
    crawl_parser.add_argument(
        "--no-comments",
        action="store_true",
        help="Do not parse post comments.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "crawl":
        if args.limit is not None and args.limit < 1:
            parser.error("--limit must be at least 1")
        if args.delay < 0:
            parser.error("--delay cannot be negative")

        counts = crawl(
            output_path=args.output,
            summary_path=args.summary,
            cache_dir=args.cache_dir,
            base_url=args.base_url,
            delay_seconds=args.delay,
            refresh=args.refresh,
            include_comments=not args.no_comments,
            limit=args.limit,
        )
        print(json.dumps(counts, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
