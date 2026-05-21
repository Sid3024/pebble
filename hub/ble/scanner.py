from bleak import BleakScanner
from .constants import PEBBLE_NAME_PREFIX


async def scan_for_pebbles(timeout: float = 10.0) -> list:
    """
    Scan for BLE devices whose name starts with PEBBLE_NAME_PREFIX.
    Returns a list of BLEDevice objects.
    """
    devices = await BleakScanner.discover(timeout=timeout)
    found = [d for d in devices if d.name and d.name.startswith(PEBBLE_NAME_PREFIX)]
    return found
