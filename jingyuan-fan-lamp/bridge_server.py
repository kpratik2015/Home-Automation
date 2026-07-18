#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from command_dispatch import dispatch_command
from config_loader import load_config
from protocol import COMMANDS
from queue_poller import start_queue_poller_thread

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
        path = urlparse(self.path).path
        if path == "/health":
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


def start_webhook_server(
    host: str,
    port: int,
    token: str,
    debounce_seconds: float,
) -> HTTPServer:
    handler = type(
        "ConfiguredWebhookHandler",
        (WebhookHandler,),
        {"token": token, "debounce_seconds": debounce_seconds},
    )
    server = HTTPServer((host, port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Webhook on http://{host}:{port}", file=sys.stderr)
    return server


def main() -> int:
    config = load_config()
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)

    stop_event = threading.Event()
    webhook_server = start_webhook_server(
        "0.0.0.0",
        config.WEBHOOK_PORT,
        config.WEBHOOK_TOKEN,
        config.DEBOUNCE_SECONDS,
    )

    queue_enabled = bool(getattr(config, "QUEUE_ENABLED", False))
    if queue_enabled:
        base_url = getattr(config, "QUEUE_BASE_URL", "")
        dequeue_token = getattr(config, "QUEUE_DEQUEUE_TOKEN", "")
        poll_interval = float(getattr(config, "POLL_INTERVAL_SECONDS", 2.0))
        if (
            not base_url
            or not dequeue_token
            or dequeue_token.startswith("change-me")
        ):
            print(
                "QUEUE_BASE_URL and QUEUE_DEQUEUE_TOKEN required when QUEUE_ENABLED is true.",
                file=sys.stderr,
            )
            return 1
        start_queue_poller_thread(
            base_url,
            dequeue_token,
            config.DEBOUNCE_SECONDS,
            poll_interval,
            stop_event,
        )

    print("Bridge running. Quit iPhone app before Mac control.", file=sys.stderr)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        stop_event.set()
        webhook_server.shutdown()
        print("Stopped", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
