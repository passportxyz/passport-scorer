"""
Models for data from cgrants.
We only define fields in this model that we are directly interested in,
and we store the JSON dump of the recoords containing all the fields
from the original record in the `data` attribute
"""
from account.models import EthAddressField
from django.db import models
from django.utils.translation import gettext_lazy as _


class Profile(models.Model):
    """
    Original model: https://github.com/gitcoinco/web/blob/master/app/dashboard/models.py#L2982
    """

    handle = models.CharField(
        max_length=255,
        db_index=True,
        unique=True,
        help_text="DEPRECATED: The github handle of the user. This has been deprecated in favour of github_id.",
    )
    github_id = models.BigIntegerField(
        help_text=_(
            "This is the github users unique id. This should not change even if the user changes his handle."
        ),
        db_index=True,
        blank=True,
        null=True,
        unique=True,
    )
    notes = models.TextField(
        help_text=_(
            "These notes are intended for the support team, in case they make manual adjustments to the profile."
        ),
        null=True,
        blank=True,
    )
    data = models.JSONField(
        help_text=_("Original profile data in JSON format"), default=dict
    )

    def __str__(self):
        return f"{self.github_id} - {self.handle}"


class Grant(models.Model):
    """
    Original model: https://github.com/gitcoinco/web/blob/master/app/grants/models/grant.py
    """

    admin_profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
    )
    hidden = models.BooleanField(
        default=False,
        help_text=_("Hide the grant from the /grants page?"),
        db_index=True,
    )
    active = models.BooleanField(
        default=True, help_text=_("Whether or not the Grant is active."), db_index=True
    )
    is_clr_eligible = models.BooleanField(
        default=True, help_text="Is grant eligible for CLR"
    )

    data = models.JSONField(
        help_text=_("Original grant data in JSON format"), default=dict
    )


class Subscription(models.Model):
    """
    Original model: https://github.com/gitcoinco/web/blob/master/app/grants/models/subscription.py
    """

    grant = models.ForeignKey(
        Grant,
        on_delete=models.CASCADE,
    )
    contributor_profile = models.ForeignKey(
        Profile,
        related_name="grant_contributor",
        on_delete=models.CASCADE,
        null=True,
        help_text=_("The Subscription contributor's Profile."),
    )

    is_mainnet = models.BooleanField(
        help_text=_("Is the network for this subscription mainnet?"),
        default=False,
    )
    data = models.JSONField(
        help_text=_("Original subscription data in JSON format"), default=dict
    )


class Contribution(models.Model):
    """
    Original model: https://github.com/gitcoinco/web/blob/master/app/grants/models/contribution.py
    """

    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
    )
    success = models.BooleanField(
        default=False,
    )

    amount_per_period_usdt = models.DecimalField(
        default=0,
        decimal_places=18,
        max_digits=64,
        help_text=_("The amount per contribution period in USDT"),
    )

    data = models.JSONField(
        help_text=_("Original contribution data in JSON format"), default=dict
    )


class GrantCLR(models.Model):
    """
    Original model: https://github.com/gitcoinco/web/blob/master/app/grants/models/grant.py#L89
    """

    CLR_TYPES = (
        ("main", "Main Round"),
        ("ecosystem", "Ecosystem Round"),
        ("cause", "Cause Round"),
    )
    type = models.CharField(
        max_length=25, choices=CLR_TYPES, default="main", help_text="Grant CLR Type"
    )
    data = models.JSONField(
        help_text=_("Original contribution data in JSON format"), default=dict
    )


class GrantCLRCalculation(models.Model):
    """
    Original model: https://github.com/gitcoinco/web/blob/master/app/grants/models/grant_clr_calculation.py
    """

    active = models.BooleanField(
        default=False, db_index=True, help_text="Is this calc active?"
    )
    latest = models.BooleanField(
        default=False, db_index=True, help_text="Is this calc the latest?"
    )

    grant = models.ForeignKey(
        Grant,
        on_delete=models.CASCADE,
        related_name="clr_calculations",
        help_text=_("The grant"),
    )
    grantclr = models.ForeignKey(
        GrantCLR,
        on_delete=models.CASCADE,
        related_name="clr_calculations",
        help_text=_("The grant CLR Round"),
    )

    data = models.JSONField(
        help_text=_("Original contribution data in JSON format"), default=dict
    )


class SquelchProfile(models.Model):
    """
    Original model: https://github.com/gitcoinco/web/blob/master/app/townsquare/models.py#L439-L463
    """

    profile = models.ForeignKey(
        Profile, on_delete=models.CASCADE, related_name="squelches"
    )
    active = models.BooleanField(help_text="Is squelch applied?", default=True)

    data = models.JSONField(
        help_text=_("Original contribution data in JSON format"), default=dict
    )


class GrantContributionIndex(models.Model):
    """
    Stores data brought over from cgrants. Original model: https://github.com/gitcoinco/web/blob/master/app/grants/models/grant_contribution_index.py

    Stores the grants and round number to shich a user contributed to.
    The purpose of this table is to allow a a fast query. This will be used from
    the `contributor_statistics` API"""

    profile = models.ForeignKey(
        Profile,
        help_text=_("Contributor"),
        on_delete=models.CASCADE,
        db_index=True,
    )
    contribution = models.ForeignKey(
        Contribution,
        help_text=_("Contribution"),
        on_delete=models.CASCADE,
        db_index=True,
        null=True,
        blank=True,
    )
    grant = models.ForeignKey(
        Grant,
        help_text=_("The grant a user contributed to"),
        on_delete=models.CASCADE,
    )
    round_num = models.IntegerField(
        help_text=_("The round number a user contributed to"), null=True, blank=True
    )
    amount = models.DecimalField(
        default=0,
        decimal_places=18,
        max_digits=64,
        db_index=True,
        help_text=_("The USD amount contributed"),
    )


class ProtocolContributions(models.Model):
    """
    This will store allo protocol contributions.
    The data in this table was produced by the allo indexer, see: https://github.com/gitcoinco/allo-indexer
    """

    ext_id = models.CharField(
        null=False, blank=False, max_length=66, db_index=True, unique=True, default=""
    )
    contributor = EthAddressField(
        null=False, blank=False, max_length=100, db_index=True, default=""
    )
    round = EthAddressField(
        null=False, blank=False, max_length=100, db_index=True, default=""
    )
    project = EthAddressField(
        null=False, blank=False, max_length=100, db_index=True, default=""
    )
    amount = models.DecimalField(
        default=0,
        decimal_places=18,
        max_digits=64,
        db_index=True,
        help_text=_("The USD amount contributed"),
    )
    data = models.JSONField(
        help_text=_("Original contribution data in JSON format"), default=dict
    )
