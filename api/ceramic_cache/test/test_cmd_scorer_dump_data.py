import json
import shutil
from datetime import datetime

import pytest
from account.models import Community
from django.core.management import call_command
from registry.models import Passport, Score
from scorer_weighted.models import BinaryWeightedScorer, Scorer


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
                last_score_timestamp=datetime.now(),
                status=Score.Status.DONE,
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

        for i in range(5):
            p = Passport.objects.create(address=f"0x{i}", community=community_2)
            Score.objects.create(
                passport=p,
                score=10,
                last_score_timestamp=datetime.now(),
                status=Score.Status.DONE,
            )

        file_names = []

        class MockS3:
            """
            This is a mock class for boto S3.
            We just want to capture the file that is about to be iploaded and check its contents.
            """

            def upload_file(self, file_name, *args, **kwargs):
                copy_file_name = f"cpy_{file_name}"
                shutil.copy(file_name, copy_file_name)
                file_names.append(copy_file_name)

        with mocker.patch(
            "ceramic_cache.management.commands.scorer_dump_data.boto3.client",
            return_value=MockS3(),
        ):

            call_command(
                "scorer_dump_data",
                *[],
                **{
                    "config": f'[{{"name":"registry.Score","filter":{{"passport__community_id":{community_1.id}}},"select_related":["passport"]}}]',
                    "s3_uri": "s3://public.scorer.gitcoin.co/passport_scores/",
                },
            )

        # The data file will always be the 1st file in the list
        data_file = file_names[0]
        data = []
        expected_keys = {
            "passport",
            "score",
            "last_score_timestamp",
            "status",
            "error",
            "evidence",
            "stamp_scores",
            "id",
        }
        expected_passport_keys = {"address", "community", "requires_calculation"}
        with open(data_file, "r") as f:
            for line in f.readlines():
                line_data = json.loads(line)
                data.append(line_data)

                assert line_data["passport"]["community"] == community_1.id
                assert expected_keys == set(line_data.keys())
                assert expected_passport_keys == set(line_data["passport"].keys())

        # We only expect the number of records we generated for the community that we filtered by
        assert len(data) == 5
