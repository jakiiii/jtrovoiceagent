from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from jtrovoiceagent.core.config import TranslationConfig
from jtrovoiceagent.core.errors import DependencyError
from jtrovoiceagent.core.runtime import resolve_compute_device
from jtrovoiceagent.translation.base import TranslationResult, TranslatorBackend
from jtrovoiceagent.utils.text import normalize_bangla_text, normalize_english_text, split_sentences_for_translation


class TransformersNllbTranslator(TranslatorBackend):
    def __init__(self, config: TranslationConfig) -> None:
        self.config = config
        self.logger = logging.getLogger("jtrovoiceagent.translation.nllb")
        self._torch: Any | None = None
        self._model: Any | None = None
        self._tokenizer: Any | None = None
        self._device: str | None = None

    def warmup(self) -> None:
        self._ensure_loaded()

    def translate(self, text: str) -> TranslationResult:
        normalized = normalize_bangla_text(text)
        if not normalized:
            return TranslationResult(text="", backend="nllb")

        self._ensure_loaded()
        pieces = split_sentences_for_translation(normalized) or [normalized]
        translated_parts = [self._translate_segment(item) for item in pieces]
        translated = normalize_english_text(" ".join(part for part in translated_parts if part))
        return TranslationResult(text=translated, backend="nllb")

    def _translate_segment(self, text: str) -> str:
        assert self._tokenizer is not None
        assert self._model is not None
        assert self._torch is not None
        assert self._device is not None

        encoded = self._tokenizer(text, return_tensors="pt")
        encoded = {key: value.to(self._device) for key, value in encoded.items()}
        forced_bos_token_id = self._tokenizer.convert_tokens_to_ids(self.config.target_lang)
        generated = self._model.generate(
            **encoded,
            forced_bos_token_id=forced_bos_token_id,
            max_new_tokens=self.config.max_new_tokens,
            num_beams=self.config.num_beams,
        )
        decoded = self._tokenizer.batch_decode(generated, skip_special_tokens=True)
        return decoded[0].strip() if decoded else ""

    def _ensure_loaded(self) -> None:
        if self._model is not None and self._tokenizer is not None:
            return

        try:
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError as exc:
            raise DependencyError("transformers, sentencepiece, and torch are required") from exc

        self._torch = torch
        self._device = resolve_compute_device(self.config.device)
        cache_dir = Path(self.config.cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info(
            "Loading translation model=%s device=%s",
            self.config.model_id,
            self._device,
        )
        self._tokenizer = AutoTokenizer.from_pretrained(
            self.config.model_id,
            cache_dir=str(cache_dir),
            src_lang=self.config.source_lang,
        )
        if hasattr(self._tokenizer, "src_lang"):
            self._tokenizer.src_lang = self.config.source_lang
        if hasattr(self._tokenizer, "tgt_lang"):
            self._tokenizer.tgt_lang = self.config.target_lang
        self._model = AutoModelForSeq2SeqLM.from_pretrained(
            self.config.model_id,
            cache_dir=str(cache_dir),
        )
        self._model.to(self._device)
        self._model.eval()
