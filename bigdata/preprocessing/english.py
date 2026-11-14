"""English tokenization with an honest optional spaCy model fallback."""
from __future__ import annotations

from functools import lru_cache

from bigdata.classification.text import clean_text


@lru_cache(maxsize=1)
def _load_nlp():
    import spacy

    if spacy.util.is_package("en_core_web_sm"):
        return spacy.load("en_core_web_sm", disable=["parser", "ner"]), True
    return spacy.blank("en"), False


def preprocess_english(text: str) -> dict[str, object]:
    cleaned = clean_text(text)
    nlp, has_lemmatizer = _load_nlp()
    document = nlp(cleaned)
    all_tokens = [token.text for token in document if not token.is_space and not token.is_punct]
    removed = [token for token in document if token.is_stop]
    kept = [token for token in document if not token.is_stop and not token.is_space and not token.is_punct]
    if has_lemmatizer:
        processed = [token.lemma_.casefold() for token in kept if token.lemma_.strip()]
        method = "spaCy en_core_web_sm lemmatization"
    else:
        processed = [token.text.casefold() for token in kept]
        method = "spaCy English tokenization; lemmatizer model unavailable"
    return {
        "original_text": text,
        "cleaned_text": cleaned,
        "tokens": all_tokens,
        "stopwords_removed": [token.text for token in removed],
        "processed_tokens": processed,
        "processed_text": " ".join(processed),
        "token_count": len(all_tokens),
        "processed_token_count": len(processed),
        "method": method,
        "lemmatized": has_lemmatizer,
    }
