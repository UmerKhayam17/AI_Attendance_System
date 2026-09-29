from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from employees.models import Employee
from organizations.models import Membership, Organization
from visitors.models import Visit, Visitor
from visitors.services import check_in, check_out, create_visit, set_watchlist


class VisitorFlowTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Gate Co", slug="gate-co-vms")
        self.user = User.objects.create_user("desk@gate.test", "desk@gate.test", "pass12345")
        Membership.objects.create(user=self.user, organization=self.org, role=Membership.ROLE_ADMIN)
        self.host = Employee.objects.create(
            organization=self.org,
            employee_id="h1",
            first_name="Sara",
            last_name="Host",
            email="sara@gate.test",
            designation="Reception",
            user=self.user,
        )

    def test_walk_in_check_in_and_out(self):
        visit = create_visit(
            self.org,
            {
                "first_name": "Ali",
                "last_name": "Guest",
                "phone": "03001234567",
                "host": self.host,
                "purpose": Visit.PURPOSE_MEETING,
                "source": Visit.SOURCE_WALKIN,
            },
            user=self.user,
        )
        self.assertEqual(visit.status, Visit.STATUS_EXPECTED)
        checked = check_in(visit)
        self.assertEqual(checked.status, Visit.STATUS_CHECKED_IN)
        self.assertTrue(checked.badge_code)
        done = check_out(checked)
        self.assertEqual(done.status, Visit.STATUS_CHECKED_OUT)

    def test_watchlist_blocks_new_visit(self):
        visitor = Visitor.objects.create(
            organization=self.org,
            first_name="Blocked",
            last_name="Person",
            phone="03008888888",
        )
        set_watchlist(visitor, True, "security")
        with self.assertRaises(ValidationError):
            create_visit(self.org, {"visitor": visitor, "host": self.host})

    def test_watchlist_blocks_check_in(self):
        visitor = Visitor.objects.create(
            organization=self.org,
            first_name="Blocked",
            last_name="Person",
            phone="03009999999",
        )
        set_watchlist(visitor, True, "security")
        visit = Visit.objects.create(organization=self.org, visitor=visitor, host=self.host)
        with self.assertRaises(ValidationError):
            check_in(visit)

    def test_public_gate_check_in(self):
        visit = create_visit(
            self.org,
            {"first_name": "Nadia", "phone": "03111111111", "host": self.host, "source": Visit.SOURCE_PREREGISTER},
        )
        client = APIClient()
        res = client.get(f"/api/visitors/gate/{visit.public_token}/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["visitor_name"], "Nadia")
        res = client.post(f"/api/visitors/gate/{visit.public_token}/", {"action": "check_in"}, format="json")
        self.assertEqual(res.status_code, 200)
        visit.refresh_from_db()
        self.assertEqual(visit.status, Visit.STATUS_CHECKED_IN)
