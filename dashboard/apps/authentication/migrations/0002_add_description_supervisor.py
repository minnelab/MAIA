# Generated migration for adding description and supervisor fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='maiaproject',
            name='description',
            field=models.TextField(blank=True, null=True, verbose_name='description'),
        ),
        migrations.AddField(
            model_name='maiaproject',
            name='supervisor',
            field=models.EmailField(max_length=150, null=True, blank=True, verbose_name='supervisor'),
        ),
    ]
