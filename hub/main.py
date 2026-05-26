import asyncio

from hub.config.config import Config
from hub.volume.volume import build_volume_backend, RateLimitedVolume
from hub.effort.controller import VolumeController
from ble.scanner import scan_for_pebbles
from ble.client import PebbleClient

SCAN_TIMEOUT = 10.0  # seconds


async def main():
    config = Config()
    backend = build_volume_backend()
    volume = RateLimitedVolume(backend)
    controller = VolumeController(config, volume)

    print(f"[HUB] Scanning for Pebble devices ({SCAN_TIMEOUT}s)...")
    devices = await scan_for_pebbles(timeout=SCAN_TIMEOUT)

    if not devices:
        print("[HUB] No Pebble devices found.")
        return

    print(f"[HUB] Found {len(devices)}: {[d.name for d in devices]}")

    clients = [PebbleClient(d, controller) for d in devices]
    await asyncio.gather(*[c.run() for c in clients])


if __name__ == "__main__":
    asyncio.run(main())
