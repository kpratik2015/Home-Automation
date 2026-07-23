#!/usr/bin/env python3
"""ESP-Touch / SmartConfig style broadcast while panel is in EZ (fast blink).

Run on *home* WiFi (not SKIT SoftAP). Put panel in pairing mode with
*fast* WiFi LED blink first.
"""

from __future__ import annotations

import argparse
import socket
import time


def log(msg: str) -> None:
    print(msg, flush=True)


def encode_guide() -> list[bytes]:
    # Guide codes: lengths 1..3 (classic esptouch guide)
    return [b"\x01" * n for n in (1, 2, 3, 4, 5, 6)]


def encode_data(ssid: str, password: str) -> list[bytes]:
    """Length-based encoding used by many ESP SmartConfig clones.

    Each byte B is sent as a UDP datagram of length (B + 40) to a
    multicast/broadcast address. Crude but matches common OEM EZ mode.
    """
    total = password.encode("utf-8") + b"\x00" + ssid.encode("utf-8")
    datagrams: list[bytes] = []
    for value in total:
        size = value + 40
        datagrams.append(b"\x01" * size)
    return datagrams


def blast(ssid: str, password: str, seconds: float = 20.0) -> None:
    targets = (
        ("255.255.255.255", 7001),
        ("255.255.255.255", 18266),
        ("224.0.0.1", 7001),
        ("239.0.0.1", 7001),
        ("255.255.255.255", 8266),
    )
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(0.05)

    guides = encode_guide()
    data = encode_data(ssid, password)
    end = time.time() + seconds
    rounds = 0
    while time.time() < end:
        for target in targets:
            for pkt in guides:
                try:
                    sock.sendto(pkt, target)
                except OSError:
                    pass
            for pkt in data:
                try:
                    sock.sendto(pkt, target)
                except OSError:
                    pass
        rounds += 1
        time.sleep(0.05)
    sock.close()
    log(f"sent {rounds} rounds over {seconds:.0f}s")


def main() -> int:
    parser = argparse.ArgumentParser(description="SmartConfig/EZ blast for SKIT panel")
    parser.add_argument("--ssid", required=True, help="home 2.4GHz SSID")
    parser.add_argument("--password", required=True, help="home WiFi password")
    parser.add_argument("--seconds", type=float, default=25.0)
    args = parser.parse_args()

    log("SmartConfig / EZ blast")
    log("=" * 40)
    log("prereq: Mac on home 2.4GHz WiFi")
    log("prereq: panel WiFi LED fast-blinking (EZ), not SoftAP-only")
    log(f"ssid: {args.ssid!r}")
    log("blasting...")
    blast(args.ssid, args.password, args.seconds)
    log("done - check if SKIT SoftAP disappeared / panel joined LAN")
    log("then: python3 discover.py --full-scan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
