import django_filters
from django.db.models import Q
from registry.models import GTCStakeEvents


class GTCStakeEventsFilter(django_filters.FilterSet):
    address = django_filters.CharFilter(method="filter_address")

    class Meta:
        model = GTCStakeEvents
        fields = ["round_id", "address"]

    def filter_address(self, queryset, name, value):
        beginner_experienced_community_staker = Q(
            round_id=self.request.GET.get("round_id", ""),
            amount__gte=5000000000000000000,
            event_type="Xstake",
            staker=value,
        ) | Q(address=value)

        trusted_citizen_staker = Q(
            round_id=self.request.GET.get("round_id", ""),
            amount__gte=20000000000000000000,
            event_type="Xstake",
            address=value,
        )

        self_stake = Q(
            round_id=self.request.GET.get("round_id", ""),
            amount__gte=5000000000000000000,
            event_type="SelfStake",
            staker=value,
        )

        return queryset.filter(
            beginner_experienced_community_staker | trusted_citizen_staker | self_stake
        )
