from __future__ import annotations

import math
from dataclasses import dataclass

from ble.imu import ImuWindow


@dataclass(frozen=True)
class SimilarityResult:
    score: float
    movement_score: float
    rotation_score: float
    angle_score: float


def _cosine(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    amag = math.sqrt(sum(v * v for v in a))
    bmag = math.sqrt(sum(v * v for v in b))
    if amag < 0.02 and bmag < 0.02:
        return 1.0
    if amag < 0.02 or bmag < 0.02:
        return 0.0
    value = sum(x * y for x, y in zip(a, b)) / (amag * bmag)
    return max(-1.0, min(1.0, value))


def _direction_score(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return (_cosine(a, b) + 1.0) / 2.0


def _magnitude_score(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    """1.0 when the two vectors have the same magnitude (speed/intensity), 0.0 when very different."""
    amag = math.sqrt(sum(v * v for v in a))
    bmag = math.sqrt(sum(v * v for v in b))
    if amag < 0.02 and bmag < 0.02:
        return 1.0
    return min(amag, bmag) / max(amag, bmag)


def _angle_delta(a: float, b: float) -> float:
    delta = abs(a - b) % 360.0
    return min(delta, 360.0 - delta)


def compute_similarity(
    instructor: ImuWindow,
    student: ImuWindow,
    *,
    movement_weight: float = 0.50,
    rotation_weight: float = 0.20,
    angle_weight: float = 0.30,
    speed_sensitivity: float = 0.30,
    angle_tolerance_degrees: float = 90.0,
) -> SimilarityResult:
    instructor_accel = (instructor.ax, instructor.ay, instructor.az)
    student_accel = (student.ax, student.ay, student.az)

    direction_score = _direction_score(instructor_accel, student_accel)
    speed_score = _magnitude_score(instructor_accel, student_accel)
    movement_score = (
        (1.0 - speed_sensitivity) * direction_score +
        speed_sensitivity * speed_score
    )

    rotation_score = _direction_score(
        (instructor.gx, instructor.gy, instructor.gz),
        (student.gx, student.gy, student.gz),
    )

    roll_delta = _angle_delta(instructor.roll, student.roll)
    pitch_delta = _angle_delta(instructor.pitch, student.pitch)
    angle_error = math.sqrt((roll_delta * roll_delta + pitch_delta * pitch_delta) / 2.0)
    angle_score = max(0.0, 1.0 - angle_error / angle_tolerance_degrees)

    score = (
        movement_weight * movement_score +
        rotation_weight * rotation_score +
        angle_weight * angle_score
    )
    return SimilarityResult(
        score=max(0.0, min(1.0, score)),
        movement_score=movement_score,
        rotation_score=rotation_score,
        angle_score=angle_score,
    )
