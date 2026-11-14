"""Create a JSON-safe EDA summary from the dataset ingestion report."""
from collections import Counter
from typing import Any


def summarize(dataset_report: dict[str, Any]) -> dict[str, Any]:
    articles = dataset_report["articles"]
    category_words: dict[str, Counter[str]] = {}
    for article in articles:
        category = article["category"]
        words = category_words.setdefault(category, Counter())
        words.update(word.casefold() for word in article["content"].split())
    return {
        key: value for key, value in dataset_report.items() if key != "articles"
    } | {
        "vocabulary_size": len({word for counts in category_words.values() for word in counts}),
        "top_words_by_category": {
            category: [{"word": word, "count": count} for word, count in counts.most_common(20)]
            for category, counts in sorted(category_words.items())
        },
    }
