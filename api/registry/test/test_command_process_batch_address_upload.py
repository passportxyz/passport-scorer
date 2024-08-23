import asyncio
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from django.core.management import call_command
from django.test import TransactionTestCase, override_settings

from registry.models import BatchModelScoringRequest, BatchRequestStatus


class TestProcessBatchModelAddressUploads(TransactionTestCase):
    def test_process_pending_requests(self):
        mock_s3_client = MagicMock()
        mock_s3_client.get_object.return_value = {
            "ContentLength": 100,
            "Body": MagicMock(
                read=lambda: StringIO(
                    "0xd5680a051302d427efa518238fda2c848eebe714\n0xd5680a051302d427efa518238fda2c848eebe714\n0x0636F974D29d947d4946b2091d769ec6D2d415DE"
                )
                .getvalue()
                .encode()
            ),
        }

        # Create a mock for handle_get_analysis
        mock_handle_get_analysis = AsyncMock(return_value={"score": 75})

        with patch(
            "registry.management.commands.process_batch_model_address_upload.get_s3_client",
            return_value=mock_s3_client,
        ):
            with patch(
                "registry.management.commands.process_batch_model_address_upload.handle_get_analysis",
                mock_handle_get_analysis,
            ):
                old_request = BatchModelScoringRequest.objects.create(
                    status=BatchRequestStatus.PENDING.value,
                    s3_filename=f"test_file_0.csv",
                    model_list=["model1", "model2"],
                )

                good_request = BatchModelScoringRequest.objects.create(
                    status=BatchRequestStatus.PENDING.value,
                    s3_filename=f"test_file.csv",
                    model_list=["model1", "model2"],
                )

                all_requests = BatchModelScoringRequest.objects.all()
                self.assertEqual(
                    len(all_requests),
                    2,
                    f"Expected 2 requests, but found {len(all_requests)}",
                )

                call_command("process_batch_model_address_upload")

                self.assertEqual(
                    old_request.status,
                    BatchRequestStatus.PENDING.value,
                    f"Expected status PENDING, but got {old_request.status}",
                )

                self.assertEqual(
                    good_request.status,
                    BatchRequestStatus.DONE.value,
                    f"Expected status DONE, but got {good_request.status}",
                )
                self.assertEqual(
                    good_request.progress,
                    100,
                    f"Expected progress 100, but got {good_request.progress}",
                )

                expected_calls = 3  # 1 files * 3 addresses each
                self.assertEqual(
                    mock_handle_get_analysis.call_count,
                    expected_calls,
                    f"Expected {expected_calls} calls to handle_get_analysis, but got {mock_handle_get_analysis.call_count}",
                )

        assert mock_s3_client.get_object.call_count > 1

    # If you comment out the following test, the first test will fail :()
    def test_handle_error_during_processing(self):
        with patch(
            "registry.management.commands.process_batch_model_address_upload.get_s3_client"
        ) as mock_get_s3_client:
            mock_get_s3_client.return_value.get_object.side_effect = Exception(
                "Test error"
            )

            # Create a pending request
            BatchModelScoringRequest.objects.create(
                status=BatchRequestStatus.PENDING.value,
                s3_filename="test_file.csv",
                model_list=["model1", "model2"],
            )

            # Call the command
            call_command("process_batch_model_address_upload")

            # Refresh the request from the database
            request = BatchModelScoringRequest.objects.first()
            self.assertEqual(
                request.status,
                BatchRequestStatus.ERROR.value,
                f"Expected status ERROR, but got {request.status}",
            )
