"""Unit tests for CRUDServiceProtocol.

Tests cover:
- Protocol compliance checking
- Structural subtyping (duck typing)
- validate_service_protocol() function
- Optional methods detection
- Protocol documentation
"""

import pytest

from uipath._cli._utils._service_protocol import (
    CRUDServiceProtocol,
    has_exists_method,
    validate_service_protocol,
)

__all__ = [
    "TestCRUDServiceProtocol",
    "TestValidateServiceProtocol",
    "TestProtocolDuckTyping",
    "TestProtocolRealWorldExamples",
]


class TestCRUDServiceProtocol:
    """Test CRUDServiceProtocol structural typing."""

    def test_complete_service_implements_protocol(self):
        """Test that a complete service implements the protocol."""

        class CompleteService:
            """Service implementing all CRUD methods."""

            def list(self, *, folder_path=None, folder_key=None, **kwargs):
                return iter([])

            def retrieve(self, name, *, folder_path=None, folder_key=None, **kwargs):
                return {"name": name}

            def create(self, name, *, folder_path=None, folder_key=None, **kwargs):
                return {"name": name}

            def delete(self, name, *, folder_path=None, folder_key=None, **kwargs):
                pass

            def exists(self, name, *, folder_path=None, folder_key=None, **kwargs):
                return True

        service = CompleteService()

        # isinstance check should work with runtime_checkable Protocol
        assert isinstance(service, CRUDServiceProtocol)

    def test_service_without_exists_still_valid(self):
        """Test that service without exists() is still valid (optional method)."""

        class ServiceWithoutExists:
            """Service without optional exists() method."""

            def list(self, *, folder_path=None, folder_key=None, **kwargs):
                return iter([])

            def retrieve(self, name, *, folder_path=None, folder_key=None, **kwargs):
                return {"name": name}

            def create(self, name, *, folder_path=None, folder_key=None, **kwargs):
                return {"name": name}

            def delete(self, name, *, folder_path=None, folder_key=None, **kwargs):
                pass

            # No exists() method

        service = ServiceWithoutExists()

        # Should still be considered valid since exists() is optional
        assert isinstance(service, CRUDServiceProtocol)

    def test_incomplete_service_not_protocol(self):
        """Test that incomplete service doesn't match protocol."""

        class IncompleteService:
            """Service missing required methods."""

            def list(self, *, folder_path=None, folder_key=None, **kwargs):
                return iter([])

            # Missing retrieve, create, delete

        service = IncompleteService()

        # Should not be considered valid
        assert not isinstance(service, CRUDServiceProtocol)


class TestValidateServiceProtocol:
    """Test validate_service_protocol() function."""

    def test_validate_complete_service(self):
        """Test validation of complete service."""

        class CompleteService:
            def list(self, *, folder_path=None, folder_key=None, **kwargs):
                return iter([])

            def retrieve(self, name, *, folder_path=None, folder_key=None, **kwargs):
                return {}

            def create(self, name, *, folder_path=None, folder_key=None, **kwargs):
                return {}

            def delete(self, name, *, folder_path=None, folder_key=None, **kwargs):
                pass

            def exists(self, name, *, folder_path=None, folder_key=None, **kwargs):
                return True

        service = CompleteService()

        # Should not raise for valid service
        validate_service_protocol(service, "complete")

        # Check optional exists method separately
        assert has_exists_method(service)

    def test_validate_service_without_exists(self):
        """Test validation of service without optional exists()."""

        class ServiceWithoutExists:
            def list(self, *, folder_path=None, folder_key=None, **kwargs):
                return iter([])

            def retrieve(self, name, *, folder_path=None, folder_key=None, **kwargs):
                return {}

            def create(self, name, *, folder_path=None, folder_key=None, **kwargs):
                return {}

            def delete(self, name, *, folder_path=None, folder_key=None, **kwargs):
                pass

        service = ServiceWithoutExists()

        # Should not raise, exists is optional
        validate_service_protocol(service, "test")

        # Verify exists method is not present
        assert not has_exists_method(service)

    def test_validate_incomplete_service_raises(self):
        """Test that incomplete service raises TypeError."""

        class IncompleteService:
            def list(self, *, folder_path=None, folder_key=None, **kwargs):
                return iter([])

            # Missing retrieve, create, delete

        service = IncompleteService()

        with pytest.raises(TypeError) as exc_info:
            validate_service_protocol(service, "incomplete")

        error_msg = str(exc_info.value)
        assert "incomplete" in error_msg
        assert "must implement" in error_msg
        assert "retrieve" in error_msg
        assert "create" in error_msg
        assert "delete" in error_msg

    def test_validate_service_missing_single_method(self):
        """Test validation when only one method is missing."""

        class ServiceMissingCreate:
            def list(self, *, folder_path=None, folder_key=None, **kwargs):
                return iter([])

            def retrieve(self, name, *, folder_path=None, folder_key=None, **kwargs):
                return {}

            # Missing create
            def delete(self, name, *, folder_path=None, folder_key=None, **kwargs):
                pass

        service = ServiceMissingCreate()

        with pytest.raises(TypeError) as exc_info:
            validate_service_protocol(service, "test")

        error_msg = str(exc_info.value)
        assert "create" in error_msg

    def test_validate_service_with_non_callable_attribute(self):
        """Test that non-callable attributes don't count as methods."""

        class ServiceWithNonCallable:
            list = "not_a_method"  # String instead of method

            def retrieve(self, name, *, folder_path=None, folder_key=None, **kwargs):
                return {}

            def create(self, name, *, folder_path=None, folder_key=None, **kwargs):
                return {}

            def delete(self, name, *, folder_path=None, folder_key=None, **kwargs):
                pass

        service = ServiceWithNonCallable()

        # Should raise because list is not callable
        with pytest.raises(TypeError) as exc_info:
            validate_service_protocol(service, "test")

        error_msg = str(exc_info.value)
        assert "list" in error_msg


class TestProtocolDuckTyping:
    """Test duck typing behavior of the protocol."""

    def test_service_without_inheritance_works(self):
        """Test that services don't need to inherit from protocol."""

        # No explicit inheritance from CRUDServiceProtocol
        class IndependentService:
            def list(self, *, folder_path=None, folder_key=None, **kwargs):
                return iter([{"id": 1}, {"id": 2}])

            def retrieve(self, name, *, folder_path=None, folder_key=None, **kwargs):
                return {"name": name, "id": 1}

            def create(self, name, *, folder_path=None, folder_key=None, **kwargs):
                return {"name": name, "created": True}

            def delete(self, name, *, folder_path=None, folder_key=None, **kwargs):
                return None

        service = IndependentService()

        # Should work with structural typing
        assert isinstance(service, CRUDServiceProtocol)

        # Can be used as CRUDServiceProtocol type
        def use_service(s: CRUDServiceProtocol):
            return list(s.list())

        result = use_service(service)
        assert len(result) == 2

    def test_different_signature_compatible(self):
        """Test that compatible signatures work (extra params OK)."""

        class ExtendedService:
            def list(
                self, *, folder_path=None, folder_key=None, extra_filter=None, **kwargs
            ):
                # Extra parameter is OK
                return iter([])

            def retrieve(
                self,
                name,
                *,
                folder_path=None,
                folder_key=None,
                include_meta=False,
                **kwargs,
            ):
                # Extra parameter is OK
                return {}

            def create(self, name, *, folder_path=None, folder_key=None, **kwargs):
                return {}

            def delete(self, name, *, folder_path=None, folder_key=None, **kwargs):
                pass

        service = ExtendedService()

        # Should still match protocol
        assert isinstance(service, CRUDServiceProtocol)


class TestProtocolRealWorldExamples:
    """Test protocol with real-world service examples."""

    def test_buckets_service_like(self):
        """Test service similar to actual BucketsService."""

        class BucketsService:
            def list(self, *, folder_path=None, folder_key=None):
                return iter(
                    [
                        {"name": "bucket1", "description": "Test"},
                        {"name": "bucket2", "description": "Test"},
                    ]
                )

            def retrieve(self, name, *, folder_path=None, folder_key=None):
                return {"name": name, "description": "Retrieved bucket"}

            def create(
                self, name, *, description=None, folder_path=None, folder_key=None
            ):
                return {"name": name, "description": description}

            def delete(self, name, *, folder_path=None, folder_key=None):
                pass

            def exists(self, name, *, folder_path=None, folder_key=None):
                return True

        service = BucketsService()

        # Should match protocol
        assert isinstance(service, CRUDServiceProtocol)

        # Validation should pass
        validate_service_protocol(service, "buckets")

        # Check optional exists method separately
        assert has_exists_method(service)

    def test_assets_service_like(self):
        """Test service similar to actual AssetsService."""

        class AssetsService:
            def list(self, *, folder_path=None, folder_key=None):
                return iter([])

            def retrieve(self, name, *, folder_path=None, folder_key=None):
                return {"name": name, "value": "secret"}

            def create(
                self,
                name,
                *,
                value,
                description=None,
                folder_path=None,
                folder_key=None,
            ):
                return {"name": name, "value": value}

            def delete(self, name, *, folder_path=None, folder_key=None):
                pass

            # No exists() method for assets

        service = AssetsService()

        # Should still match (exists is optional)
        assert isinstance(service, CRUDServiceProtocol)

        # Validation should pass
        validate_service_protocol(service, "assets")

        # Verify exists method is not present
        assert not has_exists_method(service)
