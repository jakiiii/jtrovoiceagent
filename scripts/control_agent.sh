#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACTION="${1:-status}"
CONFIG_PATH="${2:-$ROOT_DIR/configs/config.example.yaml}"

source "$ROOT_DIR/.venv/bin/activate"
exec voice-agent --config "$CONFIG_PATH" control "$ACTION"
