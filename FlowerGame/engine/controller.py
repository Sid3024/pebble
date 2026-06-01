from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..config.config import FlowerConfig
from effort.baseline import BaselineCalculator, expected_effort
from ble.constants import VIBR_MILESTONE1, VIBR_MILESTONE2, VIBR_MILESTONE3, VIBR_WIN

_MILESTONES = [(0.25, VIBR_MILESTONE1), (0.50, VIBR_MILESTONE2),
               (0.75, VIBR_MILESTONE3), (1.00, VIBR_WIN)]


@dataclass
class DeviceState:
    phase: str = "baseline"   # baseline | active | idle | wilt
    last_seen: float = field(default_factory=time.monotonic)


class PersonGrowthTracker:
    """
    Tracks one device's baseline and converts each window into growth points.
    Uses the shared effort.baseline module — same baseline logic as the volume game.
    """

    def __init__(self, config: FlowerConfig) -> None:
        self._config = config
        self._baseline = BaselineCalculator(config.baseline_n_windows)
        self.state = DeviceState()

    @property
    def is_ready(self) -> bool:
        return self._baseline.is_ready()

    def process_window(self, window_sum: float) -> float:
        """Returns growth delta for this window (negative = wilt penalty)."""
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
            # Scale growth by how much harder than baseline the effort is.
            # ratio=1 → base growth; ratio=2 → 2× growth; no upper cap.
            return self._config.growth_per_window * (window_sum / exp)

        if window_sum < exp * (1.0 - self._config.wilt_margin):
            self.state.phase = "wilt"
            return -self._config.wilt_per_window

        self.state.phase = "idle"
        return self._config.idle_growth_per_window


class FlowerController:
    """
    Aggregates per-device growth into a shared garden state.
    Exposes the same process_window(device_name, window_sum) interface
    as VolumeController so the shared BLE client works with both games.
    """

    def __init__(self, config: FlowerConfig) -> None:
        self._config = config
        self._trackers: dict[str, PersonGrowthTracker] = {}
        self._total_growth: float = 0.0
        self.phase: str = "waiting"  # waiting | playing | won
        self._milestones_hit: set[float] = set()
        self._pending_vibrations: dict[str, list[int]] = {}

    def process_window(self, device_name: str, window_sum: float) -> None:
        if self.phase not in ("playing",):
            return

        if device_name not in self._trackers:
            print(f"[{device_name}] new device — collecting baseline "
                  f"({self._config.baseline_n_windows} windows)")
            self._trackers[device_name] = PersonGrowthTracker(self._config)

        tracker = self._trackers[device_name]
        delta = tracker.process_window(window_sum)

        if delta != 0:
            self._total_growth = max(0.0, self._total_growth + delta)
            arrow = "↑" if delta > 0 else "↓"
            print(
                f"[{device_name}] score={window_sum:.2f}  "
                f"growth {arrow}{abs(delta):.1f} → "
                f"{self._total_growth:.1f}/{self._config.total_growth_needed:.0f} "
                f"({self.progress * 100:.1f}%)"
            )

        if self._total_growth >= self._config.total_growth_needed:
            self.phase = "won"
            print("[GARDEN] Full bloom! Session complete.")

        self._check_milestones()

    def _check_milestones(self) -> None:
        for threshold, pattern_id in _MILESTONES:
            if threshold not in self._milestones_hit and self.progress >= threshold:
                self._milestones_hit.add(threshold)
                for name in self._trackers:
                    self._pending_vibrations.setdefault(name, []).append(pattern_id)
                print(f"[GARDEN] {int(threshold*100)}% milestone — "
                      f"queued pattern {pattern_id} for {len(self._trackers)} device(s)")

    def pop_vibration_commands(self, device_name: str) -> list[int]:
        return self._pending_vibrations.pop(device_name, [])

    def start_session(self) -> None:
        self._trackers.clear()
        self._total_growth = 0.0
        self.phase = "playing"
        self._milestones_hit.clear()
        self._pending_vibrations.clear()
        print("[GARDEN] Session started.")

    def reset(self) -> None:
        self._trackers.clear()
        self._total_growth = 0.0
        self.phase = "waiting"
        self._milestones_hit.clear()
        self._pending_vibrations.clear()
        print("[GARDEN] Session reset.")

    @property
    def progress(self) -> float:
        return min(1.0, self._total_growth / self._config.total_growth_needed)

    def get_state(self) -> dict:
        devices = {
            name: {"phase": tracker.state.phase, "ready": tracker.is_ready}
            for name, tracker in self._trackers.items()
        }
        return {
            "mode":         "single",
            "phase":        self.phase,
            "progress":     round(self.progress, 4),
            "total_growth": round(self._total_growth, 2),
            "total_needed": self._config.total_growth_needed,
            "num_devices":  len(self._trackers),
            "devices":      devices,
            "plants":       self._compute_plants(),
        }

    def _compute_plants(self) -> list[dict]:
        n = self._config.num_plants
        p = self.progress
        plants = []
        for i in range(n):
            start = i / n
            end = (i + 1) / n
            if p <= start:
                growth = 0.0
            elif p >= end:
                growth = 1.0
            else:
                growth = (p - start) / (end - start)
            plants.append({"id": i, "growth": round(growth, 4)})
        return plants
