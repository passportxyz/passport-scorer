from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0055_walletgroup_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="accountapikey",
            name="linked_wallet_breakdown",
            field=models.BooleanField(default=False),
        ),
    ]
