"""Execute the real dataset EDA through the existing Spark runtime.

Usage: spark-submit bigdata/spark_cli.py <csv-or-dataset-directory> [--output path]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from bigdata.ingestion.bbc import DatasetError
from bigdata.spark.data import read_articles
from bigdata.spark.eda import analyze_articles
from bigdata.spark.session import create_spark_session


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute real BBC corpus EDA with Apache Spark")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, default=PROJECT_DIR / "datasets/exports/spark_eda.json")
    args = parser.parse_args()
    if not args.dataset.expanduser().exists():
        parser.error(f"Dataset path does not exist: {args.dataset}")
    spark = create_spark_session()
    try:
        articles = read_articles(spark, args.dataset)
        spark_report = analyze_articles(spark, articles)
    except DatasetError as exc:
        parser.error(str(exc))
    finally:
        spark.stop()

    report = {"source": str(args.dataset.expanduser().resolve()), "layout": "spark_distributed", **spark_report}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Spark analyzed {spark_report['article_count']} supplied articles; wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
