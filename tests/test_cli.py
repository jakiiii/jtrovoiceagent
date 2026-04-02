from __future__ import annotations

import shlex
from pathlib import Path
from types import SimpleNamespace

from jtrovoiceagent.cli.main import main
from jtrovoiceagent.core.errors import ControlError


def test_control_command_reports_missing_daemon(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    config_path = tmp_path / "config with spaces.yaml"
    config = SimpleNamespace(
        daemon=SimpleNamespace(control_socket_path=tmp_path / "control.sock"),
        logging=SimpleNamespace(),
    )

    monkeypatch.setattr("jtrovoiceagent.cli.main.load_runtime_config", lambda *_: config)
    monkeypatch.setattr("jtrovoiceagent.cli.main.configure_logging", lambda *_: None)
    monkeypatch.setattr(
        "jtrovoiceagent.cli.main.send_control_command",
        lambda socket_path, action: (_ for _ in ()).throw(
            ControlError(f"Control socket not found: {socket_path}")
        ),
    )

    exit_code = main(["--config", str(config_path), "control", "status"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Control socket not found" in captured.err
    assert (
        f"voice-agent --config {shlex.quote(str(config_path))} run"
        in captured.err
    )
