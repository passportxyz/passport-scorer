from v2.schema import V2StampScoreResponse, get_fail_reason


def stamp(dedup):
    return {"score": "0.00000", "dedup": dedup, "expiration_date": None}


def test_passing_wallet_has_no_fail_reason():
    assert get_fail_reason(True, None, {"Google": stamp(False)}) is None


def test_scoring_error_has_no_fail_reason():
    assert get_fail_reason(False, "Something went wrong", {}) is None


def test_unknown_stamps_have_no_fail_reason():
    # A score still processing, or an old history event without stamps
    assert get_fail_reason(False, None, None) is None


def test_no_stamps():
    assert get_fail_reason(False, None, {}) == "no_valid_stamps"


def test_stamp_claimed_by_another_wallet():
    stamps = {"Google": stamp(False), "Discord": stamp(True)}
    assert get_fail_reason(False, None, stamps) == "stamps_claimed_elsewhere"


def test_stamp_claimed_by_another_wallet_as_schema():
    stamps = {
        "Discord": V2StampScoreResponse(
            score="0.00000", dedup=True, expiration_date=None
        )
    }
    assert get_fail_reason(False, None, stamps) == "stamps_claimed_elsewhere"


def test_below_threshold():
    assert get_fail_reason(False, None, {"Google": stamp(False)}) == "below_threshold"
