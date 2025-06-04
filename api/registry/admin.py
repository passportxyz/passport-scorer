import csv
import io
import logging
from datetime import UTC, datetime
from io import StringIO

import boto3
from asgiref.sync import async_to_sync
from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import path

from registry.api.schema import SubmitPassportPayload
from registry.api.v1 import ahandle_submit_passport
from registry.models import (
    BatchModelScoringRequest,
    BatchModelScoringRequestItem,
    BatchRequestStatus,
    Event,
    GTCStakeEvent,
    HashScorerLink,
    Passport,
    Score,
    Stamp,
)
from registry.weight_models import WeightConfiguration, WeightConfigurationItem
from scorer.scorer_admin import ScorerModelAdmin
from scorer.settings import (
    BULK_MODEL_SCORE_REQUESTS_RESULTS_FOLDER,
    BULK_SCORE_REQUESTS_ADDRESS_LIST_FOLDER,
    BULK_SCORE_REQUESTS_BUCKET_NAME,
)

ONE_HOUR = 60 * 60

log = logging.getLogger(__name__)

_s3_client = None


def get_s3_client():
    global _s3_client
    if not _s3_client:
        _s3_client = boto3.client("s3")
    return _s3_client


@admin.action(
    description="Recalculate user score", permissions=["rescore_individual_score"]
)
def recalculate_user_score(modeladmin, request, queryset):
    score_ids = [str(id) for id in queryset.values_list("id", flat=True)]
    rescored_ids = []
    failed_rescoring = []
    for score in Score.objects.filter(id__in=score_ids).prefetch_related("passport"):
        p = score.passport
        c = p.community
        scorer_id = p.community_id
        address = p.address
        try:
            sp = SubmitPassportPayload(
                address=address, scorer_id=scorer_id, signature="", nonce=""
            )
            async_to_sync(ahandle_submit_passport)(sp, c.account)
            rescored_ids.append(score.id)
        except Exception:
            print(f"Error for {scorer_id} and {address}")
            failed_rescoring.append(score.id)

        modeladmin.message_user(
            request,
            f"Have successfully rescored: {rescored_ids}",
            level=messages.SUCCESS,
        )
        if failed_rescoring:
            modeladmin.message_user(
                request,
                f"Rescoring has failed for: {failed_rescoring}",
                level=messages.ERROR,
            )


@admin.register(Passport)
class PassportAdmin(ScorerModelAdmin):
    list_display = ["address", "community"]
    search_fields = ["address"]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.select_related("community")
        return queryset


@admin.register(Stamp)
class StampAdmin(ScorerModelAdmin):
    list_display = ["passport", "community", "provider"]
    search_fields = ["passport__address"]
    search_help_text = "This will perform a search by passport__address"
    raw_id_fields = ["passport"]
    show_full_result_count = False

    def community(self, obj):
        return obj.passport.community

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.select_related("passport__community")
        return queryset


@admin.register(Score)
class ScoreAdmin(ScorerModelAdmin):
    list_display = [
        "passport",
        "community",
        "score",
        "last_score_timestamp",
        "status",
        "error",
    ]
    search_fields = ["passport__address", "status"]
    raw_id_fields = ["passport"]
    actions = [recalculate_user_score]

    def community(self, obj):
        return obj.passport.community

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.select_related("passport__community")
        return queryset

    def has_rescore_individual_score_permission(self, request):
        return request.user.has_perm("registry.rescore_individual_score")


@admin.register(Event)
class EventAdmin(ScorerModelAdmin):
    list_display = [
        "action",
        "created_at",
        "address",
        "data",
    ]

    list_filter = [
        "action",
    ]

    search_fields = [
        "created_at",
        "address",
        "data",
    ]


@admin.register(HashScorerLink)
class HashScorerLinkAdmin(ScorerModelAdmin):
    list_display = ["hash", "community", "address", "expires_at"]

    search_fields = [
        "hash",
        "community",
        "address",
    ]


@admin.register(GTCStakeEvent)
class GTCStakeEventAdmin(ScorerModelAdmin):
    list_display = ["id", "address", "staker", "round_id", "amount", "event_type"]

    list_filter = [
        "round_id",
        "event_type",
    ]

    search_fields = [
        "round_id",
        "address",
        "staker",
        "event_type",
    ]


class BatchModelScoringRequestCsvImportForm(forms.Form):
    models = forms.CharField(
        max_length=100,
        required=True,
        help_text='Example: "nft,ethereum_activity"',
    )
    address_list = forms.FileField(required=True)


@admin.register(BatchModelScoringRequest)
class BatchModelScoringRequestAdmin(ScorerModelAdmin):
    list_display = ["id", "created_at", "model_list", "progress", "status"]
    # readonly_fields = [
    #     field.name for field in BatchModelScoringRequest._meta.get_fields()
    # ] + ["address_list", "results"]


@admin.register(BatchModelScoringRequestItem)
class BatchModelScoringRequestItemAdmin(ScorerModelAdmin):
    list_display = ["id", "batch_scoring_request", "address", "status"]
    list_filter = ["batch_scoring_request"]
    search_fields = ("address",)


class WeightConfigurationItemInline(admin.TabularInline):
    model = WeightConfigurationItem
    extra = 0


class WeightConfigurationForm(forms.ModelForm):
    class Meta:
        model = WeightConfiguration
        fields = "__all__"

    def clean_csv_source(self):
        """
        Validate the content of the CSV file
        """
        csv_source = self.cleaned_data["csv_source"]
        # using 'utf-8-sig' will also handle the case where the file is saved with a BOM (byte order mark - \ufeff)
        csv_data = csv_source.read().decode("utf-8-sig")

        csv_reader = csv.reader(StringIO(csv_data))
        for row in csv_reader:
            if len(row) != 2:
                raise ValueError(f"Invalid row format: {row}")
            if not row[0] or not row[1]:
                raise ValidationError("Provider and weight must not be empty.")

            provider, weight = row
            try:
                weight = float(weight)
            except ValueError:
                raise ValidationError(
                    f"Invalid weight value for '{provider}': '{weight}'"
                )
        return csv_source


@admin.register(WeightConfiguration)
class WeightConfigurationAdmin(admin.ModelAdmin):
    form = WeightConfigurationForm
    list_display = (
        "version",
        "threshold",
        "description",
        "active",
        "created_at",
        "updated_at",
    )
    search_fields = ("version", "description")
    readonly_fields = ("created_at", "updated_at", "csv_source")
    inlines = [WeightConfigurationItemInline]

    def csv_source_url(self, obj: WeightConfiguration):
        return obj.csv_file.url

    def save_model(self, request, obj: WeightConfiguration, form, change):
        if not obj.version:
            version = 0
            weight_config = WeightConfiguration.objects.order_by("-created_at").first()
            if weight_config:
                version = int(weight_config.version) + 1

            obj.version = version
        super().save_model(request, obj, form, change)

        # If saving any of the objects below fails, we expect to roll back
        # using 'utf-8-sig' will also handle the case where the file is saved with a BOM (byte order mark - \ufeff)

        csv_data = obj.csv_source.open("rb").read().decode("utf-8-sig")
        csv_reader = csv.reader(StringIO(csv_data))
        for row in csv_reader:
            if len(row) != 2:
                raise ValueError(f"Invalid row format: {row}")

            provider, weight = row
            log.info(f"Adding weight configuration for {provider} with weight {weight}")
            WeightConfigurationItem.objects.create(
                weight_configuration=obj,
                provider=provider,
                weight=float(weight),
            )

        WeightConfiguration.objects.filter(active=True).update(active=False)
        obj.active = True
        obj.save()


admin.site.register(WeightConfigurationItem)
