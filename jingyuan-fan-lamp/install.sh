#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_CONFIG="$SCRIPT_DIR/config.local.py"
EXAMPLE_CONFIG="$SCRIPT_DIR/config.example.py"
TEMPLATE="$SCRIPT_DIR/launchd/com.jingyuan.fanlamp.bridge.plist.template"
LABEL="com.jingyuan.fanlamp.bridge"
PLIST_DEST="$HOME/Library/LaunchAgents/${LABEL}.plist"
DOMAIN="gui/$(id -u)"

if [[ ! -f "$LOCAL_CONFIG" ]]; then
  cp "$EXAMPLE_CONFIG" "$LOCAL_CONFIG"
  echo "Created $LOCAL_CONFIG from example."
  echo "Edit WEBHOOK_TOKEN and QUEUE_DEQUEUE_TOKEN, then run ./install.sh again."
  exit 1
fi

CONFIG_VALUES="$(
  python3 - "$LOCAL_CONFIG" <<'PY'
import importlib.util
import sys
from pathlib import Path

path = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("config_local", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print(module.STATE_DIR)
PY
)"
STATE_DIR="$(echo "$CONFIG_VALUES" | sed -n '1p')"

mkdir -p "$STATE_DIR" "$HOME/Library/LaunchAgents"

PYTHON3="$(command -v python3)"
CAFFEINATE="$(command -v caffeinate)"
BRIDGE_SERVER="$SCRIPT_DIR/bridge_server.py"
LOG_PATH="$STATE_DIR/bridge.log"

if [[ ! -x "$PYTHON3" ]]; then
  echo "python3 not found" >&2
  exit 1
fi

if [[ ! -x "$CAFFEINATE" ]]; then
  echo "caffeinate not found" >&2
  exit 1
fi

sed \
  -e "s|__CAFFEINATE__|$CAFFEINATE|g" \
  -e "s|__PYTHON3__|$PYTHON3|g" \
  -e "s|__BRIDGE_SERVER__|$BRIDGE_SERVER|g" \
  -e "s|__WORKING_DIR__|$SCRIPT_DIR|g" \
  -e "s|__LOG_PATH__|$LOG_PATH|g" \
  "$TEMPLATE" > "$PLIST_DEST"

chmod +x "$SCRIPT_DIR/bin/fan-bridge"
chmod +x "$SCRIPT_DIR/bridge_server.py"
chmod +x "$SCRIPT_DIR/fan_ble.py"
chmod +x "$SCRIPT_DIR/webhook_server.py"
chmod +x "$SCRIPT_DIR/fan_ble.swift"

if launchctl print "${DOMAIN}/${LABEL}" >/dev/null 2>&1; then
  launchctl bootout "${DOMAIN}" "$PLIST_DEST" 2>/dev/null || true
fi

launchctl bootstrap "${DOMAIN}" "$PLIST_DEST"

BIN_LINK="$HOME/bin/fan-bridge"
mkdir -p "$HOME/bin"
ln -sf "$SCRIPT_DIR/bin/fan-bridge" "$BIN_LINK"

echo "Installed LaunchAgent: $PLIST_DEST"
echo "CLI: $BIN_LINK fan-on | ./bin/fan-bridge start"
echo "Logs: $LOG_PATH"
echo "Health: curl http://127.0.0.1:8787/health"
