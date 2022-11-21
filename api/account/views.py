from ninja import NinjaAPI
import random
import hashlib
import string
import logging
from eth_account.messages import defunct_hash_message
from web3.auto import w3
from ninja_jwt.controller import NinjaJWTDefaultController
from ninja_extra import NinjaExtraAPI
from ninja import Schema

log = logging.getLogger(__name__)

api = NinjaExtraAPI()
api.register_controllers(NinjaJWTDefaultController)


class ChallengeSubmission(Schema):
    address: str
    signature: str


CHALLENGE_STATEMENT = "I authorize the passport scorer.\n\nnonce:"


@api.get("/challenge")
def challenge(request, address: str):
    challenge = {
        "statement": CHALLENGE_STATEMENT,
        "nonce": hashlib.sha256(
            str(
                address
                # + "".join(random.choice(string.ascii_letters) for i in range(32))  TODO: need to track the 'random' part
            ).encode("utf")
        ).hexdigest(),
    }
    return challenge


@api.post("/submit_signed_challenge")
def submit_siigned_challenge(request, payload: ChallengeSubmission):
    log.debug("payload:  %s", payload)

    address = payload.address
    signature = payload.signature

    challenge_string = CHALLENGE_STATEMENT
    # check for valid sig
    message_hash = defunct_hash_message(text=challenge_string)
    signer = w3.eth.account.recoverHash(message_hash, signature=signature)

    log.debug("signer:  %s", signer)
    sig_is_valid = address.lower() == signer.lower()

    # TODO: return JWT token to the user
    return {"ok": sig_is_valid}
