from datetime import time

from django.db import migrations, models
import django.db.models.deletion


def seed_default_shifts(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    Shift = apps.get_model("organizations", "Shift")
    for org in Organization.objects.all():
        if Shift.objects.filter(organization=org).exists():
            continue
        Shift.objects.create(
            organization=org,
            name="General",
            start_time=org.work_start or time(9, 0),
            late_after=org.late_after or time(9, 30),
            end_time=time(18, 0),
            is_default=True,
            is_active=True,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0003_platform_config"),
    ]

    operations = [
        migrations.CreateModel(
            name="Shift",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80)),
                ("start_time", models.TimeField()),
                ("late_after", models.TimeField()),
                ("end_time", models.TimeField()),
                ("is_default", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="shifts",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={
                "db_table": "org_shift",
                "ordering": ["-is_default", "start_time", "name"],
            },
        ),
        migrations.AddConstraint(
            model_name="shift",
            constraint=models.UniqueConstraint(fields=("organization", "name"), name="uniq_shift_name_per_org"),
        ),
        migrations.RunPython(seed_default_shifts, migrations.RunPython.noop),
    ]
