from ceramic_cache.utils import validate_dag_jws_payload


def test_validate_dag_jws_payload():
    payload = "AXESIJ-t3oi3FWOnXzz1JomHf4BeT-DVOaW5-RtZGPf_miHs"
    nonce = "super-secure-nonce"

    assert validate_dag_jws_payload({"nonce": nonce}, payload)
    assert not validate_dag_jws_payload({"nonce": nonce + "BAD"}, payload)
