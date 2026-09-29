import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("recognition", "0006_trust_the_match"),
        ("employees", "0005_employee_shift"),
        ("organizations", "0005_weekend_days"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MatchReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("camera_name", models.CharField(blank=True, max_length=100)),
                ("image", models.ImageField(blank=True, null=True, upload_to="reviews/%Y/%m/%d/")),
                ("confidence", models.FloatField(default=0.0)),
                ("second_best", models.FloatField(blank=True, null=True)),
                (
                    "reason",
                    models.CharField(
                        choices=[("low_confidence", "Low confidence"), ("ambiguous", "Ambiguous identity")],
                        default="low_confidence",
                        max_length=32,
                    ),
                ),
                ("suggested_employee_id", models.CharField(blank=True, max_length=40)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("confirmed", "Confirmed"),
                            ("rejected", "Rejected"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("track_id", models.IntegerField(blank=True, null=True)),
                ("source", models.CharField(default="cctv", max_length=20)),
                ("notes", models.TextField(blank=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("attendance_action", models.CharField(blank=True, max_length=32)),
                ("detected_at", models.DateTimeField(auto_now_add=True)),
                (
                    "camera",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="match_reviews",
                        to="recognition.camera",
                    ),
                ),
                (
                    "employee",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="match_reviews",
                        to="employees.employee",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="match_reviews",
                        to="organizations.organization",
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="match_reviews",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "match_review",
                "ordering": ["-detected_at"],
            },
        ),
    ]
