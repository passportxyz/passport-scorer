# Generated by Django 4.2.6 on 2024-09-17 15:21

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0036_customization_show_explanation_panel"),
    ]

    operations = [
        migrations.AddField(
            model_name="customization",
            name="partner_name",
            field=models.CharField(
                default="Partner",
                help_text="The name of the partner, e.g. Gitcoin",
                max_length=100,
            ),
        ),
    ]