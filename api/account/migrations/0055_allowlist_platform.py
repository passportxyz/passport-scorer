from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0054_seed_nft_holder_example"),
    ]

    operations = [
        migrations.AddField(
            model_name="allowlist",
            name="platform",
            field=models.ForeignKey(
                blank=True,
                help_text="Optional: group this AllowList under a CustomPlatform",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="account.customplatform",
            ),
        ),
    ]
