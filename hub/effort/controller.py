from __future__ import annotations

from config.config import Config
from volume.volume import RateLimitedVolume, clamp_percent
from effort.baseline import BaselineCalculator, expected_effort


class PersonTracker:
    """
    Tracks one person's baseline and computes their volume delta per window.

    During the first baseline_n_windows windows, the score is fed into the
    baseline calculator and no volume change is produced. After that, each
    window is compared to expected_effort() using percentage deviation:
      score > expected * (1 + increase_margin)  →  +increase_alpha
      score < expected * (1 - decrease_margin)  →  -decrease_alpha
      otherwise                                 →  0
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._baseline = BaselineCalculator(config.baseline_n_windows)

    def process_window(self, window_sum: float) -> tuple[int, float | None]:
        """Returns (volume_delta, expected_value) for this window."""
        if not self._baseline.is_ready():
            self._baseline.add(window_sum)
            remaining = self._config.baseline_n_windows - self._baseline.samples_collected
            if remaining > 0:
                print(f"    [baseline] {remaining} window(s) remaining")
            else:
                print(f"    [baseline] ready — mean={self._baseline.baseline():.2f}")
            return 0, None

        exp = expected_effort(self._baseline)
        if exp is None or exp == 0:
            return 0, exp

        if window_sum > exp * (1.0 + self._config.increase_margin):
            return self._config.increase_alpha, exp
        if window_sum < exp * (1.0 - self._config.decrease_margin):
            return -self._config.decrease_alpha, exp
        return 0, exp


class VolumeController:
    """
    Applies per-person volume deltas to the system volume.

    Each device has its own PersonTracker. When a window arrives from any
    device, its delta is computed and immediately applied. Deltas from
    different devices accumulate independently — if two people are both
    working hard, volume rises by 2 * increase_alpha per window pair.
    """

    def __init__(self, config: Config, volume: RateLimitedVolume) -> None:
        self._config = config
        self._volume = volume
        self._current = config.initial_volume
        self._trackers: dict[str, PersonTracker] = {}
        volume.set_volume(self._current)

    def process_window(self, device_name: str, window_sum: float) -> None:
        if device_name not in self._trackers:
            print(f"[{device_name}] new device — collecting baseline "
                  f"({self._config.baseline_n_windows} windows)")
            self._trackers[device_name] = PersonTracker(self._config)

        delta, exp = self._trackers[device_name].process_window(window_sum)

        exp_str = f"{exp:.2f}" if exp is not None else "n/a"
        if delta != 0:
            self._current = clamp_percent(self._current + delta)
            self._volume.set_volume(self._current)
            arrow = "↑" if delta > 0 else "↓"
            print(f"[{device_name}] score={window_sum:.2f}  exp={exp_str}  "
                  f"vol {arrow}{abs(delta)} → {self._current}%")
        else:
            print(f"[{device_name}] score={window_sum:.2f}  exp={exp_str}  "
                  f"vol={self._current}% (no change)")
