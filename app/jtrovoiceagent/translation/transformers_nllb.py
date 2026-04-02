from __future__ import annotations

import logging
import os
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
        self._requested_device: str | None = None
        self._fallback_used = False

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

        try:
            encoded = self._tokenizer(text, return_tensors="pt")
            encoded = {key: value.to(self._device) for key, value in encoded.items()}
            forced_bos_token_id = self._tokenizer.convert_tokens_to_ids(self.config.target_lang)
            generated = self._model.generate(
                **encoded,
                forced_bos_token_id=forced_bos_token_id,
                max_new_tokens=self.config.max_new_tokens,
                num_beams=self.config.num_beams,
            )
        except Exception as exc:
            if self._should_retry_on_cpu(exc):
                self._fallback_to_device("translation", exc)
                return self._translate_segment(text)
            raise
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
        self._requested_device = self._resolve_requested_device()
        cache_dir = Path(self.config.cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info(
            "Loading translation model=%s requested_device=%s fallback_device=%s force_cpu=%s",
            self.config.model_id,
            self._requested_device,
            self.config.fallback_device,
            self.config.force_cpu,
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
        try:
            self._load_model(self._requested_device)
        except Exception as exc:
            if self._should_retry_on_cpu(exc, attempted_device=self._requested_device):
                self._fallback_to_device("startup", exc)
            else:
                raise
        self.logger.info(
            "Translation runtime ready model=%s requested_device=%s effective_device=%s fallback_used=%s",
            self.config.model_id,
            self._requested_device,
            self._device,
            self._fallback_used,
        )

    def _resolve_requested_device(self) -> str:
        if self.config.force_cpu:
            return "cpu"
        return resolve_compute_device(self.config.device)

    def _load_model(self, target_device: str) -> None:
        from transformers import AutoModelForSeq2SeqLM

        model: Any | None = None
        previous_disable_conversion = os.environ.get("DISABLE_SAFETENSORS_CONVERSION")
        os.environ["DISABLE_SAFETENSORS_CONVERSION"] = "1"
        try:
            model = AutoModelForSeq2SeqLM.from_pretrained(
                self.config.model_id,
                cache_dir=str(self.config.cache_dir),
                use_safetensors=False,
            )
            model.to(target_device)
            model.eval()
        except Exception:
            if model is not None:
                del model
            self._clear_cuda_memory()
            raise
        finally:
            if previous_disable_conversion is None:
                os.environ.pop("DISABLE_SAFETENSORS_CONVERSION", None)
            else:
                os.environ["DISABLE_SAFETENSORS_CONVERSION"] = previous_disable_conversion

        self._model = model
        self._device = target_device

    def _should_retry_on_cpu(
        self,
        exc: Exception,
        attempted_device: str | None = None,
    ) -> bool:
        device = attempted_device or self._device
        if device != "cuda" or self.config.fallback_device == device:
            return False
        return self._is_cuda_oom(exc)

    def _fallback_to_device(self, phase: str, exc: Exception) -> None:
        fallback_device = self.config.fallback_device
        self.logger.warning(
            "Translation model=%s hit CUDA OOM during %s on device=%s; "
            "clearing CUDA cache and falling back to %s. error=%s",
            self.config.model_id,
            phase,
            self._device or self._requested_device,
            fallback_device,
            exc,
        )
        self._fallback_used = True
        self._teardown_model()
        self._clear_cuda_memory()
        self._load_model(fallback_device)
        self.logger.info(
            "Translation runtime recovered model=%s requested_device=%s effective_device=%s fallback_used=%s",
            self.config.model_id,
            self._requested_device,
            self._device,
            self._fallback_used,
        )

    def _teardown_model(self) -> None:
        if self._model is None:
            return
        model = self._model
        self._model = None
        self._device = None
        del model

    def _clear_cuda_memory(self) -> None:
        if self._torch is None:
            return
        cuda = getattr(self._torch, "cuda", None)
        if cuda is None or not cuda.is_available():
            return
        try:
            cuda.empty_cache()
        except Exception:
            return
        ipc_collect = getattr(cuda, "ipc_collect", None)
        if callable(ipc_collect):
            try:
                ipc_collect()
            except Exception:
                return

    def _is_cuda_oom(self, exc: Exception) -> bool:
        if self._torch is not None:
            oom_type = getattr(self._torch, "OutOfMemoryError", None)
            if oom_type is not None and isinstance(exc, oom_type):
                return True
        message = str(exc).lower()
        return "cuda out of memory" in message or "cuda error: out of memory" in message
