"""Notify school/company management when attendance is written."""
from __future__ import annotations

import json
import logging
import threading
from typing import Any

import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


def _serialize_record(record) -> dict[str, Any]:
    return {
        "id": record.id,
        "employee_id": record.employee.employee_id,
        "employee_name": f"{record.employee.first_name} {record.employee.last_name}".strip(),
        "date": record.date.isoformat() if record.date else None,
        "check_in": record.check_in.isoformat() if record.check_in else None,
        "check_out": record.check_out.isoformat() if record.check_out else None,
        "status": record.status,
        "check_in_confidence": record.check_in_confidence,
        "check_out_confidence": record.check_out_confidence,
        "source": record.source,
        "notes": record.notes or "",
        "department": record.employee.department_name,
        "organization_id": getattr(record.employee, "organization_id", None),
    }


def _post(url: str, payload: dict, secret: str) -> None:
    body = json.dumps({"record": payload, "action": payload.get("_action")}).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if secret:
        headers["X-Webhook-Secret"] = secret
        headers["X-API-Key"] = secret
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp.read()
    except urllib.error.URLError as exc:
        logger.warning("Attendance webhook failed: %s", exc)


def notify_school(record, action: str) -> None:
    if action == "ignored":
        return
    org = getattr(record.employee, "organization", None)
    if org is None:
        return
    url = (org.webhook_url or "").strip()
    if not url or not org.has_feature("webhooks"):
        return
    payload = _serialize_record(record)
    payload["_action"] = action
    threading.Thread(
        target=_post,
        args=(url, payload, org.webhook_secret or ""),
        daemon=True,
    ).start()
