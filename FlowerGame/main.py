"""
FlowerGame entry point.

Usage (from pebble/ root):
    python -m FlowerGame
    python -m FlowerGame --simulate
    python -m FlowerGame --simulate --sim-pods 4
"""
from __future__ import annotations

import argparse
import asyncio

from .config.config import FlowerConfig
from .ws.server import FlowerWSServer


async def _run_with_ble(server: FlowerWSServer, config: FlowerConfig) -> None:
    from ble.scanner import scan_for_pebbles
    from .ble.client import PebbleClient

    print(f"[HUB] Scanning for Pebble pods ({config.ble_scan_timeout}s)...")
    devices = await scan_for_pebbles(timeout=config.ble_scan_timeout, debug=True)

    if not devices:
        print("[HUB] No Pebble pods found. Exiting.")
        return

    print(f"[HUB] Found {len(devices)}: {[d.name for d in devices]}")
    clients = [PebbleClient(d, server) for d in devices]
    await asyncio.gather(*[c.run() for c in clients])


async def _run_with_simulator(server: FlowerWSServer, num_pods: int) -> None:
    from .simulator import run_simulated_pods
    await run_simulated_pods(server, num_pods=num_pods)


async def main(simulate: bool = False, sim_pods: int = 3) -> None:
    config = FlowerConfig()
    server = FlowerWSServer(config)

    print("=" * 55)
    print("  Pebble Garden — Flower Game")
    print("=" * 55)
    print(f"  Open GameDashboard/index.html in your browser.")
    print(f"  WebSocket: ws://{config.ws_host}:{config.ws_port}")
    print("=" * 55)

    ble_coro = (
        _run_with_simulator(server, sim_pods)
        if simulate
        else _run_with_ble(server, config)
    )

    try:
        await asyncio.gather(server.run(), ble_coro)
    except asyncio.CancelledError:
        pass


def cli() -> None:
    parser = argparse.ArgumentParser(description="Pebble Flower Game backend.")
    parser.add_argument("--simulate", action="store_true",
                        help="Run without hardware using simulated pods.")
    parser.add_argument("--sim-pods", type=int, default=3, metavar="N",
                        help="Number of simulated pods (default: 3).")
    args = parser.parse_args()
    asyncio.run(main(simulate=args.simulate, sim_pods=args.sim_pods))


if __name__ == "__main__":
    cli()
