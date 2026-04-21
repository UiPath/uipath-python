"""Tests for PII rehydration utilities."""

from uipath.platform.semantic_proxy import (
    PiiDetectionResponse,
    PiiDocumentResult,
    PiiEntity,
    PiiFileResult,
    rehydrate_from_pii_entities,
    rehydrate_from_pii_response,
)


def _entity(
    pii_text: str,
    replacement_text: str,
    pii_type: str = "Person",
    offset: int = 0,
    confidence_score: float = 0.9,
) -> PiiEntity:
    return PiiEntity(
        pii_text=pii_text,
        replacement_text=replacement_text,
        pii_type=pii_type,
        offset=offset,
        confidence_score=confidence_score,
    )


class TestRehydrateFromPiiEntities:
    """Test rehydrate_from_pii_entities."""

    def test_empty_text_returns_empty(self) -> None:
        assert rehydrate_from_pii_entities("", [_entity("Alice", "[Person-1]")]) == ""

    def test_no_entities_returns_text_unchanged(self) -> None:
        text = "Hello [Person-1]"
        assert rehydrate_from_pii_entities(text, []) == text

    def test_replaces_single_placeholder(self) -> None:
        result = rehydrate_from_pii_entities(
            "Hello [Person-1]", [_entity("Alice", "[Person-1]")]
        )
        assert result == "Hello Alice"

    def test_replaces_multiple_placeholders(self) -> None:
        result = rehydrate_from_pii_entities(
            "Contact [Person-1] at [Email-1]",
            [
                _entity("Alice", "[Person-1]"),
                _entity("alice@example.com", "[Email-1]", pii_type="Email"),
            ],
        )
        assert result == "Contact Alice at alice@example.com"

    def test_longer_placeholders_replaced_first(self) -> None:
        """[Person-10] must be rehydrated before [Person-1] to avoid partial match."""
        result = rehydrate_from_pii_entities(
            "[Person-1] and [Person-10]",
            [
                _entity("Alice", "[Person-1]"),
                _entity("Zara", "[Person-10]"),
            ],
        )
        assert result == "Alice and Zara"

    def test_case_insensitive_placeholder_match(self) -> None:
        result = rehydrate_from_pii_entities(
            "Hello [person-1]", [_entity("Alice", "[Person-1]")]
        )
        assert result == "Hello Alice"

    def test_replaces_bracketless_variant(self) -> None:
        """The LLM may drop brackets; bracketless variant should still be replaced."""
        result = rehydrate_from_pii_entities(
            "Hello Person-1", [_entity("Alice", "[Person-1]")]
        )
        assert result == "Hello Alice"

    def test_skips_entities_with_empty_replacement_text(self) -> None:
        result = rehydrate_from_pii_entities(
            "Hello [Person-1]",
            [
                _entity("Ignored", ""),
                _entity("Alice", "[Person-1]"),
            ],
        )
        assert result == "Hello Alice"

    def test_skips_entities_with_empty_pii_text(self) -> None:
        result = rehydrate_from_pii_entities(
            "Hello [Person-1]",
            [_entity("", "[Person-1]")],
        )
        assert result == "Hello [Person-1]"

    def test_preserves_non_placeholder_content(self) -> None:
        result = rehydrate_from_pii_entities(
            "The meeting with [Person-1] is at 3pm in the boardroom.",
            [_entity("Alice", "[Person-1]")],
        )
        assert result == "The meeting with Alice is at 3pm in the boardroom."

    def test_pii_text_with_special_characters(self) -> None:
        """Special chars in PII text must not break regex substitution."""
        result = rehydrate_from_pii_entities(
            "Visit [URL-1]",
            [_entity("https://example.com/path?q=1&x=2", "[URL-1]", pii_type="URL")],
        )
        assert result == "Visit https://example.com/path?q=1&x=2"

    def test_regex_special_chars_in_replacement_text(self) -> None:
        """Regex special chars in the placeholder must be escaped for the pattern."""
        result = rehydrate_from_pii_entities(
            "Hello [Person.1]",
            [_entity("Alice", "[Person.1]")],
        )
        assert result == "Hello Alice"


class TestRehydrateFromPiiResponse:
    """Test rehydrate_from_pii_response."""

    def test_merges_document_and_file_entities(self) -> None:
        response = PiiDetectionResponse(
            response=[
                PiiDocumentResult(
                    id="user-prompt",
                    role="user",
                    masked_document="Hi [Person-1]",
                    initial_document="Hi Alice",
                    pii_entities=[_entity("Alice", "[Person-1]")],
                )
            ],
            files=[
                PiiFileResult(
                    file_name="doc.pdf",
                    file_url="https://example.com/doc.pdf",
                    pii_entities=[
                        _entity("bob@example.com", "[Email-1]", pii_type="Email")
                    ],
                )
            ],
        )

        result = rehydrate_from_pii_response(
            "From [Person-1]: contact [Email-1]", response
        )
        assert result == "From Alice: contact bob@example.com"

    def test_file_only_entity_is_rehydrated(self) -> None:
        """Entities detected in files (not prompts) must also rehydrate."""
        response = PiiDetectionResponse(
            response=[],
            files=[
                PiiFileResult(
                    file_name="doc.pdf",
                    file_url="https://example.com/doc.pdf",
                    pii_entities=[
                        _entity("alice@example.com", "[Email-1]", pii_type="Email")
                    ],
                )
            ],
        )

        result = rehydrate_from_pii_response("Email is [Email-1]", response)
        assert result == "Email is alice@example.com"

    def test_empty_response_returns_text_unchanged(self) -> None:
        response = PiiDetectionResponse(response=[], files=[])
        assert rehydrate_from_pii_response("No PII here", response) == "No PII here"
