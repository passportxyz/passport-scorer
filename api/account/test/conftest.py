"""
This module contains pytest fixtures and configuration for the account API tests.

It sets up common test data, mocks, and other utilities used across multiple test files
in the account API test suite.
"""

# pylint: disable=unused-import
import pytest

from registry.weight_models import WeightConfiguration, WeightConfigurationItem
from scorer.settings.gitcoin_passport_weights import GITCOIN_PASSPORT_WEIGHTS
from scorer.test.conftest import (
    access_token,
    scorer_account,
    scorer_community,
    scorer_user,
    weight_config,
)
