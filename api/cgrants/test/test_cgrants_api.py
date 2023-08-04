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

        self.profile1 = Profile.objects.create(handle="user1", github_id=1)
        self.profile2 = Profile.objects.create(handle="user2", github_id=2)
        self.profile3 = Profile.objects.create(handle="user3", github_id=3)
        self.profile4 = Profile.objects.create(handle="user4", github_id=4)

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
                    amount=1,
                    ext_id="0xext_1",
                ),
                ProtocolContributions(
                    contributor=self.address,
                    project=project2,
                    round=round2,
                    amount=1,
                    ext_id="0xext_2",
                ),
                ProtocolContributions(
                    contributor=self.address,
                    project=project3,
                    round=round1,
                    amount=1,
                    ext_id="0xext_3",
                ),
                ProtocolContributions(
                    contributor=self.address,
                    project=project4,
                    round=round2,
                    amount=1,
                    ext_id="0xext_4",
                ),
                ProtocolContributions(
                    contributor=self.address,
                    project=project1,
                    round=round1,
                    amount=1,
                    ext_id="0xext_5",
                ),
                ProtocolContributions(
                    contributor=self.address,
                    project=project2,
                    round=round2,
                    amount=1,
                    ext_id="0xext_6",
                ),
                ProtocolContributions(
                    contributor=self.address,
                    project=project3,
                    round=round1,
                    amount=1,
                    ext_id="0xext_7",
                ),
                ProtocolContributions(
                    contributor=self.address,
                    project=project4,
                    round=round2,
                    amount=1,
                    ext_id="0xext_8",
                ),
                ProtocolContributions(
                    contributor=self.address,
                    project=project1,
                    round=round1,
                    amount=1,
                    ext_id="0xext_9",
                ),
                ProtocolContributions(
                    contributor=self.address,
                    project=project2,
                    round=round2,
                    amount=1,
                    ext_id="0xext_10",
                ),
            ]
        )

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

    def test_contributor_statistics(self):
        # Standard case
        response = self.client.get(
            reverse("cgrants:contributor_statistics"),
            {"handle": "user1"},
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
            {"handle": "user2"},
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
            {"handle": "user1"},
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
            {"handle": "user2"},
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
            {"handle": ""},
            **self.headers,
        )
        self.assertEqual(response.status_code, 400)  # Not found
        self.assertEqual(
            response.json(),
            {
                "error": "Bad request, 'handle' and 'github_id' parameter is missing or invalid. Either one is required."
            },
        )

    def test_contributor_statistics_squelched_profile(self):
        response = self.client.get(
            reverse("cgrants:contributor_statistics"),
            {"handle": self.profile3.handle},
            **self.headers,
        )

        print("response", response.json())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("num_gr14_contributions"), 0)

    def test_grantee_statistics_invalid_token(self):
        response = self.client.get(
            reverse("cgrants:contributor_statistics"),
            {"handle": self.profile1.handle},
            **{"HTTP_AUTHORIZATION": "invalidtoken"},
        )

        self.assertEqual(response.status_code, 401)

    def test_invalid_address_for_allo(self):
        response = self.client.get(
            reverse("cgrants:allo_contributor_statistics"),
            {"address": ""},
            **self.headers,
        )
        self.assertEqual(response.status_code, 400)  # Not found
        self.assertEqual(
            response.json(),
            {"error": "Bad request, 'address' parameter is missing or invalid"},
        )

    def test_missing_address_for_allo(self):
        response = self.client.get(
            reverse("cgrants:allo_contributor_statistics"),
            {},
            **self.headers,
        )
        self.assertEqual(response.status_code, 400)  # Not found
        self.assertEqual(
            response.json(),
            {"error": "Bad request, 'address' parameter is missing or invalid"},
        )

    def test_contributor_statistics_with_only_protocol_contributions(self):
        # Edge case: User has made no contributions
        response = self.client.get(
            reverse("cgrants:allo_contributor_statistics"),
            {"address": self.address},
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

    def test_contributor_statistics_by_github_id(self):
        # Standard case
        response = self.client.get(
            reverse("cgrants:contributor_statistics"),
            {"github_id": "1"},
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        output = response.json()
        self.assertEqual(output["num_grants_contribute_to"], 1)
        self.assertEqual(output["num_rounds_contribute_to"], 0)
        self.assertEqual(float(output["total_contribution_amount"]), 100.0)
        self.assertEqual(output["num_gr14_contributions"], 0)

    def test_contributor_statistics_no_contributions_by_github_id(self):
        # Edge case: User has made no contributions
        response = self.client.get(
            reverse("cgrants:contributor_statistics"),
            {"github_id": "2"},
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

    def test_grantee_statistics_by_github_id(self):
        response = self.client.get(
            reverse("cgrants:grantee_statistics"),
            {"github_id": "1"},
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        output = response.json()
        self.assertEqual(output["num_owned_grants"], 1)
        self.assertEqual(output["num_grant_contributors"], 1)
        self.assertEqual(output["num_grants_in_eco_and_cause_rounds"], 0)
        self.assertEqual(float(output["total_contribution_amount"]), 100.0)

    def test_grantee_statistics_no_grants_by_github_id(self):
        response = self.client.get(
            reverse("cgrants:grantee_statistics"),
            {"github_id": "2"},
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

    def test_invalid_github_id(self):
        response = self.client.get(
            reverse("cgrants:contributor_statistics"),
            {"github_id": ""},
            **self.headers,
        )
        self.assertEqual(response.status_code, 400)  # Not found
        self.assertEqual(
            response.json(),
            {
                "error": "Bad request, 'handle' and 'github_id' parameter is missing or invalid. Either one is required."
            },
        )

    def test_contributor_statistics_squelched_profile_by_github_id(self):
        response = self.client.get(
            reverse("cgrants:contributor_statistics"),
            {"github_id": self.profile3.github_id},
            **self.headers,
        )

        print("response", response.json())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("num_gr14_contributions"), 0)

    def test_grantee_statistics_invalid_token_by_github_id(self):
        response = self.client.get(
            reverse("cgrants:contributor_statistics"),
            {"github_id": self.profile1.github_id},
            **{"HTTP_AUTHORIZATION": "invalidtoken"},
        )

        self.assertEqual(response.status_code, 401)
