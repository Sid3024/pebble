"""
Simulated pods - generates synthetic IMU windows so the game can be tested
without physical hardware. Run main.py with --simulate to use this.
"""
from __future__ import annotations

import asyncio
import math
import random

from ble.imu import ImuWindow


def _motion(step: int, phase_offset: float = 0.0, noise: float = 0.0) -> ImuWindow:
    t = step / 3.0 + phase_offset
    ax = math.sin(t) * 0.35 + random.uniform(-noise, noise)
    ay = math.cos(t * 0.8) * 0.25 + random.uniform(-noise, noise)
    az = math.sin(t * 1.3) * 0.18 + random.uniform(-noise, noise)
    gx = math.cos(t) * 80.0 + random.uniform(-noise * 120.0, noise * 120.0)
    gy = math.sin(t * 0.7) * 55.0 + random.uniform(-noise * 120.0, noise * 120.0)
    gz = math.cos(t * 1.2) * 35.0 + random.uniform(-noise * 120.0, noise * 120.0)
    roll = math.sin(t * 0.5) * 45.0 + random.uniform(-noise * 40.0, noise * 40.0)
    pitch = math.cos(t * 0.5) * 35.0 + random.uniform(-noise * 40.0, noise * 40.0)
    return ImuWindow(100, ax, ay, az, gx, gy, gz, roll, pitch)


async def run_simulated_pods(
    controller,
    num_pods: int = 3,
    window_interval_s: float = 1.0,
) -> None:
    print(f"[SIM] Starting {num_pods} simulated IMU pod(s)")

    async def pod(name: str, pod_index: int) -> None:
        step = 0
        while True:
            if step < 2:
                window = ImuWindow(100, 0.01, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            elif pod_index == 0:
                window = _motion(step, 0.0, 0.01)
            else:
                delay = pod_index * 0.12
                window = _motion(step, -delay, 0.04)
            controller.process_imu_window(name, window)
            step += 1
            await asyncio.sleep(window_interval_s)

    await asyncio.gather(*[
        pod(f"Pebble_SIM{i+1:02d}", i)
        for i in range(num_pods)
    ])
