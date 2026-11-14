"""Persist idempotently fetched headlines in the local database."""
from django.db import transaction
from django.utils import timezone

from .api_client import BBCFeedError, FeedSnapshot, fetch_latest
from .models import LiveNewsItem


def persist_snapshot(snapshot: FeedSnapshot) -> dict[str, object]:
    created = 0
    updated = 0
    seen_at = timezone.now()
    with transaction.atomic():
        for item in snapshot.items:
            _, was_created = LiveNewsItem.objects.update_or_create(
                article_url=item.article_url,
                defaults={
                    "title": item.title,
                    "summary": item.summary,
                    "image_url": item.image_url,
                    "sections": list(item.sections),
                    "language": snapshot.language,
                    "snapshot_at": snapshot.snapshot_at,
                    "last_seen_at": seen_at,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1
    return {
        "language": snapshot.language,
        "snapshot_at": snapshot.snapshot_at,
        "fetched": len(snapshot.items),
        "created": created,
        "updated": updated,
    }


def import_latest(language: str = "english") -> dict[str, object]:
    return persist_snapshot(fetch_latest(language))
