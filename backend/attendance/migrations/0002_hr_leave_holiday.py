import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0001_initial"),
        ("employees", "0005_employee_shift"),
        ("organizations", "0005_weekend_days"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="attendancerecord",
            name="early_leave",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="attendancerecord",
            name="overtime_minutes",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="attendancerecord",
            name="status",
            field=models.CharField(
                choices=[
                    ("present", "Present"),
                    ("late", "Late"),
                    ("absent", "Absent"),
                    ("half_day", "Half Day"),
                    ("on_leave", "On Leave"),
                ],
                default="present",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="Holiday",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("name", models.CharField(max_length=120)),
                ("repeats_yearly", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="holidays",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={
                "db_table": "org_holiday",
                "ordering": ["date"],
            },
        ),
        migrations.AddConstraint(
            model_name="holiday",
            constraint=models.UniqueConstraint(fields=("organization", "date"), name="uniq_holiday_date_per_org"),
        ),
        migrations.CreateModel(
            name="LeaveRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "leave_type",
                    models.CharField(
                        choices=[
                            ("annual", "Annual"),
                            ("sick", "Sick"),
                            ("unpaid", "Unpaid"),
                            ("other", "Other"),
                        ],
                        default="annual",
                        max_length=20,
                    ),
                ),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("reason", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "decided_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="leave_decisions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "employee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="leave_requests",
                        to="employees.employee",
                    ),
                ),
            ],
            options={
                "db_table": "leave_request",
                "ordering": ["-start_date", "-id"],
            },
        ),
    ]
