from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from employees.models import Employee
from organizations.permissions import CanView, IsOwnerOrAdmin
from payroll.models import EmployeeCompensation, PayrollPolicy, PayrollRun, Payslip
from payroll.serializers import (
    EmployeeCompensationSerializer,
    GeneratePayrollSerializer,
    PayrollPolicySerializer,
    PayrollRunListSerializer,
    PayrollRunSerializer,
)
from payroll.services.engine import generate_payroll_run
from payroll.services.leave_policy import balances_for, previous_calendar_month


class PayrollPolicyView(APIView):
    def get_permissions(self):
        if self.request.method in ("PUT", "PATCH"):
            return [IsOwnerOrAdmin()]
        return [CanView()]

    def get(self, request):
        policy = PayrollPolicy.for_org(request.organization)
        return Response(PayrollPolicySerializer(policy).data)

    def put(self, request):
        return self._save(request, partial=False)

    def patch(self, request):
        return self._save(request, partial=True)

    def _save(self, request, partial):
        policy = PayrollPolicy.for_org(request.organization)
        serializer = PayrollPolicySerializer(policy, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


def _empty_compensation(employee: Employee) -> dict:
    return {
        "employee_id": employee.employee_id,
        "employee_name": employee.display_name,
        "department": employee.department_name,
        "designation": employee.designation,
        "is_active": employee.is_active,
        "pay_type": EmployeeCompensation.PAY_MONTHLY,
        "basic_salary": "0.00",
        "housing_allowance": "0.00",
        "transport_allowance": "0.00",
        "medical_allowance": "0.00",
        "other_allowance": "0.00",
        "other_deduction": "0.00",
        "hire_date": None,
        "bank_name": "",
        "account_title": "",
        "account_number": "",
        "notes": "",
        "gross": "0.00",
        "salary_set": False,
    }


class CompensationListView(APIView):
    permission_classes = [IsOwnerOrAdmin]

    def get(self, request):
        employees = (
            Employee.objects.filter(organization=request.organization)
            .select_related("department", "compensation")
            .order_by("-is_active", "first_name", "last_name", "employee_id")
        )
        rows = []
        for employee in employees:
            try:
                rows.append(EmployeeCompensationSerializer(employee.compensation).data)
            except EmployeeCompensation.DoesNotExist:
                rows.append(_empty_compensation(employee))
        return Response(rows)


class CompensationView(APIView):
    permission_classes = [IsOwnerOrAdmin]

    def get(self, request, employee_id):
        employee = get_object_or_404(
            Employee,
            organization=request.organization,
            employee_id=employee_id,
        )
        compensation, _ = EmployeeCompensation.objects.get_or_create(employee=employee)
        return Response(EmployeeCompensationSerializer(compensation).data)

    def put(self, request, employee_id):
        return self._save(request, employee_id)

    def patch(self, request, employee_id):
        return self._save(request, employee_id)

    def _save(self, request, employee_id):
        employee = get_object_or_404(
            Employee,
            organization=request.organization,
            employee_id=employee_id,
        )
        compensation, _ = EmployeeCompensation.objects.get_or_create(employee=employee)
        serializer = EmployeeCompensationSerializer(compensation, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class LeaveBalanceView(APIView):
    permission_classes = [CanView]

    def get(self, request):
        employees = Employee.objects.filter(
            organization=request.organization,
            is_active=True,
        ).select_related("compensation").order_by("employee_id")
        employee_id = request.query_params.get("employee_id")
        if employee_id:
            employees = employees.filter(employee_id=employee_id)
        return Response([balances_for(emp) for emp in employees])


class PayrollRunListView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsOwnerOrAdmin()]
        return [CanView()]

    def get(self, request):
        runs = (
            PayrollRun.objects.filter(organization=request.organization)
            .annotate(payslip_count=Count("payslips"))
            .order_by("-period_start", "-id")
        )
        return Response(PayrollRunListSerializer(runs, many=True).data)

    def post(self, request):
        serializer = GeneratePayrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            run = generate_payroll_run(
                request.organization,
                serializer.validated_data["period_start"],
                serializer.validated_data["period_end"],
                user=request.user,
            )
            from approvals.audit import write_audit

            write_audit(
                organization=request.organization,
                actor=request.user,
                action="payroll.generate",
                model="PayrollRun",
                object_id=run.id,
                new_value={"period_start": str(run.period_start), "period_end": str(run.period_end)},
                request=request,
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        run = (
            PayrollRun.objects.filter(pk=run.pk)
            .annotate(payslip_count=Count("payslips"))
            .prefetch_related(
                Prefetch("payslips", queryset=Payslip.objects.select_related("employee", "employee__department"))
            )
            .get()
        )
        return Response(PayrollRunSerializer(run).data, status=status.HTTP_201_CREATED)


class PayrollRunDetailView(APIView):
    def get_permissions(self):
        if self.request.method in ("POST", "DELETE"):
            return [IsOwnerOrAdmin()]
        return [CanView()]

    def _run(self, request, pk):
        return get_object_or_404(
            PayrollRun.objects.annotate(payslip_count=Count("payslips")).prefetch_related(
                Prefetch("payslips", queryset=Payslip.objects.select_related("employee", "employee__department"))
            ),
            organization=request.organization,
            pk=pk,
        )

    def get(self, request, pk):
        return Response(PayrollRunSerializer(self._run(request, pk)).data)

    def delete(self, request, pk):
        run = get_object_or_404(PayrollRun, organization=request.organization, pk=pk)
        if run.status == PayrollRun.STATUS_FINALIZED:
            return Response({"error": "Finalized payroll cannot be deleted"}, status=status.HTTP_400_BAD_REQUEST)
        run.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PayrollRunFinalizeView(APIView):
    permission_classes = [IsOwnerOrAdmin]

    def post(self, request, pk):
        run = get_object_or_404(PayrollRun, organization=request.organization, pk=pk)
        if run.status == PayrollRun.STATUS_FINALIZED:
            return Response({"error": "Already finalized"}, status=status.HTTP_400_BAD_REQUEST)
        if not run.payslips.exists():
            return Response({"error": "Generate payslips before finalizing"}, status=status.HTTP_400_BAD_REQUEST)
        run.status = PayrollRun.STATUS_FINALIZED
        run.finalized_by = request.user
        run.finalized_at = timezone.now()
        from payroll.services.engine import snapshot_attendance
        from approvals.audit import write_audit

        snapshot_attendance(run)
        write_audit(
            organization=request.organization,
            actor=request.user,
            action="payroll.finalize",
            model="PayrollRun",
            object_id=run.id,
            new_value={"period_start": str(run.period_start), "period_end": str(run.period_end)},
            request=request,
        )
        run = (
            PayrollRun.objects.filter(pk=run.pk)
            .annotate(payslip_count=Count("payslips"))
            .prefetch_related(
                Prefetch("payslips", queryset=Payslip.objects.select_related("employee", "employee__department"))
            )
            .get()
        )
        return Response(PayrollRunSerializer(run).data)


class PayrollDefaultPeriodView(APIView):
    permission_classes = [CanView]

    def get(self, request):
        start, end = previous_calendar_month()
        return Response({"period_start": str(start), "period_end": str(end)})
