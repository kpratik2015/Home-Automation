#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from advertiser import AdvertiserError, send_command
from protocol import COMMANDS, parse_command


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay Jingyuan fan/lamp BLE advertisement commands.",
    )
    parser.add_argument(
        "command",
        choices=sorted(COMMANDS),
        help="Command to broadcast",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        command = parse_command(args.command)
        send_command(command)
    except (AdvertiserError, ValueError, FileNotFoundError, RuntimeError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
