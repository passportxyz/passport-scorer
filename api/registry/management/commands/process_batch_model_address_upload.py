import asyncio
import csv
import json
import time
from datetime import datetime, timezone
from io import StringIO
from typing import AsyncGenerator, Dict, List

from asgiref.sync import sync_to_async
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from eth_utils.address import to_checksum_address

from passport.api import handle_get_analysis
from registry.models import (
    BatchModelScoringRequest,
    BatchModelScoringRequestItem,
    BatchRequestItemStatus,
    BatchRequestStatus,
)
from scorer.settings import (
    BULK_MODEL_SCORE_BATCH_SIZE,
    BULK_MODEL_SCORE_RETRY_SLEEP,
    S3_BUCKET,
    S3_OBJECT_KEY,
)


class Command(BaseCommand):
    help = "Process batch model address uploads"
    average_lambda_duration = 0
    total_lambda_calls = 0

    def add_arguments(self, parser):
        parser.add_argument(
            "tigger-file",
            nargs="?",
            type=str,
            default=None,
            help="Path to the trigger file",
        )

    def handle(self, *args, **options):
        asyncio.run(self.async_handle(*args, **options))

    async def async_handle(self, *args, **options):
        trigger_file_path = None
        request = None
        try:
            trigger_file_path = options.get("tigger-file")
            self.stdout.write(f"Received trigger_file_path: `{trigger_file_path}`")
            self.stdout.write(f"Received bucket name: `{S3_BUCKET}`")
            self.stdout.write(f"Received object key : `{S3_OBJECT_KEY}`")
            self.stdout.write(f"Batch size          : `{BULK_MODEL_SCORE_BATCH_SIZE}`")
            if not trigger_file_path:
                trigger_file_path = S3_OBJECT_KEY

            self.stdout.write(f"Search request with path: `{trigger_file_path}`")
            request = await sync_to_async(BatchModelScoringRequest.objects.get)(
                trigger_processing_file=trigger_file_path
            )
            self.stdout.write(f"Found request: {request.id}")

            await self.create_batch_request_items(request)

            with request.trigger_processing_file.open("rb") as trigger_file:
                data = json.load(trigger_file)
                print(data)

                if data["action"] == "score_all":
                    await BatchModelScoringRequestItem.objects.filter(
                        batch_scoring_request=request
                    ).aupdate(status=BatchRequestItemStatus.PENDING)
                elif data["action"] == "score_errors":
                    await BatchModelScoringRequestItem.objects.filter(
                        batch_scoring_request=request,
                        status=BatchRequestItemStatus.ERROR,
                    ).aupdate(status=BatchRequestItemStatus.PENDING)

            total_items = await request.items.acount()
            request.progress = 0
            request.last_progress_update = datetime.now(timezone.utc)
            request.status = BatchRequestStatus.PENDING
            await request.asave()

            self.stdout.write(f"total_items {total_items}")

            self.stdout.write(f"Processing file: {trigger_file_path}")

            model_list = request.model_list

            processed_items = await request.items.filter(
                status=BatchRequestStatus.DONE
            ).acount()
            self.stdout.write("initial processed_items: {processed_items}")
            async for batch in self.process_request_in_batches(request):
                try:
                    batch_results = await self.get_analysis(batch.values(), model_list)

                    for address, result in batch_results:
                        scoring_reqeust_item = batch[address.lower()]
                        if isinstance(result, dict):
                            scoring_reqeust_item.result = result
                            scoring_reqeust_item.status = BatchRequestItemStatus.DONE
                        else:
                            scoring_reqeust_item.result = str(result)
                            scoring_reqeust_item.status = BatchRequestItemStatus.ERROR

                    await BatchModelScoringRequestItem.objects.abulk_update(
                        batch.values(), fields=("result", "status")
                    )

                    processed_items += len(batch_results)
                    progress = int((processed_items / total_items) * 100)
                    self.stdout.write(
                        "progress {processed_items} / {total_items} => {progress}"
                    )
                    await self.update_progress(request, progress)
                except Exception as e:
                    self.stderr.write(
                        self.style.ERROR(
                            f"Error processing batch: {str(e)} - Processed rows: {processed_items}, Total Rows: {total_items}"
                        )
                    )

            await self.create_and_upload_results_csv(request)

            # Update status to DONE
            request.status = BatchRequestStatus.DONE
            request.progress = 100
            await request.asave()

            self.stdout.write(
                self.style.SUCCESS(f"Successfully processed request: {request.id}")
            )
        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f"Error processing file {trigger_file_path}: {str(e)}")
            )
            if request:
                request.status = BatchRequestStatus.ERROR
                await request.asave()

    async def create_batch_request_items(
        self, batch_scoring_request: BatchModelScoringRequest
    ):
        batch_items = []
        with batch_scoring_request.input_addresses_file.open("r") as f:
            first_row = True
            for row in csv.reader(f):
                print(row)
                if first_row and row[0].lower() == "address":
                    first_row = False
                    continue
                else:
                    batch_items.append(
                        BatchModelScoringRequestItem(
                            batch_scoring_request=batch_scoring_request,
                            address=row[0],
                        )
                    )

                if len(batch_items) >= 1000:
                    await BatchModelScoringRequestItem.objects.abulk_create(
                        batch_items,
                        ignore_conflicts=True,
                        unique_fields=["batch_scoring_request", "address"],
                    )
                    batch_items = []

        if batch_items:
            await BatchModelScoringRequestItem.objects.abulk_create(
                batch_items,
                ignore_conflicts=True,
                unique_fields=["batch_scoring_request", "address"],
            )

    async def update_progress(self, request, progress):
        request.progress = progress
        request.last_progress_update = datetime.now(timezone.utc)
        await sync_to_async(request.save)()
        self.stdout.write(f"Updated progress for request {request.id}: {progress}%")

    async def process_request_in_batches(
        self,
        batch_scoring_request: BatchModelScoringRequest,
        batch_size=BULK_MODEL_SCORE_BATCH_SIZE,
    ) -> AsyncGenerator[Dict[str, BatchModelScoringRequestItem], None]:
        last_id = None
        base_query = BatchModelScoringRequestItem.objects.filter(
            batch_scoring_request=batch_scoring_request,
            status=BatchRequestItemStatus.PENDING,
        ).order_by("id")
        while True:
            if last_id:
                query = base_query.filter(id__gt=last_id)
            else:
                query = base_query

            batch = {}
            async for item in query[:batch_size]:
                batch[item.address.lower()] = item
                last_id = item.id

            if not batch:
                break

            yield batch

    async def get_analysis(
        self, batch_request_items: List[BatchModelScoringRequestItem], model_list: str
    ):
        tasks = []
        for batch_request_item in batch_request_items:
            address = batch_request_item.address
            if not address or address == "":
                continue
            try:
                task = asyncio.create_task(
                    self.process_address(to_checksum_address(address), model_list)
                )
                tasks.append(task)
            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f"Error getting analysis for {address}: {str(e)}")
                )
        results = await asyncio.gather(*tasks)
        return results

    def update_average_duration(self, duration):
        self.total_lambda_calls += 1
        self.average_lambda_duration = (
            self.average_lambda_duration * (self.total_lambda_calls - 1) + duration
        ) / self.total_lambda_calls

    async def process_address(self, address, model_list):
        num_attempts = 5
        last_attempt = num_attempts - 1

        for attempt in range(num_attempts):
            try:
                return await self._process_address(address, model_list)
            except Exception as e:
                if attempt == last_attempt:
                    self.stderr.write(
                        self.style.ERROR(
                            f"Error processing address {address}: {str(e)}"
                        )
                    )
                    return address, e
                else:
                    await asyncio.sleep(BULK_MODEL_SCORE_RETRY_SLEEP)

    async def _process_address(self, address, model_list):
        start_time = time.time()
        analysis = await handle_get_analysis(address, model_list, False, True)
        end_time = time.time()
        duration = end_time - start_time

        self.update_average_duration(duration)

        details_dict = {
            "models": {
                model: {
                    "score": score.score,
                    "num_transactions": score.num_transactions,
                    "first_funder": score.first_funder,
                    "first_funder_amount": score.first_funder_amount,
                    "first_funder_timestamp": score.first_funder_timestamp,
                }
                for model, score in analysis.details.models.items()
            }
        }
        result = details_dict

        self.stdout.write(f"Processed address {address}:")
        self.stdout.write(f"  Duration: {duration:.2f} seconds")
        self.stdout.write(
            f"  Average Duration: {self.average_lambda_duration:.2f} seconds"
        )

        return address, result

    async def create_and_upload_results_csv(self, request: BatchModelScoringRequest):
        csv_buffer = StringIO()
        csv_writer = csv.writer(csv_buffer)
        csv_writer.writerow(["Address", "Result"])  # Header row
        async for item in request.items.all():
            csv_writer.writerow([item.address, json.dumps(item.result)])

        filename = f"request_id_{request.id}.csv"

        # Create a ContentFile
        content_file = ContentFile(csv_buffer.getvalue(), name=filename)

        request.results_file = content_file
