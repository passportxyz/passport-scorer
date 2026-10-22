from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0055_walletgroup_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="featuredcampaign",
            name="audience_label",
            field=models.CharField(
                blank=True,
                help_text="Short label on the card, e.g. 'For builders'. Leave blank for none.",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="featuredcampaign",
            name="details_text",
            field=models.TextField(
                blank=True,
                help_text="Text for the 'Learn more' panel. Leave blank to hide the button.",
            ),
        ),
    ]
