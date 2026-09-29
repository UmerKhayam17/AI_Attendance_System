from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.localtime import local_date
from organizations.mixins import OrganizationScopedMixin
from organizations.permissions import CanOperate, CanView, IsOwnerOrAdmin
from organizations.query import parse_branch_id
from visitors.models import Visit, Visitor
from visitors.serializers import (
    PublicVisitSerializer,
    VisitSerializer,
    VisitWriteSerializer,
    VisitorSerializer,
)
from visitors.services import (
    cancel_visit,
    check_in,
    check_out,
    deny_visit,
    mark_no_show,
    set_watchlist,
)


class VisitorViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    queryset = Visitor.objects.annotate(visit_count=Count("visits"))
    serializer_class = VisitorSerializer
    organization_field = "organization"

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [CanView()]
        if self.action in ("watchlist", "destroy"):
            return [IsOwnerOrAdmin()]
        return [CanOperate()]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("watchlist") == "1":
            qs = qs.filter(is_blacklisted=True)
        q = (self.request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(phone__icontains=q)
                | Q(company__icontains=q)
                | Q(id_number__icontains=q)
                | Q(email__icontains=q)
            )
        return qs.distinct()

    def perform_create(self, serializer):
        serializer.save(organization=self.request.organization)

    @action(detail=True, methods=["post"])
    def watchlist(self, request, pk=None):
        visitor = self.get_object()
        blocked = bool(request.data.get("blocked", True))
        set_watchlist(visitor, blocked, request.data.get("reason") or "")
        visitor.refresh_from_db()
        visitor.visit_count = visitor.visits.count()
        return Response(VisitorSerializer(visitor, context={"request": request}).data)


class VisitViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    queryset = Visit.objects.select_related("visitor", "host", "branch")
    serializer_class = VisitSerializer
    organization_field = "organization"
    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self):
        if self.action in ("list", "retrieve", "summary"):
            return [CanView()]
        return [CanOperate()]

    def get_queryset(self):
        qs = super().get_queryset()
        status_filter = self.request.query_params.get("status")
        if status_filter and status_filter != "all":
            qs = qs.filter(status=status_filter)
        branch_id = parse_branch_id(self.request)
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        day = self.request.query_params.get("date")
        if day:
            parsed = parse_date(day)
            if parsed:
                qs = qs.filter(Q(expected_at__date=parsed) | Q(check_in_at__date=parsed)).distinct()
        q = (self.request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(visitor__first_name__icontains=q)
                | Q(visitor__last_name__icontains=q)
                | Q(visitor__phone__icontains=q)
                | Q(visitor__company__icontains=q)
                | Q(badge_code__icontains=q)
            ).distinct()
        return qs

    def create(self, request, *args, **kwargs):
        writer = VisitWriteSerializer(data=request.data)
        writer.is_valid(raise_exception=True)
        visit = writer.create_visit(request.organization, user=request.user)
        return Response(
            VisitSerializer(visit, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"])
    def summary(self, request):
        org = request.organization
        today = local_date(organization=org)
        qs = Visit.objects.filter(organization=org)
        branch_id = parse_branch_id(request)
        if branch_id:
            qs = qs.filter(branch_id=branch_id)
        return Response({
            "date": str(today),
            "on_site": qs.filter(status=Visit.STATUS_CHECKED_IN).count(),
            "expected_today": qs.filter(status=Visit.STATUS_EXPECTED, expected_at__date=today).count(),
            "checked_in_today": qs.filter(check_in_at__date=today).count(),
            "watchlist": Visitor.objects.filter(organization=org, is_blacklisted=True).count(),
        })

    @action(detail=True, methods=["post"])
    def check_in(self, request, pk=None):
        visit = check_in(self.get_object())
        return Response(VisitSerializer(visit, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def check_out(self, request, pk=None):
        visit = check_out(self.get_object())
        return Response(VisitSerializer(visit, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        visit = cancel_visit(self.get_object())
        return Response(VisitSerializer(visit, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def no_show(self, request, pk=None):
        visit = mark_no_show(self.get_object())
        return Response(VisitSerializer(visit, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def deny(self, request, pk=None):
        visit = deny_visit(self.get_object(), request.data.get("reason") or "")
        return Response(VisitSerializer(visit, context={"request": request}).data)


class PublicVisitGateView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get_object(self, token):
        return get_object_or_404(
            Visit.objects.select_related("visitor", "host", "branch", "organization"),
            public_token=token,
        )

    def get(self, request, token):
        return Response(PublicVisitSerializer(self.get_object(token)).data)

    def post(self, request, token):
        action_name = request.data.get("action") or "check_in"
        visit = self.get_object(token)
        if action_name == "check_in":
            visit = check_in(visit)
        elif action_name == "check_out":
            visit = check_out(visit)
        else:
            return Response({"error": "Unknown action"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PublicVisitSerializer(visit).data)
