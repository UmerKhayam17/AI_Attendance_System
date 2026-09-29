from datetime import date

from django.test import TestCase

from employees.models import Employee
from exits.models import ExitCase, ExitPolicy
from exits.services import complete_exit, init_exit_module, initiate_exit
from organizations.models import Organization
from rest_framework.exceptions import ValidationError


class ExitModuleTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Exit Co", slug="exit-co")
        self.employee = Employee.objects.create(
            organization=self.org,
            employee_id="x1",
            first_name="Lea",
            last_name="Ver",
            email="lea@exit.test",
            designation="Staff",
        )

    def test_init_seeds_policy_and_checklist(self):
        policy = init_exit_module(self.org)
        self.assertIsInstance(policy, ExitPolicy)
        self.assertGreater(self.org.exit_checklist_templates.count(), 0)

    def test_complete_deactivates_employee(self):
        case = initiate_exit(
            organization=self.org,
            employee=self.employee,
            user=None,
            data={"resignation_date": date(2026, 8, 18), "reason": "Moving"},
        )
        for item in case.checklist_items.all():
            item.is_cleared = True
            item.save()
        case.interview_completed = True
        case.save(update_fields=["interview_completed"])
        complete_exit(case, None)
        self.employee.refresh_from_db()
        self.assertFalse(self.employee.is_active)
        case.refresh_from_db()
        self.assertEqual(case.status, ExitCase.STATUS_COMPLETED)

    def test_cannot_complete_without_clearance(self):
        case = initiate_exit(
            organization=self.org,
            employee=self.employee,
            user=None,
            data={},
        )
        with self.assertRaises(ValidationError):
            complete_exit(case, None)
