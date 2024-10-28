from unittest.mock import patch

import pytest

from registry.models import serialize_score


@pytest.mark.django_db
class TestSerializeScore:
    def test_successful_serialization(self, scorer_score):
        """Test successful serialization of a score object"""
        # Use the existing scorer_score fixture
        score = scorer_score

        # Serialize the score
        result = serialize_score(score)

        # Verify the structure and content
        assert isinstance(result, dict)
        assert "model" in result
        assert "fields" in result
        assert "error" not in result

        # Verify the model name
        assert (
            result["model"] == "registry.score"
        )  # adjust if your model is named differently

        # Verify key fields are present
        assert "status" in result["fields"]
        assert "passport" in result["fields"]

    @patch("django.core.serializers.serialize")
    def test_serialization_error(self, mock_serialize, scorer_score):
        """Test handling of serialization errors"""
        # Use the existing scorer_score fixture
        score = scorer_score

        # Make serialize throw an exception
        mock_serialize.side_effect = Exception("Serialization failed")

        # Attempt to serialize
        result = serialize_score(score)

        # Verify error handling
        assert result == {"error": "Error serializing score"}
