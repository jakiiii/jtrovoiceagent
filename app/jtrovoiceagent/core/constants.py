from pathlib import Path

APP_NAME = "jtrovoiceagent"
DEFAULT_STATE_DIR = Path.home() / ".local" / "state" / APP_NAME
DEFAULT_SOCKET_PATH = DEFAULT_STATE_DIR / "control.sock"
DEFAULT_LOG_DIR = Path("logs")
