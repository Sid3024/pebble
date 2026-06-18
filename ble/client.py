"""
BLE client that manages a persistent connection to a single Pebble sensor pod.

This module contains PebbleClient, the core BLE communication class.  One
PebbleClient instance is created per discovered pod.  It handles three jobs:

    1. **Receive IMU data** -- subscribes to GATT notifications on the
       WINDOW_CHAR_UUID characteristic.  The firmware sends a 4-byte
       little-endian float (the "window sum") roughly every 250 ms.
       Each notification is forwarded to the game controller via
       controller.process_window(device_name, window_sum).

    2. **Send vibration commands** -- once per second, polls the controller
       for any queued vibration pattern IDs and writes each one (as a single
       byte) to the pod's COMMAND_CHAR_UUID characteristic.

    3. **Auto-reconnect** -- if the BLE connection drops or an error occurs,
       waits 5 seconds and retries indefinitely.  This makes the system
       resilient to temporary range issues or pod restarts.

Dependencies:
    - bleak   : Cross-platform async BLE library (BleakClient).
    - struct  : Standard library -- unpacks the 4-byte float from the BLE payload.

How it fits into Pebble:
    FlowerGame.main (or any game backend) discovers pods via scanner.py, then
    creates one PebbleClient per pod and runs them all as concurrent asyncio
    tasks.  The *controller* argument is any object with a process_window()
    method (e.g. FlowerWSServer, FlowerController).
"""

import asyncio
import struct

from bleak import BleakClient

from .constants import WINDOW_CHAR_UUID, COMMAND_CHAR_UUID


class PebbleClient:
    """
    Manages the BLE connection to a single Pebble pod.

    Lifecycle:
        1. Created with a bleak BLEDevice and a game controller reference.
        2. run() is called as an asyncio task -- it connects, subscribes, and
           loops forever (with auto-reconnect on failure).
        3. On each GATT notification the pod sends, _on_window() unpacks the
           float and forwards it to the controller.
        4. Every 1 second, any pending vibration commands are popped from the
           controller and written back to the pod.

    Attributes:
        name: The BLE advertising name of the pod (e.g. "Pebble_01").
    """

    def __init__(self, device, controller) -> None:
        """
        Args:
            device:     A bleak BLEDevice returned by the scanner.
            controller: Any object with process_window(device_name, window_sum)
                        and optionally pop_vibration_commands(device_name).
        """
        self._device     = device         # bleak BLEDevice handle
        self.name        = device.name    # e.g. "Pebble_01"
        self._controller = controller     # game controller or WS server proxy

    def _on_window(self, _sender, data: bytearray) -> None:
        """
        GATT notification callback -- fired each time the pod sends a window sum.

        The firmware packs the window sum as a single little-endian 32-bit float
        (4 bytes).  We unpack it and forward to the controller's process_window().
        Any exception is caught and logged so one bad packet does not kill the task.

        Args:
            _sender: The bleak characteristic handle (unused).
            data:    Raw bytes received from the pod (expected: 4 bytes, "<f").
        """
        try:
            (window_sum,) = struct.unpack("<f", bytes(data))
            self._controller.process_window(self.name, window_sum)
        except Exception as exc:
            print(f"[{self.name}] ERROR in window callback: {exc}")

    def _pop_vibration_commands(self) -> list[int]:
        """
        Ask the controller for any queued vibration pattern IDs for this pod.

        Uses getattr() because not all controllers implement
        pop_vibration_commands() (e.g. a minimal test stub might not).

        Returns:
            A list of integer pattern IDs to write to the pod, or [].
        """
        fn = getattr(self._controller, "pop_vibration_commands", None)
        return fn(self.name) if fn else []

    async def _send_command(self, client: BleakClient, pattern_id: int) -> None:
        """
        Write a single vibration pattern ID to the pod's command characteristic.

        Uses response=True (write-with-response) so we know the pod acknowledged.
        Errors are logged but do not propagate -- a failed vibration is not fatal.

        Args:
            client:     An active BleakClient connection.
            pattern_id: One of the VIBR_* constants from ble.constants.
        """
        try:
            await client.write_gatt_char(
                COMMAND_CHAR_UUID, bytes([pattern_id]), response=True)
            print(f"[{self.name}] vibration pattern {pattern_id} sent")
        except Exception as exc:
            print(f"[{self.name}] vibration send failed: {exc}")

    async def run(self) -> None:
        """
        Main loop: connect, subscribe, relay data, and auto-reconnect forever.

        Algorithm:
            1. Open a BLE connection to the pod (async context manager).
            2. Subscribe to WINDOW_CHAR_UUID notifications (calls _on_window).
            3. Enter a polling loop:
               - Pop any pending vibration commands from the controller.
               - Write each command to the pod.
               - Sleep 1 second, then repeat.
            4. If the connection drops or any error occurs, wait RETRY_DELAY
               seconds and go back to step 1.
            5. asyncio.CancelledError is re-raised so the task can be cleanly
               cancelled at shutdown.
        """
        RETRY_DELAY = 5.0   # seconds to wait before reconnecting after failure
        while True:
            try:
                async with BleakClient(self._device) as client:
                    print(f"[{self.name}] connected")
                    await client.start_notify(WINDOW_CHAR_UUID, self._on_window)
                    print(f"[{self.name}] subscribed to window notifications")

                    # Stay connected: poll for vibration commands every 1 second.
                    while client.is_connected:
                        for cmd in self._pop_vibration_commands():
                            await self._send_command(client, cmd)
                        await asyncio.sleep(1.0)

                print(f"[{self.name}] disconnected — retrying in {RETRY_DELAY:.0f}s")
            except asyncio.CancelledError:
                raise   # honour task cancellation
            except Exception as exc:
                print(f"[{self.name}] error: {exc} — retrying in {RETRY_DELAY:.0f}s")
            await asyncio.sleep(RETRY_DELAY)
