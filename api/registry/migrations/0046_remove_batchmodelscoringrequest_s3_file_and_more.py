# Generated by Django 4.2.6 on 2025-05-20 12:34

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("registry", "0045_batchmodelscoringrequest_s3_file_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="batchmodelscoringrequest",
            name="s3_file",
        ),
        migrations.AlterField(
            model_name="batchmodelscoringrequest",
            name="s3_filename",
            field=models.CharField(max_length=100),
        ),
    ]
