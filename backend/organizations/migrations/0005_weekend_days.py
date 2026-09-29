from django.db import migrations, models


def fill_weekends(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    for org in Organization.objects.all():
        if not org.weekend_days:
            org.weekend_days = [5, 6]
            org.save(update_fields=["weekend_days"])


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0004_shift"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="weekend_days",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Python weekdays that are off: 0=Mon … 6=Sun. Default Sat+Sun.",
            ),
        ),
        migrations.RunPython(fill_weekends, migrations.RunPython.noop),
    ]
