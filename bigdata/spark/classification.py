"""Distributed, leakage-safe Spark MLlib Multinomial Naive Bayes training."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from bigdata.spark.data import clean_text_column, read_articles
from bigdata.spark.inference import SparkNBInference


def _preprocessing_pipeline(labels: list[str], max_features: int, min_df: float, max_df: float):
    from pyspark.ml import Pipeline
    from pyspark.ml.feature import CountVectorizer, IDF, RegexTokenizer, StopWordsRemover, StringIndexerModel

    return Pipeline(stages=[
        RegexTokenizer(inputCol="text", outputCol="tokens", pattern=r"(?U)\b[a-zA-Z][a-zA-Z]+\b", toLowercase=True),
        StopWordsRemover(inputCol="tokens", outputCol="filtered_tokens", stopWords=StopWordsRemover.loadDefaultStopWords("english")),
        CountVectorizer(inputCol="filtered_tokens", outputCol="term_counts", vocabSize=max_features, minDF=min_df, maxDF=max_df),
        IDF(inputCol="term_counts", outputCol="features"),
        StringIndexerModel.from_labels(labels, inputCol="category", outputCol="label"),
    ])


def _stratified_holdout(frame: Any, test_size: float, seed: int):
    from pyspark.sql import Window, functions as F

    counts = {row["category"]: int(row["count"]) for row in frame.groupBy("category").count().collect()}
    if len(counts) < 2:
        raise ValueError("Spark classification requires at least two categories.")
    if min(counts.values()) < 2:
        raise ValueError("Each category needs at least two distinct articles for stratified train/test splitting.")
    order = Window.partitionBy("category").orderBy(F.xxhash64("document_id", F.lit(seed)), F.col("document_id"))
    totals = frame.groupBy("category").agg(F.count(F.lit(1)).alias("_class_total"))
    ranked = frame.withColumn("_class_row", F.row_number().over(order)).join(totals, "category")
    ideal_train = F.floor(F.col("_class_total") * (1 - test_size)).cast("int")
    train_limit = F.least(F.greatest(ideal_train, F.lit(1)), F.col("_class_total") - F.lit(1))
    ranked = ranked.withColumn("_train_limit", train_limit)
    labels = sorted(counts)
    train = ranked.filter(F.col("_class_row") <= F.col("_train_limit")).drop("_class_row", "_class_total", "_train_limit")
    test = ranked.filter(F.col("_class_row") > F.col("_train_limit")).drop("_class_row", "_class_total", "_train_limit")
    train_counts = {row["category"]: int(row["count"]) for row in train.groupBy("category").count().collect()}
    return train, test, labels, train_counts


def _assign_stratified_folds(train: Any, folds: int, seed: int):
    from pyspark.sql import Window, functions as F

    order = Window.partitionBy("category").orderBy(F.xxhash64("document_id", F.lit(seed + 1)), F.col("document_id"))
    return train.withColumn("_cv_row", F.row_number().over(order)).withColumn(
        "_fold", F.pmod(F.col("_cv_row") - F.lit(1), F.lit(folds)),
    ).drop("_cv_row")


def _fit_selector(train: Any, selector: str, k_features: int):
    from pyspark.ml.feature import ChiSqSelector, VectorSlicer
    from pyspark.ml.stat import Summarizer
    from pyspark.sql import functions as F

    feature_count = int(train.select("features").first()["features"].size)
    if feature_count < 1:
        raise ValueError("Spark produced an empty vocabulary; check article text and minDF/maxDF settings.")
    if selector == "none":
        return None, list(range(feature_count)), "features"
    if selector == "chi2":
        selector_model = ChiSqSelector(
            numTopFeatures=min(max(1, k_features), feature_count),
            featuresCol="features", outputCol="selected_features", labelCol="label",
        ).fit(train)
        indices = [int(index) for index in selector_model.selectedFeatures]
        return selector_model, indices, "selected_features"
    if selector == "variance":
        variance = train.select(Summarizer.metrics("variance").summary(F.col("features")).alias("stats")).first()["stats"].variance
        values = variance.toArray().tolist()
        indices = [index for index, value in enumerate(values) if value > 1e-5]
        if not indices:
            raise ValueError("Variance selector removed every feature; lower the threshold or check the corpus.")
        return VectorSlicer(inputCol="features", outputCol="selected_features", indices=indices), indices, "selected_features"
    raise ValueError("selector must be none, variance, or chi2")


def _evaluate(predictions: Any, labels: list[str]) -> dict[str, Any]:
    pairs = predictions.groupBy("label", "prediction").count().collect()
    matrix = [[0 for _ in labels] for _ in labels]
    for row in pairs:
        actual, predicted = int(row["label"]), int(row["prediction"])
        matrix[actual][predicted] = int(row["count"])
    per_class = {}
    precisions, recalls, f1s = [], [], []
    total = sum(sum(line) for line in matrix)
    correct = 0
    for index, label in enumerate(labels):
        true_positive = matrix[index][index]
        predicted_count = sum(matrix[actual][index] for actual in range(len(labels)))
        actual_count = sum(matrix[index])
        precision = true_positive / predicted_count if predicted_count else 0.0
        recall = true_positive / actual_count if actual_count else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {"precision": precision, "recall": recall, "f1-score": f1, "support": actual_count}
        precisions.append(precision); recalls.append(recall); f1s.append(f1); correct += true_positive
    return {
        "accuracy": correct / total if total else 0.0,
        "precision_macro": float(np.mean(precisions)),
        "recall_macro": float(np.mean(recalls)),
        "f1_macro": float(np.mean(f1s)),
        "classification_report": per_class,
        "confusion_matrix": {"labels": labels, "values": matrix},
    }


def train_spark_naive_bayes(
    spark: Any,
    dataset_path: str | Path,
    artifact_root: str | Path,
    experiment_id: str,
    selector: str = "none",
    *,
    random_state: int = 42,
    test_size: float = 0.2,
    folds: int = 5,
    max_features: int = 5000,
    k_features: int = 500,
    min_df: float = 2.0,
    max_df: float = 0.95,
    smoothing_values: tuple[float, ...] = (0.5, 1.0, 1.5),
) -> dict[str, Any]:
    """Train, stratified-CV tune, holdout-evaluate, and save Spark MLlib NB."""
    from pyspark.ml.classification import NaiveBayes
    from pyspark.ml import PipelineModel
    from pyspark.sql import functions as F

    if selector not in {"none", "variance", "chi2"}:
        raise ValueError("selector must be none, variance, or chi2")
    if not 0.05 <= test_size <= 0.5:
        raise ValueError("test_size must be between 0.05 and 0.5")
    if folds < 2:
        raise ValueError("folds must be at least two")

    started = time.perf_counter()
    source = read_articles(spark, dataset_path)
    conflicts = source.groupBy("document_id").agg(F.countDistinct("category").alias("label_count")).filter(F.col("label_count") > 1)
    if conflicts.limit(1).count():
        raise ValueError("The same article text has conflicting category labels; resolve these records before supervised training.")
    source = source.dropDuplicates(["document_id"])
    frame = source.withColumn("text", clean_text_column(F.concat_ws(" ", "title", "content"))).select("document_id", "category", "text")
    train_raw, test_raw, labels, class_counts = _stratified_holdout(frame, test_size, random_state)
    cv_folds = min(folds, min(class_counts.values()))
    if cv_folds < 2:
        raise ValueError("Each class needs at least two training articles for stratified cross-validation.")
    fold_frame = _assign_stratified_folds(train_raw, cv_folds, random_state).cache()
    fold_results = {alpha: [] for alpha in smoothing_values}

    for fold_index in range(cv_folds):
        fold_train = fold_frame.filter(F.col("_fold") != fold_index).drop("_fold")
        fold_valid = fold_frame.filter(F.col("_fold") == fold_index).drop("_fold")
        preprocessing_model = _preprocessing_pipeline(labels, max_features, min_df, max_df).fit(fold_train)
        base_train = preprocessing_model.transform(fold_train).cache()
        base_valid = preprocessing_model.transform(fold_valid).cache()
        selector_model, _, features_col = _fit_selector(base_train, selector, k_features)
        if selector_model is not None:
            processed_train = selector_model.transform(base_train).cache()
            processed_valid = selector_model.transform(base_valid).cache()
        else:
            processed_train, processed_valid = base_train, base_valid
        for alpha in smoothing_values:
            classifier = NaiveBayes(
                modelType="multinomial", smoothing=float(alpha), labelCol="label",
                featuresCol=features_col, predictionCol="prediction",
            ).fit(processed_train)
            scores = _evaluate(classifier.transform(processed_valid).select("label", "prediction"), labels)
            fold_results[alpha].append(scores)
        if selector_model is not None:
            processed_train.unpersist(); processed_valid.unpersist()
        base_train.unpersist(); base_valid.unpersist()
    fold_frame.unpersist()

    cv_summary = {
        alpha: {
            metric: float(np.mean([score[metric] for score in scores]))
            for metric in ("accuracy", "precision_macro", "recall_macro", "f1_macro")
        }
        for alpha, scores in fold_results.items()
    }
    best_alpha = max(smoothing_values, key=lambda alpha: cv_summary[alpha]["f1_macro"])

    final_preprocessor = _preprocessing_pipeline(labels, max_features, min_df, max_df)
    preprocessing_model = final_preprocessor.fit(train_raw)
    base_train = preprocessing_model.transform(train_raw).cache()
    base_test = preprocessing_model.transform(test_raw).cache()
    selector_model, selected_indices, features_col = _fit_selector(base_train, selector, k_features)
    if selector_model is not None:
        processed_train = selector_model.transform(base_train).cache()
        processed_test = selector_model.transform(base_test).cache()
    else:
        processed_train, processed_test = base_train, base_test
    classifier = NaiveBayes(
        modelType="multinomial", smoothing=float(best_alpha), labelCol="label",
        featuresCol=features_col, predictionCol="prediction",
    ).fit(processed_train)
    test_scores = _evaluate(classifier.transform(processed_test).select("label", "prediction"), labels)
    train_count = processed_train.count()
    test_count = processed_test.count()
    vocabulary_model = next(stage for stage in preprocessing_model.stages if hasattr(stage, "vocabulary"))
    idf_model = next(stage for stage in preprocessing_model.stages if hasattr(stage, "idf"))
    stopword_model = next(stage for stage in preprocessing_model.stages if hasattr(stage, "getStopWords"))
    vocabulary = {term: index for index, term in enumerate(vocabulary_model.vocabulary)}
    stop_words = set(stopword_model.getStopWords())
    inference = SparkNBInference(
        vocabulary=vocabulary,
        idf=np.asarray(idf_model.idf.toArray(), dtype=np.float64),
        labels=labels,
        log_priors=np.asarray(classifier.pi.toArray(), dtype=np.float64),
        feature_log_probabilities=np.asarray(classifier.theta.toArray(), dtype=np.float64).reshape(
            (classifier.theta.numRows, classifier.theta.numCols), order="F",
        ),
        selected_features=selected_indices,
        stop_words=stop_words,
    )

    output_dir = Path(artifact_root).expanduser().resolve() / "spark_naive_bayes"
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / f"{experiment_id}.joblib"
    spark_model_path = output_dir / f"{experiment_id}.spark"
    stages = list(preprocessing_model.stages)
    if selector_model is not None:
        stages.append(selector_model)
    stages.append(classifier)
    PipelineModel(stages=stages).write().overwrite().save(str(spark_model_path))
    joblib.dump({"kind": "spark_mllib_naive_bayes", "inference": inference, "experiment_id": experiment_id}, artifact_path)
    if selector_model is not None:
        processed_train.unpersist(); processed_test.unpersist()
    base_train.unpersist(); base_test.unpersist()

    metrics = {
        **{key: test_scores[key] for key in ("accuracy", "precision_macro", "recall_macro", "f1_macro", "classification_report")},
        "cv_accuracy": cv_summary[best_alpha]["accuracy"],
        "cv_precision_macro": cv_summary[best_alpha]["precision_macro"],
        "cv_recall_macro": cv_summary[best_alpha]["recall_macro"],
        "cv_f1_macro": cv_summary[best_alpha]["f1_macro"],
        "training_seconds": round(time.perf_counter() - started, 3),
        "train_documents": train_count,
        "test_documents": test_count,
        "cv_folds": cv_folds,
        "feature_count_before_selection": len(vocabulary),
        "feature_count_after_selection": len(selected_indices),
        "classes": labels,
        "best_hyperparameters": {"smoothing": float(best_alpha)},
        "cross_validation": {str(alpha): scores for alpha, scores in cv_summary.items()},
        "engine": "Apache Spark MLlib",
        "spark_model_path": str(spark_model_path),
    }
    return {
        "algorithm": "spark_naive_bayes",
        "selector": selector,
        "metrics": metrics,
        "confusion_matrix": test_scores["confusion_matrix"],
        "artifact_path": str(artifact_path),
        "spark_model_path": str(spark_model_path),
        "best_hyperparameters": {"smoothing": float(best_alpha)},
    }
