import copy
from typing import Tuple

import api_logging as logging
from account.models import Community
from registry.models import Stamp

log = logging.getLogger(__name__)


# --> LIFO deduplication
def lifo(
    community: Community, lifo_passport: dict, address: str
) -> Tuple[dict, list | None]:
    deduped_passport = copy.deepcopy(lifo_passport)
    deduped_passport["stamps"] = []
    if "stamps" in lifo_passport:
        for stamp in lifo_passport["stamps"]:
            stamp_hash = stamp["credential"]["credentialSubject"]["hash"]

            # query db to see if hash already exists, if so remove stamp from passport
            if (
                not Stamp.objects.filter(hash=stamp_hash, passport__community=community)
                .exclude(passport__address=address)
                .aexists()
            ):
                deduped_passport["stamps"].append(copy.deepcopy(stamp))

    return (deduped_passport, None)


async def alifo(
    community: Community, lifo_passport: dict, address: str
) -> Tuple[dict, list | None]:
    deduped_passport = copy.deepcopy(lifo_passport)
    log.error("===? lifo_passport stamps: %s", lifo_passport["stamps"])
    deduped_passport["stamps"] = []
    if "stamps" in lifo_passport:
        for stamp in lifo_passport["stamps"]:
            stamp_hash = stamp["credential"]["credentialSubject"]["hash"]

            # query db to see if hash already exists, if so remove stamp from passport
            if (
                not await Stamp.objects.filter(
                    hash=stamp_hash, passport__community=community
                )
                .exclude(passport__address=address)
                .aexists()
            ):
                deduped_passport["stamps"].append(copy.deepcopy(stamp))

    return (deduped_passport, None)
