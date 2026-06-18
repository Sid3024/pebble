from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ble.imu import ImuWindow


@dataclass(frozen=True)
class SimilarityResult:
    score: float
    direction_score: float
    magnitude_score: float


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
    """Compare instructor vs. student movement, axis by axis (ax, ay, az).

    Gravity is removed per-axis using each pod's own (EMA-tracked) gravity
    vector, so resting acceleration doesn't count as "movement".

    Rules:
      - If ANY axis (x, y or z) is below min_movement_accel for EITHER the
        instructor or the student, the match is 0 - not enough real motion
        to judge.
      - If ANY axis moves in OPPOSITE directions between instructor and
        student, the match is capped below 0.5 - it should clearly reflect
        a mismatch.
      - If ALL THREE axes move in the SAME direction, the match is at least
        0.9 - direction match is rewarded generously regardless of exact
        intensity.
    """
    instructor_accel = (
        instructor.ax - instructor_gravity[0],
        instructor.ay - instructor_gravity[1],
        instructor.az - instructor_gravity[2],
    )
    student_accel = (
        student.ax - student_gravity[0],
        student.ay - student_gravity[1],
        student.az - student_gravity[2],
    )

    for ia, sa in zip(instructor_accel, student_accel):
        if abs(ia) < min_movement_accel or abs(sa) < min_movement_accel:
            return SimilarityResult(score=0.0, direction_score=0.0, magnitude_score=0.0)

    same_direction_count = 0
    magnitude_ratios = []
    for ia, sa in zip(instructor_accel, student_accel):
        if ia * sa >= 0:
            same_direction_count += 1
        magnitude_ratios.append(min(abs(ia), abs(sa)) / max(abs(ia), abs(sa)))

    direction_score = same_direction_count / 3.0
    magnitude_score = sum(r ** (1.0 / direction_penalty_exponent) for r in magnitude_ratios) / 3.0

    if same_direction_count == 3:
        # All axes match direction -> high score (90%-100%), leniency on
        # magnitude only affects how close to 100% it gets.
        score = 0.9 + 0.1 * magnitude_score
    else:
        # At least one axis is moving the opposite way -> always below 50%,
        # and the more axes disagree, the lower the score.
        score = 0.5 * magnitude_score * direction_score

    return SimilarityResult(
        score=max(0.0, min(1.0, score)),
        direction_score=direction_score,
        magnitude_score=magnitude_score,
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
