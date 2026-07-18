from __future__ import annotations

import asyncio
import sys

from protocol import Command, burst_steps

BLUEZ_SERVICE = "org.bluez"
ADAPTER_INTERFACE = "org.bluez.Adapter1"
LE_ADVERTISING_MANAGER = "org.bluez.LEAdvertisingManager1"
LE_ADVERTISEMENT = "org.bluez.LEAdvertisement1"


def word_to_bluez_uuid(word: int) -> str:
    return f"0000{word:04x}-0000-1000-8000-00805f9b34fb"


class LinuxBlueZAdvertiser:
    def send_burst(self, command: Command) -> None:
        asyncio.run(self._send_burst(command))

    async def _send_burst(self, command: Command) -> None:
        try:
            from dbus_next.aio import MessageBus
            from dbus_next.constants import BusType, PropertyAccess
            from dbus_next.service import ServiceInterface, dbus_property, method
        except ImportError as exc:
            raise RuntimeError(
                "Linux backend needs dbus-next. Install with:\n"
                "  pip install -r requirements-linux.txt"
            ) from exc

        class FanAdvertisement(ServiceInterface):
            def __init__(self, index: int, words: tuple[int, ...]) -> None:
                self._uuids = [word_to_bluez_uuid(word) for word in words]
                self._path = f"/org/jingyuan/fan/advertisement{index}"
                super().__init__(LE_ADVERTISEMENT)

            def get_path(self) -> str:
                return self._path

            @dbus_property(access=PropertyAccess.READ)
            def Type(self) -> "s":
                return "peripheral"

            @dbus_property(access=PropertyAccess.READ)
            def ServiceUUIDs(self) -> "as":
                return self._uuids

            @dbus_property(access=PropertyAccess.READ)
            def IncludeTxPower(self) -> "b":
                return False

            @method()
            def Release(self) -> "":  # noqa: N802
                pass

        bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        adapter_path = await self._find_adapter(bus)
        manager = await bus.introspect(BLUEZ_SERVICE, adapter_path)
        manager_proxy = bus.get_proxy_object(BLUEZ_SERVICE, adapter_path, manager)
        advertising_manager = manager_proxy.get_interface(LE_ADVERTISING_MANAGER)

        print(f"Broadcasting {command.name}...", file=sys.stderr)
        for index, (words, hold_s) in enumerate(burst_steps(command)):
            advertisement = FanAdvertisement(index, words)
            bus.export(advertisement.get_path(), advertisement)
            await advertising_manager.call_register_advertisement(
                advertisement.get_path(),
                {},
            )
            await asyncio.sleep(hold_s)
            await advertising_manager.call_unregister_advertisement(advertisement.get_path())

        print(f"Sent {command.name}", file=sys.stderr)

    async def _find_adapter(self, bus) -> str:
        introspection = await bus.introspect(BLUEZ_SERVICE, "/")
        root = bus.get_proxy_object(BLUEZ_SERVICE, "/", introspection)
        object_manager = root.get_interface("org.freedesktop.DBus.ObjectManager")
        managed = await object_manager.call_get_managed_objects()
        for path, interfaces in managed.items():
            if ADAPTER_INTERFACE in interfaces:
                return str(path)
        raise RuntimeError("No Bluetooth adapter found. Is BlueZ running?")
