from __future__ import annotations

import argparse
import json
from pathlib import Path

from .crawler import DEFAULT_BLOG_URL, crawl
from .validator import validate_catalogue


def _add_common_network_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-url", default=DEFAULT_BLOG_URL)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("cache"),
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Minimum seconds between live HTTP requests (default: 1.5).",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Ignore existing cache entries and refetch.",
    )


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
    _add_common_network_args(crawl_parser)
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
        "--limit",
        type=int,
        default=None,
        help="Stop after writing this many posts.",
    )
    crawl_parser.add_argument(
        "--no-comments",
        action="store_true",
        help="Do not parse post comments.",
    )

    validate_parser = subparsers.add_parser(
        "validate",
        help="Inspect a varied sample and print a human-readable validation report.",
    )
    _add_common_network_args(validate_parser)
    validate_parser.add_argument(
        "--sample-size",
        type=int,
        default=8,
        help="Number of representative posts in the final report (default: 8).",
    )
    validate_parser.add_argument(
        "--candidate-pool",
        type=int,
        default=24,
        help="Number of distributed catalogue pages to inspect before selecting cases (default: 24).",
    )
    validate_parser.add_argument(
        "--report",
        type=Path,
        default=Path("data/validation-report.txt"),
        help="Text report path; a JSON report is written beside it.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.delay < 0:
        parser.error("--delay cannot be negative")

    if args.command == "crawl":
        if args.limit is not None and args.limit < 1:
            parser.error("--limit must be at least 1")

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
        return

    if args.command == "validate":
        if args.sample_size < 1:
            parser.error("--sample-size must be at least 1")
        if args.candidate_pool < args.sample_size:
            parser.error("--candidate-pool must be at least --sample-size")

        report = validate_catalogue(
            cache_dir=args.cache_dir,
            report_path=args.report,
            base_url=args.base_url,
            delay_seconds=args.delay,
            refresh=args.refresh,
            sample_size=args.sample_size,
            candidate_pool=args.candidate_pool,
        )
        print(report)
        return


if __name__ == "__main__":
    main()
