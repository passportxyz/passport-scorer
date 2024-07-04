import re
from unittest import mock

import pytest
from ceramic_cache.models import CeramicCache, CeramicCacheLegacy
from django.conf import settings
from django.core.management import call_command
from passport_admin.models import DismissedBanners, PassportBanner

from registry.models import Event, HashScorerLink, Passport, Score, Stamp
from registry.utils import get_utc_time

pytestmark = pytest.mark.django_db

current_weights = settings.GITCOIN_PASSPORT_WEIGHTS


@pytest.fixture(name="user_data")
def user_data(passport_holder_addresses, scorer_community_with_binary_scorer):
    address = passport_holder_addresses[0]["address"]
    passport = Passport.objects.create(
        address=address,
        community=scorer_community_with_binary_scorer,
    )
    Stamp.objects.create(
        passport=passport,
        provider="FirstEthTxnProvider",
        hash="0x1234",
        credential={
            "expirationDate": "2022-01-01T00:00:00Z",
        },
    )
    Score.objects.create(
        passport=passport,
        score=1,
        status=Score.Status.DONE,
        last_score_timestamp=get_utc_time(),
        error=None,
        stamp_scores=[],
        evidence={
            "rawScore": 10,
            "type": "binary",
            "success": True,
            "threshold": 5,
        },
    )
    CeramicCache.objects.create(
        address=address, provider="Google", type=CeramicCache.StampType.V1
    )
    CeramicCacheLegacy.objects.create(address=address, provider="Google")
    # No need for an event, one will be created automatically when the score is saved
    # Event.objects.create(
    #     action=Event.Action.TRUSTALAB_SCORE,
    #     address=address,
    #     data={"some": "data"},
    # )
    HashScorerLink.objects.create(
        community=scorer_community_with_binary_scorer,
        hash="hash1",
        address=address,
        expires_at="2099-01-02 00:00:00+00:00",
    )

    banner = PassportBanner.objects.create(content="test", link="test")
    DismissedBanners.objects.create(address=address, banner=banner)


def test_delete_user_data_dry_run(passport_holder_addresses, user_data, capsys):
    """Test the delete_user_data command in dry_run mode"""

    args = []
    opts = {"eth_address": passport_holder_addresses[0]["address"], "exec": False}

    call_command("delete_user_data", *args, **opts)

    # List of phrases that lines should end with
    end_phrases = ["would to be deleted"]
    end_pattern = "|".join(re.escape(phrase) for phrase in end_phrases)

    captured = capsys.readouterr()
    print("captured.out", captured.out)

    objects_to_be_deleted = [
        "1 CeramicCache ",
        "1 CeramicCacheLegacy ",
        "1 Stamp ",
        "1 Score ",
        "1 Passport ",
        "1 Event ",
        "1 HashScorerLink ",
        "1 DismissedBanners ",
    ]
    objects_to_be_deleted = [re.escape(word) for word in objects_to_be_deleted]

    for start_word in objects_to_be_deleted:
        match = re.search(rf"^{start_word}.*{end_pattern}$", captured.out, re.MULTILINE)
        print(match)

    # Construct the regular expression
    start_pattern = "|".join(objects_to_be_deleted)
    regex_pattern = rf"^(?!({start_pattern})).*({end_pattern})$"

    # Find all matching lines
    unexpected_objects_to_delete = [
        match.group(0)
        for match in re.finditer(regex_pattern, captured.out, re.MULTILINE)
    ]

    assert (
        unexpected_objects_to_delete == []
    ), " apparently more objects are checked for deletion than we expect ..."

    # Check that passport objects have NOT been deleted
    assert Passport.objects.all().count() == 1
    assert Stamp.objects.all().count() == 1
    assert Score.objects.all().count() == 1
    assert CeramicCache.objects.all().count() == 1
    assert CeramicCacheLegacy.objects.all().count() == 1
    assert Event.objects.all().count() == 1
    assert HashScorerLink.objects.all().count() == 1
    assert DismissedBanners.objects.all().count() == 1


def test_delete_user_data_exec(passport_holder_addresses, user_data, capsys):
    """Test the delete_user_data command in exec mode"""

    def input_response(message):
        return "yes\n"

    with mock.patch(
        "registry.management.commands.delete_user_data.input",
        side_effect=input_response,
    ):
        args = []
        opts = {"eth_address": passport_holder_addresses[0]["address"], "exec": True}

        call_command("delete_user_data", *args, **opts)

        # List of phrases that lines should end with
        end_phrases = ["would to be deleted"]
        end_pattern = "|".join(re.escape(phrase) for phrase in end_phrases)

        captured = capsys.readouterr()

        print("captured.out", captured.out)
        objects_to_be_deleted = [
            "1 CeramicCache ",
            "1 CeramicCacheLegacy ",
            "1 Stamp ",
            "1 Score ",
            "1 Passport ",
            "1 Event ",
            "1 HashScorerLink ",
            "1 DismissedBanners ",
        ]
        objects_to_be_deleted = [re.escape(word) for word in objects_to_be_deleted]

        for start_word in objects_to_be_deleted:
            match = re.search(
                rf"^{start_word}.*{end_pattern}$", captured.out, re.MULTILINE
            )
            print(match)

        # Construct the regular expression
        start_pattern = "|".join(objects_to_be_deleted)
        regex_pattern = rf"^(?!({start_pattern})).*({end_pattern})$"

        # Find all matching lines
        unexpected_objects_to_delete = [
            match.group(0)
            for match in re.finditer(regex_pattern, captured.out, re.MULTILINE)
        ]

        assert (
            unexpected_objects_to_delete == []
        ), " apparently more objects are deleted than we expect ..."

        # Check that passport objects have indeed been deleted
        assert Passport.objects.all().count() == 0
        assert Stamp.objects.all().count() == 0
        assert Score.objects.all().count() == 0
        assert CeramicCache.objects.all().count() == 0
        assert CeramicCacheLegacy.objects.all().count() == 0
        assert Event.objects.all().count() == 0
        assert HashScorerLink.objects.all().count() == 0
        assert DismissedBanners.objects.all().count() == 0
