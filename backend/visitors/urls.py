from django.urls import include, path
from rest_framework.routers import DefaultRouter

from visitors.views import PublicVisitGateView, VisitViewSet, VisitorViewSet

router = DefaultRouter()
router.register("people", VisitorViewSet, basename="visitor")
router.register("visits", VisitViewSet, basename="visit")

urlpatterns = [
    path("gate/<str:token>/", PublicVisitGateView.as_view(), name="visitor-gate"),
    path("", include(router.urls)),
]
