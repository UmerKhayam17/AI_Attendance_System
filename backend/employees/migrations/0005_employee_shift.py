import django.db.models.deletion
from django.db import migrations, models


def assign_default_shifts(apps, schema_editor):
    Employee = apps.get_model("employees", "Employee")
    Shift = apps.get_model("organizations", "Shift")
    defaults = {
        shift.organization_id: shift
        for shift in Shift.objects.filter(is_default=True)
    }
    for employee in Employee.objects.filter(shift_id__isnull=True):
        shift = defaults.get(employee.organization_id)
        if shift:
            employee.shift_id = shift.id
            employee.save(update_fields=["shift_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("employees", "0004_employee_organization"),
        ("organizations", "0004_shift"),
    ]

    operations = [
        migrations.AddField(
            model_name="employee",
            name="shift",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="employees",
                to="organizations.shift",
            ),
        ),
        migrations.RunPython(assign_default_shifts, migrations.RunPython.noop),
    ]
