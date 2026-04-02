from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from jtrovoiceagent.core.constants import DEFAULT_LOG_DIR, DEFAULT_SOCKET_PATH, DEFAULT_STATE_DIR
from jtrovoiceagent.core.errors import ConfigurationError


PathLike = str | Path


@dataclass(slots=True)
class AudioConfig:
    device: str | int | None = None
    sample_rate: int = 16000
    channels: int = 1
    block_duration_ms: int = 100
    speech_threshold: float = 0.015
    speech_prefix_ms: int = 300
    silence_duration_ms: int = 900
    min_utterance_ms: int = 700
    max_utterance_ms: int = 12000
    queue_maxsize: int = 256


@dataclass(slots=True)
class STTConfig:
    backend: str = "faster-whisper"
    model_id: str = "medium"
    local_model_path: str | None = None
    language: str = "bn"
    task: str = "transcribe"
    beam_size: int = 5
    vad_filter: bool = True
    vad_min_silence_ms: int = 500
    device: str = "auto"
    compute_type_cpu: str = "int8"
    compute_type_cuda: str = "float16"
    cpu_threads: int | None = None
    cache_dir: PathLike = Path("models/cache/stt")
    temp_dir: PathLike = Path("models/cache/tmp")


@dataclass(slots=True)
class TranslationConfig:
    enabled: bool = True
    backend: str = "nllb"
    model_id: str = "facebook/nllb-200-distilled-600M"
    source_lang: str = "ben_Beng"
    target_lang: str = "eng_Latn"
    device: str = "cpu"
    fallback_device: str = "cpu"
    force_cpu: bool = False
    max_new_tokens: int = 256
    num_beams: int = 4
    cache_dir: PathLike = Path("models/cache/translation")


@dataclass(slots=True)
class InjectionConfig:
    backend: str = "auto"
    xdotool_command: str = "xdotool"
    ydotool_command: str = "ydotool"
    ydotool_socket: str | None = None
    typing_delay_ms: int = 8
    dry_run: bool = False
    fallback_to_dry_run: bool = True
    preserve_newlines: bool = False


@dataclass(slots=True)
class DaemonConfig:
    control_socket_path: PathLike = DEFAULT_SOCKET_PATH
    state_dir: PathLike = DEFAULT_STATE_DIR
    start_listening: bool = False
    idle_sleep_ms: int = 200


@dataclass(slots=True)
class LoggingConfig:
    level: str = "INFO"
    directory: PathLike = DEFAULT_LOG_DIR
    filename: str = "agent.log"
    rotate_bytes: int = 1_048_576
    backups: int = 5
    console: bool = True


@dataclass(slots=True)
class AppConfig:
    app_name: str = "jtrovoiceagent"
    audio: AudioConfig = field(default_factory=AudioConfig)
    stt: STTConfig = field(default_factory=STTConfig)
    translation: TranslationConfig = field(default_factory=TranslationConfig)
    injection: InjectionConfig = field(default_factory=InjectionConfig)
    daemon: DaemonConfig = field(default_factory=DaemonConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    def resolve_paths(self, base_dir: Path) -> None:
        self.stt.cache_dir = _resolve_path(self.stt.cache_dir, base_dir)
        self.stt.temp_dir = _resolve_path(self.stt.temp_dir, base_dir)
        self.translation.cache_dir = _resolve_path(self.translation.cache_dir, base_dir)
        self.daemon.control_socket_path = _resolve_path(self.daemon.control_socket_path, base_dir)
        self.daemon.state_dir = _resolve_path(self.daemon.state_dir, base_dir)
        self.logging.directory = _resolve_path(self.logging.directory, base_dir)


def load_config(path: str | Path | None = None) -> AppConfig:
    config_path = Path(path).expanduser().resolve() if path else None
    raw_data = _read_yaml(config_path) if config_path else {}
    if raw_data is None:
        raw_data = {}
    if not isinstance(raw_data, dict):
        raise ConfigurationError("Top-level config must be a mapping")

    config = AppConfig(
        app_name=raw_data.get("app_name", "jtrovoiceagent"),
        audio=_build_dataclass(AudioConfig, raw_data.get("audio", {})),
        stt=_build_dataclass(STTConfig, raw_data.get("stt", {})),
        translation=_build_dataclass(TranslationConfig, raw_data.get("translation", {})),
        injection=_build_dataclass(InjectionConfig, raw_data.get("injection", {})),
        daemon=_build_dataclass(DaemonConfig, raw_data.get("daemon", {})),
        logging=_build_dataclass(LoggingConfig, raw_data.get("logging", {})),
    )

    base_dir = config_path.parent if config_path else Path.cwd()
    config.resolve_paths(base_dir)
    validate_config(config)
    return config


def validate_config(config: AppConfig) -> None:
    if config.audio.sample_rate <= 0:
        raise ConfigurationError("audio.sample_rate must be greater than 0")
    if config.audio.channels != 1:
        raise ConfigurationError("Version-01 supports mono microphone capture only")
    if config.audio.block_duration_ms <= 0:
        raise ConfigurationError("audio.block_duration_ms must be greater than 0")
    if config.audio.min_utterance_ms <= 0 or config.audio.max_utterance_ms <= 0:
        raise ConfigurationError("audio utterance limits must be greater than 0")
    if config.audio.min_utterance_ms >= config.audio.max_utterance_ms:
        raise ConfigurationError("audio.min_utterance_ms must be less than audio.max_utterance_ms")
    if config.audio.speech_threshold <= 0:
        raise ConfigurationError("audio.speech_threshold must be greater than 0")
    if config.stt.backend != "faster-whisper":
        raise ConfigurationError(f"Unsupported STT backend: {config.stt.backend}")
    if config.stt.device not in {"auto", "cpu", "cuda"}:
        raise ConfigurationError(f"Unsupported STT device: {config.stt.device}")
    if config.translation.enabled and config.translation.backend not in {"nllb", "identity"}:
        raise ConfigurationError(f"Unsupported translation backend: {config.translation.backend}")
    if config.translation.device not in {"auto", "cpu", "cuda"}:
        raise ConfigurationError(f"Unsupported translation device: {config.translation.device}")
    if config.translation.fallback_device not in {"cpu", "cuda"}:
        raise ConfigurationError(
            f"Unsupported translation.fallback_device: {config.translation.fallback_device}"
        )
    if config.injection.backend not in {"auto", "xdotool", "ydotool", "dry-run"}:
        raise ConfigurationError(f"Unsupported injection backend: {config.injection.backend}")


def _read_yaml(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        raise ConfigurationError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _build_dataclass(cls: type[Any], source: dict[str, Any]) -> Any:
    if source is None:
        return cls()
    if not isinstance(source, dict):
        raise ConfigurationError(f"Expected mapping for {cls.__name__}")
    field_names = {item.name for item in cls.__dataclass_fields__.values()}
    unknown = sorted(set(source) - field_names)
    if unknown:
        raise ConfigurationError(f"Unknown config keys for {cls.__name__}: {', '.join(unknown)}")
    return cls(**source)


def _resolve_path(value: PathLike, base_dir: Path) -> Path:
    path = Path(os.path.expandvars(str(value))).expanduser()
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return path
