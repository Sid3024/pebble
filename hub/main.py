import asyncio

from hub.config.config import Config
from hub.volume.volume import build_volume_backend, RateLimitedVolume
from hub.effort.controller import VolumeController
from ble.scanner import load_known_pods, scan_for_pebbles
from ble.client import PebbleClient

SCAN_TIMEOUT = 10.0  # seconds


async def main():
    config = Config()
    backend = build_volume_backend()
    volume = RateLimitedVolume(backend)
    controller = VolumeController(config, volume)
    known: set[str] = set()
    cached_pods = load_known_pods()
    if cached_pods:
        print(f"[HUB] Known pod address(es): {[pod['address'] for pod in cached_pods]}")

    print(f"[HUB] Scanning for Pebble devices ({SCAN_TIMEOUT}s)...")

    async def scan_and_connect() -> None:
        devices = await scan_for_pebbles(timeout=SCAN_TIMEOUT, debug=True)
        new_devices = [d for d in devices if d.address not in known]

        if new_devices:
            print(f"[HUB] Found {len(new_devices)} new pod(s): {[d.name or d.address for d in new_devices]}")
        for device in new_devices:
            known.add(device.address)
            asyncio.create_task(PebbleClient(device, controller).run())

        if new_devices:
            return

        for pod in load_known_pods():
            address = pod["address"]
            if address in known:
                continue
            print(f"[HUB] Scan missed pod, trying known address {address} directly...")
            known.add(address)
            asyncio.create_task(PebbleClient(address, controller, name=pod.get("name")).run())

    await scan_and_connect()
    if not known:
        print("[HUB] No Pebble devices found on initial scan - will keep checking every 15 s.")

    while True:
        await asyncio.sleep(15.0)
        await scan_and_connect()


if __name__ == "__main__":
    asyncio.run(main())
