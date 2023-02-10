import logging
from datetime import datetime

from account.deduplication.lifo import lifo
from account.models import Community
from asgiref.sync import async_to_sync
from celery import shared_task
from ninja_extra.exceptions import APIException
from reader.passport_reader import get_did, get_passport
from registry.exceptions import NoPassportException
from registry.models import Passport, Score, Stamp
from registry.utils import validate_credential, verify_issuer

log = logging.getLogger(__name__)


def get_utc_time():
    return datetime.utcnow()


@shared_task
def score_passport(community_id: int, address: str):
    log.info(
        "score_passport request for community_id=%s, address='%s'",
        community_id,
        address,
    )

    passport = None
    try:
        passport = load_passport_record(community_id, address)
        populate_passport_record(passport)
        remove_existing_stamps_from_db(passport)
        validate_and_save_stamps(passport)
        calculate_score(passport, community_id)

    except APIException as e:
        log.error(
            "APIException when handling passport submission. community_id=%s, address='%s'",
            community_id,
            address,
            exc_info=True,
        )
        if passport:
            # Create a score with error status
            Score.objects.update_or_create(
                passport_id=passport.pk,
                defaults=dict(
                    score=None,
                    status=Score.Status.ERROR,
                    last_score_timestamp=None,
                    evidence=None,
                    error=str(e),
                ),
            )
    except Exception as e:
        log.error(
            "Error when handling passport submission. community_id=%s, address='%s'",
            community_id,
            address,
            exc_info=True,
        )
        if passport:
            # Create a score with error status
            Score.objects.update_or_create(
                passport_id=passport.pk,
                defaults=dict(
                    score=None,
                    status=Score.Status.ERROR,
                    last_score_timestamp=None,
                    evidence=None,
                    error=str(e),
                ),
            )


def load_passport_record(community_id: int, address: str):
    # Create a DB record for the passport unless one already exists
    db_passport, _ = Passport.objects.update_or_create(
        address=address.lower(),
        community_id=community_id,
        defaults={
            "passport": None,
        },
    )

    return db_passport


def populate_passport_record(passport: Passport):
    passport_data = get_passport(passport.address)
    log.debug(
        "score_passport loaded for address='%s' passport=%s",
        passport.address,
        passport_data,
    )

    if not passport_data:
        raise NoPassportException()

    log.debug("deduplicating ...")

    # Check if stamp(s) with hash already exist and remove it/them from the incoming passport
    passport.passport = lifo(passport_data, passport.address)

    passport.save()

    return passport


def validate_and_save_stamps(passport: Passport):
    log.debug("validating stamps")

    did = get_did(passport.address)

    for stamp in passport.passport["stamps"]:
        stamp_return_errors = async_to_sync(validate_credential)(
            did, stamp["credential"]
        )
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
            Stamp.objects.update_or_create(
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


def remove_existing_stamps_from_db(passport: Passport):
    Stamp.objects.filter(passport=passport).delete()


def calculate_score(passport: Passport, community_id: int):
    log.debug("Scoring")
    user_community = Community.objects.get(pk=community_id)

    scorer = user_community.get_scorer()
    scores = scorer.compute_score([passport.pk])

    log.info("Scores for address '%s': %s", passport.address, scores)
    scoreData = scores[0]

    Score.objects.update_or_create(
        passport_id=passport.pk,
        defaults=dict(
            score=scoreData.score,
            status=Score.Status.DONE,
            last_score_timestamp=get_utc_time(),
            evidence=scoreData.evidence[0].as_dict() if scoreData.evidence else None,
            error=None,
        ),
    )
