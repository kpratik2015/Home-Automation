from pathlib import Path

# Copy to config.local.py and edit for your setup.

WEBHOOK_TOKEN = "change-me-to-a-long-random-string"
WEBHOOK_PORT = 8787
DEBOUNCE_SECONDS = 1.5

QUEUE_ENABLED = True
QUEUE_BASE_URL = "https://pratikkataria.com/home-automation/fan-queue"
QUEUE_DEQUEUE_TOKEN = "change-me-dequeue-token"
POLL_INTERVAL_SECONDS = 2.0

STATE_DIR = Path.home() / ".local/share/jingyuan-fan-lamp"
