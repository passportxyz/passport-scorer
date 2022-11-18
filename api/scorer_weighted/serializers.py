from rest_framework import serializers

from registry.serializers import PassportSerializer

from .models import Score, WeightedScorer


class WeightedScorerSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeightedScorer
        fields = ["id", "start_time", "end_time", "weights"]


class ScoreSerializer(serializers.ModelSerializer):
    passport = PassportSerializer(many=False, read_only=True)

    class Meta:
        model = Score
        fields = ["id", "passport_id", "passport", "scorer", "score"]
