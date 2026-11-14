"""Read-only dataset summary endpoint for the local dashboard."""
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from bigdata.eda.report import summarize
from bigdata.ingestion.bbc import DatasetError, inspect_dataset


@require_GET
def summary(request):
    configured = request.GET.get("path")
    if configured:
        return JsonResponse({"error": "Passing a dataset path in a request is disabled; configure BBC_DATASET_PATH in the environment."}, status=400)
    source = settings.BBC_DATASET_PATH
    if not source.exists():
        return JsonResponse({"status": "unavailable", "reason": "dataset_not_found"}, status=404)
    try:
        report = summarize(inspect_dataset(source))
    except DatasetError as exc:
        return JsonResponse({"status": "invalid", "reason": str(exc)}, status=422)
    return JsonResponse({"status": "available", **report})


@require_GET
def articles(request):
    """Search actual archive documents with bounded preview responses."""
    try:
        dataset = inspect_dataset(settings.BBC_DATASET_PATH)
    except DatasetError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    query = request.GET.get("q", "").strip().casefold()
    category = request.GET.get("category", "").strip().casefold()
    try:
        limit = min(max(int(request.GET.get("limit", "25")), 1), 100)
        offset = max(int(request.GET.get("offset", "0")), 0)
    except ValueError:
        return JsonResponse({"error": "limit and offset must be integers."}, status=400)
    selected = []
    for item in dataset["articles"]:
        if category and item["category"].casefold() != category:
            continue
        if query and query not in f"{item['title']} {item['content']}".casefold():
            continue
        selected.append({
            "document_id": item["document_id"], "title": item["title"] or "Untitled article",
            "category": item["category"], "content_preview": item["content"][:900],
            "word_count": len(item["content"].split()),
        })
    return JsonResponse({
        "total": len(selected), "limit": limit, "offset": offset,
        "categories": sorted(dataset["categories"]), "items": selected[offset:offset + limit],
    })
