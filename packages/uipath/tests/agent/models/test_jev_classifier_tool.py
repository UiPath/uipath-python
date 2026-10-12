from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from uipath.agent.models.agent import (
    AgentInternalJevClassifierSettings,
    AgentInternalJevClassifierToolProperties,
    AgentInternalToolResourceConfig,
    AgentInternalToolType,
    AgentToolArgumentArgumentProperties,
    AgentToolObjectBuilderArgumentProperties,
    AgentToolStaticArgumentProperties,
    JevChoiceQuestion,
    JevNoulCriteria,
    JevNoulQuestion,
    JevQuestion,
    JevScoreQuestion,
)


def _resource(**settings: Any) -> dict[str, Any]:
    return {
        "$resourceType": "tool",
        "id": "3f1c2a3e-0000-0000-0000-000000000001",
        "name": "Jev Classifier",
        "description": "Classify support tickets",
        "type": "Internal",
        "referenceKey": None,
        "isEnabled": True,
        "inputSchema": {
            "type": "object",
            "properties": {
                "state": {"type": "string"},
                "questions": {"type": "array"},
            },
            "required": ["state", "questions"],
        },
        "outputSchema": {"type": "object", "properties": {}},
        "settings": {},
        "argumentProperties": {},
        "properties": {"toolType": "jev-classifier", "settings": settings},
    }


CHOICE = {
    "name": "department",
    "type": "choice",
    "instructions": "Which team should handle this",
    "options": [
        {"name": "billing", "description": "Payment issues"},
        {"name": "technical", "description": None},
    ],
}
SCORE = {
    "name": "frustration",
    "type": "score",
    "instructions": "How frustrated the customer appears",
    "levels": ["Calm", "Frustrated", "Very angry"],
}
NOUL = {"name": "is_urgent", "type": "noul", "instructions": "Is this urgent?"}

_QUESTION: TypeAdapter[JevQuestion] = TypeAdapter(JevQuestion)


def _validate(data: dict[str, Any]) -> AgentInternalToolResourceConfig:
    return AgentInternalToolResourceConfig.model_validate(data)


def _settings(
    resource: AgentInternalToolResourceConfig,
) -> AgentInternalJevClassifierSettings:
    assert isinstance(resource.properties, AgentInternalJevClassifierToolProperties)
    return resource.properties.settings


def test_settings_hold_only_the_model() -> None:
    resource = _validate(_resource(model="jev-1.13.0"))

    assert isinstance(resource.properties, AgentInternalJevClassifierToolProperties)
    assert resource.properties.tool_type == AgentInternalToolType.JEV_CLASSIFIER
    assert _settings(resource).model == "jev-1.13.0"
    assert _settings(resource).model_dump() == {"model": "jev-1.13.0"}


@pytest.mark.parametrize(
    "settings",
    [pytest.param({}, id="missing"), pytest.param({"model": ""}, id="empty")],
)
def test_model_is_required(settings: dict[str, Any]) -> None:
    # No default Jev model: a tool without one fails to load.
    with pytest.raises(ValidationError, match="model"):
        _validate(_resource(**settings))


def test_tool_type_is_case_insensitive() -> None:
    data = _resource(model="jev-1.13.0")
    data["properties"]["toolType"] = "Jev-Classifier"

    assert isinstance(
        _validate(data).properties, AgentInternalJevClassifierToolProperties
    )


def test_legacy_state_and_questions_settings_are_ignored_extras() -> None:
    # BaseCfg allows extra fields: settings written before questions and state
    # moved to inputSchema still parse, but nothing reads or validates them.
    resource = _validate(
        _resource(
            model="jev-1.13.0",
            state={"type": "number"},
            questions=[{"type": "freeform"}],
        )
    )

    settings = _settings(resource)
    assert settings.model == "jev-1.13.0"
    assert not hasattr(AgentInternalJevClassifierSettings, "questions")
    assert settings.model_extra == {
        "state": {"type": "number"},
        "questions": [{"type": "freeform"}],
    }


def test_parses_all_question_types() -> None:
    choice = _QUESTION.validate_python(CHOICE)
    score = _QUESTION.validate_python(SCORE)
    noul = _QUESTION.validate_python({**NOUL, "type": "NOUL"})

    assert isinstance(choice, JevChoiceQuestion)
    assert [option.name for option in choice.options] == ["billing", "technical"]
    assert isinstance(score, JevScoreQuestion)
    assert score.levels == ["Calm", "Frustrated", "Very angry"]
    assert isinstance(noul, JevNoulQuestion)


def test_fields_of_other_types_may_be_null() -> None:
    noul = _QUESTION.validate_python({**NOUL, "options": None, "levels": None})

    assert isinstance(noul, JevNoulQuestion)


@pytest.mark.parametrize(
    ("criteria", "expected"),
    [
        pytest.param(
            {"true": "Needs a reply today", "false": "Can wait"},
            JevNoulCriteria.model_validate(
                {"true": "Needs a reply today", "false": "Can wait"}
            ),
            id="both",
        ),
        pytest.param({"true": "Yes"}, JevNoulCriteria(true="Yes"), id="true-only"),
        pytest.param({"false": None}, JevNoulCriteria(), id="null-side"),
        pytest.param({}, JevNoulCriteria(), id="empty"),
        pytest.param(None, None, id="null"),
    ],
)
def test_noul_criteria(
    criteria: dict[str, Any] | None, expected: JevNoulCriteria | None
) -> None:
    noul = _QUESTION.validate_python({**NOUL, "criteria": criteria})

    assert isinstance(noul, JevNoulQuestion)
    assert noul.criteria == expected


def test_noul_criteria_serialise_with_true_false_keys() -> None:
    noul = _QUESTION.validate_python({**NOUL, "criteria": {"true": "Yes"}})

    assert isinstance(noul, JevNoulQuestion)
    assert noul.criteria is not None
    assert noul.criteria.true == "Yes"
    assert noul.criteria.model_dump(by_alias=True) == {"true": "Yes", "false": None}


@pytest.mark.parametrize(
    "question",
    [
        pytest.param({**NOUL, "name": "has space"}, id="invalid-name"),
        pytest.param({**NOUL, "name": "1st"}, id="name-starts-with-digit"),
        pytest.param({**NOUL, "name": "a" * 65}, id="name-too-long"),
        pytest.param({**NOUL, "instructions": ""}, id="empty-instructions"),
        pytest.param({**CHOICE, "options": CHOICE["options"][:1]}, id="one-option"),
        pytest.param(
            {**CHOICE, "options": [{"name": str(i)} for i in range(256)]},
            id="too-many-options",
        ),
        pytest.param(
            {**CHOICE, "options": [{"name": "a"}, {"name": "a"}]},
            id="duplicate-options",
        ),
        pytest.param(
            {**CHOICE, "options": [{"name": "a"}, {"name": ""}]}, id="empty-option"
        ),
        pytest.param({**SCORE, "levels": ["only"]}, id="one-level"),
        pytest.param(
            {**SCORE, "levels": [str(i) for i in range(11)]}, id="too-many-levels"
        ),
        pytest.param({**SCORE, "levels": ["Low", ""]}, id="empty-level"),
        pytest.param({**CHOICE, "levels": ["a", "b"]}, id="levels-on-choice"),
        pytest.param({**SCORE, "options": CHOICE["options"]}, id="options-on-score"),
        pytest.param({**NOUL, "options": CHOICE["options"]}, id="options-on-noul"),
        pytest.param({**NOUL, "levels": ["a", "b"]}, id="levels-on-noul"),
        pytest.param({**NOUL, "type": "freeform"}, id="unknown-type"),
        pytest.param({**CHOICE, "criteria": {"true": "Yes"}}, id="criteria-on-choice"),
        pytest.param({**SCORE, "criteria": {}}, id="criteria-on-score"),
        pytest.param({**NOUL, "criteria": {"maybe": "x"}}, id="criteria-unknown-key"),
        pytest.param({**NOUL, "criteria": {"yes": "x"}}, id="criteria-field-name"),
        pytest.param({**NOUL, "criteria": {"true": 1}}, id="criteria-not-string"),
        pytest.param({**NOUL, "criteria": "Yes"}, id="criteria-not-object"),
    ],
)
def test_rejects_invalid_question(question: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        _QUESTION.validate_python(question)


def test_parses_object_builder_argument_properties() -> None:
    raw = _resource(model="jev-1.13.0")
    raw["argumentProperties"] = {
        "$['questions']": {"variant": "ObjectBuilder"},
        "$['questions']['department']": {"variant": "objectBuilder"},
        "$['questions']['department']['options']": {
            "variant": "argument",
            "argumentPath": "$['departments']",
            "isSensitive": False,
        },
        "$['questions']['is_urgent']['instructions']": {
            "variant": "static",
            "value": "Does the customer need an answer today?",
            "isSensitive": False,
        },
    }

    props = _validate(raw).argument_properties

    assert isinstance(props["$['questions']"], AgentToolObjectBuilderArgumentProperties)
    assert isinstance(
        props["$['questions']['department']"],
        AgentToolObjectBuilderArgumentProperties,
    )
    assert isinstance(
        props["$['questions']['department']['options']"],
        AgentToolArgumentArgumentProperties,
    )
    assert isinstance(
        props["$['questions']['is_urgent']['instructions']"],
        AgentToolStaticArgumentProperties,
    )
