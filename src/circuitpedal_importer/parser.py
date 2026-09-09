from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from .models import CommentRecord, LinkRecord, PostRecord


SCHEMATIC_TERMS = (
    "schematic",
    "circuit diagram",
    "circuit",
    "trace",
)
DOCUMENT_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif")


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _absolute_url(base_url: str, value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if not value or value.startswith(("javascript:", "mailto:")):
        return None
    return urljoin(base_url, value)


def _classify_link(text: str, url: str) -> str:
    lowered_text = text.lower()
    lowered_url = url.lower()
    path = urlparse(lowered_url).path

    if any(term in lowered_text for term in SCHEMATIC_TERMS):
        return "schematic"
    if "datasheet" in lowered_text or "datasheet" in lowered_url:
        return "datasheet"
    if "youtube.com" in lowered_url or "youtu.be" in lowered_url:
        return "demo"
    if path.endswith(".pdf"):
        return "document"
    if path.endswith(DOCUMENT_EXTENSIONS):
        return "image"
    return "reference"


def _verification_status(labels: list[str]) -> str:
    lowered = {label.casefold() for label in labels}
    if "verified" in lowered:
        return "verified"
    if "unverified" in lowered:
        return "unverified"
    return "unknown"


def _extract_post_body(soup: BeautifulSoup) -> Tag | None:
    selectors = (
        ".post-body.entry-content",
        ".post-body",
        "article .entry-content",
        "article",
    )
    for selector in selectors:
        node = soup.select_one(selector)
        if isinstance(node, Tag):
            return node
    return None


def _extract_title(soup: BeautifulSoup) -> str:
    for selector in (
        "h3.post-title.entry-title",
        "h1.post-title",
        "h2.post-title",
        "article h1",
        "article h2",
    ):
        node = soup.select_one(selector)
        if node:
            value = _clean_text(node.get_text(" ", strip=True))
            if value:
                return value
    if soup.title:
        return _clean_text(soup.title.get_text(" ", strip=True))
    return ""


def _extract_labels(soup: BeautifulSoup) -> list[str]:
    labels: list[str] = []
    for node in soup.select('a[rel="tag"], .post-labels a'):
        value = _clean_text(node.get_text(" ", strip=True))
        if value and value not in labels:
            labels.append(value)
    return labels


def _extract_published_at(soup: BeautifulSoup) -> str | None:
    for node in soup.select("abbr.published, time[datetime], .published"):
        value = node.get("title") or node.get("datetime")
        if value:
            return str(value).strip()
    return None


def _extract_comments(
    soup: BeautifulSoup,
    *,
    blog_author_names: set[str],
) -> list[CommentRecord]:
    comments: list[CommentRecord] = []

    candidates = soup.select(
        "#comments .comment, #comments li.comment, "
        ".comments .comment, .comment-thread li"
    )
    seen: set[tuple[str, str]] = set()
    normalized_blog_authors = {name.casefold() for name in blog_author_names}

    for node in candidates:
        if not isinstance(node, Tag):
            continue

        content = node.select_one(
            ".comment-content, .comment-body, .comment-text, p.comment-content"
        )
        if content is None:
            continue

        text = _clean_text(content.get_text(" ", strip=True))
        if not text:
            continue

        author_node = node.select_one(
            ".user, .comment-author, cite.user, .comment-header cite"
        )
        author = _clean_text(author_node.get_text(" ", strip=True)) if author_node else ""

        stamp_node = node.select_one(".datetime, .comment-timestamp, time")
        published_at = None
        if stamp_node:
            published_at = (
                stamp_node.get("datetime")
                or stamp_node.get("title")
                or _clean_text(stamp_node.get_text(" ", strip=True))
            )

        key = (author, text)
        if key in seen:
            continue
        seen.add(key)

        depth = len(node.find_parents(["li"], class_=re.compile(r"comment")))
        comments.append(
            CommentRecord(
                author=author,
                text=text,
                published_at=str(published_at) if published_at else None,
                is_blog_author=author.casefold() in normalized_blog_authors,
                depth=max(0, depth - 1),
            )
        )

    return comments


def parse_post(
    html: str,
    *,
    source_url: str,
    feed_title: str | None = None,
    feed_published_at: str | None = None,
    feed_labels: list[str] | None = None,
    include_comments: bool = True,
    blog_author_names: set[str] | None = None,
) -> PostRecord:
    soup = BeautifulSoup(html, "html.parser")
    body = _extract_post_body(soup)

    title = _extract_title(soup) or (feed_title or "")
    labels = _extract_labels(soup) or list(feed_labels or [])
    published_at = _extract_published_at(soup) or feed_published_at

    links: list[LinkRecord] = []
    schematic_links: list[str] = []
    image_urls: list[str] = []
    embedded_urls: list[str] = []

    if body is not None:
        seen_links: set[str] = set()
        for anchor in body.find_all("a", href=True):
            url = _absolute_url(source_url, anchor.get("href"))
            if not url or url in seen_links:
                continue
            seen_links.add(url)
            text = _clean_text(anchor.get_text(" ", strip=True))
            kind = _classify_link(text, url)
            links.append(LinkRecord(url=url, text=text, kind=kind))
            if kind == "schematic":
                schematic_links.append(url)

        seen_images: set[str] = set()
        for image in body.find_all("img"):
            candidate = image.get("data-src") or image.get("src")
            url = _absolute_url(source_url, candidate)
            if url and url not in seen_images:
                seen_images.add(url)
                image_urls.append(url)

        seen_embeds: set[str] = set()
        for embed in body.find_all(["iframe", "embed"]):
            candidate = embed.get("src")
            url = _absolute_url(source_url, candidate)
            if url and url not in seen_embeds:
                seen_embeds.add(url)
                embedded_urls.append(url)

        body_text = _clean_text(body.get_text(" ", strip=True))
    else:
        body_text = ""

    comments = (
        _extract_comments(
            soup,
            blog_author_names=blog_author_names or {"Effects Layouts"},
        )
        if include_comments
        else []
    )

    content_hash = hashlib.sha256(
        (
            title
            + "\n"
            + body_text
            + "\n"
            + "\n".join(link.url for link in links)
            + "\n"
            + "\n".join(embedded_urls)
        ).encode("utf-8")
    ).hexdigest()

    return PostRecord(
        source_url=source_url,
        title=title,
        published_at=published_at,
        labels=labels,
        verification_status=_verification_status(labels),
        body_text=body_text,
        links=links,
        schematic_links=schematic_links,
        image_urls=image_urls,
        embedded_urls=embedded_urls,
        comments=comments,
        scraped_at=datetime.now(UTC).isoformat(),
        content_hash=content_hash,
    )
