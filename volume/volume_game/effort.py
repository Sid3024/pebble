from __future__ import annotations

from dataclasses import dataclass
from math import sqrt


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def map_effort_to_volume(
    effort: float,
    min_effort: float,
    max_effort: float,
    min_volume: int,
    max_volume: int,
) -> int:
    """Map an effort value onto an integer volume percentage."""
    if max_effort <= min_effort:
        raise ValueError("max_effort must be greater than min_effort")

    ratio = clamp((effort - min_effort) / (max_effort - min_effort), 0.0, 1.0)
    return round(min_volume + ratio * (max_volume - min_volume))


@dataclass(frozen=True)
class ImuReading:
    ax: float
    ay: float
    az: float
    gx: float = 0.0
    gy: float = 0.0
    gz: float = 0.0


class EffortCalculator:
    """Convert raw accelerometer and optional gyro readings into smooth effort."""

    def __init__(
        self,
        gravity_g: float = 1.0,
        gyro_weight: float = 0.02,
        smoothing: float = 0.25,
    ) -> None:
        self.gravity_g = gravity_g
        self.gyro_weight = gyro_weight
        self.smoothing = clamp(smoothing, 0.0, 1.0)
        self._smoothed = 0.0

    def update(self, reading: ImuReading) -> float:
        accel_mag = sqrt(reading.ax**2 + reading.ay**2 + reading.az**2)
        movement_g = abs(accel_mag - self.gravity_g)

        gyro_mag = sqrt(reading.gx**2 + reading.gy**2 + reading.gz**2)
        raw_effort = movement_g + self.gyro_weight * gyro_mag

        self._smoothed = (
            self.smoothing * raw_effort + (1.0 - self.smoothing) * self._smoothed
        )
        return self._smoothed

    def reset(self) -> None:
        self._smoothed = 0.0
