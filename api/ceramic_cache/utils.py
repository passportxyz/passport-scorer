import base64
import json
from datetime import datetime, timezone
from hashlib import sha256

import dag_cbor
import uvarint
from ecdsa import NIST256p, VerifyingKey
from jose import jwk, jws
from multiformats import CID
from multiformats.multibase import decode
from nacl.signing import VerifyKey

import api_logging as logging

log = logging.getLogger(__name__)


def get_utc_time():
    return datetime.now(timezone.utc)


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


def pad_b64decoded_string(base64url_string):
    return base64url_string + "=" * (4 - len(base64url_string) % 4)


def pad_and_urlsafe_b64decode(base64url_string):
    return base64.urlsafe_b64decode(pad_b64decoded_string(base64url_string))


def base64url_to_json(base64url_string):
    # Decode the Base64 URL-encoded string
    decoded_bytes = pad_and_urlsafe_b64decode(base64url_string)

    # Convert the decoded bytes to a JSON object
    json_data = json.loads(decoded_bytes.decode("utf-8"))

    return json_data


def verify_jws_old(data):
    """
    https://github.com/decentralized-identity/did-jwt/blob/master/src/JWT.ts

    This is a simplified implementation for validating the JWS signature in the payload.
    It will only check for the signature part, and skip validating any claims (like signature expiration) om the payload
    """
    p = base64url_to_json(data["signatures"][0]["protected"])
    kid = p["kid"]

    kid_key = kid.split("#")[1]
    decoded_kid = decode(kid_key)

    decoded_bytes = decoded_kid[2:]

    signature = base64.urlsafe_b64decode(
        pad_b64decoded_string(data["signatures"][0]["signature"])
    )

    signing_input = (data["signatures"][0]["protected"] + "." + data["payload"]).encode(
        "utf-8"
    )

    vk = VerifyKey(decoded_bytes)
    vk.verify(signing_input, signature)


def verify_jws_new(data):
    """
    https://github.com/decentralized-identity/did-jwt/blob/master/src/JWT.ts

    This is a simplified implementation for validating the JWS signature in the payload.
    It will only check for the signature part, and skip validating any claims (like signature expiration) om the payload
    """
    p = base64url_to_json(data["signatures"][0]["protected"])
    kid = p["kid"]

    did_key = kid.split("#")[1]

    decoded_key = decode(did_key)
    code = uvarint.decode(decoded_key)

    compressed_key = decoded_key[code.bytes_read :]

    # Decode the compressed public key
    public_key = VerifyingKey.from_string(compressed_key, curve=NIST256p)

    x_coordinate = public_key.pubkey.point.x()
    y_coordinate = public_key.pubkey.point.y()

    # Convert x and y coordinates to base64url encoding
    x_base64url = (
        base64.urlsafe_b64encode(x_coordinate.to_bytes(32, byteorder="big"))
        .decode("utf-8")
        .rstrip("=")
    )
    y_base64url = (
        base64.urlsafe_b64encode(y_coordinate.to_bytes(32, byteorder="big"))
        .decode("utf-8")
        .rstrip("=")
    )

    # Create the JWK
    jwk1 = {
        "alg": "ES256",
        "kty": "EC",
        "crv": "P-256",  # Adjust the curve as per your key type
        "x": x_base64url,
        "y": y_base64url,
    }

    jwkObj = jwk.construct(jwk1)

    signature = data["signatures"][0]["signature"]
    signing_input = (
        data["signatures"][0]["protected"] + "." + data["payload"] + "." + signature
    )

    jws.verify(signing_input, jwkObj, algorithms=["ES256"])


def verify_jws(data):
    try:
        verify_jws_old(data)
    except Exception:
        verify_jws_new(data)
