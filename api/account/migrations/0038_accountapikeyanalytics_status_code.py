# Generated by Django 4.2.6 on 2024-10-23 21:10

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0037_customization_partner_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="accountapikeyanalytics",
            name="status_code",
            field=models.IntegerField(
                db_index=True, help_text="HTTP status code of the response", null=True
            ),
        ),
    ]
