from cgrants.models import (
    Contribution,
    Grant,
    GrantContributionIndex,
    Profile,
    ProtocolContributions,
    SquelchProfile,
    Subscription,
)
from django.conf import settings
from django.test import Client, TestCase
from django.urls import reverse


class CgrantsTest(TestCase):
    def setUp(self):
        self.client = Client()

        self.headers = {"HTTP_AUTHORIZATION": settings.CGRANTS_API_TOKEN}

        self.profile1 = Profile.objects.create(handle="user1")
        self.profile2 = Profile.objects.create(handle="user2")
        self.profile3 = Profile.objects.create(handle="user3")
        self.profile4 = Profile.objects.create(handle="user4")

        self.grant1 = Grant.objects.create(
            admin_profile=self.profile1, hidden=False, active=True, is_clr_eligible=True
        )

        self.subscription = Subscription.objects.create(
            grant=self.grant1, contributor_profile=self.profile4, is_mainnet=True
        )
        Contribution.objects.create(
            subscription=self.subscription, success=True, amount_per_period_usdt="100"
        )

        # create test grant contribution indexes
        GrantContributionIndex.objects.create(
            profile=self.profile1, grant=self.grant1, amount=100
        )

        SquelchProfile.objects.create(profile=self.profile3, active=True)

        self.address = "0x12345"
        project1 = "0xprj_1"
        project2 = "0xprj_2"
        project3 = "0xprj_3"
        project4 = "0xprj_4"
        round1 = "0xround_1"
        round2 = "0xround_2"

        ProtocolContributions.objects.bulk_create(
            [
                ProtocolContributions(
                    contributor=self.address,
                    project=project1,
                    round=round1,
                    amount_usd=1,
                ),
                ProtocolContributions(
                    contributor=self.address,
                    project=project2,
                    round=round2,
                    amount_usd=1,
                ),
                ProtocolContributions(
                    contributor=self.address,
                    project=project3,
                    round=round1,
                    amount_usd=1,
                ),
                ProtocolContributions(
                    contributor=self.address,
                    project=project4,
                    round=round2,
                    amount_usd=1,
                ),
                ProtocolContributions(
                    contributor=self.address,
                    project=project1,
                    round=round1,
                    amount_usd=1,
                ),
                ProtocolContributions(
                    contributor=self.address,
                    project=project2,
                    round=round2,
                    amount_usd=1,
                ),
                ProtocolContributions(
                    contributor=self.address,
                    project=project3,
                    round=round1,
                    amount_usd=1,
                ),
                ProtocolContributions(
                    contributor=self.address,
                    project=project4,
                    round=round2,
                    amount_usd=1,
                ),
                ProtocolContributions(
                    contributor=self.address,
                    project=project1,
                    round=round1,
                    amount_usd=1,
                ),
                ProtocolContributions(
                    contributor=self.address,
                    project=project2,
                    round=round2,
                    amount_usd=1,
                ),
            ]
        )

        ProtocolContributions.objects.bulk_create(
            [
                ProtocolContributions(
                    contributor="0xsome_{i}",
                    project="0xprj_{i}",
                    round="0xround_{i}",
                    amount_usd=1,
                )
                for i in range(200)
            ]
        )

    def test_contributor_statistics(self):
        # Standard case
        response = self.client.get(
            reverse("cgrants:contributor_statistics"),
            {"handle": "user1", "address": "0x_bad_address"},
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        output = response.json()
        self.assertEqual(output["num_grants_contribute_to"], 1)
        self.assertEqual(output["num_rounds_contribute_to"], 0)
        self.assertEqual(float(output["total_contribution_amount"]), 100.0)
        self.assertEqual(output["num_gr14_contributions"], 0)

    def test_contributor_statistics_no_contributions(self):
        # Edge case: User has made no contributions
        response = self.client.get(
            reverse("cgrants:contributor_statistics"),
            {"handle": "user2", "address": "0x_bad_address"},
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "num_grants_contribute_to": 0,
                "num_rounds_contribute_to": 0,
                "total_contribution_amount": 0,
                "num_gr14_contributions": 0,
            },
        )

    def test_grantee_statistics(self):
        response = self.client.get(
            reverse("cgrants:grantee_statistics"),
            {"handle": "user1", "address": "0x_bad_address"},
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        output = response.json()
        self.assertEqual(output["num_owned_grants"], 1)
        self.assertEqual(output["num_grant_contributors"], 1)
        self.assertEqual(output["num_grants_in_eco_and_cause_rounds"], 0)
        self.assertEqual(float(output["total_contribution_amount"]), 100.0)

    def test_grantee_statistics_no_grants(self):
        response = self.client.get(
            reverse("cgrants:grantee_statistics"),
            {"handle": "user2", "address": "0x_bad_address"},
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "num_owned_grants": 0,
                "num_grant_contributors": 0,
                "num_grants_in_eco_and_cause_rounds": 0,
                "total_contribution_amount": 0,
            },
        )

    def test_invalid_handle(self):
        response = self.client.get(
            reverse("cgrants:contributor_statistics"),
            {"handle": "", "address": "0x_bad_address"},
            **self.headers,
        )
        self.assertEqual(response.status_code, 400)  # Not found
        self.assertEqual(
            response.json(),
            {"error": "Bad request, 'handle' parameter is missing or invalid"},
        )

    def test_invalid_address(self):
        response = self.client.get(
            reverse("cgrants:contributor_statistics"),
            {"handle": "some_handle", "address": ""},
            **self.headers,
        )
        self.assertEqual(response.status_code, 400)  # Not found
        self.assertEqual(
            response.json(),
            {"error": "Bad request, 'address' parameter is missing or invalid"},
        )

    def test_missing_address(self):
        response = self.client.get(
            reverse("cgrants:contributor_statistics"),
            {"handle": "some_handle"},
            **self.headers,
        )
        self.assertEqual(response.status_code, 400)  # Not found
        self.assertEqual(
            response.json(),
            {"error": "Bad request, 'address' parameter is missing or invalid"},
        )

    def test_contributor_statistics_squelched_profile(self):
        response = self.client.get(
            reverse("cgrants:contributor_statistics"),
            {"handle": self.profile3.handle, "address": "0x_bad_address"},
            **self.headers,
        )

        print("response", response.json())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("num_gr14_contributions"), 0)

    def test_grantee_statistics_invalid_token(self):
        response = self.client.get(
            reverse("cgrants:contributor_statistics"),
            {"handle": self.profile1.handle, "address": "0x_bad_address"},
            **{"HTTP_AUTHORIZATION": "invalidtoken"},
        )

        self.assertEqual(response.status_code, 401)

    def test_contributor_statistics_with_cgrants_and_protocol_contributions(self):
        # Standard case
        response = self.client.get(
            reverse("cgrants:contributor_statistics"),
            {"handle": "user1", "address": self.address},
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "num_grants_contribute_to": 5,
                "num_rounds_contribute_to": 2,
                "total_contribution_amount": "110",
                "num_gr14_contributions": 0,
            },
        )

    def test_contributor_statistics_with_only_protocol_contributions(self):
        # Edge case: User has made no contributions
        response = self.client.get(
            reverse("cgrants:contributor_statistics"),
            {"handle": "user2", "address": self.address},
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "num_grants_contribute_to": 4,
                "num_rounds_contribute_to": 2,
                "total_contribution_amount": "10",
                "num_gr14_contributions": 0,
            },
        )
