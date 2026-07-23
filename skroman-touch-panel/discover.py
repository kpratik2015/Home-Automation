#!/usr/bin/env python3
"""Discover Skroman/Tuya panel identity while joined to SKIT* AP."""

from __future__ import annotations

import json
import re
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

UDP_PORTS = (6666, 6667, 6669, 7000)
GATEWAY_CANDIDATES = (
    "192.168.4.1",
    "192.168.176.1",
    "192.168.133.1",
    "10.0.0.1",
)
PROBE_PORTS = (80, 443, 6666, 6667, 6668, 6669, 7000, 8080, 8888, 1883)


def log(msg: str) -> None:
    print(msg, flush=True)


def run(cmd: list[str], timeout: float = 3.0) -> str:
    try:
        return subprocess.check_output(
            cmd,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
        )
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ):
        return ""


def wifi_info() -> dict[str, str]:
    info: dict[str, str] = {}
    out = run(
        [
            "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport",
            "-I",
        ],
        timeout=2.0,
    )
    for line in out.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        info[key.strip().lower().replace(" ", "_")] = value.strip()
    return info


def local_ip() -> str | None:
    for iface in ("en0", "en1"):
        ip = run(["ipconfig", "getifaddr", iface], timeout=1.0).strip()
        if ip:
            return ip
    return None


def subnet_broadcast(ip: str) -> str:
    parts = ip.split(".")
    if len(parts) != 4:
        return "255.255.255.255"
    return f"{parts[0]}.{parts[1]}.{parts[2]}.255"


def udp_broadcast(local_ip_addr: str, timeout: float = 1.0) -> list[str]:
    hits: list[str] = []
    bcast = subnet_broadcast(local_ip_addr)
    payloads = (
        b'{"from":"app","ip":""}',
        f'{{"from":"app","ip":"{local_ip_addr}"}}'.encode(),
        b'{"gwId":"","devId":"","uid":"","t":""}',
    )
    for port in UDP_PORTS:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(timeout)
        try:
            sock.bind((local_ip_addr, 0))
            for payload in payloads:
                for target in (bcast, "255.255.255.255"):
                    try:
                        sock.sendto(payload, (target, port))
                    except OSError as exc:
                        hits.append(f"send error {target}:{port} -> {exc}")
                        break
            try:
                data, addr = sock.recvfrom(4096)
                text = data.decode("utf-8", errors="replace")
                hits.append(f"{addr[0]}:{port} {text}")
            except socket.timeout:
                pass
        finally:
            sock.close()
    return hits


def default_gateway() -> str | None:
    out = run(["route", "-n", "get", "default"], timeout=1.0)
    for line in out.splitlines():
        if line.strip().startswith("gateway:"):
            return line.split(":", 1)[1].strip()
    return None


def tcp_alive(host: str, port: int, timeout: float = 0.25) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def http_get(url: str, timeout: float = 1.0) -> str | None:
    req = urllib.request.Request(url, headers={"User-Agent": "skroman-discover/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read(2048).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.read(2048).decode("utf-8", errors="replace")
    except Exception:
        return None


def extract_ids(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    patterns = {
        "gwId": r'"gwId"\s*:\s*"([^"]+)"',
        "devId": r'"devId"\s*:\s*"([^"]+)"',
        "productKey": r'"productKey"\s*:\s*"([^"]+)"',
        "uuid": r'"uuid"\s*:\s*"([^"]+)"',
        "mac": r'"mac"\s*:\s*"([^"]+)"',
        "model": r'"model"\s*:\s*"([^"]+)"',
        "product_name": r'"productName"\s*:\s*"([^"]+)"',
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            found[key] = match.group(1)
    return found


def is_local_http_noise(body: str) -> bool:
    markers = ("404 - Not Found", "@font-face", "color-scheme")
    return body.startswith("<!DOCTYPE html>") and any(marker in body for marker in markers)


def probe_host(host: str, local_ip_addr: str) -> list[str]:
    if host == local_ip_addr:
        return []

    lines: list[str] = []
    open_ports = [port for port in PROBE_PORTS if tcp_alive(host, port)]
    if not open_ports:
        lines.append(f"{host} no open probe ports")
        return lines

    lines.append(f"{host} open ports: {open_ports}")
    for port in open_ports:
        if port not in (80, 8080, 8888):
            continue
        for path in ("/", "/gw.json", "/status", "/device/info"):
            body = http_get(f"http://{host}:{port}{path}")
            if not body or is_local_http_noise(body):
                continue
            lines.append(f"{host}:{port}{path} -> {body[:240]!r}")
            ids = extract_ids(body)
            if ids:
                lines.append(f"{host}:{port}{path} ids: {json.dumps(ids)}")
    return lines


def scan_subnet(prefix: str, local_ip_addr: str) -> list[str]:
    lines: list[str] = []
    hosts = [f"{prefix}.{n}" for n in range(1, 255) if f"{prefix}.{n}" != local_ip_addr]

    with ThreadPoolExecutor(max_workers=80) as pool:
        futures = [pool.submit(probe_host, host, local_ip_addr) for host in hosts]
        for future in as_completed(futures):
            result = future.result()
            if any("open ports" in row and "no open" not in row for row in result):
                lines.extend(result)
    return lines


def main() -> int:
    log("Skroman/Tuya AP discovery")
    log("=" * 40)

    ip = local_ip()
    wifi = wifi_info()
    ssid = wifi.get("ssid", "")
    bssid = wifi.get("bssid", "")

    if not ip:
        log("no local ip - join SKIT58* WiFi first, then re-run")
        return 1

    gateway = default_gateway()
    log(f"local ip: {ip}")
    if gateway:
        log(f"gateway:  {gateway}")
    if ssid:
        log(f"ssid:     {ssid}")
    if bssid:
        log(f"bssid:    {bssid}")
        log(f"mac id:   {bssid.replace(':', '').lower()}")
    if ssid.upper().startswith("SKIT"):
        log(f"ssid suffix: {ssid[4:]!r}")

    log("\n[1] UDP broadcast discovery")
    udp_hits = udp_broadcast(ip)
    response_hits = [row for row in udp_hits if not row.startswith("send error")]
    send_errors = [row for row in udp_hits if row.startswith("send error")]
    for row in send_errors:
        log(f"  {row}")
    if response_hits:
        for row in response_hits:
            log(f"  {row}")
            ids = extract_ids(row)
            if ids:
                log(f"    parsed: {json.dumps(ids)}")
    else:
        log("  no UDP replies")

    log("\n[2] gateway probe")
    targets: list[str] = []
    if gateway:
        targets.append(gateway)
    prefix = ".".join(ip.split(".")[:3])
    for host in GATEWAY_CANDIDATES:
        if host.startswith(prefix + ".") and host not in targets:
            targets.append(host)

    gateway_hits: list[str] = []
    for host in targets:
        gateway_hits.extend(probe_host(host, ip))
    if gateway_hits:
        for row in gateway_hits:
            log(f"  {row}")
    else:
        log("  no panel response on gateway")

    subnet_hits: list[str] = []
    if "--full-scan" in sys.argv:
        log(f"\n[3] full subnet scan {prefix}.0/24 (excluding {ip})")
        subnet_hits = scan_subnet(prefix, ip)
        if subnet_hits:
            for row in subnet_hits:
                log(f"  {row}")
        else:
            log("  no other hosts with open ports")
    else:
        log("\n[3] full subnet scan skipped (pass --full-scan)")

    log("\ninterpretation:")
    if not response_hits and all("no open probe ports" in row for row in gateway_hits if row):
        log("  panel AP is up but not exposing tuya http/udp to mac")
        log("  use phone app pairing (Ki Touch+ / Smart Life), not Ora manual id/pop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
