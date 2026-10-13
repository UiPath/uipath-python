"""Tests for attachment forwarding and the ``detection_scope`` scope of ``@guardrail``."""

from __future__ import annotations

import inspect
import json
import logging
import uuid
from collections.abc import Iterator
from typing import Annotated, Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from pydantic import BaseModel, ConfigDict
from uipath.core.guardrails import (
    GuardrailValidationResult,
    GuardrailValidationResultType,
)

from uipath.platform.attachments import Attachment
from uipath.platform.errors import EnrichedException
from uipath.platform.guardrails.decorators import (
    BlockAction,
    BuiltInGuardrailValidator,
    ByoValidator,
    CustomValidator,
    DetectionScope,
    GuardrailBlockException,
    GuardrailExclude,
    GuardrailExecutionStage,
    GuardrailValidatorBase,
    LogAction,
    PIIDetectionEntity,
    PIIDetectionEntityType,
    PIIValidator,
    guardrail,
)
from uipath.platform.guardrails.decorators._core import (
    _collect_input,
    _make_evaluator,
    _serialize_value,
)
from uipath.platform.guardrails.guardrails import (
    BuiltInValidatorGuardrail,
    EnumParameterValue,
    GuardrailAttachment,
)

_PASSED = GuardrailValidationResult(
    result=GuardrailValidationResultType.PASSED,
    reason="ok",
)
_FAILED = GuardrailValidationResult(
    result=GuardrailValidationResultType.VALIDATION_FAILED,
    reason="email found",
)
_QUESTION = "Does this CV fit the role?"
_VALIDATORS_LOGGER = "uipath.platform.guardrails.decorators.validators._base"


class _Screening(BaseModel):
    verdict: str
    cv: Attachment


class _Opaque:
    pass


class _OpaqueState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    topic: str
    handle: _Opaque


class _LegacyValidator(GuardrailValidatorBase):
    """A third-party validator written against the original ``run`` signature."""

    def __init__(self) -> None:
        self.inputs: list[dict[str, Any] | None] = []

    def run(
        self,
        name: str,
        description: str | None,
        enabled_for_evals: bool,
        data: str | dict[str, Any],
        stage: GuardrailExecutionStage,
        input_data: dict[str, Any] | None,
        output_data: dict[str, Any] | None,
    ) -> GuardrailValidationResult:
        self.inputs.append(input_data)
        return _PASSED


class _LegacyBuiltInValidator(BuiltInGuardrailValidator):
    """A third-party API validator overriding ``run`` with the original signature."""

    def __init__(self) -> None:
        self.inputs: list[dict[str, Any] | None] = []

    def get_built_in_guardrail(
        self, name: str, description: str | None, enabled_for_evals: bool
    ) -> BuiltInValidatorGuardrail:
        return _pii().get_built_in_guardrail(name, description, enabled_for_evals)

    def run(  # type: ignore[override]
        self,
        name: str,
        description: str | None,
        enabled_for_evals: bool,
        data: str | dict[str, Any],
        stage: GuardrailExecutionStage,
        input_data: dict[str, Any] | None,
        output_data: dict[str, Any] | None,
    ) -> GuardrailValidationResult:
        self.inputs.append(input_data)
        return _FAILED


class _ForwardingBuiltInValidator(BuiltInGuardrailValidator):
    """A third-party API validator overriding ``run`` with a ``**kwargs`` catch-all."""

    def __init__(self) -> None:
        self.kwargs: list[dict[str, Any]] = []

    def get_built_in_guardrail(
        self, name: str, description: str | None, enabled_for_evals: bool
    ) -> BuiltInValidatorGuardrail:
        return _pii().get_built_in_guardrail(name, description, enabled_for_evals)

    def run(self, *args: Any, **kwargs: Any) -> GuardrailValidationResult:
        self.kwargs.append(kwargs)
        return super().run(*args, **kwargs)


@pytest.fixture
def evaluate() -> Iterator[MagicMock]:
    """Patch the UiPath client and yield its ``guardrails.evaluate_guardrail``."""
    uipath = MagicMock()
    uipath.guardrails.evaluate_guardrail.return_value = _PASSED
    with patch("uipath.platform.UiPath", return_value=uipath):
        yield uipath.guardrails.evaluate_guardrail


def _attachment(name: str = "cv.pdf", mime: str = "application/pdf") -> Attachment:
    return Attachment(id=uuid.uuid4(), full_name=name, mime_type=mime)


def _reference(attachment: Attachment) -> GuardrailAttachment:
    return GuardrailAttachment(
        id=str(attachment.id),
        file_name=attachment.full_name,
        mime_type=attachment.mime_type,
    )


def _dumped(attachment: Attachment) -> dict[str, Any]:
    return {
        "id": str(attachment.id),
        "full_name": attachment.full_name,
        "mime_type": attachment.mime_type,
        "metadata": None,
    }


def _pii() -> PIIValidator:
    return PIIValidator(entities=[PIIDetectionEntity(PIIDetectionEntityType.EMAIL)])


def _sent_guardrail(evaluate: MagicMock) -> BuiltInValidatorGuardrail:
    return evaluate.call_args.args[1]


def _scope(value: str) -> EnumParameterValue:
    return EnumParameterValue(parameter_type="enum", id="appliesTo", value=value)


def _rejection(status: int) -> EnrichedException:
    request = httpx.Request("POST", "https://example.com/validate")
    response = httpx.Response(status, request=request, text="rejected")
    return EnrichedException(
        httpx.HTTPStatusError(str(status), request=request, response=response)
    )


class TestInputAttachments:
    def test_sync_function_forwards_attachment_argument(self, evaluate: MagicMock):
        cv = _attachment()

        @guardrail(
            validator=_pii(), action=LogAction(), stage=GuardrailExecutionStage.PRE
        )
        def screen(cv: Attachment, question: str) -> str:
            return question

        assert screen(cv, _QUESTION) == _QUESTION
        evaluate.assert_called_once()
        assert evaluate.call_args.args[0] == {"cv": _dumped(cv), "question": _QUESTION}
        assert evaluate.call_args.kwargs == {"attachments": [_reference(cv)]}

    async def test_async_function_forwards_attachment_argument(
        self, evaluate: MagicMock
    ):
        cv = _attachment()

        @guardrail(
            validator=_pii(), action=LogAction(), stage=GuardrailExecutionStage.PRE
        )
        async def screen(cv: Attachment, question: str) -> str:
            return question

        assert await screen(cv, _QUESTION) == _QUESTION
        evaluate.assert_called_once()
        assert evaluate.call_args.args[0] == {"cv": _dumped(cv), "question": _QUESTION}
        assert evaluate.call_args.kwargs == {"attachments": [_reference(cv)]}

    def test_wire_shaped_mapping_is_forwarded(self, evaluate: MagicMock):
        cv = _attachment()
        wire = {"ID": str(cv.id), "FullName": cv.full_name, "MimeType": cv.mime_type}

        @guardrail(
            validator=_pii(), action=LogAction(), stage=GuardrailExecutionStage.PRE
        )
        def screen(cv: dict[str, Any]) -> None:
            return None

        screen(wire)
        assert evaluate.call_args.kwargs == {"attachments": [_reference(cv)]}

    def test_bare_id_mapping_is_not_forwarded(self, evaluate: MagicMock):
        @guardrail(
            validator=_pii(), action=LogAction(), stage=GuardrailExecutionStage.PRE
        )
        def screen(cv: dict[str, Any]) -> None:
            return None

        screen({"ID": str(uuid.uuid4())})
        evaluate.assert_called_once()
        assert evaluate.call_args.kwargs == {}

    def test_excluded_attachment_is_neither_serialized_nor_forwarded(
        self, evaluate: MagicMock
    ):
        @guardrail(
            validator=_pii(), action=LogAction(), stage=GuardrailExecutionStage.PRE
        )
        def screen(cv: Annotated[Attachment, GuardrailExclude()], question: str) -> str:
            return question

        screen(_attachment(), _QUESTION)
        assert evaluate.call_args.args[0] == {"question": _QUESTION}
        assert evaluate.call_args.kwargs == {}


class TestOutputAttachments:
    def test_returned_attachment_is_forwarded_on_post_only(self, evaluate: MagicMock):
        cv = _attachment()

        @guardrail(validator=_pii(), action=LogAction())
        def fetch(question: str) -> Attachment:
            return cv

        assert fetch(_QUESTION) is cv
        pre, post = evaluate.call_args_list
        assert pre.args[0] == {"question": _QUESTION}
        assert pre.kwargs == {}
        assert post.args[0] == _dumped(cv)
        assert post.kwargs == {"attachments": [_reference(cv)]}

    def test_attachment_field_of_returned_model_is_forwarded_on_post(
        self, evaluate: MagicMock
    ):
        cv = _attachment()

        @guardrail(
            validator=_pii(), action=LogAction(), stage=GuardrailExecutionStage.POST
        )
        def screen(question: str) -> _Screening:
            return _Screening(verdict="fit", cv=cv)

        screen(_QUESTION)
        evaluate.assert_called_once()
        assert evaluate.call_args.args[0] == {"verdict": "fit", "cv": _dumped(cv)}
        assert evaluate.call_args.kwargs == {"attachments": [_reference(cv)]}


class TestDetectionScope:
    def test_files_scope_is_sent_as_one_enum_parameter(self, evaluate: MagicMock):
        cv = _attachment()

        @guardrail(
            validator=_pii(),
            action=LogAction(),
            stage=GuardrailExecutionStage.PRE,
            detection_scope=DetectionScope.FILES,
        )
        def screen(cv: Attachment) -> None:
            return None

        screen(cv)
        parameters = _sent_guardrail(evaluate).validator_parameters
        assert [p.id for p in parameters] == [
            "entities",
            "entityThresholds",
            "appliesTo",
        ]
        assert [p for p in parameters if p.id == "appliesTo"] == [_scope("Files")]
        assert evaluate.call_args.kwargs == {"attachments": [_reference(cv)]}

    def test_text_scope_sends_the_scope_and_no_attachments(self, evaluate: MagicMock):
        @guardrail(
            validator=_pii(),
            action=LogAction(),
            stage=GuardrailExecutionStage.PRE,
            detection_scope=DetectionScope.TEXT,
        )
        def screen(cv: Attachment, question: str) -> str:
            return question

        screen(_attachment(), _QUESTION)
        parameters = _sent_guardrail(evaluate).validator_parameters
        assert [p for p in parameters if p.id == "appliesTo"] == [_scope("Text")]
        assert evaluate.call_args.kwargs == {}

    def test_scope_given_as_wire_string_is_accepted(self, evaluate: MagicMock):
        cv = _attachment()

        @guardrail(
            validator=_pii(),
            action=LogAction(),
            stage=GuardrailExecutionStage.PRE,
            detection_scope="Both",
        )
        def screen(cv: Attachment) -> None:
            return None

        screen(cv)
        parameters = _sent_guardrail(evaluate).validator_parameters
        assert [p for p in parameters if p.id == "appliesTo"] == [_scope("Both")]
        assert evaluate.call_args.kwargs == {"attachments": [_reference(cv)]}

    @pytest.mark.parametrize("detection_scope", ["files", "TEXT", "", 1])
    def test_invalid_scope_raises_at_decoration(self, detection_scope: Any):
        with pytest.raises(
            ValueError, match="detection_scope must be a DetectionScope member"
        ):
            guardrail(
                validator=_pii(), action=LogAction(), detection_scope=detection_scope
            )

    def test_no_scope_leaves_the_validator_parameters_unchanged(
        self, evaluate: MagicMock
    ):
        validator = _pii()

        @guardrail(
            validator=validator,
            action=LogAction(),
            stage=GuardrailExecutionStage.PRE,
        )
        def screen(cv: Attachment) -> None:
            return None

        screen(_attachment())
        expected = validator.get_built_in_guardrail("G", None, True)
        sent = _sent_guardrail(evaluate)
        assert sent.validator_parameters == expected.validator_parameters

    def test_text_scope_supplied_as_a_validator_parameter_drops_the_attachments(
        self, evaluate: MagicMock
    ):
        validator = ByoValidator("my-byog", parameters=[_scope("Text")])

        @guardrail(
            validator=validator, action=LogAction(), stage=GuardrailExecutionStage.PRE
        )
        def screen(cv: Attachment, question: str) -> str:
            return question

        screen(_attachment(), _QUESTION)
        evaluate.assert_called_once()
        parameters = _sent_guardrail(evaluate).validator_parameters
        assert [p for p in parameters if p.id == "appliesTo"] == [_scope("Text")]
        assert evaluate.call_args.kwargs == {}


class TestExplicitEmptyAttachments:
    @pytest.mark.parametrize(
        ("detection_scope", "expected"),
        [
            (DetectionScope.FILES, {"attachments": []}),
            (DetectionScope.BOTH, {"attachments": []}),
            (DetectionScope.TEXT, {}),
            (None, {}),
        ],
    )
    def test_a_call_without_files_sends_an_empty_list_only_when_files_apply(
        self,
        evaluate: MagicMock,
        detection_scope: DetectionScope | None,
        expected: dict[str, Any],
    ):
        @guardrail(
            validator=_pii(),
            action=LogAction(),
            stage=GuardrailExecutionStage.PRE,
            detection_scope=detection_scope,
        )
        def screen(question: str) -> str:
            return question

        screen(_QUESTION)
        evaluate.assert_called_once()
        assert evaluate.call_args.args[0] == {"question": _QUESTION}
        assert evaluate.call_args.kwargs == expected

    def test_files_scope_supplied_as_a_validator_parameter_sends_an_empty_list(
        self, evaluate: MagicMock
    ):
        validator = ByoValidator("my-byog", parameters=[_scope("Both")])

        @guardrail(
            validator=validator, action=LogAction(), stage=GuardrailExecutionStage.PRE
        )
        def screen(question: str) -> str:
            return question

        screen(_QUESTION)
        evaluate.assert_called_once()
        assert evaluate.call_args.kwargs == {"attachments": []}

    def test_arguments_that_cannot_be_scanned_say_nothing_about_files(
        self, evaluate: MagicMock
    ):
        @guardrail(
            validator=_pii(),
            action=LogAction(),
            stage=GuardrailExecutionStage.PRE,
            detection_scope=DetectionScope.FILES,
        )
        def screen(question: str) -> str:
            return question

        with patch(
            "uipath.platform.guardrails.decorators._core.discover_attachments",
            return_value=None,
        ):
            screen(_QUESTION)
        evaluate.assert_called_once()
        assert evaluate.call_args.kwargs == {}


class TestDiscoveryOnlyWhenFilesAreForwarded:
    @pytest.mark.parametrize(
        "validator, detection_scope",
        [
            (CustomValidator(lambda args: False), None),
            (_pii(), DetectionScope.TEXT),
        ],
        ids=["custom-validator", "text-scope"],
    )
    def test_skips_discovery_when_the_evaluator_drops_files(
        self, evaluate: MagicMock, validator: Any, detection_scope: Any
    ):
        @guardrail(
            validator=validator,
            action=LogAction(),
            detection_scope=detection_scope,
        )
        def screen(cv: Attachment) -> Attachment:
            return cv

        with (
            patch(
                "uipath.platform.guardrails.decorators._guardrail._discover_input_attachments"
            ) as discover_input,
            patch(
                "uipath.platform.guardrails.decorators._guardrail._discover_output_attachments"
            ) as discover_output,
        ):
            screen(_attachment())

        discover_input.assert_not_called()
        discover_output.assert_not_called()

    def test_discovers_when_files_are_forwarded(self, evaluate: MagicMock):
        @guardrail(
            validator=_pii(),
            action=LogAction(),
            stage=GuardrailExecutionStage.PRE,
            detection_scope=DetectionScope.FILES,
        )
        def screen(cv: Attachment) -> Attachment:
            return cv

        cv = _attachment()
        screen(cv)
        assert evaluate.call_args.kwargs == {"attachments": [_reference(cv)]}


class TestDetectionScopeOnLocalValidators:
    def test_warns_once_at_decoration(self, caplog: pytest.LogCaptureFixture):
        with caplog.at_level(logging.WARNING):

            @guardrail(
                validator=CustomValidator(lambda args: False),
                action=LogAction(),
                name="Local rule",
                detection_scope=DetectionScope.FILES,
            )
            def screen(question: str) -> str:
                return question

            screen(_QUESTION)
            screen(_QUESTION)

        warnings = [r for r in caplog.records if "sets detection_scope" in r.message]
        assert len(warnings) == 1
        assert "Local rule" in warnings[0].getMessage()

    def test_no_warning_without_a_scope(self, caplog: pytest.LogCaptureFixture):
        with caplog.at_level(logging.WARNING):

            @guardrail(
                validator=CustomValidator(lambda args: False), action=LogAction()
            )
            def screen(question: str) -> str:
                return question

        assert "sets detection_scope" not in caplog.text


class TestValidatorsWithoutFileSupport:
    def test_custom_validator_rule_receives_the_serialized_input_only(self):
        cv = _attachment()
        captured: list[dict[str, Any]] = []

        def rule(args: dict[str, Any]) -> bool:
            captured.append(args)
            return False

        validator = CustomValidator(rule)

        @guardrail(
            validator=validator, action=LogAction(), stage=GuardrailExecutionStage.PRE
        )
        def screen(cv: Attachment, question: str) -> str:
            return question

        with patch.object(validator, "run", wraps=validator.run) as run:
            assert screen(cv, _QUESTION) == _QUESTION

        assert captured == [{"cv": _dumped(cv), "question": _QUESTION}]
        assert run.call_args.kwargs == {}

    def test_validator_with_the_original_run_signature_still_works(self):
        cv = _attachment()
        validator = _LegacyValidator()

        @guardrail(validator=validator, action=LogAction())
        def screen(cv: Attachment, question: str) -> str:
            return question

        assert screen(cv, _QUESTION) == _QUESTION
        expected = {"cv": _dumped(cv), "question": _QUESTION}
        assert validator.inputs == [expected, expected]

    def test_built_in_validator_with_the_original_run_signature_still_blocks(
        self, caplog: pytest.LogCaptureFixture
    ):
        cv = _attachment()
        validator = _LegacyBuiltInValidator()

        @guardrail(
            validator=validator,
            action=BlockAction(),
            name="CV check",
            stage=GuardrailExecutionStage.PRE,
        )
        def screen(cv: Attachment) -> None:
            return None

        with caplog.at_level(logging.WARNING):
            for _ in range(2):
                with pytest.raises(GuardrailBlockException):
                    screen(cv)

        assert validator.inputs == [{"cv": _dumped(cv)}, {"cv": _dumped(cv)}]
        assert [record.getMessage() for record in caplog.records] == [
            "Validator _LegacyBuiltInValidator overrides run() without the "
            "attachments/detection_scope parameters; files and scope are ignored for "
            "guardrail 'CV check'."
        ]

    def test_built_in_validator_with_a_kwargs_catch_all_receives_the_files(
        self, evaluate: MagicMock
    ):
        cv = _attachment()
        validator = _ForwardingBuiltInValidator()

        @guardrail(
            validator=validator,
            action=LogAction(),
            stage=GuardrailExecutionStage.PRE,
            detection_scope=DetectionScope.FILES,
        )
        def screen(cv: Attachment) -> None:
            return None

        screen(cv)
        assert validator.kwargs == [
            {"detection_scope": DetectionScope.FILES, "attachments": [_reference(cv)]}
        ]
        assert evaluate.call_args.kwargs == {"attachments": [_reference(cv)]}


class TestEvaluator:
    @pytest.mark.parametrize(
        ("validator", "detection_scope", "expected"),
        [
            (_pii(), None, True),
            (_pii(), DetectionScope.BOTH, True),
            (_pii(), DetectionScope.TEXT, False),
            (_pii(), "Text", False),
            (ByoValidator("byog", parameters=[_scope("Text")]), None, False),
            (
                ByoValidator("byog", parameters=[_scope("Text")]),
                DetectionScope.FILES,
                True,
            ),
            (CustomValidator(lambda args: False), DetectionScope.BOTH, False),
            (_LegacyBuiltInValidator(), DetectionScope.BOTH, False),
        ],
        ids=[
            "backend-default",
            "both",
            "text",
            "text-wire-string",
            "text-parameter",
            "applies-to-overrides-parameter",
            "custom-validator",
            "legacy-run-override",
        ],
    )
    def test_tells_adapters_whether_it_forwards_files(
        self, validator: GuardrailValidatorBase, detection_scope: Any, expected: bool
    ):
        evaluator = _make_evaluator(validator, "G", None, True, detection_scope)

        assert evaluator.forwards_attachments is expected  # type: ignore[attr-defined]

    def test_attachments_from_an_adapter_reach_the_service(self, evaluate: MagicMock):
        cv = _attachment()
        evaluator = _make_evaluator(_pii(), "G", None, True)

        evaluator(
            "text",
            GuardrailExecutionStage.PRE,
            None,
            None,
            attachments=[_reference(cv)],
        )

        assert evaluate.call_args.kwargs == {"attachments": [_reference(cv)]}

    def test_call_without_attachments_keeps_the_text_only_request(
        self, evaluate: MagicMock
    ):
        evaluator = _make_evaluator(_pii(), "G", None, True)

        evaluator("text", GuardrailExecutionStage.PRE, None, None)

        assert evaluate.call_args.args[0] == "text"
        assert len(evaluate.call_args.args) == 2
        assert evaluate.call_args.kwargs == {}

    def test_text_scope_given_as_wire_string_forwards_no_attachments(
        self, evaluate: MagicMock
    ):
        validator = _pii()
        evaluator = _make_evaluator(
            validator,
            "G",
            None,
            True,
            detection_scope="Text",  # type: ignore[arg-type]
        )

        with patch.object(validator, "run", wraps=validator.run) as run:
            evaluator(
                "text",
                GuardrailExecutionStage.PRE,
                None,
                None,
                attachments=[_reference(_attachment())],
            )

        assert run.call_args.kwargs == {"detection_scope": "Text"}
        assert evaluate.call_args.kwargs == {}


class TestAttachmentRejection:
    def test_rejected_attachments_are_dropped_and_the_text_re_evaluated(
        self, evaluate: MagicMock, caplog: pytest.LogCaptureFixture
    ):
        cv, letter = _reference(_attachment()), _reference(_attachment("letter.pdf"))
        evaluate.side_effect = [_rejection(400), _FAILED]
        evaluator = _make_evaluator(_pii(), "G", None, True)

        with caplog.at_level(logging.DEBUG, logger=_VALIDATORS_LOGGER):
            result = evaluator(
                "text",
                GuardrailExecutionStage.PRE,
                None,
                None,
                attachments=[cv, letter],
            )

        assert result is _FAILED
        with_files, text_only = evaluate.call_args_list
        assert with_files.kwargs == {"attachments": [cv, letter]}
        assert text_only.args == with_files.args
        assert text_only.kwargs == {}
        records = [r for r in caplog.records if r.name == _VALIDATORS_LOGGER]
        assert [(r.levelno, r.getMessage()) for r in records] == [
            (
                logging.WARNING,
                "Guardrail 'G' rejected the attachment references (HTTP 400); "
                "re-evaluating without attachments (2 dropped).",
            ),
            (
                logging.DEBUG,
                f"Guardrail 'G' dropped the attachment ids {cv.id}, {letter.id}.",
            ),
        ]
        assert "cv.pdf" not in caplog.text
        assert "letter.pdf" not in caplog.text

    def test_other_status_with_attachments_propagates(self, evaluate: MagicMock):
        evaluate.side_effect = _rejection(500)
        evaluator = _make_evaluator(_pii(), "G", None, True)

        with pytest.raises(EnrichedException) as exc_info:
            evaluator(
                "text",
                GuardrailExecutionStage.PRE,
                None,
                None,
                attachments=[_reference(_attachment())],
            )

        assert exc_info.value.status_code == 500
        evaluate.assert_called_once()

    def test_400_on_a_text_only_call_propagates(self, evaluate: MagicMock):
        evaluate.side_effect = _rejection(400)
        evaluator = _make_evaluator(_pii(), "G", None, True)

        with pytest.raises(EnrichedException) as exc_info:
            evaluator("text", GuardrailExecutionStage.PRE, None, None)

        assert exc_info.value.status_code == 400
        evaluate.assert_called_once()


class TestJsonSafeSerialization:
    def test_attachment_id_serializes_as_string(self):
        cv = _attachment()
        assert _serialize_value(cv) == _dumped(cv)

    def test_collected_attachment_input_is_json_serializable(self):
        cv = _attachment()

        def screen(cv: Attachment, question: str) -> None:
            return None

        bound = inspect.signature(screen).bind(cv, _QUESTION)
        payload = json.loads(json.dumps(_collect_input(bound, set())))
        assert payload == {"cv": _dumped(cv), "question": _QUESTION}

    def test_model_without_a_json_form_keeps_its_python_dump(self):
        handle = _Opaque()
        assert _serialize_value(_OpaqueState(topic="cats", handle=handle)) == {
            "topic": "cats",
            "handle": handle,
        }
