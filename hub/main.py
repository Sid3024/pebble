import asyncio
from ble.scanner import scan_for_pebbles
from ble.client import PebbleClient

SCAN_TIMEOUT = 10.0  # seconds


async def main():
    print(f"[HUB] Scanning for Pebble devices ({SCAN_TIMEOUT}s)...")
    devices = await scan_for_pebbles(timeout=SCAN_TIMEOUT)

    if not devices:
        print("[HUB] No Pebble devices found.")
        return

    print(f"[HUB] Found {len(devices)}: {[d.name for d in devices]}")

    # Connect to all devices concurrently.
    clients = [PebbleClient(d) for d in devices]
    await asyncio.gather(*[c.run() for c in clients])


if __name__ == "__main__":
    asyncio.run(main())
