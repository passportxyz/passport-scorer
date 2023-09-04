import datetime
import random
from datetime import datetime as dt

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client
from registry.models import Passport, Score
from web3 import Web3

User = get_user_model()
web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()
my_mnemonic = settings.TEST_MNEMONIC

pytestmark = pytest.mark.django_db


@pytest.fixture
def paginated_scores(scorer_passport, passport_holder_addresses, scorer_community):
    scores = []
    i = 0
    for holder in passport_holder_addresses:
        passport = Passport.objects.create(
            address=holder["address"],
            community=scorer_community,
        )

        score = Score.objects.create(
            passport=passport,
            score="1",
            last_score_timestamp=datetime.datetime.now()
            + datetime.timedelta(days=i + 1),
        )

        scores.append(score)
        i += 1
    return scores


class TestPassportGetScores:
    def test_get_scores_returns_first_page_scores(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        limit = 2

        client = Client()
        response = client.get(
            f"/registry/v2/score/{scorer_community.id}?limit={limit}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        response_data = response.json()

        assert response.status_code == 200
        assert response_data["prev"] == None

        next_page = client.get(
            response_data["next"],
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        assert next_page.status_code == 200

        for i in range(limit):
            assert (
                response_data["items"][i]["address"]
                == passport_holder_addresses[i]["address"].lower()
            )

    def test_get_scores_returns_second_page_scores(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        limit = 2

        client = Client()
        page_one_response = client.get(
            f"/registry/v2/score/{scorer_community.id}?limit={limit}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        page_one_data = page_one_response.json()

        assert page_one_response.status_code == 200

        page_two_response = client.get(
            page_one_data["next"],
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        page_two_data = page_two_response.json()

        assert page_two_response.status_code == 200

        page_two_prev = client.get(
            page_two_data["prev"],
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        assert page_two_prev.status_code == 200
        assert page_two_prev.json() == page_one_data

        for i in range(limit):
            assert (
                page_two_data["items"][i]["address"]
                == passport_holder_addresses[i + limit]["address"].lower()
            )

    def test_get_scores_filter_by_last_score_timestamp__gte(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        scores = list(Score.objects.all())
        middle = len(scores) // 2
        older_scores = scores[:middle]
        newer_scores = scores[middle:]
        now = datetime.datetime.now()
        past_time_stamp = now - datetime.timedelta(days=1)
        future_time_stamp = now + datetime.timedelta(days=1)

        # Make sure we have sufficient data in both queries
        assert len(newer_scores) >= 2
        assert len(older_scores) >= 2

        for score in older_scores:
            score.last_score_timestamp = past_time_stamp
            score.save()

        # The first score will have a last_score_timestamp equal to the value we filter by
        for idx, score in enumerate(newer_scores):
            if idx == 0:
                score.last_score_timestamp = now
            else:
                score.last_score_timestamp = future_time_stamp
            score.save()

        # Check the query when the filtered timestamp equals a score last_score_timestamp
        client = Client()
        response = client.get(
            f"/registry/score/{scorer_community.id}?last_score_timestamp__gte={now.isoformat()}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        assert response.status_code == 200
        assert len(response.json()["items"]) == len(newer_scores)

        # Check the query when the filtered timestamp does not equal a score last_score_timestamp
        response = client.get(
            f"/registry/score/{scorer_community.id}?last_score_timestamp__gte={(now - datetime.timedelta(milliseconds=1)).isoformat()}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        assert response.status_code == 200
        assert len(response.json()["items"]) == len(newer_scores)

    def test_get_scores_filter_by_last_score_timestamp__gt(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        scores = list(Score.objects.all())
        middle = len(scores) // 2
        older_scores = scores[:middle]
        newer_scores = scores[middle:]
        now = datetime.datetime.now()
        past_time_stamp = now - datetime.timedelta(days=1)
        future_time_stamp = now + datetime.timedelta(days=1)

        # Make sure we have sufficient data in both queries
        assert len(newer_scores) >= 2
        assert len(older_scores) >= 2

        for score in older_scores:
            score.last_score_timestamp = past_time_stamp
            score.save()

        # The first score will have a last_score_timestamp equal to the value we filter by
        for idx, score in enumerate(newer_scores):
            if idx == 0:
                score.last_score_timestamp = now
            else:
                score.last_score_timestamp = future_time_stamp
            score.save()

        # Check the query when the filtered timestamp equals a score last_score_timestamp
        client = Client()
        response = client.get(
            f"/registry/score/{scorer_community.id}?last_score_timestamp__gt={now.isoformat()}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        assert response.status_code == 200
        assert len(response.json()["items"]) == len(newer_scores) - 1

        # Check the query when the filtered timestamp does not equal a score last_score_timestamp
        response = client.get(
            f"/registry/score/{scorer_community.id}?last_score_timestamp__gt={(now - datetime.timedelta(milliseconds=1)).isoformat()}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        assert response.status_code == 200
        assert len(response.json()["items"]) == len(newer_scores)

    def test_get_scores_with_shuffled_ids(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        limit = 6
        scores = list(Score.objects.all())
        random.shuffle(scores)

        client = Client()
        response = client.get(
            f"/registry/v2/score/{scorer_community.id}?limit={limit}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        response_data = response.json()

        assert response.status_code == 200

        for score, item in zip(list(Score.objects.all()), response_data["items"]):
            dt_res_score = item["last_score_timestamp"]
            dt_res_score_object = dt.fromisoformat(dt_res_score)
            dt_res_score_object_str_space = dt_res_score_object.strftime(
                "%Y-%m-%d %H:%M:%S.%f%z"
            )
            dt_last_score_string = score.last_score_timestamp.strftime(
                "%Y-%m-%d %H:%M:%S.%f%z"
            )
            assert dt_last_score_string == dt_res_score_object_str_space

    def test_last_score_timestamp(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        limit = 10
        scores = list(Score.objects.all())

        client = Client()
        response = client.get(
            f"/registry/v2/score/{scorer_community.id}?limit={limit}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        response_data = response.json()

        last_score = scores[len(scores) - 1]
        last_response_score = response_data["items"][len(response_data["items"]) - 1]

        dt_res_score = last_response_score["last_score_timestamp"]
        dt_res_score_object = dt.fromisoformat(dt_res_score)
        dt_res_score_object_str_space = dt_res_score_object.strftime(
            "%Y-%m-%d %H:%M:%S.%f%z"
        )
        dt_last_score_string = last_score.last_score_timestamp.strftime(
            "%Y-%m-%d %H:%M:%S.%f%z"
        )

        assert response.status_code == 200
        assert dt_last_score_string == dt_res_score_object_str_space

    def test_correct_ordering(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        limit = 10

        def to_datetime(string_timestamp):
            return dt.fromisoformat(string_timestamp)

        client = Client()
        response = client.get(
            f"/registry/v2/score/{scorer_community.id}?limit={limit}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        response_data = response.json()

        assert response.status_code == 200

        is_sorted = all(
            to_datetime(response_data["items"][i]["last_score_timestamp"])
            <= to_datetime(response_data["items"][i + 1]["last_score_timestamp"])
            for i in range(len(response_data) - 1)
        )

        assert is_sorted, "The scores are not in order"
