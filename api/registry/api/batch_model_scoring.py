from django.shortcuts import get_object_or_404
from ninja import File, Form
from ninja.files import UploadedFile

from registry.api.schema import (
    BatchModelScoringRequestCreateResponse,
    BatchModelScoringRequestStatusResponse,
)
from registry.models import BatchModelScoringRequest


def handle_create_batch_request(
    file: UploadedFile, model_list: str
) -> BatchModelScoringRequestCreateResponse:
    request = BatchModelScoringRequest.objects.create(
        model_list=model_list,
        s3_filename="",
        input_addresses_file=file,
    )
    request.trigger("score")
    return BatchModelScoringRequestCreateResponse(
        id=request.id,
        status=request.status,
    )


def handle_get_batch_request_status(
    request_id: int,
) -> BatchModelScoringRequestStatusResponse:
    obj = get_object_or_404(BatchModelScoringRequest, id=request_id)
    results_url = obj.results_file.url if obj.results_file else None
    return BatchModelScoringRequestStatusResponse(
        id=obj.id,
        status=obj.status,
        progress=obj.progress,
        model_list=obj.model_list,
        created_at=obj.created_at,
        last_progress_update=obj.last_progress_update,
        results_url=results_url,
    )
