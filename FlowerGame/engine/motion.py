from __future__ import annotations

from ble.imu import ImuWindow


def selection_motion_score(window: ImuWindow) -> float:
    """Light-motion detector for instructor/team selection, not similarity."""
    return window.shake_score
