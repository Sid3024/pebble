"""
IMU data structures and BLE packet parser for Pebble sensor pods.

This file defines the ImuWindow dataclass — the fundamental data unit flowing
through the entire Pebble system — and the parser that converts raw BLE bytes
into ImuWindow instances.

Data flow:
    Firmware (20 bytes over BLE) -> parse_imu_window() -> ImuWindow
    -> game controller (similarity scoring, growth, etc.)

ImuWindow fields:
    Each window represents 250ms of IMU data (25 samples at 100Hz), averaged
    by the firmware into a single reading:
      ax, ay, az : Accelerometer (g) — includes gravity + movement
      gx, gy, gz : Gyroscope (deg/s) — rotational velocity
      roll, pitch: Orientation angles (degrees)
      samples    : Number of raw samples (v1 packets)
      activity   : Pre-computed movement score (v2 packets, firmware-side)

BLE packet format (20 bytes, little-endian):
    Byte 0:   magic    (0x50 = 'P' for Pebble)
    Byte 1:   version  (1 = samples field, 2 = activity field)
    Bytes 2-3:  samples (v1) or activity*1000 (v2), uint16
    Bytes 4-19: ax, ay, az, gx, gy, gz, roll, pitch — each int16
                accel scaled by 1000 (milli-g), gyro by 100, angles by 100

Legacy 4-byte format:
    A single float (window_sum) from older firmware. Converted to a
    synthetic ImuWindow with movement on the ax axis only.

Dependencies:
    - struct (stdlib): Binary unpacking of BLE payloads.
    - math (stdlib): Vector magnitude calculations.
    - dataclasses (stdlib): Frozen dataclass for immutable window objects.

How it fits into Pebble:
    Every component that touches IMU data imports ImuWindow from here:
    BLE client, similarity engine, game controllers, simulator.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass


@dataclass(frozen=True)
class ImuWindow:
    """
    One 250ms window of averaged IMU sensor data from a Pebble pod.

    Frozen (immutable) so it can be safely stored in history buffers
    and passed between components without risk of accidental mutation.
    """
    samples: int       # Number of raw IMU samples (v1) or 0 (v2)
    ax: float          # Accelerometer X axis (g, includes gravity)
    ay: float          # Accelerometer Y axis (g)
    az: float          # Accelerometer Z axis (g)
    gx: float          # Gyroscope X axis (deg/s)
    gy: float          # Gyroscope Y axis (deg/s)
    gz: float          # Gyroscope Z axis (deg/s)
    roll: float        # Roll angle (degrees)
    pitch: float       # Pitch angle (degrees)
    activity: float | None = None  # Pre-computed movement score (v2 only)

    @property
    def movement_magnitude(self) -> float:
        """Euclidean magnitude of acceleration vector (includes gravity ~1g at rest)."""
        return math.sqrt(self.ax * self.ax + self.ay * self.ay + self.az * self.az)

    @property
    def gyro_magnitude(self) -> float:
        """Euclidean magnitude of gyroscope vector (deg/s)."""
        return math.sqrt(self.gx * self.gx + self.gy * self.gy + self.gz * self.gz)

    @property
    def shake_score(self) -> float:
        """Combined movement score: accel magnitude + small gyro contribution.
        If firmware already computed activity (v2), use that directly."""
        if self.activity is not None:
            return self.activity
        return self.movement_magnitude + 0.01 * self.gyro_magnitude

    @property
    def effort_fallback(self) -> float:
        """Convert shake_score back to a legacy window_sum-like value (~300 at rest).
        Used by older code paths that expect the float-window format."""
        return 300.0 * (1.0 + self.shake_score)


def parse_imu_window(data: bytes) -> ImuWindow:
    """Parse raw BLE notification bytes into an ImuWindow.

    Supports two formats:
      - 4 bytes: Legacy single float (window_sum). Converted to synthetic ImuWindow.
      - 20 bytes: Full IMU packet with magic byte, version, and all sensor fields.
        Version 1: third field is sample count.
        Version 2: third field is pre-computed activity score (×1000).
    """
    # Legacy 4-byte format: a single float representing the old "window sum"
    if len(data) == 4:
        (window_sum,) = struct.unpack("<f", data)
        movement = max(0.0, window_sum / 300.0 - 1.0)
        return ImuWindow(0, movement, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    if len(data) != 20:
        raise ValueError(f"expected 20-byte IMU packet, got {len(data)} bytes")

    # Unpack: magic(u8) version(u8) samples_or_activity(u16) then 8x int16
    magic, version, samples_or_activity, ax, ay, az, gx, gy, gz, roll, pitch = struct.unpack("<BBHhhhhhhhh", data)
    if magic != 0x50 or version not in (1, 2):
        raise ValueError(f"unsupported IMU packet magic={magic:#x} version={version}")

    # Version 2 repurposes the samples field as activity (×1000 for int precision)
    activity = samples_or_activity / 1000.0 if version == 2 else None
    samples = 0 if version == 2 else samples_or_activity

    # Scale int16 values back to physical units:
    #   accel: divide by 1000 -> g (so ±32g range fits in int16)
    #   gyro:  divide by 100  -> deg/s
    #   angles: divide by 100 -> degrees
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
