from pathlib import Path

# Copy to config.local.py and edit for your home network.
BULB_IP = "192.168.0.103"

# 24-hour clock (hour, minute). Same calendar day; no cross-midnight window.
NIGHT_START = (1, 0)
NIGHT_END = (10, 0)

POLL_SECONDS = 30
BLIP_REOFF_SECONDS = 90
PAUSE_DEFAULT_MINUTES = 60

STATE_DIR = Path.home() / ".local/share/wiz-night-guard"
