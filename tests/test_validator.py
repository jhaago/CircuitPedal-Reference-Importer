from circuitpedal_importer.models import CommentRecord, LinkRecord, PostRecord
from circuitpedal_importer.validator import (
    _candidate_indexes,
    render_validation_report,
    select_validation_cases,
)


def make_record(
    title: str,
    *,
    status: str = "verified",
    published: str = "2026-01-01T00:00:00Z",
    schematics: int = 0,
    embeds: int = 0,
    comments: int = 0,
    author_replies: int = 0,
    links: int = 0,
) -> PostRecord:
    comment_records = [
        CommentRecord(author="Builder", text="Works") for _ in range(comments)
    ]
    comment_records.extend(
        CommentRecord(
            author="Effects Layouts",
            text="Correction",
            is_blog_author=True,
        )
        for _ in range(author_replies)
    )
    return PostRecord(
        source_url=f"https://example.com/{title}",
        title=title,
        published_at=published,
        labels=["Verified"] if status == "verified" else ["Unverified"],
        verification_status=status,
        body_text="Useful technical notes",
        links=[
            LinkRecord(url=f"https://example.com/ref-{index}", text="ref")
            for index in range(links)
        ],
        schematic_links=[
            f"https://example.com/schematic-{index}.pdf"
            for index in range(schematics)
        ],
        image_urls=["https://example.com/layout.png"],
        embedded_urls=[
            f"https://example.com/embed-{index}" for index in range(embeds)
        ],
        comments=comment_records,
    )


def test_candidate_indexes_cover_edges():
    indexes = _candidate_indexes(100, 12)
    assert 0 in indexes
    assert 99 in indexes
    assert len(indexes) == 12
    assert len(set(indexes)) == 12


def test_select_validation_cases_prefers_varied_evidence():
    records = [
        make_record("unverified", status="unverified"),
        make_record("schematic", schematics=1),
        make_record("embed", embeds=1),
        make_record("reply", comments=2, author_replies=1),
        make_record("rich", links=5),
        make_record("old", published="2012-01-01T00:00:00Z"),
        make_record("new", published="2026-09-01T00:00:00Z"),
    ]

    cases = select_validation_cases(records, sample_size=7)
    reasons = {case.reason for case in cases}
    urls = [case.record.source_url for case in cases]

    assert "Unverified post" in reasons
    assert "Schematic link" in reasons
    assert "Embedded reference" in reasons
    assert "Author reply" in reasons
    assert len(urls) == len(set(urls))


def test_render_validation_report_is_human_readable():
    record = make_record(
        "Example Fuzz",
        schematics=1,
        comments=2,
        author_replies=1,
    )
    report = render_validation_report(
        total_posts=800,
        candidate_records=[record],
        cases=select_validation_cases([record], sample_size=1),
        errors=[],
    )

    assert "Example Fuzz" in report
    assert "Schematic links:" in report
    assert "Author replies:" in report
    assert "MANUAL CHECK" in report
