"""
Effort calculation module for the Volume game.

This file is responsible for converting raw IMU sensor data (accelerometer and
gyroscope readings) from a XIAO ESP32S3 pod into a single, smooth "effort"
value that represents how much the player is moving. That effort value is then
mapped onto an integer volume percentage.

Algorithm overview:
    1. An ImuReading captures one snapshot of accelerometer (ax, ay, az) and
       optional gyroscope (gx, gy, gz) data.
    2. EffortCalculator.update() computes the magnitude of acceleration, subtracts
       Earth's gravity to isolate deliberate movement, adds a weighted gyroscope
       component, and applies exponential moving average (EMA) smoothing.
    3. map_effort_to_volume() linearly maps the smoothed effort onto a configurable
       [min_volume, max_volume] integer range, clamping at the boundaries.

Libraries used:
    - dataclasses: for the frozen ImuReading data container.
    - math.sqrt: for computing vector magnitudes.

Classes:
    - ImuReading: immutable snapshot of one IMU sample (accel + gyro).
    - EffortCalculator: stateful converter from ImuReading stream to smoothed effort.

Functions:
    - clamp(): generic numeric clamping utility.
    - map_effort_to_volume(): linear mapping from effort range to volume range.

Fits into the Pebble project as the core signal-processing layer of the Volume
game. It sits between the input sources (inputs.py) and the volume control
layer (volume.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt


def clamp(value: float, low: float, high: float) -> float:
    """Restrict *value* to the closed interval [low, high].

    A simple utility used throughout this module to prevent effort and volume
    values from exceeding their valid ranges.
    """
    return max(low, min(high, value))


def map_effort_to_volume(
    effort: float,
    min_effort: float,
    max_effort: float,
    min_volume: int,
    max_volume: int,
) -> int:
    """Map an effort value onto an integer volume percentage.

    Performs a linear interpolation from the effort range [min_effort, max_effort]
    to the volume range [min_volume, max_volume]. The effort is clamped so values
    outside the expected range still produce a valid volume. The result is rounded
    to the nearest integer.

    Raises ValueError if max_effort <= min_effort to prevent division by zero or
    an inverted mapping.
    """
    if max_effort <= min_effort:
        raise ValueError("max_effort must be greater than min_effort")

    ratio = clamp((effort - min_effort) / (max_effort - min_effort), 0.0, 1.0)
    return round(min_volume + ratio * (max_volume - min_volume))


@dataclass(frozen=True)
class ImuReading:
    """Immutable snapshot of one IMU sample from the XIAO ESP32S3 pod.

    Contains three-axis accelerometer data (ax, ay, az) measured in g-force units
    and optional three-axis gyroscope data (gx, gy, gz) measured in degrees per
    second. The gyroscope fields default to 0.0 because some serial formats only
    transmit accelerometer data.
    """

    ax: float
    ay: float
    az: float
    gx: float = 0.0
    gy: float = 0.0
    gz: float = 0.0


class EffortCalculator:
    """Convert raw accelerometer and optional gyro readings into smooth effort.

    The calculator is stateful: it maintains an exponentially smoothed effort
    value across successive update() calls, producing a stable signal from
    noisy IMU data.

    Parameters:
        gravity_g:   Expected magnitude of gravity in g-units (default 1.0).
                     Subtracted from the accelerometer magnitude so that a
                     stationary pod produces near-zero effort.
        gyro_weight: How much the gyroscope magnitude contributes relative to
                     the accelerometer-derived movement. A small default (0.02)
                     keeps rotation as a secondary signal.
        smoothing:   EMA coefficient in [0, 1]. Higher values make the output
                     track sudden changes more closely; lower values produce a
                     smoother, more sluggish signal. At 1.0 there is no smoothing
                     (raw value passes through). At 0.0 the output never changes.
    """

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
        """Ingest one IMU reading and return the updated smoothed effort.

        Steps:
            1. Compute the total accelerometer magnitude (Euclidean norm).
            2. Subtract expected gravity to isolate movement-only acceleration.
            3. Compute gyroscope magnitude and add it weighted by gyro_weight.
            4. Apply EMA smoothing: new = alpha * raw + (1 - alpha) * previous.
        """
        accel_mag = sqrt(reading.ax**2 + reading.ay**2 + reading.az**2)
        movement_g = abs(accel_mag - self.gravity_g)

        gyro_mag = sqrt(reading.gx**2 + reading.gy**2 + reading.gz**2)
        raw_effort = movement_g + self.gyro_weight * gyro_mag

        self._smoothed = (
            self.smoothing * raw_effort + (1.0 - self.smoothing) * self._smoothed
        )
        return self._smoothed

    def reset(self) -> None:
        """Reset the internal smoothed effort back to zero.

        Useful when switching between pods or restarting a game session so that
        stale effort history does not bleed into the new session.
        """
        self._smoothed = 0.0
