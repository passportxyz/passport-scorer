# Generated by Django 4.2.6 on 2024-10-21 20:57

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0037_customization_partner_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="accountapikey",
            name="historical_endpoint",
            field=models.BooleanField(default=False),
        ),
    ]
