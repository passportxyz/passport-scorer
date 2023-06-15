import api_logging as logging
from account.models import AccountAPIKeyAnalytics
from asgiref.sync import async_to_sync
from celery import shared_task
from registry.models import Passport, Score, Stamp

from .atasks import ascore_passport

log = logging.getLogger(__name__)


@shared_task
def save_api_key_analytics(api_key_id, path):
    try:
        AccountAPIKeyAnalytics.objects.create(
            api_key_id=api_key_id,
            path=path,
        )
    except Exception as e:
        pass


@shared_task
def score_passport_passport(community_id: int, address: str):
    score_passport(community_id, address)


@shared_task
def score_registry_passport(community_id: int, address: str):
    score_passport(community_id, address)


def score_passport(community_id: int, address: str):
    passport = load_passport_record(community_id, address)

    if not passport:
        log.info(
            "Passport no passport found for address='%s', community_id='%s' that has requires_calculation=True or None",
            address,
            community_id,
        )
        return

    score, _ = Score.objects.get_or_create(
        passport=passport,
        defaults=dict(
            score=None,
            status=None,
            last_score_timestamp=None,
            evidence=None,
            error=None,
        ),
    )
    async_to_sync(ascore_passport)(passport.community, passport, address, score)
    score.save()
    return


def load_passport_record(community_id: int, address: str) -> Passport | None:
    # A Passport instance should exist, and have the requires_calculation flag set to True if it requires calculation.
    # We check for this by running an update and checking for the number of updated rows
    # This update should also avoid race conditions as stated in the documentation: https://docs.djangoproject.com/en/4.2/ref/models/querysets/#update
    # We query for all passports that have requires_calculation not set to False
    # because we want to calculate the score for any passport that has requires_calculation set to True or None
    #
    # Note: this will also pre-sellect the community of the passport
    num_passports_updated = (
        Passport.objects.filter(address=address.lower(), community_id=community_id)
        .exclude(requires_calculation=False)
        .update(requires_calculation=False)
    )

    # If the num_passports_updated == 1, this means we are in the lucky task that has managed to pick this passport up for processing
    # Other tasks which are potentially racing for the same calculation should get num_passports_updated == 0
    if num_passports_updated == 1:
        db_passport = Passport.objects.select_related("community").get(
            address=address.lower(),
            community_id=community_id,
        )
        return db_passport
    else:
        # Just in case the Passport does not exist, we create it
        if not Passport.objects.filter(
            address=address.lower(), community_id=community_id
        ).exists():
            db_passport, _ = Passport.objects.select_related(
                "community"
            ).update_or_create(address=address.lower(), community_id=community_id)
            return db_passport
    return None
