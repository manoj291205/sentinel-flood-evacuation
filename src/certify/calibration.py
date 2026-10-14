"""Rolling calibration monitor for executed FEASIBLE dispatches (report only in Phase 24)."""

from __future__ import annotations

from collections import deque

from .params import CertParams


class CalibrationMonitor:
    def __init__(self, params: CertParams | None = None, window: int = 50) -> None:
        self.params = params or CertParams()
        self.window = window
        self._records: deque[tuple[float, bool]] = deque(maxlen=window)

    def record(self, predicted_lower: float, succeeded: bool) -> None:
        self._records.append((predicted_lower, bool(succeeded)))

    @property
    def executions(self) -> int:
        return len(self._records)

    def coverage(self) -> float | None:
        if not self._records:
            return None
        return sum(ok for _, ok in self._records) / len(self._records)

    def recommend_fallback(self) -> str | None:
        """"TIGHTEN" (halve eps) or "DETERMINISTIC_MASK"; None while data or coverage suffice."""
        if len(self._records) < self.window:
            return None
        coverage = self.coverage()
        eps = self.params.eps_dispatch
        if coverage < 1.0 - 2.0 * eps:
            return "DETERMINISTIC_MASK"
        if coverage < 1.0 - eps - 0.02:
            return "TIGHTEN"
        return None
