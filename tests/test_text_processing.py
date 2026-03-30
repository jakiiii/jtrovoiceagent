from jtrovoiceagent.utils.text import (
    normalize_bangla_text,
    normalize_english_text,
    split_sentences_for_translation,
)


def test_normalize_bangla_text() -> None:
    assert normalize_bangla_text("আমি  ভালো  আছি ।") == "আমি ভালো আছি।"


def test_split_sentences_for_translation() -> None:
    assert split_sentences_for_translation("আমি ভালো আছি। তুমি কেমন আছো?") == [
        "আমি ভালো আছি।",
        "তুমি কেমন আছো?",
    ]


def test_normalize_english_text() -> None:
    assert normalize_english_text("Hello ,   world !") == "Hello, world!"
