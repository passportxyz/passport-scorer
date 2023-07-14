from cgrants.models import (
    Contribution,
    Grant,
    GrantContributionIndex,
    Profile,
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

    def test_contributor_statistics_squelched_profile(self):
        response = self.client.get(
            reverse("cgrants:contributor_statistics"),
            {"handle": self.profile3.handle},
            **self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("num_gr14_contributions"), 0)

    def test_grantee_statistics_invalid_token(self):
        response = self.client.get(
            reverse("cgrants:contributor_statistics"),
            {"handle": self.profile1.handle},
            **{"HTTP_AUTHORIZATION": "invalidtoken"},
        )

        self.assertEqual(response.status_code, 401)
