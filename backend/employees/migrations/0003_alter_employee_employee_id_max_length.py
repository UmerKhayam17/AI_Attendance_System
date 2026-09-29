from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("employees", "0002_employee_created_at_employee_updated_at"),
    ]

    operations = [
        migrations.AlterField(
            model_name="employee",
            name="employee_id",
            field=models.CharField(max_length=40, unique=True),
        ),
    ]
