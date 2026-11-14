"""Spark session configuration that does not mutate host environment variables."""
from __future__ import annotations

import os
import sys
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
    builder = builder.master(os.getenv("SPARK_MASTER", "local[*]"))
    python_executable = os.getenv("PYSPARK_PYTHON", sys.executable)
    builder = builder.config("spark.pyspark.python", python_executable)
    builder = builder.config("spark.pyspark.driver.python", python_executable)
    return builder.getOrCreate()
