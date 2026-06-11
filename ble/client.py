import asyncio
import time

from bleak import BleakClient

from .constants import WINDOW_CHAR_UUID, COMMAND_CHAR_UUID
from .imu import parse_imu_window


class PebbleClient:
    """
    Manages the BLE connection to a single Pebble pod.

    - Forwards IMU window notifications to the game controller via
      process_imu_window(device_name, imu_window) when available.
    - Falls back to process_window(device_name, effort_value) for older games.
    - Polls the controller for pending vibration commands once per second
      and writes them to the pod's command characteristic.
    - Auto-reconnects on disconnect or error.
    """

    def __init__(self, device, controller, name: str | None = None) -> None:
        self._device     = device
        address = getattr(device, "address", None) or str(device)
        suffix = str(address)[-8:].replace(":", "")
        self.name        = name or getattr(device, "name", None) or f"Pebble_{suffix}"
        self._controller = controller
        self._last_window_seen = 0.0

    def _on_window(self, _sender, data: bytearray) -> None:
        try:
            imu_window = parse_imu_window(bytes(data))
            self._last_window_seen = time.monotonic()
            print(f"[{self.name}] imu activity={imu_window.shake_score:.3f} "
                  f"move={imu_window.movement_magnitude:.3f} gyro={imu_window.gyro_magnitude:.1f}")
            fn = getattr(self._controller, "process_imu_window", None)
            if fn:
                fn(self.name, imu_window)
            else:
                self._controller.process_window(self.name, imu_window.effort_fallback)
        except Exception as exc:
            print(f"[{self.name}] ERROR in window callback: {exc}")

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

    async def run(self) -> None:
        RETRY_DELAY = 5.0
        while True:
            try:
                async with BleakClient(self._device) as client:
                    print(f"[{self.name}] connected")
                    await client.start_notify(WINDOW_CHAR_UUID, self._on_window)
                    print(f"[{self.name}] subscribed to window notifications")
                    self._last_window_seen = time.monotonic()

                    while client.is_connected:
                        for cmd in self._pop_vibration_commands():
                            await self._send_command(client, cmd)
                        if time.monotonic() - self._last_window_seen > 5.0:
                            print(f"[{self.name}] connected, but no IMU windows received for 5 s. "
                                  "Check MPU6050 wiring/init and pod serial logs.")
                            self._last_window_seen = time.monotonic()
                        await asyncio.sleep(1.0)

                print(f"[{self.name}] disconnected — retrying in {RETRY_DELAY:.0f}s")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"[{self.name}] error: {exc} — retrying in {RETRY_DELAY:.0f}s")
            await asyncio.sleep(RETRY_DELAY)
