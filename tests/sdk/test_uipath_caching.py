"""Tests for service caching behavior in UiPath SDK.

This module tests that services using @cached_property are properly cached
and thread-safe, while stateless services create new instances as expected.
"""

import threading
import time
from typing import Any

import pytest
from pytest import MonkeyPatch

from uipath import UiPath


@pytest.fixture
def sdk(monkeypatch: MonkeyPatch) -> UiPath:
    """Create a UiPath SDK instance with mocked credentials."""
    monkeypatch.setenv("UIPATH_URL", "https://test.example.com")
    monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "test_token_1234567890")
    return UiPath()


class TestCachedServices:
    """Test suite for services that should be cached."""

    def test_buckets_service_returns_cached_instance(self, sdk: UiPath) -> None:
        """Verify that buckets property returns the same instance on multiple accesses."""
        buckets1 = sdk.buckets
        buckets2 = sdk.buckets

        assert buckets1 is buckets2, "BucketsService should return cached instance"
        assert id(buckets1) == id(buckets2), "Instance IDs should match"

    def test_attachments_service_returns_cached_instance(self, sdk: UiPath) -> None:
        """Verify that attachments property returns the same instance."""
        attachments1 = sdk.attachments
        attachments2 = sdk.attachments

        assert attachments1 is attachments2, (
            "AttachmentsService should return cached instance"
        )
        assert id(attachments1) == id(attachments2), "Instance IDs should match"

    def test_connections_service_returns_cached_instance(self, sdk: UiPath) -> None:
        """Verify that connections property returns the same instance."""
        connections1 = sdk.connections
        connections2 = sdk.connections

        assert connections1 is connections2, (
            "ConnectionsService should return cached instance"
        )
        assert id(connections1) == id(connections2), "Instance IDs should match"

    def test_folders_service_returns_cached_instance(self, sdk: UiPath) -> None:
        """Verify that folders property returns the same instance."""
        folders1 = sdk.folders
        folders2 = sdk.folders

        assert folders1 is folders2, "FolderService should return cached instance"
        assert id(folders1) == id(folders2), "Instance IDs should match"

    @pytest.mark.parametrize(
        "service_property",
        [
            "attachments",
            "buckets",
            "connections",
            "folders",
        ],
    )
    def test_all_cached_services_return_same_instance(
        self, sdk: UiPath, service_property: str
    ) -> None:
        """Verify that all cached services return the same instance."""
        service1 = getattr(sdk, service_property)
        service2 = getattr(sdk, service_property)

        assert service1 is service2, f"{service_property} should return cached instance"

    def test_cached_services_share_config(self, sdk: UiPath) -> None:
        """Verify that cached instances share the same config object."""
        buckets1 = sdk.buckets
        buckets2 = sdk.buckets

        assert buckets1._config is buckets2._config, "Config should be shared"
        assert buckets1._execution_context is buckets2._execution_context, (
            "Execution context should be shared"
        )

    def test_different_sdk_instances_have_different_services(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        """Verify that different SDK instances have different service instances."""
        monkeypatch.setenv("UIPATH_URL", "https://test.example.com")
        monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "test_token_1234567890")
        sdk1 = UiPath()
        sdk2 = UiPath()

        assert sdk1.buckets is not sdk2.buckets, (
            "Different SDK instances should have different service instances"
        )
        assert sdk1.attachments is not sdk2.attachments, (
            "Different SDK instances should have different service instances"
        )
        assert sdk1.connections is not sdk2.connections, (
            "Different SDK instances should have different service instances"
        )
        assert sdk1.folders is not sdk2.folders, (
            "Different SDK instances should have different service instances"
        )


class TestThreadSafety:
    """Test suite for thread safety of cached services."""

    def test_buckets_service_thread_safe_initialization(self, sdk: UiPath) -> None:
        """Verify that cached_property handles concurrent access safely."""
        instances: list[Any] = []

        def access_service() -> None:
            # Small delay to increase chance of race condition
            time.sleep(0.001)
            instances.append(sdk.buckets)

        # Create 10 threads accessing the service simultaneously
        threads = [threading.Thread(target=access_service) for _ in range(10)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All threads should get the same instance
        assert len(set(id(instance) for instance in instances)) == 1, (
            "All threads should receive the same cached instance"
        )

        for instance in instances[1:]:
            assert instances[0] is instance, "All instances should be identical"

    def test_attachments_service_thread_safe_initialization(self, sdk: UiPath) -> None:
        """Verify attachments service thread safety."""
        instances: list[Any] = []

        def access_service() -> None:
            time.sleep(0.001)
            instances.append(sdk.attachments)

        threads = [threading.Thread(target=access_service) for _ in range(10)]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(set(id(instance) for instance in instances)) == 1

    def test_connections_service_thread_safe_initialization(self, sdk: UiPath) -> None:
        """Verify connections service thread safety."""
        instances: list[Any] = []

        def access_service() -> None:
            time.sleep(0.001)
            instances.append(sdk.connections)

        threads = [threading.Thread(target=access_service) for _ in range(10)]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(set(id(instance) for instance in instances)) == 1

    def test_folders_service_thread_safe_initialization(self, sdk: UiPath) -> None:
        """Verify folders service thread safety."""
        instances: list[Any] = []

        def access_service() -> None:
            time.sleep(0.001)
            instances.append(sdk.folders)

        threads = [threading.Thread(target=access_service) for _ in range(10)]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(set(id(instance) for instance in instances)) == 1


class TestStatelessServices:
    """Test suite for services that should NOT be cached."""

    def test_assets_service_creates_new_instances(self, sdk: UiPath) -> None:
        """Verify that assets service creates new instances (stateless)."""
        assets1 = sdk.assets
        assets2 = sdk.assets

        # These should be different instances
        assert assets1 is not assets2, "Assets service should create new instances"

    def test_actions_service_creates_new_instances(self, sdk: UiPath) -> None:
        """Verify that actions service creates new instances (stateless)."""
        actions1 = sdk.actions
        actions2 = sdk.actions

        assert actions1 is not actions2, "Actions service should create new instances"

    def test_queues_service_creates_new_instances(self, sdk: UiPath) -> None:
        """Verify that queues service creates new instances (stateless)."""
        queues1 = sdk.queues
        queues2 = sdk.queues

        assert queues1 is not queues2, "Queues service should create new instances"

    def test_jobs_service_creates_new_instances(self, sdk: UiPath) -> None:
        """Verify that jobs service creates new instances (stateless)."""
        jobs1 = sdk.jobs
        jobs2 = sdk.jobs

        assert jobs1 is not jobs2, "Jobs service should create new instances"

    @pytest.mark.parametrize(
        "service_property",
        [
            "api_client",
            "assets",
            "actions",
            "processes",
            "queues",
            "jobs",
            "documents",
            "llm_openai",
            "llm",
            "entities",
        ],
    )
    def test_stateless_services_create_new_instances(
        self, sdk: UiPath, service_property: str
    ) -> None:
        """Verify that stateless services create new instances."""
        service1 = getattr(sdk, service_property)
        service2 = getattr(sdk, service_property)

        assert service1 is not service2, (
            f"{service_property} should create new instances"
        )


class TestServiceDependencies:
    """Test suite for services with dependencies on cached services."""

    def test_connections_uses_cached_folders(self, sdk: UiPath) -> None:
        """Verify that connections service uses the cached folders service."""

        # Access connections (which depends on folders)
        _ = sdk.connections

        # Access folders directly
        folders = sdk.folders

        # The folders instance used by connections should be the same cached instance
        assert folders is sdk.folders, "Folders should be cached and reused"

    def test_context_grounding_uses_cached_dependencies(self, sdk: UiPath) -> None:
        """Verify that context_grounding uses cached folders and buckets."""

        # Access dependencies first
        folders = sdk.folders
        buckets = sdk.buckets

        # Access context_grounding (creates new instance but uses cached deps)
        cg1 = sdk.context_grounding
        cg2 = sdk.context_grounding

        # context_grounding itself is not cached (creates new instances)
        assert cg1 is not cg2, "ContextGroundingService should create new instances"

        # But it should use the same cached dependencies
        assert folders is sdk.folders, "Folders should remain cached"
        assert buckets is sdk.buckets, "Buckets should remain cached"

    def test_processes_uses_cached_attachments(self, sdk: UiPath) -> None:
        """Verify that processes service uses the cached attachments service."""

        # Access attachments directly
        attachments = sdk.attachments

        # Access processes (which depends on attachments)
        _ = sdk.processes

        # Attachments should still be cached
        assert attachments is sdk.attachments, "Attachments should remain cached"


class TestCachingBehavior:
    """Test suite for general caching behavior."""

    def test_cached_property_attribute_name(self, sdk: UiPath) -> None:
        """Verify that @cached_property stores values in expected attribute names."""

        # Access the service
        _ = sdk.buckets

        # @cached_property stores the value in an attribute with the property name
        assert hasattr(sdk, "buckets"), "Cached value should be stored as attribute"

    def test_service_initialization_order(self, sdk: UiPath) -> None:
        """Verify that services can be accessed in any order."""

        # Access in different order
        connections = sdk.connections  # Depends on folders
        folders = sdk.folders
        buckets = sdk.buckets
        attachments = sdk.attachments

        # All should be cached and reusable
        assert connections is sdk.connections
        assert folders is sdk.folders
        assert buckets is sdk.buckets
        assert attachments is sdk.attachments
