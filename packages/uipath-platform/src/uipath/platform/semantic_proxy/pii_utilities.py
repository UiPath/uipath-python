"""Utility methods for working with PII data.

Python port of UiPath.SemanticProxy.Client.PiiUtilities (C#).
"""

import json
import re
from typing import Callable, Iterable

from .semantic_proxy import PiiDetectionResponse, PiiEntity


def rehydrate_from_pii_entities(
    masked_text: str, pii_entities: Iterable[PiiEntity]
) -> str:
    """Rehydrate masked text by replacing PII placeholders with original values.

    Placeholders (e.g. ``[Person-1]``) are matched case-insensitively and replaced
    with the corresponding original PII text. The function also replaces variants
    without the surrounding brackets (e.g. ``Person-1``) in case the LLM stripped
    them in its output.

    Args:
        masked_text: The masked text with PII placeholders.
        pii_entities: The PII entities containing the original values.

    Returns:
        The rehydrated text with original PII values.
    """
    if not masked_text:
        return masked_text

    entities = [e for e in pii_entities if e.replacement_text]
    if not entities:
        return masked_text

    # Sort by replacement text length descending to avoid substring collisions
    # (e.g. "[Person-10]" must be replaced before "[Person-1]").
    entities.sort(key=lambda e: len(e.replacement_text), reverse=True)

    rehydrated = masked_text
    for entity in entities:
        if not entity.replacement_text or not entity.pii_text:
            continue
        escaped_pii = _add_escape_characters(entity.pii_text)
        # Replace the full placeholder (with brackets) case-insensitively.
        # ``_literal_replacer`` bypasses regex backreference interpretation in the
        # replacement string.
        rehydrated = re.sub(
            re.escape(entity.replacement_text),
            _literal_replacer(escaped_pii),
            rehydrated,
            flags=re.IGNORECASE,
        )
        # Also replace the content without brackets (in case the LLM dropped them).
        if entity.replacement_text.startswith("[") and entity.replacement_text.endswith(
            "]"
        ):
            no_brackets = entity.replacement_text[1:-1]
            rehydrated = re.sub(
                re.escape(no_brackets),
                _literal_replacer(escaped_pii),
                rehydrated,
                flags=re.IGNORECASE,
            )

    return rehydrated


def _literal_replacer(replacement: str) -> Callable[[re.Match[str]], str]:
    """Return a replacement function that ignores regex backreference syntax."""

    def replace(_match: re.Match[str]) -> str:
        return replacement

    return replace


def rehydrate_from_pii_response(
    masked_text: str, response: PiiDetectionResponse
) -> str:
    """Rehydrate masked text using all PII entities from a detection response.

    Merges entities from both ``response.response`` (detected in documents/prompts)
    and ``response.files`` (detected in files), so placeholders originating from
    either source are rehydrated.

    Args:
        masked_text: The masked text with PII placeholders.
        response: The PII detection response containing entities to rehydrate.

    Returns:
        The rehydrated text with original PII values.
    """
    entities: list[PiiEntity] = []
    for doc in response.response:
        entities.extend(doc.pii_entities)
    for file in response.files:
        entities.extend(file.pii_entities)
    return rehydrate_from_pii_entities(masked_text, entities)


def _add_escape_characters(text: str) -> str:
    """Escape special characters in text using JSON serialization.

    Mirrors C# ``AddEscapeCharacters`` — serializes as JSON then strips the
    surrounding quotes to get the escaped content.
    """
    if not text:
        return ""
    try:
        serialized = json.dumps(text, ensure_ascii=False)
        return serialized[1:-1]
    except (TypeError, ValueError):
        return text
