from __future__ import annotations

import argparse
import json
from pathlib import Path

from jtrovoiceagent.audio.devices import list_input_devices
from jtrovoiceagent.core.config import AppConfig, load_config
from jtrovoiceagent.core.logging import configure_logging
from jtrovoiceagent.core.runtime import detect_session_info, has_uinput_access, resolve_compute_device
from jtrovoiceagent.daemon.control import send_control_command
from jtrovoiceagent.injection.factory import create_text_injector
from jtrovoiceagent.utils.command import command_exists


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="voice-agent")
    parser.add_argument("--config", default="configs/config.example.yaml")
    parser.add_argument("--debug", action="store_true")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("run", help="Run the local voice agent daemon")
    subparsers.add_parser("devices", help="List microphone input devices")
    subparsers.add_parser("doctor", help="Show runtime compatibility info")

    control_parser = subparsers.add_parser("control", help="Send a control command to the daemon")
    control_parser.add_argument("action", choices=["status", "pause", "resume", "toggle", "shutdown"])

    models_parser = subparsers.add_parser("models", help="Warm local model caches")
    models_subparsers = models_parser.add_subparsers(dest="models_command", required=True)
    models_subparsers.add_parser("pull", help="Download/load configured local models")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_runtime_config(args.config, args.debug)
    configure_logging(config.logging)

    if args.command == "run":
        from jtrovoiceagent.daemon.service import VoiceAgentService

        service = VoiceAgentService(config)
        service.run_forever()
        return 0

    if args.command == "devices":
        _print_devices()
        return 0

    if args.command == "doctor":
        _print_doctor(config)
        return 0

    if args.command == "control":
        response = send_control_command(Path(config.daemon.control_socket_path), args.action)
        print(json.dumps(response, ensure_ascii=False, indent=2))
        return 0 if response.get("ok") else 1

    if args.command == "models" and args.models_command == "pull":
        from jtrovoiceagent.services.pipeline import SpeechPipeline

        pipeline = SpeechPipeline(config)
        pipeline.warmup()
        print("Models loaded successfully")
        return 0

    parser.error("Unsupported command")
    return 2


def load_runtime_config(config_path: str, debug: bool) -> AppConfig:
    config = load_config(config_path)
    if debug:
        config.logging.level = "DEBUG"
    return config


def _print_devices() -> None:
    for device in list_input_devices():
        print(
            f"{device.index}: {device.name} | "
            f"inputs={device.max_input_channels} | "
            f"default_sample_rate={device.default_sample_rate:.0f}"
        )


def _print_doctor(config: AppConfig) -> None:
    session = detect_session_info()
    injector = create_text_injector(config.injection, session)
    status = {
        "session_type": session.session_type,
        "display": session.display,
        "wayland_display": session.wayland_display,
        "desktop": session.desktop,
        "stt_device": resolve_compute_device(config.stt.device),
        "translation_device": resolve_compute_device(config.translation.device),
        "xdotool_available": command_exists(config.injection.xdotool_command),
        "ydotool_available": command_exists(config.injection.ydotool_command),
        "uinput_access": has_uinput_access(),
        "selected_injector": injector.__class__.__name__,
    }
    print(json.dumps(status, ensure_ascii=False, indent=2))
