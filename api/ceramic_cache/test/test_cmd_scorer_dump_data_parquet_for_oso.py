import shutil
from datetime import datetime, timezone

import pytest
from account.models import Community
from django.core.management import call_command
from registry.models import Passport, Score
from scorer_weighted.models import BinaryWeightedScorer, Scorer
from django.conf import settings
import pyarrow.parquet as pq


class TestGetStamps:
    @pytest.mark.django_db
    def test_export_filtered_scored_for_scorer(self, scorer_account, mocker):
        """Make sure that it is not possible to have duplicate stamps in the DB"""

        scorer = BinaryWeightedScorer.objects.create(type=Scorer.Type.WEIGHTED_BINARY)

        ###############################################################
        # Create community 1 and some scores for that community
        ###############################################################
        community_1 = Community.objects.create(
            name="Community 1",
            description="Community 1 - testing",
            account=scorer_account,
            scorer=scorer,
        )

        for i in range(5):
            p = Passport.objects.create(address=f"0x{i}", community=community_1)
            Score.objects.create(
                passport=p,
                score=10,
                last_score_timestamp=datetime.now(timezone.utc),
                status=Score.Status.DONE,
                evidence={"rawScore": "12.23", "threshold": "20.0"},
                stamp_scores={"provider-1": 1, "provider-2": 2},
            )

        ###############################################################
        # Create community 2 and some scores for that community
        ###############################################################
        community_2 = Community.objects.create(
            name="Community 2",
            description="Community 2 - testing",
            account=scorer_account,
            scorer=scorer,
        )

        settings.CERAMIC_CACHE_SCORER_ID = community_2.pk

        expected_results = []
        for i in range(5):
            p = Passport.objects.create(address=f"0x{i}", community=community_2)
            score = Score.objects.create(
                passport=p,
                score=10,
                last_score_timestamp=datetime.now(timezone.utc),
                status=Score.Status.DONE,
                evidence={"rawScore": "12.23", "threshold": "20.0"},
                stamp_scores={"provider-1": 1, "provider-2": 2},
            )
            expected_results.append(
                {
                    "passport_address": p.address,
                    "last_score_timestamp": score.last_score_timestamp.replace(
                        tzinfo=None
                    ),
                    "evidence_rawScore": score.evidence["rawScore"],
                    "evidence_threshold": score.evidence["threshold"],
                    "provider_scores": [
                        {"provider": k, "score": str(v)}
                        for k, v in score.stamp_scores.items()
                    ],
                }
            )

        mocked_upload_to_s3_call_args = []

        def mocked_upload_to_s3(output_file, _s3_folder, _s3_bucket_name, _extra_args):
            copy_file_name = f"cpy_{output_file}"
            mocked_upload_to_s3_call_args.append(
                {
                    "file_path": copy_file_name,
                    "s3_folder": _s3_folder,
                    "s3_bucket_name": _s3_bucket_name,
                    "extra_args": _extra_args,
                }
            )
            shutil.copy(output_file, copy_file_name)

        mocker.patch(
            "ceramic_cache.management.commands.scorer_dump_data_parquet_for_oso.upload_to_s3",
            side_effect=mocked_upload_to_s3,
        )
        call_command(
            "scorer_dump_data_parquet_for_oso",
            *[],
            **{
                "filename": "my_scores.parquet",
                "s3_uri": "s3://some_bucket/some_path/",
            },
        )

        assert mocked_upload_to_s3_call_args[0]["file_path"] == "cpy_my_scores.parquet"
        assert (
            mocked_upload_to_s3_call_args[0]["s3_folder"]
            == "some_path/" + datetime.now(timezone.utc).isoformat().split("T")[0]
        )
        assert mocked_upload_to_s3_call_args[0]["s3_bucket_name"] == "some_bucket"
        assert mocked_upload_to_s3_call_args[0]["extra_args"] == {}

        # Check the content of the parquet file
        # Load the Parquet file
        table = pq.read_table(mocked_upload_to_s3_call_args[0]["file_path"])

        # Convert to Pandas DataFrame
        df = table.to_pandas()

        # Check the dataframe
        assert [
            "passport_address",
            "last_score_timestamp",
            "evidence_rawScore",
            "evidence_threshold",
            "provider_scores",
        ] == list(df.columns)
        assert df.shape == (5, 5)
        for idx, (_, r) in enumerate(df.iterrows()):
            assert expected_results[idx]["passport_address"] == r.iloc[0]
            assert (
                expected_results[idx]["last_score_timestamp"]
                == r.iloc[1].to_pydatetime()
            )
            assert expected_results[idx]["evidence_rawScore"] == r.iloc[2]
            assert expected_results[idx]["evidence_threshold"] == r.iloc[3]
            assert expected_results[idx]["provider_scores"] == list(r.iloc[4])
