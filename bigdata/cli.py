"""Command-line dataset audit and EDA export."""
import argparse
import json
import os
from pathlib import Path

from bigdata.eda.report import summarize
from bigdata.ingestion.bbc import DatasetError, inspect_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect a BBC News dataset and export real EDA statistics")
    parser.add_argument(
        "dataset", nargs="?", type=Path,
        default=Path(os.environ.get("BBC_DATASET_PATH", "datasets/raw")),
        help="CSV file or directory of category folders / one CSV (default: BBC_DATASET_PATH or datasets/raw)",
    )
    parser.add_argument("--output", type=Path, default=Path("datasets/exports/eda.json"))
    args = parser.parse_args()
    try:
        report = summarize(inspect_dataset(args.dataset))
    except DatasetError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote EDA for {report['article_count']} real articles to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
