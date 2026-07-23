#!/usr/bin/env python3
"""Local control for Skroman iTouch after panel is on home WiFi.

  python3 kitouch_control.py --host 192.168.0.X --cmd 'M:L:1;'
  python3 kitouch_control.py --host 192.168.0.X --status
  python3 kitouch_control.py --scan
"""

from __future__ import annotations

import argparse
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

PORTS = (80, 6666, 6667, 6668, 6669, 7000, 8000, 8080, 8888, 10000)


def log(msg: str) -> None:
    print(msg, flush=True)


def local_ip() -> str | None:
    for iface in ("en0", "en1"):
        try:
            out = subprocess.check_output(
                ["ipconfig", "getifaddr", iface],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=1.0,
            ).strip()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            continue
        if out:
            return out
    return None


def send(host: str, port: int, path: str, body: bytes, timeout: float = 1.0) -> bytes | None:
    frames = [
        (
            f"POST {path} HTTP/1.0\r\nHost: {host}\r\n"
            f"Content-Type: text/plain\r\nContent-Length: {len(body)}\r\n"
            f"Connection: close\r\n\r\n"
        ).encode()
        + body,
        path.encode() + b"\n" + body + b"\n",
        body + b"\n",
    ]
    for frame in frames:
        try:
            with socket.create_connection((host, port), timeout=timeout) as sock:
                sock.settimeout(timeout)
                sock.sendall(frame)
                try:
                    return sock.recv(4096)
                except socket.timeout:
                    return b""
        except OSError:
            continue
    return None


def probe_host(host: str) -> list[tuple[int, bytes]]:
    hits: list[tuple[int, bytes]] = []
    for port in PORTS:
        resp = send(host, port, "/status", b"", timeout=0.35)
        if resp:
            hits.append((port, resp))
    return hits


def scan_subnet() -> None:
    ip = local_ip()
    if not ip:
        log("No local IP")
        return
    base = ".".join(ip.split(".")[:3])
    log(f"Scanning {base}.0/24 for /status ...")
    hosts = [f"{base}.{i}" for i in range(1, 255) if f"{base}.{i}" != ip]

    def work(h: str) -> tuple[str, list[tuple[int, bytes]]]:
        return h, probe_host(h)

    with ThreadPoolExecutor(max_workers=64) as pool:
        futs = [pool.submit(work, h) for h in hosts]
        for fut in as_completed(futs):
            host, hits = fut.result()
            if hits:
                for port, resp in hits:
                    log(f"  {host}:{port} -> {resp[:120]!r}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", help="Panel IP on LAN")
    ap.add_argument("--port", type=int, default=0, help="Force port (0=try all)")
    ap.add_argument("--cmd", default="", help="e.g. M:L:1; or configw-ssid:pass")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--scan", action="store_true")
    args = ap.parse_args()

    if args.scan:
        scan_subnet()
        return 0
    if not args.host:
        log("Need --host or --scan")
        return 2

    ports = [args.port] if args.port else list(PORTS)
    if args.status or not args.cmd:
        for port in ports:
            resp = send(args.host, port, "/status", b"")
            if resp is not None:
                log(f":{port} status -> {resp!r}")
    if args.cmd:
        body = args.cmd.encode()
        for port in ports:
            resp = send(args.host, port, "/command", body)
            if resp is not None:
                log(f":{port} command -> {resp!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
