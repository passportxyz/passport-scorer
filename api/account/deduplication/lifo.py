import copy
import logging

from registry.models import Stamp

log = logging.getLogger(__name__)

# --> LIFO deduplication
def lifo(lifo_passport: dict) -> dict:
    deduped_passport = copy.deepcopy(lifo_passport)
    for stamp in deduped_passport["stamps"]:
        stamp_hash = stamp["credential"]["credentialSubject"]["hash"]

        # query db to see if hash already exists, if so remove stamp from passport
        if Stamp.objects.filter(hash=stamp_hash).exists():
            deduped_passport["stamps"].remove(stamp)

    return deduped_passport
