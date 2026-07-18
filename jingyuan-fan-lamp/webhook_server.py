#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from command_dispatch import dispatch_command
from protocol import COMMANDS

ROUTES = {
    "/fan/on": "fan-on",
    "/fan/off": "fan-off",
    "/light/on": "light-on",
    "/light/off": "light-off",
}


class WebhookHandler(BaseHTTPRequestHandler):
    token = ""
    debounce_seconds = 1.5

    def log_message(self, format: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

    def _authorized(self) -> bool:
        if not self.token:
            return True
        auth = self.headers.get("Authorization", "")
        return auth == f"Bearer {self.token}"

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if urlparse(self.path).path == "/health":
            self._send_json(200, {"ok": True, "commands": sorted(COMMANDS)})
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        route = urlparse(self.path).path
        command_name = ROUTES.get(route)
        if command_name is None:
            self._send_json(404, {"error": "not found"})
            return
        if not self._authorized():
            self._send_json(401, {"error": "unauthorized"})
            return
        try:
            dispatch_command(command_name, self.debounce_seconds)
        except Exception as exc:
            self._send_json(500, {"error": str(exc)})
            return
        self._send_json(200, {"ok": True, "command": command_name})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local HTTP bridge for fan BLE commands (for Alexa/cloud relay).",
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument(
        "--token",
        default=os.environ.get("FAN_BLE_TOKEN", ""),
        help="Bearer token required on POST requests",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    WebhookHandler.token = args.token
    server = HTTPServer((args.host, args.port), WebhookHandler)
    print(f"Listening on http://{args.host}:{args.port}", file=sys.stderr)
    print(
        "Routes: POST /fan/on, POST /fan/off, POST /light/on, POST /light/off, GET /health",
        file=sys.stderr,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
