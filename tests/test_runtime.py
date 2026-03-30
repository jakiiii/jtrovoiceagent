from jtrovoiceagent.core.runtime import detect_session_info, resolve_compute_device


def test_detect_session_info_wayland() -> None:
    session = detect_session_info(
        {
            "XDG_SESSION_TYPE": "wayland",
            "WAYLAND_DISPLAY": "wayland-0",
        }
    )
    assert session.session_type == "wayland"


def test_detect_session_info_x11() -> None:
    session = detect_session_info(
        {
            "DISPLAY": ":0",
        }
    )
    assert session.session_type == "x11"


def test_resolve_compute_device_passthrough() -> None:
    assert resolve_compute_device("cpu") == "cpu"
