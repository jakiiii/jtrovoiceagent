from __future__ import annotations

from dataclasses import dataclass

from jtrovoiceagent.core.errors import AudioError, DependencyError


@dataclass(slots=True)
class AudioDevice:
    index: int
    name: str
    max_input_channels: int
    default_sample_rate: float


def list_input_devices() -> list[AudioDevice]:
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise DependencyError("sounddevice is not installed") from exc

    try:
        raw_devices = sd.query_devices()
    except Exception as exc:
        raise AudioError(f"Unable to query audio devices: {exc}") from exc

    devices: list[AudioDevice] = []
    for index, item in enumerate(raw_devices):
        if int(item.get("max_input_channels", 0)) <= 0:
            continue
        devices.append(
            AudioDevice(
                index=index,
                name=str(item.get("name")),
                max_input_channels=int(item.get("max_input_channels", 0)),
                default_sample_rate=float(item.get("default_samplerate", 0.0)),
            )
        )
    return devices
