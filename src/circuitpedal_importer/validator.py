from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .crawler import DEFAULT_BLOG_URL, FeedPost, discover_posts
from .fetcher import Fetcher
from .models import PostRecord
from .parser import parse_post


@dataclass(slots=True)
class ValidationCase:
    reason: str
    record: PostRecord


def _candidate_indexes(total: int, pool_size: int) -> list[int]:
    if total <= 0:
        return []
    if pool_size >= total:
        return list(range(total))

    wanted: list[int] = []
    edge = min(4, total)
    wanted.extend(range(edge))
    wanted.extend(range(max(0, total - edge), total))

    remaining = max(0, pool_size - len(set(wanted)))
    if remaining:
        for step in range(1, remaining + 1):
            index = round((total - 1) * step / (remaining + 1))
            wanted.append(index)

    result: list[int] = []
    seen: set[int] = set()
    for index in wanted:
        if 0 <= index < total and index not in seen:
            seen.add(index)
            result.append(index)

    if len(result) < pool_size:
        for index in range(total):
            if index not in seen:
                result.append(index)
                seen.add(index)
                if len(result) >= pool_size:
                    break
    return result[:pool_size]


def _add_label_candidates(posts: list[FeedPost], indexes: list[int]) -> list[int]:
    wanted = list(indexes)
    seen = set(indexes)
    for target in ("verified", "unverified"):
        for index, post in enumerate(posts):
            labels = {label.casefold() for label in post.labels}
            if target in labels and index not in seen:
                wanted.append(index)
                seen.add(index)
                break
    return wanted


def _author_reply_count(record: PostRecord) -> int:
    return sum(1 for comment in record.comments if comment.is_blog_author)


def _record_score(record: PostRecord) -> int:
    return (
        bool(record.body_text)
        + bool(record.labels)
        + bool(record.image_urls)
        + bool(record.schematic_links)
        + bool(record.embedded_urls)
        + bool(record.comments)
        + bool(_author_reply_count(record))
        + (len(record.links) >= 3)
    )


def select_validation_cases(
    records: list[PostRecord],
    *,
    sample_size: int = 8,
) -> list[ValidationCase]:
    if sample_size < 1 or not records:
        return []

    selected: list[ValidationCase] = []
    used: set[str] = set()

    def take(
        reason: str,
        predicate: Callable[[PostRecord], bool],
        *,
        prefer_high_score: bool = True,
    ) -> None:
        if len(selected) >= sample_size:
            return
        matches = [
            record
            for record in records
            if record.source_url not in used and predicate(record)
        ]
        if not matches:
            return
        chooser = max if prefer_high_score else min
        record = chooser(matches, key=_record_score)
        selected.append(ValidationCase(reason=reason, record=record))
        used.add(record.source_url)

    # Select specialist evidence first so a generic category cannot consume the
    # only useful example of a schematic, embed, or author correction.
    take("Unverified post", lambda record: record.verification_status == "unverified")
    take("Schematic link", lambda record: bool(record.schematic_links))
    take("Embedded reference", lambda record: bool(record.embedded_urls))
    take("Author reply", lambda record: _author_reply_count(record) > 0)

    # Preserve the actual temporal edges of the inspected catalogue sample.
    remaining = [record for record in records if record.source_url not in used]
    dated = [record for record in remaining if record.published_at]
    if dated and len(selected) < sample_size:
        oldest = min(dated, key=lambda record: record.published_at or "")
        selected.append(ValidationCase(reason="Older catalogue post", record=oldest))
        used.add(oldest.source_url)

    remaining = [record for record in records if record.source_url not in used]
    dated = [record for record in remaining if record.published_at]
    if dated and len(selected) < sample_size:
        newest = max(dated, key=lambda record: record.published_at or "")
        selected.append(ValidationCase(reason="Recent catalogue post", record=newest))
        used.add(newest.source_url)

    # Generic coverage comes later and deliberately prefers a less feature-rich
    # record, leaving unusual pages available for their specialist categories.
    take(
        "Verified post",
        lambda record: record.verification_status == "verified",
        prefer_high_score=False,
    )
    take(
        "Community comments",
        lambda record: bool(record.comments) and _author_reply_count(record) == 0,
    )
    take("Rich reference set", lambda record: len(record.links) >= 3)

    for record in sorted(
        (record for record in records if record.source_url not in used),
        key=_record_score,
        reverse=True,
    ):
        if len(selected) >= sample_size:
            break
        selected.append(ValidationCase(reason="Additional coverage", record=record))
        used.add(record.source_url)

    return selected[:sample_size]


def _case_dict(case: ValidationCase) -> dict[str, object]:
    record = case.record
    return {
        "reason": case.reason,
        "title": record.title,
        "source_url": record.source_url,
        "published_at": record.published_at,
        "verification_status": record.verification_status,
        "labels": record.labels,
        "body_text_present": bool(record.body_text),
        "body_text_characters": len(record.body_text),
        "image_count": len(record.image_urls),
        "link_count": len(record.links),
        "schematic_link_count": len(record.schematic_links),
        "embedded_reference_count": len(record.embedded_urls),
        "comment_count": len(record.comments),
        "author_reply_count": _author_reply_count(record),
    }


def render_validation_report(
    *,
    total_posts: int,
    candidate_records: list[PostRecord],
    cases: list[ValidationCase],
    errors: list[dict[str, str]],
) -> str:
    lines = [
        "CIRCUITPEDAL REFERENCE IMPORTER - VALIDATION REPORT",
        "=" * 54,
        f"Catalogue posts discovered: {total_posts}",
        f"Candidate pages inspected: {len(candidate_records)}",
        f"Validation cases selected: {len(cases)}",
        f"Fetch/parse errors: {len(errors)}",
        "",
    ]

    for number, case in enumerate(cases, start=1):
        record = case.record
        lines.extend(
            [
                f"[{number}] {record.title}",
                f"Reason:              {case.reason}",
                f"Verification:        {record.verification_status.upper()}",
                f"Published:           {record.published_at or 'unknown'}",
                f"Body text:           {'YES' if record.body_text else 'NO'} ({len(record.body_text)} chars)",
                f"Images:              {len(record.image_urls)}",
                f"Links:               {len(record.links)}",
                f"Schematic links:     {len(record.schematic_links)}",
                f"Embedded references: {len(record.embedded_urls)}",
                f"Comments:            {len(record.comments)}",
                f"Author replies:      {_author_reply_count(record)}",
                f"Source:              {record.source_url}",
                "",
            ]
        )

    if errors:
        lines.append("ERRORS")
        lines.append("-" * 54)
        for error in errors:
            lines.append(f"{error.get('title', '')}: {error.get('error', '')}")
        lines.append("")

    lines.extend(
        [
            "MANUAL CHECK",
            "-" * 54,
            "Open each Source URL above and compare the report with the original post.",
            "Check title/status, technical notes, schematic links, images, embeds,",
            "comments, and whether Effects Layouts author replies were identified.",
        ]
    )
    return "\n".join(lines) + "\n"


def validate_catalogue(
    *,
    cache_dir: Path,
    report_path: Path,
    base_url: str = DEFAULT_BLOG_URL,
    delay_seconds: float = 1.5,
    refresh: bool = False,
    sample_size: int = 8,
    candidate_pool: int = 24,
) -> str:
    fetcher = Fetcher(
        cache_dir,
        delay_seconds=delay_seconds,
        refresh=refresh,
    )

    feed_posts = list(discover_posts(fetcher, base_url=base_url))
    indexes = _candidate_indexes(len(feed_posts), candidate_pool)
    indexes = _add_label_candidates(feed_posts, indexes)

    records: list[PostRecord] = []
    errors: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for index in indexes:
        feed_post = feed_posts[index]
        if feed_post.url in seen_urls:
            continue
        seen_urls.add(feed_post.url)
        try:
            html = fetcher.get_text(feed_post.url)
            records.append(
                parse_post(
                    html,
                    source_url=feed_post.url,
                    feed_title=feed_post.title,
                    feed_published_at=feed_post.published_at,
                    feed_labels=feed_post.labels,
                    include_comments=True,
                )
            )
        except Exception as exc:
            errors.append(
                {
                    "title": feed_post.title,
                    "source_url": feed_post.url,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    cases = select_validation_cases(records, sample_size=sample_size)
    report = render_validation_report(
        total_posts=len(feed_posts),
        candidate_records=records,
        cases=cases,
        errors=errors,
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_path = report_path.with_suffix(".json")
    payload = {
        "total_posts": len(feed_posts),
        "candidate_pages_inspected": len(records),
        "errors": errors,
        "cases": [_case_dict(case) for case in cases],
    }
    report_path.write_text(report, encoding="utf-8")
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report
