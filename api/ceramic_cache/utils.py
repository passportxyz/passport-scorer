import base64
import json
from hashlib import sha256
from pprint import pprint

import api_logging as logging
import base58
import dag_cbor
from multibase import decode
from multiformats import CID
from nacl.signing import VerifyKey

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


def verify_jws(data):
    """
    https://github.com/decentralized-identity/did-jwt/blob/master/src/JWT.ts
    """
    jws = {
        "signatures": data["signatures"],
        "payload": data["payload"],
        "cid": CID.decode(bytearray(data["cid"])),
    }
    pprint(jws)
    print("kid   " + "=" * 40)
    p = base64url_to_json(jws["signatures"][0]["protected"])
    pprint(p)
    kid = p["kid"]
    # signerDid = kid.split("#")[0]

    print("kid   " + "=" * 40)

    print("X" * 40)
    print("X" * 40)
    kid_key = kid.split("#")[1]
    # decoded_kid = decode("z6MkjS8jpTw3jS78gLDK5Z3BtGkKQ5fpPE2CGEn9ifgi1FPc")
    decoded_kid = decode(kid_key)
    print("decoded_kid: ", decoded_kid)
    print("decoded_kid: ", decoded_kid[2:])
    print("X" * 40)
    print("X" * 40)

    decoded_bytes = base58.b58decode(
        "5yshEDgcPtcfZqNcPz5M3BCKaWPxyLmqaDsDtPih62cE"
    )  # Key  --> this was working
    decoded_bytes = decoded_kid[2:]

    print("decoded_bytes: ", decoded_bytes)
    print("decoded_bytes: ", len(decoded_bytes))

    print(
        "signature: qpc4rcmVeK74GpkfYiiMRB1ikwG_vANek4OjGq3GbgpPUH5MxkReK3urvDF0aQlVRP2UqXt8ombJYQ4L87Z0Dg"
    )
    # signature = jws["signatures"][0]["signature"] + "=="
    signature = pad_b64decoded_string(jws["signatures"][0]["signature"])
    print("signature:", signature, len(signature))
    signature = base64.urlsafe_b64decode(signature)
    print("signature:", signature)

    # print("jws_string       : ", jws_string)
    # jwss = jws_string.split(".")
    # print("jwss             : ", jwss)
    # signing_input = jwss[0] + "." + jwss[1]
    signing_input = jws["signatures"][0]["protected"] + "." + jws["payload"]

    print("signature        : ", signature, len(signature))
    print("signing_input    : ", signing_input, len(signing_input))
    signing_input = signing_input.encode("utf-8")
    print("signing_input    : ", signing_input, len(signing_input))

    vk = VerifyKey(decoded_bytes)
    v = vk.verify(signing_input, signature)

    print("v   " + "=" * 40)
    print(v)
