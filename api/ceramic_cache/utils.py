import base64
from hashlib import sha256

import api_logging as logging
import dag_cbor
from multiformats import CID

log = logging.getLogger(__name__)


def validate_dag_jws_payload(payload: dict, payload_cid_str: str) -> bool:
    """
    payload_cid_str is a base65url encoded cid of the dagCBor encoded payload
    We compute the expected version of the CID, and compare it to the one provided in the payload.

    See how this is computed in the createDagJWS function of
    js-did lib here:: https://github.com/ceramicnetwork/js-did/blob/3fa2c43b17c2e55f242a2d022e687d22862a7060/packages/dids/src/did.ts#L294-L323
    """
    # Dag-cbor encode the payload
    encoded_payload = dag_cbor.encode(payload)

    # Compute the hash
    hash = sha256()
    hash.update(encoded_payload)

    digest = hash.digest()

    # Create the expected CID
    expected_cid = CID("base32", 1, "dag-cbor", ("sha2-256", digest))

    # Decode the received CID (it will be received a base64url encoded string)
    payload_cid_bytes = base64.urlsafe_b64decode(payload_cid_str)
    payload_cid = CID.decode(payload_cid_bytes)

    # Verify
    return payload_cid == expected_cid
