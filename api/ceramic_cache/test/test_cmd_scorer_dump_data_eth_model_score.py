import json
from datetime import datetime, timezone

import pytest
from django.core.management import call_command
from data_model.models import Cache
from django.core.serializers.json import DjangoJSONEncoder


class TestGetStamps:
    @pytest.mark.django_db(databases=["default", "data_model"])
    def test_dump_data_eth_model_score(self, mocker):
        """Test the 'scorer_dump_data_eth_model_score' command"""

        ###############################################################
        # Create data in the DB
        ###############################################################
        expected_data = []
        for i in range(10):
            address = f"0x{i}"
            timestamp = datetime(2024, 4, 9, i, 0, 0, tzinfo=timezone.utc)
            Cache.objects.create(
                key=json.dumps(["predict", address]),
                value={
                    "data": {"human_probability": i},
                    "meta": {"version": "v1", "Training_date": "2023/12/27"},
                },
                updated_at=timestamp,
            )
            expected_data.append(
                json.loads(
                    json.dumps(
                        {
                            "address": address,
                            "data": {"score": str(i)},
                            "updated_at": timestamp,
                        },
                        cls=DjangoJSONEncoder,
                    )
                )
            )

        s3_upload_mock = mocker.patch(
            "ceramic_cache.management.commands.scorer_dump_data_eth_model_score.upload_to_s3"
        )
        call_command(
            "scorer_dump_data_eth_model_score",
            *[],
            **{
                "batch_size": 2,  # set a small batch size, we want make sure it can handle pagination
                "s3_uri": "s3://public.scorer.gitcoin.co/passport_scores/",
                "database": "data_model",  # needs to be set to the data model DB
            },
        )

        s3_upload_mock.assert_called_once()

        # The data file will always be the 1st file in the list
        data_file = s3_upload_mock.call_args[0][0]
        data = []
        expected_keys = {"address", "data", "updated_at"}
        expected_data_keys = {"score"}
        with open(data_file, "r") as f:
            for idx, expected_record in enumerate(expected_data):
                line = f.readline()
                line_data = json.loads(line)
                data.append(line_data)

                assert expected_keys == set(line_data.keys())
                assert expected_data_keys == set(line_data["data"].keys())
                assert expected_data[idx] == line_data

        # We only expect the number of records we generated for the community that we filtered by
        assert len(data) == 10
