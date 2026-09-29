import secrets

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


def create_default_org(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    Organization.objects.get_or_create(
        slug="default",
        defaults={
            "name": "Default Organization",
            "org_type": "company",
            "timezone": "Asia/Karachi",
            "plan": "starter",
            "subscription_status": "trialing",
            "api_key": secrets.token_urlsafe(32),
            "is_active": True,
        },
    )


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Organization",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("slug", models.SlugField(max_length=220, unique=True)),
                ("org_type", models.CharField(choices=[("company", "Company"), ("school", "School")], default="company", max_length=20)),
                ("timezone", models.CharField(default="Asia/Karachi", max_length=64)),
                ("work_start", models.TimeField(default="09:00:00")),
                ("late_after", models.TimeField(default="09:30:00")),
                ("is_active", models.BooleanField(default=True)),
                ("webhook_url", models.URLField(blank=True)),
                ("webhook_secret", models.CharField(blank=True, max_length=128)),
                ("api_key", models.CharField(blank=True, max_length=64, unique=True)),
                ("stripe_customer_id", models.CharField(blank=True, max_length=80)),
                ("stripe_subscription_id", models.CharField(blank=True, max_length=80)),
                ("plan", models.CharField(default="starter", max_length=20)),
                ("subscription_status", models.CharField(default="trialing", max_length=20)),
                ("current_period_end", models.DateTimeField(blank=True, null=True)),
                ("trial_ends_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "organization",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="Membership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("owner", "Owner"), ("admin", "Admin"), ("operator", "Operator"), ("viewer", "Viewer")], max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to="organizations.organization",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "membership",
                "ordering": ["id"],
                "unique_together": {("user", "organization")},
            },
        ),
        migrations.CreateModel(
            name="Invite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(max_length=254)),
                ("role", models.CharField(choices=[("owner", "Owner"), ("admin", "Admin"), ("operator", "Operator"), ("viewer", "Viewer")], max_length=20)),
                ("token", models.CharField(max_length=64, unique=True)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("expires_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "invited_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sent_invites",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invites",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={
                "db_table": "org_invite",
                "ordering": ["-created_at"],
            },
        ),
        migrations.RunPython(create_default_org, migrations.RunPython.noop),
    ]
