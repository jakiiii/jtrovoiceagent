from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import ModuleType

from jtrovoiceagent.core.config import TranslationConfig
from jtrovoiceagent.translation.transformers_nllb import TransformersNllbTranslator


def test_translation_falls_back_to_cpu_after_cuda_oom(
    monkeypatch,
    tmp_path: Path,
    caplog,
) -> None:
    move_calls: list[str] = []
    cuda_cleanup_calls: list[str] = []

    class FakeOOM(RuntimeError):
        pass

    class FakeCuda:
        @staticmethod
        def is_available() -> bool:
            return True

        @staticmethod
        def empty_cache() -> None:
            cuda_cleanup_calls.append("empty_cache")

        @staticmethod
        def ipc_collect() -> None:
            cuda_cleanup_calls.append("ipc_collect")

    fake_torch = ModuleType("torch")
    fake_torch.OutOfMemoryError = FakeOOM
    fake_torch.cuda = FakeCuda

    class FakeTokenizer:
        src_lang: str | None = None
        tgt_lang: str | None = None

        def __call__(self, text: str, return_tensors: str = "pt") -> dict[str, object]:
            return {}

        def convert_tokens_to_ids(self, token: str) -> int:
            return 1

        def batch_decode(self, generated: object, skip_special_tokens: bool = True) -> list[str]:
            return ["hello"]

    class FakeAutoTokenizer:
        @staticmethod
        def from_pretrained(*args, **kwargs) -> FakeTokenizer:
            return FakeTokenizer()

    class FakeModel:
        def to(self, device: str) -> "FakeModel":
            move_calls.append(device)
            if device == "cuda":
                raise FakeOOM("CUDA out of memory")
            return self

        def eval(self) -> "FakeModel":
            return self

        def generate(self, **kwargs) -> list[list[int]]:
            return [[1]]

    class FakeAutoModelForSeq2SeqLM:
        @staticmethod
        def from_pretrained(*args, **kwargs) -> FakeModel:
            return FakeModel()

    fake_transformers = ModuleType("transformers")
    fake_transformers.AutoModelForSeq2SeqLM = FakeAutoModelForSeq2SeqLM
    fake_transformers.AutoTokenizer = FakeAutoTokenizer

    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    config = TranslationConfig(
        device="cuda",
        fallback_device="cpu",
        cache_dir=tmp_path,
    )
    translator = TransformersNllbTranslator(config)

    with caplog.at_level(logging.WARNING):
        translator.warmup()

    assert move_calls == ["cuda", "cpu"]
    assert translator._device == "cpu"
    assert translator._fallback_used is True
    assert cuda_cleanup_calls
    assert "falling back to cpu" in caplog.text.lower()
