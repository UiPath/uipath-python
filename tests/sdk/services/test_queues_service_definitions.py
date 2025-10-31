"""Comprehensive tests for QueuesService queue definition operations.

Tests the ACTUAL implemented API signatures for queue definitions:
- list_definitions() with OData filtering and pagination
- retrieve_definition() by name or key
- create_definition() with various parameters
- delete_definition() by name or key
- exists_definition() boolean checks
- Async variants for all operations
"""

from typing import Any, Dict

import pytest
from pytest_httpx import HTTPXMock

from uipath._services.queues_service import QueuesService
from uipath.models.queues import QueueDefinition


@pytest.fixture
def queue_definition_data() -> Dict[str, Any]:
    """Sample queue definition response data."""
    return {
        "Name": "TestQueue",
        "Key": "queue-123-abc",
        "Description": "Test queue for unit tests",
        "MaxNumberOfRetries": 3,
        "AcceptAutomaticallyRetry": True,
        "EnforceUniqueReference": False,
    }


@pytest.fixture
def queue_definitions_list_data(
    queue_definition_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Sample queue definitions list response."""
    return {
        "@odata.context": "https://test.uipath.com/odata/$metadata#QueueDefinitions",
        "@odata.count": 2,
        "value": [
            queue_definition_data,
            {
                "Name": "SecondQueue",
                "Key": "queue-456-def",
                "Description": "Second test queue",
                "MaxNumberOfRetries": 5,
                "AcceptAutomaticallyRetry": False,
                "EnforceUniqueReference": True,
            },
        ],
    }


class TestQueuesServiceListDefinitions:
    """Tests for QueuesService.list_definitions() method."""

    def test_list_definitions_basic(
        self,
        queues_service: QueuesService,
        httpx_mock: HTTPXMock,
        queue_definitions_list_data: Dict[str, Any],
    ) -> None:
        """Test basic queue definitions listing."""
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/QueueDefinitions?%24top=100&%24skip=0",
            json=queue_definitions_list_data,
        )

        definitions = list(queues_service.list_definitions())

        assert len(definitions) == 2
        assert all(isinstance(d, QueueDefinition) for d in definitions)
        assert definitions[0].name == "TestQueue"
        assert definitions[1].name == "SecondQueue"

    def test_list_definitions_with_filter(
        self,
        queues_service: QueuesService,
        httpx_mock: HTTPXMock,
        queue_definition_data: Dict[str, Any],
    ) -> None:
        """Test listing queue definitions with OData filter."""
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/QueueDefinitions?%24filter=Name+eq+%27TestQueue%27&%24top=100&%24skip=0",
            json={"value": [queue_definition_data]},
        )

        definitions = list(
            queues_service.list_definitions(filter="Name eq 'TestQueue'")
        )

        assert len(definitions) == 1
        assert definitions[0].name == "TestQueue"

    def test_list_definitions_with_orderby(
        self,
        queues_service: QueuesService,
        httpx_mock: HTTPXMock,
        queue_definitions_list_data: Dict[str, Any],
    ) -> None:
        """Test listing queue definitions with ordering."""
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/QueueDefinitions?%24orderby=Name+desc&%24top=100&%24skip=0",
            json=queue_definitions_list_data,
        )

        definitions = list(queues_service.list_definitions(orderby="Name desc"))

        assert len(definitions) == 2

    def test_list_definitions_with_pagination(
        self,
        queues_service: QueuesService,
        httpx_mock: HTTPXMock,
        queue_definition_data: Dict[str, Any],
    ) -> None:
        """Test listing queue definitions with pagination."""
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/QueueDefinitions?%24top=10&%24skip=5",
            json={"value": [queue_definition_data]},
        )

        definitions = list(queues_service.list_definitions(top=10, skip=5))

        assert len(definitions) == 1

    def test_list_definitions_auto_pagination(
        self,
        queues_service: QueuesService,
        httpx_mock: HTTPXMock,
        queue_definition_data: Dict[str, Any],
    ) -> None:
        """Test automatic pagination when more results available."""
        # First page
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/QueueDefinitions?%24top=1&%24skip=0",
            json={"value": [queue_definition_data]},
        )
        # Second page (empty)
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/QueueDefinitions?%24top=1&%24skip=1",
            json={"value": []},
        )

        definitions = list(queues_service.list_definitions(top=1))

        assert len(definitions) == 1


class TestQueuesServiceRetrieveDefinition:
    """Tests for QueuesService.retrieve_definition() method."""

    def test_retrieve_definition_by_name(
        self,
        queues_service: QueuesService,
        httpx_mock: HTTPXMock,
        queue_definition_data: Dict[str, Any],
    ) -> None:
        """Test retrieving queue definition by name."""
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/QueueDefinitions?%24filter=Name+eq+%27TestQueue%27&%24top=1",
            json={"value": [queue_definition_data]},
        )

        definition = queues_service.retrieve_definition(name="TestQueue")

        assert isinstance(definition, QueueDefinition)
        assert definition.name == "TestQueue"
        assert definition.key == "queue-123-abc"

    def test_retrieve_definition_by_key(
        self,
        queues_service: QueuesService,
        httpx_mock: HTTPXMock,
        queue_definition_data: Dict[str, Any],
    ) -> None:
        """Test retrieving queue definition by key."""
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/QueueDefinitions?%24filter=Key+eq+%27queue-123-abc%27&%24top=1",
            json={"value": [queue_definition_data]},
        )

        definition = queues_service.retrieve_definition(key="queue-123-abc")

        assert isinstance(definition, QueueDefinition)
        assert definition.name == "TestQueue"
        assert definition.key == "queue-123-abc"

    def test_retrieve_definition_not_found_by_name(
        self,
        queues_service: QueuesService,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test retrieving non-existent queue definition by name raises LookupError."""
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/QueueDefinitions?%24filter=Name+eq+%27NonExistent%27&%24top=1",
            json={"value": []},
        )

        with pytest.raises(
            LookupError,
            match="Queue definition with name 'NonExistent' or key 'None' not found",
        ):
            queues_service.retrieve_definition(name="NonExistent")

    def test_retrieve_definition_not_found_by_key(
        self,
        queues_service: QueuesService,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test retrieving non-existent queue definition by key raises LookupError."""
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/QueueDefinitions?%24filter=Key+eq+%27invalid-key%27&%24top=1",
            json={"value": []},
        )

        with pytest.raises(
            LookupError,
            match="Queue definition with name 'None' or key 'invalid-key' not found",
        ):
            queues_service.retrieve_definition(key="invalid-key")


class TestQueuesServiceCreateDefinition:
    """Tests for QueuesService.create_definition() method."""

    def test_create_definition_basic(
        self,
        queues_service: QueuesService,
        httpx_mock: HTTPXMock,
        queue_definition_data: Dict[str, Any],
    ) -> None:
        """Test creating a queue definition with basic parameters."""
        httpx_mock.add_response(
            method="POST",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/QueueDefinitions",
            json=queue_definition_data,
        )

        definition = queues_service.create_definition(name="TestQueue")

        assert isinstance(definition, QueueDefinition)
        assert definition.name == "TestQueue"

    def test_create_definition_with_description(
        self,
        queues_service: QueuesService,
        httpx_mock: HTTPXMock,
        queue_definition_data: Dict[str, Any],
    ) -> None:
        """Test creating a queue definition with description."""
        httpx_mock.add_response(
            method="POST",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/QueueDefinitions",
            json=queue_definition_data,
        )

        definition = queues_service.create_definition(
            name="TestQueue", description="Test queue for unit tests"
        )

        assert definition.description == "Test queue for unit tests"

    def test_create_definition_with_retry_settings(
        self,
        queues_service: QueuesService,
        httpx_mock: HTTPXMock,
        queue_definition_data: Dict[str, Any],
    ) -> None:
        """Test creating a queue definition with retry settings."""
        httpx_mock.add_response(
            method="POST",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/QueueDefinitions",
            json=queue_definition_data,
        )

        definition = queues_service.create_definition(
            name="TestQueue",
            max_number_of_retries=3,
            accept_automatically_retry=True,
        )

        assert definition.max_number_of_retries == 3
        assert definition.accept_automatically_retry is True


class TestQueuesServiceDeleteDefinition:
    """Tests for QueuesService.delete_definition() method."""

    def test_delete_definition_by_name(
        self,
        queues_service: QueuesService,
        httpx_mock: HTTPXMock,
        queue_definition_data: Dict[str, Any],
    ) -> None:
        """Test deleting a queue definition by name."""
        # First, retrieve to get the ID
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/QueueDefinitions?%24filter=Name+eq+%27TestQueue%27&%24top=1",
            json={"value": [{"Id": 123, **queue_definition_data}]},
        )
        # Then delete by ID
        httpx_mock.add_response(
            method="DELETE",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/QueueDefinitions(123)",
            status_code=204,
        )

        queues_service.delete_definition(name="TestQueue")

        # Verify both requests were made
        requests = httpx_mock.get_requests()
        assert len(requests) == 2
        assert requests[0].method == "GET"
        assert requests[1].method == "DELETE"


class TestQueuesServiceExistsDefinition:
    """Tests for QueuesService.exists_definition() method."""

    def test_exists_definition_by_name_true(
        self,
        queues_service: QueuesService,
        httpx_mock: HTTPXMock,
        queue_definition_data: Dict[str, Any],
    ) -> None:
        """Test exists check returns True when queue definition exists."""
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/QueueDefinitions?%24filter=Name+eq+%27TestQueue%27&%24top=1",
            json={"value": [queue_definition_data]},
        )

        exists = queues_service.exists_definition(name="TestQueue")

        assert exists is True

    def test_exists_definition_by_name_false(
        self,
        queues_service: QueuesService,
        httpx_mock: HTTPXMock,
    ) -> None:
        """Test exists check returns False when queue definition doesn't exist."""
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/QueueDefinitions?%24filter=Name+eq+%27NonExistent%27&%24top=1",
            json={"value": []},
        )

        exists = queues_service.exists_definition(name="NonExistent")

        assert exists is False


class TestQueuesServiceAsyncDefinitions:
    """Tests for async variants of queue definition operations."""

    @pytest.mark.asyncio
    async def test_list_definitions_async(
        self,
        queues_service: QueuesService,
        httpx_mock: HTTPXMock,
        queue_definitions_list_data: Dict[str, Any],
    ) -> None:
        """Test async queue definitions listing."""
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/QueueDefinitions?%24top=100&%24skip=0",
            json=queue_definitions_list_data,
        )

        definitions = []
        async for definition in queues_service.list_definitions_async():
            definitions.append(definition)

        assert len(definitions) == 2
        assert all(isinstance(d, QueueDefinition) for d in definitions)

    @pytest.mark.asyncio
    async def test_retrieve_definition_async(
        self,
        queues_service: QueuesService,
        httpx_mock: HTTPXMock,
        queue_definition_data: Dict[str, Any],
    ) -> None:
        """Test async queue definition retrieval."""
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/QueueDefinitions?%24filter=Name+eq+%27TestQueue%27&%24top=1",
            json={"value": [queue_definition_data]},
        )

        definition = await queues_service.retrieve_definition_async(name="TestQueue")

        assert isinstance(definition, QueueDefinition)
        assert definition.name == "TestQueue"

    @pytest.mark.asyncio
    async def test_create_definition_async(
        self,
        queues_service: QueuesService,
        httpx_mock: HTTPXMock,
        queue_definition_data: Dict[str, Any],
    ) -> None:
        """Test async queue definition creation."""
        httpx_mock.add_response(
            method="POST",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/QueueDefinitions",
            json=queue_definition_data,
        )

        definition = await queues_service.create_definition_async(name="TestQueue")

        assert isinstance(definition, QueueDefinition)
        assert definition.name == "TestQueue"

    @pytest.mark.asyncio
    async def test_exists_definition_async(
        self,
        queues_service: QueuesService,
        httpx_mock: HTTPXMock,
        queue_definition_data: Dict[str, Any],
    ) -> None:
        """Test async queue definition existence check."""
        httpx_mock.add_response(
            method="GET",
            url="https://test.uipath.com/org/tenant/orchestrator_/odata/QueueDefinitions?%24filter=Name+eq+%27TestQueue%27&%24top=1",
            json={"value": [queue_definition_data]},
        )

        exists = await queues_service.exists_definition_async(name="TestQueue")

        assert exists is True
