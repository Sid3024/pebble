from bleak import BleakScanner
from .constants import PEBBLE_NAME_PREFIX


async def scan_for_pebbles(timeout: float = 10.0) -> list:
    """Scan for BLE devices whose name starts with PEBBLE_NAME_PREFIX."""
    devices = await BleakScanner.discover(timeout=timeout)
    return [d for d in devices if d.name and d.name.startswith(PEBBLE_NAME_PREFIX)]
