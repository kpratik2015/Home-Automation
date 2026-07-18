#!/usr/bin/env python3
"""WiZ night guard: arm after off, force off on power blips during night window."""

from __future__ import annotations

import argparse
import importlib.util
import json
import socket
import sys
import time
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
WIZ_PORT = 38899
UDP_TIMEOUT = 3.0


def load_config():
    local_path = SCRIPT_DIR / "config.local.py"
    example_path = SCRIPT_DIR / "config.example.py"
    if not local_path.exists():
        print(
            f"Missing {local_path}\n"
            f"Create it from the example:\n"
            f"  cp {example_path} {local_path}\n"
            f"Then edit BULB_IP and schedule in config.local.py.",
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


def log_line(config, level: str, message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp} [{level}] {message}"
    print(line, flush=True)
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    log_path = config.STATE_DIR / "guard.log"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def state_path(config) -> Path:
    return config.STATE_DIR / "state.json"


def load_state(config) -> dict[str, Any]:
    path = state_path(config)
    if not path.exists():
        return {"armed": False, "paused_until": 0, "last_guard_off_at": 0}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"armed": False, "paused_until": 0, "last_guard_off_at": 0}


def save_state(config, state: dict[str, Any]) -> None:
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_path(config).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def send_udp(ip: str, payload: dict[str, Any]) -> dict[str, Any]:
    message = json.dumps(payload).encode("utf-8")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(UDP_TIMEOUT)
        sock.sendto(message, (ip, WIZ_PORT))
        data, _ = sock.recvfrom(4096)
    return json.loads(data.decode("utf-8"))


def get_bulb_state(config) -> bool | None:
    try:
        response = send_udp(config.BULB_IP, {"method": "getPilot", "params": {}})
    except (OSError, json.JSONDecodeError, TimeoutError, socket.timeout) as error:
        log_line(config, "WARN", f"getPilot failed for {config.BULB_IP}: {error}")
        return None
    result = response.get("result")
    if not isinstance(result, dict):
        log_line(config, "WARN", f"Unexpected getPilot response: {response}")
        return None
    return bool(result.get("state"))


def turn_off(config, dry_run: bool) -> None:
    if dry_run:
        log_line(config, "INFO", f"[dry-run] would turn off {config.BULB_IP}")
        return
    try:
        send_udp(config.BULB_IP, {"method": "setPilot", "params": {"state": False}})
        log_line(config, "INFO", f"Turned off {config.BULB_IP}")
    except (OSError, json.JSONDecodeError, TimeoutError, socket.timeout) as error:
        log_line(config, "WARN", f"setPilot off failed for {config.BULB_IP}: {error}")


def parse_time_tuple(value: tuple[int, int]) -> dt_time:
    hour, minute = value
    return dt_time(hour=hour, minute=minute)


def in_night_window(config, now: datetime | None = None) -> bool:
    current = now or datetime.now()
    start = parse_time_tuple(config.NIGHT_START)
    end = parse_time_tuple(config.NIGHT_END)
    now_time = current.time()
    return start <= now_time < end


def is_paused(state: dict[str, Any]) -> bool:
    return int(state.get("paused_until", 0)) > int(time.time())


def cmd_status(config) -> int:
    state = load_state(config)
    bulb_on = get_bulb_state(config)
    paused = is_paused(state)
    window = in_night_window(config)
    print(f"bulb_ip:      {config.BULB_IP}")
    print(f"night_window: {config.NIGHT_START} - {config.NIGHT_END}")
    print(f"in_window:    {window}")
    print(f"armed:        {state.get('armed', False)}")
    print(f"paused:       {paused}")
    if paused:
        until = datetime.fromtimestamp(int(state["paused_until"]))
        print(f"paused_until: {until.isoformat(sep=' ', timespec='seconds')}")
    if bulb_on is None:
        print("bulb_state:   unreachable")
        return 1
    print(f"bulb_state:   {'on' if bulb_on else 'off'}")
    return 0


def cmd_pause(config, minutes: int) -> int:
    state = load_state(config)
    state["paused_until"] = int(time.time()) + minutes * 60
    save_state(config, state)
    until = datetime.fromtimestamp(state["paused_until"])
    log_line(config, "INFO", f"Paused until {until.isoformat(sep=' ', timespec='seconds')}")
    return 0


def cmd_resume(config) -> int:
    state = load_state(config)
    state["paused_until"] = 0
    save_state(config, state)
    log_line(config, "INFO", "Pause cleared")
    return 0


def run_loop(config, dry_run: bool, force_window: bool) -> int:
    if not force_window and not in_night_window(config):
        log_line(config, "INFO", "Outside night window; exiting")
        return 0

    log_line(
        config,
        "INFO",
        f"Starting guard (dry_run={dry_run}, force_window={force_window})",
    )
    was_paused = False

    while force_window or in_night_window(config):
        state = load_state(config)
        paused = is_paused(state)
        bulb_on = get_bulb_state(config)

        if bulb_on is None:
            time.sleep(config.POLL_SECONDS)
            continue

        pause_just_ended = was_paused and not paused
        was_paused = paused

        if paused:
            log_line(config, "INFO", "Paused; skipping force-off")
            time.sleep(config.POLL_SECONDS)
            continue

        if not state.get("armed", False):
            if not bulb_on:
                state["armed"] = True
                save_state(config, state)
                log_line(config, "INFO", "Bulb off; guard armed")
            else:
                log_line(config, "INFO", "Waiting for bulb to turn off before arming")
        elif bulb_on:
            reason = "pause ended" if pause_just_ended else "bulb on while armed"
            log_line(config, "INFO", f"Forcing off ({reason})")
            turn_off(config, dry_run)
            if not dry_run:
                state["last_guard_off_at"] = int(time.time())
                save_state(config, state)

        time.sleep(config.POLL_SECONDS)

    state = load_state(config)
    state["armed"] = False
    save_state(config, state)
    log_line(config, "INFO", "Night window ended; disarmed and exiting")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WiZ night guard")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the guard daemon")
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log actions without sending turn-off commands",
    )
    run_parser.add_argument(
        "--force-window",
        action="store_true",
        help="Ignore clock; stay in night mode until Ctrl-C (for testing)",
    )

    pause_parser = subparsers.add_parser("pause", help="Pause force-off")
    pause_parser.add_argument(
        "minutes",
        nargs="?",
        type=int,
        default=None,
        help="Pause duration in minutes (default from config)",
    )

    subparsers.add_parser("resume", help="Clear pause")
    subparsers.add_parser("status", help="Show guard and bulb status")
    return parser


def main() -> int:
    config = load_config()
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "run":
        return run_loop(config, dry_run=args.dry_run, force_window=args.force_window)
    if args.command == "pause":
        minutes = args.minutes if args.minutes is not None else config.PAUSE_DEFAULT_MINUTES
        return cmd_pause(config, minutes)
    if args.command == "resume":
        return cmd_resume(config)
    if args.command == "status":
        return cmd_status(config)
    parser.error(f"Unknown command: {args.command}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
