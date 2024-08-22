import asyncio
import csv
import json
import os
import time
from io import BytesIO, StringIO, TextIOWrapper
from itertools import islice
from nis import cat

import boto3
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from eth_utils.address import to_checksum_address
from tqdm import tqdm

from passport.api import fetch_all, handle_get_analysis
from registry.admin import get_s3_client
from registry.models import BatchModelScoringRequest, BatchRequestStatus
from scorer.settings import (
    BULK_MODEL_SCORE_BATCH_SIZE,
    BULK_MODEL_SCORE_REQUESTS_RESULTS_FOLDER,
    BULK_SCORE_REQUESTS_ADDRESS_LIST_FOLDER,
    BULK_SCORE_REQUESTS_BUCKET_NAME,
)


class Command(BaseCommand):
    help = "Process batch model address uploads"
    average_lambda_duration = 0
    total_lambda_calls = 0

    def handle(self, *args, **options):
        asyncio.run(self.async_handle(*args, **options))

    async def async_handle(self, *args, **options):
        self.stdout.write(f"Received bucket name: {os.environ['S3_BUCKET']}")
        self.stdout.write(f"Received object key : {os.environ['S3_OBJECT_KEY']}")

        s3_uri = f"s3://{os.environ['S3_BUCKET']}/{os.environ['S3_OBJECT_KEY']}"

        try:
            self.stdout.write(f"Processing fil: {s3_uri}")

            file = await sync_to_async(self.download_from_s3)(s3_uri)

            # Find the request id from the filename.
            filename = os.environ["S3_OBJECT_KEY"].split(
                f"{BULK_SCORE_REQUESTS_ADDRESS_LIST_FOLDER}/"
            )[-1]

            request = BatchModelScoringRequest.objects.get(s3_filename=filename)

            if file and request:
                self.stdout.write(self.style.SUCCESS("Got stream, processing CSV"))
                bytes = BytesIO(file.read())
                text = TextIOWrapper(bytes, encoding="utf-8")
                csv_data = csv.reader(text)
                total_rows = sum(1 for row in csv_data)

                text.seek(0)
                csv_data = csv.reader(text)

                model_list = request.model_list

                results = []
                processed_rows = 0
                for batch in self.process_csv_in_batches(csv_data):
                    try:
                        batch_results = await self.get_analysis(batch, model_list)
                        results.extend(batch_results)
                        processed_rows += len(batch_results)
                        progress = int((processed_rows / total_rows) * 100)
                        await self.update_progress(request, progress)
                        if progress % 5 == 0:
                            await self.create_and_upload_results_csv(
                                request.id,
                                results,
                                f"{request.s3_filename}-partial-{progress}",
                            )
                    except Exception as e:
                        self.stderr.write(
                            self.style.ERROR(
                                f"Error processing batch: {str(e)} - Processed rows: {processed_rows}, Total Rows: {total_rows}"
                            )
                        )

                await self.create_and_upload_results_csv(
                    request.id, results, request.s3_filename
                )

            # Update status to DONE
            request.status = BatchRequestStatus.DONE
            request.progress = 100
            await sync_to_async(request.save)()

            self.stdout.write(
                self.style.SUCCESS(f"Successfully processed request: {request.id}")
            )
        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f"Error processing file {s3_uri}: {str(e)}")
            )
            request.status = BatchRequestStatus.ERROR
            await sync_to_async(request.save)()

    async def update_progress(self, request, progress):
        request.progress = progress
        await sync_to_async(request.save)()
        self.stdout.write(f"Updated progress for request {request.id}: {progress}%")

    def download_from_s3(self, s3_filename):
        try:
            response = get_s3_client().get_object(
                Bucket=BULK_SCORE_REQUESTS_BUCKET_NAME,
                Key=f"{BULK_SCORE_REQUESTS_ADDRESS_LIST_FOLDER}/{s3_filename}",
            )
            return response["Body"]
        except Exception as e:
            raise CommandError(f"Failed to download file from S3: {str(e)}")

    def process_csv_in_batches(self, csv_data, batch_size=BULK_MODEL_SCORE_BATCH_SIZE):
        while True:
            batch = list(islice(csv_data, batch_size))
            if not batch:
                break
            yield batch

    async def get_analysis(self, batch, model_list):
        tasks = []
        for row in batch:
            address = row[0]
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
        try:
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
            result = json.dumps(details_dict)

            self.stdout.write(f"Processed address {address}:")
            self.stdout.write(f"  Duration: {duration:.2f} seconds")
            self.stdout.write(
                f"  Average Duration: {self.average_lambda_duration:.2f} seconds"
            )

            return address, result
        except Exception as e:
            error = self.style.ERROR(f"Error processing address {address}: {str(e)}")
            self.stderr.write(error)
            return address, error

    async def create_and_upload_results_csv(self, request_id, results, filename):
        csv_buffer = StringIO()
        csv_writer = csv.writer(csv_buffer)
        csv_writer.writerow(["Address", "Result"])  # Header row
        for address, result in results:
            csv_writer.writerow([address, result])

        # Upload to S3
        s3_client = get_s3_client()
        await sync_to_async(s3_client.put_object)(
            Bucket=BULK_SCORE_REQUESTS_BUCKET_NAME,
            Key=f"{BULK_MODEL_SCORE_REQUESTS_RESULTS_FOLDER}/{filename}",
            Body=csv_buffer.getvalue().encode("utf-8"),
            ContentType="text/csv",
        )
        self.stdout.write(self.style.SUCCESS(f"Uploaded results to S3: {filename}"))
