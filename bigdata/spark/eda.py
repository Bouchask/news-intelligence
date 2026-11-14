"""Distributed EDA calculations over ingested article records."""
from __future__ import annotations

from typing import Any

from bigdata.ingestion.bbc import Article


def analyze_articles(spark: Any, articles: list[Article]) -> dict[str, Any]:
    """Compute corpus dimensions, class counts, duplicate count, and length stats in Spark."""
    from pyspark.sql import functions as F

    rows = [(item.document_id, item.title, item.content, item.category) for item in articles]
    frame = spark.createDataFrame(rows, ["document_id", "title", "content", "category"])
    enriched = frame.withColumn("word_count", F.size(F.split(F.trim("content"), r"\s+")))
    category_counts = {
        row["category"]: row["count"]
        for row in enriched.groupBy("category").count().orderBy("category").collect()
    }
    lengths = enriched.agg(
        F.min("word_count").alias("min"),
        F.expr("percentile_approx(word_count, 0.5)").alias("median"),
        F.max("word_count").alias("max"),
        F.avg("word_count").alias("mean"),
    ).first()
    return {
        "article_count": enriched.count(),
        "category_count": len(category_counts),
        "category_distribution": category_counts,
        "duplicate_documents": enriched.count() - enriched.select("document_id").distinct().count(),
        "word_count": {key: lengths[key] for key in ("min", "median", "max", "mean")},
    }
