from asgiref.sync import async_to_sync
from django.contrib import admin, messages
from import_export.forms import ModelResource
from registry.api.schema import SubmitPassportPayload
from registry.api.v1 import ahandle_submit_passport
from registry.models import (
    Event,
    GTCStakeEvent,
    HashScorerLink,
    Passport,
    Score,
    Stamp,
    AddressListMember,
    AddressList,
)
from scorer.scorer_admin import ScorerModelAdmin
from import_export.admin import ImportMixin, ImportForm
from django import forms
from django.urls import path
from django.shortcuts import render, redirect
import csv
import codecs


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
            f"Have succesfully rescored: {rescored_ids}",
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


class AddressListMemberInline(admin.TabularInline):
    model = AddressListMember
    extra = 0


class AddressListImportForm(ImportForm):
    list = forms.ModelChoiceField(queryset=AddressList.objects.all(), required=True)


class AddressListMemberResource(ModelResource):
    def __init__(self, **kwargs):
        super().__init__()
        print(kwargs, "ALMR init - KWARGS!!!!!!")
        self.list_id = kwargs.get("list_id")

    class Meta:
        model = AddressListMember


class AddressListCsvImportForm(forms.Form):
    csv_file = forms.FileField()
    list = forms.ModelChoiceField(queryset=AddressList.objects.all(), required=True)


@admin.register(AddressListMember)
class AddressListMemberAdmin(ImportMixin, admin.ModelAdmin):
    import_form_class = AddressListImportForm

    def get_import_resource_kwargs(self, request, *args, **kwargs):
        kwargs = super().get_resource_kwargs(request, *args, **kwargs)
        print(kwargs, "girk - KWARGS!!!!!!")
        # kwargs.update({"user": request.user})
        return kwargs

    def get_import_data_kwargs(self, **kwargs):
        """
        Prepare kwargs for import_data.
        """
        print(kwargs, "gidk - KWARGS!!!!!!")
        form = kwargs.get("form", None)
        if form and hasattr(form, "cleaned_data"):
            print(form.cleaned_data, "gidk - FORM.CLEANED_DATA!!!!!!")
            kwargs.update({"list_id": form.cleaned_data.get("list", None)})
        return kwargs

    def after_init_instance(self, instance, new, row, **kwargs):
        print(kwargs, "KWARGS!!!!!!")
        if "list_id" in kwargs:
            instance.list_id = kwargs["list_id"]


@admin.register(AddressList)
class AddressListAdmin(ScorerModelAdmin):
    list_display = ["name", "address_count"]
    inlines = [AddressListMemberInline]
    change_list_template = "registry/addresslist_changelist.html"

    def address_count(self, obj):
        return obj.addresses.count()

    def get_urls(self):
        return [
            path("import-csv/", self.import_csv),
        ] + super().get_urls()

    def import_csv(self, request):
        if request.method == "POST":
            csv_file = request.FILES["csv_file"]
            reader = csv.reader(codecs.iterdecode(csv_file, "utf-8"))
            list_id = request.POST.get("list")
            address_list = AddressList.objects.get(id=list_id)
            for row in reader:
                address = row[0].strip()
                AddressListMember.objects.create(address=address, list=address_list)
            self.message_user(request, "Your csv file has been imported")
            return redirect("..")
        form = AddressListCsvImportForm()
        payload = {"form": form}
        return render(request, "registry/address_list_csv_import_form.html", payload)
