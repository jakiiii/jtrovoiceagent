from __future__ import annotations

import re

_MULTISPACE_RE = re.compile(r"\s+")
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,.;:!?])")
_BANGLA_SENTENCE_SPLIT_RE = re.compile(r"(?<=[।!?])\s+")
_EN_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def normalize_bangla_text(text: str) -> str:
    value = _MULTISPACE_RE.sub(" ", text.replace("\n", " ")).strip()
    return value.replace(" ।", "।")


def split_sentences_for_translation(text: str) -> list[str]:
    normalized = normalize_bangla_text(text)
    if not normalized:
        return []
    if "।" in normalized:
        parts = _BANGLA_SENTENCE_SPLIT_RE.split(normalized)
    else:
        parts = _EN_SENTENCE_SPLIT_RE.split(normalized)
    return [part.strip() for part in parts if part.strip()]


def normalize_english_text(text: str, preserve_newlines: bool = False) -> str:
    working = text.strip()
    if not preserve_newlines:
        working = working.replace("\n", " ")
        working = _MULTISPACE_RE.sub(" ", working)
    else:
        lines = [_MULTISPACE_RE.sub(" ", line).strip() for line in working.splitlines()]
        working = "\n".join(line for line in lines if line)
    working = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", working)
    return working.strip()
