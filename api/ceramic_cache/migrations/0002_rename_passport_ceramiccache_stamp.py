# Generated by Django 4.1.5 on 2023-01-27 00:19

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("ceramic_cache", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="ceramiccache",
            old_name="passport",
            new_name="stamp",
        ),
    ]
