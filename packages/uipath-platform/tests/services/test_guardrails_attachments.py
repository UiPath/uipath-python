"""Tests for attachment discovery and the appliesTo scope of coded guardrails."""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Mapping
from typing import Any, cast

import pytest
from pydantic import BaseModel

from uipath.platform.attachments import Attachment
from uipath.platform.guardrails import (
    APPLIES_TO_PARAMETER_ID,
    BuiltInValidatorGuardrail,
    DetectionScope,
    GuardrailAttachment,
    discover_attachments,
    iter_attachment_mentions,
    mention_id,
    referenced_attachments,
    scope_includes_files,
    to_references,
    with_detection_scope,
)
from uipath.platform.guardrails.attachments import (
    MAX_ATTACHMENTS,
    MAX_FILE_NAME_LENGTH,
    MAX_SCAN_DEPTH,
    MAX_SCAN_NODES,
)
from uipath.platform.guardrails.guardrails import (
    EnumListParameterValue,
    EnumParameterValue,
)


def _attachment(name: str = "cv.pdf", mime: str = "application/pdf") -> Attachment:
    return Attachment(id=uuid.uuid4(), full_name=name, mime_type=mime)


def _wire(attachment: Attachment) -> dict[str, Any]:
    return {
        "ID": str(attachment.id),
        "FullName": attachment.full_name,
        "MimeType": attachment.mime_type,
    }


def _snake(attachment: Attachment) -> dict[str, Any]:
    return {
        "id": str(attachment.id),
        "full_name": attachment.full_name,
        "mime_type": attachment.mime_type,
    }


def _reference(attachment: Attachment) -> GuardrailAttachment:
    return GuardrailAttachment(
        id=str(attachment.id),
        file_name=attachment.full_name,
        mime_type=attachment.mime_type,
    )


def _entities() -> EnumListParameterValue:
    return EnumListParameterValue(
        parameter_type="enum-list", id="entities", value=["Email"]
    )


def _scope(value: str, parameter_id: str = "appliesTo") -> EnumParameterValue:
    return EnumParameterValue(parameter_type="enum", id=parameter_id, value=value)


def _guardrail(
    *parameters: EnumParameterValue | EnumListParameterValue,
) -> BuiltInValidatorGuardrail:
    return BuiltInValidatorGuardrail(
        id="guardrail-id",
        name="CV judge",
        guardrail_type="builtInValidator",
        validator_type="llm_as_judge",
        validator_parameters=list(parameters),
    )


class _Candidate(BaseModel):
    notes: str
    cv: Attachment


class _Order(BaseModel):
    id: uuid.UUID
    cv: Attachment


class _FrozenMention(Mapping[str, Any]):
    """A hashable mapping, so a mention can sit inside a set."""

    def __init__(self, data: Mapping[str, Any]) -> None:
        self._data = dict(data)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __hash__(self) -> int:
        return hash(tuple(sorted(self._data.items())))


class _UnreadableMapping(Mapping[str, Any]):
    """A mapping whose values cannot be listed, as a broken tool result might."""

    def __getitem__(self, key: str) -> Any:
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        raise RuntimeError("boom")

    def __len__(self) -> int:
        return 1


class _ExplodingLookup(Mapping[str, Any]):
    """A mapping whose every lookup fails."""

    def __getitem__(self, key: str) -> Any:
        raise RuntimeError("boom")

    def __iter__(self) -> Iterator[str]:
        return iter(["ID"])

    def __len__(self) -> int:
        return 1

    def get(self, key: str, default: Any = None) -> Any:
        raise RuntimeError("boom")


class _Unreadable:
    """An object whose every attribute access fails."""

    def __getattribute__(self, name: str) -> Any:
        raise RuntimeError("boom")


class _UnreadableParameters:
    def __iter__(self) -> Iterator[Any]:
        raise RuntimeError("boom")


class TestDetectionScope:
    def test_wire_values(self) -> None:
        assert [member.value for member in DetectionScope] == ["Text", "Files", "Both"]
        assert DetectionScope("Files") is DetectionScope.FILES
        assert APPLIES_TO_PARAMETER_ID == "appliesTo"


class TestWithDetectionScope:
    def test_appends_the_enum_parameter(self) -> None:
        guardrail = _guardrail(_entities())

        scoped = with_detection_scope(guardrail, DetectionScope.FILES)

        assert scoped.validator_parameters == [
            _entities(),
            EnumParameterValue(parameter_type="enum", id="appliesTo", value="Files"),
        ]

    @pytest.mark.parametrize("parameter_id", ["appliesTo", "appliesto", "AppliesTo"])
    def test_replaces_an_existing_scope_instead_of_duplicating(
        self, parameter_id: str
    ) -> None:
        guardrail = _guardrail(_scope("Text", parameter_id), _entities())

        scoped = with_detection_scope(guardrail, DetectionScope.BOTH)

        scopes = [
            parameter
            for parameter in scoped.validator_parameters
            if parameter.id.lower() == "appliesto"
        ]
        assert scopes == [
            EnumParameterValue(parameter_type="enum", id="appliesTo", value="Both")
        ]
        assert _entities() in scoped.validator_parameters

    def test_none_returns_the_same_guardrail(self) -> None:
        guardrail = _guardrail(_scope("Text"))

        assert with_detection_scope(guardrail, None) is guardrail

    def test_does_not_mutate_the_input(self) -> None:
        guardrail = _guardrail(_scope("Text"), _entities())
        original = guardrail.validator_parameters
        before = list(original)

        scoped = with_detection_scope(guardrail, DetectionScope.FILES)

        assert scoped is not guardrail
        assert guardrail.validator_parameters is original
        assert guardrail.validator_parameters == before
        assert scope_includes_files(guardrail) is False
        assert scope_includes_files(scoped) is True

    def test_an_invalid_scope_leaves_the_guardrail_unchanged(self) -> None:
        guardrail = _guardrail(_entities())

        assert with_detection_scope(guardrail, cast(Any, "files")) is guardrail

    def test_round_trips_through_the_wire_shape(self) -> None:
        scoped = with_detection_scope(_guardrail(_entities()), DetectionScope.TEXT)

        dumped = scoped.model_dump(by_alias=True)

        assert {
            "$parameterType": "enum",
            "id": "appliesTo",
            "value": "Text",
        } in dumped["validatorParameters"]
        assert BuiltInValidatorGuardrail.model_validate(dumped) == scoped


class TestScopeIncludesFiles:
    @pytest.mark.parametrize(
        "value,includes_files",
        [
            ("Text", False),
            ("text", False),
            ("  TEXT  ", False),
            ("Prompts", False),
            ("Files", True),
            ("Both", True),
            ("both", True),
            ("", True),
            ("   ", True),
        ],
    )
    def test_matrix(self, value: str, includes_files: bool) -> None:
        assert scope_includes_files(_guardrail(_scope(value))) is includes_files

    def test_absent_parameter_leaves_files_in_scope(self) -> None:
        assert scope_includes_files(_guardrail(_entities())) is True

    def test_matches_the_parameter_id_case_insensitively(self) -> None:
        assert scope_includes_files(_guardrail(_scope("Text", "AppliesTo"))) is False

    def test_unreadable_parameters_leave_files_in_scope(self) -> None:
        fields: dict[str, Any] = {
            "id": "guardrail-id",
            "name": "CV judge",
            "validator_type": "llm_as_judge",
            "validator_parameters": _UnreadableParameters(),
        }
        guardrail = BuiltInValidatorGuardrail.model_construct(**fields)

        assert scope_includes_files(guardrail) is True


class TestIterAttachmentMentions:
    def test_wire_dict(self) -> None:
        cv = _attachment()
        mention = _wire(cv)

        assert list(iter_attachment_mentions({"file": mention})) == [mention]
        assert mention_id(mention) == str(cv.id)

    def test_snake_case_dict(self) -> None:
        cv = _attachment()
        mention = _snake(cv)

        assert list(iter_attachment_mentions({"file": mention})) == [mention]
        assert mention_id(mention) == str(cv.id)

    @pytest.mark.parametrize("key", ["ID", "id"])
    def test_uuid_object_id(self, key: str) -> None:
        attachment_id = uuid.uuid4()
        mention = {key: attachment_id}

        assert list(iter_attachment_mentions([mention])) == [mention]
        assert mention_id(mention) == str(attachment_id)

    def test_attachment_instance(self) -> None:
        cv = _attachment()

        mentions = list(iter_attachment_mentions({"cv": cv}))

        assert len(mentions) == 1
        assert mentions[0] is cv
        assert mention_id(cv) == str(cv.id)

    def test_nested_containers(self) -> None:
        attachments = [_attachment(f"{index}.pdf") for index in range(6)]
        data = {
            "list": [_wire(attachments[0])],
            "tuple": (_snake(attachments[1]),),
            "set": {_FrozenMention(_wire(attachments[2]))},
            "frozenset": frozenset({_FrozenMention(_snake(attachments[3]))}),
            "nested": {"inner": {"deeper": [{"ref": attachments[4]}]}},
            "mixed": [({"file": _wire(attachments[5])},)],
        }

        found = {mention_id(mention) for mention in iter_attachment_mentions(data)}

        assert found == {str(attachment.id) for attachment in attachments}

    def test_non_attachment_model_is_scanned_by_alias(self) -> None:
        cv = _attachment()

        mentions = list(iter_attachment_mentions(_Candidate(notes="n/a", cv=cv)))

        assert [mention_id(mention) for mention in mentions] == [str(cv.id)]
        assert isinstance(mentions[0], Mapping)
        assert mentions[0]["FullName"] == "cv.pdf"

    def test_non_uuid_id_is_not_a_mention_but_its_children_are_scanned(self) -> None:
        cv = _attachment()
        data = {"ID": "queue-item-42", "child": _wire(cv)}

        assert list(iter_attachment_mentions(data)) == [_wire(cv)]
        assert mention_id(data) is None

    @pytest.mark.parametrize("key", ["ID", "id"])
    @pytest.mark.parametrize("raw_id", [True, False, None, 12, ""])
    def test_non_id_values_are_not_mentions(self, key: str, raw_id: Any) -> None:
        data = {key: raw_id, "FullName": "cv.pdf", "MimeType": "application/pdf"}

        assert list(iter_attachment_mentions(data)) == []
        assert mention_id(data) is None

    def test_a_mentions_own_values_are_scanned(self) -> None:
        cv = _attachment()
        order = {"id": str(uuid.uuid4()), "files": [_wire(cv)]}

        found = [mention_id(mention) for mention in iter_attachment_mentions(order)]

        assert str(cv.id) in found

    def test_depth_bound(self) -> None:
        cv = _attachment()
        within: Any = _wire(cv)
        for _ in range(MAX_SCAN_DEPTH):
            within = {"child": within}
        beyond: Any = _wire(cv)
        for _ in range(40):
            beyond = {"child": beyond}

        assert [mention_id(m) for m in iter_attachment_mentions(within)] == [str(cv.id)]
        assert list(iter_attachment_mentions(beyond)) == []

    def test_node_bound(self) -> None:
        mention = _wire(_attachment())
        mentions = [mention] * 20_000

        assert list(iter_attachment_mentions(list(range(20_000)))) == []
        found = list(iter_attachment_mentions(mentions))
        assert 0 < len(found) <= MAX_SCAN_NODES

    def test_unreadable_payload_stops_without_raising(self) -> None:
        assert list(iter_attachment_mentions({"result": _UnreadableMapping()})) == []

    def test_mention_id_canonicalises(self) -> None:
        attachment_id = uuid.uuid4()

        assert mention_id({"ID": str(attachment_id).upper()}) == str(attachment_id)

    @pytest.mark.parametrize(
        "value", [None, "text", 42, {"name": "cv.pdf"}, _ExplodingLookup()]
    )
    def test_mention_id_is_none_for_non_mentions(self, value: Any) -> None:
        assert mention_id(value) is None


class TestToReferences:
    def test_wire_and_snake_case_dicts(self) -> None:
        wire, snake = _attachment("a.pdf"), _attachment("b.csv", "text/csv")

        assert to_references([_wire(wire), _snake(snake)]) == [
            _reference(wire),
            _reference(snake),
        ]

    def test_uuid_object_id_in_a_dict(self) -> None:
        cv = _attachment()
        mention = {"ID": cv.id, "FullName": "cv.pdf", "MimeType": "application/pdf"}

        assert to_references([mention]) == [_reference(cv)]

    def test_attachment_instance(self) -> None:
        cv = _attachment()

        assert to_references([cv]) == [_reference(cv)]

    @pytest.mark.parametrize(
        "item",
        [
            {"ID": str(uuid.uuid4()), "MimeType": "application/pdf"},
            {"ID": str(uuid.uuid4()), "FullName": "", "MimeType": "application/pdf"},
            Attachment(id=uuid.uuid4(), full_name="", mime_type="application/pdf"),
        ],
    )
    def test_skips_a_missing_name(self, item: Any) -> None:
        assert to_references([item]) == []

    @pytest.mark.parametrize(
        "item",
        [
            {"ID": str(uuid.uuid4()), "FullName": "cv.pdf"},
            {"id": str(uuid.uuid4()), "full_name": "cv.pdf", "mime_type": ""},
            Attachment(id=uuid.uuid4(), full_name="cv.pdf", mime_type=""),
        ],
    )
    def test_skips_a_missing_mime_type(self, item: Any) -> None:
        assert to_references([item]) == []

    def test_skips_an_unparseable_id(self) -> None:
        item = {"ID": "not-a-uuid", "FullName": "cv.pdf", "MimeType": "application/pdf"}

        assert to_references([item]) == []

    def test_truncates_a_long_file_name(self) -> None:
        name = "x" * 300 + ".pdf"

        [reference] = to_references([_attachment(name)])

        assert len(reference.file_name) == MAX_FILE_NAME_LENGTH == 260
        assert reference.file_name == name[:260]

    def test_dedupes_by_id_keeping_the_first(self) -> None:
        cv = _attachment("first.pdf")
        again = {
            "ID": str(cv.id).upper(),
            "FullName": "second.pdf",
            "MimeType": "application/pdf",
        }

        assert to_references([cv, again]) == [_reference(cv)]

    def test_caps_at_the_api_limit(self) -> None:
        attachments = [_attachment(f"{index}.pdf") for index in range(7)]

        references = to_references(attachments)

        assert len(references) == MAX_ATTACHMENTS == 5
        assert references == [_reference(a) for a in attachments[:5]]

    def test_unexpected_items_are_skipped_without_using_a_slot(self) -> None:
        attachments = [_attachment(f"{index}.pdf") for index in range(MAX_ATTACHMENTS)]
        items: list[Any] = [_Unreadable(), object(), 42, "text", None, *attachments]

        assert to_references(items) == [_reference(a) for a in attachments]

    def test_an_iterable_that_breaks_degrades_to_nothing(self) -> None:
        def broken() -> Iterator[Any]:
            yield _attachment()
            raise RuntimeError("boom")

        assert to_references(broken()) == []

    def test_wire_shape(self) -> None:
        cv = _attachment()

        [reference] = to_references([cv])

        assert reference.model_dump(by_alias=True) == {
            "id": str(cv.id),
            "fileName": "cv.pdf",
            "mimeType": "application/pdf",
        }

    def test_warns_when_references_past_the_limit_are_dropped(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        attachments = [
            _attachment(f"{index}.pdf") for index in range(MAX_ATTACHMENTS + 2)
        ]

        with caplog.at_level("WARNING"):
            references = to_references(attachments)

        assert len(references) == MAX_ATTACHMENTS
        assert f"Forwarding {MAX_ATTACHMENTS} of {MAX_ATTACHMENTS + 2}" in caplog.text

    def test_no_warning_at_the_limit(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level("WARNING"):
            to_references(
                [_attachment(f"{index}.pdf") for index in range(MAX_ATTACHMENTS)]
            )

        assert "Forwarding" not in caplog.text


class TestScanBudget:
    def test_a_wide_mapping_is_read_only_up_to_the_scan_budget(self) -> None:
        consumed = 0

        class _Wide(Mapping[str, Any]):
            def __getitem__(self, key: str) -> Any:
                raise KeyError(key)

            def __iter__(self) -> Iterator[str]:
                return iter(())

            def __len__(self) -> int:
                return 10 * MAX_SCAN_NODES

            def values(self) -> Any:
                nonlocal consumed
                for index in range(10 * MAX_SCAN_NODES):
                    consumed += 1
                    yield index

        assert list(iter_attachment_mentions({"payload": _Wide()})) == []
        assert consumed <= MAX_SCAN_NODES

    def test_a_long_list_is_read_only_up_to_the_scan_budget(self) -> None:
        consumed = 0

        def values() -> Iterator[int]:
            nonlocal consumed
            for index in range(10 * MAX_SCAN_NODES):
                consumed += 1
                yield index

        class _Long(list[int]):
            def __iter__(self) -> Iterator[int]:
                return values()

        assert discover_attachments({"rows": _Long()}) == []
        assert consumed <= MAX_SCAN_NODES


class TestReferencedAttachments:
    def test_registry_name_and_type_win_over_the_mention(self) -> None:
        cv = _attachment()
        data = {
            "file": {
                "ID": str(cv.id),
                "FullName": "renamed.exe",
                "MimeType": "application/x-msdownload",
            }
        }

        assert referenced_attachments(data, {str(cv.id): cv}) == [_reference(cv)]

    def test_skips_a_mention_the_run_does_not_hold(self) -> None:
        cv, other = _attachment(), _attachment("out.csv", "text/csv")

        assert referenced_attachments({"file": _wire(other)}, {str(cv.id): cv}) == []

    def test_none_data(self) -> None:
        cv = _attachment()

        assert referenced_attachments(None, {str(cv.id): cv}) == []

    def test_empty_registry(self) -> None:
        assert referenced_attachments({"file": _wire(_attachment())}, {}) == []

    def test_matches_an_upper_case_mention(self) -> None:
        cv = _attachment()

        result = referenced_attachments(
            {"file": {"ID": str(cv.id).upper()}}, {str(cv.id): cv}
        )

        assert result == [_reference(cv)]

    def test_matches_attachment_instances_and_models_by_id(self) -> None:
        cv = _attachment()
        stale = Attachment(id=cv.id, full_name="stale.txt", mime_type="text/plain")
        data = {"direct": stale, "wrapped": _Candidate(notes="", cv=stale)}

        assert referenced_attachments(data, {str(cv.id): cv}) == [_reference(cv)]

    def test_finds_a_held_file_inside_an_object_with_its_own_id(self) -> None:
        cv = _attachment()
        data = {"id": str(uuid.uuid4()), "files": [{"ID": str(cv.id)}]}

        assert referenced_attachments(data, {str(cv.id): cv}) == [_reference(cv)]

    @pytest.mark.parametrize(
        ("decoys", "found"),
        [
            (MAX_SCAN_NODES // 4, True),
            (MAX_SCAN_NODES - 2, True),
            (MAX_SCAN_NODES - 1, False),
        ],
    )
    def test_a_plain_mention_costs_one_scanned_value(
        self, decoys: int, found: bool
    ) -> None:
        cv = _attachment()
        mentions = [*[_wire(_attachment("decoy.pdf"))] * decoys, _wire(cv)]

        result = referenced_attachments(mentions, {str(cv.id): cv})

        assert result == ([_reference(cv)] if found else [])

    def test_unscannable_payload_says_nothing_about_files(self) -> None:
        cv = _attachment()
        data = {"held": {"ID": str(cv.id)}, "result": _UnreadableMapping()}

        assert referenced_attachments(data, {str(cv.id): cv}) is None

    @pytest.mark.parametrize("data", [42, "just text", object(), [1, "two"]])
    def test_non_structured_payloads(self, data: Any) -> None:
        cv = _attachment()

        assert referenced_attachments(data, {str(cv.id): cv}) == []


class TestDiscoverAttachments:
    def test_forwards_a_self_describing_mention(self) -> None:
        cv = _attachment()

        result = discover_attachments({"cv": _wire(cv), "question": "summarize"})

        assert result == [_reference(cv)]

    def test_drops_a_bare_id(self) -> None:
        assert discover_attachments({"file": {"ID": str(uuid.uuid4())}}) == []

    def test_caps_a_mixture_at_the_api_limit(self) -> None:
        attachments = [_attachment(f"{index}.pdf") for index in range(7)]
        data = [
            attachments[0],
            _wire(attachments[1]),
            {"ID": str(uuid.uuid4())},
            _snake(attachments[2]),
            _Candidate(notes="", cv=attachments[3]),
            _wire(attachments[4]),
            _wire(attachments[5]),
            _wire(attachments[6]),
        ]

        result = discover_attachments(data)

        assert result is not None
        assert len(result) == MAX_ATTACHMENTS
        assert len({reference.id for reference in result}) == MAX_ATTACHMENTS
        assert {reference.id for reference in result} <= {
            str(attachment.id) for attachment in attachments
        }

    def test_keeps_the_first_references_in_source_order(self) -> None:
        attachments = [_attachment(f"{index}.pdf") for index in range(7)]
        first = [_reference(attachment) for attachment in attachments[:MAX_ATTACHMENTS]]
        kwargs = {f"a{index}": a for index, a in enumerate(attachments)}

        assert discover_attachments(attachments) == first
        assert discover_attachments(kwargs) == first

    def test_finds_files_next_to_an_own_id(self) -> None:
        cv = _attachment()

        assert discover_attachments({"id": uuid.uuid4(), "cv": cv}) == [_reference(cv)]
        assert discover_attachments(_Order(id=uuid.uuid4(), cv=cv)) == [_reference(cv)]

    @pytest.mark.parametrize("data", [None, 42, "text"])
    def test_finds_nothing_in_unstructured_data(self, data: Any) -> None:
        assert discover_attachments(data) == []

    def test_unscannable_payload_says_nothing_about_files(self) -> None:
        assert discover_attachments({"result": _UnreadableMapping()}) is None
