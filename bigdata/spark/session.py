"""Spark session configuration that does not mutate host environment variables."""
from __future__ import annotations

import os
from typing import Any


def create_spark_session(app_name: str | None = None) -> Any:
    try:
        from pyspark.sql import SparkSession
    except ImportError as exc:
        raise RuntimeError(
            "PySpark is not importable in this interpreter. Run the job with the existing "
            "Spark installation's spark-submit and its bundled PySpark libraries."
        ) from exc

    builder = SparkSession.builder.appName(app_name or os.getenv("SPARK_APP_NAME", "news-intelligence"))
    master = os.getenv("SPARK_MASTER")
    if master:
        builder = builder.master(master)
    return builder.getOrCreate()
