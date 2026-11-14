from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


class EventValidationError(ValueError):
    pass


def validate_news_event(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EventValidationError("Event payload must be a JSON object.")
    required = ("event_id", "document_id", "title", "content", "source_url", "timestamp")
    missing = [key for key in required if not isinstance(value.get(key), str) or not value[key].strip()]
    if missing:
        raise EventValidationError(f"Missing or empty string fields: {', '.join(missing)}")
    if len(value["title"]) > 500 or len(value["content"]) > 50000:
        raise EventValidationError("Event title/content exceeds size limits.")
    source_url = urlparse(value["source_url"])
    host = (source_url.hostname or "").lower()
    if source_url.scheme != "https" or not any(host == domain or host.endswith("." + domain) for domain in ("bbc.com", "bbc.co.uk", "bbci.co.uk")):
        raise EventValidationError("source_url must point to an HTTPS BBC page.")
    value["sections"] = [str(section)[:100] for section in value.get("sections", []) if isinstance(section, str)][:20]
    return value
