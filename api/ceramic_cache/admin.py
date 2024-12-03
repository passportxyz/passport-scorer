"""
Admin for the ceramic cache app
"""

import csv
from datetime import datetime
from io import StringIO
from typing import Optional

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.forms import ModelForm
from django.utils import timezone

from scorer.scorer_admin import ScorerModelAdmin

from .models import Ban, BanList, CeramicCache, Revocation, RevocationList


@admin.action(
    description="Undeleted selected stamps", permissions=["rescore_individual_score"]
)
def undelete_selected_stamps(modeladmin, request, queryset):
    score_ids = [str(id) for id in queryset.values_list("id", flat=True)]
    undeleted_ids = []
    failed_to_undelete = []
    for c in CeramicCache.objects.filter(id__in=score_ids):
        try:
            if c.deleted_at:
                c.deleted_at = None
                c.save()
                undeleted_ids.append(c.id)
            else:
                failed_to_undelete.append(c.id)

        except Exception:
            failed_to_undelete.append(c.id)

    modeladmin.message_user(
        request,
        f"Have succesfully undeleted: {undeleted_ids}",
        level=messages.SUCCESS,
    )
    if failed_to_undelete:
        modeladmin.message_user(
            request,
            f"Failed to undelete: {failed_to_undelete}",
            level=messages.ERROR,
        )


@admin.register(CeramicCache)
class CeramicCacheAdmin(ScorerModelAdmin):
    list_display = (
        "id",
        "address",
        "provider",
        "stamp",
        "deleted_at",
        "compose_db_save_status",
        "compose_db_stream_id",
        "proof_value",
    )
    list_filter = ("deleted_at", "compose_db_save_status")
    search_fields = ("address__exact", "compose_db_stream_id__exact", "proof_value")
    search_help_text = (
        "This will perform a search by 'address' and 'compose_db_stream_id'"
    )

    actions = [undelete_selected_stamps]
    show_full_result_count = False

    def has_rescore_individual_score_permission(self, request):
        return request.user.has_perm("registry.rescore_individual_score")


class AccountAPIKeyAdmin(ScorerModelAdmin):
    list_display = ("id", "name", "prefix", "created", "expiry_date", "revoked")
    search_fields = ("id", "name", "prefix")


@admin.register(Revocation)
class RevocationAdmin(ScorerModelAdmin):
    list_display = ("id", "proof_value", "ceramic_cache", "revocation_list")
    search_fields = ("proof_value",)
    list_filter = ["revocation_list"]


class RevocationListForm(forms.ModelForm):
    class Meta:
        model = RevocationList
        fields = "__all__"

    def clean_csv_file(self):
        """
        Validate the content of the CSV file
        """
        csv_file = self.cleaned_data["csv_file"]
        csv_data = csv_file.read().decode("utf-8")

        csv_reader = csv.DictReader(StringIO(csv_data))
        line = 0
        for revocation_item in csv_reader:
            line += 1
            try:
                # In this case we'll only validate that the proof_values provided indicate valid (existing) stamps
                proof_value = revocation_item["proof_value"]
                if not CeramicCache.objects.filter(
                    proof_value=revocation_item["proof_value"]
                ).exists():
                    raise ValidationError(
                        f"Unable to find stamp for proof_value '{proof_value}'"
                    )
            except ValueError as e:
                raise ValidationError(f"Failed to validate line {line}, {e}") from e
            except ValidationError as e:
                raise ValidationError(f"Failed to validate line {line}, {e}") from e
            except Exception as e:
                raise ValidationError(
                    f"Failed to validate line {line} (unknown error), {e}"
                ) from e
        return csv_file


@admin.register(RevocationList)
class RevocationListAdmin(admin.ModelAdmin):
    form = RevocationListForm
    list_display = [
        "name",
        "description",
        "csv_file",
    ]

    def csv_file_url(self, obj: RevocationList):
        return obj.csv_file.url

    def save_model(self, request, obj: RevocationList, form, change):
        super().save_model(request, obj, form, change)

        # If saving any of the objects below fails, we expect to roll back
        csv_reader = csv.DictReader(obj.csv_file.open("rt"))
        revocation_item_list = []
        for revocation_item in csv_reader:
            proof_value = revocation_item["proof_value"]
            ceramic_cache = CeramicCache.objects.get(proof_value=proof_value)
            db_revocation_item = Revocation(
                proof_value=proof_value,
                ceramic_cache=ceramic_cache,
                revocation_list=obj,
            )
            revocation_item_list.append(db_revocation_item)
        Revocation.objects.bulk_create(revocation_item_list, batch_size=1000)


class BanForm(ModelForm):
    class Meta:
        model = Ban
        fields = ["hash", "address", "provider", "end_time", "reason"]
        widgets = {
            "reason": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            "hash": "Specific credential hash to ban",
            "address": "Address to ban",
            "provider": "Provider (e.g. CoinbaseDualVerification) to ban - must be used with address",
            "end_time": "Leave blank for indefinite ban",
            "reason": "(Optional) THIS WILL BE PUBLICLY VISIBLE",
        }


@admin.action(description="Revoke matching credentials for selected bans")
def revoke_matching_credentials_action(modeladmin, request, queryset):
    success_count = 0
    error_count = 0

    for ban in queryset:
        try:
            ban.revoke_matching_credentials()
            success_count += 1
        except Exception as e:
            error_count += 1
            modeladmin.message_user(
                request,
                f"Error processing ban {ban.pk}: {str(e)}",
                level=messages.ERROR,
            )

    if success_count:
        modeladmin.message_user(
            request,
            f"Successfully processed {success_count} ban(s)",
            level=messages.SUCCESS,
        )

    if error_count:
        modeladmin.message_user(
            request,
            f"Failed to process {error_count} ban(s). See errors above.",
            level=messages.WARNING,
        )


@admin.register(Ban)
class BanAdmin(admin.ModelAdmin):
    form = BanForm
    list_display = [
        "type",
        "ban_list",
        "get_ban_description",
        "is_active",
        "end_time",
        "matching_revoked",
        "created_at",
    ]
    actions = [revoke_matching_credentials_action]
    change_form_template = "ban/change_form.html"
    list_filter = ["created_at", "end_time", "ban_list"]
    search_fields = ["address", "hash", "provider", "reason"]
    readonly_fields = ["created_at", "last_run_revoke_matching"]

    @admin.display(description="Ban Condition")
    def get_ban_description(self, obj):
        parts = []
        if obj.hash:
            parts.append(f"hash={obj.hash}")
        if obj.address:
            parts.append(f"address={obj.address}")
        if obj.provider:
            parts.append(f"provider={obj.provider}")
        return "Ban if: " + " AND ".join(parts)

    @admin.display(boolean=True)
    def is_active(self, obj):
        if not obj.end_time:
            return True
        return obj.end_time > timezone.now()

    @admin.display(boolean=True)
    def matching_revoked(self, obj):
        return obj.last_run_revoke_matching is not None


def get_isodatetime_or_none(value) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value != "null" and value != "" else None


class BanListForm(forms.ModelForm):
    class Meta:
        model = BanList
        fields = "__all__"

    def clean_csv_file(self):
        """
        Validate the content of the CSV file
        """
        csv_file = self.cleaned_data["csv_file"]
        csv_data = csv_file.read().decode("utf-8")

        csv_reader = csv.DictReader(StringIO(csv_data))
        line = 0
        for ban_item in csv_reader:
            line += 1
            try:
                db_ban_item = Ban(
                    type=ban_item["type"],
                    provider=ban_item["provider"],
                    hash=ban_item["hash"],
                    end_time=get_isodatetime_or_none(ban_item["end_time"]),
                    address=ban_item["address"],
                )
                # This will run all validators on the fields in Ban see: https://docs.djangoproject.com/en/5.1/ref/models/instances/#validating-objects
                db_ban_item.full_clean()

            except ValueError as e:
                raise ValidationError(f"Failed to validate line {line}, {e}") from e
            except ValidationError as e:
                raise ValidationError(f"Failed to validate line {line}, {e}") from e
            except Exception as e:
                raise ValidationError(
                    f"Failed to validate line {line} (unknown error), {e}"
                ) from e
        return csv_file


@admin.register(BanList)
class BanListAdmin(admin.ModelAdmin):
    form = BanListForm
    list_display = [
        "name",
        "description",
        "csv_file",
    ]

    def csv_file_url(self, obj: BanList):
        return obj.csv_file.url

    def save_model(self, request, obj: BanList, form, change):
        super().save_model(request, obj, form, change)

        # If saving any of the objects below fails, we expect to roll back
        csv_reader = csv.DictReader(obj.csv_file.open("rt"))
        ban_item_list = []
        for ban_item in csv_reader:
            db_ban_item = Ban(
                type=ban_item["type"],
                provider=ban_item["provider"],
                hash=ban_item["hash"],
                end_time=get_isodatetime_or_none(ban_item["end_time"]),
                address=ban_item["address"],
                ban_list=obj,
            )
            ban_item_list.append(db_ban_item)
        Ban.objects.bulk_create(ban_item_list, batch_size=1000)
