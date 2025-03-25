# pylint: disable=redefined-outer-name
"""
This module contains unit tests for the server-status api.
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from django.test import Client
from django.utils import timezone

from passport_admin.models import (
    SystemTestResult,
    SystemTestRun,
)
from passport_admin.schema import (
    ServerStatusResponse,
)

pytestmark = pytest.mark.django_db

client = Client()


@pytest.fixture
def test_run_all_pass():
    test_runs = SystemTestRun.objects.create(timestamp=timezone.now())

    SystemTestResult.objects.create(
        run=test_runs,
        name="Test 1",
        category='["category 1"]',
        success=True,
        error=None,
        timestamp=timezone.now(),
    )

    SystemTestResult.objects.create(
        run=test_runs,
        name="Test 2",
        category='["category 1"]',
        success=True,
        error=None,
        timestamp=timezone.now(),
    )
    return test_runs


@pytest.fixture
def test_run_1_failed():
    test_runs = SystemTestRun.objects.create(timestamp=timezone.now())

    SystemTestResult.objects.create(
        run=test_runs,
        name="Test 1",
        category='["category 1"]',
        success=True,
        error=None,
        timestamp=timezone.now(),
    )

    SystemTestResult.objects.create(
        run=test_runs,
        name="Test 2",
        category='["category 1"]',
        success=False,
        error="Something ...",
        timestamp=timezone.now(),
    )
    return test_runs


@pytest.fixture
def test_run_outdated():
    timestamp = timezone.now() - timedelta(
        seconds=settings.SYSTEM_TESTS_MAX_AGE_BEFORE_OUTDATED + 1
    )
    test_runs = SystemTestRun.objects.create(timestamp=timestamp)

    SystemTestResult.objects.create(
        run=test_runs,
        name="Test 1",
        category='["category 1"]',
        success=True,
        error=None,
        timestamp=timestamp,
    )

    SystemTestResult.objects.create(
        run=test_runs,
        name="Test 2",
        category='["category 1"]',
        success=True,
        error=None,
        timestamp=timestamp,
    )
    return test_runs


@pytest.fixture
def test_run_1_failed_but_outdated():
    timestamp = timezone.now() - timedelta(
        seconds=settings.SYSTEM_TESTS_MAX_AGE_BEFORE_OUTDATED + 1
    )
    test_runs = SystemTestRun.objects.create(timestamp=timestamp)

    SystemTestResult.objects.create(
        run=test_runs,
        name="Test 1",
        category='["category 1"]',
        success=True,
        error=None,
        timestamp=timestamp,
    )

    SystemTestResult.objects.create(
        run=test_runs,
        name="Test 2",
        category='["category 1"]',
        success=False,
        error="Something ...",
        timestamp=timestamp,
    )
    return test_runs


mock_cache = MagicMock()
mock_cache.get.return_value = None
mock_cache.set.return_value = None


class TestNotifications:
    def test_server_status_caches_results(self, test_run_all_pass):
        """
        Test that results are written to cache
        """
        mock_test_cache = MagicMock()
        mock_test_cache.get.return_value = None
        mock_test_cache.set.return_value = None

        with patch("passport_admin.api.cache", mock_test_cache):
            response = client.get(
                "/passport-admin/server-status",
            )

            mock_test_cache.set.assert_called_with(
                "server_status",
                ServerStatusResponse(
                    timestamp=test_run_all_pass.timestamp.isoformat(),
                    success=2,
                    failed=0,
                    total=2,
                    status=None,
                    age=None,
                ).model_dump_json(),
                180,
            )

    def test_server_status_loads_caches_results(self, test_run_all_pass):
        """
        Test that results from cache are loaded when available and returned
        """
        mock_test_cache = MagicMock()
        mock_test_cache.get.return_value = ServerStatusResponse(
            timestamp=test_run_all_pass.timestamp.isoformat(),
            success=36,
            failed=4,
            total=40,
            status=None,
            age=None,
        ).model_dump_json()
        mock_test_cache.set.return_value = None

        with patch("passport_admin.api.cache", mock_test_cache):
            response = client.get(
                "/passport-admin/server-status",
            )

            response_json = response.json()
            age = response_json.pop("age")

            # Check the aproximate age
            assert (
                age - (timezone.now() - test_run_all_pass.timestamp).total_seconds()
                <= 2
            )

            # Verify the cached values are returned
            assert response_json == {
                "failed": 4,
                "status": "unhealthy",
                "success": 36,
                "timestamp": test_run_all_pass.timestamp.isoformat(),
                "total": 40,
            }

    def test_server_status_all_pass(self, test_run_all_pass):
        with patch("passport_admin.api.cache", mock_cache):
            response = client.get(
                "/passport-admin/server-status",
            )

            response_json = response.json()
            age = response_json.pop("age")

            # Check the aproximate age
            assert (
                age - (timezone.now() - test_run_all_pass.timestamp).total_seconds()
                <= 2
            )
            assert response_json == {
                "failed": 0,
                "status": "healthy",
                "success": 2,
                "timestamp": test_run_all_pass.timestamp.isoformat(),
                "total": 2,
            }

    def test_server_status_1_failed(self, test_run_1_failed):
        with patch("passport_admin.api.cache", mock_cache):
            response = client.get(
                "/passport-admin/server-status",
            )

            response_json = response.json()
            age = response_json.pop("age")

            # Check the aproximate age
            assert (
                age - (timezone.now() - test_run_1_failed.timestamp).total_seconds()
                <= 2
            )
            assert response_json == {
                "failed": 1,
                "status": "unhealthy",
                "success": 1,
                "timestamp": test_run_1_failed.timestamp.isoformat(),
                "total": 2,
            }

    def test_server_status_all_pass_but_outdated(self, test_run_outdated):
        with patch("passport_admin.api.cache", mock_cache):
            response = client.get(
                "/passport-admin/server-status",
            )

            response_json = response.json()
            age = response_json.pop("age")

            # Check the aproximate age
            assert (
                age - (timezone.now() - test_run_outdated.timestamp).total_seconds()
                <= 2
            )
            assert response_json == {
                "failed": 0,
                "status": "outdated",
                "success": 2,
                "timestamp": test_run_outdated.timestamp.isoformat(),
                "total": 2,
            }

    def test_server_status_failed_but_outdated(self, test_run_1_failed_but_outdated):
        with patch("passport_admin.api.cache", mock_cache):
            response = client.get(
                "/passport-admin/server-status",
            )

            response_json = response.json()
            age = response_json.pop("age")

            # Check the aproximate age
            assert (
                age
                - (
                    timezone.now() - test_run_1_failed_but_outdated.timestamp
                ).total_seconds()
                <= 2
            )
            assert response_json == {
                "failed": 1,
                "status": "outdated",
                "success": 1,
                "timestamp": test_run_1_failed_but_outdated.timestamp.isoformat(),
                "total": 2,
            }
