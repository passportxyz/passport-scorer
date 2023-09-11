import json
from datetime import datetime

import pytest
from ceramic_cache.models import CeramicCache
from django.test import Client

pytestmark = pytest.mark.django_db

client = Client()


def get_v2_stamp_for_v1(stamp_v1: CeramicCache) -> CeramicCache:
    return CeramicCache.objects.create(
        type=CeramicCache.StampType.V2,
        address=stamp_v1.address,
        provider=stamp_v1.provider,
        stamp=stamp_v1.stamp,
    )


class TestConvertStamps:
    base_url = "/ceramic-cache/v2"
    stamp_version = CeramicCache.StampType.V1

    def test_succesfully_get_v2_stamp(
        self, sample_provider, sample_address, verifiable_credential, mocker
    ):
        # Create V1 stamps
        CeramicCache.objects.create(
            type=CeramicCache.StampType.V1,
            address=sample_address,
            provider=sample_provider,
            stamp=verifiable_credential,
        )

        with mocker.patch(
            "ceramic_cache.api.v2.migrate_stamp_to_v2",
            return_value=CeramicCache.objects.create(
                type=CeramicCache.StampType.V2,
                address=sample_address,
                provider=sample_provider,
                stamp=verifiable_credential,
            ),
        ):
            response = client.get(
                f"{self.base_url}/stamp?address={sample_address}",
            )

            first_stamp = response.json()["stamps"][0]

            assert response.status_code is 200
            assert first_stamp["address"] == sample_address.lower()
            assert first_stamp["provider"] == sample_provider
            assert first_stamp["stamp"] == verifiable_credential

    def test_bulk_delete_and_get_back_v2_state(
        self, sample_providers, sample_address, sample_stamps, sample_token, mocker
    ):
        for provider, stamp in zip(sample_providers, sample_stamps):
            CeramicCache.objects.create(
                type=CeramicCache.StampType.V1,
                address=sample_address,
                provider=provider,
                stamp=stamp,
            )
            CeramicCache.objects.create(
                type=CeramicCache.StampType.V2,
                address=sample_address,
                provider=provider,
                stamp=stamp,
            )

        middle = int(len(sample_providers) / 2)
        providers_to_delete = sample_providers[:middle]
        providers_to_keep = sample_providers[middle:]

        assert len(providers_to_delete) > 0
        assert len(providers_to_keep) > 0

        bulk_payload = [
            {"address": sample_address, "provider": p} for p in providers_to_delete
        ]

        with mocker.patch(
            "ceramic_cache.api.v2.migrate_stamp_to_v2", side_effect=get_v2_stamp_for_v1
        ):
            cache_stamp_response = client.delete(
                f"{self.base_url}/stamps/bulk",
                json.dumps(bulk_payload),
                content_type="application/json",
                **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
            )

            assert cache_stamp_response.status_code == 200
            data = cache_stamp_response.json()
            assert data["success"] == True
            stamps = data["stamps"]
            assert [s["provider"] for s in stamps] == providers_to_keep

    def test_bulk_patch_and_get_back_v2_state(
        self, sample_providers, sample_address, sample_stamps, sample_token, mocker
    ):
        middle = int(len(sample_providers) / 2)
        providers_that_exist_in_db = sample_providers[:middle]
        providers_to_create = sample_providers[middle:]

        assert len(providers_that_exist_in_db) > 0
        assert len(providers_to_create) > 0

        for provider, stamp in zip(providers_that_exist_in_db, sample_stamps):
            # Create only v1 stamps, we expect these to be delete in the patch
            CeramicCache.objects.create(
                type=CeramicCache.StampType.V1,
                address=sample_address,
                provider=provider,
                stamp=stamp,
            )

        bulk_payload = []
        for provider, stamp in zip(providers_to_create, sample_stamps[middle:]):
            bulk_payload.append(
                {
                    "provider": provider,
                    "stamp": stamp,
                }
            )
        for provider in providers_that_exist_in_db:
            bulk_payload.append(
                {
                    "provider": provider,
                    # don't speciy stamp, we want to delete these ...
                }
            )

        from pprint import pprint

        pprint(bulk_payload)
        with mocker.patch(
            "ceramic_cache.api.v2.migrate_stamp_to_v2", side_effect=get_v2_stamp_for_v1
        ):
            cache_stamp_response = client.patch(
                f"{self.base_url}/stamps/bulk",
                json.dumps(bulk_payload),
                content_type="application/json",
                **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
            )

            assert cache_stamp_response.status_code == 200
            data = cache_stamp_response.json()
            assert data["success"] == True
            stamps = data["stamps"]
            assert sorted([s["provider"] for s in stamps]) == sorted(
                providers_to_create
            )
