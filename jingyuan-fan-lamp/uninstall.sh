#!/usr/bin/env bash
set -euo pipefail

LABEL="com.jingyuan.fanlamp.bridge"
PLIST_DEST="$HOME/Library/LaunchAgents/${LABEL}.plist"
DOMAIN="gui/$(id -u)"
BIN_LINK="$HOME/bin/fan-bridge"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if launchctl print "${DOMAIN}/${LABEL}" >/dev/null 2>&1; then
  launchctl bootout "${DOMAIN}" "$PLIST_DEST"
  echo "Stopped LaunchAgent ${LABEL}"
fi

if [[ -f "$PLIST_DEST" ]]; then
  rm "$PLIST_DEST"
  echo "Removed $PLIST_DEST"
fi

if [[ -L "$BIN_LINK" ]]; then
  rm "$BIN_LINK"
  echo "Removed symlink $BIN_LINK"
fi

if grep -q 'com.jingyuan.fanlamp' /etc/pf.conf 2>/dev/null; then
  echo "Hue port-80 pf rules still installed. Remove with:"
  echo "  sudo ./scripts/teardown-hue-port80.sh"
fi

if [[ "${1:-}" == "--purge" ]]; then
  STATE_DIR="$(python3 - "$SCRIPT_DIR/config.local.py" <<'PY' 2>/dev/null || true
import importlib.util
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    sys.exit(0)
spec = importlib.util.spec_from_file_location("config_local", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print(module.STATE_DIR)
PY
)"
  if [[ -n "${STATE_DIR:-}" && -d "$STATE_DIR" ]]; then
    rm -rf "$STATE_DIR"
    echo "Removed runtime data: $STATE_DIR"
  fi
fi

echo "Uninstall complete."
