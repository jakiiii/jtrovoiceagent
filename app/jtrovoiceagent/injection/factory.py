from __future__ import annotations

import logging

from jtrovoiceagent.core.config import InjectionConfig
from jtrovoiceagent.core.errors import InjectionError
from jtrovoiceagent.core.runtime import SessionInfo, detect_session_info, has_uinput_access
from jtrovoiceagent.injection.base import TextInjector
from jtrovoiceagent.injection.command_injectors import DryRunInjector, XdotoolInjector, YdotoolInjector
from jtrovoiceagent.utils.command import command_exists


def create_text_injector(
    config: InjectionConfig,
    session_info: SessionInfo | None = None,
) -> TextInjector:
    logger = logging.getLogger("jtrovoiceagent.injection.factory")
    session = session_info or detect_session_info()

    if config.dry_run or config.backend == "dry-run":
        return DryRunInjector()

    backend = config.backend.lower()

    if backend == "xdotool":
        if command_exists(config.xdotool_command):
            return XdotoolInjector(config.xdotool_command, config.typing_delay_ms)
    elif backend == "ydotool":
        if command_exists(config.ydotool_command) and _ydotool_ready(session, logger):
            return YdotoolInjector(
                config.ydotool_command,
                config.typing_delay_ms,
                config.ydotool_socket,
            )
    elif backend == "auto":
        candidates = _auto_candidate_order(session)
        for candidate in candidates:
            if candidate == "xdotool" and command_exists(config.xdotool_command):
                return XdotoolInjector(config.xdotool_command, config.typing_delay_ms)
            if candidate == "ydotool" and command_exists(config.ydotool_command):
                if _ydotool_ready(session, logger):
                    return YdotoolInjector(
                        config.ydotool_command,
                        config.typing_delay_ms,
                        config.ydotool_socket,
                    )

    if config.fallback_to_dry_run:
        logger.warning(
            "No supported injector available for session=%s. Falling back to dry-run.",
            session.session_type,
        )
        return DryRunInjector()

    raise InjectionError(
        f"No supported injector available for session={session.session_type}. "
        f"backend={config.backend}"
    )


def _auto_candidate_order(session: SessionInfo) -> list[str]:
    if session.session_type == "x11":
        return ["xdotool", "ydotool"]
    if session.session_type == "wayland":
        return ["ydotool", "xdotool"]
    return ["xdotool", "ydotool"]


def _ydotool_ready(session: SessionInfo, logger: logging.Logger) -> bool:
    if session.session_type == "wayland" and not has_uinput_access():
        logger.warning("Wayland detected, but /dev/uinput is not writable for ydotool")
        return False
    return True
