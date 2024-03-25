# Register your models here.
from django import forms
from django.contrib import admin
from django_ace import AceWidget
from scorer.scorer_admin import ScorerModelAdmin

from .models import Tos, TosAcceptanceProof


class TosForm(forms.ModelForm):
    class Meta:
        model = Tos
        widgets = {
            "content": AceWidget(
                # mode="text",
                theme=None,  # try for example "twilight"
                wordwrap=False,
                width="500px",
                height="300px",
                minlines=None,
                maxlines=None,
                showprintmargin=True,
                showinvisibles=False,
                usesofttabs=True,
                tabsize=None,
                fontsize=None,
                toolbar=True,
                readonly=False,
                showgutter=True,  # To hide/show line numbers
                behaviours=True,  # To disable auto-append of quote when quotes are entered
            )
        }
        fields = "__all__"


@admin.register(Tos)
class TosAdmin(ScorerModelAdmin):
    form = TosForm
    list_display = ("id", "type", "active", "created_at", "modified_at")
    readonly_fields = ("created_at", "modified_at")
    search_fields = ("content", "type")
    list_filter = ["active", "type"]


@admin.register(TosAcceptanceProof)
class TosAcceptanceProofAdmin(ScorerModelAdmin):
    list_display = ("id", "tos", "created_at", "address", "nonce", "signature")
    readonly_fields = ["created_at"]
    search_fields = ("address", "nonce", "signature")
