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
    growth_per_window:      float = 10.0
    idle_growth_per_window: float = 2.0
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
    instructor_select_shake_threshold: float = 0.10
    team_select_imu_threshold: float = 0.10

    # Legacy float-window threshold, kept for simulator/backward compatibility.
    # At rest sum ≈ 300.  330 ≈ 10 % above resting — slow deliberate movement.
    # Raise if accidental joins occur; lower if users struggle to register.
    team_select_shake_threshold: float = 400.0

    # --- Similarity scoring (instructor vs. student IMU window) ---
    # Final score = movement_weight*movement + rotation_weight*rotation + angle_weight*angle.
    # The three weights should add up to 1.0.
    similarity_movement_weight: float = 0.50
    similarity_rotation_weight: float = 0.20
    similarity_angle_weight:    float = 0.30

    # Within the movement component, blend "same direction" vs. "same speed":
    #   0.0 -> direction only (speed/intensity ignored)
    #   1.0 -> speed/intensity only (direction ignored)
    similarity_speed_sensitivity: float = 0.0

    # Roll/pitch angle difference (degrees) at which angle_score reaches 0.
    similarity_angle_tolerance_degrees: float = 90.0
