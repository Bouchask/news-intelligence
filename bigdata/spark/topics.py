"""Fit a Spark MLlib LDA model on nonnegative document-term counts."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bigdata.ingestion.bbc import Article


def fit_lda_topics(
    spark: Any,
    articles: list[Article],
    artifact_path: str | Path,
    *,
    num_topics: int = 8,
    max_iter: int = 30,
    vocabulary_size: int = 10000,
    random_state: int = 42,
) -> dict[str, Any]:
    if not 2 <= num_topics <= 30:
        raise ValueError("num_topics must be between 2 and 30.")
    if not articles:
        raise ValueError("At least one article is required for topic modeling.")

    from pyspark.ml import Pipeline
    from pyspark.ml.clustering import LDA
    from pyspark.ml.feature import CountVectorizer, RegexTokenizer, StopWordsRemover

    rows = [(article.document_id, f"{article.title} {article.content}") for article in articles]
    frame = spark.createDataFrame(rows, ["document_id", "text"])
    pipeline = Pipeline(stages=[
        RegexTokenizer(inputCol="text", outputCol="tokens", pattern=r"(?U)\b[a-zA-Z][a-zA-Z]+\b", toLowercase=True),
        StopWordsRemover(inputCol="tokens", outputCol="filtered_tokens"),
        CountVectorizer(inputCol="filtered_tokens", outputCol="term_counts", vocabSize=vocabulary_size, minDF=2.0),
        LDA(k=num_topics, maxIter=max_iter, featuresCol="term_counts", seed=random_state, optimizer="online"),
    ])
    model = pipeline.fit(frame)
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
    distributions = [
        {"document_id": row["document_id"], "distribution": [float(value) for value in row["topicDistribution"]]}
        for row in model.transform(frame).select("document_id", "topicDistribution").collect()
    ]
    output = Path(artifact_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    model.write().overwrite().save(str(output))
    return {
        "algorithm": "spark_mllib_lda",
        "num_topics": num_topics,
        "max_iter": max_iter,
        "document_count": len(articles),
        "vocabulary_size": len(vocabulary),
        "topics": topic_terms,
        "document_distributions": distributions,
        "artifact_path": str(output),
    }
