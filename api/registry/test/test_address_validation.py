import pytest

from registry.api.v1 import is_valid_address

address = "0x71Ad3e3057Ca74967239C66ca6D3A9C2A43a58fC"


@pytest.mark.django_db
def test_good_checksum():
    assert is_valid_address(address) is True


@pytest.mark.django_db
def test_good_lowercase():
    assert is_valid_address(address.lower()) is True


@pytest.mark.django_db
def test_good_uppercase():
    assert is_valid_address(address.upper()) is True


@pytest.mark.django_db
def test_bad_checksum():
    assert is_valid_address(address.replace("A", "a")) is False


@pytest.mark.django_db
def test_bad_length():
    assert is_valid_address(address.lower() + "a") is False


@pytest.mark.django_db
def test_bad_length_checksummed():
    assert is_valid_address(address + "a") is False
