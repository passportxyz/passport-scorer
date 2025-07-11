import json
from copy import deepcopy
from datetime import datetime
from typing import Any
from unittest.mock import patch

import pytest

from ceramic_cache.api.v1 import get_address_from_did
from ceramic_cache.models import CeramicCache

pytestmark = pytest.mark.django_db


def ascore_passport_patch(_community, _passport, _address, score):
    score.status = "DONE"


class TestBulkStampUpdates:
    base_url = "/ceramic-cache"
    stamp_version = CeramicCache.StampType.V1

    @patch(
        "registry.api.v1.ascore_passport",
        side_effect=ascore_passport_patch,
    )
    def test_bulk_create(
        self,
        sample_providers,
        sample_address,
        sample_stamps,
        sample_token,
        ui_scorer,
        client,
    ):
        bulk_payload = []
        for i in range(0, len(sample_providers)):
            bulk_payload.append(
                {
                    "provider": sample_providers[i],
                    "stamp": sample_stamps[i],
                }
            )

        cache_stamp_response = client.post(
            f"{self.base_url}/stamps/bulk",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 201
        cache_stamp_response_data = cache_stamp_response.json()
        stamps = cache_stamp_response_data["stamps"]
        sorted_stamps = sorted(stamps, key=lambda x: x["stamp"]["issuanceDate"])
        score = cache_stamp_response_data["score"]
        assert len(stamps) == len(sample_providers)

        sorted_sample_stamps = sorted(sample_stamps, key=lambda x: x["issuanceDate"])

        # Verify the returned score
        assert "last_score_timestamp" in score
        del score["last_score_timestamp"]
        assert score == {
            "address": sample_address.lower(),
            "error": None,
            "expiration_timestamp": None,
            "score": "0.00000",
            "stamps": {},
            "threshold": "20.00000",
            "passing_score": False,
            "points_data": None,
            "possible_points_data": None,
        }

        # Verify the returned stamps
        for i in range(0, len(sorted_stamps)):
            provider = sorted_sample_stamps[i]["credentialSubject"]["provider"]
            stamp = sorted_sample_stamps[i]
            assert sorted_stamps[i] == {
                # For these fields, values are set by the server
                "id": sorted_stamps[i]["id"],
                # For the attributes below we know the expected values
                "address": sample_address.lower(),
                "provider": provider,
                "stamp": stamp,
            }

        # Test that stamps are stored correctly
        cc = sorted(
            CeramicCache.objects.all().values(),
            key=lambda x: x["stamp"]["issuanceDate"],
        )
        for idx, c in enumerate(cc):
            provider = sorted_sample_stamps[idx]["credentialSubject"]["provider"]
            stamp = sorted_sample_stamps[idx]
            assert c == {
                # Just copy the automatically generated values over
                "id": c["id"],
                "created_at": c["created_at"],
                "updated_at": c["updated_at"],
                # Here are the values we control
                "address": sample_address.lower(),
                "compose_db_save_status": "pending",
                "compose_db_stream_id": "",
                "deleted_at": None,
                "expiration_date": datetime.fromisoformat(stamp["expirationDate"]),
                "issuance_date": datetime.fromisoformat(stamp["issuanceDate"]),
                "proof_value": stamp["proof"]["proofValue"],
                "provider": provider,
                "scorer_id": ui_scorer,
                "stamp": stamp,
                "source_app": CeramicCache.SourceApp.PASSPORT.value,
                "type": 1,
            }

    @patch(
        "registry.api.v1.ascore_passport",
        side_effect=ascore_passport_patch,
    )
    def test_bulk_update(
        self,
        _avalidate_credentials,
        sample_providers,
        sample_address,
        sample_stamps,
        sample_token,
        scorer_account,
        ui_scorer,
        client,
    ):
        bulk_payload = []
        for i in range(0, len(sample_providers)):
            bulk_payload.append(
                {
                    "provider": sample_providers[i],
                    "stamp": sample_stamps[i],
                }
            )

        cache_stamp_response = client.post(
            f"{self.base_url}/stamps/bulk",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 201
        assert len(cache_stamp_response.json()["stamps"]) == len(sample_providers)

        bulk_payload = []
        sorted_sample_stamps = sorted(sample_stamps, key=lambda x: x["issuanceDate"])
        sorted_sample_stamps_updates = []

        for i, stamp in enumerate(sorted_sample_stamps):
            new_stamp = deepcopy(stamp)
            new_stamp["proof"]["proofValue"] = f"updated {i}"
            sorted_sample_stamps_updates.append(new_stamp)
            bulk_payload.append({"provider": sample_providers[i], "stamp": new_stamp})

        cache_stamp_response = client.post(
            f"{self.base_url}/stamps/bulk",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 201

        response = cache_stamp_response.json()
        stamps = response["stamps"]
        score = response["score"]

        assert len(stamps) == len(sample_providers)

        assert "last_score_timestamp" in score
        del score["last_score_timestamp"]
        assert score == {
            "address": sample_address.lower(),
            "error": None,
            "expiration_timestamp": None,
            "stamps": {},
            "threshold": "20.00000",
            "score": "0.00000",
            "passing_score": False,
            "points_data": None,
            "possible_points_data": None,
        }

        sorted_stamps_returned = sorted(
            stamps, key=lambda x: x["stamp"]["issuanceDate"]
        )

        for i in range(0, len(sorted_sample_stamps_updates)):
            provider = sorted_sample_stamps_updates[i]["credentialSubject"]["provider"]
            stamp = sorted_sample_stamps_updates[i]
            assert sorted_stamps_returned[i] == {
                # For these fields, values are set by the server
                "id": sorted_stamps_returned[i]["id"],
                # For the attributes below we know the expected values
                "address": sample_address.lower(),
                "provider": provider,
                "stamp": stamp,
            }

        # Test that stamps are stored correctly
        cc = sorted(
            list(CeramicCache.objects.filter(deleted_at__isnull=True).values()),
            key=lambda x: x["stamp"]["issuanceDate"],
        )

        for i, c in enumerate(cc):
            provider = sorted_sample_stamps_updates[i]["credentialSubject"]["provider"]
            stamp = sorted_sample_stamps_updates[i]
            assert c == {
                # Just copy the automatically generated values over
                "id": c["id"],
                "created_at": c["created_at"],
                "updated_at": c["updated_at"],
                # Here are the values we control
                "address": sample_address.lower(),
                "compose_db_save_status": "pending",
                "compose_db_stream_id": "",
                "deleted_at": None,
                "expiration_date": datetime.fromisoformat(stamp["expirationDate"]),
                "issuance_date": datetime.fromisoformat(stamp["issuanceDate"]),
                "proof_value": stamp["proof"]["proofValue"],
                "provider": provider,
                "source_scorer_id": ui_scorer,
                "stamp": stamp,
                "source_app": CeramicCache.SourceApp.PASSPORT.value,
                "type": 1,
            }

    @patch(
        "registry.api.v1.ascore_passport",
        side_effect=ascore_passport_patch,
    )
    def test_bulk_patch_partial_update(
        self,
        _avalidate_credentials,
        sample_providers,
        sample_address,
        sample_stamps,
        sample_token,
        scorer_account,
        ui_scorer,
        client,
    ):
        """
        Test updating only a part of the stamps
        """
        assert CeramicCache.objects.all().count() == 0

        bulk_payload = []
        for i in range(0, len(sample_providers)):
            bulk_payload.append(
                {
                    "provider": sample_providers[i],
                    "stamp": sample_stamps[i],
                }
            )

        cache_stamp_response = client.post(
            f"{self.base_url}/stamps/bulk",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 201
        assert len(cache_stamp_response.json()["stamps"]) == len(sample_providers)

        bulk_payload = []
        sorted_sample_stamps = sorted(sample_stamps, key=lambda x: x["issuanceDate"])
        # This will hold the state we expect when getting the stamp list back (or reading from DB)
        sorted_sample_stamps_updated = []

        for i, stamp in enumerate(sorted_sample_stamps):
            if i < len(sample_providers) / 2:
                new_stamp = deepcopy(stamp)
                new_stamp["proof"]["proofValue"] = f"updated {i}"
                sorted_sample_stamps_updated.append(new_stamp)
                bulk_payload.append(
                    {"provider": sample_providers[i], "stamp": new_stamp}
                )
            else:
                sorted_sample_stamps_updated.append(deepcopy(stamp))

        cache_stamp_response = client.post(
            f"{self.base_url}/stamps/bulk",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 201

        response = cache_stamp_response.json()
        stamps = response["stamps"]
        score = response["score"]

        assert len(stamps) == len(sample_providers)

        assert "last_score_timestamp" in score
        del score["last_score_timestamp"]
        assert score == {
            "address": sample_address.lower(),
            "error": None,
            "expiration_timestamp": None,
            "score": "0.00000",
            "stamps": {},
            "threshold": "20.00000",
            "passing_score": False,
            "points_data": None,
            "possible_points_data": None,
        }

        sorted_stamps_returned = sorted(
            stamps, key=lambda x: x["stamp"]["issuanceDate"]
        )

        for i in range(0, len(sorted_sample_stamps_updated)):
            provider = sorted_sample_stamps_updated[i]["credentialSubject"]["provider"]
            stamp = sorted_sample_stamps_updated[i]
            assert sorted_stamps_returned[i] == {
                # For these fields, values are set by the server
                "id": sorted_stamps_returned[i]["id"],
                # For the attributes below we know the expected values
                "address": sample_address.lower(),
                "provider": provider,
                "stamp": stamp,
            }

        # Test that stamps are stored correctly
        cc = sorted(
            list(CeramicCache.objects.filter(deleted_at__isnull=True).values()),
            key=lambda x: x["stamp"]["issuanceDate"],
        )

        for i, c in enumerate(cc):
            provider = sorted_sample_stamps_updated[i]["credentialSubject"]["provider"]
            stamp = sorted_sample_stamps_updated[i]
            assert c == {
                # Just copy the automatically generated values over
                "id": c["id"],
                "created_at": c["created_at"],
                "updated_at": c["updated_at"],
                # Here are the values we control
                "address": sample_address.lower(),
                "compose_db_save_status": "pending",
                "compose_db_stream_id": "",
                "deleted_at": None,
                "expiration_date": datetime.fromisoformat(stamp["expirationDate"]),
                "issuance_date": datetime.fromisoformat(stamp["issuanceDate"]),
                "proof_value": stamp["proof"]["proofValue"],
                "provider": provider,
                "source_scorer_id": ui_scorer,
                "stamp": stamp,
                "source_app": CeramicCache.SourceApp.PASSPORT.value,
                "type": 1,
            }

        # Check that old versions of stamps are marked as deleted
        cc = sorted(
            list(CeramicCache.objects.filter(deleted_at__isnull=False).values()),
            key=lambda x: x["stamp"]["issuanceDate"],
        )

        assert len(cc) == len(bulk_payload)

        for i, c in enumerate(cc):
            provider = bulk_payload[i]["stamp"]["credentialSubject"]["provider"]
            stamp = sorted_sample_stamps[i]

            assert c["deleted_at"] is not None
            assert c == {
                # Just copy the automatically generated values over
                "id": c["id"],
                "created_at": c["created_at"],
                "updated_at": c["updated_at"],
                "deleted_at": c["deleted_at"],
                # Here are the values we control
                "address": sample_address.lower(),
                "compose_db_save_status": "pending",
                "compose_db_stream_id": "",
                "expiration_date": datetime.fromisoformat(stamp["expirationDate"]),
                "issuance_date": datetime.fromisoformat(stamp["issuanceDate"]),
                "proof_value": stamp["proof"]["proofValue"],
                "provider": provider,
                "source_scorer_id": ui_scorer,
                "stamp": stamp,
                "source_app": CeramicCache.SourceApp.PASSPORT.value,
                "type": 1,
            }

    def test_bulk_update_create_doesnt_accept_greater_than_100_stamps(
        self, sample_providers, sample_address, sample_stamps, sample_token, client
    ):
        bulk_payload = []
        for i in range(0, 101):
            bulk_payload.append(
                {
                    "provider": sample_providers[0],
                    "stamp": sample_stamps[0],
                }
            )

        cache_stamp_response = client.post(
            f"{self.base_url}/stamps/bulk",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 422
        assert cache_stamp_response.json() == {
            "detail": "You have submitted too many stamps."
        }

    def test_successful_bulk_delete(
        self,
        sample_providers,
        sample_address,
        sample_stamps,
        sample_token,
        ui_scorer,
        client,
    ):
        sorted_sample_stamps = sorted(sample_stamps, key=lambda x: x["issuanceDate"])
        bulk_payload = []
        for stamp in sorted_sample_stamps:
            CeramicCache.objects.create(
                type=self.stamp_version,
                address=sample_address,
                provider=stamp["credentialSubject"]["provider"],
                stamp=stamp,
                source_app=CeramicCache.SourceApp.PASSPORT.value,
                source_scorer_id=ui_scorer,
                compose_db_save_status="pending",
                expiration_date=datetime.fromisoformat(stamp["expirationDate"]),
                issuance_date=datetime.fromisoformat(stamp["issuanceDate"]),
                proof_value=stamp["proof"]["proofValue"],
            )
            bulk_payload.append(
                {
                    "address": sample_address,
                    "provider": stamp["credentialSubject"]["provider"],
                }
            )

        cache_stamp_response = client.delete(
            f"{self.base_url}/stamps/bulk",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 200
        cache_stamp_response_data = cache_stamp_response.json()
        assert cache_stamp_response_data["success"] is True
        assert len(cache_stamp_response_data["stamps"]) == 0

        # TODO: ideally score would be returned as well on DELETE, this
        # should be fixed in the future
        # score = cache_stamp_response_data["score"]

        # assert score == {
        #     "address": sample_address.lower(),
        #     "error": None,
        #     "evidence": None,
        #     "expiration_date": None,
        #     "last_score_timestamp": None,
        #     "score": None,
        #     "stamp_scores": {},
        #     "status": "DONE",
        # }

        # Check that old versions of stamps are marked as deleted
        cc = sorted(
            list(CeramicCache.objects.filter(deleted_at__isnull=False).values()),
            key=lambda x: x["stamp"]["issuanceDate"],
        )

        assert len(cc) == len(sorted_sample_stamps)

        for i, c in enumerate(cc):
            provider = bulk_payload[i]["provider"]
            stamp = sorted_sample_stamps[i]

            assert c["deleted_at"] is not None
            assert c == {
                # Just copy the automatically generated values over
                "id": c["id"],
                "created_at": c["created_at"],
                "updated_at": c["updated_at"],
                "deleted_at": c["deleted_at"],
                # Here are the values we control
                "address": sample_address.lower(),
                "compose_db_save_status": "pending",
                "compose_db_stream_id": "",
                "expiration_date": datetime.fromisoformat(stamp["expirationDate"]),
                "issuance_date": datetime.fromisoformat(stamp["issuanceDate"]),
                "proof_value": stamp["proof"]["proofValue"],
                "provider": provider,
                "source_scorer_id": ui_scorer,
                "stamp": stamp,
                "source_app": CeramicCache.SourceApp.PASSPORT.value,
                "type": 1,
            }

    def test_bulk_delete_indicates_a_subset_of_stamps_were_deleted(
        self,
        sample_providers,
        sample_address,
        sample_stamps,
        sample_token,
        ui_scorer,
        client,
    ):
        bulk_payload = []
        for i in range(0, 3):
            CeramicCache.objects.create(
                type=self.stamp_version,
                address=sample_address,
                provider=sample_providers[i],
                stamp=sample_stamps[i],
            )
            bulk_payload.append(
                {"address": sample_address, "provider": sample_providers[i]}
            )

        bulk_payload.append({"address": sample_address, "provider": "not-a-provider"})

        cache_stamp_response = client.delete(
            f"{self.base_url}/stamps/bulk",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 200
        assert cache_stamp_response.json()["success"] == True

    def test_bulk_delete_indicates_no_stamps_were_deleted(
        self, sample_providers, sample_address, sample_stamps, sample_token, client
    ):
        bulk_payload = []

        for i in range(0, 3):
            bulk_payload.append(
                {"address": sample_address, "provider": sample_providers[i]}
            )

        cache_stamp_response = client.delete(
            f"{self.base_url}/stamps/bulk",
            json.dumps(bulk_payload),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert cache_stamp_response.status_code == 404
        assert cache_stamp_response.json() == {
            "detail": "Unable to find stamp to delete."
        }

    def test_get_address_from_did(self, sample_address):
        did = f"did:pkh:eip155:1:{sample_address}"
        address = get_address_from_did(did)
        assert address == sample_address
