from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional, Type

from django.conf import settings
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils.deconstruct import deconstructible
from rest_framework_api_key.models import AbstractAPIKey

import api_logging as logging
from scorer_weighted.models import BinaryWeightedScorer, Scorer, WeightedScorer

from .deduplication import Rules

log = logging.getLogger(__name__)

Q = models.Q
tz = timezone.utc


HEXA_RE = re.compile("^0x[A-Fa-f0-9]+$")
HEXA_VALID = RegexValidator(HEXA_RE, "Enter a valid hex string ", "invalid")
RGB_HEXA_RE = re.compile("^#[A-Fa-f0-9]{6}$")
RGB_HEXA_VALID = RegexValidator(
    RGB_HEXA_RE, "Enter a valid RGBA color as hex string ", "invalid"
)
RGBA_HEXA_RE = re.compile("^#[A-Fa-f0-9]{8}$")
RGBA_HEXA_VALID = RegexValidator(
    RGBA_HEXA_RE, "Enter a valid RGBA color as hex string ", "invalid"
)


@deconstructible
class ForbiddenList:
    forbidden_values = []
    message = "Forbidden vaue has been used"
    code = "invalid"

    def __init__(self, forbidden_values=None, code=None, message=None):
        if forbidden_values is not None:
            self.forbidden_values = forbidden_values
        if code is not None:
            self.code = code
        if message is not None:
            self.message = message

    def __call__(self, value):
        """
        Validate that the input is not amongst the forbidden vaules.
        """
        if value in self.forbidden_values:
            raise ValidationError(self.message, code=self.code, params={"value": value})


class HexStringField(models.CharField):
    def __init__(self, *args, **kwargs):
        if "validators" not in kwargs:
            kwargs["validators"] = [HEXA_VALID]

        super(HexStringField, self).__init__(*args, **kwargs)

    def get_prep_value(self, value):
        return str(value).lower()


class RGBAHexColorField(models.CharField):
    def __init__(self, *args, **kwargs):
        if "validators" not in kwargs:
            kwargs["validators"] = [RGB_HEXA_VALID]

        if "max_length" not in kwargs:
            kwargs["max_length"] = 7

        super(RGBAHexColorField, self).__init__(*args, **kwargs)

    def get_prep_value(self, value):
        if value is None:
            return None
        return str(value).lower()


class RGBHexColorField(models.CharField):
    def __init__(self, *args, **kwargs):
        if "validators" not in kwargs:
            kwargs["validators"] = [RGB_HEXA_VALID]

        if "max_length" not in kwargs:
            kwargs["max_length"] = 7

        super(RGBHexColorField, self).__init__(*args, **kwargs)

    def get_prep_value(self, value):
        if value is None:
            return None
        return str(value).lower()


class ReactNodeField(models.TextField):
    def __init__(self, *args, **kwargs):
        super(ReactNodeField, self).__init__(*args, **kwargs)


class EthAddressField(models.CharField):
    def __init__(self, *args, **kwargs):
        if "max_length" not in kwargs:
            kwargs["max_length"] = 42
        super().__init__(*args, **kwargs)

    def get_prep_value(self, value):
        return str(value).lower()


class EthSignature(HexStringField):
    """
    Stores an ETH signature in hex format at like: '0x...'
    The value will always be converted to lowercase
    """

    def __init__(self, *args, **kwargs):
        if "max_length" not in kwargs:
            kwargs["max_length"] = 132
        super().__init__(*args, **kwargs)


class NonceField(models.CharField):
    """
    Field to store a Nonce
    """

    def __init__(self, *args, **kwargs):
        if "max_length" not in kwargs:
            kwargs["max_length"] = 60
        super().__init__(*args, **kwargs)

    def get_prep_value(self, value):
        return str(value).lower()


class Nonce(models.Model):
    nonce = NonceField(blank=False, null=False, unique=True, db_index=True)
    created_on = models.DateTimeField(auto_now_add=True)
    expires_on = models.DateTimeField(null=True, blank=True)
    was_used = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.nonce} - used={self.was_used} - expires_on={self.expires_on}"

    def mark_as_used(self):
        self.was_used = True
        self.save()

    @classmethod
    def create_nonce(cls: Type[Nonce], ttl: Optional[int] = None) -> Nonce:
        expires_on = datetime.now(tz) + timedelta(seconds=ttl) if ttl else None

        nonce = Nonce(nonce=secrets.token_hex(30), expires_on=expires_on)
        nonce.save()

        return nonce

    @classmethod
    def validate_nonce(cls: Type[Nonce], nonce: str) -> Nonce:
        try:
            log.debug("Checking nonce: %s", nonce)
            return Nonce.objects.filter(
                Q(nonce=nonce),
                (Q(expires_on__isnull=True) | Q(expires_on__gt=datetime.now(tz))),
                Q(was_used=False),
            ).get()
        except Nonce.DoesNotExist:
            # Re-raise the exception
            raise

    @classmethod
    async def avalidate_nonce(cls: Type[Nonce], nonce: str) -> Nonce:
        try:
            log.debug("Checking nonce: %s", nonce)
            return await Nonce.objects.filter(
                Q(nonce=nonce),
                (Q(expires_on__isnull=True) | Q(expires_on__gt=datetime.now(tz))),
                Q(was_used=False),
            ).aget()
        except Nonce.DoesNotExist:
            # Re-raise the exception
            raise

    @classmethod
    def use_nonce(cls: Type[Nonce], nonce: str):
        try:
            nonceRecord = cls.validate_nonce(nonce)
            nonceRecord.was_used = True
            nonceRecord.save()
            return True
        except Exception:
            log.error("Error when validating nonce", exc_info=True)
            return False

    @classmethod
    async def ause_nonce(cls: Type[Nonce], nonce: str):
        try:
            nonceRecord = await cls.avalidate_nonce(nonce)
            nonceRecord.was_used = True
            await nonceRecord.asave()
            return True
        except Exception:
            log.error("Error when validating nonce", exc_info=True)
            return False


class RateLimits(str, Enum):
    TIER_1 = "125/15m"
    TIER_2 = "350/15m"
    TIER_3 = "2000/15m"
    UNLIMITED = ""

    def __str__(self):
        return f"{self.name} - {self.value}"


class AnalysisRateLimits(str, Enum):
    TIER_1 = "15/15m"
    TIER_2 = "350/15m"
    TIER_3 = "2000/15m"
    UNLIMITED = ""

    def __str__(self):
        return f"{self.name} - {self.value}"


class Account(models.Model):
    address = EthAddressField(max_length=100, blank=False, null=False, db_index=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="account"
    )

    def __str__(self):
        return f"Account #{self.id} - {self.address} - {self.user_id}"


class AccountAPIKey(AbstractAPIKey):
    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="api_keys", default=None
    )

    rate_limit = models.CharField(
        max_length=20,
        choices=[(limit.value, limit) for limit in RateLimits],
        default=RateLimits.TIER_1.value,
        null=True,
        blank=True,
    )

    analysis_rate_limit = models.CharField(
        max_length=20,
        choices=[(limit.value, limit) for limit in AnalysisRateLimits],
        default=AnalysisRateLimits.TIER_1.value,
        null=True,
        blank=True,
    )

    submit_passports = models.BooleanField(default=True)
    read_scores = models.BooleanField(default=True)
    create_scorers = models.BooleanField(default=False)

    @admin.display(description="Rate Limit")
    def rate_limit_display(self):
        if self.rate_limit == "" or self.rate_limit is None:
            return "Unlimited"
        return str(RateLimits(self.rate_limit))

    @admin.display(description="Analysis Rate Limit")
    def analysis_rate_limit_display(self):
        if self.analysis_rate_limit == "" or self.analysis_rate_limit is None:
            return "Unlimited"
        return str(AnalysisRateLimits(self.analysis_rate_limit))


class AccountAPIKeyAnalytics(models.Model):
    api_key = models.ForeignKey(
        AccountAPIKey, on_delete=models.CASCADE, related_name="analytics"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        null=True,
        blank=True,
        db_index=True,
    )
    path = models.CharField(max_length=1000, blank=False, null=False, default="/")
    base_path = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        db_index=True,
    )

    path_segments = models.JSONField(
        help_text="Contains the parameters that are passed in the path segments",
        default=list,
        null=True,
        db_index=True,
    )

    query_params = models.JSONField(
        help_text="Contains the parameters that are passed in the query (get) parameters",
        null=True,
        db_index=True,
    )
    payload = models.JSONField(
        help_text="Contains the payload sent as part of the HTTP request body",
        null=True,
        db_index=True,
    )
    headers = models.JSONField(
        help_text="Contains the HTTP headers from the request", null=True
    )
    response = models.JSONField(
        help_text="Contains the response, unless response_skipped is set to True",
        null=True,
    )
    response_skipped = models.BooleanField(
        help_text="Indicates that the response response is not filled in this record. This will typically happen for large responses (when reading pages of data)",
        null=True,
        db_index=True,
    )
    error = models.TextField(help_text="Error that occured", null=True, db_index=True)


def get_default_community_scorer():
    """Returns the default scorer that shall be used for communities"""
    ws = WeightedScorer()
    ws.save()
    return ws


class Community(models.Model):
    class Meta:
        verbose_name_plural = "Communities"
        constraints = [
            # UniqueConstraint for non-deleted records
            models.UniqueConstraint(
                fields=["account", "name"],
                name="unique_non_deleted_name_per_account",
                condition=Q(deleted_at__isnull=True),
            ),
            # UniqueConstraint for deleted records
            models.UniqueConstraint(
                fields=["account", "name", "deleted_at"],
                name="unique_deleted_name_per_account",
                condition=Q(deleted_at__isnull=False),
            ),
        ]

    name = models.CharField(max_length=100, blank=False, null=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    rule = models.CharField(
        max_length=100,
        blank=False,
        null=False,
        default=Rules.LIFO.value,
        choices=Rules.choices(),
    )
    description = models.CharField(
        max_length=100, blank=False, null=False, default="My community"
    )
    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="community", default=None
    )
    scorer = models.ForeignKey(
        Scorer, on_delete=models.CASCADE, default=get_default_community_scorer
    )
    use_case = models.CharField(
        blank=True,
        null=True,
        max_length=100,
        help_text="The use case that the creator of this community (Scorer) would like to cover",
    )

    external_scorer_id = models.CharField(
        max_length=42, unique=True, null=True, blank=True
    )

    def __repr__(self):
        return f"<Community {self.name}>"

    def __str__(self):
        return f"Community - #{self.id}, name={self.name}, account_id={self.account_id}"

    def get_scorer(self) -> Scorer:
        if self.scorer.type == Scorer.Type.WEIGHTED:
            return self.scorer.weightedscorer
        elif self.scorer.type == Scorer.Type.WEIGHTED_BINARY:
            return self.scorer.binaryweightedscorer

    async def aget_scorer(self) -> Scorer:
        scorer = await Scorer.objects.aget(pk=self.scorer_id)
        if scorer.type == Scorer.Type.WEIGHTED:
            return await WeightedScorer.objects.aget(scorer_ptr_id=scorer.id)
        elif scorer.type == Scorer.Type.WEIGHTED_BINARY:
            return await BinaryWeightedScorer.objects.aget(scorer_ptr_id=scorer.id)


alphanumeric = RegexValidator(
    r"^[0-9a-zA-Z]*$", "Only alphanumeric characters are allowed."
)


class AddressList(models.Model):
    name = models.CharField(
        max_length=100,
        db_index=True,
        unique=True,
        null=False,
        blank=False,
        validators=[alphanumeric],
    )

    def __str__(self):
        return f"AllowList - {self.name}"


class AddressListMember(models.Model):
    address = EthAddressField(null=False, blank=False, max_length=100, db_index=True)
    list = models.ForeignKey(
        AddressList,
        related_name="addresses",
        on_delete=models.CASCADE,
        null=False,
        db_index=True,
    )

    class Meta:
        unique_together = ["address", "list"]


class Customization(models.Model):
    class CustomizationLogoBackgroundType(models.TextChoices):
        DOTS = "DOTS"
        NONE = "NONE"

    class CustomizationOnChainButtonAction(models.TextChoices):
        SIMPLE_LINK = "Simple Link"
        ONCHAIN_PUSH = "Onchain Push"

    path = models.CharField(
        max_length=100,
        db_index=True,
        null=False,
        blank=False,
        unique=True,
        validators=[],
    )
    scorer_panel_title = models.CharField(
        help_text="This is the title for the scorer panel",
        max_length=100,
        null=True,
        blank=True,
        unique=False,
    )
    scorer_panel_text = models.TextField(
        help_text="This is the text for the scorer panel",
        null=True,
        blank=True,
        unique=False,
    )
    scorer = models.OneToOneField(Community, on_delete=models.PROTECT)
    use_custom_dashboard_panel = models.BooleanField(default=False)

    # CustomizationTheme
    customization_background_1 = RGBHexColorField(
        help_text="Background color 1. RGB hex value expected, for example `#aaff66`",
        null=True,
        blank=True,
    )
    customization_background_2 = RGBHexColorField(
        help_text="Background color 2. RGB hex value expected, for example `#aaff66`",
        null=True,
        blank=True,
    )
    customization_foreground_1 = RGBHexColorField(
        help_text="Foreground color. RGB hex value expected, for example `#aaff66`",
        null=True,
        blank=True,
    )

    customization_background_3 = RGBHexColorField(
        help_text="Action button background color. RGB hex value expected, for example `#aaff66`",
        null=True,
        blank=True,
    )

    customization_foreground_2 = RGBHexColorField(
        help_text="Action button text color. RGB hex value expected, for example `#aaff66`",
        null=True,
        blank=True,
    )

    # Logo
    logo_image = ReactNodeField(
        help_text="The logo in SVG format", null=True, blank=True
    )
    logo_caption = ReactNodeField(
        help_text="The caption as text or react node object", null=True, blank=True
    )
    logo_background = models.CharField(
        max_length=10,
        choices=CustomizationLogoBackgroundType.choices,
        blank=True,
        null=True,
    )

    # Body
    body_main_text = ReactNodeField(
        help_text="The body main text", null=True, blank=True
    )
    body_sub_text = ReactNodeField(help_text="The body sub text", null=True, blank=True)
    body_action_text = models.TextField(
        blank=True,
        null=True,
    )
    body_action_url = models.URLField(
        blank=True,
        null=True,
    )

    button_action_type = models.CharField(
        max_length=25,
        choices=CustomizationOnChainButtonAction.choices,
        default=CustomizationOnChainButtonAction.SIMPLE_LINK,
    )

    body_display_info_tooltip = models.BooleanField(default=False)
    body_info_tooltip_text = ReactNodeField(
        help_text="The info tooltip text", null=True, blank=True
    )

    show_explanation_panel = models.BooleanField(
        default=True, help_text="Toggle to show or hide the middle component"
    )

    def get_customization_dynamic_weights(self) -> dict:
        weights = {}
        for allow_list in self.allow_lists.all():
            weights[f"AllowList#{allow_list.address_list.name}"] = str(
                allow_list.weight
            )

        for custom_github_stamp in self.custom_github_stamps.all():
            weights[
                f"CustomGithubStamp#{custom_github_stamp.category}#{custom_github_stamp.value}"
            ] = str(custom_github_stamp.weight)

        return weights

    async def aget_customization_dynamic_weights(self) -> dict:
        weights = {}
        async for allow_list in self.allow_lists.all():
            address_list = await AddressList.objects.aget(pk=allow_list.address_list_id)
            weights[f"AllowList#{address_list.name}"] = str(allow_list.weight)

        async for custom_github_stamp in self.custom_github_stamps.all():
            weights[
                f"CustomGithubStamp#{custom_github_stamp.category}#{custom_github_stamp.value}"
            ] = str(custom_github_stamp.weight)

        return weights


class IncludedChainId(models.Model):
    chain_id = models.CharField(max_length=200, blank=False, null=False)
    customization = models.ForeignKey(
        Customization, on_delete=models.CASCADE, related_name="included_chain_ids"
    )

    class Meta:
        unique_together = ["chain_id", "customization"]


class AllowList(models.Model):
    address_list = models.ForeignKey(
        AddressList, on_delete=models.PROTECT, related_name="allow_lists"
    )

    customization = models.ForeignKey(
        Customization, on_delete=models.PROTECT, related_name="allow_lists"
    )

    weight = models.DecimalField(default=0.0, max_digits=7, decimal_places=4)


class CustomGithubStamp(models.Model):
    class Category(models.TextChoices):
        REPOSITORY = "repo"
        ORGANIZATION = "org"

    customization = models.ForeignKey(
        Customization, on_delete=models.PROTECT, related_name="custom_github_stamps"
    )

    category = models.CharField(
        max_length=4,
        choices=Category.choices,
        blank=False,
    )

    value = models.CharField(
        max_length=100,
        blank=False,
        null=False,
        help_text="The repository (e.g. 'passportxyz/passport-scorer') or organization name (e.g. 'passportxyz')",
    )

    weight = models.DecimalField(default=0.0, max_digits=7, decimal_places=4)
