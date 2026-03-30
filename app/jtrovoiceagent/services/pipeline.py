from __future__ import annotations

import logging
from dataclasses import dataclass

from jtrovoiceagent.audio.capture import CapturedAudio
from jtrovoiceagent.core.config import AppConfig
from jtrovoiceagent.core.runtime import detect_session_info
from jtrovoiceagent.injection.base import InjectionResult
from jtrovoiceagent.injection.factory import create_text_injector
from jtrovoiceagent.stt.factory import create_stt_engine
from jtrovoiceagent.translation.factory import create_translator
from jtrovoiceagent.utils.text import normalize_bangla_text, normalize_english_text


@dataclass(slots=True)
class PipelineResult:
    bangla_text: str
    english_text: str
    transcription_backend: str
    translation_backend: str
    injection: InjectionResult


class SpeechPipeline:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.logger = logging.getLogger("jtrovoiceagent.services.pipeline")
        self.session_info = detect_session_info()
        self.stt_engine = create_stt_engine(config.stt)
        self.translator = create_translator(config.translation)
        self.injector = create_text_injector(config.injection, self.session_info)

    def warmup(self) -> None:
        self.stt_engine.warmup()
        self.translator.warmup()

    def process_utterance(self, audio: CapturedAudio) -> PipelineResult | None:
        transcription = self.stt_engine.transcribe(audio)
        bangla_text = normalize_bangla_text(transcription.text)
        if not bangla_text:
            self.logger.debug("Discarded empty transcription result")
            return None

        translation = self.translator.translate(bangla_text)
        english_text = normalize_english_text(
            translation.text,
            preserve_newlines=self.config.injection.preserve_newlines,
        )
        if not english_text:
            self.logger.debug("Discarded empty translation result")
            return None

        injection = self.injector.inject_text(english_text)
        return PipelineResult(
            bangla_text=bangla_text,
            english_text=english_text,
            transcription_backend=transcription.backend,
            translation_backend=translation.backend,
            injection=injection,
        )
