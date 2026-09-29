"""Process-local vector index for ArcFace galleries (numpy, optional FAISS).

Embeddings stay in FaceEnrollment JSON. This cache avoids reloading JSON and
looping people one-by-one on every CCTV frame. A dedicated `run_cctv_worker`
process holds one copy of the index + one InsightFace session.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

import numpy as np

from recognition.services.gallery import build_gallery
from recognition.services.matching import as_vector_matrix, l2_normalize

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_CACHE: dict[int, tuple[float, "GalleryIndex"]] = {}
_TTL_SEC = 30.0


def _try_faiss():
    try:
        import faiss  # type: ignore

        return faiss
    except Exception:
        return None


@dataclass
class GalleryIndex:
    gallery: dict[str, list[list[float]]]
    matrix: np.ndarray
    row_ids: list[str]
    backend: str = "numpy"
    _faiss_index: object | None = None

    def __len__(self):
        return len(self.gallery)

    def __bool__(self):
        return bool(self.gallery)

    def items(self):
        return self.gallery.items()

    def keys(self):
        return self.gallery.keys()

    def values(self):
        return self.gallery.values()

    def get(self, key, default=None):
        return self.gallery.get(key, default)

    def __iter__(self):
        return iter(self.gallery)

    def search(self, probe: np.ndarray) -> tuple[np.ndarray, list[str]]:
        vec = l2_normalize(probe)
        if vec is None or self.matrix.size == 0:
            return np.zeros(0, dtype=np.float32), []
        if self._faiss_index is not None:
            scores, idx = self._faiss_index.search(vec.reshape(1, -1), min(32, len(self.row_ids)))
            scores = scores[0]
            ids = [self.row_ids[int(i)] for i in idx[0] if int(i) >= 0]
            return scores.astype(np.float32), ids
        scores = self.matrix @ vec
        return scores.astype(np.float32), self.row_ids


def build_index(gallery: dict[str, list[list[float]]]) -> GalleryIndex:
    rows: list[np.ndarray] = []
    ids: list[str] = []
    for employee_id, stored in gallery.items():
        mat = as_vector_matrix(stored)
        if mat is None:
            continue
        for i in range(mat.shape[0]):
            rows.append(mat[i])
            ids.append(str(employee_id))
    if not rows:
        return GalleryIndex(gallery=gallery, matrix=np.zeros((0, 0), dtype=np.float32), row_ids=[], backend="empty")

    matrix = np.stack(rows, axis=0).astype(np.float32)
    faiss = _try_faiss()
    index = GalleryIndex(gallery=gallery, matrix=matrix, row_ids=ids, backend="numpy")
    if faiss is not None and matrix.shape[0] >= 8:
        try:
            idx = faiss.IndexFlatIP(matrix.shape[1])
            idx.add(matrix)
            index._faiss_index = idx
            index.backend = "faiss"
        except Exception:
            logger.debug("FAISS index build skipped", exc_info=True)
    return index


def get_gallery_index(organization_id: int | None, *, force: bool = False) -> GalleryIndex:
    if not organization_id:
        return GalleryIndex(gallery={}, matrix=np.zeros((0, 0), dtype=np.float32), row_ids=[], backend="empty")
    now = time.time()
    with _LOCK:
        cached = _CACHE.get(organization_id)
        if cached and not force and now - cached[0] < _TTL_SEC:
            return cached[1]
    gallery = build_gallery(organization_id=organization_id)
    index = build_index(gallery)
    with _LOCK:
        _CACHE[organization_id] = (now, index)
    return index


def invalidate_gallery(organization_id: int | None = None):
    with _LOCK:
        if organization_id is None:
            _CACHE.clear()
        else:
            _CACHE.pop(organization_id, None)
