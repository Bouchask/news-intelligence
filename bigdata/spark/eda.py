"""Distributed corpus statistics and per-class word frequencies."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bigdata.spark.data import read_articles


def analyze_articles(spark: Any, articles: Any) -> dict[str, Any]:
    """Analyze a Spark DataFrame or source path; legacy Article lists remain supported."""
    from pyspark.sql import Window, functions as F

    if isinstance(articles, (str, Path)):
        frame = read_articles(spark, articles)
    elif hasattr(articles, "select"):
        frame = articles
    else:
        rows = [(item.document_id, item.title, item.content, item.category) for item in articles]
        frame = spark.createDataFrame(rows, ["document_id", "title", "content", "category"])

    enriched = frame.withColumn("word_count", F.size(F.split(F.trim(F.col("content")), r"\s+")))
    category_counts = {
        row["category"]: int(row["count"])
        for row in enriched.groupBy("category").count().orderBy("category").collect()
    }
    lengths = enriched.agg(
        F.min("word_count").alias("min"),
        F.expr("percentile_approx(word_count, 0.5)").alias("median"),
        F.max("word_count").alias("max"),
        F.avg("word_count").alias("mean"),
    ).first()
    tokens = enriched.select(
        "category",
        F.explode(F.split(F.regexp_replace(F.lower(F.col("content")), r"[^\p{L}\p{N}]+", " "), r"\s+")).alias("word"),
    ).filter(F.length("word") > 1)
    word_counts = tokens.groupBy("category", "word").count()
    vocabulary_size = word_counts.select("word").distinct().count()
    ranking = Window.partitionBy("category").orderBy(F.desc("count"), F.asc("word"))
    top_words: dict[str, list[dict[str, Any]]] = {}
    for row in word_counts.withColumn("rank", F.row_number().over(ranking)).filter(F.col("rank") <= 20).collect():
        top_words.setdefault(row["category"], []).append({"word": row["word"], "count": int(row["count"])})

    article_count = enriched.count()
    unique_documents = enriched.select("document_id").distinct().count()
    return {
        "article_count": article_count,
        "category_count": len(category_counts),
        "categories": category_counts,
        "category_distribution": category_counts,
        "duplicate_documents": article_count - unique_documents,
        "vocabulary_size": vocabulary_size,
        "top_words_by_category": top_words,
        "word_count": {key: float(lengths[key]) if key == "mean" else int(lengths[key]) for key in ("min", "median", "max", "mean")},
    }
