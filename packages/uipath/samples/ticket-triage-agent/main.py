"""Two-tier support-ticket triage agent.

Demonstrates a "System 1 / System 2" pattern:

1.  Tier 1 (System 1) - a fast, cheap, structured-decision model triages the
    ticket: which department it belongs to, whether it's urgent, and how
    frustrated the customer sounds. Uses TypeSafe AI's `typesafe-sdk` and
    its "Jev" System One model (requires TYPESAFE_API_KEY; see README.md).
2.  Tier 2 (System 2) - branches on the triage result:
      * High urgency/frustration, or low routing confidence -> escalate to a
        human via a UiPath Action Center QuickForm task (HITL), with the
        Tier 1 decision attached as context.
      * Otherwise -> call a real LLM (UiPath LLM Gateway) to draft a reply
        for the routed department and mark the ticket resolved.
"""

from __future__ import annotations

import os

from pydantic import BaseModel, Field
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

from uipath.platform import UiPath
from uipath.platform.chat import ChatModels
from uipath.tracing import traced

# --- Tunable escalation thresholds -----------------------------------------
URGENCY_THRESHOLD = 0.6
FRUSTRATION_THRESHOLD = 1.0  # out of 2 ("Calm" / "Frustrated" / "Very angry")
ROUTING_CONFIDENCE_THRESHOLD = 0.45

# Fixed schema key for the QuickForm task this sample registers/reuses.
TRIAGE_TASK_SCHEMA_KEY = "5b6f7e2a-3c9d-4e11-9a2b-6d1f0c9a2e77"

DEPARTMENT_SYSTEM_PROMPTS = {
    "billing": (
        "You are a billing support agent. Write a short, polite reply that "
        "acknowledges the customer's billing issue and explains next steps."
    ),
    "technical": (
        "You are a technical support agent. Write a short, polite reply "
        "acknowledging the technical issue and the troubleshooting steps "
        "that will follow."
    ),
    "sales": (
        "You are a sales representative. Write a short, polite reply "
        "addressing the customer's pricing or account question."
    ),
}


class TicketInput(BaseModel):
    """A support ticket to triage."""

    subject: str = Field(description="Ticket subject line")
    message: str = Field(description="Ticket body / customer message")


class TriageDecision(BaseModel):
    """Tier 1 (Jev) structured triage output."""

    department: str
    department_confidence: float
    is_urgent: float
    frustration_score: float


class TicketOutput(BaseModel):
    """Final agent output."""

    triage: TriageDecision
    escalated: bool
    auto_reply: str | None = Field(
        default=None, description="LLM-drafted reply, when auto-handled"
    )
    action_task_id: int | None = Field(
        default=None, description="Action Center task id, when escalated"
    )


@traced()
def triage_ticket(ticket: TicketInput) -> TriageDecision:
    """Run the fast Tier 1 structured triage over the ticket."""
    client = TypeSafeClient()
    response = client.system_one(
        state={"subject": ticket.subject, "message": ticket.message},
        questions={
            "department": Choice(
                instructions="Which team should handle this ticket?",
                criteria={
                    "billing": "Payments, invoicing, refunds, subscriptions",
                    "technical": "Bugs, outages, integrations, errors",
                    "sales": "Pricing, upgrades, new accounts, demos",
                },
            ),
            "is_urgent": Noul(instructions="Does this convey urgency?"),
            "frustration": Score(
                instructions="How frustrated does the customer sound?",
                criteria=["Calm", "Frustrated", "Very angry"],
            ),
        },
    )
    department = response.answers["department"]
    is_urgent = response.answers["is_urgent"]
    frustration = response.answers["frustration"]
    return TriageDecision(
        department=department.choice,
        department_confidence=department.confidence,
        is_urgent=is_urgent.noul,
        frustration_score=frustration.score,
    )


def needs_escalation(triage: TriageDecision) -> bool:
    """Decide whether the ticket should go to a human instead of auto-reply."""
    return (
        triage.is_urgent >= URGENCY_THRESHOLD
        or triage.frustration_score >= FRUSTRATION_THRESHOLD
        or triage.department_confidence < ROUTING_CONFIDENCE_THRESHOLD
    )


@traced()
def escalate_to_human(
    client: UiPath, ticket: TicketInput, triage: TriageDecision
) -> int:
    """Create an Action Center QuickForm task for a human reviewer."""
    folder_path = os.environ.get("UIPATH_FOLDER_PATH", "").strip()
    if not folder_path:
        raise RuntimeError(
            "UIPATH_FOLDER_PATH is not set. Action Center tasks must be "
            "created in an Orchestrator folder; set it in .env (see "
            ".env.example)."
        )

    schema = {
        "id": TRIAGE_TASK_SCHEMA_KEY,
        "fields": [
            {"id": "subject", "type": "text", "label": "Subject", "direction": "input"},
            {"id": "message", "type": "text", "label": "Message", "direction": "input"},
            {
                "id": "department",
                "type": "text",
                "label": "Suggested department",
                "direction": "input",
            },
            {
                "id": "urgency",
                "type": "text",
                "label": "Urgency score",
                "direction": "input",
            },
            {
                "id": "frustration",
                "type": "text",
                "label": "Frustration score",
                "direction": "input",
            },
            {
                "id": "reply",
                "type": "text",
                "label": "Reviewer reply",
                "direction": "output",
            },
        ],
        "outcomes": [
            {"id": "resolve", "name": "Resolve", "type": "string", "isPrimary": True},
        ],
    }
    task = client.tasks.create_quickform(
        title=f"Review ticket: {ticket.subject}",
        task_schema_key=TRIAGE_TASK_SCHEMA_KEY,
        schema=schema,
        data={
            "subject": ticket.subject,
            "message": ticket.message,
            "department": f"{triage.department} ({triage.department_confidence:.0%} confidence)",
            "urgency": f"{triage.is_urgent:.2f}",
            "frustration": f"{triage.frustration_score:.2f}",
        },
        priority="High" if triage.is_urgent >= URGENCY_THRESHOLD else "Medium",
        folder_path=folder_path,
    )
    if task.id is None:
        raise RuntimeError(
            "Action Center did not return a task id for the created task."
        )
    return task.id


@traced()
async def draft_auto_reply(
    client: UiPath, ticket: TicketInput, triage: TriageDecision
) -> str:
    """Use a real LLM to draft a reply for a routine, non-urgent ticket."""
    system_prompt = DEPARTMENT_SYSTEM_PROMPTS.get(
        triage.department, DEPARTMENT_SYSTEM_PROMPTS["technical"]
    )
    result = await client.llm.chat_completions(
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Subject: {ticket.subject}\n\n{ticket.message}",
            },
        ],
        model=ChatModels.gpt_4_1_mini_2025_04_14,
        max_tokens=300,
        temperature=0.3,
    )
    return result.choices[0].message.content or ""


@traced()
async def main(input: TicketInput) -> TicketOutput:
    """Triage a ticket and either auto-reply or escalate to a human."""
    triage = triage_ticket(input)
    client = UiPath()

    if needs_escalation(triage):
        task_id = escalate_to_human(client, input, triage)
        return TicketOutput(triage=triage, escalated=True, action_task_id=task_id)

    reply = await draft_auto_reply(client, input, triage)
    return TicketOutput(triage=triage, escalated=False, auto_reply=reply)
