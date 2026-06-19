"""
Similarity scoring engine — compares instructor vs student IMU movement.

This is the core algorithm that makes the flower game work: it takes one
instructor IMU window and one student IMU window and produces a 0-to-1
similarity score based on how well the student's movement matches the
instructor's movement.

Orientation-independent design:
    Pods can be held at any angle. The algorithm decomposes each pod's
    movement into vertical (along gravity) and horizontal (perpendicular)
    components using each pod's gravity direction (reconstructed from
    roll/pitch). This way, "up" means the same thing for both pods
    regardless of how they're tilted.

    - Vertical direction (up vs down) is compared for both direction
      and magnitude — this is the only axis we can reliably compare.
    - Horizontal magnitude is compared (intensity match), but direction
      is NOT compared because we don't know which way the pod is facing
      horizontally (no magnetometer / no yaw information).

Algorithm overview:
    1. Use ax, ay, az directly as movement (gravity already removed by
       firmware). Use gravity direction (from roll/pitch EMA) to define
       which way is "down" for each pod.
    2. Project movement onto gravity axis → vertical component (signed).
       Remainder → horizontal component (magnitude only).
    3. Check minimum total movement. If either pod is too still → score 0.
    4. Compare vertical direction (same or opposite).
    5. Compute magnitude ratios for vertical and horizontal separately,
       weighted by how much of the movement is vertical vs horizontal.
    6. If vertical matches: score = 0.9 + 0.1 * magnitude (90-100%).
       If vertical is opposite: score capped below 50%, penalty scaled
       by how vertical the movement is.

Phase compensation (best_similarity):
    Pods start their 250ms windows independently, so best_similarity()
    compares against the last N instructor windows and picks the best.

Key functions:
    compute_similarity()           : Core scoring with orientation alignment
    best_similarity()              : Phase-compensated wrapper
    gravity_from_roll_pitch()      : Reconstruct gravity direction from angles
    update_gravity_estimate()      : EMA tracker (used for gravity direction)
    merge_windows()                : Average N ImuWindows into one
    fallback_score()               : Activity-only scoring when similarity off

Dependencies:
    - ble.imu : ImuWindow dataclass.
    - math    : sqrt, sin, cos, radians for vector math.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from ble.imu import ImuWindow


@dataclass(frozen=True)
class SimilarityResult:
    """Result of comparing one instructor window to one student window.
    score: 0.0 (no match) to 1.0 (perfect match).
    direction_score: 1.0 if vertical matches, lower if opposite (weighted).
    magnitude_score: weighted average of vertical and horizontal magnitude ratios."""
    score: float
    direction_score: float
    magnitude_score: float


# ── Vector math helpers ──────────────────────────────────────────

def _vec_mag(v: tuple[float, float, float]) -> float:
    return math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)


def _vec_normalize(v: tuple[float, float, float]) -> tuple[float, float, float]:
    m = _vec_mag(v)
    if m < 1e-9:
        return (0.0, 0.0, 1.0)
    return (v[0] / m, v[1] / m, v[2] / m)


def _vec_dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def gravity_from_roll_pitch(roll_deg: float, pitch_deg: float) -> tuple[float, float, float]:
    """Reconstruct a unit gravity direction vector from roll and pitch angles.

    Uses the standard IMU convention where:
        roll  = atan2(ay, az)              — tilt left/right
        pitch = atan2(-ax, sqrt(ay²+az²))  — tilt forward/backward

    Returns a unit vector pointing in the direction of gravity in the
    pod's local coordinate frame. This tells us which way "down" is
    for this pod, regardless of how it's held.
    """
    r = math.radians(roll_deg)
    p = math.radians(pitch_deg)
    gx = -math.sin(p)
    gy = math.sin(r) * math.cos(p)
    gz = math.cos(r) * math.cos(p)
    return (gx, gy, gz)


def merge_windows(windows: list[ImuWindow]) -> ImuWindow:
    """Average N consecutive ImuWindows into one, extending the effective
    sampling interval without a firmware change."""
    n = len(windows)
    if n == 1:
        return windows[0]
    activities = [w.activity for w in windows if w.activity is not None]
    return ImuWindow(
        samples=sum(w.samples for w in windows),
        ax=sum(w.ax for w in windows) / n,
        ay=sum(w.ay for w in windows) / n,
        az=sum(w.az for w in windows) / n,
        gx=sum(w.gx for w in windows) / n,
        gy=sum(w.gy for w in windows) / n,
        gz=sum(w.gz for w in windows) / n,
        roll=sum(w.roll for w in windows) / n,
        pitch=sum(w.pitch for w in windows) / n,
        activity=sum(activities) / len(activities) if activities else None,
    )


def fallback_score(student: ImuWindow, activity_scale: float) -> SimilarityResult:
    """Activity-only score used when similarity_enabled is False.

    Ignores the instructor entirely and just rewards the student's own
    movement, in case the instructor-matching similarity score is too
    noisy/unreliable to use on the day.
    """
    score = max(0.0, min(1.0, student.shake_score / activity_scale))
    return SimilarityResult(score=score, direction_score=0.0, magnitude_score=0.0)


def update_gravity_estimate(
    gravity: tuple[float, float, float],
    accel: tuple[float, float, float],
    alpha: float,
    initialized: bool = True,
) -> tuple[float, float, float]:
    """Slowly track the gravity component of a pod's acceleration via an EMA.

    A fixed (0, 0, 1g) assumption only works if the pod's z-axis happens to
    be vertical. Pods can be worn/held at any angle, so instead each pod's
    own gravity vector is estimated as a slow-moving average of its raw
    acceleration - fast, movement-induced changes average out, leaving the
    pod's resting orientation regardless of which axis that is on.

    `initialized=False` (i.e. this is the first window from this pod) snaps
    the estimate straight to the current reading instead of slowly EMA-ing
    from the (0, 0, 1) default. With alpha=0.02 that EMA takes many seconds
    to converge - until then, `accel - gravity` is dominated by the gap
    between the pod's *actual* resting orientation and (0, 0, 1), not by
    real movement, which makes the vertical/horizontal split meaningless
    (e.g. reporting "movement" - and a high similarity score - while both
    pods are sitting still).
    """
    if not initialized:
        return accel
    return tuple((1.0 - alpha) * g + alpha * a for g, a in zip(gravity, accel))


def compute_similarity(
    instructor: ImuWindow,
    student: ImuWindow,
    *,
    min_movement_accel: float = 0.0,
    instructor_gravity: tuple[float, float, float] = (0.0, 0.0, 1.0),
    student_gravity: tuple[float, float, float] = (0.0, 0.0, 1.0),
    direction_penalty_exponent: float = 4.0,
) -> SimilarityResult:
    """Compare instructor vs student movement using orientation-independent
    vertical/horizontal decomposition.

    ax, ay, az are already gravity-removed by the firmware, so they represent
    pure movement. instructor_gravity and student_gravity are gravity direction
    vectors (from roll/pitch EMA) telling us which way "down" is for each pod.

    The movement is decomposed into:
      - Vertical (along gravity): signed scalar — can compare direction.
      - Horizontal (perpendicular to gravity): magnitude only — can't compare
        direction without a magnetometer, so only intensity is compared.
    """
    # Movement vectors (already gravity-removed by firmware)
    i_move = (instructor.ax, instructor.ay, instructor.az)
    s_move = (student.ax, student.ay, student.az)

    # Total movement — if either pod is too still, can't compare
    i_mag = _vec_mag(i_move)
    s_mag = _vec_mag(s_move)
    if i_mag < min_movement_accel or s_mag < min_movement_accel:
        return SimilarityResult(score=0.0, direction_score=0.0, magnitude_score=0.0)

    # "Down" direction for each pod (from roll/pitch-derived gravity EMA)
    i_down = _vec_normalize(instructor_gravity)
    s_down = _vec_normalize(student_gravity)

    # Vertical component: projection of movement onto gravity direction.
    # Positive = moving downward (with gravity), negative = moving upward.
    i_vert = _vec_dot(i_move, i_down)
    s_vert = _vec_dot(s_move, s_down)

    # Horizontal component: everything perpendicular to gravity.
    # Pythagorean: horiz² = total² - vert²
    i_horiz = math.sqrt(max(0.0, i_mag ** 2 - i_vert ** 2))
    s_horiz = math.sqrt(max(0.0, s_mag ** 2 - s_vert ** 2))

    # ── Direction check (vertical only) ──────────────────────────
    # Vertical is the ONLY axis where we can compare direction, because
    # gravity alignment gives both pods the same "up/down" reference.
    vert_same = (i_vert * s_vert >= 0)
    vert_significant = (abs(i_vert) > min_movement_accel * 0.5 and
                        abs(s_vert) > min_movement_accel * 0.5)

    # ── Magnitude ratios ─────────────────────────────────────────
    exp = 1.0 / direction_penalty_exponent

    # Vertical ratio (handle near-zero cases)
    if abs(i_vert) < 1e-9 and abs(s_vert) < 1e-9:
        vert_ratio = 1.0
    elif abs(i_vert) < 1e-9 or abs(s_vert) < 1e-9:
        vert_ratio = 0.0
    else:
        vert_ratio = (min(abs(i_vert), abs(s_vert)) / max(abs(i_vert), abs(s_vert))) ** exp

    # Horizontal ratio
    if i_horiz < 1e-9 and s_horiz < 1e-9:
        horiz_ratio = 1.0
    elif i_horiz < 1e-9 or s_horiz < 1e-9:
        horiz_ratio = 0.0
    else:
        horiz_ratio = (min(i_horiz, s_horiz) / max(i_horiz, s_horiz)) ** exp

    # Weight by how much of the movement is vertical vs horizontal.
    # If mostly vertical → vertical comparison dominates the score.
    # If mostly horizontal → horizontal magnitude dominates.
    total_component = abs(i_vert) + abs(s_vert) + i_horiz + s_horiz + 1e-9
    vert_weight = (abs(i_vert) + abs(s_vert)) / total_component

    magnitude_score = vert_weight * vert_ratio + (1.0 - vert_weight) * horiz_ratio

    # ── Final score ──────────────────────────────────────────────
    if vert_same or not vert_significant:
        # Vertical matches, or not enough vertical movement to judge
        direction_score = 1.0
        score = 0.9 + 0.1 * magnitude_score
    else:
        # Vertical directions are clearly opposite — harsh penalty.
        # Capped at 25% (not 50%). The penalty uses vert_weight² so
        # even moderate vertical opposition is punished heavily:
        #   purely vertical opposite → 0%
        #   50% vertical opposite   → ~6%
        #   mostly horizontal       → ~16-20%
        direction_score = (1.0 - vert_weight) ** 2
        score = 0.25 * direction_score * magnitude_score

    return SimilarityResult(
        score=max(0.0, min(1.0, score)),
        direction_score=round(direction_score, 3),
        magnitude_score=round(magnitude_score, 3),
    )


def best_similarity(
    instructor_history: Iterable[ImuWindow],
    student: ImuWindow,
    *,
    instructor_gravity: tuple[float, float, float],
    **kwargs,
) -> SimilarityResult:
    """compute_similarity against each recent instructor window, keeping the
    highest-scoring match.

    Each pod's 0.25 s sampling window starts independently when it connects,
    so the instructor's and student's windows aren't phase-aligned - the
    "same" movement can land mostly in window N for one pod and mostly in
    window N+1 for the other. Comparing the student's window against a short
    history of recent instructor windows (instead of only the latest one)
    finds whichever pairing actually overlaps the movement, without needing
    the pods to be clock-synced.
    """
    best: SimilarityResult | None = None
    for instructor in instructor_history:
        result = compute_similarity(instructor, student, instructor_gravity=instructor_gravity, **kwargs)
        if best is None or result.score > best.score:
            best = result
    if best is None:
        return SimilarityResult(score=0.0, direction_score=0.0, magnitude_score=0.0)
    return best
