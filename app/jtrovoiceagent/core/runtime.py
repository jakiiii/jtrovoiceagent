from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


@dataclass(slots=True)
class SessionInfo:
    session_type: str
    display: str | None
    wayland_display: str | None
    desktop: str | None


def detect_session_info(env: Mapping[str, str] | None = None) -> SessionInfo:
    source = env or os.environ
    session_type = (source.get("XDG_SESSION_TYPE") or "").strip().lower()
    display = source.get("DISPLAY")
    wayland_display = source.get("WAYLAND_DISPLAY")
    desktop = source.get("XDG_CURRENT_DESKTOP")

    if session_type == "wayland" or wayland_display:
        resolved = "wayland"
    elif session_type == "x11" or display:
        resolved = "x11"
    else:
        resolved = "unknown"

    return SessionInfo(
        session_type=resolved,
        display=display,
        wayland_display=wayland_display,
        desktop=desktop,
    )


def resolve_compute_device(preference: str) -> str:
    desired = preference.strip().lower()
    if desired != "auto":
        return desired

    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def has_uinput_access() -> bool:
    return os.access("/dev/uinput", os.R_OK | os.W_OK)
