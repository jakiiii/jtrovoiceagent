#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

sudo apt update
sudo apt install -y \
  python3 \
  python3-venv \
  python3-dev \
  build-essential \
  libportaudio2 \
  portaudio19-dev \
  xdotool \
  ydotool

"$ROOT_DIR/scripts/setup_venv.sh"

cat <<'EOF'

Base setup complete.

Notes:
- On X11, xdotool usually works without extra privileges.
- On Wayland, ydotool requires ydotoold and access to /dev/uinput.
- If you want the agent to start at login, install the user service from systemd/jtrovoiceagent.service.
EOF
