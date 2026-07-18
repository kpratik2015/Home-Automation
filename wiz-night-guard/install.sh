#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_CONFIG="$SCRIPT_DIR/config.local.py"
EXAMPLE_CONFIG="$SCRIPT_DIR/config.example.py"
TEMPLATE="$SCRIPT_DIR/launchd/com.wiz.nightguard.plist.template"
LABEL="com.wiz.nightguard"
PLIST_DEST="$HOME/Library/LaunchAgents/${LABEL}.plist"
DOMAIN="gui/$(id -u)"

if [[ ! -f "$LOCAL_CONFIG" ]]; then
  cp "$EXAMPLE_CONFIG" "$LOCAL_CONFIG"
  echo "Created $LOCAL_CONFIG from example."
  echo "Edit BULB_IP and schedule, then run ./install.sh again."
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
print(module.NIGHT_START[0])
print(module.NIGHT_START[1])
print(module.STATE_DIR)
PY
)"
START_HOUR="$(echo "$CONFIG_VALUES" | sed -n '1p')"
START_MINUTE="$(echo "$CONFIG_VALUES" | sed -n '2p')"
STATE_DIR="$(echo "$CONFIG_VALUES" | sed -n '3p')"

mkdir -p "$STATE_DIR" "$HOME/Library/LaunchAgents"

PYTHON3="$(command -v python3)"
CAFFEINATE="$(command -v caffeinate)"
WIZ_GUARD="$SCRIPT_DIR/wiz_guard.py"
LOG_PATH="$STATE_DIR/guard.log"

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
  -e "s|__WIZ_GUARD__|$WIZ_GUARD|g" \
  -e "s|__START_HOUR__|$START_HOUR|g" \
  -e "s|__START_MINUTE__|$START_MINUTE|g" \
  -e "s|__LOG_PATH__|$LOG_PATH|g" \
  "$TEMPLATE" > "$PLIST_DEST"

chmod +x "$SCRIPT_DIR/bin/wiz-guard"
chmod +x "$SCRIPT_DIR/wiz_guard.py"

if launchctl print "${DOMAIN}/${LABEL}" >/dev/null 2>&1; then
  launchctl bootout "${DOMAIN}" "$PLIST_DEST" 2>/dev/null || true
fi

launchctl bootstrap "${DOMAIN}" "$PLIST_DEST"

BIN_LINK="$HOME/bin/wiz-guard"
mkdir -p "$HOME/bin"
ln -sf "$SCRIPT_DIR/bin/wiz-guard" "$BIN_LINK"

echo "Installed LaunchAgent: $PLIST_DEST"
echo "Starts daily at ${START_HOUR}:$(printf '%02d' "$START_MINUTE")"
echo "CLI: $BIN_LINK (ensure ~/bin is on PATH)"
echo "Logs: $LOG_PATH"
