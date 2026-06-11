from __future__ import annotations

import math
import struct
from dataclasses import dataclass


@dataclass(frozen=True)
class ImuWindow:
    samples: int
    ax: float
    ay: float
    az: float
    gx: float
    gy: float
    gz: float
    roll: float
    pitch: float
    activity: float | None = None

    @property
    def movement_magnitude(self) -> float:
        return math.sqrt(self.ax * self.ax + self.ay * self.ay + self.az * self.az)

    @property
    def gyro_magnitude(self) -> float:
        return math.sqrt(self.gx * self.gx + self.gy * self.gy + self.gz * self.gz)

    @property
    def shake_score(self) -> float:
        if self.activity is not None:
            return self.activity
        return self.movement_magnitude + 0.01 * self.gyro_magnitude

    @property
    def effort_fallback(self) -> float:
        return 300.0 * (1.0 + self.shake_score)


def parse_imu_window(data: bytes) -> ImuWindow:
    if len(data) == 4:
        (window_sum,) = struct.unpack("<f", data)
        movement = max(0.0, window_sum / 300.0 - 1.0)
        return ImuWindow(0, movement, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    if len(data) != 20:
        raise ValueError(f"expected 20-byte IMU packet, got {len(data)} bytes")

    magic, version, samples_or_activity, ax, ay, az, gx, gy, gz, roll, pitch = struct.unpack("<BBHhhhhhhhh", data)
    if magic != 0x50 or version not in (1, 2):
        raise ValueError(f"unsupported IMU packet magic={magic:#x} version={version}")

    activity = samples_or_activity / 1000.0 if version == 2 else None
    samples = 0 if version == 2 else samples_or_activity

    return ImuWindow(
        samples=samples,
        ax=ax / 1000.0,
        ay=ay / 1000.0,
        az=az / 1000.0,
        gx=gx / 100.0,
        gy=gy / 100.0,
        gz=gz / 100.0,
        roll=roll / 100.0,
        pitch=pitch / 100.0,
        activity=activity,
    )
