import base64
import io
import threading
from pathlib import Path

import cv2
import numpy as np
from django.conf import settings
from PIL import Image

from recognition.services.antispoof import AntiSpoofChecker
from recognition.services.lighting import (
    apply_clahe_bgr,
    closest_face,
    correct_exposure,
    crop_bbox,
    exposure_stats,
    lighting_variants,
)
from recognition.services.matching import (
    CCTV_SIMILARITY_THRESHOLD,
    MatchResult,
    best_match,
)
from recognition.services.quality_checker import FaceQualityChecker

_engine = None
_engine_lock = threading.Lock()


def _provider_loads(provider: str) -> bool:
    """True if ORT can actually create a session with this EP (DLL/runtime present)."""
    from onnx import TensorProto, helper
    import onnxruntime as ort

    try:
        graph = helper.make_graph(
            [helper.make_node("Identity", ["x"], ["y"])],
            "probe",
            [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1])],
            [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1])],
        )
        model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
        sess = ort.InferenceSession(model.SerializeToString(), providers=[provider])
        active = sess.get_providers()
        return bool(active) and active[0] == provider
    except Exception:
        return False


def _select_onnx_providers() -> list[str]:
    """Prefer NVIDIA CUDA, then DirectML (Windows), else CPU."""
    import logging

    import onnxruntime as ort

    available = set(ort.get_available_providers())
    preferred = (
        "CUDAExecutionProvider",
        "DmlExecutionProvider",
        "CPUExecutionProvider",
    )
    providers: list[str] = []
    for name in preferred:
        if name not in available:
            continue
        if name == "CPUExecutionProvider" or _provider_loads(name):
            providers.append(name)
    if not providers:
        providers = ["CPUExecutionProvider"]
    logging.getLogger(__name__).info("ONNX Runtime providers: %s", providers)
    return providers


def get_face_engine():
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = FaceEngine()
    return _engine


class FaceEngine:
    def __init__(self):
        from insightface.app import FaceAnalysis

        providers = _select_onnx_providers()
        # InsightFace: ctx_id >= 0 for GPU providers, -1 for CPU-only
        ctx_id = -1 if providers == ["CPUExecutionProvider"] else 0
        self.providers = providers
        self.app = FaceAnalysis(name="buffalo_l", providers=providers)
        self.app.prepare(ctx_id=ctx_id, det_size=(640, 640))
        self.quality = FaceQualityChecker()
        self.liveness = AntiSpoofChecker()
        threading.Thread(target=self.liveness.ensure_models, name="antispoof-preload", daemon=True).start()
        # InsightFace / ONNX Runtime is not safe for concurrent app.get() calls
        self._infer_lock = threading.Lock()

    @staticmethod
    def decode_image(image_bytes: bytes) -> np.ndarray:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Invalid image data")
        return image

    @staticmethod
    def decode_base64(data: str) -> np.ndarray:
        if "," in data:
            data = data.split(",", 1)[1]
        return FaceEngine.decode_image(base64.b64decode(data))

    def detect_faces(self, image: np.ndarray):
        with self._infer_lock:
            return self.app.get(image)

    @staticmethod
    def resize_max(image: np.ndarray, max_side: int = 640) -> np.ndarray:
        h, w = image.shape[:2]
        side = max(h, w)
        if side <= max_side:
            return image
        scale = max_side / side
        return cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    def get_single_face(self, image: np.ndarray, allow_largest: bool = False):
        faces = self.detect_faces(image)
        if not faces:
            return None, "No face detected"
        if len(faces) > 1 and not allow_largest:
            return None, "Multiple faces detected — only one person allowed"
        if len(faces) == 1:
            return faces[0], None
        # Enrollment: pick the largest face (ignore background people)
        def face_area(f):
            x1, y1, x2, y2 = f.bbox
            return max(float(x2 - x1), 1.0) * max(float(y2 - y1), 1.0)

        return max(faces, key=face_area), None

    def extract_embedding(self, image: np.ndarray) -> np.ndarray | None:
        face, error = self.get_single_face(image, allow_largest=True)
        if error:
            return None
        return face.embedding

    def _relight_probe(self, image: np.ndarray, face):
        """Re-embed after gamma correction when sunlight blows out or darkens the face.

        Liveness should still run on the original frame — MiniFASNet expects natural photos.
        """
        crop = crop_bbox(image, getattr(face, "bbox", None))
        stats = exposure_stats(crop if crop.size else image)
        if not stats.needs_correction:
            return face
        corrected = correct_exposure(image, stats.mean)
        if corrected is image:
            return face
        faces = self.detect_faces(corrected)
        relit = closest_face(faces, getattr(face, "bbox", None))
        return relit if relit is not None else face

    def check_quality(self, image: np.ndarray, require_liveness: bool = True) -> dict:
        # Smaller input = much faster under CCTV lock contention
        small = self.resize_max(image, 640)
        face, error = self.get_single_face(small, allow_largest=True)
        if error:
            return {"passed": False, "message": error}
        result = self.quality.evaluate(small, face)
        result["bbox"] = face.bbox.astype(int).tolist()
        result["image"] = small
        if result["passed"] and require_liveness:
            live = self.liveness.evaluate(small, face, mode="webcam")
            result["liveness"] = live
            if not live["passed"]:
                result["passed"] = False
                result["message"] = live["message"]
        return result

    def check_liveness(self, image: np.ndarray, face, mode: str = "cctv") -> dict:
        return self.liveness.evaluate(image, face, mode=mode)

    def generate_embeddings_from_folder(
        self, folder_path: Path, augment_lighting: bool = True
    ) -> tuple[list[np.ndarray], int]:
        embeddings: list[np.ndarray] = []
        source_count = 0
        for img_path in sorted(folder_path.glob("*.jpg")):
            image = cv2.imread(str(img_path))
            if image is None:
                continue
            image = self.resize_max(image, 640)
            variants = lighting_variants(image) if augment_lighting else [image]
            got_source = False
            for index, variant in enumerate(variants):
                emb = self.extract_embedding(variant)
                if emb is None:
                    continue
                embeddings.append(emb)
                if index == 0:
                    got_source = True
            if got_source:
                source_count += 1
        return embeddings, source_count

    @staticmethod
    def average_embedding(embeddings: list[np.ndarray]) -> list[float]:
        if not embeddings:
            return []
        mean = np.mean(np.stack(embeddings), axis=0)
        norm = np.linalg.norm(mean)
        if norm > 0:
            mean = mean / norm
        return mean.tolist()

    def save_dataset_image(self, image: np.ndarray, folder: Path, index: int) -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"face_{index:03d}.jpg"
        cv2.imwrite(str(path), image)
        return path

    def save_profile_image(self, image: np.ndarray, employee_id: str, org_id=None) -> str:
        if org_id:
            profile_dir = Path(settings.MEDIA_ROOT) / f"org_{org_id}" / "profile"
        else:
            profile_dir = Path(settings.MEDIA_ROOT) / "profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        path = profile_dir / f"{employee_id}.jpg"
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        Image.fromarray(rgb).save(path, format="JPEG", quality=90)
        return str(path.relative_to(settings.MEDIA_ROOT)).replace("\\", "/")

    def match_probe(
        self,
        probe: np.ndarray | list[float],
        gallery: dict,
        threshold: float | None = None,
    ) -> MatchResult:
        return best_match(probe, gallery, threshold=threshold)

    def match_embedding(
        self,
        probe: np.ndarray | list[float],
        gallery: dict,
        threshold: float | None = None,
    ) -> tuple[str | None, float]:
        result = self.match_probe(probe, gallery, threshold=threshold)
        return result.employee_id, result.confidence

    def identify_from_image(
        self,
        image: np.ndarray,
        gallery: dict,
        threshold: float | None = None,
        check_liveness: bool = True,
        liveness_mode: str = "webcam",
    ) -> dict:
        small = self.resize_max(image, 640)
        live_image = small
        face, error = self.get_single_face(small)
        if error == "No face detected":
            # Local contrast helps backlight / harsh sun when the detector misses the face.
            boosted = apply_clahe_bgr(small)
            face, error = self.get_single_face(boosted)
            if face is not None:
                small = boosted
        if error:
            return {"matched": False, "message": error, "confidence": 0.0}

        liveness = None
        if check_liveness:
            liveness = self.check_liveness(live_image, face, mode=liveness_mode)
            if not liveness["passed"] and not liveness.get("skipped"):
                return {
                    "matched": False,
                    "confidence": 0.0,
                    "message": liveness["message"],
                    "liveness": liveness,
                }

        probe_face = self._relight_probe(small, face)
        result = self.match_probe(probe_face.embedding, gallery, threshold=threshold)
        payload = {
            "matched": result.matched,
            "employee_id": result.employee_id,
            "candidate_id": result.candidate_id,
            "confidence": round(result.confidence, 4),
            "message": result.message,
            "needs_review": result.needs_review(),
        }
        if liveness is not None:
            payload["liveness"] = liveness
        if result.ambiguous:
            payload["ambiguous"] = True
        return payload
