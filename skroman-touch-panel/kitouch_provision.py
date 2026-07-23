#!/usr/bin/env python3
"""Skroman iTouch SoftAP provisioner (from APK com.skroman.iTouch 1.7).

SoftAP join (values in local.env, gitignored):
  source local.env
  networksetup -setairportnetwork en0 "$SKIT_SOFTAP_SSID" "$SKIT_SOFTAP_PASSWORD"

Then push home WiFi:
  python3 kitouch_provision.py --ssid "$HOME_WIFI_SSID" --password "$HOME_WIFI_PASSWORD"

APK notes:
  - Local paths: /command  /status
  - WiFi cmds: configw-...  config-...
  - LocalNetworkManager: UDP broadcast + TCP (often phone listens, device dials)
  - SoftAP gw often has NO open ports until woken - do not hammer closed TCP
"""

from __future__ import annotations

import argparse
import json
import re
import socket
import subprocess
import threading
import time

IP_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")

TCP_SCAN = (
    80,
    443,
    1883,
    3000,
    5000,
    5555,
    6000,
    6666,
    6667,
    6668,
    6669,
    7000,
    8000,
    8080,
    8266,
    8888,
    9000,
    9999,
    10000,
)
UDP_PORTS = (
    1024,
    1883,
    5000,
    6666,
    6667,
    6668,
    6669,
    7000,
    7550,
    8080,
    8266,
    8888,
    10000,
    18266,
)
# App starts TCP server; device may connect inbound
LISTEN_PORTS = (
    80,
    1883,
    5000,
    6666,
    6667,
    6668,
    6669,
    7000,
    8080,
    8266,
    8888,
    9999,
    10000,
)


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


def subnet_broadcast(ip: str) -> str:
    parts = ip.split(".")
    if len(parts) != 4:
        return "255.255.255.255"
    return f"{parts[0]}.{parts[1]}.{parts[2]}.255"


def gateway_for(ip: str) -> str:
    parts = ip.split(".")
    return f"{parts[0]}.{parts[1]}.{parts[2]}.1"


def wifi_config_payloads(ssid: str, password: str) -> list[tuple[str, bytes]]:
    pairs = [
        f"configw-{ssid}:{password}",
        f"configw-{ssid},{password}",
        f"configw-{ssid};{password}",
        f"configw-{ssid}|{password}",
        f"configw-{ssid}\n{password}",
        f"config-{ssid}:{password}",
        f"config-{ssid},{password}",
        f"config-{ssid};{password}",
        f"getssidpassword:::",
        f"ssidPassword:{ssid}:{password}",
        f"devicessidPassword:{ssid}:{password}",
        json.dumps({"ssid": ssid, "password": password}, separators=(",", ":")),
        json.dumps(
            {"ssid": ssid, "password": password, "ssidPassword": f"{ssid}:{password}"},
            separators=(",", ":"),
        ),
    ]
    out: list[tuple[str, bytes]] = []
    for p in pairs:
        name = p[:28].replace("\n", "\\n")
        out.append((name, p.encode()))
        if not p.endswith(";"):
            out.append((name + ";", (p + ";").encode()))
    return out


def http_post(path: str, body: bytes) -> bytes:
    return (
        f"POST {path} HTTP/1.0\r\n"
        f"Host: device\r\n"
        f"Content-Type: text/plain\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode() + body


def tcp_exchange(host: str, port: int, payload: bytes, timeout: float = 0.2) -> bytes | None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        sock.sendall(payload)
        try:
            return sock.recv(4096)
        except socket.timeout:
            return b""
    except OSError:
        return None
    finally:
        sock.close()


def scan_open_tcp(host: str, ports: tuple[int, ...]) -> list[int]:
    open_ports: list[int] = []
    lock = threading.Lock()

    def probe(port: int) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.15)
        try:
            sock.connect((host, port))
            with lock:
                open_ports.append(port)
        except OSError:
            pass
        finally:
            sock.close()

    threads = [threading.Thread(target=probe, args=(p,), daemon=True) for p in ports]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=0.5)
    return sorted(open_ports)


def start_listeners(
    bind_ip: str,
    stop: threading.Event,
    reply: bytes,
    events: list[str],
) -> None:
    def accept_loop(port: int) -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            srv.bind((bind_ip, port))
            srv.listen(5)
            srv.settimeout(0.4)
            log(f"  [listen] {bind_ip}:{port}")
        except OSError as exc:
            log(f"  [listen] :{port} skip ({exc.errno})")
            return
        while not stop.is_set():
            try:
                conn, addr = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            msg = f"TCP-IN {addr} :{port}"
            events.append(msg)
            log(f"  [{msg}]")
            try:
                conn.settimeout(2.0)
                data = conn.recv(4096)
                log(f"  [recv] {data[:300]!r}")
                events.append(f"recv:{data[:80]!r}")
                # push all likely configs on inbound
                for payload in reply.split(b"\0"):
                    if payload:
                        conn.sendall(payload + b"\n")
            except OSError as exc:
                log(f"  [err] {exc}")
            finally:
                conn.close()
        srv.close()

    def udp_loop(port: int) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((bind_ip, port))
            sock.settimeout(0.4)
            log(f"  [udp-listen] {bind_ip}:{port}")
        except OSError:
            return
        while not stop.is_set():
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            msg = f"UDP-IN {addr} :{port} {data[:120]!r}"
            events.append(msg)
            log(f"  [{msg}]")
            try:
                sock.sendto(reply.split(b"\0")[0] + b"\n", addr)
            except OSError:
                pass
        sock.close()

    for port in LISTEN_PORTS:
        threading.Thread(target=accept_loop, args=(port,), daemon=True).start()
        threading.Thread(target=udp_loop, args=(port,), daemon=True).start()


def udp_send(local: str, dests: list[str], ports: tuple[int, ...], payloads: list[bytes]) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        sock.bind((local, 0))
    except OSError:
        pass
    for dest in dests:
        for port in ports:
            for payload in payloads:
                try:
                    sock.sendto(payload, (dest, port))
                except OSError:
                    continue
    sock.close()


def discovery_payloads(local: str) -> list[bytes]:
    return [
        local.encode(),
        f"{local}\n".encode(),
        json.dumps({"ip": local}).encode(),
        json.dumps({"selfIP": local}).encode(),
        f"ip:{local}".encode(),
        b"discover",
        b"DISCOVER",
        b"kitouch",
        b"SKIT",
        b"getssidpassword:::",
        b"/status",
        b"/command",
    ]


def provision_once(ssid: str, password: str, wait: float) -> int:
    ip = local_ip()
    if not ip:
        log("No local IP - join SKIT SoftAP first (see local.env)")
        return 2
    if IP_RE.match(ssid):
        log(f"Refuse IP-looking --ssid {ssid!r}")
        return 2

    gw = gateway_for(ip)
    bcast = subnet_broadcast(ip)
    log(f"local={ip} gateway={gw} ssid={ssid!r}")
    if not any(ip.startswith(p) for p in ("192.168.4.", "192.168.41.", "192.168.43.")):
        log("WARN: not on SoftAP subnet - join SKIT* first")

    cmds = wifi_config_payloads(ssid, password)
    cfg_bodies = [b for _, b in cmds]
    # null-separated bundle for inbound reply
    reply_bundle = b"\0".join(cfg_bodies[:6])

    stop = threading.Event()
    events: list[str] = []
    log("\n[0] listen (device may dial Mac)")
    start_listeners(ip, stop, reply_bundle, events)

    log("\n[1] TCP scan gateway only (open ports)")
    open_ports = scan_open_tcp(gw, TCP_SCAN)
    log(f"  {gw}: {open_ports or 'none'}")

    dests = [gw, bcast, "255.255.255.255"]
    log("\n[2] UDP discovery + config (fast)")
    udp_send(ip, dests, UDP_PORTS, discovery_payloads(ip))
    udp_send(ip, dests, UDP_PORTS, cfg_bodies)

    hits = 0
    if open_ports:
        log(f"\n[3] TCP to open ports only: {open_ports}")
        for port in open_ports:
            for path, body in (("/status", b""),) + tuple(
                ("/command", b) for _, b in cmds[:8]
            ):
                for frame in (
                    http_post(path, body),
                    path.encode() + b"\n" + body + b"\n",
                    body + b"\n" if body else b"",
                ):
                    if not frame:
                        continue
                    resp = tcp_exchange(gw, port, frame)
                    if resp is None:
                        break
                    if resp:
                        hits += 1
                        log(f"  HIT :{port} {path} -> {resp[:160]!r}")
    else:
        log("\n[3] skip outbound TCP (no open ports - was hang before)")

    log(f"\n[4] wait {wait:.0f}s: UDP repeat + inbound")
    deadline = time.time() + wait
    n = 0
    while time.time() < deadline:
        n += 1
        udp_send(ip, dests, UDP_PORTS, discovery_payloads(ip) + cfg_bodies[:8])
        # re-scan occasionally in case device opens a port after UDP
        if n % 3 == 0:
            anew = scan_open_tcp(gw, TCP_SCAN)
            if anew and anew != open_ports:
                log(f"  new open ports: {anew}")
                open_ports = anew
                for port in anew:
                    for _, body in cmds[:4]:
                        resp = tcp_exchange(gw, port, http_post("/command", body))
                        if resp:
                            hits += 1
                            log(f"  HIT :{port} -> {resp[:160]!r}")
        still = local_ip()
        if still is None:
            log("  SoftAP IP gone - panel may be joining home WiFi")
            break
        if still != ip:
            log(f"  IP {ip} -> {still}")
            break
        time.sleep(1.0)
        if n % 5 == 0:
            log(f"  ... {n}s events={len(events)}")

    stop.set()
    log(f"\nDone. tcp_hits={hits} events={len(events)}")
    for e in events[:20]:
        log(f"  event: {e}")
    if not events and hits == 0:
        log("No reply from module. Capture while this runs:")
        log("  sudo tcpdump -i en0 -w skit-prov.pcap udp or tcp")
    else:
        log("If SoftAP dropped: rejoin home WiFi, python3 kitouch_control.py --scan")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ssid", required=True, help="Home 2.4 GHz WiFi SSID")
    ap.add_argument("--password", required=True, help="Home WiFi password")
    ap.add_argument("--wait", type=float, default=20.0, help="Seconds to wait for inbound")
    args = ap.parse_args()
    return provision_once(args.ssid, args.password, args.wait)


if __name__ == "__main__":
    raise SystemExit(main())
