from django.db import migrations, models


def copy_mean_into_embeddings(apps, schema_editor):
    FaceEnrollment = apps.get_model("recognition", "FaceEnrollment")
    for row in FaceEnrollment.objects.exclude(embedding=None):
        if row.embeddings:
            continue
        row.embeddings = [row.embedding]
        row.save(update_fields=["embeddings"])


class Migration(migrations.Migration):
    dependencies = [
        ("recognition", "0005_camera_organization"),
    ]

    operations = [
        migrations.AddField(
            model_name="camera",
            name="zone",
            field=models.CharField(
                choices=[
                    ("mixed", "Mixed (check-in then check-out)"),
                    ("entry", "Entry (check-in only)"),
                    ("exit", "Exit (check-out only)"),
                    ("interior", "Interior (check-in if missing, never check-out)"),
                ],
                default="mixed",
                help_text="Controls whether this camera can check people in, out, or both.",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="faceenrollment",
            name="embeddings",
            field=models.JSONField(
                blank=True,
                help_text="Per-pose ArcFace vectors used for nearest-neighbor matching.",
                null=True,
            ),
        ),
        migrations.RunPython(copy_mean_into_embeddings, migrations.RunPython.noop),
    ]
