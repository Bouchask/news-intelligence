"""Lightweight serving adapter for Spark MLlib multinomial Naive Bayes artifacts."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

import numpy as np

from bigdata.classification.text import clean_text

_TOKEN = re.compile(r"\b[a-zA-Z][a-zA-Z]+\b")


@dataclass
class SparkNBInference:
    vocabulary: dict[str, int]
    idf: np.ndarray
    labels: list[str]
    log_priors: np.ndarray
    feature_log_probabilities: np.ndarray
    selected_features: list[int]
    stop_words: set[str]

    def predict_proba(self, texts: list[str]) -> np.ndarray:
        outputs = []
        for text in texts:
            tokens = [token for token in _TOKEN.findall(clean_text(text)) if token not in self.stop_words]
            frequencies = Counter(self.vocabulary[token] for token in tokens if token in self.vocabulary)
            vector = np.zeros(len(self.vocabulary), dtype=np.float64)
            for index, count in frequencies.items():
                vector[index] = count * float(self.idf[index])
            vector = vector[self.selected_features]
            scores = self.log_priors + self.feature_log_probabilities @ vector
            scores -= scores.max()
            probabilities = np.exp(scores)
            outputs.append(probabilities / probabilities.sum())
        return np.asarray(outputs)

    def predict(self, texts: list[str]) -> np.ndarray:
        probabilities = self.predict_proba(texts)
        return np.asarray([self.labels[index] for index in probabilities.argmax(axis=1)])
