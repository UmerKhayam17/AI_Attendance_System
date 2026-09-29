import django.db.models.deletion
from django.db import migrations, models


def assign_default_org(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    Camera = apps.get_model("recognition", "Camera")
    org = Organization.objects.filter(slug="default").first()
    if not org:
        org = Organization.objects.create(
            name="Default Organization",
            slug="default",
            org_type="company",
            timezone="Asia/Karachi",
            plan="starter",
            subscription_status="trialing",
            api_key="default-org-api-key-migrate-cam",
            is_active=True,
        )
    Camera.objects.filter(organization_id__isnull=True).update(organization=org)


class Migration(migrations.Migration):
    dependencies = [
        ("recognition", "0004_detection_snapshot"),
        ("organizations", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="camera",
            name="organization",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="cameras",
                to="organizations.organization",
            ),
        ),
        migrations.RunPython(assign_default_org, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="camera",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="cameras",
                to="organizations.organization",
            ),
        ),
    ]
