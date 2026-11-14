"""Fit a Spark MLlib LDA model on nonnegative document-term counts."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bigdata.spark.data import clean_text_column, read_articles


def fit_lda_topics(
    spark: Any,
    articles: Any,
    artifact_path: str | Path,
    *,
    num_topics: int = 8,
    max_iter: int = 30,
    vocabulary_size: int = 10000,
    random_state: int = 42,
) -> dict[str, Any]:
    if not 2 <= num_topics <= 30:
        raise ValueError("num_topics must be between 2 and 30.")
    if isinstance(articles, (str, Path)):
        frame = read_articles(spark, articles)
    elif hasattr(articles, "select"):
        frame = articles
    else:
        rows = [(item.document_id, item.title, item.content, item.category) for item in articles]
        frame = spark.createDataFrame(rows, ["document_id", "title", "content", "category"])
    frame = frame.dropDuplicates(["document_id"])
    if frame.limit(1).count() == 0:
        raise ValueError("At least one article is required for topic modeling.")

    from pyspark.ml import Pipeline
    from pyspark.ml.clustering import LDA
    from pyspark.ml.feature import CountVectorizer, RegexTokenizer, StopWordsRemover
    from pyspark.ml.functions import vector_to_array
    from pyspark.sql import functions as F

    rows = frame.select("document_id", clean_text_column(F.concat_ws(" ", "title", "content")).alias("text"))
    pipeline = Pipeline(stages=[
        RegexTokenizer(inputCol="text", outputCol="tokens", pattern=r"(?U)\b[a-zA-Z][a-zA-Z]+\b", toLowercase=True),
        StopWordsRemover(inputCol="tokens", outputCol="filtered_tokens"),
        CountVectorizer(inputCol="filtered_tokens", outputCol="term_counts", vocabSize=vocabulary_size, minDF=2.0),
        LDA(k=num_topics, maxIter=max_iter, featuresCol="term_counts", seed=random_state, optimizer="online"),
    ])
    model = pipeline.fit(rows)
    lda_model = model.stages[-1]
    vectorizer_model = model.stages[-2]
    vocabulary = vectorizer_model.vocabulary
    topic_terms = []
    for row in lda_model.describeTopics(maxTermsPerTopic=12).orderBy("topic").collect():
        topic_terms.append({
            "topic_id": int(row["topic"]),
            "terms": [
                {"term": vocabulary[int(index)], "weight": float(weight)}
                for index, weight in zip(row["termIndices"], row["termWeights"])
            ],
        })
    output = Path(artifact_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    model.write().overwrite().save(str(output))
    distribution_path = output.with_name(output.name + ".distributions.parquet")
    model.transform(rows).select(
        "document_id", vector_to_array("topicDistribution").alias("topic_distribution"),
    ).write.mode("overwrite").parquet(str(distribution_path))
    return {
        "algorithm": "spark_mllib_lda",
        "num_topics": num_topics,
        "max_iter": max_iter,
        "document_count": frame.count(),
        "vocabulary_size": len(vocabulary),
        "topics": topic_terms,
        "distribution_path": str(distribution_path),
        "artifact_path": str(output),
    }
