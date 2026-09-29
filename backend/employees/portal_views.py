from datetime import datetime, timedelta
from io import BytesIO

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from attendance.models import AttendanceRecord, LeaveRequest
from attendance.serializers import LeaveRequestSerializer
from attendance.services.workday import holiday_on, is_non_working, leave_on
from employees.access import portal_employees_qs
from employees.models import Employee
from organizations.permissions import IsPortalUser
from organizations.shifts import schedule_for


def _person_status(employee, day):
    off, reason = is_non_working(employee.organization, day)
    record = (
        AttendanceRecord.objects.filter(employee=employee, date=day)
        .select_related("employee")
        .first()
    )
    leave = leave_on(employee, day)
    hol = holiday_on(employee.organization, day)
    schedule = schedule_for(employee=employee, organization=employee.organization)
    if off:
        status = "holiday" if hol else "weekend"
    elif leave:
        status = "on_leave"
    elif record is None:
        status = "absent"
    else:
        status = record.status
    return {
        "employee_id": employee.employee_id,
        "employee_pk": employee.id,
        "name": employee.display_name,
        "department": employee.department_name,
        "designation": employee.designation,
        "status": status,
        "workday": {"is_workday": not off, "reason": reason},
        "shift": {
            "name": getattr(employee.shift, "name", None) or "Default",
            "start_time": schedule.start_time.strftime("%H:%M"),
            "late_after": schedule.late_after.strftime("%H:%M"),
            "end_time": schedule.end_time.strftime("%H:%M"),
        },
        "check_in": record.check_in.isoformat() if record and record.check_in else None,
        "check_out": record.check_out.isoformat() if record and record.check_out else None,
        "early_leave": bool(record.early_leave) if record else False,
        "overtime_minutes": record.overtime_minutes if record else 0,
        "notes": record.notes if record else "",
        "leave_type": leave.leave_type if leave else None,
    }


class PortalStatusView(APIView):
    permission_classes = [IsAuthenticated, IsPortalUser]

    def get(self, request):
        date_str = request.query_params.get("date")
        if date_str:
            day = datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            day = timezone.localdate()
        people = list(
            portal_employees_qs(request.user, request.organization, request.role).select_related(
                "shift", "organization"
            )
        )
        recent = []
        if people:
            start = day - timedelta(days=6)
            recs = AttendanceRecord.objects.filter(
                employee__in=people,
                date__gte=start,
                date__lte=day,
            ).select_related("employee")
            by_emp = {}
            for rec in recs:
                by_emp.setdefault(rec.employee_id, []).append({
                    "date": rec.date.isoformat(),
                    "status": rec.status,
                    "check_in": rec.check_in.isoformat() if rec.check_in else None,
                    "check_out": rec.check_out.isoformat() if rec.check_out else None,
                })
            recent = [
                {"employee_id": emp.employee_id, "days": by_emp.get(emp.id, [])}
                for emp in people
            ]
        return Response({
            "date": str(day),
            "role": request.role,
            "people": [_person_status(emp, day) for emp in people],
            "recent": recent,
        })


class PortalLeaveView(APIView):
    permission_classes = [IsAuthenticated, IsPortalUser]

    def get(self, request):
        people = portal_employees_qs(request.user, request.organization, request.role)
        rows = LeaveRequest.objects.filter(employee__in=people).select_related("employee", "decided_by")
        return Response(LeaveRequestSerializer(rows, many=True).data)

    def post(self, request):
        people = list(portal_employees_qs(request.user, request.organization, request.role))
        allowed_ids = {e.id for e in people}
        employee_id = request.data.get("employee")
        if employee_id is None and len(people) == 1:
            employee_id = people[0].id
        try:
            employee_id = int(employee_id)
        except (TypeError, ValueError):
            return Response({"error": "Select a person"}, status=400)
        if employee_id not in allowed_ids:
            return Response({"error": "You cannot request leave for that person"}, status=403)
        data = {k: v for k, v in request.data.items() if k != "status"}
        data["employee"] = employee_id
        serializer = LeaveRequestSerializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        leave = serializer.save()
        from approvals.engine import submit
        from approvals.models import ApprovalWorkflow

        submit(
            organization=request.organization,
            kind=ApprovalWorkflow.KIND_LEAVE,
            target_id=leave.pk,
            employee=leave.employee,
            user=request.user,
        )
        return Response(LeaveRequestSerializer(leave).data, status=201)


def _portal_people(request):
    return list(portal_employees_qs(request.user, request.organization, request.role))


def _pick_employee(request):
    people = _portal_people(request)
    allowed = {e.id: e for e in people}
    employee_id = request.data.get("employee") if hasattr(request, "data") else None
    if employee_id is None and len(people) == 1:
        return people[0], people
    try:
        employee_id = int(employee_id)
    except (TypeError, ValueError):
        return None, people
    return allowed.get(employee_id), people


class PortalBalanceView(APIView):
    permission_classes = [IsAuthenticated, IsPortalUser]

    def get(self, request):
        from payroll.services.leave_policy import balances_for

        people = _portal_people(request)
        return Response([balances_for(emp) for emp in people])


class PortalCorrectionView(APIView):
    permission_classes = [IsAuthenticated, IsPortalUser]

    def get(self, request):
        from attendance.models import AttendanceCorrection
        from attendance.serializers import AttendanceCorrectionSerializer

        people = _portal_people(request)
        rows = AttendanceCorrection.objects.filter(employee__in=people).select_related("employee", "decided_by")
        return Response(AttendanceCorrectionSerializer(rows, many=True).data)

    def post(self, request):
        from approvals.engine import submit
        from approvals.models import ApprovalWorkflow
        from attendance.models import AttendanceCorrection, AttendanceRecord
        from attendance.serializers import AttendanceCorrectionSerializer

        employee, _people = _pick_employee(request)
        if employee is None:
            return Response({"error": "Select a person"}, status=400)
        data = {k: v for k, v in request.data.items()}
        data["employee"] = employee.id
        serializer = AttendanceCorrectionSerializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        day = serializer.validated_data["date"]
        record = AttendanceRecord.objects.filter(employee=employee, date=day).first()
        row = serializer.save(
            original_check_in=record.check_in if record else None,
            original_check_out=record.check_out if record else None,
            original_status=record.status if record else "",
        )
        submit(
            organization=request.organization,
            kind=ApprovalWorkflow.KIND_CORRECTION,
            target_id=row.pk,
            employee=employee,
            user=request.user,
        )
        return Response(AttendanceCorrectionSerializer(row).data, status=201)


class PortalOvertimeView(APIView):
    permission_classes = [IsAuthenticated, IsPortalUser]

    def get(self, request):
        from attendance.models import OvertimeRequest
        from attendance.serializers import OvertimeRequestSerializer

        people = _portal_people(request)
        rows = OvertimeRequest.objects.filter(employee__in=people).select_related("employee", "decided_by")
        return Response(OvertimeRequestSerializer(rows, many=True).data)

    def post(self, request):
        from approvals.engine import submit
        from approvals.models import ApprovalWorkflow
        from attendance.models import OvertimeRequest
        from attendance.serializers import OvertimeRequestSerializer

        employee, _people = _pick_employee(request)
        if employee is None:
            return Response({"error": "Select a person"}, status=400)
        data = {**request.data, "employee": employee.id}
        serializer = OvertimeRequestSerializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        row = serializer.save(source=OvertimeRequest.SOURCE_MANUAL)
        submit(
            organization=request.organization,
            kind=ApprovalWorkflow.KIND_OVERTIME,
            target_id=row.pk,
            employee=employee,
            user=request.user,
        )
        return Response(OvertimeRequestSerializer(row).data, status=201)


class PortalDocumentView(APIView):
    permission_classes = [IsAuthenticated, IsPortalUser]

    def get(self, request):
        from employees.models import EmployeeDocument
        from employees.serializers import EmployeeDocumentSerializer

        people = _portal_people(request)
        rows = EmployeeDocument.objects.filter(employee__in=people)
        return Response(EmployeeDocumentSerializer(rows, many=True, context={"request": request}).data)


class PortalPayslipView(APIView):
    permission_classes = [IsAuthenticated, IsPortalUser]

    def get(self, request):
        from payroll.models import Payslip
        from payroll.serializers import PayslipSerializer

        people = _portal_people(request)
        rows = Payslip.objects.filter(employee__in=people, run__status="finalized").select_related(
            "run", "employee", "employee__department"
        )
        return Response(PayslipSerializer(rows, many=True).data)


class PortalResignationView(APIView):
    permission_classes = [IsAuthenticated, IsPortalUser]

    def get(self, request):
        from exits.models import ExitCase
        from exits.serializers import ExitCaseSerializer

        people = _portal_people(request)
        rows = ExitCase.objects.filter(employee__in=people).select_related("employee", "initiated_by")
        return Response(ExitCaseSerializer(rows, many=True, context={"request": request}).data)

    def post(self, request):
        from exits.services import request_resignation
        from exits.serializers import ExitCaseSerializer

        employee, _people = _pick_employee(request)
        if employee is None:
            return Response({"error": "Select a person"}, status=400)
        case = request_resignation(
            organization=request.organization,
            employee=employee,
            user=request.user,
            data=request.data,
        )
        return Response(ExitCaseSerializer(case, context={"request": request}).data, status=201)


class PortalPunchView(APIView):
    permission_classes = [IsAuthenticated, IsPortalUser]

    def _employee(self, request):
        from organizations.models import Membership

        if request.role != Membership.ROLE_EMPLOYEE:
            return None
        try:
            employee = request.user.employee_profile
        except Employee.DoesNotExist:
            return None
        if employee.organization_id != request.organization.id or not employee.is_active:
            return None
        return employee

    def get(self, request):
        from attendance.services.camera_punch import punch_context

        employee = self._employee(request)
        if employee is None:
            return Response({"error": "Camera punch is for linked employees only"}, status=403)
        return Response(punch_context(employee, request.organization))

    def post(self, request):
        from attendance.services.camera_punch import selfie_punch

        employee = self._employee(request)
        if employee is None:
            return Response({"error": "Camera punch is for linked employees only"}, status=403)
        data = selfie_punch(
            organization=request.organization,
            employee=employee,
            image_b64=request.data.get("image") or "",
            latitude=request.data.get("latitude"),
            longitude=request.data.get("longitude"),
        )
        return Response(data)
