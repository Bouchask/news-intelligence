"""Run Spark MLlib LDA on the configured BBC archive and export real topic data."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from bigdata.ingestion.bbc import DatasetError, inspect_dataset
from bigdata.spark.session import create_spark_session
from bigdata.spark.topics import fit_lda_topics


def main() -> int:
    parser = argparse.ArgumentParser(description="Train an LDA topic model with Spark MLlib")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--topics", type=int, default=8)
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--output", type=Path, default=PROJECT_DIR / "datasets/exports/topics.json")
    parser.add_argument("--model-path", type=Path, default=PROJECT_DIR / "ml_artifacts/topics/lda")
    args = parser.parse_args()
    try:
        records = inspect_dataset(args.dataset)["articles"]
    except DatasetError as exc:
        parser.error(str(exc))
    from bigdata.ingestion.bbc import Article

    articles = [Article(**row) for row in records]
    spark = create_spark_session("news-intelligence-lda")
    try:
        result = fit_lda_topics(spark, articles, args.model_path, num_topics=args.topics, max_iter=args.iterations)
    finally:
        spark.stop()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Spark LDA generated {result['num_topics']} topics from {result['document_count']} documents")
    print(f"Saved topic report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
