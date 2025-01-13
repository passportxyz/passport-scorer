from django.db import models

from account.models import EthAddressField


# Stores the current summary for each (chain, staker, stakee) combo
class Stake(models.Model):
    chain = models.IntegerField(
        null=False, blank=False, db_index=True, help_text="Decimal chain ID"
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
        decimal_places=18,
        null=False,
        blank=False,
        max_digits=78,
        help_text="Summary stake amount",
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

    chain = models.IntegerField(
        null=False, blank=False, db_index=True, help_text="Decimal chain ID"
    )

    # For self-stake, staker and stakee are the same
    staker = EthAddressField(null=False, blank=False, db_index=True)
    stakee = EthAddressField(null=False, blank=False, db_index=True)

    amount = models.DecimalField(
        decimal_places=18, null=False, blank=False, max_digits=78
    )

    block_number = models.DecimalField(
        decimal_places=0, null=False, blank=False, max_digits=78, db_index=True
    )

    tx_hash = models.CharField(max_length=66, null=False, blank=False)

    # Only applies to SelfStake and CommunityStake events
    unlock_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ["tx_hash", "chain", "stakee"]


class ReindexRequest(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)

    chain = models.IntegerField(
        null=False,
        blank=False,
        db_index=True,
        help_text="Decimal chain ID. Ethereum: 1, Optimism: 10, Arbitrum: 42161",
    )

    start_block_number = models.DecimalField(
        decimal_places=0, null=False, blank=False, max_digits=78
    )

    pending = models.BooleanField(null=False, blank=False, default=True, db_index=True)

    class Meta:
        # Only one reindex request can be pending at a time for a chain
        constraints = [
            models.UniqueConstraint(
                fields=["chain"],
                name="unique_only_one_pending_per_chain",
                condition=models.Q(pending=True),
            ),
        ]


class LastBlock(models.Model):
    chain = models.IntegerField(
        null=False,
        blank=False,
        db_index=True,
        unique=True,
        # The legacy indexer is using totally different rust code from the new indexer, so
        # instead of passing its chain ID, it's just passing a hardcoded "0"
        help_text="Decimal chain ID. Ethereum: 1, Optimism: 10, Arbitrum: 42161, Legacy: 0",
    )

    block_number = models.DecimalField(
        decimal_places=0, null=False, blank=False, max_digits=78, db_index=True
    )
