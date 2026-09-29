from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.stripe_service import (
    create_checkout_session,
    create_portal_session,
    handle_webhook_event,
)
from organizations.permissions import IsOwner
from organizations.plans import PLAN_LIMITS, PLAN_PRO, PLAN_STARTER
from organizations.serializers import OrganizationSerializer


class BillingSummaryView(APIView):
    permission_classes = [IsOwner]

    def get(self, request):
        org = request.organization
        return Response({
            "organization": OrganizationSerializer(org).data,
            "plans": [
                {"id": key, **value}
                for key, value in PLAN_LIMITS.items()
            ],
            "stripe_configured": bool(getattr(settings, "STRIPE_SECRET_KEY", "")),
            "has_stripe_customer": bool(org.stripe_customer_id),
            "billing_exempt": bool(org.billing_exempt),
        })


class CheckoutView(APIView):
    permission_classes = [IsOwner]

    def post(self, request):
        if request.organization.billing_exempt:
            return Response(
                {"error": "This organization is managed by the platform and does not require payment."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        plan = request.data.get("plan", PLAN_STARTER)
        if plan not in (PLAN_STARTER, PLAN_PRO):
            return Response({"error": "Choose starter or pro"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            url = create_checkout_session(
                request.organization,
                plan,
                request.user.email or request.user.username,
            )
        except RuntimeError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"url": url})


class PortalView(APIView):
    permission_classes = [IsOwner]

    def post(self, request):
        try:
            url = create_portal_session(request.organization)
        except RuntimeError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"url": url})


class StripeWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
        payload = request.body
        sig = request.META.get("HTTP_STRIPE_SIGNATURE", "")
        if secret:
            try:
                import stripe

                event = stripe.Webhook.construct_event(payload, sig, secret)
            except Exception:
                return Response({"error": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            event = request.data if isinstance(request.data, dict) else {}
        handle_webhook_event(event if isinstance(event, dict) else event.to_dict())
        return Response({"received": True})
