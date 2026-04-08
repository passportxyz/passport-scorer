from django.db import migrations

import account.models


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0055_walletgroup_models"),
    ]

    operations = [
        migrations.AlterField(
            model_name="walletgroupcommunityclaim",
            name="canonical_address",
            field=account.models.EthAddressField(db_index=True, max_length=42),
        ),
    ]
