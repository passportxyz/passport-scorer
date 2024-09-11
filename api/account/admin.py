import codecs
import csv

import boto3
from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.safestring import mark_safe
from django_ace import AceWidget
from rest_framework_api_key.admin import APIKeyAdmin

from scorer.scorer_admin import ScorerModelAdmin
from scorer_weighted.models import Scorer

from .models import (
    Account,
    AccountAPIKey,
    AddressList,
    AddressListMember,
    AllowList,
    Community,
    CustomGithubStamp,
    Customization,
    IncludedChainId,
)


@admin.register(Account)
class AccountAdmin(ScorerModelAdmin):
    list_display = ("id", "address", "user")
    search_fields = ("address", "user__username")
    raw_id_fields = ("user",)


@admin.action(description="Recalculate scores", permissions=["change"])
def recalculate_scores(modeladmin, request, queryset):
    community_ids = [str(id) for id in queryset.values_list("id", flat=True)]

    # Create SQS client
    sqs = boto3.client("sqs", region_name="us-west-2")

    queue_url = settings.RESCORE_QUEUE_URL

    if queue_url == "":
        modeladmin.message_user(
            request,
            "Please set the RESCORE_QUEUE_URL environment variable to the URL of the SQS queue to use for rescoring.",
            level=messages.ERROR,
        )
        return

    # Send message to SQS queue
    response = sqs.send_message(
        QueueUrl=queue_url,
        MessageAttributes={
            "type": {"DataType": "String", "StringValue": "rescore"},
        },
        MessageBody=(",".join(community_ids)),
    )

    modeladmin.message_user(
        request,
        f"Submitted {len(community_ids)} communities for recalculation with message id {response['MessageId']}",
    )


@admin.register(Community)
class CommunityAdmin(ScorerModelAdmin):
    list_display = (
        "id",
        "name",
        "created_at",
        "description",
        "account",
        "scorer_link",
        "use_case",
        "deleted_at",
    )
    raw_id_fields = ("account", "scorer")
    search_fields = (
        "name",
        "description",
        "account__address",
        "created_at",
        "deleted_at",
    )
    readonly_fields = ("scorer_link",)
    actions = [recalculate_scores]

    def scorer_link(self, obj):
        # To add additional scorer types, just look at the URL on_delete
        # the edit page for the scorer type to get the category and field
        match obj.scorer.type:
            case Scorer.Type.WEIGHTED:
                category = "scorer_weighted"
                field = "weightedscorer"
            case Scorer.Type.WEIGHTED_BINARY | _:
                category = "scorer_weighted"
                field = "binaryweightedscorer"

        href = reverse(
            f"admin:{category}_{field}_change",
            args=[obj.get_scorer().pk],
        )
        return mark_safe(f'<a href="{href}">Scorer #{obj.scorer.id}</a>')

    scorer_link.short_description = "Scorer Link"


@admin.register(AccountAPIKey)
class AccountAPIKeyAdmin(APIKeyAdmin):
    raw_id_fields = ("account",)
    search_fields = (
        "id",
        "name",
        "prefix",
        "rate_limit",
        "analysis_rate_limit",
        "account__user__username",
        "account__address",
    )

    list_display = (
        "name",
        "account",
        "rate_limit_display",
        "analysis_rate_limit_display",
        "created",
        "revoked",
    )

    # Step 1: Define the edit action function
    def edit_selected(modeladmin, request, queryset):
        if queryset.count() != 1:
            modeladmin.message_user(
                request, "Please select exactly one row to edit.", level=messages.ERROR
            )
            return

        selected_instance = queryset.first()
        return HttpResponseRedirect(
            reverse(
                f"admin:{selected_instance._meta.app_label}_{selected_instance._meta.model_name}_change",
                args=(selected_instance.id,),
            )
        )

    # Step 3: Customize the action's display name in the dropdown menu
    edit_selected.short_description = "Edit selected row"

    # Step 2: Register the edit action
    actions = [edit_selected]


class APIKeyPermissionsAdmin(ScorerModelAdmin):
    list_display = ("id", "submit_passports", "read_scores", "create_scorers")


svg_widget = AceWidget(
    mode="svg",
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
xml_widget = AceWidget(
    mode="xml",
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


class CustomizationForm(forms.ModelForm):
    class Meta:
        model = Customization
        widgets = {
            "logo_image": svg_widget,
            # "logo_background": xml_widget,
            "logo_caption": xml_widget,
            "body_main_text": xml_widget,
            "body_sub_text": xml_widget,
        }
        fields = "__all__"


class AllowListInline(admin.TabularInline):
    model = AllowList
    extra = 0


class IncludedChainIdInline(admin.TabularInline):
    model = IncludedChainId
    extra = 0


class CustomGithubStampInline(admin.TabularInline):
    model = CustomGithubStamp
    extra = 0


@admin.register(Customization)
class CustomizationAdmin(ScorerModelAdmin):
    form = CustomizationForm
    raw_id_fields = ["scorer"]
    inlines = [AllowListInline, CustomGithubStampInline, IncludedChainIdInline]
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "path",
                    "scorer_panel_title",
                    "scorer_panel_text",
                    "scorer",
                    "use_custom_dashboard_panel",
                    "show_explanation_panel",
                ],
            },
        ),
        (
            "Colors",
            {
                "classes": ["collapse"],
                "fields": [
                    "customization_background_1",
                    "customization_background_2",
                    "customization_foreground_1",
                    "customization_foreground_2",
                    "customization_background_3",
                ],
            },
        ),
        (
            "Logo",
            {
                "classes": ["collapse"],
                "fields": ["logo_background", "logo_image", "logo_caption"],
            },
        ),
        (
            "Body",
            {
                "classes": ["collapse"],
                "fields": [
                    "body_action_text",
                    "body_action_url",
                    "body_main_text",
                    "body_sub_text",
                    "button_action_type",
                    "body_display_info_tooltip",
                    "body_info_tooltip_text",
                ],
            },
        ),
    ]

    list_display = [
        "display",
        "id",
        "path",
        "use_custom_dashboard_panel",
        "scorer",
        "show_explanation_panel",
    ]

    @admin.display(ordering="id")
    def display(self, obj):
        return f"{obj.id} - {obj.path}"

    def save_model(self, request, obj, form, change):
        # Perform your validation logic
        if "validate_something" in request.POST:
            # Perform some validation...
            pass
        super().save_model(request, obj, form, change)


class AddressListMemberInline(admin.TabularInline):
    model = AddressListMember
    extra = 0


class AddressListCsvImportForm(forms.Form):
    list = forms.ModelChoiceField(queryset=AddressList.objects.all(), required=True)
    csv_file = forms.FileField()


@admin.register(AddressList)
class AddressListAdmin(ScorerModelAdmin):
    list_display = ["name", "address_count"]
    inlines = [AddressListMemberInline]
    change_list_template = "account/addresslist_changelist.html"

    def get_readonly_fields(self, request, obj=None):
        # This makes name read-only after creation, but editable during creation
        if obj:
            return ["name"]
        else:
            return []

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
            duplicate_count = 0
            success_count = 0
            for row in reader:
                address = row[0].strip()
                try:
                    AddressListMember.objects.create(address=address, list=address_list)
                    success_count += 1
                except Exception:
                    duplicate_count += 1
                    continue

            self.message_user(
                request,
                "Imported %d addresses, skipped %d duplicates"
                % (success_count, duplicate_count),
            )
            return redirect("..")
        form = AddressListCsvImportForm()
        payload = {"form": form}
        return render(request, "account/address_list_csv_import_form.html", payload)
