from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class LinkRecord:
    url: str
    text: str = ""
    kind: str = "reference"


@dataclass(slots=True)
class CommentRecord:
    author: str
    text: str
    published_at: str | None = None
    is_blog_author: bool = False
    depth: int = 0


@dataclass(slots=True)
class PostRecord:
    source_url: str
    title: str
    published_at: str | None
    labels: list[str] = field(default_factory=list)
    verification_status: str = "unknown"
    body_text: str = ""
    links: list[LinkRecord] = field(default_factory=list)
    schematic_links: list[str] = field(default_factory=list)
    image_urls: list[str] = field(default_factory=list)
    comments: list[CommentRecord] = field(default_factory=list)
    scraped_at: str = ""
    content_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
