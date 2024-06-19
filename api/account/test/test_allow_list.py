from django.conf import settings
import pytest
from django.test import Client
from account.models import AddressListMember, AddressList

pytestmark = pytest.mark.django_db

user_address = "0x14dC79964da2C08b23698B3D3cc7Ca32193d9955"


class TestAllowList:
    def test_successful_get_allow_list(self):
        list_name = "test"
        address_list = AddressList.objects.create(
            name=list_name,
        )
        AddressListMember.objects.create(
            list=address_list,
            address=user_address,
        )

        client = Client()
        response = client.get(
            f"/account/allow-list/{list_name}/{user_address}",
            HTTP_AUTHORIZATION=settings.CGRANTS_API_TOKEN,
        )
        assert response.status_code == 200
        assert response.json()["is_member"]

    def test_unsuccessful_get_allow_list(self):
        list_name = "test"
        client = Client()
        response = client.get(
            f"/account/allow-list/{list_name}/0x123",
            HTTP_AUTHORIZATION=settings.CGRANTS_API_TOKEN,
        )
        assert response.status_code == 200
        assert not response.json()["is_member"]
