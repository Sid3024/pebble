"""
Unit tests for the Volume game's effort calculation, input parsing, and volume
control modules.

This file tests the core logic of the Volume game without requiring any
hardware (no XIAO ESP32S3 pod, no serial port, no audio device). It covers:
    - Effort-to-volume mapping (linear interpolation, clamping, boundary values).
    - EffortCalculator behaviour (gravity subtraction, smoothing).
    - Serial line parsing (JSON format, CSV format).
    - Volume percentage clamping.
    - RateLimitedVolume behaviour (clamping before forwarding to backend).

Libraries used:
    - unittest: standard Python test framework.
    - sys / pathlib: for inserting the parent directory into sys.path so the
      volume_game package can be imported when running tests directly.

Classes:
    - FakeVolumeBackend: test double that records set_volume() calls.
    - EffortMappingTests: test case with all assertions.

How to run:
    ``python -m pytest volume/tests/`` or ``python volume/tests/test_effort.py``

Fits into the Pebble project as the regression test suite for the Volume game's
signal-processing and volume-control pipeline.
"""

import sys
import unittest
from pathlib import Path

# Ensure the volume_game package is importable when this file is run directly
# (e.g. ``python tests/test_effort.py``), since the package lives one directory
# above the tests folder.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from volume_game.effort import EffortCalculator, ImuReading, map_effort_to_volume
from volume_game.inputs import parse_sensor_line
from volume_game.volume import RateLimitedVolume, VolumeBackend, clamp_percent


class FakeVolumeBackend(VolumeBackend):
    """Test double for VolumeBackend that records all set_volume() calls.

    Instead of changing real audio, it appends each requested percentage to
    a list so tests can assert on the exact sequence of values.
    """

    def __init__(self) -> None:
        self.values: list[int] = []

    def set_volume(self, percent: int) -> None:
        """Record the requested volume percentage."""
        self.values.append(percent)


class EffortMappingTests(unittest.TestCase):
    """Tests for effort-to-volume mapping, IMU parsing, and volume clamping."""

    def test_effort_maps_to_volume_range(self):
        """Verify that min, mid, and max effort map to min, mid, and max volume."""
        self.assertEqual(map_effort_to_volume(0.2, 0.2, 1.8, 10, 90), 10)
        self.assertEqual(map_effort_to_volume(1.0, 0.2, 1.8, 10, 90), 50)
        self.assertEqual(map_effort_to_volume(1.8, 0.2, 1.8, 10, 90), 90)

    def test_effort_maps_by_ten_percent_steps(self):
        """Verify linear interpolation produces even 10% volume steps across
        evenly spaced effort values, plus clamping at effort above max."""
        self.assertEqual(map_effort_to_volume(0.2, 0.2, 1.8, 10, 90), 10)
        self.assertEqual(map_effort_to_volume(0.4, 0.2, 1.8, 10, 90), 20)
        self.assertEqual(map_effort_to_volume(0.6, 0.2, 1.8, 10, 90), 30)
        self.assertEqual(map_effort_to_volume(0.8, 0.2, 1.8, 10, 90), 40)
        self.assertEqual(map_effort_to_volume(1.0, 0.2, 1.8, 10, 90), 50)
        self.assertEqual(map_effort_to_volume(1.2, 0.2, 1.8, 10, 90), 60)
        self.assertEqual(map_effort_to_volume(1.4, 0.2, 1.8, 10, 90), 70)
        self.assertEqual(map_effort_to_volume(1.6, 0.2, 1.8, 10, 90), 80)
        self.assertEqual(map_effort_to_volume(1.8, 0.2, 1.8, 10, 90), 90)
        self.assertEqual(map_effort_to_volume(2.0, 0.2, 1.8, 10, 90), 90)

    def test_effort_is_clamped(self):
        """Effort values below min or above max should clamp to volume boundaries."""
        self.assertEqual(map_effort_to_volume(-1.0, 0.0, 2.0, 10, 90), 10)
        self.assertEqual(map_effort_to_volume(3.0, 0.0, 2.0, 10, 90), 90)

    def test_calculator_ignores_stationary_gravity(self):
        """A pod sitting still at 1g on the z-axis should produce zero effort.

        Uses smoothing=1.0 so the raw value passes through without blending
        with previous history.
        """
        calculator = EffortCalculator(smoothing=1.0)
        self.assertAlmostEqual(calculator.update(ImuReading(0.0, 0.0, 1.0)), 0.0)

    def test_parser_accepts_effort_json(self):
        """JSON with an explicit 'effort' key should be parsed directly."""
        event = parse_sensor_line('{"effort": 0.72}', EffortCalculator())
        assert event is not None
        self.assertAlmostEqual(event.effort, 0.72)

    def test_parser_accepts_imu_csv(self):
        """Six-value CSV (ax,ay,az,gx,gy,gz) should be parsed as IMU data.

        With az=1.5 and gravity=1.0, the movement is 0.5g. smoothing=1.0
        means no EMA blending, so the output equals the raw effort.
        """
        event = parse_sensor_line("0,0,1.5,0,0,0", EffortCalculator(smoothing=1.0))
        assert event is not None
        self.assertAlmostEqual(event.effort, 0.5)

    def test_volume_percent_is_clamped(self):
        """clamp_percent should restrict values to [0, 100]."""
        self.assertEqual(clamp_percent(-20), 0)
        self.assertEqual(clamp_percent(55), 55)
        self.assertEqual(clamp_percent(120), 100)

    def test_rate_limiter_clamps_before_backend(self):
        """RateLimitedVolume should clamp to 100 before forwarding to the backend."""
        backend = FakeVolumeBackend()
        volume = RateLimitedVolume(backend, min_change=0, min_interval_s=0.0)
        self.assertTrue(volume.set_volume(120))
        self.assertEqual(backend.values, [100])


if __name__ == "__main__":
    unittest.main()
