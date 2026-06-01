from dataclasses import dataclass


@dataclass
class FlowerConfig:
    # --- Baseline collection ---
    baseline_n_windows: int = 2

    # --- Growth thresholds ---
    growth_margin: float = 0.05
    wilt_margin:   float = 0.20

    # --- Growth point values ---
    # growth_per_window is the coefficient at 1× effort; harder shaking scales it up.
    growth_per_window:      float = 3.0
    idle_growth_per_window: float = 2.0
    wilt_per_window:        float = 0.0

    # --- Timed game ---
    # Duration options shown in the UI (seconds). Adjust to taste.
    game_durations: tuple[int, ...] = (60, 120, 180, 300)   # 1 / 2 / 3 / 5 min
    default_duration: int = 120                    # pre-selected option

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
    broadcast_interval_s: float = 0.33

    # --- Late-joiner team assignment (competitive mode only) ---
    # Devices that miss the shake-to-join phase and connect mid-game are
    # assigned to the smaller team. "random" = balanced fill.
    team_pairing: str = "random"

    # --- Team selection shake threshold ---
    # At rest sum ≈ 300.  330 ≈ 10 % above resting — slow deliberate movement.
    # Raise if accidental joins occur; lower if users struggle to register.
    team_select_shake_threshold: float = 330.0
