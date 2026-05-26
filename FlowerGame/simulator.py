"""
Simulated pod — generates synthetic window_sum values so the game can be
tested without physical hardware.  Run main.py with --simulate to use this.
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
    Simulate `num_pods` pods each emitting window sums at `window_interval_s`.
    Each pod has a slowly varying effort level with small random jitter,
    mimicking a real workout session.
    """
    print(f"[SIM] Starting {num_pods} simulated pod(s) "
          f"(window every {window_interval_s}s)")

    async def pod(name: str, phase_offset: float) -> None:
        step = 0
        while True:
            # Baseline value ~300 (100 Hz * 3 s, each sample ~1 g)
            base = 300.0
            # Effort wave: gentle sine oscillation above baseline
            effort_wave = math.sin(step / 8.0 + phase_offset) * 0.15 + 1.10
            window_sum = base * effort_wave + random.uniform(-10, 10)
            controller.process_window(name, window_sum)
            step += 1
            await asyncio.sleep(window_interval_s)

    await asyncio.gather(*[
        pod(f"Pebble_SIM{i+1:02d}", phase_offset=i * 1.3)
        for i in range(num_pods)
    ])
