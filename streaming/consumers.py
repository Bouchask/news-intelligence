from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from bigdata.classification.text import clean_text
from bigdata.classification.train import predict_with_artifact
from apps.experiments.models import KafkaEvent, Prediction, RegisteredModel

from .kafka_client import create_consumer, create_producer, send_json
from .schemas import EventValidationError, validate_news_event


def _record(topic: str, event: dict, status: str, error: str = "") -> None:
    key = f"{topic}:{event.get('event_id', 'unknown')}"[:128]
    KafkaEvent.objects.update_or_create(
        event_id=key,
        defaults={"topic": topic, "event_type": str(event.get("event_type", "unknown"))[:120],
                  "status": status, "error_message": error[:4000],
                  "processed_at": timezone.now() if status != KafkaEvent.Status.RECEIVED else None},
    )


def _decode(message) -> dict:
    value = json.loads(message.value.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Kafka payload must be a JSON object.")
    return value


def _dlq(producer, topic: str, raw: bytes, error: str, key: bytes | None) -> None:
    destination = "news.raw.dlq" if topic == "news.raw" else "news.classification.dlq"
    producer.send(destination, key=key, value={"source_topic": topic, "error": error[:2000],
                    "payload": raw.decode("utf-8", errors="replace")[:60000], "failed_at": timezone.now().isoformat()}).get(timeout=20)


def _raw(message, producer) -> None:
    event = _decode(message)
    event = validate_news_event(event)
    event["content"] = clean_text(event["content"])
    if not event["content"]:
        raise ValueError("BBC summary contains no usable text after cleaning.")
    event["event_type"] = "news.preprocessed"
    send_json(producer, "news.preprocessed", event, event["document_id"])
    request = {**event, "event_type": "news.classification.requested"}
    send_json(producer, "news.classification.requests", request, event["document_id"])
    _record("news.raw", event, KafkaEvent.Status.PROCESSED)


def _classify(message, producer) -> None:
    event = validate_news_event(_decode(message))
    model = RegisteredModel.objects.filter(is_active=True).first()
    if model is None:
        raise RuntimeError("No active model is registered.")
    artifact = Path(model.artifact_path).resolve()
    if not artifact.is_relative_to(settings.MODEL_ARTIFACT_DIR.resolve()) or not artifact.is_file():
        raise RuntimeError("Active model artifact is missing or outside the model artifact directory.")
    text = f"{event['title'].strip()}\n{event['content'].strip()}"
    started = time.perf_counter()
    result = predict_with_artifact(artifact, text)
    output = {"event_id": event["event_id"], "document_id": event["document_id"],
              "event_type": "news.classification.completed", "model_version_id": str(model.pk),
              "category": result["category"], "probabilities": result["probabilities"],
              "confidence": result["confidence"], "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
              "latency_ms": (time.perf_counter() - started) * 1000,
              "source_url": event["source_url"], "title": event["title"], "classified_at": timezone.now().isoformat()}
    send_json(producer, "news.classification.results", output, event["event_id"])
    _record("news.classification.requests", event, KafkaEvent.Status.PROCESSED)


def _persist(message, producer) -> None:
    event = _decode(message)
    event_id = str(event.get("event_id", ""))
    try:
        model = RegisteredModel.objects.get(pk=event["model_version_id"])
        with transaction.atomic():
            Prediction.objects.get_or_create(event_id=event_id, defaults={
                "model_version": model, "content_sha256": event["content_sha256"],
                "predicted_category": event["category"], "probabilities": event.get("probabilities", {}),
                "confidence": event.get("confidence"), "latency_ms": event.get("latency_ms", 0),
                "source_type": "bbc_live_kafka",
            })
            _record("news.classification.results", event, KafkaEvent.Status.PROCESSED)
    except RegisteredModel.DoesNotExist:
        raise ValueError("Result references an unknown model version.")


def run_consumer(mode: str) -> None:
    topics = {"raw": "news.raw", "classify": "news.classification.requests", "results": "news.classification.results"}
    topic = topics[mode]
    consumer = create_consumer(topic, f"news-intelligence-{mode}-v1")
    producer = create_producer()
    handlers = {"raw": _raw, "classify": _classify, "results": _persist}
    print(f"Consuming {topic}; Ctrl-C to stop.", flush=True)
    try:
        while True:
            for message in consumer:
                try:
                    handlers[mode](message, producer)
                except Exception as exc:
                    try:
                        _dlq(producer, topic, message.value, str(exc), message.key)
                        try:
                            failed_event = _decode(message)
                        except (ValueError, UnicodeDecodeError):
                            failed_event = {"event_id": f"{message.partition}-{message.offset}", "event_type": "invalid_json"}
                        _record(topic, failed_event, KafkaEvent.Status.DEAD_LETTERED, str(exc))
                    except Exception as dlq_error:
                        print(f"DLQ publish failed; leaving offset uncommitted: {dlq_error}", flush=True)
                        time.sleep(2)
                        continue
                    print(f"Sent invalid event to DLQ: {exc}", flush=True)
                consumer.commit()
    except KeyboardInterrupt:
        print("Stopping consumer.", flush=True)
    finally:
        consumer.close()
        producer.close(timeout=10)
