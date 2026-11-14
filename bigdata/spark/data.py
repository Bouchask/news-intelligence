"""Read labeled article sources directly into Spark without collecting them on the driver."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from bigdata.ingestion.bbc import DatasetError, EXPECTED_CATEGORIES


def clean_text_column(column_name: Any):
    """Return a Spark SQL expression for deterministic HTML/URL/punctuation cleanup."""
    from pyspark.sql import functions as F

    source = F.col(column_name) if isinstance(column_name, str) else column_name
    value = F.regexp_replace(source, r"<[^>]*>", " ")
    value = F.regexp_replace(value, r"(?i)(https?://|www\.)\S+", " ")
    value = F.regexp_replace(value, r"&(?:amp|lt|gt|quot|apos|nbsp);", " ")
    value = F.regexp_replace(value, r"[^\p{L}\p{N}\s]+", " ")
    return F.lower(F.trim(F.regexp_replace(value, r"\s+", " ")))


def _category_root(root: Path) -> Path:
    direct = [child for child in root.iterdir() if child.is_dir() and child.name.lower() in EXPECTED_CATEGORIES]
    if direct:
        return root
    wrappers = [
        child for child in root.iterdir() if child.is_dir() and any(
            grandchild.is_dir() and grandchild.name.lower() in EXPECTED_CATEGORIES
            for grandchild in child.iterdir()
        )
    ]
    return wrappers[0] if len(wrappers) == 1 else root


def _column(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    available = {name.lower(): name for name in columns}
    return next((available[name] for name in candidates if name in available), None)


def read_articles(spark: Any, source: str | Path):
    """Read CSV or BBC category folders as a distributed DataFrame.

    The returned schema is `document_id, title, content, category`. The function
    only inspects source paths/schema on the driver; article records stay in Spark.
    """
    from pyspark.sql import functions as F

    path = Path(source).expanduser().resolve()
    if not path.exists():
        raise DatasetError(f"Dataset path does not exist: {path}")

    if path.is_file() and path.suffix.lower() == ".csv":
        csv_path = path
    elif path.is_dir():
        csv_files = sorted(path.glob("*.csv"))
        csv_path = csv_files[0] if len(csv_files) == 1 else None
    else:
        csv_path = None

    if csv_path is not None:
        raw = spark.read.option("header", True).option("inferSchema", False).option("multiLine", True).csv(str(csv_path))
        content_col = _column(raw.columns, ("content", "text", "article", "body"))
        category_col = _column(raw.columns, ("category", "label", "topic"))
        title_col = _column(raw.columns, ("title", "headline"))
        if content_col is None or category_col is None:
            raise DatasetError("CSV requires a category/label column and a content/text/article/body column.")
        content = F.trim(F.col(content_col).cast("string"))
        title = F.coalesce(F.trim(F.col(title_col).cast("string")), F.lit("")) if title_col else F.lit("")
        category = F.lower(F.trim(F.col(category_col).cast("string")))
        frame = raw.select(title.alias("title"), content.alias("content"), category.alias("category"))
    elif path.is_dir():
        root = _category_root(path)
        frames = []
        for category_dir in sorted(root.iterdir()):
            if not category_dir.is_dir() or category_dir.name.lower() not in EXPECTED_CATEGORIES:
                continue
            if next(category_dir.glob("*.txt"), None) is None:
                continue
            # Each source file is one article; wholetext avoids splitting a multi-line article into rows.
            text = spark.read.option("wholetext", True).text(str(category_dir / "*.txt"))
            content = F.trim(F.col("value"))
            frames.append(text.select(F.lit("").alias("title"), content.alias("content"), F.lit(category_dir.name.lower()).alias("category")))
        if not frames:
            raise DatasetError(f"No category folders with .txt articles found under {path}.")
        frame = frames[0]
        for other in frames[1:]:
            frame = frame.unionByName(other)
    else:
        raise DatasetError(f"Unsupported dataset input: {path}")

    frame = frame.filter(F.col("content").isNotNull() & (F.length(F.col("content")) > 0))
    frame = frame.filter(F.col("category").isNotNull() & (F.length(F.col("category")) > 0))
    frame = frame.withColumn(
        "document_id",
        F.sha2(F.concat_ws("\u0000", F.col("title"), F.col("content")), 256),
    ).select("document_id", "title", "content", "category")
    if frame.limit(1).count() == 0:
        raise DatasetError("No usable labeled articles found in the Spark dataset source.")
    return frame
