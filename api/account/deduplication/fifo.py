import copy
import logging
from typing import Tuple

from account.models import Community
from registry.models import Passport, Score, Stamp

log = logging.getLogger(__name__)


def filter_duplicate_stamps(passport, existing_stamp):
    desired_stamps = []
    for stamp in passport["stamps"]:
        if stamp["credential"]["credentialSubject"]["hash"] != existing_stamp.hash:
            desired_stamps.append(stamp)

    passport["stamps"] = desired_stamps
    return passport


# --> FIFO deduplication
def fifo(community: Community, fifo_passport: dict, address: str) -> Tuple[dict, list]:
    deduped_passport = copy.deepcopy(fifo_passport)
    affected_passports = []
    if "stamps" in fifo_passport:
        for stamp in fifo_passport["stamps"]:
            stamp_hash = stamp["credential"]["credentialSubject"]["hash"]

            existing_stamps = Stamp.objects.filter(
                hash=stamp_hash, passport__community=community
            ).exclude(passport__address=address)

            for existing_stamp in existing_stamps.iterator():
                passport = existing_stamp.passport

                existing_stamp.delete()
                Score.objects.update_or_create(
                    passport=passport,
                    defaults=dict(score=None, status=Score.Status.PROCESSING),
                )

                passport.passport = filter_duplicate_stamps(
                    passport.passport, existing_stamp
                )

                passport.save()

                affected_passports.append(passport)

    return (deduped_passport, affected_passports)
