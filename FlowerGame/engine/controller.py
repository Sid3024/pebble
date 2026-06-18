"""
Single-team (cooperative) FlowerController and per-device scoring logic.

This is the core game engine for the cooperative mode of FlowerGame.  All
connected pods contribute to a single shared score, which is converted into
virtual flowers displayed on the dashboard.

Key classes:
    DeviceState           : Tiny dataclass tracking a pod's current phase.
    PersonGrowthTracker   : Per-device object that collects a baseline, then
                            converts each incoming window sum into a score delta.
    FlowerController      : Top-level controller that aggregates all devices'
                            deltas into a shared score, manages the countdown
                            timer, triggers vibration milestones, and exposes
                            the full game state for the WebSocket broadcast.

Scoring algorithm (PersonGrowthTracker.process_window):
    1. The first N windows (baseline_n_windows) are used to learn the device's
       resting level via BaselineCalculator (from the external ``effort`` package).
    2. Once the baseline is ready, each subsequent window is compared against
       the "expected effort" derived from the baseline:
       - window_sum > expected * (1 + growth_margin)  -->  ACTIVE phase.
         Score delta = growth_per_window * (window_sum / expected).
         Harder shaking -> higher ratio -> more points.  No upper cap.
       - window_sum < expected * (1 - wilt_margin)    -->  WILT phase.
         Score delta = -wilt_per_window (currently 0 by default).
       - Otherwise                                    -->  IDLE phase.
         Score delta = idle_growth_per_window (slow passive growth).

Milestone vibration system:
    The controller checks for three kinds of milestones after every window:
    - Time-based (50 % and 75 % of game duration elapsed).
    - Score-based (every 50 flowers).
    - Last-10-seconds warning.
    Each triggers a vibration pattern sent to all connected pods.

Plant computation:
    Score is divided by sprout_points_per_plant to determine the number of
    fully-grown flowers plus one partially-grown flower.  The dashboard uses
    this list to render the garden.

Dependencies:
    - effort.baseline : BaselineCalculator, expected_effort -- external package
      for computing the resting baseline and expected effort from window sums.
    - ble.constants   : Vibration pattern IDs (VIBR_*).

How it fits into Pebble:
    FlowerWSServer creates a FlowerController when the dashboard sends a
    {"action":"start","mode":"single"} message.  process_window() is called
    from BLE notification callbacks (via the WS server proxy).  get_state()
    is called every broadcast_interval_s to push game state to the dashboard.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..config.config import FlowerConfig
from effort.baseline import BaselineCalculator, expected_effort
from ble.constants import VIBR_MILESTONE2, VIBR_MILESTONE3, VIBR_WIN, VIBR_FLOWER_50, VIBR_LAST_10

# Time-elapsed thresholds (fraction of total duration) that trigger vibration.
# Each entry is (elapsed_fraction, vibration_pattern_id).
# These are checked after every process_window() call and fire at most once each.
_TIME_MILESTONES = [
    (0.50, VIBR_MILESTONE2),   # 50 % elapsed -> three medium pulses
    (0.75, VIBR_MILESTONE3),   # 75 % elapsed -> four quick taps
]


@dataclass
class DeviceState:
    """
    Lightweight state for a single connected pod.

    Attributes:
        phase:     Current scoring phase -- one of:
                   "baseline" (still collecting resting data),
                   "active"   (player shaking hard enough to grow),
                   "idle"     (present but below growth threshold),
                   "wilt"     (too little movement, score may decrease).
        last_seen: Monotonic timestamp of the last window received from this
                   device.  Can be used for timeout/disconnect detection.
    """
    phase: str = "baseline"   # baseline | active | idle | wilt
    last_seen: float = field(default_factory=time.monotonic)


class PersonGrowthTracker:
    """
    Tracks one device's baseline and converts each window into score points.

    Growth scales with effort: harder shaking produces a higher window_sum,
    which yields a larger effort ratio, which multiplies growth_per_window.

    Lifecycle:
        1. Created when a new device name appears in process_window().
        2. First ``baseline_n_windows`` calls collect resting data (returns 0).
        3. Subsequent calls compare against expected effort and return a
           positive, negative, or zero score delta.

    Attributes:
        state: DeviceState with the current phase and last-seen timestamp.
    """

    def __init__(self, config: FlowerConfig) -> None:
        """
        Args:
            config: FlowerConfig with growth thresholds and point values.
        """
        self._config = config
        # BaselineCalculator accumulates the first N window sums to compute
        # a resting baseline (mean).  expected_effort() then returns the value
        # a pod should produce when the player is "normally" active.
        self._baseline = BaselineCalculator(config.baseline_n_windows)
        self.state = DeviceState()

    @property
    def is_ready(self) -> bool:
        """True once enough windows have been collected to establish a baseline."""
        return self._baseline.is_ready()

    def process_window(self, window_sum: float) -> float:
        """
        Process one window sum and return the score delta.

        Algorithm:
            1. If baseline is not yet ready, add the window to the baseline
               calculator and return 0 (no scoring during calibration).
            2. Compute expected effort from the baseline.
            3. Compare window_sum against expected effort +/- margins:
               - Above growth_margin  -> ACTIVE -> positive delta (scaled by ratio)
               - Below wilt_margin    -> WILT   -> negative delta
               - In between           -> IDLE   -> small positive delta

        Args:
            window_sum: The aggregated acceleration magnitude sum from the pod
                        for one time window.

        Returns:
            Score delta (positive = growth, negative = wilt, 0 = baseline phase).
        """
        self.state.last_seen = time.monotonic()

        # Phase 1: still collecting baseline samples
        if not self._baseline.is_ready():
            self._baseline.add(window_sum)
            remaining = self._config.baseline_n_windows - self._baseline.samples_collected
            if remaining > 0:
                print(f"    [baseline] {remaining} window(s) remaining")
            else:
                print(f"    [baseline] ready — mean={self._baseline.baseline():.2f}")
            self.state.phase = "baseline"
            return 0.0

        # Phase 2: scoring -- compare against expected effort
        exp = expected_effort(self._baseline)
        if exp is None or exp == 0:
            # Cannot determine expected effort (degenerate baseline).
            self.state.phase = "idle"
            return 0.0

        # ACTIVE: player is shaking harder than growth threshold
        if window_sum > exp * (1.0 + self._config.growth_margin):
            self.state.phase = "active"
            # Score scales with effort ratio -- no upper cap.
            # Example: if window_sum is 2x expected, delta = growth_per_window * 2.
            return self._config.growth_per_window * (window_sum / exp)

        # WILT: player is too still (below wilt threshold)
        if window_sum < exp * (1.0 - self._config.wilt_margin):
            self.state.phase = "wilt"
            return -self._config.wilt_per_window

        # IDLE: in between -- slow passive growth
        self.state.phase = "idle"
        return self._config.idle_growth_per_window


class FlowerController:
    """
    Aggregates per-device score into a shared garden state (cooperative mode).

    Phase flow:
        waiting -> playing (start_session) -> won (timer expires)
                                           -> waiting (reset)

    The game ends when the countdown timer expires; there is no fixed score
    goal.  The final score determines how many flowers the team grew.

    Vibration feedback is queued as pattern IDs in a per-device dict and
    consumed by PebbleClient via pop_vibration_commands().
    """

    def __init__(self, config: FlowerConfig) -> None:
        """
        Args:
            config: FlowerConfig with all game tuning parameters.
        """
        self._config     = config
        self._trackers:  dict[str, PersonGrowthTracker] = {}  # device_name -> tracker
        self._score:     float = 0.0     # cumulative team score (grows with each window)
        self.phase:      str   = "waiting"  # current game phase
        self._duration:  float = 0.0     # total game duration in seconds
        self._start_time: float = 0.0    # monotonic timestamp when game started
        self._milestones_hit: set[float] = set()  # time thresholds already triggered
        self._pending_vibrations: dict[str, list[int]] = {}  # device -> [pattern_id, ...]
        self._flower_milestone: int = 0   # how many 50-flower marks have been passed
        self._last10_sent:      bool = False  # True after the last-10s warning fires

    # ── Time ──────────────────────────────────────────────────

    @property
    def time_remaining(self) -> float:
        """Seconds remaining in the current game, or 0 if not playing."""
        if self.phase != "playing":
            return 0.0
        return max(0.0, self._duration - (time.monotonic() - self._start_time))

    # ── Score -> flower progress ──────────────────────────────

    @property
    def progress(self) -> float:
        """
        Progress toward a goal (0.0 to 1.0).

        Currently always returns 0.0 because the game uses unlimited flowers
        instead of a fixed target.  Kept for API compatibility with the dashboard.
        """
        return 0.0   # progress bar removed -- flowers are unlimited

    # ── Controller interface ──────────────────────────────────

    def process_window(self, device_name: str, window_sum: float) -> None:
        """
        Process one IMU window sum from a named device.

        This is the main entry point called by BLE clients (via the WS server
        proxy) every time a pod sends a notification.

        Algorithm:
            1. Ignore if not in "playing" phase.
            2. If the timer has expired, transition to "won" and send VIBR_WIN.
            3. Create a PersonGrowthTracker for new devices (triggers baseline).
            4. Delegate to the tracker to get a score delta.
            5. Update the cumulative score (clamped at 0).
            6. Check for vibration milestones.

        Args:
            device_name: BLE advertising name of the pod (e.g. "Pebble_01").
            window_sum:  Aggregated acceleration sum for one time window.
        """
        if self.phase != "playing":
            return

        # Check if the timer has expired
        if self.time_remaining <= 0:
            self.phase = "won"
            print("[GARDEN] Time's up!")
            self._queue_vibration_all(VIBR_WIN)
            return

        # Register new devices on the fly (late joiners)
        if device_name not in self._trackers:
            print(f"[{device_name}] new device — collecting baseline "
                  f"({self._config.baseline_n_windows} windows)")
            self._trackers[device_name] = PersonGrowthTracker(self._config)

        # Get score delta from the per-device tracker
        delta = self._trackers[device_name].process_window(window_sum)

        # Update cumulative score (floor at 0 -- no negative score)
        if delta != 0:
            self._score = max(0.0, self._score + delta)
            arrow = "↑" if delta > 0 else "↓"
            print(f"[{device_name}] score={window_sum:.2f}  "
                  f"{arrow}{abs(delta):.1f} → {self._score:.1f}  "
                  f"⏱ {self.time_remaining:.0f}s")

        # Check for time/score/last-10s milestones
        self._check_milestones()

    def start_session(self, duration_seconds: int) -> None:
        """
        Start a new timed game session, resetting all state.

        Args:
            duration_seconds: How long the game lasts (from game_durations or dashboard).
        """
        self._trackers.clear()
        self._score      = 0.0
        self.phase       = "playing"
        self._duration   = float(duration_seconds)
        self._start_time = time.monotonic()
        self._milestones_hit.clear()
        self._pending_vibrations.clear()
        self._flower_milestone = 0
        self._last10_sent      = False
        print(f"[GARDEN] Session started — {duration_seconds}s timer.")

    def reset(self) -> None:
        """Reset the controller to the initial 'waiting' state (no active game)."""
        self._trackers.clear()
        self._score      = 0.0
        self.phase       = "waiting"
        self._duration   = 0.0
        self._start_time = 0.0
        self._milestones_hit.clear()
        self._pending_vibrations.clear()
        self._flower_milestone = 0
        self._last10_sent      = False
        print("[GARDEN] Session reset.")

    def pop_vibration_commands(self, device_name: str) -> list[int]:
        """
        Drain and return all pending vibration pattern IDs for a given device.

        Called by PebbleClient every ~1 second to check if any haptic feedback
        needs to be sent to the pod.

        Args:
            device_name: BLE name of the pod.

        Returns:
            List of integer pattern IDs (may be empty).
        """
        return self._pending_vibrations.pop(device_name, [])

    def get_state(self) -> dict:
        """
        Build a snapshot of the entire game state for the dashboard.

        Returns a dict that is JSON-serialized and sent over WebSocket.
        Includes: mode, phase, timer, score, per-device info, and plant list.
        """
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
        """
        Check and fire vibration milestones (time-based, score-based, last-10s).

        Called after every process_window().  Each milestone fires at most once
        per session.

        Time milestones:  Defined in _TIME_MILESTONES (50 %, 75 % of duration).
        Score milestones: Every 50 flowers grown (VIBR_FLOWER_50).
        Last-10s:         When <=10 seconds remain (VIBR_LAST_10).
        """
        if self._duration == 0:
            return
        # Time-based milestones: compute what fraction of game time has elapsed
        elapsed_ratio = (time.monotonic() - self._start_time) / self._duration
        for threshold, pattern_id in _TIME_MILESTONES:
            if threshold not in self._milestones_hit and elapsed_ratio >= threshold:
                self._milestones_hit.add(threshold)
                self._queue_vibration_all(pattern_id)
                print(f"[GARDEN] {int(threshold*100)}% time elapsed — pattern {pattern_id}")

        # Score-based: every 50 flowers (score points), send a celebratory vibration
        current = int(self._score / 50)
        if current > self._flower_milestone:
            self._flower_milestone = current
            self._queue_vibration_all(VIBR_FLOWER_50)
            print(f"[GARDEN] {current * 50} flowers — happy vibration!")

        # Last 10 seconds warning (fires once when remaining <= 10s)
        if not self._last10_sent and 0 < self.time_remaining <= 10.0:
            self._last10_sent = True
            self._queue_vibration_all(VIBR_LAST_10)
            print("[GARDEN] Last 10 s — anxious vibration!")

    def _queue_vibration_all(self, pattern_id: int) -> None:
        """
        Queue a vibration pattern for every currently-tracked device.

        The patterns accumulate in _pending_vibrations and are drained by
        pop_vibration_commands() when the BLE client polls.

        Args:
            pattern_id: One of the VIBR_* constants from ble.constants.
        """
        for name in self._trackers:
            self._pending_vibrations.setdefault(name, []).append(pattern_id)

    def _compute_plants(self) -> list[dict]:
        """
        Convert the cumulative score into a list of plant dicts for the dashboard.

        Each fully-grown plant has growth=1.0.  If there is a fractional remainder,
        one additional partially-grown plant is appended.

        Returns:
            List of {"id": int, "growth": float} dicts.
            Example for score=2.5, sprout_points_per_plant=1:
              [{"id":0,"growth":1.0}, {"id":1,"growth":1.0}, {"id":2,"growth":0.5}]
        """
        pts      = self._config.sprout_points_per_plant
        num_full = int(self._score / pts)
        partial  = (self._score % pts) / pts
        plants   = [{"id": i, "growth": 1.0} for i in range(num_full)]
        if partial > 0.001:
            plants.append({"id": num_full, "growth": round(partial, 4)})
        return plants
