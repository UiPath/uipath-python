"""TeleCom customer support email classification agent."""

from dataclasses import dataclass

from uipath.tracing import traced

PAYMENT_KEYWORDS = {"payment", "bill", "invoice", "charge", "balance", "due", "overdue"}
PLAN_KEYWORDS = {
    "plan",
    "upgrade",
    "data",
    "unlimited",
    "downgrade",
    "subscription",
    "gb",
}


@dataclass
class ClassificationInput:
    email_subject: str
    email_body: str


@dataclass
class ClassificationOutput:
    category: str


@traced(name="classify_email", span_type="tool")
def classify_email(subject: str, body: str) -> str:
    """Classify an email into a category based on keyword matching."""
    text = f"{subject} {body}".lower()
    tokens = set(text.split())

    payment_hits = len(tokens & PAYMENT_KEYWORDS)
    plan_hits = len(tokens & PLAN_KEYWORDS)

    if payment_hits > plan_hits:
        return "payments"
    if plan_hits > payment_hits:
        return "plan_details"
    if payment_hits > 0:
        return "payments"

    return "spam"


@traced()
async def main(input: ClassificationInput) -> ClassificationOutput:
    """Classify a customer support email for TeleCom Telecom."""
    category = classify_email(input.email_subject, input.email_body)
    return ClassificationOutput(category=category)
