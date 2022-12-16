"""Create an API account feature tests."""

from pytest_bdd import given, scenario, then, when


@scenario("features/create_api_account.feature", "Successfully create an API account")
def test_successfully_create_an_api_account():
    """Successfully create an API account."""


@given("that I am a builder and I don't have an API ACCOUNT")
def _():
    """that I am a builder and I don't have an API ACCOUNT."""
    raise NotImplementedError


@when("I hit the Connect Wallet button")
def _():
    """I hit the Connect Wallet button."""
    raise NotImplementedError


@then("I Sign-in-with-Ethereum")
def _():
    """I Sign-in-with-Ethereum."""
    raise NotImplementedError


@then("I will have an account created")
def _():
    """I will have an account created."""
    raise NotImplementedError


@then("be taken to the dashboard")
def _():
    """be taken to the dashboard."""
    raise NotImplementedError
