import json
from io import StringIO
from typing import Dict
from unittest.mock import AsyncMock, MagicMock, patch

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TransactionTestCase
from ninja import Schema

from passport.api import (
    DetailedScoreModel,
)
from registry.models import BatchModelScoringRequest, BatchRequestStatus


# Something weird is going on with mocks and union types. These override
# types are necessary or else mock DetailedScoreModels are converted
# to plain ScoreModels
class MockPassportAnalysisDetails(Schema):
    models: Dict[str, DetailedScoreModel]


class MockPassportAnalysisResponse(Schema):
    address: str
    details: MockPassportAnalysisDetails


class TestProcessBatchModelAddressUploads(TransactionTestCase):
    def test_process_pending_requests(self):
        # Create a mock for handle_get_analysis
        mock_handle_get_analysis = AsyncMock(
            return_value=MockPassportAnalysisResponse(
                address="0x0",
                details=MockPassportAnalysisDetails(
                    models={
                        "optimism": DetailedScoreModel(
                            score=75,
                            num_transactions=100,
                            first_funder=None,
                            first_funder_amount=None,
                            first_funder_timestamp=None,
                        )
                    }
                ),
            )
        )

        with patch(
            "registry.management.commands.process_batch_model_address_upload.BULK_MODEL_SCORE_RETRY_SLEEP",
            0,
        ):
            with patch(
                "registry.management.commands.process_batch_model_address_upload.handle_get_analysis",
                mock_handle_get_analysis,
            ):
                # Create a pending request
                trigger_file = ContentFile(
                    json.dumps(
                        {"action": "score", "batch_model_scoring_request_id": 123}
                    ),
                    name="score.json",
                )

                input_file = ContentFile(
                    """Address
0xd5680a051302d427efa518238fda2c848eebe715
0xd5680a051302d427efa518238fda2c848eebe714
0x0636F974D29d947d4946b2091d769ec6D2d415DE""",
                    name="addresses.json",
                )
                scoring_request = BatchModelScoringRequest.objects.create(
                    status=BatchRequestStatus.PENDING.value,
                    trigger_processing_file=trigger_file,
                    input_addresses_file=input_file,
                    model_list=["model1", "model2"],
                )

                # Call the command
                call_command(
                    "process_batch_model_address_upload",
                    str(scoring_request.trigger_processing_file),
                )

                updated_request = BatchModelScoringRequest.objects.get(
                    id=scoring_request.id
                )
                self.assertEqual(
                    updated_request.status,
                    BatchRequestStatus.DONE.value,
                    f"Expected status DONE, but got {scoring_request.status}",
                )
                self.assertEqual(
                    updated_request.progress,
                    100,
                    f"Expected progress 100, but got {scoring_request.progress}",
                )

                expected_calls = 3  # 1 files * 3 addresses each
                self.assertEqual(
                    mock_handle_get_analysis.call_count,
                    expected_calls,
                    f"Expected {expected_calls} calls to handle_get_analysis, but got {mock_handle_get_analysis.call_count}",
                )

    def test_process_pending_requests_with_errors(self):
        success_response = MockPassportAnalysisResponse(
            address="0x0",
            details=MockPassportAnalysisDetails(
                models={
                    "optimism": DetailedScoreModel(
                        score=75,
                        num_transactions=100,
                        first_funder=None,
                        first_funder_amount=None,
                        first_funder_timestamp=None,
                    )
                }
            ),
        )

        mock_handle_get_analysis = AsyncMock(
            side_effect=[
                Exception({"error": "error"}),
                success_response,
                success_response,
                success_response,
            ]
        )

        with patch(
            "registry.management.commands.process_batch_model_address_upload.BULK_MODEL_SCORE_RETRY_SLEEP",
            0,
        ):
            with patch(
                "registry.management.commands.process_batch_model_address_upload.handle_get_analysis",
                mock_handle_get_analysis,
            ):
                # Create a pending request
                trigger_file = ContentFile(
                    json.dumps(
                        {"action": "score", "batch_model_scoring_request_id": 123}
                    ),
                    name="score.json",
                )

                input_file = ContentFile(
                    """Address
0xd5680a051302d427efa518238fda2c848eebe715
0xd5680a051302d427efa518238fda2c848eebe714
0x0636F974D29d947d4946b2091d769ec6D2d415DE""",
                    name="addresses.json",
                )
                scoring_request = BatchModelScoringRequest.objects.create(
                    status=BatchRequestStatus.PENDING.value,
                    trigger_processing_file=trigger_file,
                    input_addresses_file=input_file,
                    model_list=["model1", "model2"],
                )

                # Call the command
                call_command(
                    "process_batch_model_address_upload",
                    str(scoring_request.trigger_processing_file),
                )

                updated_request = BatchModelScoringRequest.objects.get(
                    id=scoring_request.id
                )
                self.assertEqual(
                    updated_request.status,
                    BatchRequestStatus.DONE.value,
                    f"Expected status DONE, but got {scoring_request.status}",
                )
                self.assertEqual(
                    updated_request.progress,
                    100,
                    f"Expected progress 100, but got {scoring_request.progress}",
                )

                expected_calls = 4
                self.assertEqual(
                    mock_handle_get_analysis.call_count,
                    expected_calls,
                    f"Expected {expected_calls} calls to handle_get_analysis, but got {mock_handle_get_analysis.call_count}",
                )

    def test_process_pending_requests_with_all_errors(self):
        mock_handle_get_analysis = AsyncMock(side_effect=Exception({"error": "error"}))

        with patch(
            "registry.management.commands.process_batch_model_address_upload.BULK_MODEL_SCORE_RETRY_SLEEP",
            0,
        ):
            with patch(
                "registry.management.commands.process_batch_model_address_upload.handle_get_analysis",
                mock_handle_get_analysis,
            ):
                # Create a pending request
                trigger_file = ContentFile(
                    json.dumps(
                        {"action": "score", "batch_model_scoring_request_id": 123}
                    ),
                    name="score.json",
                )

                input_file = ContentFile(
                    """Address
0xd5680a051302d427efa518238fda2c848eebe715
0xd5680a051302d427efa518238fda2c848eebe714
0x0636F974D29d947d4946b2091d769ec6D2d415DE""",
                    name="addresses.json",
                )
                scoring_request = BatchModelScoringRequest.objects.create(
                    status=BatchRequestStatus.PENDING.value,
                    trigger_processing_file=trigger_file,
                    input_addresses_file=input_file,
                    model_list=["model1", "model2"],
                )

                # Call the command
                call_command(
                    "process_batch_model_address_upload",
                    str(scoring_request.trigger_processing_file),
                )

                updated_request = BatchModelScoringRequest.objects.get(
                    id=scoring_request.id
                )
                self.assertEqual(
                    updated_request.status,
                    BatchRequestStatus.DONE.value,
                    f"Expected status DONE, but got {scoring_request.status}",
                )
                self.assertEqual(
                    updated_request.progress,
                    100,
                    f"Expected progress 100, but got {scoring_request.progress}",
                )

                expected_calls = 15
                self.assertEqual(
                    mock_handle_get_analysis.call_count,
                    expected_calls,
                    f"Expected {expected_calls} calls to handle_get_analysis, but got {mock_handle_get_analysis.call_count}",
                )

    def test_handle_error_during_processing(self):
        with patch(
            "registry.management.commands.process_batch_model_address_upload.BULK_MODEL_SCORE_RETRY_SLEEP",
            0,
        ):
            # Create a pending request
            trigger_file = ContentFile(
                json.dumps({"action": "score", "batch_model_scoring_request_id": 123}),
                name="score.json",
            )

            # We just create an empty invalid file ...
            input_file = ContentFile(
                """


""",
                name="addresses.json",
            )
            scoring_request = BatchModelScoringRequest.objects.create(
                status=BatchRequestStatus.PENDING.value,
                trigger_processing_file=trigger_file,
                input_addresses_file=input_file,
                model_list=["model1", "model2"],
            )

            # Call the command
            call_command(
                "process_batch_model_address_upload",
                str(scoring_request.trigger_processing_file),
            )

            # Refresh the request from the database
            request = BatchModelScoringRequest.objects.first()
            self.assertEqual(
                request.status,
                BatchRequestStatus.ERROR.value,
                f"Expected status ERROR, but got {request.status}",
            )
