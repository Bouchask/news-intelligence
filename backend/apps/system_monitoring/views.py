import importlib.metadata
import os
import socket
from urllib.parse import urlparse

from django.db import connection
from django.db.models import Count
from django.http import JsonResponse
from django.utils.timezone import now
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
import json


@ensure_csrf_cookie
@require_GET
def health(request):
    """Return API/database health without masking database failures."""
    database = "ok"
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        database = "unavailable"
    status = 200 if database == "ok" else 503
    return JsonResponse({"status": "ok" if status == 200 else "degraded", "database": database, "timestamp": now().isoformat()}, status=status)


@require_GET
def services(request):
    database = "ok"
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        database = "unavailable"
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis_status = "unavailable"
    try:
        import redis

        client = redis.Redis.from_url(redis_url, socket_connect_timeout=0.5, socket_timeout=0.5)
        redis_status = "ok" if client.ping() else "unavailable"
    except Exception:
        pass
    try:
        spark_version = importlib.metadata.version("pyspark")
        spark = {"status": "installed", "version": spark_version, "detail": "Runtime job is verified only when a Spark job completes."}
    except importlib.metadata.PackageNotFoundError:
        spark = {"status": "unavailable", "version": None, "detail": "PySpark is not installed in this Python environment."}
    redis_parsed = urlparse(redis_url)
    redis_detail = f"{redis_parsed.scheme}://{redis_parsed.hostname or 'localhost'}:{redis_parsed.port or 6379}/{redis_parsed.path.lstrip('/') or '0'}"
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "").strip()
    if bootstrap:
        broker = urlparse("//" + bootstrap.split(",", 1)[0].replace("kafka://", ""))
        broker_detail = f"{broker.hostname or 'unknown'}:{broker.port or 9092}"
        try:
            with socket.create_connection((broker.hostname or "", broker.port or 9092), timeout=0.5):
                kafka = {"status": "reachable", "detail": broker_detail}
        except (OSError, ValueError):
            kafka = {"status": "unavailable", "detail": broker_detail}
    else:
        kafka = {"status": "not_configured", "detail": "Set KAFKA_BOOTSTRAP_SERVERS to enable broker checks."}
    return JsonResponse({
        "timestamp": now().isoformat(),
        "services": [
            {"name": "Django API", "status": "ok", "detail": "This endpoint is responding."},
            {"name": "Database", "status": database, "detail": "SELECT 1 connectivity check."},
            {"name": "Redis / Celery broker", "status": redis_status, "detail": redis_detail},
            {"name": "Spark", **spark},
            {"name": "Kafka", **kafka},
        ],
    })


@require_GET
def jobs(request):
    from apps.experiments.models import Experiment, TopicRun

    experiments = Experiment.objects.filter(status__in=(Experiment.Status.QUEUED, Experiment.Status.RUNNING)).order_by("created_at")[:50]
    topics = TopicRun.objects.filter(status__in=(TopicRun.Status.QUEUED, TopicRun.Status.RUNNING)).order_by("created_at")[:50]
    return JsonResponse({"items": [
        {"id": str(item.pk), "kind": "experiment", "status": item.status, "name": item.name, "created_at": item.created_at.isoformat()}
        for item in experiments
    ] + [
        {"id": str(item.pk), "kind": "topic_model", "status": item.status, "name": f"Spark LDA · {item.num_topics} topics", "created_at": item.created_at.isoformat()}
        for item in topics
    ]})


@require_GET
def streaming_status(request):
    from apps.experiments.models import KafkaEvent, Prediction
    from streaming.kafka_client import TOPICS, bootstrap_servers

    broker = "unavailable"
    topics = []
    detail = ""
    try:
        from kafka.admin import KafkaAdminClient
        admin = KafkaAdminClient(bootstrap_servers=bootstrap_servers(), client_id="news-intelligence-status", request_timeout_ms=3000)
        try:
            topics = sorted(set(admin.list_topics()) & set(TOPICS))
            broker = "ok"
        finally:
            admin.close()
    except Exception as exc:
        detail = str(exc)[:300]
    counts = {row["topic"]: row["count"] for row in KafkaEvent.objects.values("topic").annotate(count=Count("event_id"))}
    return JsonResponse({"broker": broker, "broker_detail": detail, "configured_topics": list(TOPICS),
        "available_topics": topics, "topic_counts": counts,
        "processed_predictions": Prediction.objects.filter(source_type="bbc_live_kafka").count(),
        "dead_lettered": KafkaEvent.objects.filter(status=KafkaEvent.Status.DEAD_LETTERED).count(),
        "active_consumers": "not_observable"})


@require_POST
def streaming_replay(request):
    try:
        from streaming.kafka_client import create_topics
        from streaming.producer import publish_saved_live_items
        created = create_topics()
        result = publish_saved_live_items(limit=500)
        return JsonResponse({**result, "topics_created": created}, status=202)
    except Exception as exc:
        return JsonResponse({"error": f"Could not publish saved BBC headlines to Kafka: {str(exc)[:300]}"}, status=503)
