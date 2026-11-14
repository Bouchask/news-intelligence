"""Deterministic text cleanup shared by training and prediction."""
from __future__ import annotations

import html
import re
import unicodedata

_HTML = re.compile(r"<[^>]+>")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE = re.compile(r"\s+")


def clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = _HTML.sub(" ", value)
    value = _URL.sub(" ", value)
    value = unicodedata.normalize("NFKC", value).casefold()
    value = _NON_WORD.sub(" ", value)
    return _SPACE.sub(" ", value).strip()
