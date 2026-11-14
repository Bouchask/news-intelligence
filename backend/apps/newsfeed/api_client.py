"""Standard-library client/parser for the third-party BBC News API."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

_LANGUAGE = re.compile(r"^[a-z]{2,20}$")
_BBC_HOSTS = ("bbc.com", "bbc.co.uk", "bbci.co.uk")
_METADATA_KEYS = {"status", "elapsed time", "timestamp", "languages"}


class BBCFeedError(RuntimeError):
    """Raised for upstream timeouts, malformed payloads, and API failures."""


@dataclass(frozen=True)
class FeedItem:
    article_url: str
    title: str
    summary: str
    image_url: str
    sections: tuple[str, ...]


@dataclass(frozen=True)
class FeedSnapshot:
    language: str
    snapshot_at: datetime
    items: tuple[FeedItem, ...]


def parse_latest_payload(payload: object, language: str = "english") -> FeedSnapshot:
    language = language.strip().lower()
    if not _LANGUAGE.fullmatch(language):
        raise BBCFeedError("Language must be a lowercase language code such as 'english'.")
    try:
        api_status = int(payload.get("status", 0)) if isinstance(payload, dict) else 0
    except (TypeError, ValueError):
        api_status = 0
    if not isinstance(payload, dict) or api_status != 200:
        raise BBCFeedError("BBC News API response did not indicate success.")

    try:
        snapshot_at = datetime.fromtimestamp(int(payload["timestamp"]), tz=UTC)
    except (KeyError, TypeError, ValueError, OSError):
        snapshot_at = datetime.now(UTC)

    deduplicated: dict[str, dict[str, object]] = {}
    for section, records in payload.items():
        if section.lower() in _METADATA_KEYS or not isinstance(records, list):
            continue
        for record in records:
            if not isinstance(record, dict):
                continue
            title = str(record.get("title") or "").strip()
            article_url = str(record.get("news_link") or record.get("link") or "").strip()
            if not title or not article_url:
                continue
            parsed = urlparse(article_url)
            hostname = (parsed.hostname or "").lower()
            if parsed.scheme != "https" or not any(hostname == host or hostname.endswith("." + host) for host in _BBC_HOSTS):
                continue
            article_url = parsed._replace(fragment="").geturl()
            image_url = str(record.get("image_link") or record.get("thumbnail") or "").strip()
            image = urlparse(image_url)
            image_host = (image.hostname or "").lower()
            if image.scheme != "https" or not any(image_host == host or image_host.endswith("." + host) for host in _BBC_HOSTS):
                image_url = ""
            item = deduplicated.setdefault(article_url, {
                "title": title,
                "summary": str(record.get("summary") or record.get("description") or "").strip(),
                "image_url": image_url,
                "sections": set(),
            })
            item["sections"].add(section)

    if not deduplicated:
        raise BBCFeedError("BBC News API returned no usable article headlines.")
    items = tuple(
        FeedItem(
            article_url=url,
            title=str(value["title"]),
            summary=str(value["summary"]),
            image_url=str(value["image_url"]),
            sections=tuple(sorted(value["sections"])),
        )
        for url, value in deduplicated.items()
    )
    return FeedSnapshot(language=language, snapshot_at=snapshot_at, items=items)


def fetch_latest(language: str = "english") -> FeedSnapshot:
    language = language.strip().lower()
    if not _LANGUAGE.fullmatch(language):
        raise BBCFeedError("Language must be a lowercase language code such as 'english'.")
    base_url = os.getenv("BBC_NEWS_API_URL", "https://bbc-news-api.vercel.app").rstrip("/")
    url = f"{base_url}/latest?{urlencode({'lang': language})}"
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "NewsIntelligence/0.1 (academic project)"})
    try:
        with urlopen(request, timeout=15) as response:
            if response.status != 200:
                raise BBCFeedError(f"BBC News API returned HTTP {response.status}.")
            raw = response.read(8 * 1024 * 1024 + 1)
    except HTTPError as exc:
        raise BBCFeedError(f"BBC News API returned HTTP {exc.code}.") from exc
    except URLError as exc:
        raise BBCFeedError(f"Could not reach BBC News API: {exc.reason}") from exc
    except TimeoutError as exc:
        raise BBCFeedError("BBC News API request timed out after 15 seconds.") from exc
    if len(raw) > 8 * 1024 * 1024:
        raise BBCFeedError("BBC News API response exceeded the 8 MiB limit.")
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BBCFeedError("BBC News API returned invalid JSON.") from exc
    return parse_latest_payload(payload, language)
