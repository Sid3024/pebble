from __future__ import annotations

import math
import random
import time
from collections import deque

from ble.constants import VIBR_FLOWER_50, VIBR_LAST_10, VIBR_MILESTONE2, VIBR_MILESTONE3, VIBR_TEAM1, VIBR_TEAM2, VIBR_WIN
from ble.imu import ImuWindow

from ..config.config import FlowerConfig
from .controller import DeviceState, _REFERENCE_HISTORY, _TIME_MILESTONES
from .motion import selection_motion_score
from .similarity import SimilarityResult, best_similarity, fallback_score, update_gravity_estimate


class TeamState:
    def __init__(self, team_id: int, config: FlowerConfig) -> None:
        self.team_id = team_id
        self._config = config
        self._devices: dict[str, DeviceState] = {}
        self._score: float = 0.0
        self._flower_milestone: int = 0

    def update_gravity(self, device_name: str, window: ImuWindow, alpha: float) -> tuple[float, float, float]:
        state = self._devices.setdefault(device_name, DeviceState())
        state.gravity = update_gravity_estimate(
            state.gravity, (window.ax, window.ay, window.az), alpha, state.gravity_initialized)
        state.gravity_initialized = True
        return state.gravity

    def apply_similarity(self, device_name: str, result: SimilarityResult) -> bool:
        state = self._devices.setdefault(device_name, DeviceState())
        growth_score = result.score ** self._config.similarity_growth_exponent
        delta = self._config.growth_per_window * growth_score
        self._score = max(0.0, self._score + delta)

        state.phase = "matching" if result.score >= 0.65 else "following"
        state.ready = True
        state.similarity = result.score
        state.direction_score = result.direction_score
        state.magnitude_score = result.magnitude_score

        print(
            f"[Team {self.team_id + 1}][{device_name}] similarity={result.score:.2f} "
            f"+{delta:.1f} -> {self._score:.1f}"
        )

        current = int(self._score / 50)
        if current > self._flower_milestone:
            self._flower_milestone = current
            print(f"[Team {self.team_id + 1}] {current * 50} flowers - happy vibration!")
            return True
        return False

    @property
    def score(self) -> float:
        return self._score

    @property
    def progress(self) -> float:
        return 0.0

    def get_state(self) -> dict:
        return {
            "id": self.team_id,
            "score": int(self._score),
            "similarity": self._average_similarity(),
            "progress": round(self.progress, 4),
            "num_devices": len(self._devices),
            "devices": {
                name: {
                    "phase": state.phase,
                    "ready": state.ready,
                    "similarity": round(state.similarity, 3),
                    "direction_score": round(state.direction_score, 3),
                    "magnitude_score": round(state.magnitude_score, 3),
                }
                for name, state in self._devices.items()
            },
            "plants": self._compute_plants(),
        }

    def reset(self) -> None:
        self._devices.clear()
        self._score = 0.0
        self._flower_milestone = 0

    def _average_similarity(self) -> float:
        values = [state.similarity for state in self._devices.values() if state.ready]
        if not values:
            return 0.0
        return round(sum(values) / len(values), 3)

    def _compute_plants(self) -> list[dict]:
        pts = self._config.sprout_points_per_plant
        num_full = int(self._score / pts)
        partial = (self._score % pts) / pts
        plants = [{"id": i, "growth": 1.0} for i in range(num_full)]
        if partial > 0.001:
            plants.append({"id": num_full, "growth": round(partial, 4)})
        return plants


class CompetitiveFlowerController:
    """
    Two-team instructor-following flower game.

    Phase flow:
      waiting -> instructor_select -> team_select -> playing -> won
    """

    def __init__(self, config: FlowerConfig) -> None:
        self._config = config
        self._teams = [TeamState(0, config), TeamState(1, config)]
        self._assignment: dict[str, int] = {}
        self._pending_vibrations: dict[str, list[int]] = {}
        self._connected_devices: set[str] = set()
        self._instructor: str | None = None
        self._instructor_gravity: tuple[float, float, float] = (0.0, 0.0, 1.0)
        self._instructor_gravity_initialized: bool = False
        self._reference: ImuWindow | None = None
        self._reference_history: deque[ImuWindow] = deque(maxlen=_REFERENCE_HISTORY)
        self.phase: str = "waiting"
        self.winner: int | None = None
        self._select_step: int = 0
        self._duration: float = 0.0
        self._start_time: float = 0.0
        self._milestones_hit: set[float] = set()
        self._last10_sent: bool = False

    @property
    def time_remaining(self) -> float:
        if self.phase != "playing":
            return 0.0
        return max(0.0, self._duration - (time.monotonic() - self._start_time))

    @property
    def _student_capacity(self) -> int:
        return math.ceil(len(self._connected_devices) / 2)

    def process_window(self, device_name: str, window_sum: float) -> None:
        movement = max(0.0, window_sum / 300.0 - 1.0)
        self.process_imu_window(
            device_name,
            ImuWindow(0, movement, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        )

    def process_imu_window(self, device_name: str, window: ImuWindow) -> None:
        if self.phase == "instructor_select":
            self._handle_instructor_select(device_name, window)
        elif self.phase == "team_select":
            self._handle_select(device_name, window)
        elif self.phase == "playing":
            self._handle_playing(device_name, window)

    def start_session(self, duration_seconds: int) -> None:
        self._teams = [TeamState(0, self._config), TeamState(1, self._config)]
        self._assignment = {}
        self._pending_vibrations = {}
        self._connected_devices = set()
        self._instructor = None
        self._instructor_gravity = (0.0, 0.0, 1.0)
        self._instructor_gravity_initialized = False
        self._reference = None
        self._reference_history.clear()
        self._select_step = 0
        self.winner = None
        self.phase = "instructor_select"
        self._duration = float(duration_seconds)
        self._start_time = 0.0
        self._milestones_hit.clear()
        self._last10_sent = False
        print("[GARDEN] Competitive session - shake one pod to select the instructor.")

    def next_team(self) -> None:
        if self.phase == "team_select" and self._select_step == 0:
            self._select_step = 1
            print("[GARDEN] Team 1 locked - now selecting Team 2.")

    def begin_game(self) -> None:
        if self.phase != "team_select":
            return
        t0 = sum(1 for t in self._assignment.values() if t == 0)
        t1 = sum(1 for t in self._assignment.values() if t == 1)
        print(f"[GARDEN] Game starting - {int(self._duration)}s - Team 1: {t0}, Team 2: {t1}.")
        self._start_time = time.monotonic()
        self.phase = "playing"

    def reset(self) -> None:
        self._teams = [TeamState(0, self._config), TeamState(1, self._config)]
        self._assignment = {}
        self._pending_vibrations = {}
        self._connected_devices = set()
        self._instructor = None
        self._instructor_gravity = (0.0, 0.0, 1.0)
        self._instructor_gravity_initialized = False
        self._reference = None
        self._reference_history.clear()
        self._select_step = 0
        self.winner = None
        self.phase = "waiting"
        self._duration = 0.0
        self._start_time = 0.0
        self._milestones_hit.clear()
        self._last10_sent = False
        print("[GARDEN] Competitive session reset.")

    def pop_vibration_commands(self, device_name: str) -> list[int]:
        return self._pending_vibrations.pop(device_name, [])

    def get_state(self) -> dict:
        if self.phase == "instructor_select":
            return {
                "mode": "competitive",
                "phase": "instructor_select",
                "instructor": self._instructor,
                "instructor_ready": self._instructor is not None,
                "total_connected": len(self._connected_devices) + (1 if self._instructor else 0),
                "duration": int(self._duration),
                "teams": [{"id": 0, "num_devices": 0}, {"id": 1, "num_devices": 0}],
            }

        if self.phase == "team_select":
            counts = [sum(1 for t in self._assignment.values() if t == i) for i in range(2)]
            quota = self._student_capacity
            return {
                "mode": "competitive",
                "phase": "team_select",
                "instructor": self._instructor,
                "team_select_step": self._select_step,
                "total_connected": len(self._connected_devices) + (1 if self._instructor else 0),
                "student_capacity": quota,
                "duration": int(self._duration),
                "teams": [
                    {"id": 0, "num_devices": counts[0], "quota": quota, "locked": counts[0] >= quota},
                    {"id": 1, "num_devices": counts[1], "quota": quota, "locked": counts[1] >= quota},
                ],
            }

        return {
            "mode": "competitive",
            "phase": self.phase,
            "instructor": self._instructor,
            "time_remaining": round(self.time_remaining, 1),
            "duration": int(self._duration),
            "winner": self.winner,
            "teams": [t.get_state() for t in self._teams],
        }

    def _handle_instructor_select(self, device_name: str, window: ImuWindow) -> None:
        motion = selection_motion_score(window)
        if self._instructor is not None:
            if device_name == self._instructor:
                self._reference = window
            return
        if motion < self._config.instructor_select_shake_threshold:
            print(f"[{device_name}] instructor motion={motion:.3f} "
                  f"(need {self._config.instructor_select_shake_threshold:.3f})")
            return
        self._instructor = device_name
        self._reference = window
        self._pending_vibrations.setdefault(device_name, []).append(VIBR_MILESTONE2)
        print(f"[GARDEN] {device_name} selected as instructor (motion={motion:.3f}). "
              "Press Next to start team selection.")

    def confirm_instructor(self) -> None:
        if self.phase == "instructor_select" and self._instructor is not None:
            self.phase = "team_select"
            print("[GARDEN] Instructor confirmed. Team selection started.")

    def _handle_select(self, device_name: str, window: ImuWindow) -> None:
        motion = selection_motion_score(window)
        if device_name == self._instructor:
            self._reference = window
            return

        self._connected_devices.add(device_name)
        if device_name in self._assignment:
            return
        if motion < self._config.team_select_imu_threshold:
            print(f"[{device_name}] team motion={motion:.3f} "
                  f"(need {self._config.team_select_imu_threshold:.3f})")
            return

        team = self._select_step
        counts = [sum(1 for t in self._assignment.values() if t == i) for i in range(2)]
        quota = self._student_capacity
        if quota > 0 and counts[team] >= quota:
            print(f"[{device_name}] Team {team + 1} full ({counts[team]}/{quota})")
            return

        self._assignment[device_name] = team
        pattern = VIBR_TEAM1 if team == 0 else VIBR_TEAM2
        self._pending_vibrations.setdefault(device_name, []).append(pattern)
        print(f"[{device_name}] joined Team {team + 1}")

    def _handle_playing(self, device_name: str, window: ImuWindow) -> None:
        if self.time_remaining <= 0 and self.phase == "playing":
            self._end_game()
            return

        if device_name == self._instructor:
            self._reference = window
            self._reference_history.append(window)
            self._instructor_gravity = update_gravity_estimate(
                self._instructor_gravity, (window.ax, window.ay, window.az),
                self._config.similarity_gravity_ema_alpha, self._instructor_gravity_initialized)
            self._instructor_gravity_initialized = True
            return

        team_idx = self._assign_team(device_name)

        if not self._config.similarity_enabled:
            result = fallback_score(window, self._config.similarity_fallback_activity_scale)
        else:
            if not self._reference_history:
                return
            result = best_similarity(
                self._reference_history,
                window,
                min_movement_accel=self._config.similarity_min_movement_accel,
                instructor_gravity=self._instructor_gravity,
                student_gravity=self._teams[team_idx].update_gravity(device_name, window, self._config.similarity_gravity_ema_alpha),
                direction_penalty_exponent=self._config.similarity_direction_penalty_exponent,
            )
        flower_hit = self._teams[team_idx].apply_similarity(device_name, result)
        self._check_milestones()

        if flower_hit:
            for dev, team in self._assignment.items():
                if team == team_idx:
                    self._pending_vibrations.setdefault(dev, []).append(VIBR_FLOWER_50)

    def _end_game(self) -> None:
        self.phase = "won"
        scores = [t.score for t in self._teams]
        if scores[0] > scores[1]:
            self.winner = 0
        elif scores[1] > scores[0]:
            self.winner = 1
        else:
            self.winner = None
        print(
            f"[GARDEN] Time's up! Team 1: {scores[0]:.1f} Team 2: {scores[1]:.1f} "
            f"Winner: {'Tie' if self.winner is None else f'Team {self.winner + 1}'}"
        )
        for dev, team in self._assignment.items():
            if self.winner is None or team == self.winner:
                self._pending_vibrations.setdefault(dev, []).append(VIBR_WIN)

    def _check_milestones(self) -> None:
        if self._duration == 0 or self._start_time == 0:
            return
        elapsed_ratio = (time.monotonic() - self._start_time) / self._duration
        for threshold, pattern_id in _TIME_MILESTONES:
            if threshold not in self._milestones_hit and elapsed_ratio >= threshold:
                self._milestones_hit.add(threshold)
                for dev in self._assignment:
                    self._pending_vibrations.setdefault(dev, []).append(pattern_id)
                if self._instructor:
                    self._pending_vibrations.setdefault(self._instructor, []).append(pattern_id)
                print(f"[GARDEN] {int(threshold * 100)}% time elapsed - pattern {pattern_id}")

        remaining = self._duration - (time.monotonic() - self._start_time)
        if not self._last10_sent and 0 < remaining <= 10.0:
            self._last10_sent = True
            for dev in self._assignment:
                self._pending_vibrations.setdefault(dev, []).append(VIBR_LAST_10)
            if self._instructor:
                self._pending_vibrations.setdefault(self._instructor, []).append(VIBR_LAST_10)
            print("[GARDEN] Last 10 s - anxious vibration!")

    def _assign_team(self, device_name: str) -> int:
        if device_name not in self._assignment:
            counts = [sum(1 for t in self._assignment.values() if t == i) for i in range(2)]
            team = 0 if counts[0] <= counts[1] else 1
            if counts[0] == counts[1]:
                team = random.randint(0, 1)
            self._assignment[device_name] = team
            print(f"[{device_name}] late-assigned to Team {team + 1}")
        return self._assignment[device_name]
