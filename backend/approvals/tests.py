from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient

from approvals.bootstrap import seed_workflows
from approvals.engine import approve, inbox_for, reject, submit
from approvals.lock import assert_dates_unlocked, period_is_locked
from approvals.models import ApprovalRequest, ApprovalStep, ApprovalWorkflow, AuditEvent
from attendance.leave_types import seed_leave_types
from attendance.models import AttendanceCorrection, AttendanceRecord, LeaveRequest, LeaveType, OvertimeRequest
from attendance.services.corrections import apply_correction
from attendance.services.leave_sync import sync_leave_records
from employees.models import Employee
from organizations.models import Membership, Organization
from payroll.models import EmployeeCompensation, PayrollPolicy, Payslip
from payroll.services.engine import generate_payroll_run, snapshot_attendance
from payroll.services.leave_policy import assert_leave_allowed, balances_for


def _aware(y, m, d, hh, mm):
    return timezone.make_aware(datetime(y, m, d, hh, mm), ZoneInfo("Asia/Karachi"))


class ApprovalEngineTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="HR Co", slug="hr-co")
        seed_workflows(self.org)
        self.owner = User.objects.create_user("owner@hr.test", "owner@hr.test", "pass12345")
        self.admin = User.objects.create_user("admin@hr.test", "admin@hr.test", "pass12345")
        self.mgr_user = User.objects.create_user("mgr@hr.test", "mgr@hr.test", "pass12345")
        Membership.objects.create(user=self.owner, organization=self.org, role=Membership.ROLE_OWNER)
        Membership.objects.create(user=self.admin, organization=self.org, role=Membership.ROLE_ADMIN)
        Membership.objects.create(user=self.mgr_user, organization=self.org, role=Membership.ROLE_EMPLOYEE)
        self.manager = Employee.objects.create(
            organization=self.org,
            employee_id="m1",
            first_name="Mana",
            last_name="Ger",
            email="mgr@hr.test",
            designation="Lead",
            user=self.mgr_user,
        )
        self.employee = Employee.objects.create(
            organization=self.org,
            employee_id="e1",
            first_name="Ann",
            last_name="ual",
            email="ann@hr.test",
            designation="Staff",
        )
        self.policy = PayrollPolicy.for_org(self.org)
        self.policy.annual_leave_days = 10
        self.policy.save()
        seed_leave_types(self.org, self.policy)

    def _leave(self, **kwargs):
        data = dict(
            employee=self.employee,
            leave_type=LeaveRequest.TYPE_ANNUAL,
            start_date=date(2026, 8, 24),
            end_date=date(2026, 8, 24),
            status=LeaveRequest.STATUS_PENDING,
        )
        data.update(kwargs)
        return LeaveRequest.objects.create(**data)

    def test_default_leave_workflow_is_admin_step(self):
        wf = ApprovalWorkflow.objects.get(organization=self.org, kind=ApprovalWorkflow.KIND_LEAVE)
        steps = list(wf.steps.order_by("order"))
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].assignee_role, ApprovalStep.ROLE_ADMIN)
        leave = self._leave()
        req = submit(organization=self.org, kind=ApprovalWorkflow.KIND_LEAVE, target_id=leave.pk, employee=self.employee, user=self.admin)
        approve(req, self.admin)
        leave.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.STATUS_APPROVED)
        inbox = inbox_for(self.admin, self.org)
        self.assertEqual(inbox, [])

    def test_manager_step_skips_when_no_manager(self):
        wf = ApprovalWorkflow.objects.get(organization=self.org, kind=ApprovalWorkflow.KIND_LEAVE)
        wf.steps.all().delete()
        ApprovalStep.objects.create(workflow=wf, order=1, assignee_role=ApprovalStep.ROLE_MANAGER)
        ApprovalStep.objects.create(workflow=wf, order=2, assignee_role=ApprovalStep.ROLE_ADMIN)
        leave = self._leave()
        req = submit(organization=self.org, kind=ApprovalWorkflow.KIND_LEAVE, target_id=leave.pk, employee=self.employee, user=self.admin)
        self.assertEqual(req.current_step.assignee_role, ApprovalStep.ROLE_ADMIN)

    def test_manager_can_approve_first_step(self):
        wf = ApprovalWorkflow.objects.get(organization=self.org, kind=ApprovalWorkflow.KIND_LEAVE)
        wf.steps.all().delete()
        ApprovalStep.objects.create(workflow=wf, order=1, assignee_role=ApprovalStep.ROLE_MANAGER)
        ApprovalStep.objects.create(workflow=wf, order=2, assignee_role=ApprovalStep.ROLE_ADMIN)
        self.employee.manager = self.manager
        self.employee.save()
        leave = self._leave()
        req = submit(organization=self.org, kind=ApprovalWorkflow.KIND_LEAVE, target_id=leave.pk, employee=self.employee, user=self.employee.user)
        self.assertIn(req, inbox_for(self.mgr_user, self.org))
        approve(req, self.mgr_user)
        req.refresh_from_db()
        self.assertEqual(req.status, ApprovalRequest.STATUS_PENDING)
        self.assertEqual(req.current_step.assignee_role, ApprovalStep.ROLE_ADMIN)
        leave.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.STATUS_PENDING)
        approve(req, self.admin)
        leave.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.STATUS_APPROVED)

    def test_new_leave_type_in_balances(self):
        data = balances_for(self.employee, date(2026, 8, 22))
        self.assertIn("casual", data["balances"])
        self.assertIn("maternity", data["balances"])
        extra = LeaveRequest(
            employee=self.employee,
            leave_type="casual",
            start_date=date(2026, 8, 24),
            end_date=date(2026, 8, 31),
            status=LeaveRequest.STATUS_PENDING,
        )
        extra.save()
        LeaveType.objects.filter(organization=self.org, code="casual").update(entitlement_days=1)
        with self.assertRaises(ValidationError):
            assert_leave_allowed(extra)

    def test_correction_apply_and_payroll_lock(self):
        record = AttendanceRecord.objects.create(
            employee=self.employee,
            date=date(2026, 8, 3),
            status=AttendanceRecord.STATUS_PRESENT,
            check_in=_aware(2026, 8, 3, 9, 0),
        )
        corr = AttendanceCorrection.objects.create(
            employee=self.employee,
            date=date(2026, 8, 3),
            requested_check_out=_aware(2026, 8, 3, 18, 5),
            original_check_in=record.check_in,
            original_status=record.status,
            reason="Camera missed me",
        )
        apply_correction(corr, self.admin)
        record.refresh_from_db()
        self.assertIsNotNone(record.check_out)
        self.assertEqual(corr.status, AttendanceCorrection.STATUS_APPROVED)
        self.assertTrue(AuditEvent.objects.filter(model="AttendanceCorrection", object_id=str(corr.id)).exists())

        EmployeeCompensation.objects.create(
            employee=self.employee,
            pay_type=EmployeeCompensation.PAY_MONTHLY,
            basic_salary=Decimal("26000.00"),
        )
        run = generate_payroll_run(self.org, date(2026, 8, 1), date(2026, 8, 31), user=self.admin)
        run.status = run.STATUS_FINALIZED
        run.save(update_fields=["status"])
        snapshot_attendance(run)
        slip = Payslip.objects.get(run=run, employee=self.employee)
        self.assertTrue(slip.breakdown.get("locked"))
        self.assertTrue(period_is_locked(self.org, date(2026, 8, 3)))
        with self.assertRaises(ValidationError):
            assert_dates_unlocked(self.org, date(2026, 8, 3), date(2026, 8, 3))

    def test_overtime_requires_approval(self):
        EmployeeCompensation.objects.create(
            employee=self.employee,
            pay_type=EmployeeCompensation.PAY_MONTHLY,
            basic_salary=Decimal("26000.00"),
        )
        AttendanceRecord.objects.create(
            employee=self.employee,
            date=date(2026, 8, 3),
            status=AttendanceRecord.STATUS_PRESENT,
            check_in=_aware(2026, 8, 3, 9, 0),
            check_out=_aware(2026, 8, 3, 20, 0),
            overtime_minutes=90,
        )
        policy = PayrollPolicy.for_org(self.org)
        policy.overtime_requires_approval = True
        policy.overtime_min_minutes = 0
        policy.save()
        run = generate_payroll_run(self.org, date(2026, 8, 3), date(2026, 8, 3), user=self.admin)
        slip = Payslip.objects.get(run=run, employee=self.employee)
        self.assertEqual(slip.overtime_minutes, 0)
        self.assertEqual(slip.overtime_pay, Decimal("0.00"))
        OvertimeRequest.objects.create(
            employee=self.employee,
            date=date(2026, 8, 3),
            minutes=90,
            status=OvertimeRequest.STATUS_APPROVED,
        )
        run = generate_payroll_run(self.org, date(2026, 8, 3), date(2026, 8, 3), user=self.admin)
        slip = Payslip.objects.get(run=run, employee=self.employee)
        self.assertEqual(slip.overtime_minutes, 90)

    def test_portal_resignation_creates_pending_exit(self):
        from exits.services import request_resignation

        case = request_resignation(
            organization=self.org,
            employee=self.employee,
            user=self.admin,
            data={"reason": "Moving"},
        )
        self.assertEqual(case.status, "initiated")
        req = ApprovalRequest.objects.get(kind=ApprovalWorkflow.KIND_EXIT, target_id=case.pk)
        self.assertEqual(req.status, ApprovalRequest.STATUS_PENDING)
