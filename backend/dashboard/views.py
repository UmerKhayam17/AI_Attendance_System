from django.db.models import Count, Q, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from attendance.models import AttendanceRecord
from attendance.serializers import AttendanceRecordSerializer
from attendance.services.workday import expected_employees, holiday_on, is_non_working, leave_on
from employees.models import Employee
from organizations.localtime import local_date
from organizations.permissions import CanView
from organizations.query import parse_branch_id
from recognition.models import FaceEnrollment, MatchReview, RecognitionEvent
from recognition.services.camera_health import camera_health_summary
from recognition.services.cctv_worker import get_cctv_manager
from visitors.models import Visit
from dashboard.reports import dashboard_charts, parse_dashboard_span


def _branch_scope(request):
    org = request.organization
    branch_id = parse_branch_id(request)
    branch = None
    if branch_id:
        branch = org.branches.filter(pk=branch_id).first()
    people = Employee.objects.filter(organization=org, is_active=True).select_related(
        "department", "branch", "shift"
    )
    if branch:
        people = people.filter(branch=branch)
    today = local_date(organization=org, branch=branch)
    return org, branch, people, today


class DashboardSummaryView(APIView):
    permission_classes = [CanView]

    def get(self, request):
        org, branch, employees, today = _branch_scope(request)
        start, end = parse_dashboard_span(
            request.query_params.get("from"),
            request.query_params.get("to"),
            organization=org,
            branch=branch,
        )
        single = start == end
        total_employees = employees.count()
        trained_qs = FaceEnrollment.objects.filter(
            is_trained=True,
            employee__organization=org,
        )
        if branch:
            trained_qs = trained_qs.filter(employee__branch=branch)
        trained_faces = trained_qs.count()
        records = AttendanceRecord.objects.filter(
            date__gte=start,
            date__lte=end,
            employee__in=employees,
        ).select_related("employee")
        branch_id = branch.id if branch else None
        charts = dashboard_charts(org, start, end, branch_id=branch_id)

        if single:
            off, off_reason = is_non_working(org, start, branch=branch)
            expected = expected_employees(org, start, employees)
            expected_ids = {e.id for e in expected}
            present_ids = set(
                records.exclude(status=AttendanceRecord.STATUS_ON_LEAVE)
                .values_list("employee_id", flat=True)
            )
            present = records.filter(
                Q(status=AttendanceRecord.STATUS_PRESENT) | Q(status=AttendanceRecord.STATUS_LATE)
            ).count()
            late = records.filter(status=AttendanceRecord.STATUS_LATE).count()
            half_day = records.filter(status=AttendanceRecord.STATUS_HALF_DAY).count()
            on_leave = records.filter(status=AttendanceRecord.STATUS_ON_LEAVE).count()
            absent = 0 if off else max(len(expected_ids - present_ids), 0)
            workday = {"is_workday": not off, "reason": off_reason}
        else:
            totals = charts.get("totals") or {}
            present = (totals.get("present") or 0) + (totals.get("late") or 0)
            late = totals.get("late") or 0
            half_day = totals.get("half_day") or 0
            on_leave = totals.get("on_leave") or 0
            absent = totals.get("absent") or 0
            workday = None
        checked_out = records.filter(check_out__isnull=False).count()
        review_pending = MatchReview.objects.filter(
            organization=org,
            status=MatchReview.STATUS_PENDING,
        ).count()
        events = RecognitionEvent.objects.filter(
            organization=org,
            detected_at__date__gte=start,
            detected_at__date__lte=end,
        )
        if branch:
            events = events.filter(camera__branch=branch)
        unknown_today = events.filter(kind=RecognitionEvent.KIND_UNKNOWN).count()
        spoof_today = events.filter(kind=RecognitionEvent.KIND_SPOOF).count()
        recognized_today = events.filter(kind=RecognitionEvent.KIND_RECOGNIZED).count()
        anomaly_open = RecognitionEvent.objects.filter(
            organization=org,
            kind=RecognitionEvent.KIND_ANOMALY,
            status=RecognitionEvent.STATUS_OPEN,
        ).count()
        runtime_by_id = {}
        try:
            manager = get_cctv_manager()
            for item in manager.list_status():
                if item.get("organization_id") == org.id:
                    runtime_by_id[item["camera_id"]] = item
        except Exception:
            runtime_by_id = {}
        cameras = camera_health_summary(org, runtime_by_id)
        visit_qs = Visit.objects.filter(organization=org)
        if branch:
            visit_qs = visit_qs.filter(branch=branch)
        visitors_on_site = visit_qs.filter(status=Visit.STATUS_CHECKED_IN).count()
        visitors_expected = visit_qs.filter(
            status=Visit.STATUS_EXPECTED,
            expected_at__date__gte=start,
            expected_at__date__lte=end,
        ).count()

        department_stats = [
            {
                "department": row["dept_name"],
                "total": row["total"],
                "present_count": row["present_count"],
                "late_count": row["late_count"],
            }
            for row in (
                records.annotate(
                    dept_name=Coalesce("employee__department__name", Value("Unassigned")),
                )
                .values("dept_name")
                .annotate(
                    total=Count("id"),
                    present_count=Count("id", filter=Q(status=AttendanceRecord.STATUS_PRESENT)),
                    late_count=Count("id", filter=Q(status=AttendanceRecord.STATUS_LATE)),
                )
                .order_by("dept_name")
            )
        ]

        recent = AttendanceRecord.objects.filter(
            employee__in=employees,
            date__gte=start,
            date__lte=end,
        ).select_related("employee").order_by("-check_in", "-created_at")[:10]

        return Response({
            "date": str(today),
            "from": str(start),
            "to": str(end),
            "summary": {
                "total_employees": total_employees,
                "trained_faces": trained_faces,
                "present_today": present,
                "late_today": late,
                "absent_today": absent,
                "checked_out_today": checked_out,
                "half_day_today": half_day,
                "on_leave_today": on_leave,
                "review_pending": review_pending,
                "unknown_today": unknown_today,
                "spoof_today": spoof_today,
                "recognized_today": recognized_today,
                "anomaly_open": anomaly_open,
                "cameras": cameras,
                "visitors_on_site": visitors_on_site,
                "visitors_expected": visitors_expected,
            },
            "workday": workday,
            "department_stats": department_stats,
            "charts": charts,
            "recent_activity": AttendanceRecordSerializer(recent, many=True).data,
        })


class DailyReportView(APIView):
    permission_classes = [CanView]

    def get(self, request):
        org, branch, active_employees, today = _branch_scope(request)
        date_str = request.query_params.get("date")
        if date_str:
            from datetime import datetime
            report_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            report_date = today

        records = AttendanceRecord.objects.filter(
            date=report_date,
            employee__in=active_employees,
        ).select_related("employee")
        off, off_reason = is_non_working(org, report_date, branch=branch)
        hol = holiday_on(org, report_date, branch=branch)
        present_ids = set(
            records.exclude(status=AttendanceRecord.STATUS_ON_LEAVE).values_list("employee_id", flat=True)
        )

        on_leave_list = []
        absent_list = []
        if not off:
            for emp in active_employees:
                leave = leave_on(emp, report_date)
                if leave:
                    on_leave_list.append({
                        "employee_id": emp.employee_id,
                        "name": f"{emp.first_name} {emp.last_name}".strip(),
                        "department": emp.department_name,
                        "leave_type": leave.leave_type,
                    })
                    continue
                if emp.id not in present_ids:
                    absent_list.append({
                        "employee_id": emp.employee_id,
                        "name": f"{emp.first_name} {emp.last_name}".strip(),
                        "department": emp.department_name,
                    })

        return Response({
            "date": str(report_date),
            "workday": {"is_workday": not off, "reason": off_reason, "holiday": hol.name if hol else None},
            "attendance": AttendanceRecordSerializer(records, many=True).data,
            "absent": absent_list,
            "on_leave": on_leave_list,
            "totals": {
                "present": records.filter(status=AttendanceRecord.STATUS_PRESENT).count(),
                "late": records.filter(status=AttendanceRecord.STATUS_LATE).count(),
                "half_day": records.filter(status=AttendanceRecord.STATUS_HALF_DAY).count(),
                "absent": len(absent_list),
                "on_leave": len(on_leave_list),
            },
        })


class RangeReportView(APIView):
    permission_classes = [CanView]

    def get(self, request):
        from dashboard.reports import _parse_range, range_report

        start, end = _parse_range(
            request.query_params.get("from"),
            request.query_params.get("to"),
            organization=request.organization,
        )
        branch_id = parse_branch_id(request)
        return Response(range_report(request.organization, start, end, branch_id=branch_id))


class HrReportView(APIView):
    permission_classes = [CanView]

    def get(self, request):
        from dashboard.reports import _parse_range, hr_report

        start, end = _parse_range(
            request.query_params.get("from"),
            request.query_params.get("to"),
            organization=request.organization,
        )
        branch_id = parse_branch_id(request)
        return Response(hr_report(request.organization, start, end, branch_id=branch_id))


class RecognitionReportView(APIView):
    permission_classes = [CanView]

    def get(self, request):
        from dashboard.reports import _parse_range, recognition_report

        start, end = _parse_range(
            request.query_params.get("from"),
            request.query_params.get("to"),
            organization=request.organization,
        )
        branch_id = parse_branch_id(request)
        return Response(recognition_report(request.organization, start, end, branch_id=branch_id))


class ExportReportView(APIView):
    permission_classes = [CanView]

    def get(self, request):
        from dashboard.reports import _parse_range, as_csv, as_pdf, as_xlsx, export_rows, range_report

        fmt = (request.query_params.get("format") or "xlsx").lower()
        if fmt not in ("xlsx", "csv", "pdf"):
            return Response({"error": "format must be xlsx, csv, or pdf"}, status=400)
        if fmt == "pdf" and not request.organization.limits().get("exports"):
            return Response({"error": "Excel/PDF export requires Starter or Pro"}, status=403)
        if fmt == "xlsx" and not request.organization.limits().get("exports"):
            return Response({"error": "Excel/PDF export requires Starter or Pro"}, status=403)
        start, end = _parse_range(
            request.query_params.get("from"),
            request.query_params.get("to"),
            organization=request.organization,
        )
        branch_id = parse_branch_id(request)
        rows = export_rows(request.organization, start, end, branch_id=branch_id)
        summary = range_report(request.organization, start, end, branch_id=branch_id)["totals"]
        name = f"attendance_{start}_{end}"
        if fmt == "csv":
            payload = as_csv(rows)
            resp = HttpResponse(payload, content_type="text/csv")
            resp["Content-Disposition"] = f'attachment; filename="{name}.csv"'
            return resp
        if fmt == "pdf":
            payload = as_pdf(request.organization.name, start, end, summary, rows)
            resp = HttpResponse(payload, content_type="application/pdf")
            resp["Content-Disposition"] = f'attachment; filename="{name}.pdf"'
            return resp
        payload = as_xlsx(rows)
        resp = HttpResponse(
            payload,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        resp["Content-Disposition"] = f'attachment; filename="{name}.xlsx"'
        return resp

