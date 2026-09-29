"""Exposure helpers so outdoor sunlight matches indoor enrollment photos."""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

TARGET_MEAN = 118.0
WELL_LIT_MIN = 62.0
WELL_LIT_MAX = 178.0
MIN_USABLE_MEAN = 24.0
MAX_USABLE_MEAN = 236.0
MAX_HIGHLIGHT_RATIO = 0.32
MAX_SHADOW_RATIO = 0.42
HIGHLIGHT_VALUE = 248
SHADOW_VALUE = 18


@dataclass(frozen=True)
class ExposureStats:
    mean: float
    highlight_ratio: float
    shadow_ratio: float

    @property
    def overexposed(self) -> bool:
        return self.highlight_ratio >= MAX_HIGHLIGHT_RATIO or self.mean >= MAX_USABLE_MEAN

    @property
    def underexposed(self) -> bool:
        return self.shadow_ratio >= MAX_SHADOW_RATIO or self.mean <= MIN_USABLE_MEAN

    @property
    def needs_correction(self) -> bool:
        return self.mean < WELL_LIT_MIN or self.mean > WELL_LIT_MAX

    @property
    def unusable(self) -> bool:
        return self.overexposed or self.underexposed


def crop_bbox(image: np.ndarray, bbox) -> np.ndarray:
    if image is None or image.size == 0 or bbox is None:
        return np.zeros((0, 0, 3), dtype=np.uint8)
    h, w = image.shape[:2]
    x1, y1, x2, y2 = [int(v) for v in bbox]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return np.zeros((0, 0, 3), dtype=np.uint8)
    return image[y1:y2, x1:x2]


def exposure_stats(image: np.ndarray) -> ExposureStats:
    if image is None or image.size == 0:
        return ExposureStats(0.0, 1.0, 1.0)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    mean = float(np.mean(gray))
    highlight = float(np.mean(gray >= HIGHLIGHT_VALUE))
    shadow = float(np.mean(gray <= SHADOW_VALUE))
    return ExposureStats(mean, highlight, shadow)


def apply_gamma(image: np.ndarray, gamma: float) -> np.ndarray:
    gamma = float(np.clip(gamma, 0.35, 2.8))
    table = ((np.arange(256, dtype=np.float32) / 255.0) ** gamma * 255.0).astype(np.uint8)
    return cv2.LUT(image, table)


def gamma_for_mean(current: float, target: float = TARGET_MEAN) -> float:
    current = float(np.clip(current, 1.0, 254.0))
    target = float(np.clip(target, 1.0, 254.0))
    return float(np.log(target / 255.0) / np.log(current / 255.0))


def correct_exposure(image: np.ndarray, current_mean: float | None = None) -> np.ndarray:
    """Pull a too-dark or sun-blasted frame toward typical indoor brightness."""
    if current_mean is None:
        current_mean = exposure_stats(image).mean
    if WELL_LIT_MIN <= current_mean <= WELL_LIT_MAX:
        return image
    return apply_gamma(image, gamma_for_mean(current_mean))


def apply_clahe_bgr(image: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    lightness, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    merged = cv2.merge((clahe.apply(lightness), a, b))
    return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)


def lighting_variants(image: np.ndarray) -> list[np.ndarray]:
    """Same photo under brighter, darker, and contrast-normalized light."""
    return [
        image,
        apply_gamma(image, 0.62),
        apply_gamma(image, 1.55),
        apply_clahe_bgr(image),
    ]


def closest_face(faces, bbox):
    if not faces:
        return None
    if bbox is None:
        return max(faces, key=lambda f: float(getattr(f, "det_score", 0.0)))
    tx1, ty1, tx2, ty2 = [float(v) for v in bbox]
    tcx, tcy = (tx1 + tx2) / 2.0, (ty1 + ty2) / 2.0

    def dist(face) -> float:
        x1, y1, x2, y2 = [float(v) for v in face.bbox]
        return abs((x1 + x2) / 2.0 - tcx) + abs((y1 + y2) / 2.0 - tcy)

    return min(faces, key=dist)
