# Generated migration for adding resource_needs field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0002_add_description_supervisor"),
    ]

    operations = [
        migrations.AddField(
            model_name="maiaproject",
            name="resource_needs",
            field=models.TextField(blank=True, null=True, verbose_name="resource_needs"),
        ),
    ]
