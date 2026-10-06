"""Tests for guardrails models normalization validators."""

from typing import TYPE_CHECKING

from uipath.core.guardrails import (
    AllFieldsSelector,
    FieldReference,
    FieldSource,
    GuardrailValidationResult,
    GuardrailValidationResultType,
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


class TestGuardrailValidationResultFlaggedAttachmentIds:
    """Test GuardrailValidationResult.flagged_attachment_ids."""

    def test_defaults_to_none(self) -> None:
        result = GuardrailValidationResult(
            result=GuardrailValidationResultType.PASSED, reason=""
        )
        assert result.flagged_attachment_ids is None

    def test_populates_from_alias(self) -> None:
        result = GuardrailValidationResult.model_validate(
            {
                "result": "validation_failed",
                "reason": "PII detected",
                "flaggedAttachmentIds": ["a", "b"],
            }
        )
        assert result.flagged_attachment_ids == ["a", "b"]

    def test_populates_from_field_name(self) -> None:
        result = GuardrailValidationResult(
            result=GuardrailValidationResultType.VALIDATION_FAILED,
            reason="PII detected",
            flagged_attachment_ids=["a"],
        )
        assert result.flagged_attachment_ids == ["a"]

    def test_dumps_by_alias_like_span_id(self) -> None:
        result = GuardrailValidationResult(
            result=GuardrailValidationResultType.VALIDATION_FAILED,
            reason="PII detected",
            span_id="span",
            flagged_attachment_ids=["a"],
        )
        dumped = result.model_dump(by_alias=True)
        assert dumped["spanId"] == "span"
        assert dumped["flaggedAttachmentIds"] == ["a"]

    def test_dumps_none_by_alias_like_span_id(self) -> None:
        result = GuardrailValidationResult(
            result=GuardrailValidationResultType.PASSED, reason=""
        )
        dumped = result.model_dump(by_alias=True)
        assert dumped["spanId"] is None
        assert dumped["flaggedAttachmentIds"] is None
        assert "flaggedAttachmentIds" not in result.model_dump(
            by_alias=True, exclude_none=True
        )
