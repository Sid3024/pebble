from __future__ import annotations


class BaselineCalculator:
    """
    Accumulates the first n window sums for a person and computes their mean.
    Once ready, further values are ignored — the baseline is fixed.
    """

    def __init__(self, n: int) -> None:
        self._n = n
        self._values: list[float] = []

    def add(self, value: float) -> None:
        if not self.is_ready():
            self._values.append(value)

    def is_ready(self) -> bool:
        return len(self._values) >= self._n

    @property
    def samples_collected(self) -> int:
        return len(self._values)

    def baseline(self) -> float | None:
        """Mean of collected samples, or None if not enough data yet."""
        if not self.is_ready():
            return None
        return sum(self._values) / len(self._values)


def expected_effort(calc: BaselineCalculator) -> float | None:
    """
    Return the expected effort level for a person.
    Currently equals the baseline average.
    Replace the body of this function to use a more sophisticated model.
    """
    return calc.baseline()
