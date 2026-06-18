"""
Simulated pod -- generates synthetic window_sum values so the FlowerGame can be
tested without physical BLE hardware.  Run ``python -m FlowerGame --simulate``
to use this.

How it works:
    Each simulated pod is an async coroutine that emits one window sum every
    ``window_interval_s`` seconds.  The synthetic value is built from:

        window_sum = base * effort_wave + jitter

    - **base** (~300): Mimics a real pod at rest.  A 100 Hz IMU sampling rate
      over a 3-second window at ~1 g produces roughly 300.
    - **effort_wave**: A slow sine oscillation (period ~50 windows) centered
      at 1.10x baseline, giving +/- 15 % variation.  This simulates a player
      alternating between more and less vigorous shaking.
    - **jitter**: Uniform random noise in [-10, +10] to add realism.

    Each pod gets a different ``phase_offset`` so their effort curves are not
    synchronized (just like real humans).

Dependencies:
    - asyncio : For concurrent pod tasks and sleep.
    - math    : Sine function for the effort wave.
    - random  : Jitter noise.

How it fits into Pebble:
    FlowerGame.main._run_with_simulator() calls run_simulated_pods(), passing
    the FlowerWSServer as the controller.  Each simulated pod calls
    controller.process_window() on each tick, exactly as a real PebbleClient
    would when it receives a BLE notification.
"""
from __future__ import annotations

import asyncio
import math
import random

from .engine.controller import FlowerController


async def run_simulated_pods(
    controller: FlowerController,
    num_pods: int = 3,
    window_interval_s: float = 3.0,
) -> None:
    """
    Launch *num_pods* simulated pods, each emitting window sums at regular intervals.

    Each pod has a slowly varying effort level with small random jitter,
    mimicking a real workout session where a player shakes harder and softer
    over time.

    Args:
        controller:         Any object with process_window(device_name, window_sum).
                            Typically FlowerWSServer, which proxies to the active
                            game controller.
        num_pods:           Number of simulated pods to create (default 3).
        window_interval_s:  Seconds between consecutive window sums from each
                            pod (default 3.0).
    """
    print(f"[SIM] Starting {num_pods} simulated pod(s) "
          f"(window every {window_interval_s}s)")

    async def pod(name: str, phase_offset: float) -> None:
        """
        Single simulated pod coroutine -- runs forever, emitting one window sum per tick.

        Args:
            name:          Device name (e.g. "Pebble_SIM01").
            phase_offset:  Offset into the sine wave so pods are out of phase.
        """
        step = 0
        while True:
            # Baseline value ~300 (100 Hz * 3 s, each sample ~1 g magnitude)
            base = 300.0
            # Effort wave: gentle sine oscillation above baseline, centered at 1.10
            # This means the pod is always slightly above resting (simulating activity).
            effort_wave = math.sin(step / 8.0 + phase_offset) * 0.15 + 1.10
            # Final window sum = scaled base + small random jitter
            window_sum = base * effort_wave + random.uniform(-10, 10)
            controller.process_window(name, window_sum)
            step += 1
            await asyncio.sleep(window_interval_s)

    # Run all simulated pods concurrently; each has a unique name and phase offset.
    await asyncio.gather(*[
        pod(f"Pebble_SIM{i+1:02d}", phase_offset=i * 1.3)
        for i in range(num_pods)
    ])
