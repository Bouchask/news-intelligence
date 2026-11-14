from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from uuid import UUID

from django.conf import settings
from django.db.models import Avg, Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from bigdata.classification.train import ALGORITHMS, SELECTORS, predict_with_artifact
from bigdata.eda.report import summarize
from bigdata.ingestion.bbc import DatasetError, inspect_dataset
from bigdata.preprocessing.english import preprocess_english

from .models import Experiment, Prediction, RegisteredModel, TopicRun
from .services import activate_model, register_experiment
from .tasks import train_experiment_task, train_topics_task

logger = logging.getLogger(__name__)


def _body(request) -> dict:
    try:
        value = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("Request body must contain valid JSON.")
    if not isinstance(value, dict):
        raise ValueError("Request body must be a JSON object.")
    return value


def _experiment_data(item: Experiment) -> dict:
    return {
        "id": str(item.pk), "name": item.name, "algorithm": item.algorithm, "status": item.status,
        "configuration": item.configuration, "metrics": item.metrics,
        "confusion_matrix": item.confusion_matrix, "artifact_available": bool(item.artifact_path),
        "error": item.error_message, "created_at": item.created_at.isoformat(),
        "started_at": item.started_at.isoformat() if item.started_at else None,
        "finished_at": item.finished_at.isoformat() if item.finished_at else None,
    }


def _model_data(item: RegisteredModel) -> dict:
    return {
        "id": str(item.pk), "name": item.name, "version": item.version,
        "algorithm": item.algorithm, "is_active": item.is_active,
        "metrics": item.metrics, "created_at": item.created_at.isoformat(),
        "experiment_id": str(item.experiment_id),
    }


@ensure_csrf_cookie
@require_GET
def experiment_list(request):
    items = Experiment.objects.all()[:100]
    return JsonResponse({"items": [_experiment_data(item) for item in items]})


@require_POST
def train(request):
    try:
        data = _body(request)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    algorithm = str(data.get("algorithm", "naive_bayes"))
    selector = str(data.get("selector", "none"))
    if algorithm not in ALGORITHMS or selector not in SELECTORS:
        return JsonResponse({"error": "algorithm must be baseline, naive_bayes, or knn; selector must be none, variance, or chi2."}, status=400)
    try:
        configuration = {
            "selector": selector,
            "random_state": int(data.get("random_state", 42)),
            "test_size": float(data.get("test_size", 0.2)),
            "folds": int(data.get("folds", 5)),
            "max_features": int(data.get("max_features", 5000)),
            "k_features": int(data.get("k_features", 500)),
        }
    except (TypeError, ValueError):
        return JsonResponse({"error": "Training configuration values must be numeric."}, status=400)
    if not settings.BBC_DATASET_PATH.exists():
        return JsonResponse({"error": f"BBC dataset path not found: {settings.BBC_DATASET_PATH}"}, status=422)
    experiment = Experiment.objects.create(
        name=str(data.get("name") or f"{algorithm.replace('_', ' ').title()} · {selector}")[:180],
        algorithm=algorithm,
        dataset_path=str(settings.BBC_DATASET_PATH),
        configuration=configuration,
    )
    try:
        train_experiment_task.delay(str(experiment.pk))
    except Exception as exc:
        logger.exception("Could not queue experiment %s", experiment.pk)
        experiment.status = Experiment.Status.FAILED
        experiment.error_message = "Training queue unavailable. Start Redis and a Celery worker, then retry."
        experiment.save(update_fields=("status", "error_message"))
        return JsonResponse({"experiment": _experiment_data(experiment), "error": "Training queue unavailable."}, status=503)
    return JsonResponse({"experiment": _experiment_data(experiment)}, status=202)


@require_GET
def experiment_detail(request, experiment_id: UUID):
    item = get_object_or_404(Experiment, pk=experiment_id)
    return JsonResponse({"experiment": _experiment_data(item)})


@require_POST
def experiment_register(request, experiment_id: UUID):
    try:
        data = _body(request)
        name = data.get("name")
        if name is not None and not isinstance(name, str):
            raise ValueError("Model name must be a string.")
        item = register_experiment(str(experiment_id), name)
    except (ValueError, Experiment.DoesNotExist) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({"model": _model_data(item)}, status=201)


@ensure_csrf_cookie
@require_GET
def model_list(request):
    items = RegisteredModel.objects.select_related("experiment")[:100]
    return JsonResponse({"items": [_model_data(item) for item in items]})


@require_GET
def active_model(request):
    item = RegisteredModel.objects.filter(is_active=True).first()
    if not item:
        return JsonResponse({"model": None, "status": "no_active_model"})
    return JsonResponse({"model": _model_data(item)})


@require_POST
def model_activate(request, model_id: UUID):
    try:
        item = activate_model(str(model_id))
    except RegisteredModel.DoesNotExist:
        return JsonResponse({"error": "Model version not found."}, status=404)
    return JsonResponse({"model": _model_data(item)})


@require_POST
def classify(request):
    try:
        data = _body(request)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    title = data.get("title", "")
    content = data.get("content", "")
    if not isinstance(title, str) or not isinstance(content, str):
        return JsonResponse({"error": "title and content must be strings."}, status=400)
    if len(title) > 500 or len(content) > 50000:
        return JsonResponse({"error": "title is limited to 500 characters and content to 50,000."}, status=413)
    if not content.strip():
        return JsonResponse({"error": "Article content cannot be empty."}, status=400)
    model = RegisteredModel.objects.filter(is_active=True).first()
    if not model:
        return JsonResponse({"error": "No active model is registered."}, status=409)
    artifact_path = Path(model.artifact_path).resolve()
    try:
        artifact_path.relative_to(settings.MODEL_ARTIFACT_DIR.resolve())
    except ValueError:
        return JsonResponse({"error": "Model artifact path is outside the configured artifact directory."}, status=500)
    if not artifact_path.is_file():
        return JsonResponse({"error": "Registered model artifact is missing."}, status=503)
    input_text = f"{title.strip()}\n{content.strip()}"
    started = time.perf_counter()
    try:
        result = predict_with_artifact(artifact_path, input_text)
    except Exception:
        logger.exception("Prediction failed for model %s", model.pk)
        return JsonResponse({"error": "Prediction failed while loading or applying the model."}, status=500)
    latency_ms = (time.perf_counter() - started) * 1000
    digest = hashlib.sha256(input_text.encode("utf-8")).hexdigest()
    prediction = Prediction.objects.create(
        model_version=model,
        content_sha256=digest,
        predicted_category=result["category"],
        probabilities=result["probabilities"],
        confidence=result["confidence"],
        latency_ms=latency_ms,
    )
    return JsonResponse({
        "prediction_id": str(prediction.pk), "predicted_category": result["category"],
        "confidence": result["confidence"], "probabilities": result["probabilities"],
        "model": _model_data(model), "latency_ms": round(latency_ms, 3),
    })


@ensure_csrf_cookie
@require_GET
def prediction_history(request):
    rows = Prediction.objects.select_related("model_version")[:100]
    return JsonResponse({"items": [{
        "id": str(item.pk), "predicted_category": item.predicted_category,
        "confidence": item.confidence, "probabilities": item.probabilities,
        "latency_ms": item.latency_ms, "model": f"{item.model_version.name} v{item.model_version.version}",
        "created_at": item.created_at.isoformat(),
    } for item in rows]})


@require_GET
def dashboard_overview(request):
    try:
        dataset = summarize(inspect_dataset(settings.BBC_DATASET_PATH))
    except DatasetError:
        dataset = None
    experiments = list(Experiment.objects.all()[:100])
    best = max(
        (item for item in experiments if item.status == Experiment.Status.SUCCEEDED),
        key=lambda item: item.metrics.get("f1_macro", 0), default=None,
    )
    active = RegisteredModel.objects.filter(is_active=True).first()
    latest = experiments[0] if experiments else None
    prediction_stats = Prediction.objects.aggregate(count=Count("id"), mean_latency=Avg("latency_ms"))
    from apps.newsfeed.models import LiveNewsItem

    return JsonResponse({
        "dataset": {key: dataset[key] for key in ("article_count", "category_count", "categories", "vocabulary_size", "word_count")} if dataset else None,
        "processed_articles": 0,
        "pending_jobs": Experiment.objects.filter(status__in=(Experiment.Status.QUEUED, Experiment.Status.RUNNING)).count(),
        "active_model": _model_data(active) if active else None,
        "best_model_f1_macro": best.metrics.get("f1_macro") if best else None,
        "latest_experiment": _experiment_data(latest) if latest else None,
        "prediction_count": prediction_stats["count"],
        "average_prediction_latency_ms": round(prediction_stats["mean_latency"], 3) if prediction_stats["mean_latency"] is not None else None,
        "live_news_items": LiveNewsItem.objects.count(),
    })


@require_GET
def experiment_compare(request):
    items = Experiment.objects.filter(status=Experiment.Status.SUCCEEDED).order_by("algorithm", "-created_at")[:100]
    return JsonResponse({"items": [_experiment_data(item) for item in items]})


def _topic_run_data(item: TopicRun) -> dict:
    return {
        "id": str(item.pk), "status": item.status, "num_topics": item.num_topics,
        "max_iter": item.max_iter, "results": item.results, "error": item.error_message,
        "created_at": item.created_at.isoformat(),
        "started_at": item.started_at.isoformat() if item.started_at else None,
        "finished_at": item.finished_at.isoformat() if item.finished_at else None,
    }


@ensure_csrf_cookie
@require_GET
def topic_list(request):
    items = TopicRun.objects.all()[:20]
    return JsonResponse({"items": [_topic_run_data(item) for item in items]})


@require_POST
def topic_train(request):
    try:
        data = _body(request)
        num_topics = int(data.get("num_topics", 8))
        max_iter = int(data.get("max_iter", 30))
    except (ValueError, TypeError) as exc:
        return JsonResponse({"error": "num_topics and max_iter must be integers."}, status=400)
    if not 2 <= num_topics <= 30 or not 5 <= max_iter <= 200:
        return JsonResponse({"error": "num_topics must be 2–30 and max_iter must be 5–200."}, status=400)
    if not settings.BBC_DATASET_PATH.exists():
        return JsonResponse({"error": f"BBC dataset path not found: {settings.BBC_DATASET_PATH}"}, status=422)
    run = TopicRun.objects.create(num_topics=num_topics, max_iter=max_iter, dataset_path=str(settings.BBC_DATASET_PATH))
    try:
        train_topics_task.delay(str(run.pk))
    except Exception:
        logger.exception("Could not queue LDA topic run %s", run.pk)
        run.status = TopicRun.Status.FAILED
        run.error_message = "Training queue unavailable. Start Redis and a Celery worker, then retry."
        run.save(update_fields=("status", "error_message"))
        return JsonResponse({"topic_run": _topic_run_data(run), "error": "Training queue unavailable."}, status=503)
    return JsonResponse({"topic_run": _topic_run_data(run)}, status=202)


@require_GET
def topic_detail(request, topic_run_id: UUID):
    run = get_object_or_404(TopicRun, pk=topic_run_id)
    return JsonResponse({"topic_run": _topic_run_data(run)})


@require_POST
def preprocess_article(request):
    try:
        data = _body(request)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    text = data.get("text", "")
    if not isinstance(text, str) or not text.strip():
        return JsonResponse({"error": "text must be a non-empty string."}, status=400)
    if len(text) > 50000:
        return JsonResponse({"error": "text is limited to 50,000 characters."}, status=413)
    return JsonResponse(preprocess_english(text))
