"""Date-range attendance summaries and file exports."""
from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO

from organizations.localtime import local_date

from attendance.models import AttendanceRecord
from attendance.services.workday import daterange, expected_employees, is_non_working, leave_on
from employees.models import Employee


def _parse_range(from_str: str | None, to_str: str | None, max_days: int = 92, organization=None) -> tuple[date, date]:
    today = local_date(organization=organization)
    end = date.fromisoformat(to_str) if to_str else today
    start = date.fromisoformat(from_str) if from_str else end.replace(day=1)
    if start > end:
        start, end = end, start
    if (end - start).days > max_days:
        start = end - timedelta(days=max_days)
    return start, end


def range_report(org, start: date, end: date, branch_id: int | None = None, with_exceptions: bool = True) -> dict:
    people_qs = Employee.objects.filter(organization=org, is_active=True).select_related("shift", "branch")
    if branch_id:
        people_qs = people_qs.filter(branch_id=branch_id)
    people = list(people_qs)
    records_qs = AttendanceRecord.objects.filter(
        employee__organization=org,
        date__gte=start,
        date__lte=end,
    ).select_related("employee")
    if branch_id:
        records_qs = records_qs.filter(employee__branch_id=branch_id)
    records = list(records_qs)
    by_day: dict[date, list] = {}
    for rec in records:
        by_day.setdefault(rec.date, []).append(rec)

    days = []
    totals = {"present": 0, "late": 0, "absent": 0, "half_day": 0, "on_leave": 0, "overtime_minutes": 0}
    exceptions = []
    report_branch = people[0].branch if branch_id and people else None
    for day in daterange(start, end):
        off, reason = is_non_working(org, day, branch=report_branch)
        day_recs = by_day.get(day, [])
        present = sum(1 for r in day_recs if r.status == AttendanceRecord.STATUS_PRESENT)
        late = sum(1 for r in day_recs if r.status == AttendanceRecord.STATUS_LATE)
        half = sum(1 for r in day_recs if r.status == AttendanceRecord.STATUS_HALF_DAY)
        leave_n = 0
        absent_n = 0
        ot = sum(r.overtime_minutes or 0 for r in day_recs)
        if not off:
            expected = expected_employees(org, day, people)
            punched = {r.employee_id for r in day_recs if r.status != AttendanceRecord.STATUS_ON_LEAVE}
            for emp in people:
                if leave_on(emp, day):
                    leave_n += 1
            for emp in expected:
                if emp.id not in punched:
                    absent_n += 1
                    if with_exceptions:
                        exceptions.append({
                            "date": str(day),
                            "employee_id": emp.employee_id,
                            "name": emp.display_name,
                            "kind": "absent",
                        })
            if with_exceptions:
                for rec in day_recs:
                    if rec.status == AttendanceRecord.STATUS_LATE:
                        exceptions.append({
                            "date": str(day),
                            "employee_id": rec.employee.employee_id,
                            "name": rec.employee.display_name,
                            "kind": "late",
                        })
                    if rec.early_leave:
                        exceptions.append({
                            "date": str(day),
                            "employee_id": rec.employee.employee_id,
                            "name": rec.employee.display_name,
                            "kind": "early_leave",
                        })
                    if rec.overtime_minutes:
                        exceptions.append({
                            "date": str(day),
                            "employee_id": rec.employee.employee_id,
                            "name": rec.employee.display_name,
                            "kind": "overtime",
                            "minutes": rec.overtime_minutes,
                        })
        days.append({
            "date": str(day),
            "is_workday": not off,
            "reason": reason,
            "present": present,
            "late": late,
            "half_day": half,
            "on_leave": leave_n,
            "absent": absent_n,
            "overtime_minutes": ot,
        })
        totals["present"] += present
        totals["late"] += late
        totals["half_day"] += half
        totals["on_leave"] += leave_n
        totals["absent"] += absent_n
        totals["overtime_minutes"] += ot

    return {
        "from": str(start),
        "to": str(end),
        "days": days,
        "totals": totals,
        "exceptions": exceptions[:400],
        "people_count": len(people),
    }


DASHBOARD_MAX_DAYS = 366


def parse_dashboard_span(
    from_str: str | None,
    to_str: str | None,
    organization=None,
    branch=None,
) -> tuple[date, date]:
    today = local_date(organization=organization, branch=branch)
    try:
        end = date.fromisoformat(to_str) if to_str else today
    except ValueError:
        end = today
    try:
        start = date.fromisoformat(from_str) if from_str else end
    except ValueError:
        start = end
    if start > end:
        start, end = end, start
    if end > today:
        end = today
    if start > end:
        start = end
    if (end - start).days > DASHBOARD_MAX_DAYS:
        start = end - timedelta(days=DASHBOARD_MAX_DAYS)
    return start, end


def dashboard_charts(org, start: date, end: date, branch_id: int | None = None) -> dict:
    """Attendance + AI series for the selected dashboard range."""
    from collections import defaultdict

    from django.db.models import Count
    from django.db.models.functions import ExtractHour

    from recognition.models import RecognitionEvent

    span = range_report(org, start, end, branch_id=branch_id, with_exceptions=False)
    trend_start = start if start < end else end - timedelta(days=27)
    if trend_start < start:
        trend = range_report(org, trend_start, end, branch_id=branch_id, with_exceptions=False)
        trend_days = trend["days"]
    else:
        trend_days = span["days"]
    records_qs = AttendanceRecord.objects.filter(
        employee__organization=org,
        date__gte=start,
        date__lte=end,
    )
    ai_start = start if start < end else end - timedelta(days=6)
    events_qs = RecognitionEvent.objects.filter(
        organization=org,
        detected_at__date__gte=ai_start,
        detected_at__date__lte=end,
    )
    if branch_id:
        records_qs = records_qs.filter(employee__branch_id=branch_id)
        events_qs = events_qs.filter(camera__branch_id=branch_id)

    hourly_counts = {hour: 0 for hour in range(24)}
    for row in (
        records_qs.filter(check_in__isnull=False)
        .annotate(hour=ExtractHour("check_in"))
        .values("hour")
        .annotate(n=Count("id"))
    ):
        hour = row["hour"]
        if hour is not None:
            hourly_counts[int(hour)] = row["n"]

    sources = [
        {"source": row["source"] or "unknown", "count": row["n"]}
        for row in records_qs.values("source").annotate(n=Count("id")).order_by("-n")
    ]

    from django.db.models.functions import Coalesce
    from django.db.models import Value, Q

    branches = [
        {
            "branch": row["branch_name"],
            "total": row["total"],
            "present_count": row["present_count"],
            "late_count": row["late_count"],
        }
        for row in (
            records_qs.annotate(branch_name=Coalesce("employee__branch__name", Value("Unassigned")))
            .values("branch_name")
            .annotate(
                total=Count("id"),
                present_count=Count("id", filter=Q(status=AttendanceRecord.STATUS_PRESENT)),
                late_count=Count("id", filter=Q(status=AttendanceRecord.STATUS_LATE)),
            )
            .order_by("branch_name")
        )
    ]

    ai_by_day: dict[str, dict[str, int]] = defaultdict(lambda: {"recognized": 0, "unknown": 0, "spoof": 0, "anomaly": 0})
    for row in events_qs.values("detected_at__date", "kind").annotate(n=Count("id")):
        day = str(row["detected_at__date"])
        kind = row["kind"]
        if kind in ai_by_day[day]:
            ai_by_day[day][kind] = row["n"]
    ai_trend = []
    cursor = ai_start
    while cursor <= end:
        key = str(cursor)
        ai_trend.append({"date": key, **ai_by_day[key]})
        cursor += timedelta(days=1)

    return {
        "from": str(start),
        "to": str(end),
        "totals": span["totals"],
        "trend": trend_days,
        "hourly": [{"hour": hour, "count": hourly_counts[hour]} for hour in range(24)],
        "sources": sources,
        "branches": branches,
        "ai_trend": ai_trend,
    }


def hr_report(org, start: date, end: date, branch_id: int | None = None) -> dict:
    from collections import Counter

    from attendance.models import LeaveRequest, OvertimeRequest
    from exits.models import ExitCase

    people_qs = Employee.objects.filter(organization=org).select_related("department", "branch")
    if branch_id:
        people_qs = people_qs.filter(branch_id=branch_id)
    people = list(people_qs)
    active = [p for p in people if p.is_active]
    by_branch = Counter((p.branch_name or "Unassigned") for p in active)
    by_dept = Counter((p.department_name or "Unassigned") for p in active)
    by_type = Counter((p.employment_type or "full_time") for p in active)
    joiners = [
        {
            "employee_id": p.employee_id,
            "name": p.display_name,
            "joining_date": str(p.joining_date),
            "branch": p.branch_name,
        }
        for p in people
        if p.joining_date and start <= p.joining_date <= end
    ]
    leaves = LeaveRequest.objects.filter(
        employee__in=people,
        status=LeaveRequest.STATUS_APPROVED,
        start_date__lte=end,
        end_date__gte=start,
    )
    leave_by_type = Counter(row.leave_type for row in leaves)
    ot_minutes = 0
    records = AttendanceRecord.objects.filter(
        employee__in=people,
        date__gte=start,
        date__lte=end,
    )
    for rec in records:
        ot_minutes += rec.overtime_minutes or 0
    approved_ot = OvertimeRequest.objects.filter(
        employee__in=people,
        date__gte=start,
        date__lte=end,
        status=OvertimeRequest.STATUS_APPROVED,
    )
    exits = ExitCase.objects.filter(
        employee__in=people,
        status=ExitCase.STATUS_COMPLETED,
        completed_at__isnull=False,
        last_working_day__gte=start,
        last_working_day__lte=end,
    )
    return {
        "from": str(start),
        "to": str(end),
        "headcount": {
            "active": len(active),
            "total": len(people),
            "by_branch": dict(by_branch),
            "by_department": dict(by_dept),
            "by_employment_type": dict(by_type),
        },
        "joiners": joiners,
        "leave_utilization": dict(leave_by_type),
        "overtime_minutes": ot_minutes,
        "approved_overtime_minutes": sum(row.minutes for row in approved_ot),
        "exits": [
            {
                "employee_id": case.employee.employee_id,
                "name": case.employee.display_name,
                "exit_type": case.exit_type,
                "last_working_day": str(case.last_working_day),
            }
            for case in exits.select_related("employee")
        ],
    }


def export_rows(org, start: date, end: date, branch_id: int | None = None) -> list[dict]:
    people_qs = Employee.objects.filter(organization=org, is_active=True)
    records_qs = AttendanceRecord.objects.filter(
        employee__organization=org,
        date__gte=start,
        date__lte=end,
    ).select_related("employee")
    if branch_id:
        people_qs = people_qs.filter(branch_id=branch_id)
        records_qs = records_qs.filter(employee__branch_id=branch_id)
    people = {e.id: e for e in people_qs}
    records = {(r.employee_id, r.date): r for r in records_qs}
    rows = []
    for day in daterange(start, end):
        for emp in people.values():
            rec = records.get((emp.id, day))
            off, reason = is_non_working(org, day, branch=getattr(emp, "branch", None))
            if off:
                status = reason or "Off"
            elif rec:
                status = rec.status
            elif leave_on(emp, day):
                status = "on_leave"
            else:
                status = "absent"
            rows.append({
                "date": str(day),
                "employee_id": emp.employee_id,
                "name": emp.display_name,
                "department": emp.department_name,
                "status": status,
                "check_in": rec.check_in.isoformat() if rec and rec.check_in else "",
                "check_out": rec.check_out.isoformat() if rec and rec.check_out else "",
                "overtime_minutes": rec.overtime_minutes if rec else 0,
                "early_leave": bool(rec.early_leave) if rec else False,
            })
    return rows


def as_csv(rows: list[dict]) -> bytes:
    import csv
    from io import StringIO

    fieldnames = ["date", "employee_id", "name", "department", "status", "check_in", "check_out", "overtime_minutes", "early_leave"]
    out = StringIO()
    writer = csv.DictWriter(out, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode("utf-8-sig")


def as_xlsx(rows: list[dict]) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance"
    headers = ["Date", "ID", "Name", "Department", "Status", "Check in", "Check out", "Overtime (min)", "Early leave"]
    ws.append(headers)
    for row in rows:
        ws.append([
            row["date"],
            row["employee_id"],
            row["name"],
            row["department"],
            row["status"],
            row["check_in"],
            row["check_out"],
            row["overtime_minutes"],
            "yes" if row["early_leave"] else "",
        ])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def as_pdf(org_name: str, start: date, end: date, summary: dict, rows: list[dict]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"{org_name} — attendance {start} to {end}", styles["Title"]),
        Paragraph(
            f"Present {summary['present']} · Late {summary['late']} · Absent {summary['absent']} · "
            f"Leave {summary['on_leave']} · Half day {summary['half_day']}",
            styles["Normal"],
        ),
        Spacer(1, 12),
    ]
    data = [["Date", "ID", "Name", "Dept", "Status", "In", "Out"]]
    for row in rows[:500]:
        data.append([
            row["date"],
            row["employee_id"],
            row["name"],
            row["department"],
            row["status"],
            (row["check_in"] or "")[11:16],
            (row["check_out"] or "")[11:16],
        ])
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
    ]))
    story.append(table)
    doc.build(story)
    return buf.getvalue()


def recognition_report(org, start: date, end: date, branch_id: int | None = None) -> dict:
    from django.db.models import Count, Q
    from recognition.models import RecognitionEvent

    qs = RecognitionEvent.objects.filter(
        organization=org,
        detected_at__date__gte=start,
        detected_at__date__lte=end,
    )
    if branch_id:
        qs = qs.filter(camera__branch_id=branch_id)
    by_kind = {row["kind"]: row["n"] for row in qs.values("kind").annotate(n=Count("id"))}
    days = []
    cursor = start
    while cursor <= end:
        day_qs = qs.filter(detected_at__date=cursor)
        days.append({
            "date": str(cursor),
            "recognized": day_qs.filter(kind=RecognitionEvent.KIND_RECOGNIZED).count(),
            "unknown": day_qs.filter(kind=RecognitionEvent.KIND_UNKNOWN).count(),
            "spoof": day_qs.filter(kind=RecognitionEvent.KIND_SPOOF).count(),
            "anomaly": day_qs.filter(kind=RecognitionEvent.KIND_ANOMALY).count(),
        })
        cursor += timedelta(days=1)
    cameras = list(
        qs.exclude(camera_name="")
        .values("camera_name")
        .annotate(
            recognized=Count("id", filter=Q(kind=RecognitionEvent.KIND_RECOGNIZED)),
            unknown=Count("id", filter=Q(kind=RecognitionEvent.KIND_UNKNOWN)),
            spoof=Count("id", filter=Q(kind=RecognitionEvent.KIND_SPOOF)),
        )
        .order_by("-recognized")[:20]
    )
    return {
        "from": str(start),
        "to": str(end),
        "totals": {
            "recognized": by_kind.get(RecognitionEvent.KIND_RECOGNIZED, 0),
            "unknown": by_kind.get(RecognitionEvent.KIND_UNKNOWN, 0),
            "spoof": by_kind.get(RecognitionEvent.KIND_SPOOF, 0),
            "review": by_kind.get(RecognitionEvent.KIND_REVIEW, 0),
            "anomaly": by_kind.get(RecognitionEvent.KIND_ANOMALY, 0),
            "camera": by_kind.get(RecognitionEvent.KIND_CAMERA, 0),
        },
        "days": days,
        "cameras": cameras,
    }
