#!/usr/bin/env python3
"""SoftAP WiFi provision for SKIT* modules.

Join SKIT58* first. Pass your *home* 2.4 GHz WiFi name + password
(not the SoftAP IP, not the Mac IP).

Example:
  python3 softap_provision.py --ssid 'MyHomeWiFi' --password 'secret'
"""

from __future__ import annotations

import argparse
import json
import re
import socket
import subprocess
import time

UDP_PORTS = (8266, 6666, 6667, 6668, 6669, 7000, 7550, 8080, 10000, 18266)
TCP_PORTS = (80, 443, 8080, 8888, 6668)
IP_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


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


def gateway_for(ip: str) -> str:
    parts = ip.split(".")
    return f"{parts[0]}.{parts[1]}.{parts[2]}.1"


def payloads(ssid: str, password: str, token: str) -> list[tuple[str, bytes]]:
    return [
        (
            "bemfa-cmd1",
            json.dumps(
                {"cmdType": 1, "ssid": ssid, "password": password, "token": token},
                separators=(",", ":"),
            ).encode(),
        ),
        (
            "bemfa-plain",
            json.dumps(
                {"cmdType": 1, "ssid": ssid, "password": password},
                separators=(",", ":"),
            ).encode(),
        ),
        (
            "ssid-pwd",
            json.dumps({"ssid": ssid, "password": password}, separators=(",", ":")).encode(),
        ),
        (
            "SSID-PWD",
            json.dumps({"SSID": ssid, "PWD": password}, separators=(",", ":")).encode(),
        ),
        (
            "wifi-config",
            json.dumps(
                {"wifi": {"ssid": ssid, "password": password}},
                separators=(",", ":"),
            ).encode(),
        ),
        (
            "tuya-like",
            json.dumps(
                {"ssid": ssid, "passwd": password, "token": token},
                separators=(",", ":"),
            ).encode(),
        ),
        ("kv-ssid", f"ssid={ssid}\npassword={password}\n".encode()),
        ("pipe", f"{ssid}|{password}".encode()),
    ]


def try_udp(local: str, host: str, port: int, blob: bytes, timeout: float = 0.6) -> str | None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.bind((local, 0))
        sock.sendto(blob, (host, port))
        data, addr = sock.recvfrom(4096)
        return f"{addr[0]}:{addr[1]} -> {data[:300]!r}"
    except socket.timeout:
        return None
    except OSError as exc:
        return f"error: {exc}"
    finally:
        sock.close()


def softap_alive(local: str) -> bool:
    return local_ip() == local or (local_ip() or "").startswith("192.168.4.")


def wait_softap_drop(seconds: float = 12.0) -> bool:
    end = time.time() + seconds
    while time.time() < end:
        ip = local_ip()
        if not ip or not ip.startswith("192.168.4."):
            return True
        time.sleep(0.5)
    return False


def try_tcp_http(host: str, ssid: str, password: str) -> list[str]:
    hits: list[str] = []
    bodies = [
        json.dumps({"ssid": ssid, "password": password}).encode(),
        json.dumps({"cmdType": 1, "ssid": ssid, "password": password}).encode(),
        f"ssid={ssid}&password={password}".encode(),
    ]
    paths = ("/", "/config", "/wifi", "/provision", "/ap", "/setwifi")
    for port in TCP_PORTS:
        for path in paths:
            for body in bodies:
                try:
                    sock = socket.create_connection((host, port), timeout=0.4)
                except OSError:
                    break
                try:
                    req = (
                        f"POST {path} HTTP/1.1\r\n"
                        f"Host: {host}\r\n"
                        "Content-Type: application/json\r\n"
                        f"Content-Length: {len(body)}\r\n"
                        "Connection: close\r\n\r\n"
                    ).encode() + body
                    sock.sendall(req)
                    sock.settimeout(0.8)
                    resp = sock.recv(1024)
                    if resp:
                        hits.append(f"tcp {host}:{port}{path} -> {resp[:200]!r}")
                except OSError:
                    pass
                finally:
                    sock.close()
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description="SoftAP WiFi provision for SKIT*")
    parser.add_argument("--ssid", required=True, help="HOME 2.4GHz WiFi name (not SoftAP IP)")
    parser.add_argument("--password", required=True, help="HOME WiFi password")
    parser.add_argument("--token", default="00000000")
    parser.add_argument("--gateway", default="")
    parser.add_argument(
        "--gentle",
        action="store_true",
        help="only send bemfa/ssid payloads on 8266+6666, then wait for SoftAP drop",
    )
    args = parser.parse_args()

    if IP_RE.match(args.ssid):
        log(f"ERROR: --ssid looks like an IP ({args.ssid})")
        log("Use your home WiFi *name*, e.g. --ssid 'MyHomeWiFi'")
        log("Last run likely made the panel try to join a fake SSID, SoftAP bounced")
        return 2

    ip = local_ip()
    if not ip:
        log("no local ip - join SKIT58* WiFi first")
        return 1
    if not ip.startswith("192.168.4."):
        log(f"warning: local ip {ip} - expected 192.168.4.x on SKIT AP")

    host = args.gateway or gateway_for(ip)
    log("SoftAP provision probe")
    log("=" * 40)
    log(f"local ip:  {ip}")
    log(f"gateway:   {host}")
    log(f"home ssid: {args.ssid!r}")

    all_payloads = payloads(args.ssid, args.password, args.token)
    if args.gentle:
        all_payloads = [p for p in all_payloads if p[0] in ("bemfa-cmd1", "bemfa-plain", "ssid-pwd")]
        ports = (8266, 6666, 6667)
    else:
        ports = UDP_PORTS

    log("\n[1] UDP credential send")
    sent = 0
    replied = 0
    for label, blob in all_payloads:
        for port in ports:
            if not softap_alive(ip):
                log("  SoftAP dropped mid-send - likely accepted a payload")
                break
            reply = try_udp(ip, host, port, blob)
            sent += 1
            if reply is None:
                log(f"  {label} @{port}: sent (no reply)")
            elif reply.startswith("error:"):
                log(f"  {label} @{port}: {reply}")
                if "unreachable" in reply:
                    log("  SoftAP route gone - waiting for outcome")
                    break
            else:
                replied += 1
                log(f"  {label} @{port}: {reply}")
        else:
            continue
        break

    log(f"\n[2] wait for SoftAP drop ({12}s)")
    dropped = wait_softap_drop(12.0)
    if dropped:
        log("  SoftAP gone - panel may be joining home WiFi")
        log("  reconnect Mac to home WiFi, then: python3 discover.py --full-scan")
        log("  also check router DHCP for a new client")
    else:
        log("  SoftAP still up")

    if not args.gentle:
        log("\n[3] TCP HTTP POST attempts")
        http_hits = try_tcp_http(host, args.ssid, args.password)
        if http_hits:
            for row in http_hits:
                log(f"  {row}")
        else:
            log("  no TCP HTTP responses")

    log(f"\nsent={sent} replies={replied} softap_dropped={dropped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
