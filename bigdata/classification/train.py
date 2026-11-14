"""Train reproducible baseline, Multinomial NB, or KNN text models."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.feature_selection import SelectKBest, VarianceThreshold, chi2
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, precision_recall_fscore_support, precision_score, recall_score, make_scorer
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline

from bigdata.classification.text import clean_text
from bigdata.ingestion.bbc import inspect_dataset

Algorithm = Literal["baseline", "naive_bayes", "knn"]
Selector = Literal["none", "variance", "chi2"]
ALGORITHMS = {"baseline", "naive_bayes", "knn"}
SELECTORS = {"none", "variance", "chi2"}


def _pipeline(algorithm: Algorithm, selector: Selector, max_features: int, k_features: int) -> tuple[Pipeline, list[dict[str, Any]]]:
    if algorithm == "baseline":
        classifier = DummyClassifier(strategy="most_frequent")
        grid: list[dict[str, Any]] = [{}]
    elif algorithm == "naive_bayes":
        classifier = MultinomialNB()
        grid = [{"classifier__alpha": [0.5, 1.0, 1.5]}]
    elif algorithm == "knn":
        classifier = KNeighborsClassifier(algorithm="brute", metric="cosine", weights="distance")
        grid = [{"classifier__n_neighbors": [3, 5, 7]}]
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    steps: list[tuple[str, Any]] = [
        ("tfidf", TfidfVectorizer(
            preprocessor=clean_text,
            stop_words="english",
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.95,
            max_features=max_features,
            sublinear_tf=True,
            dtype=np.float64,
        )),
    ]
    if selector == "variance":
        steps.append(("selection", VarianceThreshold(threshold=1e-5)))
    elif selector == "chi2":
        steps.append(("selection", SelectKBest(chi2, k=k_features)))
    elif selector != "none":
        raise ValueError(f"Unsupported feature selector: {selector}")
    steps.append(("classifier", classifier))
    return Pipeline(steps), grid


def train_experiment(
    dataset_path: str | Path,
    artifact_root: str | Path,
    experiment_id: str,
    algorithm: Algorithm,
    selector: Selector = "none",
    *,
    random_state: int = 42,
    test_size: float = 0.2,
    folds: int = 5,
    max_features: int = 5000,
    k_features: int = 500,
) -> dict[str, Any]:
    if algorithm not in ALGORITHMS or selector not in SELECTORS:
        raise ValueError("Unknown algorithm or feature selector.")
    if not 0.05 <= test_size <= 0.5:
        raise ValueError("test_size must be between 0.05 and 0.5.")

    report = inspect_dataset(dataset_path)
    articles = report["articles"]
    texts = [f"{article['title']}\n{article['content']}" for article in articles]
    labels = [article["category"] for article in articles]
    if len(set(labels)) < 2:
        raise ValueError("Training requires at least two categories.")

    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=test_size, random_state=random_state, stratify=labels,
    )
    class_counts = {label: y_train.count(label) for label in sorted(set(y_train))}
    cv_folds = min(folds, min(class_counts.values()))
    if cv_folds < 2:
        raise ValueError("At least two training examples per category are required for stratified cross-validation.")
    splitter = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=random_state)
    pipeline, grid = _pipeline(algorithm, selector, max_features, k_features)

    started = time.perf_counter()
    search = GridSearchCV(
        pipeline,
        param_grid=grid,
        scoring={
            "accuracy": "accuracy",
            "precision_macro": make_scorer(precision_score, average="macro", zero_division=0),
            "recall_macro": make_scorer(recall_score, average="macro", zero_division=0),
            "f1_macro": make_scorer(f1_score, average="macro", zero_division=0),
        },
        refit="f1_macro",
        cv=splitter,
        n_jobs=1,
        return_train_score=False,
        error_score="raise",
    )
    search.fit(X_train, y_train)
    best = search.best_estimator_
    predictions = best.predict(X_test)
    precision, recall, f1, _ = precision_recall_fscore_support(y_test, predictions, average="macro", zero_division=0)
    classes = list(best.named_steps["classifier"].classes_)
    matrix = confusion_matrix(y_test, predictions, labels=classes)
    vectorizer = best.named_steps["tfidf"]
    feature_count_before = len(vectorizer.vocabulary_)
    selector_step = best.named_steps.get("selection")
    feature_count_after = int(selector_step.get_support().sum()) if selector_step is not None else feature_count_before
    elapsed = time.perf_counter() - started

    metrics = {
        "accuracy": float(accuracy_score(y_test, predictions)),
        "precision_macro": float(precision),
        "recall_macro": float(recall),
        "f1_macro": float(f1),
        "cv_accuracy": float(search.cv_results_["mean_test_accuracy"][search.best_index_]),
        "cv_precision_macro": float(search.cv_results_["mean_test_precision_macro"][search.best_index_]),
        "cv_recall_macro": float(search.cv_results_["mean_test_recall_macro"][search.best_index_]),
        "cv_f1_macro": float(search.cv_results_["mean_test_f1_macro"][search.best_index_]),
        "training_seconds": round(elapsed, 3),
        "train_documents": len(X_train),
        "test_documents": len(X_test),
        "cv_folds": cv_folds,
        "feature_count_before_selection": feature_count_before,
        "feature_count_after_selection": feature_count_after,
        "classes": classes,
        "best_hyperparameters": search.best_params_,
        "classification_report": classification_report(y_test, predictions, output_dict=True, zero_division=0),
    }
    artifact_dir = Path(artifact_root).expanduser().resolve() / algorithm
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{experiment_id}.joblib"
    joblib.dump({"pipeline": best, "algorithm": algorithm, "selector": selector, "classes": classes, "experiment_id": experiment_id}, artifact_path)
    return {
        "algorithm": algorithm,
        "selector": selector,
        "metrics": metrics,
        "confusion_matrix": {"labels": classes, "values": matrix.astype(int).tolist()},
        "artifact_path": str(artifact_path),
        "best_hyperparameters": search.best_params_,
    }


def predict_with_artifact(artifact_path: str | Path, text: str) -> dict[str, Any]:
    artifact = joblib.load(artifact_path)
    pipeline = artifact["pipeline"]
    predicted = str(pipeline.predict([text])[0])
    confidence: float | None = None
    probabilities: dict[str, float] = {}
    if hasattr(pipeline, "predict_proba"):
        values = pipeline.predict_proba([text])[0]
        classes = pipeline.named_steps["classifier"].classes_
        probabilities = {str(label): float(probability) for label, probability in zip(classes, values)}
        confidence = probabilities[predicted]
    return {"category": predicted, "confidence": confidence, "probabilities": probabilities}
