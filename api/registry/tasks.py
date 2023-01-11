import logging
from datetime import datetime

from account.deduplication.lifo import lifo
from account.models import Community
from asgiref.sync import async_to_sync
from celery import shared_task
from reader.passport_reader import get_did, get_passport
from registry.models import Passport, Score, Stamp
from registry.utils import (
    get_signer,
    get_signing_message,
    validate_credential,
    verify_issuer,
)

from .exceptions import InvalidPassportCreationException, NoPassportException

log = logging.getLogger(__name__)


@shared_task
def score_passport(community_id: int, address: str):
    log.debug(
        "score_passport request for community_id=%s, address='%s'",
        community_id,
        address,
    )
    address_lower = address.lower()
    did = get_did(address)
    passport = get_passport(did)
    log.debug("score_passport loaded passport=%s", passport)

    try:
        print("")
        if not passport:
            raise NoPassportException()

        user_community = Community.objects.get(pk=community_id)

        log.debug("deduplicating ...")
        # Check if stamp(s) with hash already exist and remove it/them from the incoming passport
        passport_to_be_saved = lifo(passport, address_lower)

        # Save passport to Passport database (related to community by community_id)
        db_passport, _ = Passport.objects.update_or_create(
            address=address_lower,
            community_id=community_id,
            defaults={
                "passport": passport_to_be_saved,
            },
        )

        log.debug("validating stamps")
        for stamp in passport_to_be_saved["stamps"]:
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
                    passport=db_passport,
                    defaults={
                        "provider": stamp["provider"],
                        "credential": stamp["credential"],
                    },
                )
            else:
                log.debug(
                    "Stamp not created. Stamp=%s\nReason: errors=%s stamp_is_expired=%s is_issuer_verified=%s",
                    stamp,
                    stamp_return_errors,
                    stamp_is_expired,
                    is_issuer_verified,
                )

        log.debug("Scoring")
        scorer = user_community.get_scorer()
        scores = scorer.compute_score([db_passport.id])

        log.debug("Scores: %s", scores)
        scoreData = scores[0]

        score, _ = Score.objects.update_or_create(
            passport_id=db_passport.id, defaults=dict(score=scoreData.score)
        )
    except Exception as e:
        log.error(
            "Error when handling passport submission. community_id=%s, address='%s'",
            community_id,
            address,
            exc_info=True,
        )
        raise InvalidPassportCreationException() from e
