from __future__ import annotations

import random

from ..config.config import FlowerConfig
from .controller import PersonGrowthTracker


class TeamState:
    """Growth state for one team in competitive mode."""

    def __init__(self, team_id: int, config: FlowerConfig) -> None:
        self.team_id = team_id
        self._config = config
        self._trackers: dict[str, PersonGrowthTracker] = {}
        self._total_growth: float = 0.0
        self.phase: str = "playing"

    def process_window(self, device_name: str, window_sum: float) -> None:
        if self.phase != "playing":
            return

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

    def reset(self) -> None:
        self._trackers.clear()
        self._total_growth = 0.0
        self.phase = "playing"


class CompetitiveFlowerController:
    """
    Two-team competitive flower game.

    Devices are assigned to teams on first contact using the strategy
    specified in config.team_pairing (currently only "random").
    The game ends when either team reaches total_growth_needed.
    """

    def __init__(self, config: FlowerConfig) -> None:
        self._config = config
        self._teams   = [TeamState(0, config), TeamState(1, config)]
        self._assignment: dict[str, int] = {}
        self.phase:  str       = "waiting"
        self.winner: int | None = None

    # ── Controller interface ──────────────────────────────────

    def process_window(self, device_name: str, window_sum: float) -> None:
        if self.phase != "playing":
            return

        team_idx = self._assign_team(device_name)
        self._teams[team_idx].process_window(device_name, window_sum)

        if self.winner is None:
            for i, team in enumerate(self._teams):
                if team.phase == "won":
                    self.winner = i
                    self.phase  = "won"
                    print(f"[GARDEN] Team {i + 1} wins — full bloom!")
                    break

    def start_session(self) -> None:
        self._teams      = [TeamState(0, self._config), TeamState(1, self._config)]
        self._assignment = {}
        self.winner      = None
        self.phase       = "playing"
        print("[GARDEN] Competitive session started.")

    def reset(self) -> None:
        self._teams      = [TeamState(0, self._config), TeamState(1, self._config)]
        self._assignment = {}
        self.winner      = None
        self.phase       = "waiting"
        print("[GARDEN] Competitive session reset.")

    def get_state(self) -> dict:
        return {
            "mode":   "competitive",
            "phase":  self.phase,
            "winner": self.winner,
            "teams":  [t.get_state() for t in self._teams],
        }

    # ── Internal ──────────────────────────────────────────────

    def _assign_team(self, device_name: str) -> int:
        if device_name not in self._assignment:
            counts = [
                sum(1 for t in self._assignment.values() if t == i)
                for i in range(2)
            ]
            # Always fill the smaller team first; random on a tie.
            # Guarantees equal sizes on even totals, +1 on odd totals.
            if counts[0] < counts[1]:
                team = 0
            elif counts[1] < counts[0]:
                team = 1
            else:
                team = random.randint(0, 1)
            self._assignment[device_name] = team
            new_counts = [counts[i] + int(team == i) for i in range(2)]
            print(f"[{device_name}] assigned to Team {team + 1} "
                  f"(Team 1: {new_counts[0]}, Team 2: {new_counts[1]})")
        return self._assignment[device_name]
