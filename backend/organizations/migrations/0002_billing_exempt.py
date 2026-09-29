from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="billing_exempt",
            field=models.BooleanField(
                default=False,
                help_text="If true, plan is granted by the platform and Stripe is not required.",
            ),
        ),
        migrations.AddField(
            model_name="organization",
            name="created_via",
            field=models.CharField(
                choices=[("signup", "Self signup"), ("platform", "Super admin")],
                default="signup",
                max_length=20,
            ),
        ),
    ]
