import json
from datetime import datetime, timezone

import pandas as pd
import pytest
from django.core.management import call_command
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connections

from data_model.models import Cache


@pytest.fixture
def create_cache_table():
    connection = connections["data_model"]
    # setup: aka this code will run before the test
    # connection.disable_constraint_checking

    db_engine = connections["data_model"].settings_dict["ENGINE"]
    # This test is expected to only fork on postgres because on SQLite the unmanaged model cannot be created successfully
    assert db_engine == "django.db.backends.postgresql", (
        f"This test is currently only supposed to work on postgres. Models cannot be created on SQLite atm. Current engine: {db_engine}"
    )

    # Disable foreign key constraint checks
    # TODO: this is unfortunatly not work for SQLite, it does not have the desired effect ...
    # with connection.cursor() as cursor:
    #     cursor.execute('PRAGMA foreign_keys=OFF')

    with connection.constraint_checks_disabled():
        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(Cache)

    yield
    # teardown: aka this will run after the test
    with connection.constraint_checks_disabled():
        with connection.schema_editor() as schema_editor:
            schema_editor.delete_model(Cache)

    # Re-enable foreign key constraint checks
    # TODO: this is unfortunatly not work for SQLite
    # with connection.cursor() as cursor:
    #     cursor.execute('PRAGMA foreign_keys=ON')


class TestGetStamps:
    @pytest.mark.django_db(databases=["default", "data_model"])
    def test_dump_data_eth_model_score_jsonl(self, mocker, create_cache_table):
        """Test the 'scorer_dump_data_model_score' command export jsonl format"""

        ###############################################################
        # Create data in the DB
        ###############################################################
        expected_data = []
        for i in range(10):
            address = f"0x{i}"
            timestamp = datetime(2024, 4, 9, i, 0, 0, tzinfo=timezone.utc)
            value = {
                "data": {"human_probability": i},
                "meta": {"version": "v1", "Training_date": "2023/12/27"},
            }
            c = Cache.objects.create(
                key_0="predict",
                key_1=address,
                value=value,
                updated_at=timestamp,
            )
            expected_data.append(
                json.loads(
                    json.dumps(
                        {
                            "id": c.id,
                            "key_0": "predict",
                            "key_1": address,
                            "value": value,
                            "updated_at": timestamp,
                        },
                        cls=DjangoJSONEncoder,
                    )
                )
            )
            # Also add data to cache for other models (differet value in first element in key)
            # The export command should filter correctly
            Cache.objects.create(
                key_0="predict_nft",
                key_1=address,
                value={
                    "data": {"human_probability": i},
                    "meta": {"version": "v1", "Training_date": "2023/12/27"},
                },
                updated_at=timestamp,
            )

        s3_client_mock = mocker.patch("boto3.client")
        s3_upload_mock = s3_client_mock.return_value.upload_file
        call_command(
            "scorer_dump_data_model_score",
            *[],
            **{
                "batch_size": 2,  # set a small batch size, we want make sure it can handle pagination
                "s3_uri": "s3://public.scorer.gitcoin.co/passport_scores/",
                "filename": "eth_model_score.jsonl",
                "data_model": "predict",
            },
        )

        s3_upload_mock.assert_called_once()

        # The data file will always be the 1st file in the list
        data_file = s3_upload_mock.call_args[0][0]
        data = []
        expected_keys = {"id", "key_0", "key_1", "value", "updated_at"}
        expected_data_keys = {"data", "meta"}
        with open(data_file, "r") as f:
            for idx, expected_record in enumerate(expected_data):
                line = f.readline()
                line_data = json.loads(line)
                data.append(line_data)

                assert expected_keys == set(line_data.keys())
                assert expected_data_keys == set(line_data["value"].keys())
                assert expected_data[idx] == line_data

        # We only expect the number of records we generated for the community that we filtered by
        assert len(data) == 10

    @pytest.mark.django_db(databases=["default", "data_model"])
    def test_dump_data_eth_model_score_parquet(self, mocker, create_cache_table):
        """Test the 'scorer_dump_data_model_score' command export parquet format"""

        ###############################################################
        # Create data in the DB
        ###############################################################
        expected_data = []
        for i in range(10):
            address = f"0x{i}"
            timestamp = datetime(2024, 4, 9, i, 0, 0, tzinfo=timezone.utc)
            value = {
                "data": {"human_probability": i},
                "meta": {"version": "v1", "Training_date": "2023/12/27"},
            }
            c = Cache.objects.create(
                key_0="predict",
                key_1=address,
                value=value,
                updated_at=timestamp,
            )
            expected_data.append(
                json.loads(
                    json.dumps(
                        {
                            "id": c.id,
                            "key_0": "predict",
                            "key_1": address,
                            "value": value,
                            "updated_at": timestamp,
                        },
                        cls=DjangoJSONEncoder,
                    )
                )
            )
            # Also add data to cache for other models (differet value in first element in key)
            # The export command should filter correctly
            Cache.objects.create(
                key_0="predict_nft",
                key_1=address,
                value={
                    "data": {"human_probability": i},
                    "meta": {"version": "v1", "Training_date": "2023/12/27"},
                },
                updated_at=timestamp,
            )

        s3_client_mock = mocker.patch("boto3.client")
        s3_upload_mock = s3_client_mock.return_value.upload_file
        call_command(
            "scorer_dump_data_model_score",
            *[],
            **{
                "batch_size": 2,  # set a small batch size, we want make sure it can handle pagination
                "s3_uri": "s3://public.scorer.gitcoin.co/passport_scores/",
                "filename": "eth_model_score.jsonl",
                "data_model": "predict",
                "format": "parquet",
            },
        )

        s3_upload_mock.assert_called_once()

        # The data file will always be the 1st file in the list
        data_file = s3_upload_mock.call_args[0][0]
        data = []
        expected_keys = {"id", "key_0", "key_1", "value", "updated_at"}
        expected_data_keys = {"data", "meta"}

        # Load the Parquet file into a DataFrame
        df = pd.read_parquet(data_file)

        for idx, row in df.iterrows():
            data.append(row)
            row_dict = row.to_dict()
            row_dict["updated_at"] = row_dict["updated_at"].isoformat() + "Z"
            row_dict["value"] = json.loads(row_dict["value"])

            row_value = json.loads(row.value)
            assert expected_keys == set(df.columns)
            assert expected_data_keys == set(row_value.keys())
            assert expected_data[idx] == row_dict

        # We only expect the number of records we generated for the community that we filtered by
        assert len(data) == 10

    @pytest.mark.django_db(databases=["default", "data_model"])
    def test_dump_data_eth_model_score_parquet_multiple_models(
        self, mocker, create_cache_table
    ):
        """Test the 'scorer_dump_data_model_score' command export multiple model to parquet format"""

        ###############################################################
        # Create data in the DB
        ###############################################################
        expected_data = []
        for i in range(10):
            address = f"0x{i}"
            timestamp = datetime(2024, 4, 9, i, 0, 0, tzinfo=timezone.utc)
            value = {
                "data": {"human_probability": i},
                "meta": {"version": "v1", "Training_date": "2023/12/27"},
            }
            c = Cache.objects.create(
                key_0="predict",
                key_1=address,
                value=value,
                updated_at=timestamp,
            )
            expected_data.append(
                json.loads(
                    json.dumps(
                        {
                            "id": c.id,
                            "key_0": c.key_0,
                            "key_1": c.key_1,
                            "value": c.value,
                            "updated_at": timestamp,
                        },
                        cls=DjangoJSONEncoder,
                    )
                )
            )
            # Also add data to cache for other models (differet value in first element in key)
            # The export command should filter correctly
            c = Cache.objects.create(
                key_0="predict_nft",
                key_1=address,
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
                            "id": c.id,
                            "key_0": c.key_0,
                            "key_1": c.key_1,
                            "value": c.value,
                            "updated_at": timestamp,
                        },
                        cls=DjangoJSONEncoder,
                    )
                )
            )
        s3_client_mock = mocker.patch("boto3.client")
        s3_upload_mock = s3_client_mock.return_value.upload_file
        call_command(
            "scorer_dump_data_model_score",
            *[],
            **{
                "batch_size": 2,  # set a small batch size, we want make sure it can handle pagination
                "s3_uri": "s3://public.scorer.gitcoin.co/passport_scores/",
                "filename": "eth_model_score.jsonl",
                "data_model": "predict,predict_nft",
                "format": "parquet",
            },
        )

        s3_upload_mock.assert_called_once()

        # The data file will always be the 1st file in the list
        data_file = s3_upload_mock.call_args[0][0]
        data = []
        expected_keys = {"id", "key_0", "key_1", "value", "updated_at"}
        expected_data_keys = {"data", "meta"}

        # Load the Parquet file into a DataFrame
        df = pd.read_parquet(data_file)

        for idx, row in df.iterrows():
            data.append(row)
            row_dict = row.to_dict()
            row_dict["updated_at"] = row_dict["updated_at"].isoformat() + "Z"
            row_dict["value"] = json.loads(row_dict["value"])

            row_value = json.loads(row.value)
            assert expected_keys == set(df.columns)
            assert expected_data_keys == set(row_value.keys())
            assert expected_data[idx] == row_dict

        # We only expect the number of records we generated for the community that we filtered by
        assert len(data) == 20
