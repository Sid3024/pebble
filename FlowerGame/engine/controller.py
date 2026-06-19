"""
Single-team (cooperative) FlowerController for the FlowerGame.

This is the core game engine for the single/cooperative mode.  An instructor
pod is selected first (by shaking); then all other pods become students whose
movements are compared against the instructor via the similarity engine.

Key classes:
    DeviceState      : Dataclass tracking a pod's phase, gravity, similarity.
    FlowerController : Top-level controller that manages the instructor,
                       computes similarity scores for students, accumulates
                       a shared score, manages the countdown timer, triggers
                       vibration milestones, and broadcasts state via WebSocket.

Similarity scoring flow:
    1. Instructor shakes a pod -> selected via motion threshold.
    2. Facilitator confirms -> phase becomes "playing", timer starts.
    3. First 3 seconds: warmup (gravity EMA stabilises, no scoring).
    4. Each student window is compared axis-by-axis (ax, ay, az) against the
       instructor's recent windows (phase-compensated).
    5. Score = growth_per_window * (similarity ^ exponent).

Milestone vibration system:
    - Time-based (50% and 75% of game duration elapsed).
    - Score-based (every 50 flowers).
    - Last-10-seconds warning.
    Each triggers a vibration pattern sent to all connected pods.

Plant computation:
    Score / sprout_points_per_plant = number of flowers.  Dashboard renders
    the garden from this list.

Dependencies:
    - ble.imu       : ImuWindow dataclass.
    - ble.constants : Vibration pattern IDs (VIBR_*).
    - .similarity   : compute_similarity, best_similarity, merge_windows.
    - .motion       : selection_motion_score for instructor selection.

How it fits into Pebble:
    FlowerWSServer creates a FlowerController when the dashboard sends
    {"action":"start","mode":"single"}.  process_imu_window() is called
    from BLE notification callbacks.  get_state() is called every
    broadcast_interval_s to push game state to the dashboard.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

from ble.constants import VIBR_FLOWER_50, VIBR_LAST_10, VIBR_MILESTONE2, VIBR_MILESTONE3, VIBR_WIN
from ble.imu import ImuWindow

from ..config.config import FlowerConfig
from .motion import selection_motion_score
from .similarity import SimilarityResult, best_similarity, fallback_score, gravity_from_roll_pitch, merge_windows, update_gravity_estimate

# Each pod's sampling window starts independently when it connects, so the
# instructor's and student's windows aren't phase-aligned. Keep this many of
# the instructor's most recent windows and match the student's window against
# whichever one overlaps best (see similarity.best_similarity).
_REFERENCE_HISTORY = 2

_TIME_MILESTONES = [
    (0.50, VIBR_MILESTONE2),
    (0.75, VIBR_MILESTONE3),
]


@dataclass
class DeviceState:
    phase: str = "waiting"
    ready: bool = False
    similarity: float = 0.0
    direction_score: float = 0.0
    magnitude_score: float = 0.0
    activity: float = 0.0
    last_seen: float = field(default_factory=time.monotonic)
    gravity: tuple[float, float, float] = (0.0, 0.0, 1.0)
    gravity_initialized: bool = False


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
        self._reference_history: deque[ImuWindow] = deque(maxlen=_REFERENCE_HISTORY)
        self._instructor_accum: list[ImuWindow] = []
        self._student_accum: dict[str, list[ImuWindow]] = {}
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
        self._reference_history.clear()
        self._instructor_accum.clear()
        self._student_accum.clear()
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
        self._reference_history.clear()
        self._instructor_accum.clear()
        self._student_accum.clear()
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
                "direction_score": round(state.direction_score, 3),
                "magnitude_score": round(state.magnitude_score, 3),
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

        n = self._config.similarity_accumulate_windows

        if device_name == self._instructor:
            state = self._devices[device_name]
            state.phase = "instructor"
            state.ready = True
            # Track gravity DIRECTION from roll/pitch (not from ax/ay/az, which
            # are already gravity-removed by firmware). This tells us which way
            # "down" is for this pod, used for vertical/horizontal decomposition.
            gravity_dir = gravity_from_roll_pitch(window.roll, window.pitch)
            state.gravity = update_gravity_estimate(
                state.gravity, gravity_dir,
                self._config.similarity_gravity_ema_alpha, state.gravity_initialized)
            state.gravity_initialized = True
            self._reference = window
            self._instructor_accum.append(window)
            if len(self._instructor_accum) >= n:
                self._reference_history.append(merge_windows(self._instructor_accum))
                self._instructor_accum = []
            return

        # 3-second warmup: let gravity EMA stabilise before scoring begins.
        # Accumulation is intentionally skipped so the first scored window is fresh.
        if time.monotonic() - self._start_time < 3.0:
            student_state = self._devices[device_name]
            gravity_dir = gravity_from_roll_pitch(window.roll, window.pitch)
            student_state.gravity = update_gravity_estimate(
                student_state.gravity, gravity_dir,
                self._config.similarity_gravity_ema_alpha, student_state.gravity_initialized)
            student_state.gravity_initialized = True
            return

        if not self._config.similarity_enabled:
            result = fallback_score(window, self._config.similarity_fallback_activity_scale)
            self._apply_similarity(device_name, result)
            self._check_milestones()
            return

        if not self._reference_history:
            return

        student_state = self._devices[device_name]
        gravity_dir = gravity_from_roll_pitch(window.roll, window.pitch)
        student_state.gravity = update_gravity_estimate(
            student_state.gravity, gravity_dir,
            self._config.similarity_gravity_ema_alpha, student_state.gravity_initialized)
        student_state.gravity_initialized = True

        self._student_accum.setdefault(device_name, []).append(window)
        if len(self._student_accum[device_name]) < n:
            return
        merged = merge_windows(self._student_accum[device_name])
        self._student_accum[device_name] = []

        result = best_similarity(
            self._reference_history,
            merged,
            min_movement_accel=self._config.similarity_min_movement_accel,
            instructor_gravity=self._devices[self._instructor].gravity,
            student_gravity=student_state.gravity,
            direction_penalty_exponent=self._config.similarity_direction_penalty_exponent,
        )
        self._apply_similarity(device_name, result)
        self._check_milestones()

    def _apply_similarity(self, device_name: str, result: SimilarityResult) -> None:
        growth_score = result.score ** self._config.similarity_growth_exponent
        delta = self._config.growth_per_window * growth_score
        self._score = max(0.0, self._score + delta)

        state = self._devices[device_name]
        state.phase = "matching" if result.score >= 0.65 else "following"
        state.ready = True
        state.similarity = result.score
        state.direction_score = result.direction_score
        state.magnitude_score = result.magnitude_score

        print(
            f"[{device_name}] similarity={result.score:.2f} "
            f"direction={result.direction_score:.2f} "
            f"magnitude={result.magnitude_score:.2f} +{delta:.1f} -> {self._score:.1f}"
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
