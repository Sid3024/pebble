import asyncio
import struct

from bleak import BleakClient

from ble.constants import WINDOW_CHAR_UUID
from ..engine.controller import FlowerController


class PebbleClient:
    """
    FlowerGame BLE client — wraps the shared ble.client pattern but
    typed to FlowerController for clarity.
    """

    def __init__(self, device, controller: FlowerController) -> None:
        self._device = device
        self.name = device.name
        self._controller = controller

    def _on_window(self, _sender, data: bytearray) -> None:
        try:
            (window_sum,) = struct.unpack("<f", bytes(data))
            self._controller.process_window(self.name, window_sum)
        except Exception as exc:
            print(f"[{self.name}] ERROR in window callback: {exc}")

    async def run(self) -> None:
        async with BleakClient(self._device) as client:
            print(f"[{self.name}] connected")
            await client.start_notify(WINDOW_CHAR_UUID, self._on_window)
            print(f"[{self.name}] subscribed to window notifications")
            while client.is_connected:
                await asyncio.sleep(1.0)
        print(f"[{self.name}] disconnected")
