"""Train ArcFace galleries from saved enrollment photos."""
from __future__ import annotations

from pathlib import Path

from django.conf import settings

from recognition.services.face_engine import get_face_engine
from recognition.services.gallery_index import invalidate_gallery

MIN_ENROLLMENT_IMAGES = 5
MODEL_VERSION = "InsightFace_v1_multi_light"


class TrainingError(ValueError):
    pass


def train_enrollment(enrollment) -> dict:
    if enrollment.total_images < MIN_ENROLLMENT_IMAGES:
        raise TrainingError(
            f"Need at least {MIN_ENROLLMENT_IMAGES} images, "
            f"currently have {enrollment.total_images}"
        )

    engine = get_face_engine()
    folder = Path(settings.MEDIA_ROOT) / enrollment.dataset_folder
    embeddings, source_count = engine.generate_embeddings_from_folder(folder)

    if source_count < MIN_ENROLLMENT_IMAGES:
        raise TrainingError(
            f"Only {source_count} valid faces found in dataset. "
            "Recapture with better quality."
        )

    mean_embedding = engine.average_embedding(embeddings)
    enrollment.embedding = mean_embedding
    enrollment.embeddings = [vec.astype(float).tolist() for vec in embeddings]
    enrollment.is_trained = True
    enrollment.is_enrolled = True
    enrollment.model_version = MODEL_VERSION
    enrollment.save(
        update_fields=[
            "embedding",
            "embeddings",
            "is_trained",
            "is_enrolled",
            "model_version",
            "updated_at",
        ]
    )
    invalidate_gallery(enrollment.employee.organization_id)
    return {
        "trained": True,
        "embedding_dim": len(mean_embedding),
        "images_used": source_count,
        "embeddings_stored": len(enrollment.embeddings),
        "model_version": MODEL_VERSION,
        "enrollment": enrollment,
    }
