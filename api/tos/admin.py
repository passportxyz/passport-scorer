# Register your models here.
from django.contrib import admin
from scorer.scorer_admin import ScorerModelAdmin

from .models import Tos, TosAcceptanceProof


@admin.register(Tos)
class TosAdmin(ScorerModelAdmin):
    list_display = ("id", "type", "created_at", "modified_at")
    readonly_fields = ("created_at", "modified_at")
    search_fields = ("content", "type")


@admin.register(TosAcceptanceProof)
class TosAcceptanceProofAdmin(ScorerModelAdmin):
    list_display = ("id", "tos", "created_at", "address", "nonce", "signature")
    readonly_fields = ["created_at"]
    search_fields = ("address", "nonce", "signature")
