import pytest
from account.deduplication import Rules
from account.models import Community
from registry.management.commands.propagate_weights_and_rescore import Command

pytestmark = pytest.mark.django_db
from unittest.mock import patch

from django.core.management import call_command


@patch("registry.tasks.score_registry_passport.delay")
def test_update_scores(
    mock_delay_score, scorer_community, scorer_passport, scorer_score, capsys
):
    call_command("propagate_weights_and_rescore")

    assert mock_delay_score.called is True

    captured = capsys.readouterr()
    assert "Updated scorers: 1" in captured.out
    assert "Updating scores: 1" in captured.out


def test_update_only_scorers(scorer_community, scorer_passport, scorer_score, capsys):
    call_command("propagate_weights_and_rescore", update_all_scores=False)

    captured = capsys.readouterr()
    assert "Updated scorers: 1" in captured.out
    assert "Updating scores: 1" not in captured.out


def test_fifo_not_included(scorer_account, scorer_community):
    assert Community.objects.get(id=scorer_community.pk).rule == Rules.LIFO.value

    # create fifo community
    Community.objects.create(
        name="FIFO Community", rule=Rules.FIFO.value, account=scorer_account
    )
    fifo_community = Community.objects.get(name="FIFO Community")
    assert fifo_community.rule == Rules.FIFO.value

    communities_to_adjust = Command.get_eligible_communities()

    assert scorer_community in communities_to_adjust
    assert fifo_community not in communities_to_adjust
