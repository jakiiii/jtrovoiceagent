from __future__ import annotations

import logging
import queue
import threading
from collections import deque
from dataclasses import dataclass
from typing import Any

import numpy as np

from jtrovoiceagent.core.config import AudioConfig
from jtrovoiceagent.core.errors import AudioError, DependencyError


@dataclass(slots=True)
class CapturedAudio:
    samples: np.ndarray
    sample_rate: int

    @property
    def duration_seconds(self) -> float:
        return float(len(self.samples)) / float(self.sample_rate)


class MicrophoneRecorder:
    def __init__(self, config: AudioConfig) -> None:
        self.config = config
        self.logger = logging.getLogger("jtrovoiceagent.audio.capture")
        self._queue: queue.Queue[bytes] = queue.Queue(maxsize=config.queue_maxsize)
        self._stream: Any | None = None
        self._sd_module: Any | None = None
        self._blocksize = int(config.sample_rate * (config.block_duration_ms / 1000.0))

    def start(self) -> None:
        if self._stream is not None:
            return

        try:
            import sounddevice as sd
        except ImportError as exc:
            raise DependencyError("sounddevice is not installed") from exc

        self._sd_module = sd
        try:
            self._stream = sd.RawInputStream(
                samplerate=self.config.sample_rate,
                channels=self.config.channels,
                dtype="int16",
                blocksize=self._blocksize,
                device=self.config.device,
                callback=self._audio_callback,
            )
            self._stream.start()
        except Exception as exc:
            raise AudioError(f"Unable to start microphone stream: {exc}") from exc

    def stop(self) -> None:
        if self._stream is None:
            return
        try:
            self._stream.stop()
            self._stream.close()
        finally:
            self._stream = None
            self.flush()

    def flush(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                return

    def capture_utterance(
        self,
        shutdown_event: threading.Event,
        listening_event: threading.Event,
    ) -> CapturedAudio | None:
        if self._stream is None:
            raise AudioError("Microphone stream has not been started")

        speech_started = False
        speech_ms = 0
        silence_ms = 0
        total_ms = 0
        prefix_frames = deque(
            maxlen=max(1, self.config.speech_prefix_ms // self.config.block_duration_ms)
        )
        utterance_frames: list[np.ndarray] = []

        while not shutdown_event.is_set():
            if not listening_event.is_set():
                self.flush()
                return None

            try:
                raw_frame = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

            frame = np.frombuffer(raw_frame, dtype=np.int16).copy()
            frame_float = frame.astype(np.float32) / 32768.0
            energy = float(np.sqrt(np.mean(np.square(frame_float))))
            is_speech = energy >= self.config.speech_threshold

            if not speech_started:
                prefix_frames.append(frame)
                if is_speech:
                    speech_started = True
                    utterance_frames.extend(prefix_frames)
                    prefix_frames.clear()
                    speech_ms += self.config.block_duration_ms
                    total_ms += self.config.block_duration_ms
                continue

            utterance_frames.append(frame)
            total_ms += self.config.block_duration_ms

            if is_speech:
                speech_ms += self.config.block_duration_ms
                silence_ms = 0
            else:
                silence_ms += self.config.block_duration_ms

            if total_ms >= self.config.max_utterance_ms:
                self.logger.debug("Utterance capped at max duration")
                break

            if (
                speech_ms >= self.config.min_utterance_ms
                and silence_ms >= self.config.silence_duration_ms
            ):
                break

        if not utterance_frames or speech_ms < self.config.min_utterance_ms:
            return None

        combined = np.concatenate(utterance_frames).astype(np.float32) / 32768.0
        return CapturedAudio(samples=combined, sample_rate=self.config.sample_rate)

    def _audio_callback(
        self,
        indata: Any,
        frames: int,
        time_info: Any,
        status: Any,
    ) -> None:
        if status:
            self.logger.debug("Audio callback status: %s", status)

        payload = bytes(indata)
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(payload)
            except queue.Full:
                self.logger.warning("Audio queue is full; dropping frame")
