"""
Pebble launcher — run from the pebble/ root with the venv active.

    python run.py flower        # flower game only
    python run.py volume        # volume game only
    python run.py both          # both simultaneously (one BLE connection per pod)
    python run.py flower --simulate
    python run.py both   --simulate --sim-pods 4
"""
from __future__ import annotations

import argparse
import asyncio


# ── Multi-controller fan-out ──────────────────────────────────────────────────

class MultiController:
    """Forwards every window to multiple game controllers."""

    def __init__(self, *controllers) -> None:
        self._controllers = controllers

    def process_window(self, device_name: str, window_sum: float) -> None:
        for ctrl in self._controllers:
            ctrl.process_window(device_name, window_sum)


# ── BLE helpers ───────────────────────────────────────────────────────────────

async def _connect_ble(controller, scan_timeout: float) -> None:
    from ble.scanner import scan_for_pebbles
    from ble.client import PebbleClient

    known: set[str] = set()   # BLE addresses already spawned

    async def scan_and_connect() -> None:
        devices = await scan_for_pebbles(timeout=scan_timeout)
        new = [d for d in devices if d.address not in known]
        if new:
            print(f"[BLE] Found {len(new)} new pod(s): {[d.name for d in new]}")
            for d in new:
                known.add(d.address)
                asyncio.create_task(PebbleClient(d, controller).run())

    print(f"[BLE] Scanning for Pebble pods ({scan_timeout}s)…")
    await scan_and_connect()

    if not known:
        print("[BLE] No pods found on initial scan — will keep checking every 15 s.")

    # Periodically re-scan so pods that appear later are picked up automatically.
    while True:
        await asyncio.sleep(15.0)
        await scan_and_connect()


async def _simulate_ble(controller, num_pods: int) -> None:
    from FlowerGame.simulator import run_simulated_pods
    await run_simulated_pods(controller, num_pods=num_pods)


async def _connect_led(state_getter, scan_timeout: float) -> None:
    # Delay until the game-pod scan has finished — two concurrent
    # BleakScanner.discover() calls on Windows conflict and return nothing.
    await asyncio.sleep(scan_timeout + 2.0)

    try:
        from ble.scanner import scan_for_led_display
        from LEDLight.client import LEDClient
    except ImportError:
        return   # LEDLight module not present

    try:
        print(f"[LED] Scanning for LED display ({scan_timeout}s)...")
        devices = await scan_for_led_display(timeout=scan_timeout)
    except Exception as exc:
        print(f"[LED] Scan failed: {exc}")
        return

    if not devices:
        print("[LED] No LED display found — running without light strip.")
        return

    print(f"[LED] Found: {devices[0].name}")
    try:
        await LEDClient(devices[0]).run(state_getter)
    except Exception as exc:
        print(f"[LED] Client error: {exc}")


# ── Game builders ─────────────────────────────────────────────────────────────

def _build_flower():
    from FlowerGame.config.config import FlowerConfig
    from FlowerGame.ws.server import FlowerWSServer

    config = FlowerConfig()
    server = FlowerWSServer(config)
    return server, server.run(), config


def _build_hub():
    from hub.config.config import Config
    from hub.volume.volume import build_volume_backend, RateLimitedVolume
    from hub.effort.controller import VolumeController

    config = Config()
    backend = build_volume_backend()
    volume = RateLimitedVolume(backend)
    controller = VolumeController(config, volume)
    return controller


# ── Mode runners ──────────────────────────────────────────────────────────────

async def run_flower(simulate: bool, sim_pods: int) -> None:
    server, ws_coro, config = _build_flower()

    ble_coro = (
        _simulate_ble(server, sim_pods)
        if simulate
        else _connect_ble(server, config.ble_scan_timeout)
    )
    led_coro = _connect_led(server.get_game_state, config.ble_scan_timeout)

    print("  Open GameDashboard/index.html in your browser, then click Start.")
    await asyncio.gather(ws_coro, ble_coro, led_coro)


async def run_volume(simulate: bool, sim_pods: int) -> None:
    controller = _build_hub()

    if simulate:
        await _simulate_ble(controller, sim_pods)
    else:
        await _connect_ble(controller, scan_timeout=10.0)


async def run_both(simulate: bool, sim_pods: int) -> None:
    flower_server, ws_coro, flower_cfg = _build_flower()
    hub_ctrl = _build_hub()

    multi = MultiController(flower_server, hub_ctrl)

    ble_coro = (
        _simulate_ble(multi, sim_pods)
        if simulate
        else _connect_ble(multi, flower_cfg.ble_scan_timeout)
    )
    led_coro = _connect_led(flower_server.get_game_state, flower_cfg.ble_scan_timeout)

    print("  Open GameDashboard/index.html in your browser.")
    print("  Music volume + flowers both respond to pod movement.")
    await asyncio.gather(ws_coro, ble_coro, led_coro)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Pebble launcher.")
    parser.add_argument(
        "mode",
        choices=["flower", "volume", "both"],
        help="Which game(s) to run.",
    )
    parser.add_argument(
        "--simulate", action="store_true",
        help="Run without hardware (simulated pods).",
    )
    parser.add_argument(
        "--sim-pods", type=int, default=3, metavar="N",
        help="Number of simulated pods (default: 3).",
    )
    args = parser.parse_args()

    runners = {
        "flower": run_flower,
        "volume": run_volume,
        "both":   run_both,
    }

    print("=" * 55)
    print(f"  Pebble — mode: {args.mode}")
    print("=" * 55)

    try:
        asyncio.run(runners[args.mode](args.simulate, args.sim_pods))
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
