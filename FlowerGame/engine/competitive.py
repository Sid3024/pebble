from __future__ import annotations

import random

from ..config.config import FlowerConfig
from .controller import PersonGrowthTracker
from ble.constants import (VIBR_TEAM1, VIBR_TEAM2,
                            VIBR_MILESTONE1, VIBR_MILESTONE2,
                            VIBR_MILESTONE3, VIBR_WIN)

_MILESTONES = [(0.25, VIBR_MILESTONE1), (0.50, VIBR_MILESTONE2),
               (0.75, VIBR_MILESTONE3), (1.00, VIBR_WIN)]


class TeamState:
    """Growth state for one team in competitive mode."""

    def __init__(self, team_id: int, config: FlowerConfig) -> None:
        self.team_id = team_id
        self._config = config
        self._trackers: dict[str, PersonGrowthTracker] = {}
        self._total_growth: float = 0.0
        self.phase: str = "playing"
        self._milestones_hit: set[float] = set()

    def process_window(self, device_name: str, window_sum: float) -> int | None:
        """Process one window. Returns a vibration pattern ID if a milestone was
        just crossed, otherwise None."""
        if self.phase != "playing":
            return None

        if device_name not in self._trackers:
            print(f"[{device_name}] assigned to Team {self.team_id + 1} — collecting baseline")
            self._trackers[device_name] = PersonGrowthTracker(self._config)

        delta = self._trackers[device_name].process_window(window_sum)

        if delta != 0:
            self._total_growth = max(0.0, self._total_growth + delta)
            arrow = "↑" if delta > 0 else "↓"
            print(
                f"[Team {self.team_id + 1}][{device_name}] "
                f"growth {arrow}{abs(delta):.1f} → "
                f"{self._total_growth:.1f}/{self._config.total_growth_needed:.0f} "
                f"({self.progress * 100:.1f}%)"
            )

        if self._total_growth >= self._config.total_growth_needed:
            self.phase = "won"

        return self._check_milestone()

    @property
    def progress(self) -> float:
        return min(1.0, self._total_growth / self._config.total_growth_needed)

    def get_state(self) -> dict:
        return {
            "id":           self.team_id,
            "phase":        self.phase,
            "progress":     round(self.progress, 4),
            "total_growth": round(self._total_growth, 2),
            "num_devices":  len(self._trackers),
            "devices":      {n: {"phase": t.state.phase, "ready": t.is_ready}
                             for n, t in self._trackers.items()},
            "plants":       self._compute_plants(),
        }

    def _compute_plants(self) -> list[dict]:
        n = self._config.num_plants
        p = self.progress
        plants = []
        for i in range(n):
            start = i / n
            end   = (i + 1) / n
            if p <= start:
                growth = 0.0
            elif p >= end:
                growth = 1.0
            else:
                growth = (p - start) / (end - start)
            plants.append({"id": i, "growth": round(growth, 4)})
        return plants

    def _check_milestone(self) -> int | None:
        for threshold, pattern_id in _MILESTONES:
            if threshold not in self._milestones_hit and self.progress >= threshold:
                self._milestones_hit.add(threshold)
                print(f"[Team {self.team_id + 1}] {int(threshold*100)}% milestone "
                      f"— pattern {pattern_id}")
                return pattern_id
        return None

    def reset(self) -> None:
        self._trackers.clear()
        self._total_growth = 0.0
        self.phase = "playing"
        self._milestones_hit.clear()


class CompetitiveFlowerController:
    """
    Two-team competitive flower game.

    Phase flow:
      waiting → team_select (step 0: team 1 shakes in)
             → team_select (step 1: team 2 shakes in)
             → playing → won

    Vibration feedback:
      - Team assignment: VIBR_TEAM1 / VIBR_TEAM2 sent to the joining device
      - Milestones (25/50/75/100%): sent to all devices on that team
    """

    def __init__(self, config: FlowerConfig) -> None:
        self._config = config
        self._teams        = [TeamState(0, config), TeamState(1, config)]
        self._assignment:  dict[str, int] = {}
        self._pending_vibrations: dict[str, list[int]] = {}
        self._connected_devices: set[str] = set()   # all devices seen during selection
        self.phase:        str       = "waiting"
        self.winner:       int | None = None
        self._select_step: int       = 0

    # ── Controller interface ──────────────────────────────────

    def process_window(self, device_name: str, window_sum: float) -> None:
        if self.phase == "team_select":
            self._handle_select(device_name, window_sum)
        elif self.phase == "playing":
            self._handle_playing(device_name, window_sum)

    def start_session(self) -> None:
        self._teams               = [TeamState(0, self._config), TeamState(1, self._config)]
        self._assignment          = {}
        self._pending_vibrations  = {}
        self._connected_devices   = set()
        self._select_step         = 0
        self.winner               = None
        self.phase                = "team_select"
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
        print(f"[GARDEN] Game starting — Team 1: {t0}, Team 2: {t1} device(s).")
        self.phase = "playing"

    def reset(self) -> None:
        self._teams               = [TeamState(0, self._config), TeamState(1, self._config)]
        self._assignment          = {}
        self._pending_vibrations  = {}
        self._connected_devices   = set()
        self._select_step         = 0
        self.winner               = None
        self.phase                = "waiting"
        print("[GARDEN] Competitive session reset.")

    def pop_vibration_commands(self, device_name: str) -> list[int]:
        return self._pending_vibrations.pop(device_name, [])

    @property
    def _team1_quota(self) -> int:
        """Max devices allowed on Team 1 = floor(n/2), minimum 1."""
        return max(1, len(self._connected_devices) // 2)

    def get_state(self) -> dict:
        if self.phase == "team_select":
            counts = [sum(1 for t in self._assignment.values() if t == i)
                      for i in range(2)]
            quota  = self._team1_quota
            return {
                "mode":             "competitive",
                "phase":            "team_select",
                "team_select_step": self._select_step,
                "total_connected":  len(self._connected_devices),
                "teams": [
                    {"id": 0, "num_devices": counts[0],
                     "quota": quota, "locked": counts[0] >= quota},
                    {"id": 1, "num_devices": counts[1]},
                ],
            }
        return {
            "mode":   "competitive",
            "phase":  self.phase,
            "winner": self.winner,
            "teams":  [t.get_state() for t in self._teams],
        }

    # ── Internal ──────────────────────────────────────────────

    def _handle_select(self, device_name: str, window_sum: float) -> None:
        # Track every device that sends a window, even if not shaking
        self._connected_devices.add(device_name)

        if device_name in self._assignment:
            return

        if window_sum < self._config.team_select_shake_threshold:
            return

        if self._select_step == 0:
            # Team 1 selection — enforce quota
            team1_count = sum(1 for t in self._assignment.values() if t == 0)
            if team1_count >= self._team1_quota:
                print(f"[{device_name}] shake detected but Team 1 is full "
                      f"({team1_count}/{self._team1_quota}) — wait for Team 2 phase")
                return
            team = 0
        else:
            team = 1

        self._assignment[device_name] = team
        pattern = VIBR_TEAM1 if team == 0 else VIBR_TEAM2
        self._pending_vibrations.setdefault(device_name, []).append(pattern)
        counts = [sum(1 for t in self._assignment.values() if t == i) for i in range(2)]
        print(f"[{device_name}] joined Team {team + 1} via shake "
              f"(sum={window_sum:.1f}) — Team 1: {counts[0]}/{self._team1_quota}, "
              f"Team 2: {counts[1]}")

    def _handle_playing(self, device_name: str, window_sum: float) -> None:
        if self.winner is not None:
            return
        team_idx = self._assign_team(device_name)
        pattern  = self._teams[team_idx].process_window(device_name, window_sum)

        # Route milestone vibration to all devices on the same team
        if pattern is not None:
            for dev, team in self._assignment.items():
                if team == team_idx:
                    self._pending_vibrations.setdefault(dev, []).append(pattern)

        if self._teams[team_idx].phase == "won":
            self.winner = team_idx
            self.phase  = "won"
            print(f"[GARDEN] Team {team_idx + 1} wins — full bloom!")

    def _assign_team(self, device_name: str) -> int:
        """Balanced random assignment for devices that missed team selection."""
        if device_name not in self._assignment:
            counts = [sum(1 for t in self._assignment.values() if t == i)
                      for i in range(2)]
            if counts[0] < counts[1]:
                team = 0
            elif counts[1] < counts[0]:
                team = 1
            else:
                team = random.randint(0, 1)
            self._assignment[device_name] = team
            new_counts = [counts[i] + int(team == i) for i in range(2)]
            print(f"[{device_name}] late-assigned to Team {team + 1} "
                  f"(Team 1: {new_counts[0]}, Team 2: {new_counts[1]})")
        return self._assignment[device_name]
