import asyncio
import struct
from bleak import BleakClient
from .constants import WINDOW_CHAR_UUID


class PebbleClient:
    """
    Manages the BLE connection to a single Pebble device.
    Subscribes to window-sum notifications and prints them as they arrive.
    """

    def __init__(self, device):
        self._device = device
        self.name = device.name

    def _on_window(self, _sender, data: bytearray):
        # Payload is a 4-byte little-endian float.
        (window_sum,) = struct.unpack('<f', bytes(data))
        print(f"[{self.name}] window sum = {window_sum:.4f} g")

    async def run(self):
        async with BleakClient(self._device) as client:
            print(f"[{self.name}] connected")
            await client.start_notify(WINDOW_CHAR_UUID, self._on_window)
            # Hold the connection open until the device disconnects.
            while client.is_connected:
                await asyncio.sleep(1.0)
        print(f"[{self.name}] disconnected")
