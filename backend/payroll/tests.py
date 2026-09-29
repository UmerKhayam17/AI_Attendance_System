from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone

from attendance.models import AttendanceRecord, LeaveRequest
from employees.models import Employee
from organizations.models import Organization
from payroll.models import EmployeeCompensation, PayrollPolicy, Payslip
from payroll.services.engine import generate_payroll_run
from payroll.services.leave_policy import assert_leave_allowed, balances_for
from rest_framework.exceptions import ValidationError


class PayrollEngineTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name="Pay Co",
            slug="pay-co",
            weekend_days=[5, 6],
        )
        self.policy = PayrollPolicy.for_org(self.org)
        self.policy.working_days_per_month = Decimal("26")
        self.policy.late_count_free = 0
        self.policy.late_penalty_mode = PayrollPolicy.LATE_FIXED
        self.policy.late_penalty_amount = Decimal("100.00")
        self.policy.annual_leave_days = 2
        self.policy.save()
        self.employee = Employee.objects.create(
            organization=self.org,
            employee_id="e1",
            first_name="Pay",
            last_name="Roll",
            email="pay@co.test",
            designation="Staff",
        )
        EmployeeCompensation.objects.create(
            employee=self.employee,
            pay_type=EmployeeCompensation.PAY_MONTHLY,
            basic_salary=Decimal("26000.00"),
        )

    def test_absent_day_is_deducted(self):
        start, end = date(2026, 8, 3), date(2026, 8, 7)  # Mon-Fri
        AttendanceRecord.objects.create(
            employee=self.employee,
            date=date(2026, 8, 3),
            status=AttendanceRecord.STATUS_PRESENT,
            check_in=timezone.make_aware(datetime(2026, 8, 3, 9, 0), ZoneInfo("Asia/Karachi")),
        )
        run = generate_payroll_run(self.org, start, end)
        slip = Payslip.objects.get(run=run, employee=self.employee)
        self.assertEqual(slip.present_days, Decimal("1.00"))
        self.assertGreater(slip.absent_days, 0)
        self.assertGreater(slip.absent_deduction, 0)
        self.assertLess(slip.net_pay, slip.gross_pay)

    def test_leave_balance_blocks_overuse(self):
        LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=LeaveRequest.TYPE_ANNUAL,
            start_date=date(2026, 8, 3),
            end_date=date(2026, 8, 4),
            status=LeaveRequest.STATUS_APPROVED,
        )
        extra = LeaveRequest(
            employee=self.employee,
            leave_type=LeaveRequest.TYPE_ANNUAL,
            start_date=date(2026, 8, 5),
            end_date=date(2026, 8, 6),
            status=LeaveRequest.STATUS_PENDING,
        )
        extra.save()
        with self.assertRaises(ValidationError):
            assert_leave_allowed(extra)

    def test_balances_include_remaining(self):
        data = balances_for(self.employee, date(2026, 8, 18))
        self.assertEqual(data["balances"]["annual"]["entitled"], 2)
        self.assertEqual(data["balances"]["annual"]["remaining"], 2)
