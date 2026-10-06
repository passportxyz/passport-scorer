from scorer.cloud_run import METADATA_TOKEN_URL, run_job


def test_run_job_overrides_args_with_metadata_token(mocker):
    get = mocker.patch("scorer.cloud_run.requests.get")
    get.return_value.json.return_value = {"access_token": "token-1"}
    post = mocker.patch("scorer.cloud_run.requests.post")
    post.return_value.json.return_value = {"name": "projects/p/operations/op-1"}

    operation = run_job("projects/p/locations/l/jobs/j", ["--community-ids", "1,2"])

    assert operation == "projects/p/operations/op-1"
    assert get.call_args[0][0] == METADATA_TOKEN_URL
    assert get.call_args.kwargs["headers"] == {"Metadata-Flavor": "Google"}
    assert (
        post.call_args[0][0]
        == "https://run.googleapis.com/v2/projects/p/locations/l/jobs/j:run"
    )
    assert post.call_args.kwargs["headers"] == {"Authorization": "Bearer token-1"}
    assert post.call_args.kwargs["json"] == {
        "overrides": {"containerOverrides": [{"args": ["--community-ids", "1,2"]}]}
    }
