"""Rule-based 3-class email router demonstrating the multiclass classification evaluator."""

from dataclasses import dataclass

from uipath.tracing import traced

SPAM_TOKENS = {"free", "winner", "congratulations", "click here", "prize", "!!!"}
PAYMENT_TOKENS = {"invoice", "payment", "refund", "charge", "billing", "$"}
SUPPORT_TOKENS = {
    "help",
    "support",
    "issue",
    "error",
    "ticket",
    "broken",
    "not working",
}


@dataclass
class EmailInput:
    email_subject: str
    email_body: str


@dataclass
class Classification:
    category: str


@traced(name="classify_email", span_type="tool")
def classify_email(subject: str, body: str) -> str:
    """Classify into 'spam', 'payments', or 'support' using priority rules.

    Spam is checked first so promos with billing-flavored words still route to spam.
    Payments is checked before support because it is the more specific intent.
    Support is the catch-all default.
    """
    text = f"{subject} {body}".lower()
    if any(token in text for token in SPAM_TOKENS):
        return "spam"
    if any(token in text for token in PAYMENT_TOKENS):
        return "payments"
    return "support"


@traced()
async def main(input: EmailInput) -> Classification:
    """Route an email to one of three queues."""
    category = classify_email(input.email_subject, input.email_body)
    return Classification(category=category)
