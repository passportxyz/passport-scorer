import copy
import logging

from registry.models import Stamp

log = logging.getLogger(__name__)

# --> LIFO deduplication
def lifo(lifo_passport: dict, address: str) -> dict:
    deduped_passport = copy.deepcopy(lifo_passport)
    deduped_passport["stamps"] = []
    if "stamps" in lifo_passport:
        for stamp in lifo_passport["stamps"]:
            stamp_hash = stamp["credential"]["credentialSubject"]["hash"]

            # query db to see if hash already exists, if so remove stamp from passport
            if (
                not Stamp.objects.filter(hash=stamp_hash)
                .exclude(passport__address=address)
                .exists()
            ):
                deduped_passport["stamps"].append(copy.deepcopy(stamp))

    return deduped_passport
