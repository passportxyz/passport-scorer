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

        results = queryset.filter(
            Q(
                round_id=round_id_value,
            )
            & (Q(staker=value) | Q(address=value))
        )

        return results
