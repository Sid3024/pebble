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
    - dataclasses (stdlib): Provides the @dataclass decorator.
"""

from dataclasses import dataclass


@dataclass
class FlowerConfig:
    # --- Baseline collection ---
    baseline_n_windows: int = 2

    # --- Growth thresholds ---
    growth_margin: float = 0.05
    wilt_margin:   float = 0.20

    # --- Growth point values ---
    # growth_per_window is the max score for a 100% similarity window.
    # Since sprout_points_per_plant = 1.0, this is also the max number of
    # flowers grown per window at 100% similarity. Actual growth is
    # growth_per_window * (similarity_score ** similarity_growth_exponent),
    # so lower matches earn disproportionately less than this max.
    growth_per_window:      float = 3.0
    idle_growth_per_window: float = 0.1
    wilt_per_window:        float = 0.0

    # --- Timed game ---
    # Duration options shown in the UI (seconds). Adjust to taste.
    game_durations: tuple[int, ...] = (30, 60, 120, 300)   # 30 s / 1 / 2 / 5 min
    default_duration: int = 60                     # pre-selected option

    # --- Sprout rate ---
    # How many score points are needed to grow ONE flower.
    # Flowers are unlimited — raise this to slow down how fast they appear.
    #   1  → 1 point  = 1 flower
    #   5  → 5 points = 1 flower
    #   10 → 10 points = 1 flower
    sprout_points_per_plant: float = 1.0

    # --- BLE scanning ---
    ble_scan_timeout: float = 10.0

    # --- WebSocket server ---
    ws_host: str = "localhost"
    ws_port: int = 8765
    broadcast_interval_s: float = 0.15

    # --- Late-joiner team assignment (competitive mode only) ---
    # Devices that miss the shake-to-join phase and connect mid-game are
    # assigned to the smaller team. "random" = balanced fill.
    team_pairing: str = "random"

    # --- Instructor / team selection shake thresholds ---
    # Uses IMU movement magnitude + a small gyro component. Raise if accidental
    # joins occur; lower if users struggle to register.
    instructor_select_shake_threshold: float = 3.0
    team_select_imu_threshold: float = 3.0

    # Legacy float-window threshold, kept for simulator/backward compatibility.
    # At rest sum ≈ 300.  330 ≈ 10 % above resting — slow deliberate movement.
    # Raise if accidental joins occur; lower if users struggle to register.
    team_select_shake_threshold: float = 400.0

    # --- Button Points (competitive mode only) ---
    # When True, keyboard keys add bonus points directly to a team's score:
    #   1/2/3/4 → Team 1 +1/+2/+3/+4 pts
    #   q/w/e/r → Team 2 +1/+2/+3/+4 pts
    button_points: bool = True

    # --- UI display ---
    # Controls whether the match % is shown alongside the score in the game UI.
    # "show" → "Score: X pts · Match: Y%" (default)
    # "hide" → "Score: X pts" only
    show_match_percent: str = "hide"

    # --- Similarity scoring (instructor vs. student IMU window) ---
    # If False, the instructor-matching similarity score is skipped entirely
    # and every student instead grows based on their own movement effort
    # (see similarity_fallback_activity_scale below). Flip this off on the
    # day if the similarity score is too noisy/unreliable - no firmware
    # reupload needed, just edit this file and restart.
    similarity_enabled: bool = True

    # Used only when similarity_enabled is False. Each student's score is
    # their own shake_score (movement magnitude + a bit of gyro) divided by
    # this value, clamped to [0, 1]. Lower = easier to reach 100%.
    similarity_fallback_activity_scale: float = 0.5

    # Movement is compared axis-by-axis (ax, ay, az), each with gravity
    # removed via the pod's own (EMA-tracked) gravity vector:
    #   - If ANY axis is below similarity_min_movement_accel for either the
    #     instructor or the student, the score is 0 (not enough real motion
    #     to judge).
    #   - If ALL THREE axes move in the SAME direction (sign) for both pods,
    #     the score is 0.9-1.0 - magnitude_ratio ** (1/exponent) only affects
    #     how close to 1.0 it gets (see exponent below).
    #   - If ANY axis moves in OPPOSITE directions between the two pods, the
    #     score is capped below 0.5, and drops further the more axes
    #     disagree.
    similarity_direction_penalty_exponent: float = 8.0

    # If the gravity-removed acceleration on ANY axis (x, y, or z) is below
    # this threshold (g) for either the instructor or the student, the
    # similarity score is forced to 0 - that axis isn't showing enough real
    # movement to compare.
    similarity_min_movement_accel: float = 0.005

    # Smoothing factor (0-1) for each pod's gravity-vector estimate, tracked
    # as an exponential moving average of its raw acceleration so gravity is
    # removed correctly regardless of how the pod is worn/oriented. Lower =
    # slower to adapt but less affected by sustained movement.
    similarity_gravity_ema_alpha: float = 0.02

    # How many 250 ms firmware windows to merge before computing similarity.
    # Effective interval = 250 ms × this value.
    #   1 → 250 ms  (current default — fastest, most responsive)
    #   2 → 500 ms  (good for slow movements, less cancellation risk)
    #   4 → 1 s     (very deliberate movements only)
    # Cannot go below 1 without reflashing firmware (change SAMPLES_PER_WINDOW
    # in firmware/src/window/window.h).
    similarity_accumulate_windows: int = 2

    # Shapes how match score -> flower growth. growth = growth_per_window *
    # (similarity_score ** this). >1 rewards high matches disproportionately
    # more than low ones:
    #   2.0 -> a 0.5 match gives 25% of growth_per_window, a 0.9 match gives
    #          81%, a 1.0 match gives 100% (the full growth_per_window).
    # Higher = steeper - medium matches earn much less, near-perfect matches
    # stay close to the max.
    similarity_growth_exponent: float = 2.0
