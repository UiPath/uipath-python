"""Rule-based spam/ham classifier demonstrating the binary classification evaluator."""

from dataclasses import dataclass

from uipath.tracing import traced

SPAMMY_TOKENS = {
    "free",
    "winner",
    "congratulations",
    "click here",
    "prize",
    "!!!",
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
    """Return 'spam' if any spam-indicator token appears in the subject or body."""
    text = f"{subject} {body}".lower()
    return "spam" if any(token in text for token in SPAMMY_TOKENS) else "ham"


@traced()
async def main(input: EmailInput) -> Classification:
    """Classify an email as 'spam' or 'ham'."""
    category = classify_email(input.email_subject, input.email_body)
    return Classification(category=category)
