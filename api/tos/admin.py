# Register your models here.
from typing import Any

from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_permission_codename
from django.http import HttpRequest
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
    list_display = ("id", "type", "active", "final", "created_at", "modified_at")
    readonly_fields = ["created_at", "modified_at"]
    search_fields = ("content", "type")
    list_filter = ["active", "final", "type"]

    actions = ["make_active"]

    def get_readonly_fields(
        self, request: HttpRequest, obj: Tos | None = ...
    ) -> list[str] | tuple[Any, ...]:
        ret = ["created_at", "modified_at"]
        # An active object shall not be made inactive ...
        if obj and obj.final:
            ret += ["final", "content", "type"]
        return ret

    @admin.action(description="Make selected TOS active", permissions=["activate"])
    def make_active(self, request, queryset):
        count = len(queryset)
        if count > 1:
            self.message_user.e
            messages.error(request, "You can only activate 1 tos")
            return

        prev_list = list(Tos.objects.filter(active=True))
        if prev_list:
            prev_active = prev_list[0]
            prev_active.active = False
            prev_active.save()
        queryset.update(active=True)

    def has_activate_permission(self, request):
        """Does the user have the activate permission?"""

        opts = self.opts
        codename = get_permission_codename("activate", opts)
        ret = request.user.has_perm("%s.%s" % (opts.app_label, codename))
        return ret


@admin.register(TosAcceptanceProof)
class TosAcceptanceProofAdmin(ScorerModelAdmin):
    list_display = ("id", "tos", "created_at", "address", "nonce", "signature")
    readonly_fields = ["created_at"]
    search_fields = ("address", "nonce", "signature")
