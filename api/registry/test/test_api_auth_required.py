# content of conftest.py
import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


@pytest.fixture(
    params=[
        ("get", "/registry/signing_message"),
        ("post", "/registry/submit-passport"),
        ("get", "/registry/score/3/0x0"),
    ]
)
def api_path_that_requires_auth(request):
    return request.param


def test_authentication_is_required(api_path_that_requires_auth):
    """
    Test that API key is required for exposed APIs"""
    method, path = api_path_that_requires_auth
    client = Client()

    method_fn = client.get
    if method == "post":
        method_fn = client.post

    response = method_fn(
        path,
        HTTP_AUTHORIZATION="Token " + "some bas API_KEY",
    )
    assert response.status_code == 401
