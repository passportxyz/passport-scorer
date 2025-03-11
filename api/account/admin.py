import csv
import json
from math import exp
from operator import ge

import boto3
from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.timezone import now
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
    AnalysisRateLimits,
    Community,
    CustomCredential,
    CustomCredentialRuleset,
    Customization,
    CustomPlatform,
    IncludedChainId,
    RateLimits,
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

    def generate_statements(self, api_keys_list):
        statements = [
            {
                "ByteMatchStatement": {
                    "SearchString": f"{api_key.prefix}.",
                    "FieldToMatch": {"SingleHeader": {"Name": "x-api-key"}},
                    "TextTransformations": [{"Priority": 0, "Type": "NONE"}],
                    "PositionalConstraint": "STARTS_WITH",
                }
            }
            for api_key in api_keys_list
        ]
        return statements

    def upload_to_s3(self, json_input, filename):
        S3_BUCKET_NAME = settings.S3_BUCKET_WAF
        try:
            s3_client = boto3.client("s3")
            s3_client.put_object(
                Bucket=S3_BUCKET_NAME,
                Key=filename,
                Body=json_input,
                ContentType="application/json",
            )
            return True
        except Exception as e:
            print(f"Failed to upload to S3: {e}")
            return False

    def manage_revoked_or_expired_waf_rule(self, name, priority, file_name):
        # [BLOCK] Create rule for the revoked & expired keys
        ###################################################################################
        revoked_or_expired_keys = AccountAPIKey.objects.filter(
            revoked=True  # Revoked keys
        ) | AccountAPIKey.objects.filter(
            expiry_date__isnull=False,  # Ensure expiry_date is set
            expiry_date__lte=now(),  # Expiry date is in the past
        )

        revoked_or_expired_waf_rule = {}
        if len(revoked_or_expired_keys) > 0:
            revoked_or_expired_statements = self.generate_statements(
                revoked_or_expired_keys
            )
            if len(revoked_or_expired_statements) == 1:
                revoked_or_expired_condition = revoked_or_expired_statements[0]
            else:
                revoked_or_expired_condition = {
                    "OrStatement": {"Statements": revoked_or_expired_statements}
                }

            revoked_or_expired_waf_rule = {
                "Name": name,
                "Priority": priority,
                "Action": {
                    "Block": {
                        "CustomResponse": {
                            "ResponseCode": 401,  # TODO: add message to response
                        }
                    }
                },
                "Statement": revoked_or_expired_condition,
                "VisibilityConfig": {
                    "SampledRequestsEnabled": True,
                    "CloudWatchMetricsEnabled": True,
                    "MetricName": name,
                },
            }

        revoked_or_expired_waf_json = json.dumps(revoked_or_expired_waf_rule, indent=3)
        self.upload_to_s3(revoked_or_expired_waf_json, file_name)

    def manage_analysis_unlimited_waf_rule(self, name, priority, file_name):
        # [ALLOW] Create rule for the analysis unlimited keys
        ###################################################################################
        analysis_unlimited_keys = AccountAPIKey.objects.filter(
            revoked=False,  # Not revoked
            expiry_date__isnull=True,  # No expiry date
            analysis_rate_limit__isnull=True,  # Unlimited rate limit
        ) | AccountAPIKey.objects.filter(
            revoked=False,  # Not revoked
            expiry_date__gt=now(),  # Expiry date is in the future
            analysis_rate_limit__isnull=True,  # Unlimited rate limit
        )

        analysis_unlimited_waf_rule = {}
        if len(analysis_unlimited_keys) > 0:
            analysis_unlimited_statements = self.generate_statements(
                analysis_unlimited_keys
            )
            if len(analysis_unlimited_statements) == 1:
                analysis_api_key_condition = analysis_unlimited_statements[0]
            else:
                analysis_api_key_condition = {
                    "OrStatement": {"Statements": analysis_unlimited_statements}
                }
            # TODO: adjust the rule to properly group the requests / api key prefix ( count / api key prefix )
            analysis_unlimited_waf_rule = {
                "Name": name,
                "Priority": priority,
                "Action": {"Count": {}},
                "Statement": {
                    "AndStatement": {
                        "Statements": [
                            {
                                "ByteMatchStatement": {
                                    "FieldToMatch": {"UriPath": {}},
                                    "PositionalConstraint": "STARTS_WITH",
                                    "SearchString": "/passport/analysis/",
                                    "TextTransformations": [
                                        {"Priority": 0, "Type": "NONE"}
                                    ],
                                },
                            },
                            analysis_api_key_condition,
                        ]
                    }
                },
                "VisibilityConfig": {
                    "SampledRequestsEnabled": True,
                    "CloudWatchMetricsEnabled": True,
                    "MetricName": name,
                },
            }
        analysis_unlimited_waf_json = json.dumps(analysis_unlimited_waf_rule, indent=3)
        self.upload_to_s3(analysis_unlimited_waf_json, file_name)

    def manage_analyisis_tier_waf_rule(
        self, api_keys, name, priority, limit, file_name
    ):
        analysis_tier_waf_rule = {}
        if len(api_keys) > 0:
            analysis_statements = self.generate_statements(api_keys)
            if len(analysis_statements) == 1:
                analysis_condition = analysis_statements[0]
            else:
                analysis_condition = {
                    "OrStatement": {"Statements": analysis_statements}
                }
            analysis_tier_waf_rule = {
                "Name": name,
                "Priority": priority,
                "Action": {
                    "Block": {
                        "CustomResponse": {
                            "ResponseCode": 429,
                            "ResponseHeaders": [
                                {"Name": "Retry-After", "Value": "300"}
                            ],
                        }
                    }
                },
                "Statement": {
                    "RateBasedStatement": {
                        "Limit": limit,
                        "EvaluationWindowSec": 300,  # 5 minutes
                        "AggregateKeyType": "CUSTOM_KEYS",
                        "CustomKeys": [
                            {
                                "Header": {
                                    "Name": "X-API-Key",
                                    "TextTransformations": [
                                        {"Priority": 0, "Type": "NONE"}
                                    ],
                                }
                            }
                        ],
                        "ScopeDownStatement": {
                            "AndStatement": {
                                "Statements": [
                                    {
                                        # Match /passport/analysis/ path
                                        "ByteMatchStatement": {
                                            "FieldToMatch": {"UriPath": {}},
                                            "PositionalConstraint": "STARTS_WITH",
                                            "SearchString": "/passport/analysis/",
                                            "TextTransformations": [
                                                {"Priority": 0, "Type": "NONE"}
                                            ],
                                        }
                                    },
                                    # Match valid API keys
                                    analysis_condition,
                                ]
                            }
                        },
                    }
                },
                "VisibilityConfig": {
                    "SampledRequestsEnabled": True,
                    "CloudWatchMetricsEnabled": True,
                    "MetricName": name,
                },
            }
        analysis_tier_waf_json = json.dumps(analysis_tier_waf_rule, indent=3)
        self.upload_to_s3(analysis_tier_waf_json, file_name)

    def manage_unlimited_waf_rule(self, name, priority, file_name):
        # [ALLOW] Create rule for the unlimited keys
        ###################################################################################
        active_unlimited_keys = AccountAPIKey.objects.filter(
            revoked=False,  # Not revoked
            expiry_date__isnull=True,  # No expiry date
            rate_limit__isnull=True,  # Unlimited rate limit
        ) | AccountAPIKey.objects.filter(
            revoked=False,  # Not revoked
            expiry_date__gt=now(),  # Expiry date is in the future
            rate_limit__isnull=True,  # Unlimited rate limit
        )
        active_unlimited_waf_rule = {}
        if len(active_unlimited_keys) > 0:
            active_unlimited_statements = self.generate_statements(
                active_unlimited_keys
            )
            # TODO: adjust the rule to properly group the requests / api key prefix ( count / api key prefix )
            if len(active_unlimited_statements) == 1:
                active_unlimited_condition = active_unlimited_statements[0]
            else:
                active_unlimited_condition = {
                    "OrStatement": {"Statements": active_unlimited_statements}
                }

            active_unlimited_waf_rule = {
                "Name": name,
                "Priority": priority,
                "Action": {"Count": {}},
                "Statement": active_unlimited_condition,
                "VisibilityConfig": {
                    "SampledRequestsEnabled": True,
                    "CloudWatchMetricsEnabled": True,
                    "MetricName": name,
                },
            }
        active_unlimited_waf_json = json.dumps(active_unlimited_waf_rule, indent=3)
        self.upload_to_s3(active_unlimited_waf_json, file_name)

    def manage_tier_waf_rule(self, api_keys, name, priority, limit, file_name):
        tier_waf_rule = {}
        if len(api_keys) > 0:
            tier_statements = self.generate_statements(api_keys)
            if len(tier_statements) == 1:
                tier_condition = tier_statements[0]
            else:
                tier_condition = {"OrStatement": {"Statements": tier_statements}}

            tier_waf_rule = {
                "Name": name,
                "Priority": priority,
                "Action": {
                    "Block": {
                        "CustomResponse": {
                            "ResponseCode": 429,
                            "ResponseHeaders": [
                                {"Name": "Retry-After", "Value": "300"}
                            ],
                        }
                    }
                },
                "Statement": {
                    "RateBasedStatement": {
                        "Limit": limit,
                        "EvaluationWindowSec": 300,  # 5 minutes
                        "AggregateKeyType": "CUSTOM_KEYS",
                        "CustomKeys": [
                            {
                                "Header": {
                                    "Name": "X-API-Key",
                                    "TextTransformations": [
                                        {"Priority": 0, "Type": "NONE"}
                                    ],
                                }
                            }
                        ],
                        "ScopeDownStatement": tier_condition,
                    }
                },
                "VisibilityConfig": {
                    "SampledRequestsEnabled": True,
                    "CloudWatchMetricsEnabled": True,
                    "MetricName": name,
                },
            }
        tier_waf_json = json.dumps(tier_waf_rule, indent=3)
        self.upload_to_s3(tier_waf_json, file_name)

    # def manage_
    @admin.action(description="[All] Generate and Upload WAF Rules to S3")
    def generate_waf_json_and_upload(self, request, queryset=None):
        # The first rule    (priority 1) will handle blocked IPs. => managed outside of python code
        # The second rule   (priority 2) will evaluate Invalid API keys. => managed outside of python code
        # <Api key specific rules>
        # The third rule    (priority 3) will evaluate Expired and Revoked API keys.
        # <All analysis / per request rules should be evaluated before the generic API keys evaluation.>
        # The fourth rule   (priority 4) will evaluate Analysis - Tier 3 API keys.
        # The fifth rule    (priority 5) will evaluate Analysis - Tier 2 API keys.
        # The sixth rule    (priority 6) will evaluate Analysis - Tier 1 API keys.
        # <Generic non path restricted rules.>
        # The seventh rule  (priority 7) will evaluate Tier 3 API keys.
        # The eighth rule   (priority 8) will evaluate Tier 2 API keys.
        # The ninth rule    (priority 9) will evaluate Tier 1 API keys
        # The tenth rule    (priority 10) will evaluate Analysis - Unlimites API keys.
        # The eleventh rule (priority 11) will evaluate Unlimites API keys.
        # <The ninth rule should also be the default rule to be evaluated>.

        # [BLOCK] Create rule for the revoked & expired keys
        ###################################################################################
        self.manage_revoked_or_expired_waf_rule(
            name="Expired-RevokedKeys",
            priority=3,
            file_name="03_revoked_or_expired_waf_rule.json",
        )

        # [BLOCK] Analysis tier 3 keys
        ###################################################################################
        analysis_tier_3_keys = AccountAPIKey.objects.filter(
            revoked=False,  # Not revoked
            expiry_date__isnull=True,  # No expiry date
            analysis_rate_limit=AnalysisRateLimits.TIER_3.value,
        ) | AccountAPIKey.objects.filter(
            revoked=False,  # Not revoked
            expiry_date__gt=now(),  # Expiry date is in the future
            analysis_rate_limit=AnalysisRateLimits.TIER_3.value,
        )
        self.manage_analyisis_tier_waf_rule(
            api_keys=analysis_tier_3_keys,
            name="Analysis-Tier-3-Keys",
            priority=4,
            limit=670,
            file_name="04_analysis_tier_3_waf_rule.json",
        )  # almost 2000/15m

        # [BLOCK] Analysis tier 2 keys
        ###################################################################################
        analysis_tier_2_keys = AccountAPIKey.objects.filter(
            revoked=False,  # Not revoked
            expiry_date__isnull=True,  # No expiry date
            analysis_rate_limit=AnalysisRateLimits.TIER_2.value,
        ) | AccountAPIKey.objects.filter(
            revoked=False,  # Not revoked
            expiry_date__gt=now(),  # Expiry date is in the future
            analysis_rate_limit=AnalysisRateLimits.TIER_2.value,
        )
        self.manage_analyisis_tier_waf_rule(
            api_keys=analysis_tier_2_keys,
            name="Analysis-Tier-2-Keys",
            priority=5,
            limit=120,
            file_name="05_analysis_tier_2_waf_rule.json",
        )  # almost 350/15m

        # [BLOCK] Analysis tier 1 keys
        ###################################################################################
        analysis_tier_1_keys = AccountAPIKey.objects.filter(
            revoked=False,  # Not revoked
            expiry_date__isnull=True,  # No expiry date
            analysis_rate_limit=AnalysisRateLimits.TIER_1.value,
        ) | AccountAPIKey.objects.filter(
            revoked=False,  # Not revoked
            expiry_date__gt=now(),  # Expiry date is in the future
            analysis_rate_limit=AnalysisRateLimits.TIER_1.value,
        )
        self.manage_analyisis_tier_waf_rule(
            api_keys=analysis_tier_1_keys,
            name="Analysis-Tier-1-Keys",
            priority=6,
            limit=10,  # Min value
            file_name="06_analysis_tier_1_waf_rule.json",
        )

        # Create rule for the Tier 3 keys
        ###################################################################################
        tier_3_api_keys = AccountAPIKey.objects.filter(
            revoked=False,  # Not revoked
            expiry_date__isnull=True,  # No expiry date
            rate_limit=RateLimits.TIER_3.value,
        ) | AccountAPIKey.objects.filter(
            revoked=False,  # Not revoked
            expiry_date__gt=now(),  # Expiry date is in the future
            rate_limit=RateLimits.TIER_3.value,
        )

        self.manage_tier_waf_rule(
            api_keys=tier_3_api_keys,
            name="Tier-3-Api-Keys",
            priority=7,
            limit=670,  # almost 2000/15m
            file_name="07_tier_3_waf_rule.json",
        )

        # [BLOCK] Analysis tier 2 keys
        ###################################################################################
        tier_2_api_keys = AccountAPIKey.objects.filter(
            revoked=False,  # Not revoked
            expiry_date__isnull=True,  # No expiry date
            rate_limit=RateLimits.TIER_2.value,
        ) | AccountAPIKey.objects.filter(
            revoked=False,  # Not revoked
            expiry_date__gt=now(),  # Expiry date is in the future
            rate_limit=RateLimits.TIER_2.value,
        )
        self.manage_tier_waf_rule(
            api_keys=tier_2_api_keys,
            name="Tier-2-Api-Keys",
            priority=8,
            limit=120,  # almost 350/15m
            file_name="08_tier_2_waf_rule.json",
        )

        # [BLOCK] Tier 1 keys / This should be also the default rule -> TODO
        ###################################################################################
        tier_1_api_keys = AccountAPIKey.objects.filter(
            revoked=False,  # Not revoked
            expiry_date__isnull=True,  # No expiry date
            rate_limit=RateLimits.TIER_1.value,
        ) | AccountAPIKey.objects.filter(
            revoked=False,  # Not revoked
            expiry_date__gt=now(),  # Expiry date is in the future
            rate_limit=RateLimits.TIER_1.value,
        )
        self.manage_tier_waf_rule(
            api_keys=tier_1_api_keys,
            name="Tier-1-Api-Keys",
            priority=9,
            limit=42,  # almost 124/15m
            file_name="09_tier_1_waf_rule.json",
        )

        # [ALLOW] Create rule for the analysis unlimited keys
        ###################################################################################
        self.manage_analysis_unlimited_waf_rule(
            name="Analysis-UnlimitedKeys",
            priority=10,
            file_name="10_analysis_unlimited_waf_rule.json",
        )

        # [ALLOW] Create rule for the unlimited keys
        ###################################################################################
        self.manage_unlimited_waf_rule(
            name="UnlimitedKeys", priority=11, file_name="11_unlimited_waf_rule.json"
        )

    actions = [edit_selected, generate_waf_json_and_upload]


class APIKeyPermissionsAdmin(ScorerModelAdmin):
    list_display = (
        "id",
        "submit_passports",
        "read_scores",
        "create_scorers",
        "historical_endpoint",
    )


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


class CustomCredentialInline(admin.TabularInline):
    model = CustomCredential
    extra = 0


@admin.register(Customization)
class CustomizationAdmin(ScorerModelAdmin):
    form = CustomizationForm
    raw_id_fields = ["scorer"]
    inlines = [
        AllowListInline,
        CustomCredentialInline,
        IncludedChainIdInline,
    ]
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "path",
                    "partner_name",
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


@admin.register(CustomPlatform)
class CustomPlatformAdmin(admin.ModelAdmin):
    list_display = ["name", "display_name", "description"]
    search_display = ["name", "display_name", "description"]


@admin.register(CustomCredentialRuleset)
class CustomCredentialRulesetAdmin(admin.ModelAdmin):
    list_display = ["name", "provider_id", "credential_type"]
    search_fields = ["name", "provider_id", "credential_type"]

    def get_readonly_fields(self, request, obj=None):
        # This makes name read-only after creation, but editable during creation
        if obj:
            return ["credential_type", "definition", "provider_id", "name"]
        else:
            return ["provider_id", "name"]
