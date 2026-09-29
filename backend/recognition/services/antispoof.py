"""Passive liveness: MiniFASNet (Silent-Face) plus a conservative screen heuristic."""
from __future__ import annotations

import logging
import threading
import urllib.error
import urllib.request
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

WEIGHTS_DIR = Path(__file__).resolve().parent.parent / "weights"

MODEL_SPECS = [
    {
        "file": "2.7_80x80_MiniFASNetV2.onnx",
        "scale": 2.7,
        "urls": [
            "https://raw.githubusercontent.com/QingHeYang/Silent-Face-Anti-Spoofing-onnx/main/onnx/2.7_80x80_MiniFASNetV2.onnx",
            "https://cdn.jsdelivr.net/gh/QingHeYang/Silent-Face-Anti-Spoofing-onnx@main/onnx/2.7_80x80_MiniFASNetV2.onnx",
            "https://github.com/yakhyo/face-anti-spoofing/releases/download/weights/MiniFASNetV2.onnx",
        ],
    },
    {
        "file": "4_0_0_80x80_MiniFASNetV1SE.onnx",
        "scale": 4.0,
        "urls": [
            "https://raw.githubusercontent.com/QingHeYang/Silent-Face-Anti-Spoofing-onnx/main/onnx/4_0_0_80x80_MiniFASNetV1SE.onnx",
            "https://cdn.jsdelivr.net/gh/QingHeYang/Silent-Face-Anti-Spoofing-onnx@main/onnx/4_0_0_80x80_MiniFASNetV1SE.onnx",
            "https://github.com/yakhyo/face-anti-spoofing/releases/download/weights/MiniFASNetV1SE.onnx",
        ],
    },
]

WEBCAM_REAL_THRESHOLD = 0.50
CCTV_REAL_THRESHOLD = 0.40
MIN_FACE_PX_FOR_MODEL = 72
SCREEN_REJECT = 0.62


def _softmax(vec: np.ndarray) -> np.ndarray:
    x = vec.astype(np.float64)
    x = x - np.max(x)
    e = np.exp(x)
    return e / np.clip(np.sum(e), 1e-9, None)


def _real_score(output: np.ndarray) -> float:
    vec = np.asarray(output, dtype=np.float32).reshape(-1)
    if vec.size == 0:
        return 0.0
    probs = _softmax(vec)
    if probs.size == 2:
        return float(probs[1])
    # Silent-Face MiniFASNet (3-class) treats index 1 as the live score
    if probs.size >= 2:
        return float(probs[1])
    return float(probs[-1])


def crop_with_scale(image: np.ndarray, bbox, scale: float, size: int = 80) -> np.ndarray | None:
    h, w = image.shape[:2]
    x1, y1, x2, y2 = [float(v) for v in bbox]
    bw = max(x2 - x1, 1.0)
    bh = max(y2 - y1, 1.0)
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    nw = bw * scale
    nh = bh * scale
    nx1 = int(round(cx - nw / 2.0))
    ny1 = int(round(cy - nh / 2.0))
    nx2 = int(round(cx + nw / 2.0))
    ny2 = int(round(cy + nh / 2.0))

    pad_left = max(0, -nx1)
    pad_top = max(0, -ny1)
    pad_right = max(0, nx2 - w)
    pad_bottom = max(0, ny2 - h)
    crop = image[max(0, ny1):min(h, ny2), max(0, nx1):min(w, nx2)]
    if crop.size == 0:
        return None
    if pad_left or pad_top or pad_right or pad_bottom:
        crop = cv2.copyMakeBorder(
            crop,
            pad_top,
            pad_bottom,
            pad_left,
            pad_right,
            cv2.BORDER_CONSTANT,
            value=(0, 0, 0),
        )
    if crop.size == 0:
        return None
    return cv2.resize(crop, (size, size), interpolation=cv2.INTER_LINEAR)


def screen_moire_score(face_bgr: np.ndarray) -> float:
    """Higher means more likely a recaptured phone/monitor (periodic grid)."""
    if face_bgr is None or face_bgr.size == 0:
        return 0.0
    gray = cv2.cvtColor(cv2.resize(face_bgr, (128, 128)), cv2.COLOR_BGR2GRAY).astype(np.float32)
    mag = np.abs(np.fft.fftshift(np.fft.fft2(gray)))
    cy, cx = mag.shape[0] // 2, mag.shape[1] // 2
    mag[cy - 3:cy + 4, cx - 3:cx + 4] = 0
    total = float(np.sum(mag)) + 1e-6
    # Phone pixels create energy along the axes away from DC
    axis = float(np.sum(mag[cy - 2:cy + 3, :]) + np.sum(mag[:, cx - 2:cx + 3]))
    return float(np.clip(axis / total, 0.0, 1.0))


def _download(url: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp")
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 AIAttendance/1.0"},
        )
        with urllib.request.urlopen(req, timeout=45) as resp, tmp.open("wb") as fh:
            while True:
                chunk = resp.read(1024 * 64)
                if not chunk:
                    break
                fh.write(chunk)
        if tmp.stat().st_size < 10_000:
            tmp.unlink(missing_ok=True)
            logger.warning("Anti-spoof download too small: %s", url)
            return False
        tmp.replace(dest)
        return True
    except urllib.error.HTTPError as exc:
        logger.warning("Anti-spoof model download failed (%s): %s", exc.code, url)
        tmp.unlink(missing_ok=True)
        return False
    except Exception as exc:
        logger.warning("Anti-spoof model download failed: %s (%s)", url, exc)
        tmp.unlink(missing_ok=True)
        return False


def _ensure_weight(spec: dict) -> Path | None:
    path = WEIGHTS_DIR / spec["file"]
    if path.exists() and path.stat().st_size >= 10_000:
        return path
    urls = spec.get("urls") or ([spec["url"]] if spec.get("url") else [])
    logger.info("Downloading anti-spoof model %s", spec["file"])
    for url in urls:
        if _download(url, path):
            return path
    return None


class AntiSpoofChecker:
    def __init__(self):
        self._lock = threading.Lock()
        self._sessions: list[tuple[object, float]] = []
        self._load_attempted = False
        self._available = False

    def ensure_models(self) -> bool:
        with self._lock:
            return self._ensure_locked()

    def _ensure_locked(self) -> bool:
        if self._load_attempted:
            return self._available
        self._load_attempted = True
        try:
            import onnxruntime as ort
        except Exception:
            logger.warning("onnxruntime missing — MiniFASNet liveness disabled")
            return False

        sessions = []
        for spec in MODEL_SPECS:
            path = _ensure_weight(spec)
            if path is None:
                continue
            try:
                sess = ort.InferenceSession(
                    str(path),
                    providers=["CPUExecutionProvider"],
                )
                sessions.append((sess, spec["scale"]))
            except Exception:
                logger.exception("Failed to load anti-spoof model %s", path)
        self._sessions = sessions
        self._available = bool(sessions)
        if not self._available:
            logger.warning("MiniFASNet weights unavailable — using heuristic liveness only")
        return self._available

    def evaluate(self, image: np.ndarray, face, mode: str = "webcam") -> dict:
        bbox = getattr(face, "bbox", None)
        if bbox is None:
            return {
                "passed": False,
                "skipped": False,
                "score": 0.0,
                "message": "No face for liveness check",
            }

        x1, y1, x2, y2 = [int(v) for v in bbox]
        face_w, face_h = max(x2 - x1, 0), max(y2 - y1, 0)
        strict = mode != "cctv"
        threshold = WEBCAM_REAL_THRESHOLD if strict else CCTV_REAL_THRESHOLD

        if min(face_w, face_h) < MIN_FACE_PX_FOR_MODEL and mode == "cctv":
            return {
                "passed": True,
                "skipped": True,
                "score": None,
                "message": "Liveness skipped — face too small on CCTV",
            }

        h, w = image.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        crop = image[y1:y2, x1:x2]
        moire = screen_moire_score(crop) if crop.size else 0.0

        model_score = self._model_score(image, bbox)
        if model_score is None:
            if not strict:
                return {
                    "passed": True,
                    "skipped": True,
                    "score": None,
                    "screen_score": round(moire, 4),
                    "message": "Liveness model unavailable — CCTV match allowed",
                }
            if moire >= SCREEN_REJECT:
                return {
                    "passed": False,
                    "skipped": False,
                    "score": 0.0,
                    "screen_score": round(moire, 4),
                    "message": "Screen recapture detected — use a live face, not a photo",
                }
            return {
                "passed": True,
                "skipped": True,
                "score": None,
                "screen_score": round(moire, 4),
                "message": "Liveness model unavailable — heuristic passed",
            }

        if model_score < threshold:
            return {
                "passed": False,
                "skipped": False,
                "score": round(model_score, 4),
                "screen_score": round(moire, 4),
                "message": "Spoof detected — use a live face, not a photo or screen",
            }
        if strict and moire >= SCREEN_REJECT:
            return {
                "passed": False,
                "skipped": False,
                "score": round(model_score, 4),
                "screen_score": round(moire, 4),
                "message": "Screen recapture detected — use a live face, not a photo",
            }
        return {
            "passed": True,
            "skipped": False,
            "score": round(model_score, 4),
            "screen_score": round(moire, 4),
            "message": "Live face",
        }

    def _model_score(self, image: np.ndarray, bbox) -> float | None:
        if not self.ensure_models():
            return None
        scores = []
        for sess, scale in self._sessions:
            crop = crop_with_scale(image, bbox, scale=scale, size=80)
            if crop is None:
                continue
            blob = crop.astype(np.float32) / 255.0
            blob = np.transpose(blob, (2, 0, 1))[None, ...]
            input_name = sess.get_inputs()[0].name
            try:
                output = sess.run(None, {input_name: blob})[0]
            except Exception:
                logger.exception("MiniFASNet inference failed")
                continue
            scores.append(_real_score(output))
        if not scores:
            return None
        return float(sum(scores) / len(scores))
