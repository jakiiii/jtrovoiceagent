from __future__ import annotations

import logging
import os
import subprocess
import time

from jtrovoiceagent.core.errors import InjectionError
from jtrovoiceagent.injection.base import InjectionResult, TextInjector


class DryRunInjector(TextInjector):
    def __init__(self) -> None:
        self.logger = logging.getLogger("jtrovoiceagent.injection.dry_run")

    def inject_text(self, text: str) -> InjectionResult:
        self.logger.info("DRY RUN OUTPUT: %s", text)
        return InjectionResult(text=text, backend="dry-run", dry_run=True)


class XdotoolInjector(TextInjector):
    def __init__(self, command: str, delay_ms: int) -> None:
        self.command = command
        self.delay_ms = delay_ms
        self.logger = logging.getLogger("jtrovoiceagent.injection.xdotool")

    def inject_text(self, text: str) -> InjectionResult:
        try:
            subprocess.run(
                [self.command, "getwindowfocus"],
                capture_output=True,
                text=True,
                check=True,
            )
            self._type_text(text)
            return InjectionResult(text=text, backend="xdotool", dry_run=False)
        except subprocess.CalledProcessError as exc:
            raise InjectionError(f"xdotool injection failed: {exc.stderr.strip()}") from exc

    def _type_text(self, text: str) -> None:
        lines = text.splitlines() or [text]
        for index, line in enumerate(lines):
            subprocess.run(
                [
                    self.command,
                    "type",
                    "--clearmodifiers",
                    "--delay",
                    str(self.delay_ms),
                    line,
                ],
                check=True,
            )
            if index < len(lines) - 1:
                subprocess.run([self.command, "key", "Return"], check=True)


class YdotoolInjector(TextInjector):
    def __init__(
        self,
        command: str,
        delay_ms: int,
        socket_path: str | None = None,
    ) -> None:
        self.command = command
        self.delay_ms = delay_ms
        self.socket_path = socket_path
        self.logger = logging.getLogger("jtrovoiceagent.injection.ydotool")

    def inject_text(self, text: str) -> InjectionResult:
        try:
            self._type_text(text)
            return InjectionResult(text=text, backend="ydotool", dry_run=False)
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() if exc.stderr else str(exc)
            raise InjectionError(f"ydotool injection failed: {stderr}") from exc

    def _type_text(self, text: str) -> None:
        env = None
        if self.socket_path:
            env = dict(os.environ)
            env["YDOTOOL_SOCKET"] = self.socket_path

        lines = text.splitlines() or [text]
        for index, line in enumerate(lines):
            subprocess.run(
                [self.command, "type", line],
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            if index < len(lines) - 1:
                time.sleep(self.delay_ms / 1000.0)
                subprocess.run(
                    [self.command, "key", "28:1", "28:0"],
                    env=env,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                time.sleep(self.delay_ms / 1000.0)
