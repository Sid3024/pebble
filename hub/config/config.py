from dataclasses import dataclass


@dataclass
class Config:
    # --- Baseline ---
    # Number of initial windows collected per person to establish their baseline.
    baseline_n_windows: int = 2

    # --- Volume control ---
    # Fractional deviation above expected before volume increases (0.20 = 20%).
    increase_margin: float = 0.20
    # Fractional deviation below expected before volume decreases.
    decrease_margin: float = 0.05

    # Volume delta (percentage points) applied on each qualifying window.
    increase_alpha: int = 10
    decrease_alpha: int = 10

    # --- Volume limits ---
    initial_volume: int = 10
    min_volume: int = 10
    max_volume: int = 90
