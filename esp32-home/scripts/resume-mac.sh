#!/usr/bin/env bash
set -euo pipefail

DOMAIN="gui/$(id -u)"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

start_agent() {
  local label="$1"
  local plist="$2"
  if [[ -f "$plist" ]]; then
    launchctl bootstrap "$DOMAIN" "$plist" 2>/dev/null || launchctl kickstart -k "$DOMAIN/$label"
    echo "Started $label"
  else
    echo "Skip $label (plist missing: $plist)"
  fi
}

start_agent "com.wiz.nightguard" "$HOME/Library/LaunchAgents/com.wiz.nightguard.plist"
start_agent "com.jingyuan.fanlamp.bridge" "$HOME/Library/LaunchAgents/com.jingyuan.fanlamp.bridge.plist"

echo
echo "If a service was never installed, run install.sh in wiz-night-guard or jingyuan-fan-lamp:"
echo "  $REPO_ROOT/wiz-night-guard/install.sh"
echo "  $REPO_ROOT/jingyuan-fan-lamp/install.sh"
