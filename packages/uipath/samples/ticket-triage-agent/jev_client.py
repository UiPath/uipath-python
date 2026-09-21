"""Local stub for TypeSafe AI's "Jev" System One model client.

*** THIS IS A MOCK, NOT A REAL UIPATH OR TYPESAFE AI PRODUCT INTEGRATION. ***

TypeSafe AI's `typesafe-sdk` PyPI package was published the same day this
sample was written, has an unusual dependency (`httpx2`), and has not been
independently vetted. Rather than pull an unverified, brand-new third-party
package into this SDK's samples, this module hand-rolls a small stand-in
that mimics the real SDK's public shape:

    from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

    client = TypeSafeClient()
    response = client.system_one(state=..., questions={...})

Once you have independently vetted the real `typesafe-sdk` package (or any
other System One provider), swapping it in is a one-line change: replace the
import below with the real package's import and delete this file. Nothing
else in `main.py` needs to change, since the public shape (`TypeSafeClient`,
`Choice`/`Noul`/`Score`, `.system_one(...)`) is mirrored here on purpose.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any


@dataclass
class Choice:
    """Declares a multi-option classification question."""

    instructions: str
    criteria: dict[str, str]


@dataclass
class Noul:
    """Declares a boolean (0-1 probability) question."""

    instructions: str
    criteria: dict[str, str] | None = None


@dataclass
class Score:
    """Declares a ranked-scale question."""

    instructions: str
    criteria: list[str]


@dataclass
class ChoiceAnswer:
    """Typed answer to a `Choice` question."""

    choice: str
    confidence: float
    probabilities: dict[str, float]


@dataclass
class NoulAnswer:
    """Typed answer to a `Noul` question."""

    noul: float


@dataclass
class ScoreAnswer:
    """Typed answer to a `Score` question."""

    score: float
    confidence: float
    probabilities: dict[str, float]


@dataclass
class SystemOneResponse:
    """Mirrors the real SDK's response envelope."""

    model: str
    answers: dict[str, ChoiceAnswer | NoulAnswer | ScoreAnswer]
    usage: dict[str, int]


def _keyword_score(text: str, keywords: dict[str, float]) -> float:
    """Deterministically scores text against a keyword table (0-1)."""
    lowered = text.lower()
    score = sum(weight for keyword, weight in keywords.items() if keyword in lowered)
    return max(0.0, min(1.0, score))


class TypeSafeClient:
    """Mock stand-in for `typesafe_sdk.TypeSafeClient`.

    Simulates a fast, deterministic "System One" model: instead of an LLM
    call, it scores keyword signals in the ticket text to produce calibrated
    typed answers, matching the shape the real API documents (see
    https://developers.cloudflare.com/ai/models/typesafe/jev/).
    """

    def __init__(self, model: str = "jev-1.13.0-mock") -> None:
        self.model = model

    def system_one(
        self, *, state: dict[str, Any], questions: dict[str, Choice | Noul | Score]
    ) -> SystemOneResponse:
        text = " ".join(
            str(value) for key in ("subject", "message") if (value := state.get(key))
        )

        answers: dict[str, ChoiceAnswer | NoulAnswer | ScoreAnswer] = {}
        for name, question in questions.items():
            if isinstance(question, Choice):
                answers[name] = self._answer_choice(text, question)
            elif isinstance(question, Noul):
                answers[name] = self._answer_noul(text)
            elif isinstance(question, Score):
                answers[name] = self._answer_score(text, question)
            else:  # pragma: no cover - defensive
                raise TypeError(f"Unsupported question type for {name!r}: {question!r}")

        input_tokens = len(text.split()) * 2 + 40
        return SystemOneResponse(
            model=self.model,
            answers=answers,
            usage={"input_tokens": input_tokens, "output_tokens": len(answers) * 12},
        )

    def _answer_choice(self, text: str, question: Choice) -> ChoiceAnswer:
        department_keywords = {
            "billing": {
                "charge": 0.6,
                "refund": 0.6,
                "invoice": 0.6,
                "payment": 0.5,
                "subscription": 0.4,
            },
            "technical": {
                "error": 0.6,
                "bug": 0.6,
                "crash": 0.6,
                "down": 0.5,
                "not working": 0.5,
                "integration": 0.4,
            },
            "sales": {
                "pricing": 0.6,
                "upgrade": 0.6,
                "plan": 0.4,
                "demo": 0.5,
                "quote": 0.5,
            },
        }
        raw_scores = {
            option: _keyword_score(text, department_keywords.get(option, {}))
            for option in question.criteria
        }
        # Deterministic tie-break salt so identical zero-scores don't all pick option 1.
        for option in raw_scores:
            salt = (
                int(hashlib.sha256(f"{text}|{option}".encode()).hexdigest(), 16) % 100
            )
            raw_scores[option] += salt / 10_000

        total = sum(raw_scores.values()) or 1.0
        probabilities = {k: round(v / total, 4) for k, v in raw_scores.items()}
        best = max(probabilities, key=probabilities.get)
        return ChoiceAnswer(
            choice=best, confidence=probabilities[best], probabilities=probabilities
        )

    def _answer_noul(self, text: str) -> NoulAnswer:
        urgency_keywords = {
            "urgent": 0.5,
            "immediately": 0.4,
            "asap": 0.5,
            "critical": 0.5,
            "down": 0.3,
            "for 3 days": 0.3,
            "for days": 0.3,
            "right now": 0.4,
        }
        return NoulAnswer(noul=round(_keyword_score(text, urgency_keywords), 4))

    def _answer_score(self, text: str, question: Score) -> ScoreAnswer:
        anger_keywords = {
            "furious": 1.0,
            "angry": 0.8,
            "unacceptable": 0.7,
            "terrible": 0.6,
            "frustrated": 0.5,
            "disappointed": 0.4,
            "please": -0.1,
            "thanks": -0.2,
        }
        intensity = _keyword_score(text, anger_keywords)
        max_level = len(question.criteria) - 1
        score = round(intensity * max_level, 4)
        low, high = int(score), min(int(score) + 1, max_level)
        frac = score - low
        probabilities = {str(i): 0.0 for i in range(len(question.criteria))}
        if low == high:
            probabilities[str(low)] = 1.0
        else:
            probabilities[str(low)] = round(1 - frac, 4)
            probabilities[str(high)] = round(frac, 4)
        confidence = round(max(probabilities.values()), 4)
        return ScoreAnswer(
            score=score, confidence=confidence, probabilities=probabilities
        )
