"""
BLE client that manages a persistent connection to a single Pebble sensor pod.

One PebbleClient instance is created per discovered pod.  It handles three jobs:

    1. **Receive IMU data** -- subscribes to GATT notifications on the IMU
       characteristic.  The firmware sends a 20-byte packet every 250ms
       containing ax, ay, az, gx, gy, gz, roll, pitch.  Each notification
       is parsed into an ImuWindow and forwarded to the game controller.

    2. **Send vibration commands** -- polls the controller for queued vibration
       pattern IDs and writes each one to the pod's command characteristic.

    3. **Auto-reconnect** -- if the BLE connection drops, waits and retries
       indefinitely.  This makes the system resilient to range issues or
       pod restarts.

Dependencies:
    - bleak : Cross-platform async BLE library (BleakClient).
    - ble.imu : ImuWindow parsing from raw BLE bytes.

How it fits into Pebble:
    FlowerGame.main discovers pods via scanner.py, then creates one
    PebbleClient per pod and runs them all as concurrent asyncio tasks.
"""

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

    _STATUS_MESSAGES = {
        0x01: "IMU offline — no I2C devices found. Check SDA/SCL/VCC wiring.",
        0x02: "IMU init failed — device found but init returned false.",
        0x03: "IMU lost — repeated read failures during operation.",
    }

    def _on_window(self, _sender, data: bytearray) -> None:
        # Status/error packet from firmware (magic=0xE1, error_code)
        if data and data[0] == 0xE1:
            code = data[1] if len(data) > 1 else 0
            msg = self._STATUS_MESSAGES.get(code, f"unknown firmware status 0x{code:02X}")
            print(f"[{self.name}] FIRMWARE: {msg}")
            return

        try:
            imu_window = parse_imu_window(bytes(data))
            self._last_window_seen = time.monotonic()
            print(f"[{self.name}] activity={imu_window.shake_score:.3f} "
                  f"accel(ax={imu_window.ax:.3f}, ay={imu_window.ay:.3f}, az={imu_window.az:.3f}) "
                  f"gyro(gx={imu_window.gx:.1f}, gy={imu_window.gy:.1f}, gz={imu_window.gz:.1f}) "
                  f"angle(roll={imu_window.roll:.1f}, pitch={imu_window.pitch:.1f})")
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
                    print(f"[{self.name}] connected (mtu={client.mtu_size})")
                    # Give the BLE stack time to finish MTU/connection-parameter
                    # negotiation before subscribing. Subscribing immediately
                    # after connect can race with that negotiation and cause
                    # the very first notification to arrive truncated to just
                    # the 3-byte ATT header instead of the 20-byte payload.
                    await asyncio.sleep(0.5)
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
