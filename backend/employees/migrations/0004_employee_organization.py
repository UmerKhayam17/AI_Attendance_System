import django.db.models.deletion
from django.db import migrations, models


def assign_default_org(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    Employee = apps.get_model("employees", "Employee")
    org = Organization.objects.filter(slug="default").first()
    if not org:
        org = Organization.objects.create(
            name="Default Organization",
            slug="default",
            org_type="company",
            timezone="Asia/Karachi",
            plan="starter",
            subscription_status="trialing",
            api_key="default-org-api-key-migrate",
            is_active=True,
        )
    Employee.objects.filter(organization_id__isnull=True).update(organization=org)


class Migration(migrations.Migration):
    dependencies = [
        ("employees", "0003_alter_employee_employee_id_max_length"),
        ("organizations", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="employee",
            name="organization",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="employees",
                to="organizations.organization",
            ),
        ),
        migrations.RunPython(assign_default_org, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="employee",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="employees",
                to="organizations.organization",
            ),
        ),
        migrations.AlterField(
            model_name="employee",
            name="employee_id",
            field=models.CharField(max_length=40),
        ),
        migrations.AlterField(
            model_name="employee",
            name="email",
            field=models.EmailField(max_length=254),
        ),
        migrations.AddConstraint(
            model_name="employee",
            constraint=models.UniqueConstraint(
                fields=("organization", "employee_id"),
                name="uniq_employee_id_per_org",
            ),
        ),
        migrations.AddConstraint(
            model_name="employee",
            constraint=models.UniqueConstraint(
                fields=("organization", "email"),
                name="uniq_employee_email_per_org",
            ),
        ),
    ]
