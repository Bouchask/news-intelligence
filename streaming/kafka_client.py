from __future__ import annotations

import json
import os
from typing import Any

TOPICS = (
    "news.raw",
    "news.preprocessed",
    "news.classification.requests",
    "news.classification.results",
    "news.analytics.events",
    "system.events",
    "news.raw.dlq",
    "news.classification.dlq",
)


def bootstrap_servers() -> list[str]:
    value = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092").strip()
    return [item.strip() for item in value.split(",") if item.strip()]


def create_producer():
    from kafka import KafkaProducer

    return KafkaProducer(
        bootstrap_servers=bootstrap_servers(),
        key_serializer=lambda value: value.encode("utf-8") if isinstance(value, str) else value,
        value_serializer=lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
        acks="all",
        retries=5,
        request_timeout_ms=15000,
        max_block_ms=15000,
    )


def create_consumer(topic: str, group_id: str):
    from kafka import KafkaConsumer

    return KafkaConsumer(
        topic,
        bootstrap_servers=bootstrap_servers(),
        group_id=group_id,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        consumer_timeout_ms=1000,
        max_poll_records=20,
        request_timeout_ms=15000,
    )


def send_json(producer: Any, topic: str, event: dict[str, Any], key: str) -> None:
    producer.send(topic, key=key, value=event).get(timeout=20)


def create_topics() -> list[str]:
    from kafka.admin import KafkaAdminClient, NewTopic
    from kafka.errors import TopicAlreadyExistsError

    admin = KafkaAdminClient(bootstrap_servers=bootstrap_servers(), client_id="news-intelligence-admin", request_timeout_ms=10000)
    try:
        existing = set(admin.list_topics())
        requested = [name for name in TOPICS if name not in existing]
        if requested:
            try:
                admin.create_topics([NewTopic(name, num_partitions=3, replication_factor=1) for name in requested], validate_only=False)
            except TopicAlreadyExistsError:
                pass
        return requested
    finally:
        admin.close()
