import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0055_walletgroup_models"),
    ]

    operations = [
        migrations.AlterField(
            model_name="accountapikeyanalytics",
            name="api_key",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="analytics",
                to="account.accountapikey",
            ),
        ),
    ]
