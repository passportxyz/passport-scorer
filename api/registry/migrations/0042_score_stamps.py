# Generated by Django 4.2.6 on 2024-11-28 20:07

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("registry", "0041_weightconfiguration_description"),
    ]

    operations = [
        migrations.AddField(
            model_name="score",
            name="stamps",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
