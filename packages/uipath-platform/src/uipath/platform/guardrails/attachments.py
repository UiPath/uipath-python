"""Discover the files a coded guardrail may inspect and scope it with ``appliesTo``.

Two call shapes feed the same reference type, `GuardrailAttachment`:

* Registry-matched (`referenced_attachments`), for the LangChain middleware
  hooks: only the mentions a payload names *and* the run's attachment registry holds
  are forwarded, with the registry's name and type. A mention the run never held, or
  a non-attachment resource id, is skipped rather than sent to the backend for lookup.
* Self-describing (`discover_attachments`), for decorated functions: the
  author's own arguments and return value are the data, so ``Attachment`` instances
  and mentions that carry their own name and type are forwarded without a registry.

The runtime forwards references only (``id``, ``fileName``, ``mimeType``). The Agents
backend resolves the id through Orchestrator, applies its own feature flags and
decides which validators and file types it can inspect.

Nothing in this module raises: a guardrail that cannot read a payload evaluates
without files instead of ending the run over a single malformed attachment.
"""

import logging
import uuid
from collections.abc import Iterable, Iterator, Mapping
from enum import Enum
from itertools import islice
from typing import Any

from pydantic import BaseModel

from uipath.platform.attachments import Attachment

from .guardrails import (
    BuiltInValidatorGuardrail,
    EnumParameterValue,
    GuardrailAttachment,
)

logger = logging.getLogger(__name__)


class DetectionScope(str, Enum):
    """Which content a guardrail evaluates; the wire values of ``appliesTo``."""

    TEXT = "Text"
    FILES = "Files"
    BOTH = "Both"


APPLIES_TO_PARAMETER_ID = "appliesTo"
MAX_ATTACHMENTS = 5
MAX_FILE_NAME_LENGTH = 260
MAX_SCAN_DEPTH = 32
MAX_SCAN_NODES = 10_000

_APPLIES_TO_KEY = APPLIES_TO_PARAMETER_ID.lower()
_FILE_SCOPES = frozenset(
    {DetectionScope.FILES.value.lower(), DetectionScope.BOTH.value.lower()}
)
_ID_KEYS = ("ID", "id")
_NAME_KEYS = ("FullName", "full_name")
_MIME_TYPE_KEYS = ("MimeType", "mime_type")
_CONTAINERS = (BaseModel, Mapping, list, tuple, set, frozenset)


def scope_includes_files(guardrail: BuiltInValidatorGuardrail) -> bool:
    """Tell whether a guardrail's ``appliesTo`` scope lets files through.

    ``appliesTo`` is an allow-list: only ``Files`` and ``Both`` (any case) include
    files, so an unknown value narrows to text only. An absent or empty value leaves
    the decision to the backend default, as does a parameter list that cannot be read.

    Args:
        guardrail: The guardrail whose validator parameters carry the scope.

    Returns:
        False when the guardrail is scoped to text only, True otherwise.
    """
    try:
        for parameter in guardrail.validator_parameters:
            if parameter.id.lower() != _APPLIES_TO_KEY:
                continue
            if isinstance(parameter.value, str):
                scope = parameter.value.strip().lower()
                if scope:
                    return scope in _FILE_SCOPES
    except Exception:
        logger.debug(
            "Could not read the guardrail scope; assuming files apply.", exc_info=True
        )
    return True


def with_detection_scope(
    guardrail: BuiltInValidatorGuardrail, detection_scope: DetectionScope | None
) -> BuiltInValidatorGuardrail:
    """Return the guardrail scoped to ``detection_scope``.

    Any existing ``appliesTo`` parameter (matched case-insensitively) is replaced, so
    the backend receives exactly one. The input guardrail is never mutated.

    Args:
        guardrail: The guardrail to scope.
        detection_scope: The scope to send, or None to leave the guardrail as it is.

    Returns:
        The same guardrail when ``detection_scope`` is None (or the scope cannot be
        applied), otherwise a copy carrying the scope.
    """
    if detection_scope is None:
        return guardrail
    try:
        scope = EnumParameterValue(
            parameter_type="enum",
            id=APPLIES_TO_PARAMETER_ID,
            value=DetectionScope(detection_scope).value,
        )
        parameters = [
            parameter
            for parameter in guardrail.validator_parameters
            if parameter.id.lower() != _APPLIES_TO_KEY
        ]
        return guardrail.model_copy(
            update={"validator_parameters": [*parameters, scope]}
        )
    except Exception:
        logger.warning(
            "Could not scope the guardrail to %r; the backend default applies.",
            detection_scope,
            exc_info=True,
        )
        return guardrail


def iter_attachment_mentions(data: Any) -> Iterator[Attachment | Mapping[str, Any]]:
    """Yield every attachment mention in ``data``, depth first in source order.

    A mention is an ``Attachment`` instance or a mapping whose ``ID`` or ``id`` is a
    UUID (a ``uuid.UUID`` or a string that parses as one): the wire shape the model
    and the tools exchange (``{"ID", "FullName", "MimeType"}``) or a snake-case dump
    (``{"id", "full_name", "mime_type"}``). Other pydantic models are scanned through
    their aliased dump; mappings, lists, tuples and sets are scanned item by item. A
    mention's nested models and collections are scanned too, so an object that carries
    an ``id`` of its own next to its files does not hide them, while a mention's plain
    fields cost nothing against the bounds. The scan stops past ``MAX_SCAN_DEPTH``
    levels or ``MAX_SCAN_NODES`` values, and when the payload cannot be read.

    Args:
        data: Any payload: tool arguments, a tool result, function arguments.

    Yields:
        ``Attachment`` instances as they are, mention mappings as they are.
    """
    try:
        yield from _scan(data)
    except Exception:
        logger.warning(
            "Stopped scanning a payload for attachments: it could not be read.",
            exc_info=True,
        )


def mention_id(mention: Any) -> str | None:
    """Return the canonical id of an attachment mention.

    Args:
        mention: An ``Attachment`` instance or a mention mapping.

    Returns:
        The id as a lowercase hyphenated UUID string, or None when ``mention`` carries
        no id that parses as a UUID.
    """
    try:
        if isinstance(mention, Attachment):
            return _canonical_id(mention.id)
        if isinstance(mention, Mapping):
            return _mapping_id(mention)
    except Exception:
        logger.debug("Could not read an attachment mention's id.", exc_info=True)
    return None


def to_references(attachments: Iterable[Any]) -> list[GuardrailAttachment]:
    """Build the references the validate API accepts.

    Items are ``Attachment`` instances or mention mappings (wire keys first, then
    snake-case). An item without a parseable id, a file name or a mime type is
    skipped, since the validate API rejects the whole request over an empty name or
    type. Names are truncated to ``MAX_FILE_NAME_LENGTH``, duplicates keep their first
    occurrence and at most ``MAX_ATTACHMENTS`` references are returned.

    Args:
        attachments: The candidates, in priority order.

    Returns:
        Up to ``MAX_ATTACHMENTS`` references; empty when ``attachments`` cannot be
        read.
    """
    references: list[GuardrailAttachment] = []
    seen: set[str] = set()
    try:
        for item in attachments:
            reference = _to_reference(item)
            if reference is None or reference.id in seen:
                continue
            seen.add(reference.id)
            if len(references) < MAX_ATTACHMENTS:
                references.append(reference)
        if len(seen) > MAX_ATTACHMENTS:
            logger.warning(
                "Forwarding %d of %d attachment references; the validate API accepts "
                "at most %d per evaluation, so the rest are not inspected.",
                MAX_ATTACHMENTS,
                len(seen),
                MAX_ATTACHMENTS,
            )
    except Exception:
        logger.warning(
            "Could not read the attachments; the guardrail evaluates without files.",
            exc_info=True,
        )
        return []
    return references


def referenced_attachments(
    data: Any, registry: Mapping[str, Attachment]
) -> list[GuardrailAttachment] | None:
    """Return references for the attachments ``data`` mentions and the run holds.

    Only mentions whose id is a key of ``registry`` are forwarded, with the registry's
    name and type, never the mention's: a payload (a tool result, a prompt-injected
    argument) can name any id, and only files the run legitimately holds are sent to
    the backend for lookup.

    Args:
        data: The payload to scan, e.g. a tool call's arguments or its result.
        registry: The run's attachments, keyed by canonical lowercase UUID string.

    Returns:
        Up to ``MAX_ATTACHMENTS`` references; empty when nothing held is mentioned;
        ``None`` when the payload cannot be scanned, so the caller says nothing about
        files and the text is evaluated as before.
    """
    try:
        if data is None or not registry:
            return []
        held: list[Attachment] = []
        for mention in _scan(data):
            attachment_id = mention_id(mention)
            known = registry.get(attachment_id) if attachment_id else None
            if known is None:
                logger.debug(
                    "Skipping attachment reference '%s': this run does not hold it.",
                    attachment_id,
                )
                continue
            held.append(known)
        return to_references(held)
    except Exception:
        logger.warning(
            "Could not scan the payload for attachments; the guardrail evaluates "
            "without files.",
            exc_info=True,
        )
        return None


def discover_attachments(data: Any) -> list[GuardrailAttachment] | None:
    """Return references for the self-describing attachments in ``data``.

    For decorated functions, whose arguments and return value the author controls:
    ``Attachment`` instances and mentions that carry their own name and type are
    forwarded without a registry; a bare ``{"ID": ...}`` is dropped.

    Args:
        data: The payload to scan, e.g. a function's arguments or return value.

    Returns:
        Up to ``MAX_ATTACHMENTS`` references; empty when there are none; ``None``
        when the payload cannot be scanned.
    """
    try:
        mentions = list(_scan(data))
    except Exception:
        logger.warning(
            "Could not scan the payload for attachments; the guardrail evaluates "
            "without files.",
            exc_info=True,
        )
        return None
    return to_references(mentions)


def _scan(data: Any) -> Iterator[Attachment | Mapping[str, Any]]:
    stack: list[tuple[Any, int]] = [(data, 0)]
    visited = 0
    too_deep = False
    while stack:
        value, depth = stack.pop()
        visited += 1
        if visited > MAX_SCAN_NODES:
            logger.debug(
                "Stopped scanning a payload for attachments after %d values.",
                MAX_SCAN_NODES,
            )
            return
        if depth > MAX_SCAN_DEPTH:
            if not too_deep:
                too_deep = True
                logger.debug(
                    "Not scanning a payload for attachments past %d levels.",
                    MAX_SCAN_DEPTH,
                )
            continue
        if isinstance(value, Attachment):
            yield value
            continue
        budget = max(MAX_SCAN_NODES - visited - len(stack), 0)
        if isinstance(value, BaseModel):
            children: list[Any] = [value.model_dump(by_alias=True)]
        elif isinstance(value, Mapping):
            children = list(islice(value.values(), budget))
            if _mapping_id(value) is not None:
                yield value
                children = [item for item in children if isinstance(item, _CONTAINERS)]
        elif isinstance(value, (list, tuple, set, frozenset)):
            children = list(islice(value, budget))
        else:
            continue
        stack.extend((item, depth + 1) for item in reversed(children))


def _canonical_id(value: Any) -> str | None:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, str):
        try:
            return str(uuid.UUID(value))
        except ValueError:
            return None
    return None


def _mapping_id(mapping: Mapping[Any, Any]) -> str | None:
    for key in _ID_KEYS:
        canonical = _canonical_id(mapping.get(key))
        if canonical is not None:
            return canonical
    return None


def _first_text(mapping: Mapping[Any, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _to_reference(item: Any) -> GuardrailAttachment | None:
    try:
        if isinstance(item, Attachment):
            attachment_id = _canonical_id(item.id)
            file_name, mime_type = item.full_name, item.mime_type
        elif isinstance(item, Mapping):
            attachment_id = _mapping_id(item)
            file_name = _first_text(item, _NAME_KEYS)
            mime_type = _first_text(item, _MIME_TYPE_KEYS)
        else:
            logger.warning(
                "Skipping a %s for guardrail inspection: not an attachment.",
                type(item).__name__,
            )
            return None
        if attachment_id is None:
            logger.debug(
                "Skipping attachment '%s' for guardrail inspection: invalid id.",
                file_name or "?",
            )
            return None
        if not file_name or not mime_type:
            logger.debug(
                "Skipping attachment '%s' for guardrail inspection: missing name or "
                "type.",
                file_name or attachment_id,
            )
            return None
        return GuardrailAttachment(
            id=attachment_id,
            file_name=file_name[:MAX_FILE_NAME_LENGTH],
            mime_type=mime_type,
        )
    except Exception:
        logger.warning(
            "Skipping a %s for guardrail inspection: invalid reference.",
            type(item).__name__,
            exc_info=True,
        )
        return None
