import django.db.models.deletion
from django.db import migrations, models


def seed_departments(apps, schema_editor):
    Employee = apps.get_model("employees", "Employee")
    Department = apps.get_model("employees", "Department")
    cache = {}
    for emp in Employee.objects.all().iterator():
        name = (getattr(emp, "department_name_legacy", None) or "").strip()
        if not name:
            continue
        key = (emp.organization_id, name.casefold())
        dept = cache.get(key)
        if dept is None:
            dept = Department.objects.filter(
                organization_id=emp.organization_id,
                name__iexact=name,
            ).first()
            if dept is None:
                dept = Department.objects.create(
                    organization_id=emp.organization_id,
                    name=name,
                )
            cache[key] = dept
        emp.department_id = dept.id
        emp.save(update_fields=["department_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("employees", "0006_phase3_portals_alerts"),
        ("organizations", "0006_phase3_portals_alerts"),
    ]

    operations = [
        migrations.CreateModel(
            name="Department",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="departments",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={
                "db_table": "department",
                "ordering": ["sort_order", "name"],
            },
        ),
        migrations.AddConstraint(
            model_name="department",
            constraint=models.UniqueConstraint(
                fields=("organization", "name"),
                name="uniq_department_name_per_org",
            ),
        ),
        migrations.RenameField(
            model_name="employee",
            old_name="department",
            new_name="department_name_legacy",
        ),
        migrations.AddField(
            model_name="employee",
            name="department",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="employees",
                to="employees.department",
            ),
        ),
        migrations.RunPython(seed_departments, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="employee",
            name="department_name_legacy",
        ),
    ]
