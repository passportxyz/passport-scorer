""" Test file for cgrants address aggregation """

import pytest
from cgrants.models import Contribution, GrantContributionIndex
from cgrants.test.conftest import (
    generate_bulk_cgrant_data,
    grant_contribution_indices_no_address,
)
from django.core.management import call_command

pytestmark = pytest.mark.django_db


class TestContribAggregation:
    """Test for cgrants address aggregation"""

    def test_addresses_are_properly_added(
        self, generate_bulk_cgrant_data, grant_contribution_indices_no_address
    ):
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

    def test_saving_address_with_bad_data(
        self, generate_bulk_cgrant_data, grant_contribution_indices_no_address
    ):
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
            == GrantContributionIndex.objects.filter(
                contribution__in=bad_contributions
            ).count()
        )
