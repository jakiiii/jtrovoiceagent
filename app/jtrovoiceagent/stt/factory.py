from jtrovoiceagent.core.config import STTConfig
from jtrovoiceagent.core.errors import ConfigurationError
from jtrovoiceagent.stt.base import STTEngine
from jtrovoiceagent.stt.faster_whisper_engine import FasterWhisperSTTEngine


def create_stt_engine(config: STTConfig) -> STTEngine:
    if config.backend == "faster-whisper":
        return FasterWhisperSTTEngine(config)
    raise ConfigurationError(f"Unsupported STT backend: {config.backend}")
