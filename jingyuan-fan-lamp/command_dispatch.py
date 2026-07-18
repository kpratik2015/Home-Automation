from __future__ import annotations

import sys
import threading
import time

from advertiser import AdvertiserError, send_command
from protocol import parse_command

_lock = threading.Lock()
_last_sent_at: dict[str, float] = {}


def dispatch_command(command_name: str, debounce_seconds: float) -> bool:
    now = time.monotonic()
    with _lock:
        last = _last_sent_at.get(command_name)
        if last is not None and now - last < debounce_seconds:
            print(f"Command {command_name} debounced", file=sys.stderr)
            return False
        _last_sent_at[command_name] = now

    try:
        command = parse_command(command_name)
        send_command(command)
    except (AdvertiserError, ValueError, FileNotFoundError, RuntimeError) as exc:
        print(f"Command {command_name} failed: {exc}", file=sys.stderr)
        raise
    return True
