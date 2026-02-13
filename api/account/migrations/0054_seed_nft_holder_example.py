import json
from hashlib import sha256

from django.db import migrations

EXAMPLE_DEFINITION = {
    "name": "ExampleNFT",
    "condition": {
        "contracts": [
            {
                "address": "0x0000000000000000000000000000000000000000",
                "chainId": 1,
                "standard": "ERC-721",
            }
        ]
    },
}

EXAMPLE_PROVIDER_ID = "NFTHolder#ExampleNFT#{}".format(
    sha256(json.dumps(EXAMPLE_DEFINITION, sort_keys=True).encode("utf8")).hexdigest()[
        0:8
    ]
)


def seed_nft_example(apps, schema_editor):
    CustomPlatform = apps.get_model("account", "CustomPlatform")
    CustomCredentialRuleset = apps.get_model("account", "CustomCredentialRuleset")

    CustomPlatform.objects.get_or_create(
        name="NFTHolder",
        defaults={
            "platform_type": "NFT",
            "is_evm": True,
            "display_name": "NFT Holder",
            "description": "Verify NFT ownership on EVM chains",
            "icon_url": "./assets/nftHolderStampIcon.svg",
        },
    )

    # NOTE: provider_id is computed manually to match CustomCredentialRuleset.save()
    # because RunPython historical models do not call custom save() methods.
    CustomCredentialRuleset.objects.get_or_create(
        provider_id=EXAMPLE_PROVIDER_ID,
        defaults={
            "credential_type": "NFT",
            "definition": EXAMPLE_DEFINITION,
            "name": "ExampleNFT",
        },
    )


def reverse_seed(apps, schema_editor):
    """Delete only the specific seeded records, not all NFT records.

    If CustomCredential records reference these, this will raise
    ProtectedError -- delete those FK records first.
    """
    CustomPlatform = apps.get_model("account", "CustomPlatform")
    CustomCredentialRuleset = apps.get_model("account", "CustomCredentialRuleset")
    # Scoped to exact seeded records -- won't delete admin-created NFT records
    CustomCredentialRuleset.objects.filter(provider_id=EXAMPLE_PROVIDER_ID).delete()
    CustomPlatform.objects.filter(name="NFTHolder").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0053_add_custom_platform_is_evm"),
    ]

    operations = [
        migrations.RunPython(seed_nft_example, reverse_seed),
    ]
