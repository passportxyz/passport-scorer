import django_filters
from django.db.models import Q
from registry.models import GTCStakeEvent


class GTCStakeEventsFilter(django_filters.FilterSet):
    address = django_filters.CharFilter(method="filter_address")

    class Meta:
        model = GTCStakeEvent
        fields = ["round_id", "address"]

    def filter_address(self, queryset, name, value):
        round_id_value = int(self.form.cleaned_data.get("round_id", ""))

        beginner_experienced_community_staker = Q(
            round_id=round_id_value,
            event_type="Xstake",
            staker=value,
            amount__gte=5,
        ) | Q(address=value)

        trusted_citizen_staker = Q(
            round_id=round_id_value,
            event_type="Xstake",
            address=value,
            amount__gte=20,
        )

        self_stake = Q(
            round_id=round_id_value,
            event_type="SelfStake",
            staker=value,
            amount__gte=5,
        )

        results = queryset.filter(
            beginner_experienced_community_staker | trusted_citizen_staker | self_stake
        )

        return results
