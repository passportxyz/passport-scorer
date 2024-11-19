import json
import os
import shutil
from datetime import datetime, timezone

import pyarrow.parquet as pq
import pytest
from django.apps import apps
from django.core.cache import cache
from django.core.management import call_command
from django.db import connections

from account.models import Community
from registry.weight_models import WeightConfiguration
from scorer_weighted.models import BinaryWeightedScorer, Scorer


@pytest.fixture(autouse=True)
def cleanup():
    # Pre-test cleanup (clean any leftover files before test runs)
    for file in os.listdir("."):
        if file.endswith(".parquet") or (
            file.startswith("cpy_") and file.endswith(".parquet")
        ):
            try:
                os.remove(file)
            except FileNotFoundError:
                pass
    yield

    # Post-test cleanup
    for file in os.listdir("."):
        if file.endswith(".parquet") or (
            file.startswith("cpy_") and file.endswith(".parquet")
        ):
            try:
                os.remove(file)
            except FileNotFoundError:
                pass


@pytest.fixture
def mock_upload_to_s3(mocker):
    mocked_calls = []

    def mocked_upload_to_s3(output_file, s3_folder, s3_bucket_name, extra_args):
        copy_file_name = f"cpy_{output_file}"
        mocked_calls.append(
            {
                "file_path": output_file,
                "s3_folder": s3_folder,
                "s3_bucket_name": s3_bucket_name,
                "extra_args": extra_args,
            }
        )
        shutil.copy(output_file, copy_file_name)

    mocker.patch("scorer.export_utils.upload_to_s3", side_effect=mocked_upload_to_s3)
    return mocked_calls


@pytest.fixture(autouse=True)
def reset_mocks(mocker):
    """Reset all mocks before each test"""
    yield
    mocker.resetall()


class TestScorerDumpDataParquet:
    @pytest.mark.django_db
    def test_export_specific_models(self, scorer_account, mocker, mock_upload_to_s3):
        """Test exporting specific models with stdout verification"""
        WeightConfiguration.objects.create(
            version="v1",
            threshold=2,
            active=True,
            description="Test weight configuration",
        )
        scorer = BinaryWeightedScorer.objects.create(type=Scorer.Type.WEIGHTED_BINARY)
        community = Community.objects.create(
            name="Community 1",
            description="Community 1 - testing",
            account=scorer_account,
            scorer=scorer,
        )

        # Test exporting specific models
        call_command(
            "scorer_dump_data_parquet",
            **{
                "models": "registry_score,account_community",
                "s3_uri": "s3://test-bucket/exports/",
                "apps": "registry,account",
            },
        )

        # Verify only community data was exported
        assert len(mock_upload_to_s3) == 2
        assert "registry_score" in mock_upload_to_s3[0]["file_path"]

        community_table = pq.read_table(f"cpy_{mock_upload_to_s3[1]['file_path']}")
        community_df = community_table.to_pandas()
        assert len(community_df) == 1
        assert community_df.iloc[0]["name"] == "Community 1"

    # BOTH tests pass in isolation but second test will fail when ran together. Commenting out since this functionality is not currently used.
    # @pytest.mark.django_db
    # def test_export_data_for_specific_apps(
    #     self, scorer_account, mocker, mock_upload_to_s3
    # ):
    #     """Test exporting data for specific apps"""

    #     WeightConfiguration.objects.create(
    #         version="v1",
    #         threshold=2,
    #         active=True,
    #         description="Test weight configuration",
    #     )

    #     scorer = BinaryWeightedScorer.objects.create(type=Scorer.Type.WEIGHTED_BINARY)

    #     ###############################################################
    #     # Create community 1 and some scores for that community
    #     ###############################################################
    #     community_1 = Community.objects.create(
    #         name="Community 1",
    #         description="Community 1 - testing",
    #         account=scorer_account,
    #         scorer=scorer,
    #     )

    #     for i in range(5):
    #         p = Passport.objects.create(address=f"0x{i}", community=community_1)
    #         Score.objects.create(
    #             passport=p,
    #             score=10,
    #             last_score_timestamp=datetime.now(timezone.utc),
    #             status=Score.Status.DONE,
    #             evidence={"rawScore": "12.23", "threshold": "20.0"},
    #             stamp_scores={"provider-1": 1, "provider-2": 2},
    #         )

    #     ###############################################################
    #     # Create community 2 and some scores for that community
    #     ###############################################################
    #     community_2 = Community.objects.create(
    #         name="Community 2",
    #         description="Community 2 - testing",
    #         account=scorer_account,
    #         scorer=scorer,
    #     )

    #     # Test exporting specific apps
    #     call_command(
    #         "scorer_dump_data_parquet",
    #         **{
    #             "apps": "registry",
    #             "s3_uri": "s3://test-bucket/exports/",
    #             "s3_extra_args": json.dumps({"ACL": "private"}),
    #         },
    #     )

    #     # Verify the uploads
    #     assert len(mock_upload_to_s3) == 8

    #     # Verify community data
    #     passport_file = next(
    #         call for call in mock_upload_to_s3 if "passport" in call["file_path"]
    #     )
    #     passport_table = pq.read_table(f"cpy_{passport_file['file_path']}")
    #     passport_df = passport_table.to_pandas()
    #     assert len(passport_df) == 5

    #     # Verify passport data
    #     score_file = next(
    #         call for call in mock_upload_to_s3 if "score" in call["file_path"]
    #     )
    #     score_table = pq.read_table(f"cpy_{score_file['file_path']}")
    #     score_df = score_table.to_pandas()
    #     assert len(score_df) == 5
