from __future__ import annotations

from typing import Any

PLAN_FREE = "free"
PLAN_STARTER = "starter"
PLAN_PRO = "pro"

PLAN_LIMITS: dict[str, dict[str, Any]] = {
    PLAN_FREE: {
        "label": "Free",
        "people": 15,
        "cameras": 0,
        "branches": 1,
        "staff": 2,
        "webhooks": False,
        "api_key": False,
        "alerts": False,
        "exports": False,
        "self_service": True,
    },
    PLAN_STARTER: {
        "label": "Starter",
        "people": 75,
        "cameras": 3,
        "branches": 3,
        "staff": 10,
        "webhooks": True,
        "api_key": False,
        "alerts": True,
        "exports": True,
        "self_service": True,
    },
    PLAN_PRO: {
        "label": "Pro",
        "people": 300,
        "cameras": 10,
        "branches": 10,
        "staff": None,
        "webhooks": True,
        "api_key": True,
        "alerts": True,
        "exports": True,
        "self_service": True,
    },
}

TRIAL_DAYS = 14


def get_trial_days() -> int:
    try:
        from organizations.models import PlatformConfig

        cfg = PlatformConfig.objects.filter(pk=1).first()
        if cfg and cfg.trial_days:
            return int(cfg.trial_days)
    except Exception:
        pass
    return TRIAL_DAYS


def limits_for(plan: str) -> dict[str, Any]:
    base = dict(PLAN_LIMITS.get(plan, PLAN_LIMITS[PLAN_FREE]))
    try:
        from organizations.models import PlatformConfig

        cfg = PlatformConfig.objects.filter(pk=1).first()
        overlay = (cfg.plan_limits or {}).get(plan) if cfg else None
        if isinstance(overlay, dict):
            for key in ("label", "people", "cameras", "branches", "staff", "webhooks", "api_key", "alerts", "exports", "self_service"):
                if key in overlay:
                    base[key] = overlay[key]
    except Exception:
        pass
    return base
