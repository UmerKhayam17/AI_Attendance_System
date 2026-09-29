from django.conf import settings
from django.db import models


def _default_branch_for(organization):
    if organization is None:
        return None
    organization.ensure_default_branch()
    return organization.default_branch()


class Department(models.Model):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="departments",
    )
    branch = models.ForeignKey(
        "organizations.Branch",
        on_delete=models.PROTECT,
        related_name="departments",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "department"
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "branch", "name"],
                name="uniq_department_name_per_branch",
            ),
        ]

    def __str__(self):
        return f"{self.organization_id} / {self.branch_id} / {self.name}"

    def save(self, *args, **kwargs):
        if not self.branch_id and self.organization_id:
            self.branch = _default_branch_for(self.organization)
        super().save(*args, **kwargs)


class Employee(models.Model):
    GENDER_MALE = "male"
    GENDER_FEMALE = "female"
    GENDER_OTHER = "other"
    GENDER_CHOICES = [
        (GENDER_MALE, "Male"),
        (GENDER_FEMALE, "Female"),
        (GENDER_OTHER, "Other"),
    ]

    TYPE_FULL_TIME = "full_time"
    TYPE_PART_TIME = "part_time"
    TYPE_CONTRACT = "contract"
    TYPE_INTERN = "intern"
    TYPE_TEMPORARY = "temporary"
    TYPE_REMOTE = "remote"
    TYPE_CHOICES = [
        (TYPE_FULL_TIME, "Full-time"),
        (TYPE_PART_TIME, "Part-time"),
        (TYPE_CONTRACT, "Contract"),
        (TYPE_INTERN, "Intern"),
        (TYPE_TEMPORARY, "Temporary"),
        (TYPE_REMOTE, "Remote"),
    ]

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="employees",
    )
    branch = models.ForeignKey(
        "organizations.Branch",
        on_delete=models.PROTECT,
        related_name="employees",
        null=True,
        blank=True,
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee_profile",
    )
    employee_id = models.CharField(max_length=40)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    national_id = models.CharField(max_length=40, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=16, choices=GENDER_CHOICES, blank=True)
    address = models.CharField(max_length=255, blank=True)
    guardian_name = models.CharField(max_length=120, blank=True)
    guardian_phone = models.CharField(max_length=20, blank=True)
    guardian_email = models.EmailField(blank=True)
    department = models.ForeignKey(
        "Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
    )
    designation = models.CharField(max_length=100)
    employment_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_FULL_TIME,
    )
    joining_date = models.DateField(null=True, blank=True)
    manager = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="direct_reports",
    )
    shift = models.ForeignKey(
        "organizations.Shift",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "employee"
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "employee_id"],
                name="uniq_employee_id_per_org",
            ),
            models.UniqueConstraint(
                fields=["organization", "email"],
                name="uniq_employee_email_per_org",
            ),
        ]

    def __str__(self):
        return f"{self.employee_id} - {self.first_name} {self.last_name}".strip()

    def save(self, *args, **kwargs):
        if not self.branch_id and self.organization_id:
            self.branch = _default_branch_for(self.organization)
        super().save(*args, **kwargs)

    @property
    def display_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def department_name(self) -> str:
        return self.department.name if self.department_id else ""

    @property
    def branch_name(self) -> str:
        return self.branch.name if self.branch_id else ""


class EmployeeDocument(models.Model):
    CATEGORY_CONTRACT = "contract"
    CATEGORY_ID = "id"
    CATEGORY_CERTIFICATE = "certificate"
    CATEGORY_OTHER = "other"
    CATEGORY_CHOICES = [
        (CATEGORY_CONTRACT, "Contract"),
        (CATEGORY_ID, "ID"),
        (CATEGORY_CERTIFICATE, "Certificate"),
        (CATEGORY_OTHER, "Other"),
    ]

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    title = models.CharField(max_length=160)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER)
    file = models.FileField(upload_to="employees/documents/%Y/%m/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "employee_document"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.employee.employee_id} / {self.title}"


class ParentLink(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="parent_links",
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="parent_links",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "parent_link"
        constraints = [
            models.UniqueConstraint(fields=["user", "employee"], name="uniq_parent_employee"),
        ]

    def __str__(self):
        return f"{self.user_id} -> {self.employee.employee_id}"
