from account.models import EthAddressField
from django.db import models


# Stores the current summary for each (chain, staker, stakee) combo
class Stake(models.Model):
    class Chain(models.IntegerChoices):
        ETHEREUM = 0, "Ethereum"
        OPTIMISM = 1, "Optimism"

    chain = models.SmallIntegerField(
        choices=Chain.choices, default=Chain.ETHEREUM, db_index=True
    )
    lock_time = models.DateTimeField(null=False, blank=False)
    unlock_time = models.DateTimeField(null=False, blank=False)

    last_updated_in_block = models.DecimalField(
        decimal_places=0,
        null=False,
        blank=False,
        max_digits=78,
        db_index=True,
        help_text="Block number (uint256) in which the stake was last updated (including slash/release)",
    )

    # For self-stake, staker and stakee are the same
    staker = EthAddressField(null=False, blank=False, db_index=True)
    stakee = EthAddressField(null=False, blank=False, db_index=True)

    current_amount = models.DecimalField(
        decimal_places=0,
        null=False,
        blank=False,
        max_digits=78,
        help_text="Summary stake amount (uint256)",
    )

    class Meta:
        unique_together = ["staker", "stakee", "chain"]


# Stores raw staking events, for analysis and debugging
class StakeEvent(models.Model):
    class StakeEventType(models.TextChoices):
        SELF_STAKE = "SST"
        COMMUNITY_STAKE = "CST"
        SELF_STAKE_WITHDRAW = "SSW"
        COMMUNITY_STAKE_WITHDRAW = "CSW"
        SLASH = "SLA"
        RELEASE = "REL"

    event_type = models.CharField(
        max_length=3,
        choices=StakeEventType.choices,
        blank=False,
        db_index=True,
    )

    chain = models.SmallIntegerField(
        choices=Stake.Chain.choices, null=False, blank=False, db_index=True
    )

    # For self-stake, staker and stakee are the same
    staker = EthAddressField(null=False, blank=False, db_index=True)
    stakee = EthAddressField(null=False, blank=False, db_index=True)

    amount = models.DecimalField(
        decimal_places=0, null=False, blank=False, max_digits=78
    )

    block_number = models.DecimalField(
        decimal_places=0, null=False, blank=False, max_digits=78
    )

    tx_hash = models.CharField(max_length=66, null=False, blank=False)

    # Only applies to SelfStake and CommunityStake events
    unlock_time = models.DateTimeField(null=True, blank=True)
