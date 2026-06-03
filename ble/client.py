import asyncio
import struct

from typing import Any

from bleak import BleakClient
from bleak.backends.device import BLEDevice

from .constants import WINDOW_CHAR_UUID, COMMAND_CHAR_UUID


class PebbleClient:
    """
    Manages the BLE connection to a single Pebble pod.

    - Forwards window-sum notifications to the game controller via
      process_window(device_name, window_sum).
    - Polls the controller for pending vibration commands once per second
      and writes them to the pod's command characteristic.
      Works with any controller that implements
      pop_vibration_commands(device_name) -> list[int].
    - Auto-reconnects on disconnect or error.
    """

    def __init__(self, device: BLEDevice, controller: Any) -> None:
        self._device: BLEDevice = device
        self.name        = device.name
        self._controller = controller

    # ── Window notification ───────────────────────────────────

    def _on_window(self, _sender, data: bytearray) -> None:
        try:
            (window_sum,) = struct.unpack("<f", bytes(data))
            self._controller.process_window(self.name, window_sum)
        except Exception as exc:
            print(f"[{self.name}] ERROR in window callback: {exc}")

    # ── Vibration commands ────────────────────────────────────

    def _pop_vibration_commands(self) -> list[int]:
        fn = getattr(self._controller, "pop_vibration_commands", None)
        return fn(self.name) if fn else []

    async def _send_command(self, client: BleakClient, pattern_id: int) -> None:
        try:
            await client.write_gatt_char(
                COMMAND_CHAR_UUID, bytes([pattern_id]), response=True)
            print(f"[{self.name}] vibration pattern {pattern_id} sent")
        except Exception as exc:
            print(f"[{self.name}] vibration send failed: {exc}")

    # ── Main loop ─────────────────────────────────────────────

    async def run(self) -> None:
        RETRY_DELAY = 5.0
        # Use the address string, not the device object — each reconnect then
        # performs fresh GATT discovery instead of reusing a stale cached profile,
        # which avoids silent failures when the MCU reboots mid-session.
        address = self._device.address
        while True:
            try:
                async with BleakClient(address, timeout=20.0) as client:
                    print(f"[{self.name}] connected")
                    await client.start_notify(WINDOW_CHAR_UUID, self._on_window)
                    print(f"[{self.name}] subscribed to window notifications")

                    while client.is_connected:
                        for cmd in self._pop_vibration_commands():
                            await self._send_command(client, cmd)
                        await asyncio.sleep(1.0)

                print(f"[{self.name}] disconnected — retrying in {RETRY_DELAY:.0f}s")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"[{self.name}] error: {exc} — retrying in {RETRY_DELAY:.0f}s")
            await asyncio.sleep(RETRY_DELAY)
