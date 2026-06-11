from __future__ import annotations

import time
from dataclasses import dataclass, field

from ble.constants import VIBR_FLOWER_50, VIBR_LAST_10, VIBR_MILESTONE2, VIBR_MILESTONE3, VIBR_WIN
from ble.imu import ImuWindow

from ..config.config import FlowerConfig
from .motion import selection_motion_score
from .similarity import SimilarityResult, compute_similarity

_TIME_MILESTONES = [
    (0.50, VIBR_MILESTONE2),
    (0.75, VIBR_MILESTONE3),
]


@dataclass
class DeviceState:
    phase: str = "waiting"
    ready: bool = False
    similarity: float = 0.0
    movement_score: float = 0.0
    rotation_score: float = 0.0
    angle_score: float = 0.0
    activity: float = 0.0
    last_seen: float = field(default_factory=time.monotonic)


class FlowerController:
    """
    Collaborative instructor-following flower game.

    Phase flow:
      waiting -> instructor_select -> playing -> won
    """

    def __init__(self, config: FlowerConfig) -> None:
        self._config = config
        self._devices: dict[str, DeviceState] = {}
        self._instructor: str | None = None
        self._reference: ImuWindow | None = None
        self._score: float = 0.0
        self.phase: str = "waiting"
        self._duration: float = 0.0
        self._start_time: float = 0.0
        self._milestones_hit: set[float] = set()
        self._pending_vibrations: dict[str, list[int]] = {}
        self._flower_milestone: int = 0
        self._last10_sent: bool = False

    @property
    def time_remaining(self) -> float:
        if self.phase != "playing":
            return 0.0
        return max(0.0, self._duration - (time.monotonic() - self._start_time))

    @property
    def progress(self) -> float:
        return 0.0

    def process_window(self, device_name: str, window_sum: float) -> None:
        movement = max(0.0, window_sum / 300.0 - 1.0)
        self.process_imu_window(
            device_name,
            ImuWindow(0, movement, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        )

    def process_imu_window(self, device_name: str, window: ImuWindow) -> None:
        state = self._devices.setdefault(device_name, DeviceState())
        state.last_seen = time.monotonic()

        if self.phase == "instructor_select":
            self._handle_instructor_select(device_name, window)
        elif self.phase == "playing":
            self._handle_playing(device_name, window)

    def start_session(self, duration_seconds: int) -> None:
        self._devices.clear()
        self._instructor = None
        self._reference = None
        self._score = 0.0
        self.phase = "instructor_select"
        self._duration = float(duration_seconds)
        self._start_time = 0.0
        self._milestones_hit.clear()
        self._pending_vibrations.clear()
        self._flower_milestone = 0
        self._last10_sent = False
        print(f"[GARDEN] Select instructor - shake one pod. Duration will be {duration_seconds}s.")

    def reset(self) -> None:
        self._devices.clear()
        self._instructor = None
        self._reference = None
        self._score = 0.0
        self.phase = "waiting"
        self._duration = 0.0
        self._start_time = 0.0
        self._milestones_hit.clear()
        self._pending_vibrations.clear()
        self._flower_milestone = 0
        self._last10_sent = False
        print("[GARDEN] Session reset.")

    def pop_vibration_commands(self, device_name: str) -> list[int]:
        return self._pending_vibrations.pop(device_name, [])

    def get_state(self) -> dict:
        devices = {
            name: {
                "phase": state.phase,
                "ready": state.ready,
                "role": "instructor" if name == self._instructor else "student",
                "similarity": round(state.similarity, 3),
                "movement_score": round(state.movement_score, 3),
                "rotation_score": round(state.rotation_score, 3),
                "angle_score": round(state.angle_score, 3),
                "activity": round(state.activity, 3),
            }
            for name, state in self._devices.items()
        }
        return {
            "mode": "single",
            "phase": self.phase,
            "instructor": self._instructor,
            "instructor_ready": self._instructor is not None,
            "time_remaining": round(self.time_remaining, 1),
            "duration": int(self._duration),
            "score": int(self._score),
            "similarity": self._average_similarity(),
            "progress": round(self.progress, 4),
            "num_devices": len(self._devices),
            "num_students": max(0, len(self._devices) - (1 if self._instructor else 0)),
            "devices": devices,
            "plants": self._compute_plants(),
        }

    def _handle_instructor_select(self, device_name: str, window: ImuWindow) -> None:
        motion = selection_motion_score(window)
        self._devices[device_name].activity = motion
        if self._instructor is not None:
            if device_name == self._instructor:
                self._reference = window
            return
        if motion < self._config.instructor_select_shake_threshold:
            self._devices[device_name].phase = "waiting"
            print(f"[{device_name}] instructor motion={motion:.3f} "
                  f"(need {self._config.instructor_select_shake_threshold:.3f})")
            return

        self._instructor = device_name
        self._reference = window
        state = self._devices[device_name]
        state.phase = "instructor"
        state.ready = True
        state.activity = motion
        self._pending_vibrations.setdefault(device_name, []).append(VIBR_MILESTONE2)
        print(f"[GARDEN] {device_name} selected as instructor (motion={motion:.3f}). "
              "Press Next to start the game.")

    def confirm_instructor(self) -> None:
        if self.phase == "instructor_select" and self._instructor is not None:
            self._start_time = time.monotonic()
            self.phase = "playing"
            print("[GARDEN] Instructor confirmed. Game started.")

    def _handle_playing(self, device_name: str, window: ImuWindow) -> None:
        if self.time_remaining <= 0:
            self.phase = "won"
            print("[GARDEN] Time's up!")
            self._queue_vibration_all(VIBR_WIN)
            return

        if device_name == self._instructor:
            self._reference = window
            state = self._devices[device_name]
            state.phase = "instructor"
            state.ready = True
            return

        if self._reference is None:
            return

        result = compute_similarity(
            self._reference,
            window,
            movement_weight=self._config.similarity_movement_weight,
            rotation_weight=self._config.similarity_rotation_weight,
            angle_weight=self._config.similarity_angle_weight,
            speed_sensitivity=self._config.similarity_speed_sensitivity,
            angle_tolerance_degrees=self._config.similarity_angle_tolerance_degrees,
        )
        self._apply_similarity(device_name, result)
        self._check_milestones()

    def _apply_similarity(self, device_name: str, result: SimilarityResult) -> None:
        delta = self._config.growth_per_window * result.score
        self._score = max(0.0, self._score + delta)

        state = self._devices[device_name]
        state.phase = "matching" if result.score >= 0.65 else "following"
        state.ready = True
        state.similarity = result.score
        state.movement_score = result.movement_score
        state.rotation_score = result.rotation_score
        state.angle_score = result.angle_score

        print(
            f"[{device_name}] similarity={result.score:.2f} "
            f"move={result.movement_score:.2f} rot={result.rotation_score:.2f} "
            f"angle={result.angle_score:.2f} +{delta:.1f} -> {self._score:.1f}"
        )

    def _average_similarity(self) -> float:
        values = [
            state.similarity
            for name, state in self._devices.items()
            if name != self._instructor and state.ready
        ]
        if not values:
            return 0.0
        return round(sum(values) / len(values), 3)

    def _check_milestones(self) -> None:
        if self._duration == 0 or self._start_time == 0:
            return

        elapsed_ratio = (time.monotonic() - self._start_time) / self._duration
        for threshold, pattern_id in _TIME_MILESTONES:
            if threshold not in self._milestones_hit and elapsed_ratio >= threshold:
                self._milestones_hit.add(threshold)
                self._queue_vibration_all(pattern_id)
                print(f"[GARDEN] {int(threshold * 100)}% time elapsed - pattern {pattern_id}")

        current = int(self._score / 50)
        if current > self._flower_milestone:
            self._flower_milestone = current
            self._queue_vibration_all(VIBR_FLOWER_50)
            print(f"[GARDEN] {current * 50} flowers - happy vibration!")

        if not self._last10_sent and 0 < self.time_remaining <= 10.0:
            self._last10_sent = True
            self._queue_vibration_all(VIBR_LAST_10)
            print("[GARDEN] Last 10 s - anxious vibration!")

    def _queue_vibration_all(self, pattern_id: int) -> None:
        for name in self._devices:
            self._pending_vibrations.setdefault(name, []).append(pattern_id)

    def _compute_plants(self) -> list[dict]:
        pts = self._config.sprout_points_per_plant
        num_full = int(self._score / pts)
        partial = (self._score % pts) / pts
        plants = [{"id": i, "growth": 1.0} for i in range(num_full)]
        if partial > 0.001:
            plants.append({"id": num_full, "growth": round(partial, 4)})
        return plants
