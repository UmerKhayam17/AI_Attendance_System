from django.urls import path

from billing.views import BillingSummaryView, CheckoutView, PortalView, StripeWebhookView

urlpatterns = [
    path("", BillingSummaryView.as_view(), name="billing-summary"),
    path("checkout/", CheckoutView.as_view(), name="billing-checkout"),
    path("portal/", PortalView.as_view(), name="billing-portal"),
    path("webhook/", StripeWebhookView.as_view(), name="billing-webhook"),
]
