import pytest
from django.conf import settings

from v2.schema import V2ScoreResponse


@pytest.fixture
def internal_auth_headers():
    return {"HTTP_AUTHORIZATION": settings.CGRANTS_API_TOKEN}


@pytest.mark.django_db
class TestScoreV2Endpoint:
    def test_score_v2_done_status(
        self, client, scorer_community, scorer_account, internal_auth_headers, mocker
    ):
        # Mock ahandle_scoring to return a successful V2ScoreResponse
        import internal.api as internal_api_module

        address = scorer_account.address
        mock_response = V2ScoreResponse(
            address=address.lower(),
            score=42.0,
            passing_score=True,
            last_score_timestamp=None,
            expiration_timestamp=None,
            threshold=20.0,
            error=None,
            stamps={"github": {"score": "1.0", "dedup": True, "expiration_date": None}},
        )
        mocker.patch.object(
            internal_api_module, "ahandle_scoring", return_value=mock_response
        )
        url = f"/internal/score/v2/{scorer_community.id}/{address}"
        response = client.get(url, **internal_auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["score"] == "42.00000"
        assert data["threshold"] == "20.00000"
        assert data["passing_score"] is True
        assert data["address"].lower() == address.lower()
        assert "stamps" in data

    def test_score_v2_error_status(
        self, client, scorer_community, scorer_account, internal_auth_headers, mocker
    ):
        # Mock ahandle_scoring to return a V2ScoreResponse with error set
        import internal.api as internal_api_module

        address = scorer_account.address
        mock_response = V2ScoreResponse(
            address=address.lower(),
            score=10.0,
            passing_score=False,
            last_score_timestamp=None,
            expiration_timestamp=None,
            threshold=20.0,
            error="Some error occurred",
            stamps={"github": {"score": "1.0", "dedup": True, "expiration_date": None}},
        )
        mocker.patch.object(
            internal_api_module, "ahandle_scoring", return_value=mock_response
        )
        url = f"/internal/score/v2/{scorer_community.id}/{address}"
        response = client.get(url, **internal_auth_headers)
        # Should return an error message about not being able to calculate score
        assert response.status_code == 500
        assert (
            "Failed to calculate score" in response.content.decode()
            or "error" in response.json()
            or "detail" in response.json()
        )
