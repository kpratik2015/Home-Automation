from __future__ import annotations

import platform

from protocol import Command


class AdvertiserError(RuntimeError):
    pass


def get_advertiser():
    system = platform.system()
    if system == "Darwin":
        from advertiser.macos import MacOSAdvertiser

        return MacOSAdvertiser()
    if system == "Linux":
        from advertiser.linux_bluez import LinuxBlueZAdvertiser

        return LinuxBlueZAdvertiser()
    raise AdvertiserError(
        f"BLE advertising is not supported on {system}. "
        "Run the bridge on macOS or Linux (Raspberry Pi recommended)."
    )


def send_command(command: Command) -> None:
    advertiser = get_advertiser()
    advertiser.send_burst(command)
