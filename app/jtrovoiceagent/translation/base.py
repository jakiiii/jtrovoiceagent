from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class TranslationResult:
    text: str
    backend: str


class TranslatorBackend(ABC):
    @abstractmethod
    def warmup(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def translate(self, text: str) -> TranslationResult:
        raise NotImplementedError


class IdentityTranslator(TranslatorBackend):
    def warmup(self) -> None:
        return None

    def translate(self, text: str) -> TranslationResult:
        return TranslationResult(text=text, backend="identity")
