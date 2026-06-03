from __future__ import annotations

import random
import time

from ..config.config import FlowerConfig
from .controller import PersonGrowthTracker, _TIME_MILESTONES
from ble.constants import (VIBR_TEAM1, VIBR_TEAM2, VIBR_WIN, VIBR_FLOWER_50)


class TeamState:
    """Score state for one team in competitive mode."""

    def __init__(self, team_id: int, config: FlowerConfig) -> None:
        self.team_id = team_id
        self._config = config
        self._trackers: dict[str, PersonGrowthTracker] = {}
        self._score:         float = 0.0
        self._flower_milestone: int = 0   # how many 50-flower marks passed

    def process_window(self, device_name: str, window_sum: float) -> bool:
        """Returns True if a 50-flower milestone was just crossed."""
        if device_name not in self._trackers:
            print(f"[{device_name}] Team {self.team_id + 1} — collecting baseline")
            self._trackers[device_name] = PersonGrowthTracker(self._config)

        delta = self._trackers[device_name].process_window(window_sum)

        if delta != 0:
            self._score = max(0.0, self._score + delta)
            arrow = "↑" if delta > 0 else "↓"
            print(f"[Team {self.team_id + 1}][{device_name}] "
                  f"{arrow}{abs(delta):.1f} → {self._score:.1f}")

        current = int(self._score / 50)
        if current > self._flower_milestone:
            self._flower_milestone = current
            print(f"[Team {self.team_id + 1}] {current * 50} flowers — happy vibration!")
            return True
        return False

    @property
    def score(self) -> float:
        return self._score

    @property
    def progress(self) -> float:
        return 0.0   # progress bar removed — flowers are unlimited

    def get_state(self) -> dict:
        return {
            "id":          self.team_id,
            "score":       int(self._score),
            "progress":    round(self.progress, 4),
            "num_devices": len(self._trackers),
            "devices":     {n: {"phase": t.state.phase, "ready": t.is_ready}
                            for n, t in self._trackers.items()},
            "plants":      self._compute_plants(),
        }

    def _compute_plants(self) -> list[dict]:
        pts      = self._config.sprout_points_per_plant
        num_full = int(self._score / pts)
        partial  = (self._score % pts) / pts
        plants   = [{"id": i, "growth": 1.0} for i in range(num_full)]
        if partial > 0.001:
            plants.append({"id": num_full, "growth": round(partial, 4)})
        return plants

    def reset(self) -> None:
        self._trackers.clear()
        self._score = 0.0


class CompetitiveFlowerController:
    """
    Two-team timed competitive flower game.

    Phase flow:
      waiting → team_select (step 0) → team_select (step 1) → playing → won

    Game ends when the countdown timer expires.
    Winner = team with higher score; tie = winner stays None.
    """

    def __init__(self, config: FlowerConfig) -> None:
        self._config = config
        self._teams        = [TeamState(0, config), TeamState(1, config)]
        self._assignment:  dict[str, int] = {}
        self._pending_vibrations: dict[str, list[int]] = {}
        self._connected_devices: set[str] = set()
        self.phase:        str       = "waiting"
        self.winner:       int | None = None
        self._select_step: int       = 0
        self._duration:    float     = 0.0
        self._start_time:  float     = 0.0
        self._milestones_hit: set[float] = set()

    # ── Time ──────────────────────────────────────────────────

    @property
    def time_remaining(self) -> float:
        if self.phase != "playing":
            return 0.0
        return max(0.0, self._duration - (time.monotonic() - self._start_time))

    @property
    def _team1_quota(self) -> int:
        return max(1, len(self._connected_devices) // 2)

    # ── Controller interface ──────────────────────────────────

    def process_window(self, device_name: str, window_sum: float) -> None:
        if self.phase == "team_select":
            self._handle_select(device_name, window_sum)
        elif self.phase == "playing":
            self._handle_playing(device_name, window_sum)

    def start_session(self, duration_seconds: int) -> None:
        self._teams               = [TeamState(0, self._config), TeamState(1, self._config)]
        self._assignment          = {}
        self._pending_vibrations  = {}
        self._connected_devices   = set()
        self._select_step         = 0
        self.winner               = None
        self.phase                = "team_select"
        self._duration            = float(duration_seconds)
        self._start_time          = 0.0   # timer starts in begin_game()
        self._milestones_hit.clear()
        print("[GARDEN] Competitive session — team selection started (Team 1).")

    def next_team(self) -> None:
        if self.phase == "team_select" and self._select_step == 0:
            self._select_step = 1
            print("[GARDEN] Team 1 locked — now selecting Team 2.")

    def begin_game(self) -> None:
        if self.phase != "team_select":
            return
        t0 = sum(1 for t in self._assignment.values() if t == 0)
        t1 = sum(1 for t in self._assignment.values() if t == 1)
        print(f"[GARDEN] Game starting — {int(self._duration)}s — "
              f"Team 1: {t0}, Team 2: {t1} device(s).")
        self._start_time = time.monotonic()
        self.phase = "playing"

    def reset(self) -> None:
        self._teams               = [TeamState(0, self._config), TeamState(1, self._config)]
        self._assignment          = {}
        self._pending_vibrations  = {}
        self._connected_devices   = set()
        self._select_step         = 0
        self.winner               = None
        self.phase                = "waiting"
        self._duration            = 0.0
        self._start_time          = 0.0
        self._milestones_hit.clear()
        print("[GARDEN] Competitive session reset.")

    def pop_vibration_commands(self, device_name: str) -> list[int]:
        return self._pending_vibrations.pop(device_name, [])

    def get_state(self) -> dict:
        if self.phase == "team_select":
            counts = [sum(1 for t in self._assignment.values() if t == i)
                      for i in range(2)]
            quota = self._team1_quota
            return {
                "mode":             "competitive",
                "phase":            "team_select",
                "team_select_step": self._select_step,
                "total_connected":  len(self._connected_devices),
                "duration":         int(self._duration),
                "teams": [
                    {"id": 0, "num_devices": counts[0],
                     "quota": quota, "locked": counts[0] >= quota},
                    {"id": 1, "num_devices": counts[1]},
                ],
            }
        return {
            "mode":           "competitive",
            "phase":          self.phase,
            "time_remaining": round(self.time_remaining, 1),
            "duration":       int(self._duration),
            "winner":         self.winner,
            "teams":          [t.get_state() for t in self._teams],
        }

    # ── Internal ──────────────────────────────────────────────

    def _handle_select(self, device_name: str, window_sum: float) -> None:
        self._connected_devices.add(device_name)

        if device_name in self._assignment:
            return
        if window_sum < self._config.team_select_shake_threshold:
            return

        if self._select_step == 0:
            team1_count = sum(1 for t in self._assignment.values() if t == 0)
            if team1_count >= self._team1_quota:
                print(f"[{device_name}] Team 1 full ({team1_count}/{self._team1_quota})")
                return
            team = 0
        else:
            team = 1

        self._assignment[device_name] = team
        pattern = VIBR_TEAM1 if team == 0 else VIBR_TEAM2
        self._pending_vibrations.setdefault(device_name, []).append(pattern)
        counts = [sum(1 for t in self._assignment.values() if t == i) for i in range(2)]
        print(f"[{device_name}] joined Team {team + 1} — "
              f"Team 1: {counts[0]}/{self._team1_quota}, Team 2: {counts[1]}")

    def _handle_playing(self, device_name: str, window_sum: float) -> None:
        if self.time_remaining <= 0 and self.phase == "playing":
            self._end_game()
            return

        team_idx    = self._assign_team(device_name)
        flower_hit  = self._teams[team_idx].process_window(device_name, window_sum)
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
            self.winner = None  # tie
        print(f"[GARDEN] Time's up! Team 1: {scores[0]:.1f}  Team 2: {scores[1]:.1f}  "
              f"Winner: {'Tie' if self.winner is None else f'Team {self.winner + 1}'}")
        # Win vibration for all devices on the winning team (or all on tie)
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
                # Send to all devices on both teams
                for dev in self._assignment:
                    self._pending_vibrations.setdefault(dev, []).append(pattern_id)
                print(f"[GARDEN] {int(threshold*100)}% time elapsed — pattern {pattern_id}")

    def _assign_team(self, device_name: str) -> int:
        if device_name not in self._assignment:
            counts = [sum(1 for t in self._assignment.values() if t == i)
                      for i in range(2)]
            team = 0 if counts[0] <= counts[1] else 1
            if counts[0] == counts[1]:
                team = random.randint(0, 1)
            self._assignment[device_name] = team
            print(f"[{device_name}] late-assigned to Team {team + 1}")
        return self._assignment[device_name]
