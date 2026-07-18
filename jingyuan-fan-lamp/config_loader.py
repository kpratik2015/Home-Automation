from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def load_config():
    local_path = SCRIPT_DIR / "config.local.py"
    example_path = SCRIPT_DIR / "config.example.py"
    if not local_path.exists():
        print(
            f"Missing {local_path}\n"
            f"Create it from the example:\n"
            f"  cp {example_path} {local_path}\n"
            f"Then edit WEBHOOK_TOKEN and QUEUE_DEQUEUE_TOKEN.",
            file=sys.stderr,
        )
        sys.exit(1)
    spec = importlib.util.spec_from_file_location("config_local", local_path)
    if spec is None or spec.loader is None:
        print(f"Could not load {local_path}", file=sys.stderr)
        sys.exit(1)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
