from django.test import TestCase, Client
from django.conf import settings
from django.urls import reverse
from cgrants.models import (
    Profile,
    Grant,
    GrantContributionIndex,
    Contribution,
    Subscription,
    SquelchProfile,
)


class CgrantsTest(TestCase):
    def setUp(self):
        self.client = Client()

        self.headers = {"HTTP_AUTHORIZATION": settings.CGRANTS_API_TOKEN}

        self.profile1 = Profile.objects.create(handle="user1")
        self.profile2 = Profile.objects.create(handle="user2")
        self.profile3 = Profile.objects.create(handle="user3")

        self.grant1 = Grant.objects.create(
            admin_profile=self.profile1, hidden=False, active=True, is_clr_eligible=True
        )

        self.subscription1 = Subscription.objects.create(
            grant=self.grant1, contributor_profile=self.profile1
        )
        Contribution.objects.create(subscription=self.subscription1)

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
        self.assertEqual(
            response.json(),
            {
                "num_grants_contribute_to": 1,
                "num_rounds_contribute_to": 0,
                "total_contribution_amount": "100.000000000000000000",
                "num_gr14_contributions": 0,
            },
        )

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

    def test_grantee_statistics_standard(self):
        # Standard case
        response = self.client.get(
            reverse("cgrants:grantee_statistics"),
            {"handle": "user1"},
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "num_owned_grants": 1,
                "num_grant_contributors": 1,
                "num_grants_in_eco_and_cause_rounds": 0,
                "total_contribution_amount": 0,
            },
        )

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
