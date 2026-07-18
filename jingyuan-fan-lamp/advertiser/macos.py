from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from protocol import Command

SCRIPT_DIR = Path(__file__).resolve().parent.parent
SWIFT_SCRIPT = SCRIPT_DIR / "fan_ble.swift"


class MacOSAdvertiser:
    def send_burst(self, command: Command) -> None:
        if not SWIFT_SCRIPT.exists():
            raise FileNotFoundError(f"Missing macOS backend: {SWIFT_SCRIPT}")

        result = subprocess.run(
            [str(SWIFT_SCRIPT), command.name],
            check=False,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"fan_ble.swift failed with exit code {result.returncode}")
        print(f"Sent {command.name}", file=sys.stderr)
