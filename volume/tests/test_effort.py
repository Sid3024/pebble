import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from volume_game.effort import EffortCalculator, ImuReading, map_effort_to_volume
from volume_game.inputs import parse_sensor_line
from volume_game.volume import RateLimitedVolume, VolumeBackend, clamp_percent


class FakeVolumeBackend(VolumeBackend):
    def __init__(self) -> None:
        self.values: list[int] = []

    def set_volume(self, percent: int) -> None:
        self.values.append(percent)


class EffortMappingTests(unittest.TestCase):
    def test_effort_maps_to_volume_range(self):
        self.assertEqual(map_effort_to_volume(0.2, 0.2, 1.8, 10, 90), 10)
        self.assertEqual(map_effort_to_volume(1.0, 0.2, 1.8, 10, 90), 50)
        self.assertEqual(map_effort_to_volume(1.8, 0.2, 1.8, 10, 90), 90)

    def test_effort_maps_by_ten_percent_steps(self):
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
        self.assertEqual(map_effort_to_volume(-1.0, 0.0, 2.0, 10, 90), 10)
        self.assertEqual(map_effort_to_volume(3.0, 0.0, 2.0, 10, 90), 90)

    def test_calculator_ignores_stationary_gravity(self):
        calculator = EffortCalculator(smoothing=1.0)
        self.assertAlmostEqual(calculator.update(ImuReading(0.0, 0.0, 1.0)), 0.0)

    def test_parser_accepts_effort_json(self):
        event = parse_sensor_line('{"effort": 0.72}', EffortCalculator())
        assert event is not None
        self.assertAlmostEqual(event.effort, 0.72)

    def test_parser_accepts_imu_csv(self):
        event = parse_sensor_line("0,0,1.5,0,0,0", EffortCalculator(smoothing=1.0))
        assert event is not None
        self.assertAlmostEqual(event.effort, 0.5)

    def test_volume_percent_is_clamped(self):
        self.assertEqual(clamp_percent(-20), 0)
        self.assertEqual(clamp_percent(55), 55)
        self.assertEqual(clamp_percent(120), 100)

    def test_rate_limiter_clamps_before_backend(self):
        backend = FakeVolumeBackend()
        volume = RateLimitedVolume(backend, min_change=0, min_interval_s=0.0)
        self.assertTrue(volume.set_volume(120))
        self.assertEqual(backend.values, [100])


if __name__ == "__main__":
    unittest.main()
