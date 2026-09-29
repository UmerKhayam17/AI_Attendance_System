"""Require several consistent recognitions before attendance is written."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass

CONFIRM_CCTV = 3
CONFIRM_WEBCAM = 2
CONFIRM_WINDOW_SEC = 12.0


@dataclass(frozen=True)
class ConfirmResult:
    confirmed: bool
    hits: int
    required: int
    message: str


class MatchConfirmer:
    def __init__(self):
        self._lock = threading.Lock()
        self._windows: dict[tuple, dict] = {}

    def observe(
        self,
        *,
        organization_id: int | None,
        source_key: str,
        employee_id: str,
        required: int = CONFIRM_CCTV,
        window_sec: float = CONFIRM_WINDOW_SEC,
        now: float | None = None,
    ) -> ConfirmResult:
        now = time.time() if now is None else now
        key = (organization_id, source_key)
        with self._lock:
            state = self._windows.get(key)
            if state is None or state.get("employee_id") != employee_id:
                state = {"employee_id": employee_id, "times": []}
            times = [t for t in state["times"] if now - t <= window_sec]
            times.append(now)
            state["times"] = times
            self._windows[key] = state
            hits = len(times)
            if hits >= required:
                state["times"] = []
                return ConfirmResult(
                    True,
                    hits,
                    required,
                    "Identity confirmed",
                )
            return ConfirmResult(
                False,
                hits,
                required,
                f"Confirming identity ({hits}/{required})",
            )

    def reset(self, organization_id: int | None, source_key: str) -> None:
        with self._lock:
            self._windows.pop((organization_id, source_key), None)

    def clear(self) -> None:
        with self._lock:
            self._windows.clear()


_confirmer: MatchConfirmer | None = None
_confirmer_lock = threading.Lock()


def get_match_confirmer() -> MatchConfirmer:
    global _confirmer
    if _confirmer is None:
        with _confirmer_lock:
            if _confirmer is None:
                _confirmer = MatchConfirmer()
    return _confirmer
