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
from .engine.controller import FlowerController
from .ws.server import FlowerWSServer


async def _run_with_ble(controller: FlowerController, config: FlowerConfig) -> None:
    from ble.scanner import scan_for_pebbles
    from .ble.client import PebbleClient

    print(f"[HUB] Scanning for Pebble pods ({config.ble_scan_timeout}s)...")
    devices = await scan_for_pebbles(timeout=config.ble_scan_timeout)

    if not devices:
        print("[HUB] No Pebble pods found. Exiting.")
        return

    print(f"[HUB] Found {len(devices)}: {[d.name for d in devices]}")
    clients = [PebbleClient(d, controller) for d in devices]
    await asyncio.gather(*[c.run() for c in clients])


async def _run_with_simulator(
    controller: FlowerController, config: FlowerConfig, num_pods: int
) -> None:
    from .simulator import run_simulated_pods

    controller.start_session()
    await run_simulated_pods(controller, num_pods=num_pods)


async def main(simulate: bool = False, sim_pods: int = 3) -> None:
    config = FlowerConfig()
    controller = FlowerController(config)
    ws_server = FlowerWSServer(controller, config)

    print("=" * 55)
    print("  Pebble Garden — Flower Game")
    print("=" * 55)
    print(f"  Open GameDashboard/index.html in your browser.")
    print(f"  WebSocket: ws://{config.ws_host}:{config.ws_port}")
    print("=" * 55)

    game_task = asyncio.create_task(
        _run_with_simulator(controller, config, sim_pods)
        if simulate
        else _run_with_ble(controller, config)
    )

    try:
        await asyncio.gather(ws_server.run(), game_task)
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
