from django.contrib import admin
from trusta_labs.models import TrustaLabsScore


class TrustaLabsScoreAdmin(admin.ModelAdmin):
    list_display = ["address", "sybil_risk_score"]
    search_fields = ["address"]
    search_help_text = "This will perform an exact case insensitive search by 'address'"
    show_full_result_count = False


admin.site.register(TrustaLabsScore, TrustaLabsScoreAdmin)
