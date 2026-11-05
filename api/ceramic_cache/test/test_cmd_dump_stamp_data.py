import json
from io import StringIO

import pytest
from django.conf import settings
from django.core.management import call_command
from django.db.models import QuerySet

from ceramic_cache.models import CeramicCache, StampExports

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def replica_reads_default(mocker):
    # The command hard-codes .using("read_replica_0"). In CI, READ_REPLICA_0_URL
    # is unset, so that alias falls back to SQLite, and its TEST MIRROR copies
    # only the database NAME, not the engine. Send the replica read to the default
    # (Postgres) connection so the real query runs against the rows under test.
    real_using = QuerySet.using

    def using(self, alias):
        return real_using(self, "default" if alias == "read_replica_0" else alias)

    mocker.patch.object(QuerySet, "using", using)


@pytest.fixture
def uploads(mocker, monkeypatch, tmp_path):
    # The command writes its .jsonl to a *relative* path, then uploads and deletes
    # it. Run in tmp_path so nothing lands in the repo, and capture the file's
    # contents at upload time, before the command removes it.
    monkeypatch.chdir(tmp_path)
    captured = []

    def fake_upload(local_path, bucket, key):
        with open(local_path) as f:
            captured.append(
                {
                    "bucket": bucket,
                    "key": key,
                    "lines": [json.loads(line) for line in f if line.strip()],
                }
            )

    mock_s3 = mocker.patch("ceramic_cache.management.commands.dump_stamp_data.s3")
    mock_s3.upload_file.side_effect = fake_upload
    return captured


def _run():
    # BaseCronJobCmd swallows every exception and writes it to stderr, so a
    # broken command still "succeeds". Fail the test on that instead.
    stderr = StringIO()
    call_command("dump_stamp_data", stderr=stderr)
    assert "CRONJOB ERROR" not in stderr.getvalue(), stderr.getvalue()


def _stamp(i):
    return CeramicCache.objects.create(
        address=f"0x{i:040x}",
        provider=f"provider-{i}",
        proof_value=f"proof-{i}",
        stamp={"credentialSubject": {"provider": f"provider-{i}"}},
    )


def test_exports_every_stamp_when_there_is_no_prior_export(uploads, tmp_path):
    for i in range(3):
        _stamp(i)

    _run()

    assert len(uploads) == 1
    upload = uploads[0]
    assert upload["bucket"] == settings.S3_WEEKLY_BACKUP_BUCKET_NAME
    assert upload["key"].startswith("stamps_") and upload["key"].endswith(".jsonl")
    assert sorted(
        line["stamp"]["credentialSubject"]["provider"] for line in upload["lines"]
    ) == ["provider-0", "provider-1", "provider-2"]

    export = StampExports.objects.order_by("-id").first()
    assert export.stamp_total == 3

    # The local dump file is removed after upload.
    assert list(tmp_path.glob("*.jsonl")) == []


def test_only_exports_stamps_updated_since_the_last_export(uploads):
    _stamp(0)
    # StampExports.last_export_ts is auto_now_add, so this watermark is "now",
    # after the stamp above was last updated.
    StampExports.objects.create()
    _stamp(1)

    _run()

    assert len(uploads) == 1
    assert [
        line["stamp"]["credentialSubject"]["provider"] for line in uploads[0]["lines"]
    ] == ["provider-1"]
    assert StampExports.objects.order_by("-id").first().stamp_total == 1
