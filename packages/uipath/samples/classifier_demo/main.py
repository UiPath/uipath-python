"""Tiny intent-classification agent for the ClassifierEvaluator demo.

Given an utterance, returns the intent label. Three intents:
  - book        (anything containing "book" / "reserve" / "schedule")
  - cancel      (anything containing "cancel" / "void")
  - reschedule  (anything containing "reschedule" / "move")

A few datapoints are deliberately misclassified so the run-level
classification metrics (precision/recall/F-score) come out non-trivially.
"""

from dataclasses import dataclass


@dataclass
class IntentInput:
    utterance: str


@dataclass
class IntentOutput:
    intent: str


BOOK_KEYWORDS = {"book", "reserve", "schedule"}
CANCEL_KEYWORDS = {"cancel", "void"}
RESCHEDULE_KEYWORDS = {"reschedule", "move"}


async def main(input: IntentInput) -> IntentOutput:
    """Classify the utterance into book / cancel / reschedule."""
    text = input.utterance.lower()
    tokens = set(text.split())

    if tokens & RESCHEDULE_KEYWORDS:
        return IntentOutput(intent="reschedule")
    if tokens & CANCEL_KEYWORDS:
        return IntentOutput(intent="cancel")
    if tokens & BOOK_KEYWORDS:
        return IntentOutput(intent="book")
    # Fallback to "book" — deliberately wrong-ish so the matrix is interesting.
    return IntentOutput(intent="book")
