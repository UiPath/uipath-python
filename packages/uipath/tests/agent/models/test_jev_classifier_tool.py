from typing import Any

import pytest
from pydantic import ValidationError

from uipath.agent.models.agent import (
    AgentInternalJevClassifierToolProperties,
    AgentInternalToolResourceConfig,
    AgentInternalToolType,
    JevChoiceQuestion,
    JevNoulQuestion,
    JevScoreQuestion,
)


def _resource(questions: list[dict[str, Any]], **settings: Any) -> dict[str, Any]:
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
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        "outputSchema": {"type": "object", "properties": {}},
        "settings": {},
        "argumentProperties": {},
        "properties": {
            "toolType": "jev-classifier",
            "settings": {"questions": questions, **settings},
        },
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


def _validate(data: dict[str, Any]) -> AgentInternalToolResourceConfig:
    return AgentInternalToolResourceConfig.model_validate(data)


def test_parses_all_question_types() -> None:
    resource = _validate(_resource([CHOICE, SCORE, NOUL]))

    properties = resource.properties
    assert isinstance(properties, AgentInternalJevClassifierToolProperties)
    assert properties.tool_type == AgentInternalToolType.JEV_CLASSIFIER
    assert properties.settings.model == "jev-latest"
    choice, score, noul = properties.settings.questions
    assert isinstance(choice, JevChoiceQuestion)
    assert [option.name for option in choice.options] == ["billing", "technical"]
    assert isinstance(score, JevScoreQuestion)
    assert score.levels == ["Calm", "Frustrated", "Very angry"]
    assert isinstance(noul, JevNoulQuestion)


def test_tool_and_question_types_are_case_insensitive() -> None:
    data = _resource([{**NOUL, "type": "NOUL"}], model="jev-1.13.0")
    data["properties"]["toolType"] = "Jev-Classifier"

    resource = _validate(data)

    assert isinstance(resource.properties, AgentInternalJevClassifierToolProperties)
    assert resource.properties.settings.model == "jev-1.13.0"
    assert isinstance(resource.properties.settings.questions[0], JevNoulQuestion)


@pytest.mark.parametrize(
    "questions",
    [
        pytest.param([], id="no-questions"),
        pytest.param([NOUL, NOUL], id="duplicate-question-names"),
        pytest.param([{**NOUL, "name": "has space"}], id="invalid-name"),
        pytest.param([{**NOUL, "instructions": ""}], id="empty-instructions"),
        pytest.param([{**CHOICE, "options": CHOICE["options"][:1]}], id="one-option"),
        pytest.param(
            [{**CHOICE, "options": [{"name": "a"}, {"name": "a"}]}],
            id="duplicate-options",
        ),
        pytest.param([{**SCORE, "levels": ["only"]}], id="one-level"),
        pytest.param([{**NOUL, "type": "freeform"}], id="unknown-type"),
    ],
)
def test_rejects_invalid_settings(questions: list[dict[str, Any]]) -> None:
    with pytest.raises(ValidationError):
        _validate(_resource(questions))
