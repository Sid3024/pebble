"""
Motion detection for instructor and team selection phases.

This is a very thin module: it provides a single function that converts an
ImuWindow into a "motion score" used to detect intentional shaking during
the instructor_select and team_select phases.

Why it's separate from similarity.py:
    Selection uses a simple motion magnitude threshold (shake_score) to detect
    whether someone is deliberately shaking their pod. The similarity engine
    does axis-by-axis comparison with gravity removal — a completely different
    algorithm meant for the playing phase. Keeping them separate avoids coupling
    the selection logic to the similarity logic.

How it fits into Pebble:
    Both FlowerController and CompetitiveFlowerController call
    selection_motion_score() during instructor_select/team_select phases.
    If the returned score exceeds the config threshold, the pod is
    registered as instructor or assigned to a team.
"""

from __future__ import annotations

from ble.imu import ImuWindow


def selection_motion_score(window: ImuWindow) -> float:
    """Return a scalar motion score for a single IMU window.

    Uses ImuWindow.shake_score which combines accelerometer magnitude
    with a small gyroscope contribution. Higher = more vigorous shaking.
    Compared against instructor_select_shake_threshold or
    team_select_imu_threshold in the calling controller.
    """
    return window.shake_score
