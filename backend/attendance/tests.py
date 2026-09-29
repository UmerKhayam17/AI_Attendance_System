from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.test import TestCase
from django.utils import timezone

from attendance.models import AttendanceRecord, Holiday, LeaveRequest
from attendance.services.decision_engine import AttendanceDecisionEngine
from attendance.services.leave_sync import sync_leave_records
from attendance.services.workday import expected_employees, is_non_working
from employees.models import Department, Employee
from organizations.models import Branch, Organization, Shift


class WorkdayTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name="HR Co",
            slug="hr-co",
            weekend_days=[5, 6],
        )
        engineering = Department.objects.create(organization=self.org, name="Engineering")
        self.employee = Employee.objects.create(
            organization=self.org,
            employee_id="emp200",
            first_name="Grace",
            last_name="Hopper",
            email="grace@hr.test",
            department=engineering,
            designation="Engineer",
        )

    def test_weekend_is_non_working(self):
        saturday = date(2026, 8, 22)
        off, reason = is_non_working(self.org, saturday)
        self.assertTrue(off)
        self.assertEqual(reason, "Weekend")
        self.assertEqual(expected_employees(self.org, saturday, [self.employee]), [])

    def test_holiday_and_leave_excluded_from_expected(self):
        day = date(2026, 8, 19)
        Holiday.objects.create(organization=self.org, date=day, name="Test Day")
        off, reason = is_non_working(self.org, day)
        self.assertTrue(off)
        self.assertEqual(reason, "Test Day")

        workday = date(2026, 8, 18)
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            start_date=workday,
            end_date=workday,
            status=LeaveRequest.STATUS_APPROVED,
            leave_type=LeaveRequest.TYPE_ANNUAL,
        )
        sync_leave_records(leave)
        self.assertEqual(expected_employees(self.org, workday, [self.employee]), [])
        record = AttendanceRecord.objects.get(employee=self.employee, date=workday)
        self.assertEqual(record.status, AttendanceRecord.STATUS_ON_LEAVE)


class CheckoutRuleTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Shift Co", slug="shift-co")
        self.shift = Shift.objects.create(
            organization=self.org,
            name="Day",
            start_time=time(9, 0),
            late_after=time(9, 30),
            end_time=time(18, 0),
            is_default=True,
        )
        rnd = Department.objects.create(organization=self.org, name="R&D")
        self.employee = Employee.objects.create(
            organization=self.org,
            employee_id="emp201",
            first_name="Alan",
            last_name="Turing",
            email="alan@shift.test",
            department=rnd,
            designation="Researcher",
            shift=self.shift,
        )
        self.tz = ZoneInfo("Asia/Karachi")

    def test_short_day_is_half_day(self):
        check_in = timezone.make_aware(datetime(2026, 8, 18, 9, 5), self.tz)
        check_out = timezone.make_aware(datetime(2026, 8, 18, 13, 0), self.tz)
        AttendanceDecisionEngine.process_recognition(
            self.employee, 0.9, zone="mixed", now=check_in
        )
        result = AttendanceDecisionEngine.process_recognition(
            self.employee, 0.9, zone="mixed", now=check_out
        )
        record = result["record"]
        self.assertEqual(record.status, AttendanceRecord.STATUS_HALF_DAY)
        self.assertTrue(record.early_leave)

    def test_staying_late_sets_overtime(self):
        check_in = timezone.make_aware(datetime(2026, 8, 18, 9, 0), self.tz)
        check_out = timezone.make_aware(datetime(2026, 8, 18, 19, 30), self.tz)
        AttendanceDecisionEngine.process_recognition(
            self.employee, 0.9, zone="mixed", now=check_in
        )
        result = AttendanceDecisionEngine.process_recognition(
            self.employee, 0.9, zone="mixed", now=check_out
        )
        self.assertGreaterEqual(result["record"].overtime_minutes, 60)
        self.assertFalse(result["record"].early_leave)


class AlertDedupeTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name="Alert Co",
            slug="alert-co",
            notify_email=True,
            notify_sms=False,
            notify_whatsapp=False,
            notify_late=True,
            notify_absent=True,
        )
        math = Department.objects.create(organization=self.org, name="Math")
        self.employee = Employee.objects.create(
            organization=self.org,
            employee_id="emp300",
            first_name="Ada",
            last_name="Lovelace",
            email="ada@alert.test",
            department=math,
            designation="Analyst",
        )

    def test_email_alert_is_deduped(self):
        from attendance.models import NotificationLog
        from attendance.services.notifier import notify_event

        first = notify_event(self.employee, NotificationLog.KIND_ABSENT)
        second = notify_event(self.employee, NotificationLog.KIND_ABSENT)
        self.assertGreaterEqual(first, 1)
        self.assertEqual(second, 0)
        self.assertEqual(
            NotificationLog.objects.filter(employee=self.employee, kind="absent").count(),
            1,
        )


class RangeReportTests(TestCase):
    def test_weekend_is_not_counted_absent(self):
        from dashboard.reports import range_report

        org = Organization.objects.create(name="Report Co", slug="report-co", weekend_days=[5, 6])
        ops = Department.objects.create(organization=org, name="Ops")
        Employee.objects.create(
            organization=org,
            employee_id="emp301",
            first_name="Lin",
            last_name="us",
            email="lin@report.test",
            department=ops,
            designation="Staff",
        )
        saturday = date(2026, 8, 22)
        data = range_report(org, saturday, saturday)
        self.assertEqual(data["days"][0]["absent"], 0)
        self.assertFalse(data["days"][0]["is_workday"])


class BranchWorkdayTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name="Cities Co",
            slug="cities-co",
            weekend_days=[5, 6],
            timezone="Asia/Karachi",
        )
        self.islamabad = self.org.default_branch()
        self.peshawar = Branch.objects.create(
            organization=self.org,
            name="Peshawar",
            timezone="Asia/Karachi",
            weekend_days=[4, 5],
        )

    def test_branch_weekend_days_differ(self):
        friday = date(2026, 8, 21)
        off_isb, reason_isb = is_non_working(self.org, friday, branch=self.islamabad)
        off_pesh, reason_pesh = is_non_working(self.org, friday, branch=self.peshawar)
        self.assertFalse(off_isb)
        self.assertTrue(off_pesh)
        self.assertEqual(reason_pesh, "Weekend")

    def test_branch_timezone_changes_late_status(self):
        utc_branch = Branch.objects.create(
            organization=self.org,
            name="Remote UTC",
            timezone="UTC",
            weekend_days=[5, 6],
        )
        emp = Employee.objects.create(
            organization=self.org,
            branch=utc_branch,
            employee_id="utc1",
            first_name="Uma",
            last_name="Tee",
            email="uma@cities.test",
            designation="Staff",
        )
        karachi = timezone.make_aware(datetime(2026, 8, 18, 15, 5), ZoneInfo("Asia/Karachi"))
        result = AttendanceDecisionEngine.process_recognition(emp, 0.9, zone="mixed", now=karachi)
        self.assertEqual(result["action"], "check_in")
        self.assertEqual(result["record"].status, AttendanceRecord.STATUS_LATE)

    def test_shift_assignment_overrides_employee_shift(self):
        from organizations.models import ShiftAssignment
        from organizations.shifts import schedule_for

        day = Shift.objects.create(
            organization=self.org,
            name="Day",
            start_time=time(9, 0),
            late_after=time(9, 30),
            end_time=time(18, 0),
        )
        night = Shift.objects.create(
            organization=self.org,
            name="Night",
            kind=Shift.KIND_NIGHT,
            start_time=time(22, 0),
            late_after=time(22, 30),
            end_time=time(6, 0),
        )
        emp = Employee.objects.create(
            organization=self.org,
            employee_id="rot1",
            first_name="Rae",
            last_name="Ster",
            email="rae@cities.test",
            designation="Staff",
            shift=day,
        )
        ShiftAssignment.objects.create(
            employee=emp,
            shift=night,
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 31),
        )
        schedule = schedule_for(employee=emp, organization=self.org, on_date=date(2026, 8, 18))
        self.assertEqual(schedule.id, night.id)

