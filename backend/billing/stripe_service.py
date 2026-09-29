import logging
from datetime import datetime, timezone as dt_timezone

from django.conf import settings

from organizations.models import Organization
from organizations.plans import PLAN_FREE, PLAN_PRO, PLAN_STARTER

logger = logging.getLogger(__name__)


def _stripe():
    if not getattr(settings, "STRIPE_SECRET_KEY", ""):
        return None
    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def plan_from_price_id(price_id: str) -> str:
    if price_id and price_id == getattr(settings, "STRIPE_PRICE_PRO", ""):
        return PLAN_PRO
    if price_id and price_id == getattr(settings, "STRIPE_PRICE_STARTER", ""):
        return PLAN_STARTER
    return PLAN_STARTER


def ensure_customer(organization: Organization, email: str, name: str) -> str:
    stripe = _stripe()
    if organization.stripe_customer_id:
        return organization.stripe_customer_id
    if stripe is None:
        raise RuntimeError("Stripe is not configured")
    customer = stripe.Customer.create(
        email=email,
        name=name or organization.name,
        metadata={"org_id": str(organization.id), "org_slug": organization.slug},
    )
    organization.stripe_customer_id = customer.id
    organization.save(update_fields=["stripe_customer_id", "updated_at"])
    return customer.id


def create_checkout_session(organization: Organization, plan: str, email: str) -> str:
    stripe = _stripe()
    if stripe is None:
        raise RuntimeError("Stripe is not configured")

    price_id = {
        PLAN_STARTER: getattr(settings, "STRIPE_PRICE_STARTER", ""),
        PLAN_PRO: getattr(settings, "STRIPE_PRICE_PRO", ""),
    }.get(plan)
    if not price_id:
        raise RuntimeError(f"No Stripe price configured for plan '{plan}'")

    customer_id = ensure_customer(organization, email, organization.name)
    frontend = getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")
    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{frontend}/settings/billing?checkout=success",
        cancel_url=f"{frontend}/settings/billing?checkout=canceled",
        metadata={"org_id": str(organization.id), "plan": plan},
        subscription_data={"metadata": {"org_id": str(organization.id), "plan": plan}},
        allow_promotion_codes=True,
    )
    return session.url


def create_portal_session(organization: Organization) -> str:
    stripe = _stripe()
    if stripe is None:
        raise RuntimeError("Stripe is not configured")
    if not organization.stripe_customer_id:
        raise RuntimeError("No Stripe customer on this organization")
    frontend = getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")
    session = stripe.billing_portal.Session.create(
        customer=organization.stripe_customer_id,
        return_url=f"{frontend}/settings/billing",
    )
    return session.url


def _ts_to_datetime(value):
    if not value:
        return None
    return datetime.fromtimestamp(int(value), tz=dt_timezone.utc)


def apply_subscription(organization: Organization, subscription: dict, plan: str | None = None):
    status = subscription.get("status") or Organization.STATUS_ACTIVE
    price_id = ""
    items = (subscription.get("items") or {}).get("data") or []
    if items:
        price_id = (items[0].get("price") or {}).get("id") or ""
    resolved_plan = plan or plan_from_price_id(price_id)

    organization.stripe_subscription_id = subscription.get("id") or organization.stripe_subscription_id
    organization.subscription_status = status
    if status in ("active", "trialing"):
        organization.plan = resolved_plan
    elif status in ("canceled", "unpaid", "incomplete_expired"):
        organization.plan = PLAN_FREE
        organization.subscription_status = Organization.STATUS_CANCELED
    organization.current_period_end = _ts_to_datetime(subscription.get("current_period_end"))
    organization.save(
        update_fields=[
            "stripe_subscription_id",
            "subscription_status",
            "plan",
            "current_period_end",
            "updated_at",
        ]
    )


def handle_webhook_event(event: dict):
    etype = event.get("type")
    data = (event.get("data") or {}).get("object") or {}

    org = None
    org_id = (data.get("metadata") or {}).get("org_id")
    if org_id:
        org = Organization.objects.filter(pk=org_id).first()
    if org is None and data.get("customer"):
        org = Organization.objects.filter(stripe_customer_id=data["customer"]).first()
    if org is None:
        logger.warning("Stripe webhook %s: organization not found", etype)
        return

    if etype == "checkout.session.completed":
        plan = (data.get("metadata") or {}).get("plan")
        sub_id = data.get("subscription")
        if sub_id:
            stripe = _stripe()
            subscription = stripe.Subscription.retrieve(sub_id) if stripe else {"id": sub_id, "status": "active"}
            if hasattr(subscription, "to_dict"):
                subscription = subscription.to_dict()
            apply_subscription(org, subscription, plan=plan)
        else:
            org.plan = plan or PLAN_STARTER
            org.subscription_status = Organization.STATUS_ACTIVE
            org.save(update_fields=["plan", "subscription_status", "updated_at"])
        return

    if etype in ("customer.subscription.updated", "customer.subscription.created"):
        apply_subscription(org, data)
        return

    if etype == "customer.subscription.deleted":
        org.plan = PLAN_FREE
        org.subscription_status = Organization.STATUS_CANCELED
        org.stripe_subscription_id = ""
        org.save(update_fields=["plan", "subscription_status", "stripe_subscription_id", "updated_at"])
        return

    if etype == "invoice.payment_failed":
        org.subscription_status = Organization.STATUS_PAST_DUE
        org.save(update_fields=["subscription_status", "updated_at"])
