#!/usr/bin/env bash
set -euo pipefail

DOMAIN="gui/$(id -u)"
WIZ_PLIST="$HOME/Library/LaunchAgents/com.wiz.nightguard.plist"
FAN_PLIST="$HOME/Library/LaunchAgents/com.jingyuan.fanlamp.bridge.plist"

stop_agent() {
  local label="$1"
  local plist="$2"
  if [[ -f "$plist" ]]; then
    launchctl bootout "$DOMAIN" "$plist" 2>/dev/null || true
    echo "Stopped $label"
  else
    echo "Skip $label (not installed)"
  fi
}

stop_agent "com.wiz.nightguard" "$WIZ_PLIST"
stop_agent "com.jingyuan.fanlamp.bridge" "$FAN_PLIST"

echo
echo "Mac automations stopped. Safe to test ESP32 WiZ guard and/or fan BLE."
echo "Resume with: ./scripts/resume-mac.sh"
