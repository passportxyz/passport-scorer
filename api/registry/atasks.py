from datetime import datetime
from typing import Dict, List

import api_logging as logging
from account.deduplication.fifo import afifo
from account.deduplication.lifo import alifo

# --- Deduplication Modules
from account.models import Community, Rules
from ceramic_cache.models import CeramicCache
from ninja_extra.exceptions import APIException
from reader.passport_reader import get_did
from registry.exceptions import NoPassportException
from registry.models import Passport, Score, Stamp
from registry.tasks import get_utc_time
from registry.utils import validate_credential, verify_issuer

from .tasks import get_utc_time

log = logging.getLogger(__name__)


async def aremove_existing_stamps_from_db(passport: Passport):
    await Stamp.objects.filter(passport=passport).adelete()


async def aget_passport(address: str = "", stream_ids: List[str] = []) -> Dict:
    did = get_did(address)

    db_stamp_list = CeramicCache.objects.filter(address=address)

    # TODO: add back loading from ceramic
    # if len(db_stamp_list) == 0:
    #     # get streamIds if non are provided
    #     stream_ids = (
    #         stream_ids
    #         if len(stream_ids) > 0
    #         else get_stream_ids(did, [CERAMIC_GITCOIN_PASSPORT_STREAM_ID])
    #     )

    #     # attempt to pull content
    #     passport = get_stamps(get_passport_stream(stream_ids))

    #     # return a list of wallet address without the @eip155:1 suffix
    #     return passport
    # else:
    return {
        "stamps": [
            {"provider": s.provider, "credential": s.stamp} async for s in db_stamp_list
        ]
    }


async def aload_passport_data(address: str) -> Dict:
    # Get the passport data from the blockchain or ceramic cache
    passport_data = await aget_passport(address)
    if not passport_data:
        raise NoPassportException()

    log.error("=" * 40)
    log.error("=" * 40)
    from pprint import pformat

    log.error("%s", pformat(passport_data))
    log.error("=" * 40)
    log.error("=" * 40)
    return passport_data


async def acalculate_score(passport: Passport, community_id: int, score: Score):
    log.debug("Scoring")
    user_community = await Community.objects.aget(pk=community_id)

    scorer = await user_community.aget_scorer()
    scores = await scorer.acompute_score([passport.pk])

    log.info("Scores for address '%s': %s", passport.address, scores)
    scoreData = scores[0]

    score.score = scoreData.score
    score.status = Score.Status.DONE
    score.last_score_timestamp = get_utc_time()
    score.evidence = scoreData.evidence[0].as_dict() if scoreData.evidence else None
    score.error = None


async def aprocess_deduplication(passport, community, passport_data):
    """
    Process deduplication based on the community rule
    """
    rule_map = {
        Rules.LIFO.value: alifo,
        Rules.FIFO.value: afifo,
    }

    method = rule_map.get(community.rule)

    log.debug(
        "Processing deduplication for address='%s' and method='%s'",
        passport.address,
        method,
    )

    if not method:
        raise Exception("Invalid rule")

    deduplicated_passport, affected_passports = await method(
        community, passport_data, passport.address
    )

    log.debug(
        "Processing deduplication found deduplicated_passport='%s' and affected_passports='%s'",
        deduplicated_passport,
        affected_passports,
    )

    # If the rule is FIFO, we need to re-score all affected passports
    if community.rule == Rules.FIFO.value:
        for passport in affected_passports:
            log.debug(
                "FIFO scoring selected, rescoring passport='%s'",
                passport,
            )

            affected_score, _ = await Score.objects.aupdate_or_create(
                passport=passport,
                defaults=dict(score=None, status=Score.Status.PROCESSING),
            )
            await acalculate_score(passport, passport.community_id, affected_score)
            await affected_score.asave()

    return deduplicated_passport


async def avalidate_and_save_stamps(
    passport: Passport, community: Community, passport_data
):
    log.debug("getting stamp data ")

    log.debug("processing deduplication")

    deduped_passport_data = await aprocess_deduplication(
        passport, community, passport_data
    )

    log.debug("validating stamps")
    did = get_did(passport.address)

    for stamp in deduped_passport_data["stamps"]:
        stamp_return_errors = await validate_credential(did, stamp["credential"])
        try:
            # TODO: use some library or https://docs.python.org/3/library/datetime.html#datetime.datetime.fromisoformat to
            # parse iso timestamps
            stamp_expiration_date = datetime.strptime(
                stamp["credential"]["expirationDate"], "%Y-%m-%dT%H:%M:%S.%fZ"
            )
        except ValueError:
            stamp_expiration_date = datetime.strptime(
                stamp["credential"]["expirationDate"], "%Y-%m-%dT%H:%M:%SZ"
            )

        is_issuer_verified = verify_issuer(stamp)
        # check that expiration date is not in the past
        stamp_is_expired = stamp_expiration_date < datetime.now()
        if (
            len(stamp_return_errors) == 0
            and not stamp_is_expired
            and is_issuer_verified
        ):
            await Stamp.objects.aupdate_or_create(
                hash=stamp["credential"]["credentialSubject"]["hash"],
                passport=passport,
                defaults={
                    "provider": stamp["provider"],
                    "credential": stamp["credential"],
                },
            )
        else:
            log.info(
                "Stamp not created. Stamp=%s\nReason: errors=%s stamp_is_expired=%s is_issuer_verified=%s",
                stamp,
                stamp_return_errors,
                stamp_is_expired,
                is_issuer_verified,
            )


async def ascore_passport(
    community: Community, passport: Passport, address: str, score: Score
):
    log.info(
        "score_passport request for community_id=%s, address='%s'",
        community.id,
        address,
    )

    try:
        # passport = load_passport_record(community_id, address)
        log.error("===> 1")
        await aremove_existing_stamps_from_db(passport)
        log.error("===> 2")
        passport_data = await aload_passport_data(address)
        log.error("===> 3")
        await avalidate_and_save_stamps(passport, community, passport_data)
        log.error("===> 4")
        await acalculate_score(passport, community.id, score)
        log.error("===> 5")

    except APIException as e:
        log.error(
            "APIException when handling passport submission. community_id=%s, address='%s'",
            community.id,
            address,
            exc_info=True,
        )
        if passport:
            # Create a score with error status
            score.score = None
            score.status = Score.Status.ERROR
            score.last_score_timestamp = None
            score.evidence = None
            score.error = e.detail
    except Exception as e:
        log.error(
            "Error when handling passport submission. community_id=%s, address='%s'",
            community.id,
            address,
            exc_info=True,
        )
        log.error("Error for passport=%s", passport)
        if passport:
            # Create a score with error status
            score.score = None
            score.status = Score.Status.ERROR
            score.last_score_timestamp = None
            score.evidence = None
            score.error = str(e)

            log.error("score.id=%s score.error=%s", score.id, score.error)
