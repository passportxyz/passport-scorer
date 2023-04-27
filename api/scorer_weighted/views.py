import api_logging as logging
from scorer_weighted.models import WeightedScorer

# from django_filters.rest_framework import DjangoFilterBackend
# from rest_framework import viewsets


# from scorer_weighted.serializers import ScoreSerializer, WeightedScorerSerializer

log = logging.getLogger(__name__)


# class WeightedScorerViewSet(viewsets.ReadOnlyModelViewSet):
#     queryset = WeightedScorer.objects.all()
#     serializer_class = WeightedScorerSerializer
#     filter_backends = [DjangoFilterBackend]


# class ScoreViewSet(viewsets.ReadOnlyModelViewSet):
#     queryset = Score.objects.all()
#     serializer_class = ScoreSerializer
#     filter_backends = [DjangoFilterBackend]

#     filterset_fields = {"passport_id": ["exact", "in"], "scorer": ["exact"]}
