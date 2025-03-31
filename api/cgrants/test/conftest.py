import random

import pytest
from faker import Faker

from cgrants.models import (
    Contribution,
    Grant,
    GrantContributionIndex,
    Profile,
    ProtocolContributions,
    Subscription,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def generate_bulk_cgrant_data():
    fake = Faker()
    Faker.seed(4321)
    random.seed(4321)

    profiles = [
        Profile(
            handle=fake.user_name(),
            github_id=fake.random_int(min=1, max=100000),
            notes=fake.text(),
            data={"extra": fake.word()},
        )
        for _ in range(100)
    ]
    Profile.objects.bulk_create(profiles)

    grants = [
        Grant(
            admin_profile=random.choice(profiles),
            hidden=fake.boolean(),
            active=fake.boolean(),
            is_clr_eligible=fake.boolean(),
            data={"extra": fake.word()},
        )
        for _ in range(50)
    ]
    Grant.objects.bulk_create(grants)

    subscriptions = [
        Subscription(
            grant=random.choice(grants),
            contributor_profile=random.choice(profiles),
            is_mainnet=fake.boolean(),
            data={"extra": fake.word()},
        )
        for _ in range(150)
    ]
    Subscription.objects.bulk_create(subscriptions)

    contributions = [
        Contribution(
            subscription=random.choice(subscriptions),
            success=fake.boolean(),
            amount_per_period_usdt=fake.random_number(digits=2),
            data={
                "fields": {
                    "originated_address": f"0x{fake.random_number(3)}5507D1a55bcC2695C58ba16FB37d819B0A4dc",
                    "grant": random.choice(grants).pk,
                }
            },
        )
        for _ in range(300)
    ]
    Contribution.objects.bulk_create(contributions)

    return {
        "profiles": profiles,
        "grants": grants,
        "subscriptions": subscriptions,
        "contributions": contributions,
    }


@pytest.fixture
def grant_contribution_indices_no_address(generate_bulk_cgrant_data):
    fake = Faker()
    grant_contribution_indices = [
        GrantContributionIndex(
            profile=random.choice(generate_bulk_cgrant_data["profiles"]),
            contribution=random.choice(generate_bulk_cgrant_data["contributions"]),
            grant=random.choice(generate_bulk_cgrant_data["grants"]),
            round_num=fake.random_int(min=1, max=10),
            amount=fake.random_number(digits=2),
        )
        for _ in range(300)
    ]
    GrantContributionIndex.objects.bulk_create(grant_contribution_indices)


@pytest.fixture
def grant_contribution_indices_with_address(generate_bulk_cgrant_data):
    fake = Faker()
    random_contrib = random.choice(generate_bulk_cgrant_data["contributions"])
    grant_contribution_indices = [
        GrantContributionIndex(
            profile=random.choice(generate_bulk_cgrant_data["profiles"]),
            contribution=random_contrib,
            grant=random.choice(generate_bulk_cgrant_data["grants"]),
            round_num=fake.random_int(min=1, max=10),
            amount=fake.random_number(digits=2),
            contributor_address=random_contrib.data["fields"]["originated_address"],
        )
        for _ in range(300)
    ]
    return GrantContributionIndex.objects.bulk_create(grant_contribution_indices)


@pytest.fixture
def protocol_contributions(scorer_account, scorer_user):
    address = scorer_account.address
    project1 = "0xprj_1"
    project2 = "0xprj_2"
    project3 = "0xprj_3"
    project4 = "0xprj_4"
    round1 = "0xround_1"
    round2 = "0xround_2"

    ProtocolContributions.objects.bulk_create(
        [
            ProtocolContributions(
                contributor=f"0xsome_{i}",
                project=f"0xprj_{i}",
                round=f"0xround_{i}",
                amount=1,
                ext_id=f"0xext_batch2_{i}",
            )
            for i in range(200)
        ]
    )

    return ProtocolContributions.objects.bulk_create(
        [
            ProtocolContributions(
                contributor=address,
                project=project1,
                round=round1,
                amount=1,
                ext_id="0xext_1",
            ),
            ProtocolContributions(
                contributor=address,
                project=project2,
                round=round2,
                amount=1,
                ext_id="0xext_2",
            ),
            ProtocolContributions(
                contributor=address,
                project=project3,
                round=round1,
                amount=1,
                ext_id="0xext_3",
            ),
            ProtocolContributions(
                contributor=address,
                project=project4,
                round=round2,
                amount=1,
                ext_id="0xext_4",
            ),
            ProtocolContributions(
                contributor=address,
                project=project1,
                round=round1,
                amount=1,
                ext_id="0xext_5",
            ),
            ProtocolContributions(
                contributor=address,
                project=project2,
                round=round2,
                amount=1,
                ext_id="0xext_6",
            ),
            ProtocolContributions(
                contributor=address,
                project=project3,
                round=round1,
                amount=1,
                ext_id="0xext_7",
            ),
            ProtocolContributions(
                contributor=address,
                project=project4,
                round=round2,
                amount=1,
                ext_id="0xext_8",
            ),
            ProtocolContributions(
                contributor=address,
                project=project1,
                round=round1,
                amount=1,
                ext_id="0xext_9",
            ),
            ProtocolContributions(
                contributor=address,
                project=project2,
                round=round2,
                amount=1,
                ext_id="0xext_10",
            ),
            # Ignored because the amount is too low
            ProtocolContributions(
                contributor=address,
                project=project1,
                round=round1,
                amount=0.5,
                ext_id="0xext_11",
            ),
        ]
    )
