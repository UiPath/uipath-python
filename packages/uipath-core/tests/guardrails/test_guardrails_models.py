"""Tests for guardrails models normalization validators."""

from typing import TYPE_CHECKING

from uipath.core.guardrails import (
    AllFieldsSelector,
    FieldReference,
    FieldSource,
)

if TYPE_CHECKING:
    pass


class TestGuardrailsModelsNormalization:
    """Test guardrails models field normalization."""

    def test_field_reference_normalizes_capitalized_source(
        self,
    ) -> None:
        """Test that FieldReference normalizes capitalized source values to lowercase."""
        # Create FieldReference with capitalized "Input" - should normalize to FieldSource.INPUT
        field_ref = FieldReference(path="testField", source="Input")  # type: ignore[arg-type]
        assert field_ref.source == FieldSource.INPUT

        # Create FieldReference with capitalized "Output" - should normalize to FieldSource.OUTPUT
        field_ref = FieldReference(path="testField", source="Output")  # type: ignore[arg-type]
        assert field_ref.source == FieldSource.OUTPUT

        # Create FieldReference with lowercase "input" - should work as-is
        field_ref = FieldReference(path="testField", source="input")  # type: ignore[arg-type]
        assert field_ref.source == FieldSource.INPUT

    def test_all_fields_selector_normalizes_capitalized_sources(
        self,
    ) -> None:
        """Test that AllFieldsSelector normalizes capitalized source values in the list."""
        # Create AllFieldsSelector with capitalized "Input" and "Output" - should normalize
        selector = AllFieldsSelector(
            selector_type="all",
            sources=["Input", "Output"],  # type: ignore[list-item]
        )
        assert FieldSource.INPUT in selector.sources
        assert FieldSource.OUTPUT in selector.sources
        assert len(selector.sources) == 2

        # Create AllFieldsSelector with mixed case - should normalize all
        selector = AllFieldsSelector(
            selector_type="all",
            sources=["Input", "output"],  # type: ignore[list-item]
        )
        assert FieldSource.INPUT in selector.sources
        assert FieldSource.OUTPUT in selector.sources
