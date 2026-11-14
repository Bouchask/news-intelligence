"""Load BBC-style category folders or CSV files without inventing labels."""
from __future__ import annotations

import csv
import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator

EXPECTED_CATEGORIES = {"business", "entertainment", "politics", "sport", "tech"}
TEXT_COLUMNS = ("content", "text", "article", "body")
CATEGORY_COLUMNS = ("category", "label", "topic")
TITLE_COLUMNS = ("title", "headline")


class DatasetError(ValueError):
    """Raised when the supplied dataset is absent or not a supported BBC layout."""


@dataclass(frozen=True)
class Article:
    document_id: str
    title: str
    content: str
    category: str
    source: str


def _stable_id(_category: str, title: str, content: str) -> str:
    payload = "\0".join((title.strip(), content.strip()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _first(row: dict[str, str], names: tuple[str, ...]) -> str:
    lowered = {key.strip().lower(): value or "" for key, value in row.items() if isinstance(key, str)}
    return next((lowered[name] for name in names if lowered.get(name, "").strip()), "").strip()


def load_csv(path: Path) -> Iterator[Article]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise DatasetError(f"CSV has no header: {path}")
        for line, row in enumerate(reader, start=2):
            content = _first(row, TEXT_COLUMNS)
            category = _first(row, CATEGORY_COLUMNS)
            title = _first(row, TITLE_COLUMNS)
            if not content or not category:
                continue
            yield Article(_stable_id(category, title, content), title, content, category, f"{path.name}:{line}")


def load_category_folders(path: Path) -> Iterator[Article]:
    for category_dir in sorted(item for item in path.iterdir() if item.is_dir()):
        if category_dir.name.lower() not in EXPECTED_CATEGORIES:
            continue
        for file_path in sorted(category_dir.glob("*.txt")):
            content = file_path.read_text(encoding="utf-8", errors="replace").strip()
            if content:
                yield Article(_stable_id(category_dir.name, "", content), "", content, category_dir.name, str(file_path))


def inspect_dataset(path: str | Path) -> dict[str, object]:
    root = Path(path).expanduser()
    if not root.exists():
        raise DatasetError(
            f"Dataset path does not exist: {root}. Create it and add either a labeled CSV "
            "or category folders (business, entertainment, politics, sport, tech) containing .txt files."
        )
    if root.is_file() and root.suffix.lower() == ".csv":
        articles = list(load_csv(root))
        layout = "csv"
    elif root.is_dir():
        csv_files = sorted(root.glob("*.csv"))
        if len(csv_files) == 1:
            articles = list(load_csv(csv_files[0]))
            layout = "csv"
        else:
            category_dirs = [item for item in root.iterdir() if item.is_dir() and item.name.lower() in EXPECTED_CATEGORIES]
            if category_dirs:
                category_root = root
            else:
                wrappers = [
                    item for item in root.iterdir()
                    if item.is_dir() and any(
                        child.is_dir() and child.name.lower() in EXPECTED_CATEGORIES
                        for child in item.iterdir()
                    )
                ]
                category_root = wrappers[0] if len(wrappers) == 1 else root
            articles = list(load_category_folders(category_root))
            layout = "category_folders"
    else:
        raise DatasetError(f"Unsupported dataset input: {root}")
    if not articles:
        raise DatasetError("No usable labeled articles found; expected a labeled CSV or category folders containing .txt files")
    counts: dict[str, int] = {}
    for article in articles:
        counts[article.category] = counts.get(article.category, 0) + 1
    duplicate_ids = len(articles) - len({article.document_id for article in articles})
    lengths = sorted(len(article.content.split()) for article in articles)
    return {
        "source": str(root), "layout": layout, "article_count": len(articles),
        "categories": counts, "category_count": len(counts),
        "missing_content": 0, "duplicate_documents": duplicate_ids,
        "word_count": {"min": lengths[0], "median": lengths[len(lengths) // 2], "max": lengths[-1]},
        "articles": [asdict(article) for article in articles],
    }
