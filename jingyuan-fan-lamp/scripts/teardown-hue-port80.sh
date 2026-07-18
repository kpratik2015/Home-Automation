#!/usr/bin/env bash
# Remove pf port-80 redirect / filter rules installed for Hue Alexa discovery.
set -euo pipefail

RDR_ANCHOR="/etc/pf.anchors/com.jingyuan.fanlamp"
FILTER_ANCHOR="/etc/pf.anchors/com.jingyuan.fanlamp-filter"
PF_CONF="/etc/pf.conf"
MARKER="com.jingyuan.fanlamp"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run with sudo:" >&2
  echo "  sudo $0" >&2
  exit 1
fi

if [[ -f "$PF_CONF" ]]; then
  python3 - "$PF_CONF" <<'PY'
import sys
from pathlib import Path

pf_conf = Path(sys.argv[1])
marker = "com.jingyuan.fanlamp"
lines = [
    line
    for line in pf_conf.read_text().splitlines()
    if marker not in line
]
pf_conf.write_text("\n".join(lines).rstrip() + "\n")
PY
  echo "Removed jingyuan entries from $PF_CONF"
fi

for anchor in "$RDR_ANCHOR" "$FILTER_ANCHOR"; do
  if [[ -f "$anchor" ]]; then
    rm "$anchor"
    echo "Removed $anchor"
  fi
done

if pfctl -nf /etc/pf.conf 2>/dev/null; then
  pfctl -f /etc/pf.conf 2>/dev/null || pfctl -ef /etc/pf.conf
  echo "Reloaded pf"
else
  echo "WARN: pf.conf syntax check failed; fix manually" >&2
  exit 1
fi

if netstat -an -p tcp 2>/dev/null | grep -q '\.80 .*LISTEN'; then
  echo "Port 80 still in use (may be Portless or another app)."
else
  echo "Port 80 is free."
fi

echo
echo "Restore Portless (if you used port 80 before):"
echo "  sudo portless proxy start --no-tls"
echo "  # or default port (no sudo): portless proxy start"
echo "  portless proxy status"
