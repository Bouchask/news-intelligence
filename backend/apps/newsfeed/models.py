from django.db import models


class LiveNewsItem(models.Model):
    """BBC feed metadata and summaries; full article text is not fetched or stored."""

    article_url = models.URLField(max_length=600, unique=True)
    title = models.CharField(max_length=500)
    summary = models.TextField(blank=True)
    image_url = models.URLField(max_length=1000, blank=True)
    sections = models.JSONField(default=list)
    language = models.CharField(max_length=30, default="english", db_index=True)
    snapshot_at = models.DateTimeField(db_index=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ("-last_seen_at", "title")
        indexes = [models.Index(fields=("language", "-last_seen_at"))]

    def __str__(self) -> str:
        return self.title
