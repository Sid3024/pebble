from dataclasses import dataclass


@dataclass
class FlowerConfig:
    # --- Baseline collection (mirrors hub/config/config.py) ---
    # Windows collected per device before their personal baseline is set.
    # During this phase the device is "warming up" and contributes no growth.
    baseline_n_windows: int = 2

    # --- Growth thresholds ---
    # Fractional deviation ABOVE baseline that counts as active effort.
    # Lowered to 0.05 so even gentle movement (5% above resting) earns full credit.
    growth_margin: float = 0.05

    # Fractional deviation BELOW baseline before the wilt penalty applies.
    wilt_margin: float = 0.20

    # --- Growth point values ---
    # Points awarded when a device window is above growth_margin.
    growth_per_window: float = 3.0

    # Points awarded when a device window is within both margins (resting at baseline).
    # Raised to 2.0 so the garden grows even when participants are just holding the pod.
    idle_growth_per_window: float = 2.0

    # Points subtracted when a device window is below wilt_margin (min total = 0).
    # 0.0 = no penalty — resting never hurts progress.
    wilt_per_window: float = 0.0

    # --- Session goal ---
    # Total accumulated growth points (across all devices) needed to reach 100%.
    # Rule of thumb (1 window = 3 s, one pod idle ≈ 2.0 pts/window = 40 pts/min):
    #   1 pod  → 40 pts ≈ 1 min   |  2 pods → 40 pts ≈ 30 sec
    #   4 pods → 40 pts ≈ 15 sec  (more participants = faster win by design)
    total_growth_needed: float = 60.0

    # --- Garden visuals ---
    # Number of plants rendered on screen (cosmetic — not tied to device count).
    # Plants bloom left-to-right as group progress increases.
    num_plants: int = 20

    # --- BLE scanning ---
    # How long (seconds) to scan for Pebble pods on startup.
    ble_scan_timeout: float = 10.0

    # --- WebSocket server ---
    # Host and port the Python backend listens on.
    # The browser dashboard connects to ws://ws_host:ws_port
    ws_host: str = "localhost"
    ws_port: int = 8765

    # --- Broadcast rate ---
    # How often (seconds) the backend pushes garden state to the browser.
    broadcast_interval_s: float = 0.33

    # --- Team pairing strategy (competitive mode only) ---
    # "random": each new device is assigned to a random team.
    # Future options: "alternating", "manual"
    team_pairing: str = "random"
