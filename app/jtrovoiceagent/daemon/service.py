from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from jtrovoiceagent.audio.capture import MicrophoneRecorder
from jtrovoiceagent.core.config import AppConfig
from jtrovoiceagent.core.runtime import detect_session_info
from jtrovoiceagent.daemon.control import ControlServer
from jtrovoiceagent.services.pipeline import PipelineResult, SpeechPipeline


@dataclass(slots=True)
class AgentState:
    running: bool
    listening: bool
    session_type: str
    processed_utterances: int = 0
    last_bangla_text: str = ""
    last_english_text: str = ""
    last_error: str = ""
    last_injection_backend: str = ""


class VoiceAgentService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.logger = logging.getLogger("jtrovoiceagent.daemon.service")
        self.shutdown_event = threading.Event()
        self.listening_event = threading.Event()
        if config.daemon.start_listening:
            self.listening_event.set()

        session_info = detect_session_info()
        self.state = AgentState(
            running=True,
            listening=self.listening_event.is_set(),
            session_type=session_info.session_type,
        )
        self._state_lock = threading.Lock()

        self.state_dir = Path(config.daemon.state_dir)
        self.state_file = self.state_dir / "state.json"
        self.recorder = MicrophoneRecorder(config.audio)
        self.pipeline = SpeechPipeline(config)
        self.control_server = ControlServer(
            Path(config.daemon.control_socket_path),
            self.handle_control_command,
        )

    def run_forever(self) -> None:
        self._prepare_runtime()
        self.logger.info(
            "Starting voice agent session=%s listening=%s",
            self.state.session_type,
            self.state.listening,
        )
        self.pipeline.warmup()
        self.recorder.start()
        self.control_server.start()
        self._write_state()

        try:
            while not self.shutdown_event.is_set():
                if not self.listening_event.is_set():
                    self.shutdown_event.wait(self.config.daemon.idle_sleep_ms / 1000.0)
                    continue

                audio = self.recorder.capture_utterance(self.shutdown_event, self.listening_event)
                if audio is None:
                    continue

                try:
                    result = self.pipeline.process_utterance(audio)
                    if result is not None:
                        self._record_success(result)
                except Exception as exc:
                    self.logger.exception("Pipeline processing failed")
                    self._record_error(str(exc))
        finally:
            self._shutdown()

    def handle_control_command(self, command: str, args: dict[str, Any]) -> dict[str, Any]:
        normalized = command.strip().lower()
        if normalized == "status":
            return {"ok": True, "state": self._state_snapshot()}
        if normalized == "resume":
            self.listening_event.set()
            self.recorder.flush()
            self._update_listening(True)
            self.logger.info("Listening enabled")
            return {"ok": True, "state": self._state_snapshot()}
        if normalized == "pause":
            self.listening_event.clear()
            self.recorder.flush()
            self._update_listening(False)
            self.logger.info("Listening paused")
            return {"ok": True, "state": self._state_snapshot()}
        if normalized == "toggle":
            if self.listening_event.is_set():
                return self.handle_control_command("pause", args)
            return self.handle_control_command("resume", args)
        if normalized == "shutdown":
            self.shutdown_event.set()
            self.logger.info("Shutdown requested by control command")
            return {"ok": True, "state": self._state_snapshot()}
        raise ValueError(f"Unsupported control command: {command}")

    def _prepare_runtime(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        Path(self.config.stt.cache_dir).mkdir(parents=True, exist_ok=True)
        Path(self.config.stt.temp_dir).mkdir(parents=True, exist_ok=True)
        Path(self.config.translation.cache_dir).mkdir(parents=True, exist_ok=True)
        Path(self.config.logging.directory).mkdir(parents=True, exist_ok=True)

    def _record_success(self, result: PipelineResult) -> None:
        self.logger.info("Bangla: %s", result.bangla_text)
        self.logger.info("English: %s", result.english_text)
        with self._state_lock:
            self.state.processed_utterances += 1
            self.state.last_bangla_text = result.bangla_text
            self.state.last_english_text = result.english_text
            self.state.last_error = ""
            self.state.last_injection_backend = result.injection.backend
        self._write_state()

    def _record_error(self, message: str) -> None:
        with self._state_lock:
            self.state.last_error = message
        self._write_state()

    def _update_listening(self, listening: bool) -> None:
        with self._state_lock:
            self.state.listening = listening
        self._write_state()

    def _state_snapshot(self) -> dict[str, Any]:
        with self._state_lock:
            return asdict(self.state)

    def _write_state(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(
            json.dumps(self._state_snapshot(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _shutdown(self) -> None:
        self.logger.info("Stopping voice agent")
        with self._state_lock:
            self.state.running = False
            self.state.listening = self.listening_event.is_set()
        self._write_state()
        self.control_server.stop()
        self.recorder.stop()
