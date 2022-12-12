"""Deduplication rules feature tests."""

from pytest_bdd import (
    given,
    scenario,
    then,
    when,
)


@scenario(
    "features/deduplication.feature",
    "As a developer, I want to rely on LIFO as a default stamp deduplication rule",
)
def test_as_a_developer_i_want_to_rely_on_lifo_as_a_default_stamp_deduplication_rule():
    """As a developer, I want to rely on LIFO as a default stamp deduplication rule."""


@given(
    "that a Passport holder submits a stamp with a hash that a different Passport holder previously submitted to the community"
)
def _():
    """that a Passport holder submits a stamp with a hash that a different Passport holder previously submitted to the community."""
    raise NotImplementedError


@when(
    "we score the associated Passports, i.e., the Passports holding the stamps with identical hashes"
)
def _():
    """we score the associated Passports, i.e., the Passports holding the stamps with identical hashes."""
    raise NotImplementedError


@then("score this Passport as if the stamp would be missing")
def _():
    """score this Passport as if the stamp would be missing."""
    raise NotImplementedError


@then(
    "we don't recognize the version of the stamp that has been more recently submitted"
)
def _():
    """we don't recognize the version of the stamp that has been more recently submitted."""
    raise NotImplementedError
