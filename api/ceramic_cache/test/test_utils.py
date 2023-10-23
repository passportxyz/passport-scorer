import copy

import pytest
from ceramic_cache.test.test_utils_data import (
    verify_jws_data_good,
    verify_jws_data_good_2,
)
from ceramic_cache.utils import validate_dag_jws_payload, verify_jws
from nacl.exceptions import BadSignatureError


def test_validate_dag_jws_payload():
    payload = "AXESIJ-t3oi3FWOnXzz1JomHf4BeT-DVOaW5-RtZGPf_miHs"
    nonce = "super-secure-nonce"

    assert validate_dag_jws_payload({"nonce": nonce}, payload)
    assert not validate_dag_jws_payload({"nonce": nonce + "BAD"}, payload)


def test_verify_jws():
    """
    Test that JWS verification works correctly for valid payloads
    """
    verify_jws(verify_jws_data_good)
    verify_jws(verify_jws_data_good_2)


def test_verify_jws_empty_payload():
    """
    Verify that validation fails if payload is empty
    """
    with pytest.raises(Exception):
        verify_jws({})


def test_verify_jws_empty_payload():
    """
    Verify that validation fails if signature, protected or payload are mismatched
    """
    with pytest.raises(BadSignatureError):
        data = copy.deepcopy(verify_jws_data_good)
        data["signatures"][0]["signature"] = verify_jws_data_good_2["signatures"][0][
            "signature"
        ]
        verify_jws(data)

    with pytest.raises(BadSignatureError):
        data = copy.deepcopy(verify_jws_data_good)
        data["signatures"][0]["protected"] = verify_jws_data_good_2["signatures"][0][
            "protected"
        ]
        verify_jws(data)

    with pytest.raises(BadSignatureError):
        data = copy.deepcopy(verify_jws_data_good)
        data["payload"] = verify_jws_data_good_2["payload"]
        verify_jws(data)
