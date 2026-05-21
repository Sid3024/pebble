import asyncio
import struct
from bleak import BleakClient
from .constants import WINDOW_CHAR_UUID
from effort.controller import VolumeController


class PebbleClient:
    """
    Manages the BLE connection to a single Pebble device.
    Forwards each window-sum notification to the VolumeController.
    """

    def __init__(self, device, controller: VolumeController) -> None:
        self._device = device
        self.name = device.name
        self._controller = controller

    def _on_window(self, _sender, data: bytearray) -> None:
        try:
            (window_sum,) = struct.unpack('<f', bytes(data))
            self._controller.process_window(self.name, window_sum)
        except Exception as e:
            print(f"[{self.name}] ERROR in window callback: {e}")

    async def run(self) -> None:
        async with BleakClient(self._device) as client:
            print(f"[{self.name}] connected")
            services = client.services
            has_char = any(
                str(c.uuid).lower() == WINDOW_CHAR_UUID.lower()
                for s in services for c in s.characteristics
            )
            print(f"[{self.name}] window characteristic present: {has_char}")
            await client.start_notify(WINDOW_CHAR_UUID, self._on_window)
            print(f"[{self.name}] subscribed to window notifications")
            while client.is_connected:
                await asyncio.sleep(1.0)
        print(f"[{self.name}] disconnected")
