import pytest
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from registry.models import BatchModelScoringRequest

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def isolated_media_root(settings, tmp_path):
    # Local FileSystemStorage writes relative to MEDIA_ROOT (default ""), i.e. the
    # working directory. Keep uploads and trigger files out of the repo.
    settings.MEDIA_ROOT = str(tmp_path)


@pytest.fixture
def auth_headers():
    return {"HTTP_AUTHORIZATION": settings.CGRANTS_API_TOKEN}


def test_create_batch_request_stores_upload_and_writes_trigger(auth_headers):
    upload = SimpleUploadedFile(
        "addresses.csv",
        b"0x0000000000000000000000000000000000000001\n",
        content_type="text/csv",
    )

    response = Client().post(
        "/internal/batch-model-scoring",
        {"model_list": "aggregate", "file": upload},
        **auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    obj = BatchModelScoringRequest.objects.get(id=body["id"])
    assert body["status"] == obj.status
    assert obj.model_list == "aggregate"
    assert obj.input_addresses_file.read() == (
        b"0x0000000000000000000000000000000000000001\n"
    )
    # .trigger("score") writes the file an EventBridge rule watches for.
    assert obj.trigger_processing_file.name
    assert b'"action": "score"' in obj.trigger_processing_file.read()


def test_get_batch_request_status_reports_progress_without_results(auth_headers):
    obj = BatchModelScoringRequest.objects.create(
        model_list="aggregate", s3_filename="", progress=42
    )

    response = Client().get(f"/internal/batch-model-scoring/{obj.id}", **auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == obj.id
    assert body["status"] == obj.status
    assert body["progress"] == 42
    assert body["model_list"] == "aggregate"
    assert body["results_url"] is None


def test_get_batch_request_status_includes_results_url_when_done(auth_headers):
    obj = BatchModelScoringRequest.objects.create(
        model_list="aggregate", s3_filename="", progress=100
    )
    obj.results_file.save("results.csv", ContentFile(b"address,score\n"))

    response = Client().get(f"/internal/batch-model-scoring/{obj.id}", **auth_headers)

    assert response.status_code == 200
    results_url = response.json()["results_url"]
    assert results_url
    assert results_url.endswith(".csv")


def test_get_batch_request_status_404s_for_unknown_id(auth_headers):
    response = Client().get("/internal/batch-model-scoring/99999", **auth_headers)

    assert response.status_code == 404
