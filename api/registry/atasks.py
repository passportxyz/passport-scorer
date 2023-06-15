from datetime import datetime
from typing import Dict, List

import api_logging as logging
from account.deduplication.fifo import afifo
from account.deduplication.lifo import alifo

# --- Deduplication Modules
from account.models import Community, Rules
from ninja_extra.exceptions import APIException
from reader.passport_reader import aget_passport, get_did
from registry.exceptions import NoPassportException
from registry.models import Passport, Score, Stamp
from registry.utils import get_utc_time, validate_credential, verify_issuer

log = logging.getLogger(__name__)


def asave_api_key_analytics(api_key_id, path):
    try:
        AccountAPIKeyAnalytics.objects.acreate(
            api_key_id=api_key_id,
            path=path,
        )
    except Exception as e:
        pass


async def aremove_existing_stamps_from_db(passport: Passport):
    await Stamp.objects.filter(passport=passport).adelete()


async def aload_passport_data(address: str) -> Dict:
    # Get the passport data from the blockchain or ceramic cache
    passport_data = await aget_passport(address)
    if not passport_data:
        raise NoPassportException()

    return passport_data


async def acalculate_score(passport: Passport, community_id: int, score: Score):
    log.debug("Scoring")
    user_community = await Community.objects.aget(pk=community_id)

    scorer = await user_community.aget_scorer()
    scores = await scorer.acompute_score([passport.id])

    log.info("Scores for address '%s': %s", passport.address, scores)
    scoreData = scores[0]

    score.score = scoreData.score
    score.status = Score.Status.DONE
    score.last_score_timestamp = get_utc_time()
    score.evidence = scoreData.evidence[0].as_dict() if scoreData.evidence else None
    score.error = None
    log.info("Calculated score: %s", score)


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
    log.debug("processing deduplication")

    deduped_passport_data = await aprocess_deduplication(
        passport, community, passport_data
    )

    did = get_did(passport.address)

    log.debug(
        "validating stamps deduped_passport_data: %s", deduped_passport_data["stamps"]
    )
    for stamp in deduped_passport_data["stamps"]:
        log.debug(
            "validating credential did='%s' credential='%s'", did, stamp["credential"]
        )
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
        await aremove_existing_stamps_from_db(passport)
        passport_data = await aload_passport_data(address)
        await avalidate_and_save_stamps(passport, community, passport_data)
        await acalculate_score(passport, community.id, score)

    except APIException as e:
        log.error(
            "APIException when handling passport submission. passport='%s' community='%s'",
            passport,
            community,
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
            "Error when handling passport submission. passport='%s' community='%s'",
            passport,
            community,
            exc_info=True,
        )
        if passport:
            # Create a score with error status
            score.score = None
            score.status = Score.Status.ERROR
            score.last_score_timestamp = None
            score.evidence = None
            score.error = str(e)
