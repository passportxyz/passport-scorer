import random

import pytest
from cgrants.models import (
    Contribution,
    Grant,
    GrantContributionIndex,
    Profile,
    Subscription,
)
from django.core.management import call_command
from faker import Faker

pytestmark = pytest.mark.django_db


@pytest.fixture
def generate_test_data():
    fake = Faker()
    Faker.seed(4321)  # for reproducibility
    random.seed(4321)  # for reproducibility

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

    grant_contribution_indices = [
        GrantContributionIndex(
            profile=random.choice(profiles),
            contribution=random.choice(contributions),
            grant=random.choice(grants),
            round_num=fake.random_int(min=1, max=10),
            amount=fake.random_number(digits=2),
        )
        for _ in range(300)
    ]
    GrantContributionIndex.objects.bulk_create(grant_contribution_indices)

    return {
        "profiles": profiles,
        "grants": grants,
        "subscriptions": subscriptions,
        "contributions": contributions,
        "grant_contribution_indices": grant_contribution_indices,
    }


class TestContribAggregation:
    def test_addresses_are_properly_added(self, generate_test_data):
        assert (
            GrantContributionIndex.objects.filter(contributor_address=None).count()
            == 300
        )
        call_command("add_address_to_contribution_index")
        assert (
            GrantContributionIndex.objects.filter(contributor_address=None).count() == 0
        )
        assert (
            GrantContributionIndex.objects.exclude(contributor_address=None).count()
            == 300
        )

    def test_saving_address_with_bad_data(self, generate_test_data):
        bad_contributions = Contribution.objects.all()[0:5]
        for contrib in bad_contributions:
            contrib.data = {"fields": {}}
            contrib.save()

        call_command("add_address_to_contribution_index")

        bad_grant_contribution_indices = GrantContributionIndex.objects.filter(
            contribution_id__in=bad_contributions
        )
        assert (
            bad_grant_contribution_indices.count()
            == GrantContributionIndex.objects.filter(contributor_address=None).count()
        )
