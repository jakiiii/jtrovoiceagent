from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from jtrovoiceagent.audio.capture import CapturedAudio


@dataclass(slots=True)
class TranscriptionResult:
    text: str
    language: str | None
    language_probability: float | None
    backend: str


class STTEngine(ABC):
    @abstractmethod
    def warmup(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def transcribe(self, audio: CapturedAudio) -> TranscriptionResult:
        raise NotImplementedError
