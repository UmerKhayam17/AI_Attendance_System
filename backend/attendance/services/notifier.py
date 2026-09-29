"""Route late/absent alerts to email, SMS, WhatsApp, and webhooks."""
from __future__ import annotations

import logging
import threading
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError
from base64 import b64encode

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError
from django.utils import timezone

from attendance.models import NotificationLog
from attendance.services.school_webhook import notify_school

logger = logging.getLogger(__name__)


def _twilio_creds(org):
    sid = (org.twilio_account_sid or "").strip() or getattr(settings, "TWILIO_ACCOUNT_SID", "")
    token = (org.twilio_auth_token or "").strip() or getattr(settings, "TWILIO_AUTH_TOKEN", "")
    sms_from = (org.twilio_from_number or "").strip() or getattr(settings, "TWILIO_FROM_NUMBER", "")
    wa_from = (org.twilio_whatsapp_from or "").strip() or getattr(settings, "TWILIO_WHATSAPP_FROM", "")
    return sid, token, sms_from, wa_from


def _digits(phone: str) -> str:
    raw = (phone or "").strip()
    if not raw:
        return ""
    keep = "".join(ch for ch in raw if ch.isdigit() or ch == "+")
    if keep and not keep.startswith("+"):
        keep = "+" + keep
    return keep


def _twilio_send(sid: str, token: str, from_n: str, to_n: str, body: str) -> bool:
    if not sid or not token or not from_n or not to_n:
        return False
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    data = urlencode({"From": from_n, "To": to_n, "Body": body}).encode("utf-8")
    auth = b64encode(f"{sid}:{token}".encode()).decode()
    req = Request(url, data=data, method="POST", headers={
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/x-www-form-urlencoded",
    })
    try:
        with urlopen(req, timeout=8) as resp:
            resp.read()
        return True
    except URLError as exc:
        logger.warning("Twilio send failed: %s", exc)
        return False


def _already_sent(employee, day, kind, channel) -> bool:
    return NotificationLog.objects.filter(
        employee=employee, date=day, kind=kind, channel=channel
    ).exists()


def _log(org, employee, day, kind, channel, recipient, message):
    try:
        NotificationLog.objects.create(
            organization=org,
            employee=employee,
            date=day,
            kind=kind,
            channel=channel,
            recipient=recipient or "",
            message=message,
        )
        return True
    except IntegrityError:
        return False


def _recipients(employee):
    emails = []
    phones = []
    for value in (employee.email, employee.guardian_email):
        v = (value or "").strip()
        if v and v not in emails:
            emails.append(v)
    for link in employee.parent_links.select_related("user").all():
        mail = (link.user.email or link.user.username or "").strip()
        if mail and "@" in mail and mail not in emails:
            emails.append(mail)
    for value in (employee.phone, employee.guardian_phone):
        digits = _digits(value)
        if digits and digits not in phones:
            phones.append(digits)
    return emails, phones


def notify_event(employee, kind: str, *, record=None, message: str = "") -> int:
    org = getattr(employee, "organization", None)
    if org is None:
        return 0
    day = timezone.localdate(getattr(record, "check_in", None) or timezone.now())
    if record is not None and record.date:
        day = record.date
    if kind == NotificationLog.KIND_LATE and not org.notify_late:
        return 0
    if kind == NotificationLog.KIND_ABSENT and not org.notify_absent:
        return 0

    name = employee.display_name
    if not message:
        if kind == NotificationLog.KIND_LATE:
            when = ""
            if record and record.check_in:
                when = timezone.localtime(record.check_in).strftime("%H:%M")
            message = f"{name} checked in late{f' at {when}' if when else ''}."
        else:
            message = f"{name} has not arrived after the late time."

    sent = 0
    emails, phones = _recipients(employee)
    can_sms = org.notify_sms and (org.has_feature("alerts") or org.has_feature("webhooks"))
    can_wa = org.notify_whatsapp and (org.has_feature("alerts") or org.has_feature("webhooks"))
    sid, token, sms_from, wa_from = _twilio_creds(org)

    if org.notify_email and emails and not _already_sent(employee, day, kind, NotificationLog.CHANNEL_EMAIL):
        try:
            send_mail(
                subject=f"Attendance: {name} ({kind})",
                message=message,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@localhost"),
                recipient_list=emails,
                fail_silently=True,
            )
            if _log(org, employee, day, kind, NotificationLog.CHANNEL_EMAIL, ", ".join(emails), message):
                sent += 1
        except Exception:
            logger.exception("Email alert failed")

    if can_sms and phones and sid:
        for phone in phones:
            if _already_sent(employee, day, kind, NotificationLog.CHANNEL_SMS):
                break
            if _twilio_send(sid, token, sms_from, phone, message):
                if _log(org, employee, day, kind, NotificationLog.CHANNEL_SMS, phone, message):
                    sent += 1
                break

    if can_wa and phones and sid and wa_from:
        to_wa = phones[0]
        wa_to = to_wa if to_wa.startswith("whatsapp:") else f"whatsapp:{to_wa}"
        wa_from_n = wa_from if wa_from.startswith("whatsapp:") else f"whatsapp:{wa_from}"
        if not _already_sent(employee, day, kind, NotificationLog.CHANNEL_WHATSAPP):
            if _twilio_send(sid, token, wa_from_n, wa_to, message):
                if _log(org, employee, day, kind, NotificationLog.CHANNEL_WHATSAPP, wa_to, message):
                    sent += 1

    if org.webhook_url and org.has_feature("webhooks") and record is not None:
        if not _already_sent(employee, day, kind, NotificationLog.CHANNEL_WEBHOOK):
            action = "late_alert" if kind == NotificationLog.KIND_LATE else "absent_alert"
            notify_school(record, action)
            if _log(org, employee, day, kind, NotificationLog.CHANNEL_WEBHOOK, org.webhook_url, message):
                sent += 1

    return sent


def notify_event_async(employee_id: int, kind: str, record_id: int | None = None):
    def _run():
        from attendance.models import AttendanceRecord
        from employees.models import Employee

        emp = Employee.objects.select_related("organization").filter(pk=employee_id).first()
        if not emp:
            return
        record = None
        if record_id:
            record = AttendanceRecord.objects.select_related("employee__organization").filter(pk=record_id).first()
        notify_event(emp, kind, record=record)

    threading.Thread(target=_run, name="attendance-alert", daemon=True).start()
