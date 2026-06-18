"""
Two-team competitive FlowerController for the FlowerGame.

This module implements the competitive game mode where players split into two
teams and race to grow more flowers before the countdown timer expires.

Key classes:
    TeamState                    : Holds one team's score, per-device trackers,
                                   and plant computation.
    CompetitiveFlowerController  : Top-level controller managing the full game
                                   lifecycle: team selection -> playing -> won.

Phase flow (competitive mode):
    waiting
      -> team_select (step 0) -- pods shake to join Team 1
      -> team_select (step 1) -- pods shake to join Team 2 (via next_team())
      -> playing              -- timer starts (via begin_game())
      -> won                  -- timer expires; highest-scoring team wins

Team selection algorithm:
    During team_select, each incoming window_sum is compared against
    team_select_shake_threshold (default 330).  If a pod's window sum exceeds
    the threshold, it is assigned to the current team (step 0 = Team 1,
    step 1 = Team 2).  Team 1 has a quota of half the connected devices
    (minimum 1).  Once full, additional pods are rejected until the dashboard
    advances to Team 2.

Late-joiner handling:
    Pods that connect during the "playing" phase (after team selection is done)
    are auto-assigned to the smaller team (ties broken randomly).

Scoring:
    Identical to the single-team mode (PersonGrowthTracker from controller.py),
    but each team accumulates score independently via its own TeamState.

Winner determination:
    When the timer expires, the team with the higher score wins.  If scores are
    equal, winner is None (tie).  The winning team's pods receive a VIBR_WIN
    vibration; on a tie, all pods receive it.

Milestones:
    Time-based (50 %, 75 %) and last-10s warnings are sent to ALL pods
    regardless of team.  Score-based (every 50 flowers) milestones are sent
    only to the team that crossed the threshold.

Dependencies:
    - FlowerConfig, PersonGrowthTracker, _TIME_MILESTONES from this package.
    - ble.constants: VIBR_TEAM1/2, VIBR_WIN, VIBR_FLOWER_50, VIBR_LAST_10.
    - random (stdlib): For tie-breaking in late-joiner assignment.

How it fits into Pebble:
    FlowerWSServer creates a CompetitiveFlowerController when the dashboard
    sends {"action":"start","mode":"competitive"}.  The WS server proxies
    process_window() calls from BLE clients.  The dashboard drives phase
    transitions via next_team() and begin_game() actions.
"""

from __future__ import annotations

import random
import time

from ..config.config import FlowerConfig
from .controller import PersonGrowthTracker, _TIME_MILESTONES
from ble.constants import (VIBR_TEAM1, VIBR_TEAM2, VIBR_WIN, VIBR_FLOWER_50, VIBR_LAST_10)


class TeamState:
    """
    Score state and device tracking for one team in competitive mode.

    Each team has its own set of PersonGrowthTrackers (one per device assigned
    to this team) and an independent cumulative score.

    Attributes:
        team_id: 0 for Team 1, 1 for Team 2 (zero-indexed internally, but
                 displayed as 1-indexed in log messages).
    """

    def __init__(self, team_id: int, config: FlowerConfig) -> None:
        """
        Args:
            team_id: 0 or 1.
            config:  FlowerConfig with growth thresholds and point values.
        """
        self.team_id = team_id
        self._config = config
        self._trackers: dict[str, PersonGrowthTracker] = {}  # device_name -> tracker
        self._score:         float = 0.0    # cumulative team score
        self._flower_milestone: int = 0     # how many 50-flower marks passed

    def process_window(self, device_name: str, window_sum: float) -> bool:
        """
        Process one window for a device belonging to this team.

        Creates a PersonGrowthTracker for new devices, delegates scoring, and
        checks for the 50-flower milestone.

        Args:
            device_name: BLE name of the pod.
            window_sum:  Aggregated acceleration sum for one time window.

        Returns:
            True if a 50-flower milestone was just crossed (caller should
            send VIBR_FLOWER_50 to this team's devices).
        """
        # Auto-register new devices with a fresh baseline tracker
        if device_name not in self._trackers:
            print(f"[{device_name}] Team {self.team_id + 1} — collecting baseline")
            self._trackers[device_name] = PersonGrowthTracker(self._config)

        # Get score delta from per-device tracker
        delta = self._trackers[device_name].process_window(window_sum)

        # Update team score (clamped at 0)
        if delta != 0:
            self._score = max(0.0, self._score + delta)
            arrow = "↑" if delta > 0 else "↓"
            print(f"[Team {self.team_id + 1}][{device_name}] "
                  f"{arrow}{abs(delta):.1f} → {self._score:.1f}")

        # Check if a new 50-flower milestone was crossed
        current = int(self._score / 50)
        if current > self._flower_milestone:
            self._flower_milestone = current
            print(f"[Team {self.team_id + 1}] {current * 50} flowers — happy vibration!")
            return True
        return False

    @property
    def score(self) -> float:
        """The team's cumulative score (read-only)."""
        return self._score

    @property
    def progress(self) -> float:
        """Progress bar value (unused -- flowers are unlimited). Always 0.0."""
        return 0.0   # progress bar removed -- flowers are unlimited

    def get_state(self) -> dict:
        """
        Build a state dict for this team, suitable for JSON serialization.

        Includes team ID, score, device phases, and the plant list.
        """
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
        """
        Convert score into a plant list (same logic as FlowerController._compute_plants).

        Returns:
            List of {"id": int, "growth": float} dicts.
        """
        pts      = self._config.sprout_points_per_plant
        num_full = int(self._score / pts)
        partial  = (self._score % pts) / pts
        plants   = [{"id": i, "growth": 1.0} for i in range(num_full)]
        if partial > 0.001:
            plants.append({"id": num_full, "growth": round(partial, 4)})
        return plants

    def reset(self) -> None:
        """Clear all trackers and reset the score to zero."""
        self._trackers.clear()
        self._score = 0.0


class CompetitiveFlowerController:
    """
    Two-team timed competitive flower game controller.

    Phase flow:
      waiting -> team_select (step 0) -> team_select (step 1) -> playing -> won

    The dashboard drives transitions:
      - start_session() : waiting -> team_select
      - next_team()     : step 0 -> step 1
      - begin_game()    : team_select -> playing (starts the countdown timer)
      - reset()         : any -> waiting

    Game ends when the countdown timer expires.
    Winner = team with higher score; tie = winner stays None.
    """

    def __init__(self, config: FlowerConfig) -> None:
        """
        Args:
            config: FlowerConfig with all game tuning parameters.
        """
        self._config = config
        self._teams        = [TeamState(0, config), TeamState(1, config)]
        self._assignment:  dict[str, int] = {}        # device_name -> team index (0 or 1)
        self._pending_vibrations: dict[str, list[int]] = {}  # device -> [pattern_id, ...]
        self._connected_devices: set[str] = set()     # all device names seen during select
        self.phase:        str       = "waiting"       # current game phase
        self.winner:       int | None = None           # 0, 1, or None (tie / not yet decided)
        self._select_step: int       = 0               # 0 = selecting Team 1, 1 = selecting Team 2
        self._duration:    float     = 0.0             # total game duration in seconds
        self._start_time:  float     = 0.0             # monotonic timestamp when playing began
        self._milestones_hit: set[float] = set()       # time thresholds already triggered
        self._last10_sent: bool      = False           # True once last-10s warning fires

    # ── Time ──────────────────────────────────────────────────

    @property
    def time_remaining(self) -> float:
        """Seconds remaining in the current game, or 0 if not playing."""
        if self.phase != "playing":
            return 0.0
        return max(0.0, self._duration - (time.monotonic() - self._start_time))

    @property
    def _team1_quota(self) -> int:
        """
        Maximum number of devices allowed on Team 1 during selection.

        Set to half the total connected devices (minimum 1), ensuring a
        roughly balanced split before Team 2 selection begins.
        """
        return max(1, len(self._connected_devices) // 2)

    # ── Controller interface ──────────────────────────────────

    def process_window(self, device_name: str, window_sum: float) -> None:
        """
        Route an incoming window to the appropriate handler based on game phase.

        - team_select: Check if the pod is shaking hard enough to join a team.
        - playing:     Forward to the assigned team's scoring logic.
        - Other phases: Ignored.

        Args:
            device_name: BLE name of the pod.
            window_sum:  Aggregated acceleration sum for one time window.
        """
        if self.phase == "team_select":
            self._handle_select(device_name, window_sum)
        elif self.phase == "playing":
            self._handle_playing(device_name, window_sum)

    def start_session(self, duration_seconds: int) -> None:
        """
        Start a new competitive session, entering the team_select phase.

        Resets all state and begins Team 1 selection.  The countdown timer
        does NOT start until begin_game() is called.

        Args:
            duration_seconds: Game duration once playing begins.
        """
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
        self._last10_sent         = False
        print("[GARDEN] Competitive session — team selection started (Team 1).")

    def next_team(self) -> None:
        """
        Lock Team 1 and advance to Team 2 selection (step 0 -> step 1).

        Called by the dashboard when the instructor clicks "Next Team".
        Does nothing if not in team_select or already on step 1.
        """
        if self.phase == "team_select" and self._select_step == 0:
            self._select_step = 1
            print("[GARDEN] Team 1 locked — now selecting Team 2.")

    def begin_game(self) -> None:
        """
        End team selection and start the countdown timer (begin playing).

        Called by the dashboard when the instructor clicks "Start Game".
        Records the current monotonic time as the start and transitions to
        the "playing" phase.
        """
        if self.phase != "team_select":
            return
        t0 = sum(1 for t in self._assignment.values() if t == 0)
        t1 = sum(1 for t in self._assignment.values() if t == 1)
        print(f"[GARDEN] Game starting — {int(self._duration)}s — "
              f"Team 1: {t0}, Team 2: {t1} device(s).")
        self._start_time = time.monotonic()
        self.phase = "playing"

    def reset(self) -> None:
        """Reset the controller to the initial 'waiting' state (no active game)."""
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
        self._last10_sent         = False
        print("[GARDEN] Competitive session reset.")

    def pop_vibration_commands(self, device_name: str) -> list[int]:
        """
        Drain and return all pending vibration pattern IDs for a given device.

        Args:
            device_name: BLE name of the pod.

        Returns:
            List of integer pattern IDs (may be empty).
        """
        return self._pending_vibrations.pop(device_name, [])

    def get_state(self) -> dict:
        """
        Build a snapshot of the game state for the dashboard.

        During team_select, returns team counts, quotas, and selection step.
        During playing/won, returns per-team state with scores and plants.
        """
        if self.phase == "team_select":
            # During selection, the dashboard needs to know how many devices
            # are on each team and whether Team 1's quota is full.
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
        # During playing or won, return full team state with scores and plants.
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
        """
        Handle a window during the team_select phase.

        Algorithm:
            1. Record the device as connected (even if it doesn't shake).
            2. If already assigned, skip (no double-assignment).
            3. If window_sum < shake threshold, skip (pod is at rest).
            4. If step 0: assign to Team 1 if quota not full.
            5. If step 1: assign to Team 2.
            6. Queue a team-assignment vibration (VIBR_TEAM1 or VIBR_TEAM2).

        Args:
            device_name: BLE name of the pod.
            window_sum:  Aggregated acceleration sum (compared against threshold).
        """
        # Track every device that sends data, even if they don't shake
        self._connected_devices.add(device_name)

        # Already assigned -- ignore subsequent windows
        if device_name in self._assignment:
            return
        # Below shake threshold -- pod is at rest, not trying to join
        if window_sum < self._config.team_select_shake_threshold:
            return

        # Assign to the appropriate team based on current selection step
        if self._select_step == 0:
            team1_count = sum(1 for t in self._assignment.values() if t == 0)
            if team1_count >= self._team1_quota:
                print(f"[{device_name}] Team 1 full ({team1_count}/{self._team1_quota})")
                return
            team = 0
        else:
            team = 1

        # Record the assignment and send a haptic confirmation
        self._assignment[device_name] = team
        pattern = VIBR_TEAM1 if team == 0 else VIBR_TEAM2
        self._pending_vibrations.setdefault(device_name, []).append(pattern)
        counts = [sum(1 for t in self._assignment.values() if t == i) for i in range(2)]
        print(f"[{device_name}] joined Team {team + 1} — "
              f"Team 1: {counts[0]}/{self._team1_quota}, Team 2: {counts[1]}")

    def _handle_playing(self, device_name: str, window_sum: float) -> None:
        """
        Handle a window during the playing phase.

        Checks the timer, auto-assigns late joiners, delegates scoring to the
        device's team, checks milestones, and sends per-team flower vibrations.

        Args:
            device_name: BLE name of the pod.
            window_sum:  Aggregated acceleration sum for one time window.
        """
        # Check if timer expired
        if self.time_remaining <= 0 and self.phase == "playing":
            self._end_game()
            return

        # Auto-assign late joiners to the smaller team
        team_idx    = self._assign_team(device_name)
        # Delegate scoring to the team; returns True if 50-flower milestone crossed
        flower_hit  = self._teams[team_idx].process_window(device_name, window_sum)
        self._check_milestones()

        # If a 50-flower milestone was crossed, vibrate all devices on that team
        if flower_hit:
            for dev, team in self._assignment.items():
                if team == team_idx:
                    self._pending_vibrations.setdefault(dev, []).append(VIBR_FLOWER_50)

    def _end_game(self) -> None:
        """
        End the game: determine the winner and send victory vibrations.

        Winner = team with higher score.  On a tie, winner is None and all
        pods receive the win vibration.
        """
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
        """
        Check and fire time-based and last-10s vibration milestones.

        Unlike single-team mode, competitive milestones are sent to ALL pods
        (both teams), since they represent game-wide time events.
        """
        if self._duration == 0 or self._start_time == 0:
            return
        # Time-based milestones: compute elapsed fraction of total duration
        elapsed_ratio = (time.monotonic() - self._start_time) / self._duration
        for threshold, pattern_id in _TIME_MILESTONES:
            if threshold not in self._milestones_hit and elapsed_ratio >= threshold:
                self._milestones_hit.add(threshold)
                # Send to ALL assigned devices (both teams)
                for dev in self._assignment:
                    self._pending_vibrations.setdefault(dev, []).append(pattern_id)
                print(f"[GARDEN] {int(threshold*100)}% time elapsed — pattern {pattern_id}")

        # Last 10 seconds warning (fires once, sent to all pods)
        remaining = self._duration - (time.monotonic() - self._start_time)
        if not self._last10_sent and 0 < remaining <= 10.0:
            self._last10_sent = True
            for dev in self._assignment:
                self._pending_vibrations.setdefault(dev, []).append(VIBR_LAST_10)
            print("[GARDEN] Last 10 s — anxious vibration!")

    def _assign_team(self, device_name: str) -> int:
        """
        Get or assign a team for a device (used for late joiners during playing).

        Late joiners are assigned to the smaller team.  If both teams have the
        same count, the assignment is random (50/50).

        Args:
            device_name: BLE name of the pod.

        Returns:
            Team index (0 or 1).
        """
        if device_name not in self._assignment:
            counts = [sum(1 for t in self._assignment.values() if t == i)
                      for i in range(2)]
            team = 0 if counts[0] <= counts[1] else 1
            if counts[0] == counts[1]:
                team = random.randint(0, 1)
            self._assignment[device_name] = team
            print(f"[{device_name}] late-assigned to Team {team + 1}")
        return self._assignment[device_name]
