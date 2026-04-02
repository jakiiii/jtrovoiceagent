from __future__ import annotations

import logging
import wave
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import numpy as np

from jtrovoiceagent.audio.capture import CapturedAudio
from jtrovoiceagent.core.config import STTConfig
from jtrovoiceagent.core.errors import DependencyError
from jtrovoiceagent.core.runtime import resolve_compute_device
from jtrovoiceagent.stt.base import STTEngine, TranscriptionResult


class FasterWhisperSTTEngine(STTEngine):
    def __init__(self, config: STTConfig) -> None:
        self.config = config
        self.logger = logging.getLogger("jtrovoiceagent.stt.faster_whisper")
        self._model: Any | None = None
        self._device: str | None = None
        self._compute_type: str | None = None

    def warmup(self) -> None:
        self._get_model()

    def transcribe(self, audio: CapturedAudio) -> TranscriptionResult:
        model = self._get_model()
        temp_dir = Path(self.config.temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)

        with NamedTemporaryFile(
            suffix=".wav",
            dir=temp_dir,
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)

        try:
            _write_wave_file(temp_path, audio.samples, audio.sample_rate)
            segments, info = model.transcribe(
                str(temp_path),
                beam_size=self.config.beam_size,
                language=self.config.language,
                task=self.config.task,
                vad_filter=self.config.vad_filter,
                vad_parameters={"min_silence_duration_ms": self.config.vad_min_silence_ms},
                condition_on_previous_text=False,
            )
            text = " ".join(segment.text.strip() for segment in segments).strip()
            return TranscriptionResult(
                text=text,
                language=getattr(info, "language", None),
                language_probability=getattr(info, "language_probability", None),
                backend="faster-whisper",
            )
        finally:
            temp_path.unlink(missing_ok=True)

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise DependencyError("faster-whisper is not installed") from exc

        model_ref = self.config.local_model_path or self.config.model_id
        device = resolve_compute_device(self.config.device)
        compute_type = (
            self.config.compute_type_cuda if device == "cuda" else self.config.compute_type_cpu
        )
        cache_dir = Path(self.config.cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)

        kwargs: dict[str, Any] = {
            "device": device,
            "compute_type": compute_type,
            "download_root": str(cache_dir),
        }
        if self.config.cpu_threads:
            kwargs["cpu_threads"] = self.config.cpu_threads

        self.logger.info(
            "Loading faster-whisper model=%s device=%s compute_type=%s",
            model_ref,
            device,
            compute_type,
        )
        self._model = WhisperModel(model_ref, **kwargs)
        self._device = device
        self._compute_type = compute_type
        self.logger.info(
            "STT runtime ready model=%s effective_device=%s compute_type=%s",
            model_ref,
            self._device,
            self._compute_type,
        )
        return self._model


def _write_wave_file(path: Path, samples: np.ndarray, sample_rate: int) -> None:
    pcm = np.clip(samples, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm.tobytes())
