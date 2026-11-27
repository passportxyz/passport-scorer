"""Score the verified chain identity without writing legacy score or points rows."""

from datetime import datetime
from decimal import Decimal

from asgiref.sync import async_to_sync, sync_to_async
from django.db import transaction

from account.deduplication.lifo import alifo, get_nullifiers
from account.models import Community
from reader.passport_reader import aget_passport
from registry.atasks import avalidate_credentials_for_identity
from registry.models import ChainWalletScore, Stamp
from registry.utils import get_utc_time
from v2.schema import ChainWalletScoreResponse


def has_scoped_nullifiers(stamp: dict) -> bool:
    subject = stamp["credential"]["credentialSubject"]
    if subject.get("provider") != stamp["provider"]:
        return False
    if not isinstance(subject.get("nullifiers"), list) and "hash" not in subject:
        return False
    nullifiers = get_nullifiers(stamp, all_versions=True)
    return bool(nullifiers) and all(
        isinstance(value, str) and 0 < len(value) <= 100 for value in nullifiers
    )


async def score_chain_wallet(
    address: str, chain_id: int, community: Community
) -> ChainWalletScoreResponse:
    passport_data = await aget_passport(address, chain_id=chain_id)
    validated = await avalidate_credentials_for_identity(
        address, passport_data, chain_id=chain_id
    )
    validated["stamps"] = [
        stamp for stamp in validated["stamps"] if has_scoped_nullifiers(stamp)
    ]
    return await persist_chain_wallet_score(address, chain_id, community, validated)


@sync_to_async
@transaction.atomic
def persist_chain_wallet_score(
    address: str, chain_id: int, community: Community, validated: dict
) -> ChainWalletScoreResponse:
    deduped, _, clashes = async_to_sync(alifo)(
        community, validated, address, chain_id=chain_id
    )

    scorer = community.get_scorer()
    stamps = [Stamp(**stamp) for stamp in deduped["stamps"]]
    # The existing recompute path accepts stamps directly. Scoped scores never
    # create a legacy Passport row or write to the address-only score history.
    [score] = scorer.recompute_score([0], {0: stamps}, community.pk)
    scored_stamps = {
        provider: {
            "score": f"{Decimal(str(weight)):.5f}",
            "dedup": False,
            "expiration_date": score.stamp_expiration_dates[provider].isoformat(),
        }
        for provider, weight in score.stamp_scores.items()
    }
    for provider, stamp in (clashes or {}).items():
        if provider not in scored_stamps:
            scored_stamps[provider] = {
                "score": "0.00000",
                "dedup": True,
                "expiration_date": datetime.fromisoformat(
                    stamp["credential"]["expirationDate"]
                ).isoformat(),
            }
    result = ChainWalletScoreResponse(
        chain_id=chain_id,
        address=address,
        score=score.evidence[0].rawScore,
        passing_score=bool(score.score),
        last_score_timestamp=get_utc_time().isoformat(),
        expiration_timestamp=(
            score.expiration_date.isoformat() if score.expiration_date else None
        ),
        threshold=Decimal(str(scorer.threshold)),
        error=None,
        stamps=scored_stamps,
    )
    ChainWalletScore.objects.update_or_create(
        community=community,
        chain_id=chain_id,
        address=address,
        defaults={"response": result.model_dump(mode="json")},
    )
    return result
