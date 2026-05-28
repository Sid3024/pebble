import asyncio
import struct

from bleak import BleakClient

from .constants import WINDOW_CHAR_UUID


class PebbleClient:
    """
    Manages the BLE connection to a single Pebble pod.
    Forwards each window-sum notification to the game controller.

    Any controller that implements process_window(device_name, window_sum)
    can be passed — VolumeController, FlowerController, etc.
    """

    def __init__(self, device, controller) -> None:
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
        """Connect and auto-reconnect on disconnect or error."""
        RETRY_DELAY = 5.0
        while True:
            try:
                async with BleakClient(self._device) as client:
                    print(f"[{self.name}] connected")
                    await client.start_notify(WINDOW_CHAR_UUID, self._on_window)
                    print(f"[{self.name}] subscribed to window notifications")
                    while client.is_connected:
                        await asyncio.sleep(1.0)
                print(f"[{self.name}] disconnected — retrying in {RETRY_DELAY:.0f}s")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"[{self.name}] error: {exc} — retrying in {RETRY_DELAY:.0f}s")
            await asyncio.sleep(RETRY_DELAY)
