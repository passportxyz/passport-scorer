#!/usr/bin/env python
"""
Extract SQL queries from Django ORM for internal API endpoints
"""
import os
import sys
import django
from datetime import datetime, timezone

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scorer.settings")
sys.path.insert(0, '/workspace/project/api')
django.setup()

from django.db import connection
from django.db.models import Q, Count, Sum
from ceramic_cache.models import Ban, Revocation, CeramicCache
from stake.models import Stake
from cgrants.models import GrantContributionIndex, ProtocolContributions, SquelchedAccounts
from account.models import AddressList, AddressListMember, CustomCredentialRuleset
from registry.models import GTCStakeEvent


def print_query(name, queryset):
    """Print the SQL query for a queryset"""
    print(f"\n{'='*60}")
    print(f"ENDPOINT: {name}")
    print(f"{'='*60}")
    try:
        # Get the SQL query
        sql = str(queryset.query) if hasattr(queryset, 'query') else str(queryset)
        print(f"SQL:\n{sql}")
    except Exception as e:
        print(f"Error getting query: {e}")
    print()


def extract_ban_check_queries():
    """Extract queries for /internal/check-bans"""
    address = "0x1234567890abcdef1234567890abcdef12345678"
    hashes = ["hash1", "hash2", "hash3"]

    # Main ban query
    bans_query = Ban.objects.filter(
        Q(address=address) | Q(hash__in=hashes)
    ).filter(
        Q(end_time__isnull=True) | Q(end_time__gt=datetime(2024, 1, 1, tzinfo=timezone.utc))
    )

    print_query("/internal/check-bans - Get bans", bans_query)


def extract_revocation_queries():
    """Extract queries for /internal/check-revocations"""
    proof_values = ["proof1", "proof2", "proof3"]

    revocations_query = Revocation.objects.filter(
        proof_value__in=proof_values
    ).values_list("proof_value", flat=True)

    print_query("/internal/check-revocations - Check revocations", revocations_query)


def extract_stake_queries():
    """Extract queries for /internal/stake/gtc/{address}"""
    address = "0x1234567890abcdef1234567890abcdef12345678"

    # GTC stake query
    stakes_query = Stake.objects.filter(
        Q(staker=address) | Q(stakee=address)
    )

    print_query("/internal/stake/gtc/{address} - Get stakes", stakes_query)

    # Legacy GTC stake query
    round_id = 1
    legacy_stakes = GTCStakeEvent.objects.filter(
        Q(staker=address) | Q(staked=address),
        round_id=round_id
    )

    print_query("/internal/stake/legacy-gtc/{address}/{round_id}", legacy_stakes)


def extract_cgrants_queries():
    """Extract queries for /internal/cgrants/contributor_statistics"""
    address = "0x1234567890abcdef1234567890abcdef12345678"

    # Check if squelched
    squelched = SquelchedAccounts.objects.filter(address=address)
    print_query("/internal/cgrants - Check if squelched", squelched)

    # cgrants contributions
    identifier_query = Q(contributor_address=address)
    contributions = GrantContributionIndex.objects.filter(
        identifier_query, contribution__success=True
    )

    # Number of grants
    num_grants = contributions.order_by("grant_id").values("grant_id").distinct()
    print_query("/internal/cgrants - Count unique grants", num_grants)

    # Total amount
    total_amount = contributions.aggregate(
        total_contribution_amount=Sum("amount")
    )
    print(f"\n{'='*60}")
    print(f"ENDPOINT: /internal/cgrants - Total contribution amount")
    print(f"{'='*60}")
    print(f"AGGREGATE: Uses Sum('amount') on the filtered contributions")
    print()

    # Protocol contributions
    protocol_contribs = ProtocolContributions.objects.filter(
        Q(from_address=address) | Q(to_address=address)
    )
    print_query("/internal/cgrants - Protocol contributions", protocol_contribs)

    # Count protocol rounds
    num_rounds = protocol_contribs.values("round").distinct()
    print_query("/internal/cgrants - Count unique rounds", num_rounds)

    # Sum protocol amounts
    from_amount = protocol_contribs.filter(from_address=address).aggregate(
        total=Sum("amount")
    )
    to_amount = protocol_contribs.filter(to_address=address).aggregate(
        total=Sum("amount")
    )
    print(f"\n{'='*60}")
    print(f"ENDPOINT: /internal/cgrants - Protocol contribution amounts")
    print(f"{'='*60}")
    print(f"FROM AGGREGATE: Sum('amount') WHERE from_address = address")
    print(f"TO AGGREGATE: Sum('amount') WHERE to_address = address")
    print()


def extract_allow_list_queries():
    """Extract queries for /internal/allow-list/{list}/{address}"""
    list_name = "some_list"
    address = "0x1234567890abcdef1234567890abcdef12345678"

    # Check membership
    is_member = AddressListMember.objects.filter(
        list__name=list_name,
        address=address
    )

    print_query("/internal/allow-list/{list}/{address}", is_member)


def extract_customization_queries():
    """Extract queries for /internal/customization/credential/{provider_id}"""
    provider_id = "some_provider#123"

    # Get custom credential ruleset
    ruleset = CustomCredentialRuleset.objects.filter(
        provider_id=provider_id
    )

    print_query("/internal/customization/credential/{provider_id}", ruleset)


def extract_ceramic_cache_queries():
    """Extract queries used in ceramic cache operations"""
    address = "0x1234567890abcdef1234567890abcdef12345678"
    providers = ["provider1", "provider2"]

    # Soft delete by providers
    soft_delete = CeramicCache.objects.filter(
        address=address,
        provider__in=providers,
        type="V1",
        deleted_at__isnull=True
    )
    print_query("Ceramic Cache - Soft delete stamps", soft_delete)

    # Get stamps from cache
    get_stamps = CeramicCache.objects.filter(
        address=address,
        type="V1",
        deleted_at__isnull=True
    ).order_by("-created_at")
    print_query("Ceramic Cache - Get stamps", get_stamps)


if __name__ == "__main__":
    print("EXTRACTING SQL QUERIES FROM DJANGO ORM")
    print("="*60)

    extract_ban_check_queries()
    extract_revocation_queries()
    extract_stake_queries()
    extract_cgrants_queries()
    extract_allow_list_queries()
    extract_customization_queries()
    extract_ceramic_cache_queries()

    print("\nNOTE: These are the parameterized queries. Actual values would be substituted at runtime.")