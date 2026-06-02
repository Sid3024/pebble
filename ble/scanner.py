from bleak import BleakScanner
from bleak.backends.device import BLEDevice

from .constants import PEBBLE_NAME_PREFIX, PEBBLE_LED_NAME_PREFIX


async def scan_for_pebbles(timeout: float = 10.0) -> list[BLEDevice]:
    """Scan for game pod MCUs (prefix: Pebble_)."""
    devices = await BleakScanner.discover(timeout=timeout)
    return [d for d in devices if d.name and d.name.startswith(PEBBLE_NAME_PREFIX)]


async def scan_for_led_display(timeout: float = 10.0) -> list[BLEDevice]:
    """Scan for the LED display MCU (prefix: PebbleLED_)."""
    devices = await BleakScanner.discover(timeout=timeout)
    return [d for d in devices if d.name and d.name.startswith(PEBBLE_LED_NAME_PREFIX)]
