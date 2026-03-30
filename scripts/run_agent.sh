#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_PATH="${1:-$ROOT_DIR/configs/config.example.yaml}"

source "$ROOT_DIR/.venv/bin/activate"
exec voice-agent --config "$CONFIG_PATH" run
