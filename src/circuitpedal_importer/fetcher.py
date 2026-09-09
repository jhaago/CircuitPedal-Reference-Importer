from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import requests


DEFAULT_USER_AGENT = (
    "CircuitPedal-Reference-Importer/0.1 "
    "(research indexer; https://github.com/jhaago/CircuitPedal-Reference-Importer)"
)


class Fetcher:
    """HTTP client with local caching and a minimum delay between live requests."""

    def __init__(
        self,
        cache_dir: Path,
        *,
        delay_seconds: float = 1.5,
        refresh: bool = False,
        timeout_seconds: float = 30.0,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.delay_seconds = max(0.0, delay_seconds)
        self.refresh = refresh
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self._last_request_at = 0.0

    @staticmethod
    def _cache_key(url: str) -> str:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    def _cache_path(self, url: str, suffix: str) -> Path:
        return self.cache_dir / f"{self._cache_key(url)}{suffix}"

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        wait = self.delay_seconds - elapsed
        if wait > 0:
            time.sleep(wait)

    def get_text(self, url: str) -> str:
        cache_path = self._cache_path(url, ".html")
        if cache_path.exists() and not self.refresh:
            return cache_path.read_text(encoding="utf-8")

        self._throttle()
        response = self.session.get(url, timeout=self.timeout_seconds)
        self._last_request_at = time.monotonic()
        response.raise_for_status()
        text = response.text
        cache_path.write_text(text, encoding="utf-8")
        return text

    def get_json(self, url: str) -> dict[str, Any]:
        cache_path = self._cache_path(url, ".json")
        if cache_path.exists() and not self.refresh:
            return json.loads(cache_path.read_text(encoding="utf-8"))

        self._throttle()
        response = self.session.get(url, timeout=self.timeout_seconds)
        self._last_request_at = time.monotonic()
        response.raise_for_status()
        payload = response.json()
        cache_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return payload
