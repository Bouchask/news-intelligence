from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from django.utils.timezone import now

from apps.newsfeed.models import LiveNewsItem

from .kafka_client import create_producer, send_json


def publish_saved_live_items(limit: int = 100) -> dict[str, int]:
    producer = create_producer()
    sent = 0
    try:
        items = LiveNewsItem.objects.filter(summary__gt="").order_by("-last_seen_at")[:limit]
        for item in items:
            document_id = hashlib.sha256(item.article_url.encode("utf-8")).hexdigest()
            event_id = hashlib.sha256(f"{document_id}:{item.snapshot_at.isoformat()}".encode("utf-8")).hexdigest()
            event = {
                "event_id": event_id,
                "document_id": document_id,
                "title": item.title,
                "content": item.summary,
                "source_url": item.article_url,
                "source": "bbc-live-api",
                "timestamp": now().astimezone(UTC).isoformat(),
                "snapshot_at": item.snapshot_at.isoformat(),
                "sections": item.sections,
                "event_type": "news.created",
            }
            send_json(producer, "news.raw", event, item.article_url)
            sent += 1
        producer.flush(timeout=20)
    finally:
        producer.close(timeout=5)
    return {"published": sent, "topic_count": 1}
