from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .models import LiveNewsItem
from .services import BBCFeedError, import_latest


def _serialize(item: LiveNewsItem) -> dict[str, object]:
    return {
        "id": item.pk,
        "title": item.title,
        "summary": item.summary,
        "url": item.article_url,
        "image_url": item.image_url or None,
        "sections": item.sections,
        "language": item.language,
        "snapshot_at": item.snapshot_at.isoformat(),
        "last_seen_at": item.last_seen_at.isoformat(),
    }


@ensure_csrf_cookie
@require_GET
def live_items(request):
    language = request.GET.get("lang", "english").strip().lower()
    try:
        limit = min(max(int(request.GET.get("limit", "50")), 1), 100)
    except ValueError:
        return JsonResponse({"error": "limit must be an integer between 1 and 100."}, status=400)
    items = LiveNewsItem.objects.filter(language=language).order_by("-last_seen_at", "title")[:limit]
    return JsonResponse({"language": language, "count": len(items), "items": [_serialize(item) for item in items]})


@require_POST
def import_live(request):
    language = request.GET.get("lang", "english").strip().lower()
    try:
        result = import_latest(language)
    except BBCFeedError as exc:
        return JsonResponse({"error": str(exc), "provider": "BBC News API"}, status=502)
    result["snapshot_at"] = result["snapshot_at"].isoformat()
    return JsonResponse(result)
