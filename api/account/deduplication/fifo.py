import copy
import logging

from account.models import Community
from registry.models import Passport, Score, Stamp
from registry.tasks import score_passport

log = logging.getLogger(__name__)


def rescore_passport(community: Community, address: str):
    passport = Passport.objects.get(community=community, address=address)
    Score.objects.update_or_create(
        passport=passport,
        defaults=dict(score=None, status=Score.Status.PROCESSING),
    )
    score_passport.delay(community.pk, address)


# --> FIFO deduplication
def fifo(community: Community, fifo_passport: dict, address: str):
    deduped_passport = copy.deepcopy(fifo_passport)
    deduped_passport["stamps"] = []
    if "stamps" in fifo_passport:
        for stamp in fifo_passport["stamps"]:
            stamp_hash = stamp["credential"]["credentialSubject"]["hash"]

            existing_stamps = Stamp.objects.filter(
                hash=stamp_hash, passport__community=community
            ).exclude(passport__address=address)

            for existing_stamp in existing_stamps.iterator():
                passport = existing_stamp.passport
                existing_stamp.delete()

                rescore_passport(community, passport.address)

    return deduped_passport
