from django.urls import include, path
from rest_framework.routers import DefaultRouter

from recognition.camera_views import (
    CameraViewSet,
    CCTVControlView,
    CCTVEventsView,
    DetectionSnapshotListView,
)
from recognition.review_views import MatchReviewViewSet
from recognition.event_views import RecognitionEventViewSet
from recognition.views import (
    CaptureFaceView,
    EnrollmentStatusView,
    GalleryStatsView,
    IdentifyFaceView,
    TrainEmbeddingsView,
)

router = DefaultRouter()
router.register("cameras", CameraViewSet, basename="camera")
router.register("reviews", MatchReviewViewSet, basename="match-review")
router.register("events", RecognitionEventViewSet, basename="recognition-event")

urlpatterns = [
    path("", include(router.urls)),
    path("gallery/stats/", GalleryStatsView.as_view(), name="gallery-stats"),
    path("identify/", IdentifyFaceView.as_view(), name="identify-face"),
    path("cctv/", CCTVControlView.as_view(), name="cctv-control"),
    path("cctv/events/", CCTVEventsView.as_view(), name="cctv-events"),
    path("detections/", DetectionSnapshotListView.as_view(), name="detection-snapshots"),
    path(
        "enroll/<str:employee_id>/",
        EnrollmentStatusView.as_view(),
        name="enrollment-status",
    ),
    path(
        "enroll/<str:employee_id>/capture/",
        CaptureFaceView.as_view(),
        name="capture-face",
    ),
    path(
        "enroll/<str:employee_id>/train/",
        TrainEmbeddingsView.as_view(),
        name="train-embeddings",
    ),
]
