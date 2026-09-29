"""Nearest-neighbor face matching against per-person embedding galleries."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Webcam / close-range matching
SIMILARITY_THRESHOLD = 0.45
# CCTV faces are often farther / lower-res — slightly more tolerant
CCTV_SIMILARITY_THRESHOLD = 0.38
# Below auto-match but worth a human look
REVIEW_MIN_SIMILARITY = 0.28
# Reject if the runner-up person is this close (false identity swaps)
MATCH_MARGIN = 0.06


@dataclass(frozen=True)
class MatchResult:
    employee_id: str | None
    confidence: float
    second_best: float
    ambiguous: bool
    message: str
    candidate_id: str | None = None

    @property
    def matched(self) -> bool:
        return self.employee_id is not None and not self.ambiguous

    def needs_review(self, review_min: float = REVIEW_MIN_SIMILARITY) -> bool:
        if self.matched:
            return False
        if not self.candidate_id:
            return False
        if self.ambiguous:
            return True
        return self.confidence >= review_min


def l2_normalize(vec: np.ndarray) -> np.ndarray | None:
    probe = np.asarray(vec, dtype=np.float32).reshape(-1)
    if probe.size == 0:
        return None
    norm = float(np.linalg.norm(probe))
    if norm == 0:
        return None
    return probe / norm


def as_vector_matrix(stored) -> np.ndarray | None:
    """Accept one vector or a list of vectors; return (K, D) L2-normalized."""
    if stored is None:
        return None
    if isinstance(stored, np.ndarray) and stored.ndim == 1:
        rows = [stored]
    elif isinstance(stored, (list, tuple)):
        if not stored:
            return None
        first = stored[0]
        if isinstance(first, (int, float, np.floating)):
            rows = [stored]
        else:
            rows = list(stored)
    else:
        return None

    mats = []
    for row in rows:
        vec = l2_normalize(row)
        if vec is not None:
            mats.append(vec)
    if not mats:
        return None
    return np.stack(mats, axis=0)


def best_match(
    probe,
    gallery: dict[str, object],
    threshold: float | None = None,
    margin: float | None = None,
) -> MatchResult:
    min_sim = SIMILARITY_THRESHOLD if threshold is None else threshold
    min_margin = MATCH_MARGIN if margin is None else margin
    probe_vec = l2_normalize(probe)
    if probe_vec is None or not gallery:
        return MatchResult(None, 0.0, -1.0, False, "Unknown face")

    search = getattr(gallery, "search", None)
    if callable(search):
        scores, row_ids = search(probe_vec)
        best_id = None
        best_sim = -1.0
        second_sim = -1.0
        per_person: dict[str, float] = {}
        for score, employee_id in zip(scores, row_ids):
            prev = per_person.get(employee_id)
            value = float(score)
            if prev is None or value > prev:
                per_person[employee_id] = value
        ranked = sorted(per_person.items(), key=lambda kv: kv[1], reverse=True)
        if ranked:
            best_id, best_sim = ranked[0]
            if len(ranked) > 1:
                second_sim = ranked[1][1]
        return _finish_match(best_id, best_sim, second_sim, min_sim, min_margin)

    best_id = None
    best_sim = -1.0
    second_sim = -1.0

    for employee_id, stored in gallery.items():
        mat = as_vector_matrix(stored)
        if mat is None:
            continue
        person_best = float(np.max(mat @ probe_vec))
        if person_best > best_sim:
            second_sim = best_sim
            best_sim = person_best
            best_id = str(employee_id)
        elif person_best > second_sim:
            second_sim = person_best

    return _finish_match(best_id, best_sim, second_sim, min_sim, min_margin)


def _finish_match(best_id, best_sim, second_sim, min_sim, min_margin) -> MatchResult:
    if best_id is None:
        return MatchResult(None, 0.0, -1.0, False, "Unknown face", None)

    if best_sim < min_sim:
        return MatchResult(
            None,
            best_sim,
            second_sim,
            False,
            "Unknown face",
            best_id,
        )

    if second_sim >= 0 and (best_sim - second_sim) < min_margin:
        return MatchResult(
            None,
            best_sim,
            second_sim,
            True,
            "Ambiguous match — skipped to avoid a false identity",
            best_id,
        )

    return MatchResult(best_id, best_sim, second_sim, False, "Face recognized", best_id)
