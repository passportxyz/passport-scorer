from django.contrib import admin
from django.core.paginator import Paginator
from django.utils.functional import cached_property

# class NoCountPaginator(Paginator):
#     @cached_property
#     def count(self):
#         """Return a fix number for the total count. We want to avoid slow loading of page ..."""
#         from django.apps import apps

#         model = apps.get_model("app_name", "model_name")
#         return 1000


class ScorerModelAdmin(admin.ModelAdmin):
    """
    This extends the default ModelAdmin in django and:
    - sets `show_full_result_count` to `False`
    - sets `paginator` to `NoCountPaginator` -> the reasoning here is that
    having the count slows queries down a lot, making the admin list page unusable and issuing a Gatway timeout.
    Also, that count & pagination have no real value. Users should rely on the search function,
    to narrow down the list of results to a small enough number.
    """

    show_full_result_count = False
    # TODO: holding back on changing the NoCountPaginator for now ...
    # paginator = NoCountPaginator
