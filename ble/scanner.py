"""
BLE device scanner for Pebble pods and LED displays.

This module provides async helper functions that use the ``bleak`` library to
discover nearby BLE devices and return only those whose advertising names match
the Pebble naming convention (defined in constants.py).

How it works:
    1. BleakScanner.discover() runs a passive BLE scan for ``timeout`` seconds,
       collecting every BLE advertisement it hears.
    2. The returned list is filtered by advertising name prefix:
       - "Pebble_"     for IMU sensor pods
       - "PebbleLED_"  for the LED display MCU
    3. Only matching BLEDevice objects are returned to the caller.

Dependencies:
    - bleak : Cross-platform async BLE library.

How it fits into Pebble:
    FlowerGame.main calls scan_for_pebbles() at startup to discover all sensor
    pods, then creates one PebbleClient per discovered device.  scan_for_led_display()
    is used similarly when the LED display feature is active.
"""

from bleak import BleakScanner
from bleak.backends.device import BLEDevice

from .constants import PEBBLE_NAME_PREFIX, PEBBLE_LED_NAME_PREFIX


async def scan_for_pebbles(timeout: float = 10.0) -> list[BLEDevice]:
    """
    Scan for IMU sensor pods whose BLE name starts with "Pebble_".

    Runs a BLE discovery for *timeout* seconds and returns a list of BLEDevice
    objects representing every detected pod.  An empty list means no pods were
    found (could be powered off, out of range, or already connected elsewhere).

    Args:
        timeout: How many seconds to listen for BLE advertisements (default 10).

    Returns:
        A list of bleak BLEDevice objects for all discovered Pebble pods.
    """
    devices = await BleakScanner.discover(timeout=timeout)
    return [d for d in devices if d.name and d.name.startswith(PEBBLE_NAME_PREFIX)]


async def scan_for_led_display(timeout: float = 10.0) -> list[BLEDevice]:
    """
    Scan for the LED display MCU whose BLE name starts with "PebbleLED_".

    Works identically to scan_for_pebbles() but filters for the LED display
    name prefix instead.

    Args:
        timeout: How many seconds to listen for BLE advertisements (default 10).

    Returns:
        A list of bleak BLEDevice objects for all discovered LED displays
        (typically zero or one).
    """
    devices = await BleakScanner.discover(timeout=timeout)
    return [d for d in devices if d.name and d.name.startswith(PEBBLE_LED_NAME_PREFIX)]
