import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db


def test_rescores_only_the_given_communities(
    mocker,
    scorer_community,
    scorer_community_with_binary_scorer,
):
    recalc_mock = mocker.patch(
        "registry.management.commands.rescore_communities.recalculate_scores"
    )
    update_scorers = mocker.patch(
        "registry.management.commands.recalculate_scores.Command.update_scorers"
    )
    community_ids = [scorer_community.id]

    call_command(
        "rescore_communities",
        "--community-ids",
        ",".join(str(id) for id in community_ids),
    )

    assert recalc_mock.call_count == 1
    communities, batch_size, _ = recalc_mock.call_args[0]
    assert [c.id for c in communities] == community_ids
    assert scorer_community_with_binary_scorer.id not in community_ids
    assert batch_size == 1000
    update_scorers.assert_not_called()
