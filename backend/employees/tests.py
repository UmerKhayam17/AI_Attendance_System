from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

from employees.access import portal_employees_qs
from employees.models import Department, Employee, ParentLink
from organizations.limits import ensure_branch_slot, ensure_staff_slot
from organizations.models import Branch, Membership, Organization
from rest_framework.exceptions import ValidationError


class PortalAccessTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Portal Co", slug="portal-co")
        self.parent_user = User.objects.create_user("parent@p.test", "parent@p.test", "x")
        self.emp_user = User.objects.create_user("kid@p.test", "kid@p.test", "x")
        grade = Department.objects.create(organization=self.org, name="Grade 1")
        self.child = Employee.objects.create(
            organization=self.org,
            employee_id="s1",
            first_name="Sam",
            last_name="Student",
            email="kid@p.test",
            department=grade,
            designation="Student",
            user=self.emp_user,
        )
        ParentLink.objects.create(user=self.parent_user, employee=self.child)
        Membership.objects.create(user=self.emp_user, organization=self.org, role=Membership.ROLE_EMPLOYEE)
        Membership.objects.create(user=self.parent_user, organization=self.org, role=Membership.ROLE_PARENT)

    def test_employee_sees_self(self):
        qs = portal_employees_qs(self.emp_user, self.org, Membership.ROLE_EMPLOYEE)
        self.assertEqual(list(qs), [self.child])

    def test_parent_sees_linked_child(self):
        qs = portal_employees_qs(self.parent_user, self.org, Membership.ROLE_PARENT)
        self.assertEqual(list(qs), [self.child])


class StaffLimitTests(TestCase):
    def test_portal_members_do_not_consume_staff_slots(self):
        org = Organization.objects.create(
            name="Limit Co",
            slug="limit-co",
            plan="free",
            billing_exempt=True,
        )
        owner = User.objects.create_user("owner@l.test", "owner@l.test", "x")
        portal = User.objects.create_user("emp@l.test", "emp@l.test", "x")
        Membership.objects.create(user=owner, organization=org, role=Membership.ROLE_OWNER)
        Membership.objects.create(user=portal, organization=org, role=Membership.ROLE_EMPLOYEE)
        # Free staff limit is 2; owner + 1 staff invite should still fit because portal is excluded
        ensure_staff_slot(org)


class DepartmentTests(TestCase):
    def test_department_name_and_uniqueness(self):
        org = Organization.objects.create(name="Dept Co", slug="dept-co")
        engineering = Department.objects.create(organization=org, name="Engineering")
        emp = Employee.objects.create(
            organization=org,
            employee_id="e1",
            first_name="Ada",
            last_name="Lovelace",
            email="ada@dept.test",
            department=engineering,
            designation="Engineer",
        )
        self.assertEqual(emp.department_name, "Engineering")
        empty = Employee.objects.create(
            organization=org,
            employee_id="e2",
            first_name="No",
            last_name="Dept",
            email="none@dept.test",
            designation="Staff",
        )
        self.assertEqual(empty.department_name, "")
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Department.objects.create(organization=org, name="Engineering")


class BranchTests(TestCase):
    def test_org_gets_default_branch(self):
        org = Organization.objects.create(name="Multi Co", slug="multi-co")
        branch = org.default_branch()
        self.assertIsNotNone(branch)
        self.assertTrue(branch.is_default)
        self.assertEqual(branch.timezone, org.timezone)

    def test_two_branches_can_share_department_name(self):
        org = Organization.objects.create(name="HR Co", slug="hr-co-branch")
        home = org.default_branch()
        pesh = Branch.objects.create(organization=org, name="Peshawar", timezone="Asia/Karachi")
        Department.objects.create(organization=org, branch=home, name="HR")
        Department.objects.create(organization=org, branch=pesh, name="HR")
        self.assertEqual(Department.objects.filter(organization=org, name="HR").count(), 2)

    def test_free_plan_branch_limit(self):
        org = Organization.objects.create(
            name="Free Co",
            slug="free-co-branch",
            plan="free",
            billing_exempt=True,
        )
        self.assertEqual(org.branches.count(), 1)
        with self.assertRaises(ValidationError):
            ensure_branch_slot(org)

    def test_employee_hr_fields_and_document(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from employees.models import EmployeeDocument

        org = Organization.objects.create(name="HR Dir", slug="hr-dir")
        manager = Employee.objects.create(
            organization=org,
            employee_id="m1",
            first_name="Pat",
            last_name="Boss",
            email="pat@hr.test",
            designation="Lead",
            employment_type=Employee.TYPE_FULL_TIME,
        )
        emp = Employee.objects.create(
            organization=org,
            employee_id="e9",
            first_name="Kim",
            last_name="Lee",
            email="kim@hr.test",
            designation="Analyst",
            national_id="35202-1234567-1",
            employment_type=Employee.TYPE_CONTRACT,
            manager=manager,
        )
        self.assertEqual(emp.branch_id, org.default_branch().id)
        self.assertEqual(emp.manager_id, manager.id)
        doc = EmployeeDocument.objects.create(
            employee=emp,
            title="Contract",
            category=EmployeeDocument.CATEGORY_CONTRACT,
            file=SimpleUploadedFile("contract.txt", b"ok"),
        )
        self.assertEqual(emp.documents.count(), 1)
        self.assertEqual(doc.title, "Contract")
