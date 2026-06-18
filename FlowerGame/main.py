"""
FlowerGame entry point -- top-level orchestrator that wires BLE and WebSocket together.

This module is the main executable for the FlowerGame backend.  It can be run
directly (``python FlowerGame/main.py``) or via the package entry point
(``python -m FlowerGame``).

Usage (from pebble/ root):
    python -m FlowerGame                        # real hardware
    python -m FlowerGame --simulate             # 3 simulated pods
    python -m FlowerGame --simulate --sim-pods 4

What it does:
    1. Parses CLI arguments (--simulate, --sim-pods).
    2. Creates a FlowerConfig (all default tuning parameters).
    3. Creates a FlowerWSServer (WebSocket server + session orchestrator).
    4. Starts two concurrent asyncio tasks:
       a. The WebSocket server (serves the dashboard and broadcasts game state).
       b. Either real BLE pod connections or a simulated pod generator.
    5. Runs until cancelled (Ctrl-C).

How BLE mode works:
    - Scans for pods via ble.scanner.scan_for_pebbles().
    - Creates one PebbleClient per pod, passing the WS server as the controller.
    - Each PebbleClient runs its own asyncio task (connect, subscribe, relay).

How simulation mode works:
    - Launches N simulated pods via simulator.run_simulated_pods().
    - Each pod generates synthetic window sums on a timer and feeds them into
      the WS server's process_window() method.

Dependencies:
    - argparse  : CLI argument parsing.
    - asyncio   : Async event loop for concurrent BLE + WS tasks.
"""
from __future__ import annotations

import argparse
import asyncio

from .config.config import FlowerConfig
from .ws.server import FlowerWSServer


async def _run_with_ble(server: FlowerWSServer, config: FlowerConfig) -> None:
    """
    Discover real Pebble pods via BLE and run a client for each one.

    Steps:
        1. Use scan_for_pebbles() to discover pods within range.
        2. If none found, print a message and return (game cannot proceed).
        3. Create a PebbleClient per pod (the WS server acts as the controller).
        4. Run all clients concurrently via asyncio.gather -- each client
           handles its own connection, notifications, and vibration commands.

    Args:
        server: The FlowerWSServer instance that proxies process_window()
                to the active game controller.
        config: FlowerConfig with BLE scan timeout and other settings.
    """
    from ble.scanner import scan_for_pebbles
    from .ble.client import PebbleClient

    print(f"[HUB] Scanning for Pebble pods ({config.ble_scan_timeout}s)...")
    devices = await scan_for_pebbles(timeout=config.ble_scan_timeout)

    if not devices:
        print("[HUB] No Pebble pods found. Exiting.")
        return

    print(f"[HUB] Found {len(devices)}: {[d.name for d in devices]}")
    clients = [PebbleClient(d, server) for d in devices]
    await asyncio.gather(*[c.run() for c in clients])


async def _run_with_simulator(server: FlowerWSServer, num_pods: int) -> None:
    """
    Launch simulated pods for hardware-free testing.

    Delegates to simulator.run_simulated_pods() which creates N async tasks,
    each feeding synthetic window sums into the server's process_window().

    Args:
        server:   The FlowerWSServer instance acting as controller proxy.
        num_pods: How many simulated pods to create.
    """
    from .simulator import run_simulated_pods
    await run_simulated_pods(server, num_pods=num_pods)


async def main(simulate: bool = False, sim_pods: int = 3) -> None:
    """
    Async entry point: create config + WS server, then run BLE and WS concurrently.

    Args:
        simulate: If True, use simulated pods instead of real BLE hardware.
        sim_pods: Number of simulated pods (only used when simulate=True).
    """
    config = FlowerConfig()
    server = FlowerWSServer(config)

    # Print a startup banner so the user knows where to connect.
    print("=" * 55)
    print("  Pebble Garden — Flower Game")
    print("=" * 55)
    print(f"  Open GameDashboard/index.html in your browser.")
    print(f"  WebSocket: ws://{config.ws_host}:{config.ws_port}")
    print("=" * 55)

    # Choose between real hardware and simulation.
    ble_coro = (
        _run_with_simulator(server, sim_pods)
        if simulate
        else _run_with_ble(server, config)
    )

    # Run the WS server and the BLE/sim data source concurrently.
    # Both run forever; CancelledError (Ctrl-C) is the normal exit path.
    try:
        await asyncio.gather(server.run(), ble_coro)
    except asyncio.CancelledError:
        pass


def cli() -> None:
    """
    Synchronous CLI wrapper: parse arguments and call asyncio.run(main(...)).

    This is the function invoked by __main__.py.
    """
    parser = argparse.ArgumentParser(description="Pebble Flower Game backend.")
    parser.add_argument("--simulate", action="store_true",
                        help="Run without hardware using simulated pods.")
    parser.add_argument("--sim-pods", type=int, default=3, metavar="N",
                        help="Number of simulated pods (default: 3).")
    args = parser.parse_args()
    asyncio.run(main(simulate=args.simulate, sim_pods=args.sim_pods))


if __name__ == "__main__":
    cli()
