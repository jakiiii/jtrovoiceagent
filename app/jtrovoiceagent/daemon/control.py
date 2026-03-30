from __future__ import annotations

import json
import os
import socket
import socketserver
import threading
from pathlib import Path
from typing import Any, Callable

from jtrovoiceagent.core.errors import ControlError


class _ThreadedUnixStreamServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        socket_path: str,
        command_handler: Callable[[str, dict[str, Any]], dict[str, Any]],
    ) -> None:
        self.command_handler = command_handler
        super().__init__(socket_path, _ControlRequestHandler)


class _ControlRequestHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        raw = self.rfile.readline().decode("utf-8").strip()
        if not raw:
            return
        try:
            payload = json.loads(raw)
            command = str(payload.get("command", ""))
            args = payload.get("args", {})
            if not isinstance(args, dict):
                raise ValueError("args must be an object")
            response = self.server.command_handler(command, args)
        except Exception as exc:
            response = {"ok": False, "error": str(exc)}
        self.wfile.write((json.dumps(response) + "\n").encode("utf-8"))


class ControlServer:
    def __init__(
        self,
        socket_path: Path,
        command_handler: Callable[[str, dict[str, Any]], dict[str, Any]],
    ) -> None:
        self.socket_path = socket_path
        self.command_handler = command_handler
        self._server: _ThreadedUnixStreamServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        if self.socket_path.exists():
            self.socket_path.unlink()
        self._server = _ThreadedUnixStreamServer(str(self.socket_path), self.command_handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self.socket_path.exists():
            self.socket_path.unlink()


def send_control_command(
    socket_path: Path,
    command: str,
    args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not socket_path.exists():
        raise ControlError(f"Control socket not found: {socket_path}")

    payload = json.dumps({"command": command, "args": args or {}}).encode("utf-8") + b"\n"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        try:
            client.connect(os.fspath(socket_path))
            client.sendall(payload)
            response = client.recv(65536)
        except OSError as exc:
            raise ControlError(f"Unable to talk to daemon: {exc}") from exc

    if not response:
        raise ControlError("Daemon returned an empty response")

    try:
        return json.loads(response.decode("utf-8").strip())
    except json.JSONDecodeError as exc:
        raise ControlError("Daemon returned invalid JSON") from exc
