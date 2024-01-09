""" Test file for cgrants contribution API """

import pytest
from account.test.conftest import scorer_account, scorer_user
from cgrants.api import _get_contributor_statistics_for_protocol
from cgrants.models import (
    GrantContributionIndex,
    ProtocolContributions,
    RoundMapping,
    SquelchedAccounts,
)
from cgrants.test.test_add_address_to_contribution_index import (
    generate_bulk_cgrant_data,
)
from django.conf import settings
from django.test import Client
from django.urls import reverse
from numpy import add

pytestmark = pytest.mark.django_db


client = Client()
headers = {"HTTP_AUTHORIZATION": settings.CGRANTS_API_TOKEN}


class TestCombinedContributionsApi:
    """Test the combined contributions API"""

    def test_combined_contributor_statistics(
        self,
        generate_bulk_cgrant_data,
        grant_contribution_indices_with_address,
        scorer_account,
        scorer_user,
        protocol_contributions,
    ):
        for contrib in GrantContributionIndex.objects.all()[0:5]:
            contrib.contributor_address = scorer_account.address
            contrib.amount = 5
            contrib.save()

        response = client.get(
            reverse("cgrants:contributor_statistics"),
            {"address": scorer_account.address},
            **headers,
        )
        assert response.status_code == 200
        assert response.json() == {
            "total_contribution_amount": 35.0,
            "num_grants_contribute_to": 9.0,
        }

    def test_combined_contributor_statistics_no_contributions(self):
        response = client.get(
            reverse("cgrants:contributor_statistics"),
            {"address": "0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc"},
            **headers,
        )
        assert response.status_code == 200

        assert response.json() == {
            "total_contribution_amount": 0.0,
            "num_grants_contribute_to": 0.0,
        }

    def test_invalid_address(self):
        response = client.get(
            reverse("cgrants:contributor_statistics"),
            {"address": "0x9965507D1a55bcC2695C58ba16FB37d819BAAAAA"},
            **headers,
        )
        assert response.status_code == 400

        assert response.json() == {"detail": "Invalid address."}

    def test_combined_contributor_invalid_token(self):
        response = client.get(
            reverse("cgrants:contributor_statistics"),
            {"address": "0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc"},
            **{"HTTP_AUTHORIZATION": "invalidtoken"},
        )

        assert response.status_code == 401

    def test_missing_address(self):
        response = client.get(
            reverse("cgrants:contributor_statistics"),
            {},
            **headers,
        )

        assert response.status_code == 400

        assert response.json() == {
            "error": "Bad request, 'address' is missing or invalid. A valid address is required."
        }

    def test_contribution_below_threshold(self, protocol_contributions, scorer_account):
        for contrib in ProtocolContributions.objects.filter(
            contributor=scorer_account.address
        ):
            contrib.amount = 0.5
            contrib.save()

        response = client.get(
            reverse("cgrants:contributor_statistics"),
            {"address": scorer_account.address},
            **headers,
        )

        assert response.status_code == 200
        assert response.json() == {
            "num_grants_contribute_to": 0.0,
            "total_contribution_amount": 0.0,
        }

    def test_only_protocol_contributions(self, protocol_contributions, scorer_account):
        response = client.get(
            reverse("cgrants:contributor_statistics"),
            {"address": scorer_account.address},
            **headers,
        )

        assert response.status_code == 200
        assert response.json() == {
            "num_grants_contribute_to": 4.0,
            "total_contribution_amount": 10.0,
        }

    def test_depegged_protocol_contribution(self, scorer_account):
        ProtocolContributions.objects.create(
            contributor=scorer_account.address,
            project="proj",
            round=1,
            amount=0.99897,
            ext_id=scorer_account.address,
        )

        response = client.get(
            reverse("cgrants:contributor_statistics"),
            {"address": scorer_account.address},
            **headers,
        )

        assert response.status_code == 200
        assert response.json() == {
            "num_grants_contribute_to": 1.0,
            "total_contribution_amount": 1.0,
        }

    def test_squelched_profile_by_round(self, scorer_account):
        ProtocolContributions.objects.create(
            contributor=scorer_account.address,
            project="proj",
            round="0x",
            amount=0.99897,
            ext_id=scorer_account.address,
        )

        SquelchedAccounts.objects.create(
            address=scorer_account.address,
            score_when_squelched=0.0,
            sybil_signal=True,
            round_number=1,
        )

        RoundMapping.objects.create(
            round_eth_address="0x",
            round_number=1,
        )

        user_contributions = _get_contributor_statistics_for_protocol(
            scorer_account.address
        )

        assert user_contributions == {
            "num_grants_contribute_to": 0,
            "total_contribution_amount": 0,
        }

    def test_squelched_profile_in_one_round_but_not_other(self, scorer_account):
        ProtocolContributions.objects.create(
            contributor=scorer_account.address,
            project="proj",
            round="0x",
            amount=1,
            ext_id="0x",
        )

        ProtocolContributions.objects.create(
            contributor=scorer_account.address,
            project="proj1",
            round="0x1",
            amount=1,
            ext_id="0x1",
        )

        SquelchedAccounts.objects.create(
            address=scorer_account.address,
            score_when_squelched=0.0,
            sybil_signal=True,
            round_number=1,
        )

        RoundMapping.objects.create(
            round_eth_address="0x",
            round_number=1,
        )

        RoundMapping.objects.create(
            round_eth_address="0x1",
            round_number=2,
        )

        user_contributions = _get_contributor_statistics_for_protocol(
            scorer_account.address
        )

        assert user_contributions == {
            "num_grants_contribute_to": 1,
            "total_contribution_amount": 1,
        }
