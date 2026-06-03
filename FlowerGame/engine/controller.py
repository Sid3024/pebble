from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..config.config import FlowerConfig
from effort.baseline import BaselineCalculator, expected_effort
from ble.constants import VIBR_MILESTONE1, VIBR_MILESTONE2, VIBR_MILESTONE3, VIBR_WIN, VIBR_FLOWER_50

# Time-elapsed thresholds (fraction of total duration) that trigger vibration.
# 0.25 = 25 % of time has passed, etc.
_TIME_MILESTONES = [
    (0.25, VIBR_MILESTONE1),
    (0.50, VIBR_MILESTONE2),
    (0.75, VIBR_MILESTONE3),
]


@dataclass
class DeviceState:
    phase: str = "baseline"   # baseline | active | idle | wilt
    last_seen: float = field(default_factory=time.monotonic)


class PersonGrowthTracker:
    """
    Tracks one device's baseline and converts each window into score points.
    Growth scales with effort: harder shaking → more points per window.
    """

    def __init__(self, config: FlowerConfig) -> None:
        self._config = config
        self._baseline = BaselineCalculator(config.baseline_n_windows)
        self.state = DeviceState()

    @property
    def is_ready(self) -> bool:
        return self._baseline.is_ready()

    def process_window(self, window_sum: float) -> float:
        """Returns score delta for this window."""
        self.state.last_seen = time.monotonic()

        if not self._baseline.is_ready():
            self._baseline.add(window_sum)
            remaining = self._config.baseline_n_windows - self._baseline.samples_collected
            if remaining > 0:
                print(f"    [baseline] {remaining} window(s) remaining")
            else:
                print(f"    [baseline] ready — mean={self._baseline.baseline():.2f}")
            self.state.phase = "baseline"
            return 0.0

        exp = expected_effort(self._baseline)
        if exp is None or exp == 0:
            self.state.phase = "idle"
            return 0.0

        if window_sum > exp * (1.0 + self._config.growth_margin):
            self.state.phase = "active"
            # Score scales with effort ratio — no upper cap.
            return self._config.growth_per_window * (window_sum / exp)

        if window_sum < exp * (1.0 - self._config.wilt_margin):
            self.state.phase = "wilt"
            return -self._config.wilt_per_window

        self.state.phase = "idle"
        return self._config.idle_growth_per_window


class FlowerController:
    """
    Aggregates per-device score into a shared garden state.
    Game ends when the timer expires; no fixed score goal.
    """

    def __init__(self, config: FlowerConfig) -> None:
        self._config     = config
        self._trackers:  dict[str, PersonGrowthTracker] = {}
        self._score:     float = 0.0
        self.phase:      str   = "waiting"
        self._duration:  float = 0.0
        self._start_time: float = 0.0
        self._milestones_hit: set[float] = set()
        self._pending_vibrations: dict[str, list[int]] = {}
        self._flower_milestone: int = 0   # tracks how many 50-flower marks passed

    # ── Time ──────────────────────────────────────────────────

    @property
    def time_remaining(self) -> float:
        if self.phase != "playing":
            return 0.0
        return max(0.0, self._duration - (time.monotonic() - self._start_time))

    # ── Score → flower progress ───────────────────────────────

    @property
    def progress(self) -> float:
        return 0.0   # progress bar removed — flowers are unlimited

    # ── Controller interface ──────────────────────────────────

    def process_window(self, device_name: str, window_sum: float) -> None:
        if self.phase != "playing":
            return

        if self.time_remaining <= 0:
            self.phase = "won"
            print("[GARDEN] Time's up!")
            self._queue_vibration_all(VIBR_WIN)
            return

        if device_name not in self._trackers:
            print(f"[{device_name}] new device — collecting baseline "
                  f"({self._config.baseline_n_windows} windows)")
            self._trackers[device_name] = PersonGrowthTracker(self._config)

        delta = self._trackers[device_name].process_window(window_sum)

        if delta != 0:
            self._score = max(0.0, self._score + delta)
            arrow = "↑" if delta > 0 else "↓"
            print(f"[{device_name}] score={window_sum:.2f}  "
                  f"{arrow}{abs(delta):.1f} → {self._score:.1f}  "
                  f"⏱ {self.time_remaining:.0f}s")

        self._check_milestones()

    def start_session(self, duration_seconds: int) -> None:
        self._trackers.clear()
        self._score      = 0.0
        self.phase       = "playing"
        self._duration   = float(duration_seconds)
        self._start_time = time.monotonic()
        self._milestones_hit.clear()
        self._pending_vibrations.clear()
        self._flower_milestone = 0
        print(f"[GARDEN] Session started — {duration_seconds}s timer.")

    def reset(self) -> None:
        self._trackers.clear()
        self._score      = 0.0
        self.phase       = "waiting"
        self._duration   = 0.0
        self._start_time = 0.0
        self._milestones_hit.clear()
        self._pending_vibrations.clear()
        self._flower_milestone = 0
        print("[GARDEN] Session reset.")

    def pop_vibration_commands(self, device_name: str) -> list[int]:
        return self._pending_vibrations.pop(device_name, [])

    def get_state(self) -> dict:
        devices = {
            name: {"phase": t.state.phase, "ready": t.is_ready}
            for name, t in self._trackers.items()
        }
        return {
            "mode":           "single",
            "phase":          self.phase,
            "time_remaining": round(self.time_remaining, 1),
            "duration":       int(self._duration),
            "score":          int(self._score),
            "progress":       round(self.progress, 4),
            "num_devices":    len(self._trackers),
            "devices":        devices,
            "plants":         self._compute_plants(),
        }

    # ── Internal ──────────────────────────────────────────────

    def _check_milestones(self) -> None:
        if self._duration == 0:
            return
        # Time-based milestones
        elapsed_ratio = (time.monotonic() - self._start_time) / self._duration
        for threshold, pattern_id in _TIME_MILESTONES:
            if threshold not in self._milestones_hit and elapsed_ratio >= threshold:
                self._milestones_hit.add(threshold)
                self._queue_vibration_all(pattern_id)
                print(f"[GARDEN] {int(threshold*100)}% time elapsed — pattern {pattern_id}")

        # Score-based: every 50 flowers
        current = int(self._score / 50)
        if current > self._flower_milestone:
            self._flower_milestone = current
            self._queue_vibration_all(VIBR_FLOWER_50)
            print(f"[GARDEN] {current * 50} flowers — happy vibration!")

    def _queue_vibration_all(self, pattern_id: int) -> None:
        for name in self._trackers:
            self._pending_vibrations.setdefault(name, []).append(pattern_id)

    def _compute_plants(self) -> list[dict]:
        # Only return fully bloomed flowers — no partial growth values.
        # The frontend animates each flower from 0→1 when it first appears.
        num_full = int(self._score / self._config.sprout_points_per_plant)
        return [{"id": i, "growth": 1.0} for i in range(num_full)]
