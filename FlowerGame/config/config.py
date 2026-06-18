"""
Central configuration for the FlowerGame backend.

This file defines FlowerConfig, a Python dataclass that holds every tunable
parameter for the flower-growing game.  All default values are set here and
shared by every game mode (single-team and competitive).

How it fits into Pebble:
    FlowerConfig is instantiated once in main.py and passed to the WebSocket
    server, which in turn passes it to whichever game controller (FlowerController
    or CompetitiveFlowerController) is created for the current session.  The
    dashboard also receives some of these values (e.g. game_durations) so it
    can render the UI accordingly.

Design notes:
    - This is a plain dataclass with default values -- no file I/O, no env vars.
      To change a setting, either edit the default here or subclass/override at
      construction time.
    - Do NOT change default values without understanding downstream effects;
      they are tuned for the physical Pebble pods and the real-time feel of the
      game.

Dependencies:
    - dataclasses (stdlib): Provides the @dataclass decorator for concise,
      immutable-ish configuration objects.
"""

from dataclasses import dataclass


@dataclass
class FlowerConfig:
    """
    All tunable parameters for the FlowerGame, grouped by subsystem.

    Each field has a sensible default.  Downstream code reads these values but
    never modifies them at runtime -- treat this as read-only after construction.
    """

    # ── Baseline collection ───────────────────────────────────────────────────
    # When a new pod joins mid-game, it first collects this many windows of
    # "resting" data to learn the player's baseline effort level.  Once the
    # baseline is ready, the pod transitions to active scoring.
    baseline_n_windows: int = 2

    # ── Growth thresholds ─────────────────────────────────────────────────────
    # growth_margin: The fraction ABOVE the expected effort that a window sum
    #   must exceed to count as "active" (growing).  0.05 = 5 % above expected.
    # wilt_margin:   The fraction BELOW expected effort that triggers "wilt"
    #   (score penalty).  0.20 = 20 % below expected.
    # The zone between them is "idle" -- the player is present but not pushing
    # hard enough to grow, yet not slack enough to wilt.
    growth_margin: float = 0.05
    wilt_margin:   float = 0.20

    # ── Growth point values ───────────────────────────────────────────────────
    # growth_per_window:      Base score points awarded per window when the
    #                         player is actively shaking.  Actual award is
    #                         scaled by the effort ratio (window_sum / expected),
    #                         so harder shaking earns more.
    # idle_growth_per_window: Points awarded when effort is between the growth
    #                         and wilt margins.  Keeps flowers slowly growing
    #                         even when the player is just holding the pod.
    # wilt_per_window:        Points SUBTRACTED per window when the player is
    #                         below the wilt margin.  Currently 0 (no penalty).
    growth_per_window:      float = 3.0
    idle_growth_per_window: float = 2.0
    wilt_per_window:        float = 0.0

    # ── Timed game ────────────────────────────────────────────────────────────
    # game_durations:   Tuple of selectable durations (in seconds) shown in the
    #                   dashboard start-game UI.
    # default_duration: Which duration is pre-selected when the dashboard loads.
    game_durations: tuple[int, ...] = (30, 60, 120, 300)   # 30 s / 1 / 2 / 5 min
    default_duration: int = 120                    # pre-selected option

    # ── Sprout rate ───────────────────────────────────────────────────────────
    # How many score points are needed to grow ONE flower.
    # Flowers are unlimited -- raise this to slow down how fast they appear.
    #   1  -> 1 point  = 1 flower  (fast)
    #   5  -> 5 points = 1 flower
    #   10 -> 10 points = 1 flower (slow)
    sprout_points_per_plant: float = 1.0

    # ── BLE scanning ──────────────────────────────────────────────────────────
    # How many seconds to scan for BLE devices at startup.
    # Increase if pods take a long time to advertise; decrease for faster startup.
    ble_scan_timeout: float = 10.0

    # ── WebSocket server ──────────────────────────────────────────────────────
    # ws_host:               Hostname to bind the WS server to.
    # ws_port:               Port number for the WS server.
    # broadcast_interval_s:  How often (seconds) the server broadcasts game state
    #                        to all connected dashboards.  0.33 = ~3 updates/sec.
    ws_host: str = "localhost"
    ws_port: int = 8765
    broadcast_interval_s: float = 0.33

    # ── Late-joiner team assignment (competitive mode only) ───────────────────
    # Devices that miss the shake-to-join phase and connect mid-game are
    # assigned to the smaller team.  "random" = balanced fill (pick the team
    # with fewer members; break ties randomly).
    team_pairing: str = "random"

    # ── Team selection shake threshold ────────────────────────────────────────
    # During the team_select phase in competitive mode, a pod must send a
    # window sum above this threshold to register as "shaking" and join a team.
    # At rest, a pod's sum is ~300.  330 is ~10 % above resting -- a slow
    # deliberate movement.  Raise if accidental joins occur; lower if users
    # struggle to register.
    team_select_shake_threshold: float = 330.0
