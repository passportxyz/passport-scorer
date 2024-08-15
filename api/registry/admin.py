import csv
import io
from datetime import UTC, datetime

import boto3
from asgiref.sync import async_to_sync
from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import path

from registry.api.schema import SubmitPassportPayload
from registry.api.v1 import ahandle_submit_passport
from registry.models import (
    BatchModelScoringRequest,
    BatchRequestStatus,
    Event,
    GTCStakeEvent,
    HashScorerLink,
    Passport,
    Score,
    Stamp,
    WeightConfiguration,
    WeightConfigurationItem,
)
from scorer.scorer_admin import ScorerModelAdmin
from scorer.settings import (
    BULK_MODEL_SCORE_REQUESTS_RESULTS_FOLDER,
    BULK_SCORE_REQUESTS_ADDRESS_LIST_FOLDER,
    BULK_SCORE_REQUESTS_BUCKET_NAME,
)

ONE_HOUR = 60 * 60

_s3_client = None


def get_s3_client():
    global _s3_client
    if not _s3_client:
        _s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.S3_DATA_AWS_SECRET_KEY_ID,
            aws_secret_access_key=settings.S3_DATA_AWS_SECRET_ACCESS_KEY,
        )
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
    list_display = ["passport", "community", "provider", "hash"]
    search_fields = ["hash__exact"]
    search_help_text = "This will perform an exact case sensitive search by 'hash'"
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
    change_list_template = "registry/batch_model_scoring_request_changelist.html"
    list_display = ["id", "created_at"]
    readonly_fields = [
        field.name for field in BatchModelScoringRequest._meta.get_fields()
    ] + ["address_list", "results"]

    def address_list(self, obj):
        object_name = f"{BULK_SCORE_REQUESTS_ADDRESS_LIST_FOLDER}/{obj.s3_filename}"
        return get_s3_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": BULK_SCORE_REQUESTS_BUCKET_NAME, "Key": object_name},
            ExpiresIn=ONE_HOUR,
        )

    def results(self, obj):
        if obj.status != BatchRequestStatus.DONE:
            return None

        object_name = f"{BULK_MODEL_SCORE_REQUESTS_RESULTS_FOLDER}/{obj.s3_filename}"
        return get_s3_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": BULK_SCORE_REQUESTS_BUCKET_NAME, "Key": object_name},
            ExpiresIn=ONE_HOUR,
        )

    def get_urls(self):
        return [
            path("import-csv/", self.import_csv),
        ] + super().get_urls()

    def import_csv(self, request):
        if request.method == "POST":
            filename = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S") + ".csv"
            object_name = f"{BULK_SCORE_REQUESTS_ADDRESS_LIST_FOLDER}/{filename}"

            get_s3_client().upload_fileobj(
                request.FILES["address_list"],
                BULK_SCORE_REQUESTS_BUCKET_NAME,
                object_name,
            )

            obj = BatchModelScoringRequest.objects.create(
                model_list=request.POST.get("models"),
                s3_filename=filename,
                status=BatchRequestStatus.PENDING,
            )

            return redirect(f"../{obj.pk}/change/")

        form = BatchModelScoringRequestCsvImportForm()
        payload = {"form": form}
        return render(
            request,
            "registry/batch_model_scoring_request_csv_import_form.html",
            payload,
        )


class WeightConfigurationItemInline(admin.TabularInline):
    model = WeightConfigurationItem
    extra = 1


class WeightConfigurationCsvImportForm(forms.Form):
    threshold = forms.FloatField(
        required=True, help_text="Threshold for Passport uniqueness"
    )
    csv_file = forms.FileField(
        required=True, help_text="Upload a CSV file with weight configuration data"
    )


@admin.register(WeightConfiguration)
class WeightConfigurationAdmin(admin.ModelAdmin):
    change_list_template = "registry/batch_model_scoring_request_changelist.html"
    list_display = ("version", "threshold", "active", "created_at", "updated_at")
    search_fields = ("version", "description")
    readonly_fields = ("created_at", "updated_at")
    inlines = [WeightConfigurationItemInline]

    def get_urls(self):
        return [
            path("import-csv/", self.import_csv),
        ] + super().get_urls()

    def import_csv(self, request):
        if request.method == "POST":
            form = WeightConfigurationCsvImportForm(request.POST, request.FILES)
            if form.is_valid():
                csv_file = request.FILES["csv_file"]
                threshold = request.POST.get("threshold")
                try:
                    decoded_file = csv_file.read().decode("utf-8")
                    io_string = io.StringIO(decoded_file)
                    reader = csv.DictReader(io_string)

                    version = 0
                    try:
                        current_version = WeightConfiguration.objects.filter(
                            active=True
                        ).first()
                        if current_version:
                            version = int(current_version.version) + 1
                    except WeightConfiguration.DoesNotExist:
                        print("This is the first weight configuration")

                    weight_config = None
                    for row in reader:
                        if not weight_config:
                            WeightConfiguration.objects.filter(active=True).exclude(
                                version=version
                            ).update(active=False)
                            weight_config = WeightConfiguration.objects.create(
                                threshold=threshold, version=version, active=True
                            )
                        print(row, "row")
                        WeightConfigurationItem.objects.create(
                            weight_configuration=weight_config,
                            provider=row[0],
                            weight=float(row[1]),
                        )

                    self.message_user(
                        request,
                        f"Successfully imported WeightConfiguration: {weight_config.version}",
                    )
                    return redirect("..")
                except Exception as e:
                    self.message_user(
                        request, f"Error importing CSV: {str(e)}", level=messages.ERROR
                    )
            else:
                self.message_user(
                    request, "Invalid form submission", level=messages.ERROR
                )
        else:
            form = WeightConfigurationCsvImportForm()

        context = {
            "form": form,
            "title": "Import Weight Configuration CSV",
        }
        return render(
            request,
            "registry/batch_model_scoring_request_csv_import_form.html",
            context,
        )


admin.site.register(WeightConfigurationItem)
