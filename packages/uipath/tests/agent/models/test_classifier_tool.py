from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from uipath.agent.models.agent import (
    AgentInternalClassifierSettings,
    AgentInternalClassifierToolProperties,
    AgentInternalToolResourceConfig,
    AgentInternalToolType,
    AgentToolArgumentArgumentProperties,
    AgentToolObjectBuilderArgumentProperties,
    AgentToolStaticArgumentProperties,
    ClassifierProvider,
    DecisionsChoiceQuestion,
    DecisionsPredicateQuestion,
    DecisionsQuestion,
    DecisionsScoreQuestion,
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
        "name": "Classifier",
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
        "properties": {"toolType": "classifier", "settings": settings},
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

DECISIONS_CHOICE = {
    "name": "department",
    "type": "choice",
    "instructions": "Which department should handle this complaint?",
    "choices": [
        {"value": "billing", "description": "Payments, invoices, and refunds."},
        {"value": "technical", "description": None},
    ],
}
DECISIONS_SCORE = {
    "name": "frustration",
    "type": "score",
    "instructions": "How frustrated the customer appears",
    "levels": [
        {"label": "Calm", "description": "No frustration"},
        {"label": "Very angry"},
    ],
}
DECISIONS_PREDICATE = {
    "name": "is_urgent",
    "type": "predicate",
    "instructions": "The customer needs an answer today.",
}

_DECISIONS_QUESTION: TypeAdapter[DecisionsQuestion] = TypeAdapter(DecisionsQuestion)

JEV = {"provider": "typesafe", "model": "jev-1.13.0"}


def _validate(data: dict[str, Any]) -> AgentInternalToolResourceConfig:
    return AgentInternalToolResourceConfig.model_validate(data)


def _settings(
    resource: AgentInternalToolResourceConfig,
) -> AgentInternalClassifierSettings:
    assert isinstance(resource.properties, AgentInternalClassifierToolProperties)
    return resource.properties.settings


@pytest.mark.parametrize(
    ("settings", "provider"),
    [
        pytest.param(JEV, ClassifierProvider.TYPESAFE, id="typesafe"),
        pytest.param(
            {"provider": "openai", "model": "gpt-6-luna"},
            ClassifierProvider.OPENAI,
            id="openai",
        ),
    ],
)
def test_settings_hold_the_provider_and_the_model(
    settings: dict[str, Any], provider: ClassifierProvider
) -> None:
    resource = _validate(_resource(**settings))

    assert isinstance(resource.properties, AgentInternalClassifierToolProperties)
    assert resource.properties.tool_type == AgentInternalToolType.CLASSIFIER
    assert _settings(resource).provider is provider
    assert _settings(resource).model == settings["model"]


@pytest.mark.parametrize(
    "settings",
    [
        pytest.param({"provider": "typesafe"}, id="missing-model"),
        pytest.param({"provider": "typesafe", "model": ""}, id="empty-model"),
        pytest.param({"model": "jev-1.13.0"}, id="missing-provider"),
        pytest.param({"provider": "anthropic", "model": "x"}, id="unknown-provider"),
    ],
)
def test_provider_and_model_are_required(settings: dict[str, Any]) -> None:
    # No default provider or model: a tool without them fails to load.
    with pytest.raises(ValidationError):
        _validate(_resource(**settings))


def test_tool_type_and_provider_are_case_insensitive() -> None:
    data = _resource(provider="OpenAI", model="gpt-6-luna")
    data["properties"]["toolType"] = "Classifier"

    resource = _validate(data)

    assert isinstance(resource.properties, AgentInternalClassifierToolProperties)
    assert _settings(resource).provider is ClassifierProvider.OPENAI


def test_the_jev_classifier_tool_type_is_gone() -> None:
    data = _resource(**JEV)
    data["properties"]["toolType"] = "jev-classifier"

    with pytest.raises(ValidationError):
        _validate(data)


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
        pytest.param({**CHOICE, "choices": [{"value": "a"}]}, id="choices-on-choice"),
        pytest.param({**NOUL, "type": "predicate"}, id="decisions-type"),
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
    raw = _resource(**JEV)
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


def test_parses_all_decisions_question_types() -> None:
    choice = _DECISIONS_QUESTION.validate_python(DECISIONS_CHOICE)
    score = _DECISIONS_QUESTION.validate_python(DECISIONS_SCORE)
    predicate = _DECISIONS_QUESTION.validate_python(
        {**DECISIONS_PREDICATE, "type": "PREDICATE"}
    )

    assert isinstance(choice, DecisionsChoiceQuestion)
    assert [c.value for c in choice.choices] == ["billing", "technical"]
    assert isinstance(score, DecisionsScoreQuestion)
    assert [level.label for level in score.levels] == ["Calm", "Very angry"]
    assert score.levels[1].description is None
    assert isinstance(predicate, DecisionsPredicateQuestion)


@pytest.mark.parametrize(
    "question",
    [
        pytest.param({**DECISIONS_PREDICATE, "name": "has space"}, id="invalid-name"),
        pytest.param({**DECISIONS_PREDICATE, "instructions": ""}, id="empty-instr"),
        pytest.param(
            {**DECISIONS_CHOICE, "choices": DECISIONS_CHOICE["choices"][:1]},
            id="one-choice",
        ),
        pytest.param(
            {**DECISIONS_CHOICE, "choices": [{"value": "a"}, {"value": "a"}]},
            id="duplicate-choices",
        ),
        pytest.param(
            {**DECISIONS_CHOICE, "choices": [{"value": "a"}, {"value": ""}]},
            id="empty-choice",
        ),
        pytest.param(
            {**DECISIONS_SCORE, "levels": [{"label": "only"}]}, id="one-level"
        ),
        pytest.param({**DECISIONS_SCORE, "levels": ["Low", "High"]}, id="jev-levels"),
        pytest.param(
            {**DECISIONS_SCORE, "levels": [{"label": "a"}, {}]}, id="no-label"
        ),
        pytest.param({**CHOICE, "type": "choice"}, id="jev-options"),
        pytest.param({**NOUL, "type": "noul"}, id="jev-type"),
        pytest.param(
            {**DECISIONS_PREDICATE, "criteria": {"true": "Yes"}}, id="jev-criteria"
        ),
        pytest.param(
            {**DECISIONS_PREDICATE, "choices": DECISIONS_CHOICE["choices"]},
            id="choices-on-predicate",
        ),
        pytest.param(
            {**DECISIONS_CHOICE, "levels": DECISIONS_SCORE["levels"]},
            id="levels-on-choice",
        ),
    ],
)
def test_rejects_invalid_decisions_question(question: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        _DECISIONS_QUESTION.validate_python(question)
