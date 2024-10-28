import pytest
from django.conf import settings
from django.test import Client

from account.models import Community
from registry.weight_models import WeightConfiguration, WeightConfigurationItem
from scorer_weighted.models import BinaryWeightedScorer, Scorer

pytestmark = pytest.mark.django_db  # noqa: F821

client = Client()


class TestGetWeights:
    base_url = "/ceramic-cache"

    def test_get_weights(
        self,
        scorer_account,
    ):
        config = WeightConfiguration.objects.create(
            version="v1",
            threshold=20.0,
            active=True,
            description="Test",
        )
        scorer_weights = {"provider-1": 0.5, "provider-2": 0.5}
        for provider, weight in scorer_weights.items():
            WeightConfigurationItem.objects.create(
                weight_configuration=config,
                provider=provider,
                weight=float(weight),
            )

        scorer = BinaryWeightedScorer.objects.create(
            type=Scorer.Type.WEIGHTED_BINARY, weights=scorer_weights
        )

        community = Community.objects.create(
            name="Community 1",
            description="Community 1 - testing",
            account=scorer_account,
            scorer=scorer,
        )

        settings.CERAMIC_CACHE_SCORER_ID = community.pk
        response = client.get(
            f"{self.base_url}/weights",
        )

        returned_weights = response.json()
        assert response.status_code == 200
        assert scorer_weights == returned_weights
