# Ticket Triage Agent: System 1 / System 2 Pattern

This sample demonstrates a two-tier triage pattern for support tickets:

1. **Tier 1 (System 1) - fast structured triage.** A "System One" model
   takes the ticket text and a set of typed questions, and returns
   calibrated typed answers (a classification, a boolean, and a score)
   instead of free text - orders of magnitude cheaper and faster than an
   LLM call. This sample stubs that tier with a mock of TypeSafe AI's `Jev`
   model.
2. **Tier 2 (System 2) - branch on the triage result.**
   - If the ticket is urgent, the customer sounds frustrated, or the
     department routing is low-confidence, the agent **escalates to a
     human** via a UiPath Action Center QuickForm task, attaching the Tier 1
     decision as context so the reviewer isn't starting cold.
   - Otherwise, the agent calls a **real LLM** (UiPath LLM Gateway) with a
     department-specific system prompt to draft a reply, and returns it as
     an auto-resolved ticket. No human, and no expensive LLM call for
     routing, is needed for the common case.

## About the "Jev" model (important - read this)

**`jev_client.py` in this sample is a local mock, not a real UiPath or
TypeSafe AI integration.** TypeSafe AI's real `typesafe-sdk` PyPI package
was published the same day this sample was written, already has several
releases, and lists an unusual dependency (`httpx2` instead of `httpx`).
Rather than pull an unverified, very-recently-published third-party package
into this SDK's samples, `jev_client.py` hand-rolls a small deterministic
stand-in that mirrors the real SDK's documented public shape:

```python
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

client = TypeSafeClient()
response = client.system_one(state=..., questions={...})
```

The mock scores keyword signals in the ticket text instead of calling any
external model, so this sample runs fully offline. If you want to use the
real `typesafe-sdk` package, **independently vet it first**, then swap the
import in `main.py` (`from jev_client import ...` -> `from typesafe_sdk
import ...`) and add it to `pyproject.toml` - the public shape used here
(`TypeSafeClient`, `Choice`/`Noul`/`Score`, `.system_one(...)`) is designed
to match the real SDK, so no other code should need to change.

**No API key is needed to run this sample.** `jev_client.py` is a local,
offline mock and reads no environment variables. `TYPESAFE_API_KEY` (in
`.env.example`, commented out) would only be needed if you later swap in
the real `typesafe-sdk` package, after independently vetting it.

## Prerequisites

* [UV package manager](https://docs.astral.sh/uv/) installed
* A UiPath Orchestrator tenant with:
  * Access to the LLM Gateway (for the auto-reply path)
  * Access to Action Center (for the escalation path)

## Setup

### Step 1: Create and activate a virtual environment

```bash
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

### Step 2: Install dependencies

```bash
uv sync
```

### Step 3: Configure credentials

Copy `.env.example` to `.env` and fill in your Orchestrator URL and access
token:

```bash
cp .env.example .env
```

### Step 4: Initialize the agent

```bash
uv run uipath init
```

### Step 5: Run the agent

```bash
uipath run main --input-file input.json
```

Try editing `input.json` to see both branches:

* A calm, clearly-worded billing request (like the default input) -> the
  agent auto-drafts a reply via the LLM Gateway and returns it directly.
* An urgent or angry-sounding message (e.g. mentioning "urgent", "ASAP", or
  "furious") -> the agent creates an Action Center task instead and returns
  its task id.

## How it works

1. `triage_ticket` sends the ticket's subject/message to the mock `Jev`
   client as `state`, along with three typed `questions`
   (`department: Choice`, `is_urgent: Noul`, `frustration: Score`), and gets
   back a `TriageDecision`.
2. `needs_escalation` checks the triage output against fixed thresholds
   (urgency, frustration, routing confidence) in `main.py`.
3. On escalation, `escalate_to_human` creates an Action Center QuickForm
   task via `client.tasks.create_quickform(...)`, with the ticket and the
   triage decision as task data for the reviewer.
4. Otherwise, `draft_auto_reply` calls `client.llm.chat_completions(...)`
   (UiPath LLM Gateway) with a department-specific system prompt to draft a
   reply.

## Evaluations

`evaluations/eval-sets/default.json` exercises the Tier 1 routing/escalation
logic against 11 tickets (billing, technical, and sales; calm and
auto-replied vs. urgent/angry/low-confidence and escalated), using two
evaluators:

* `DepartmentRoutingEvaluator` (`evaluations/evaluators/department-routing.json`)
  - a `uipath-multiclass-classification` evaluator checking
  `triage.department` against the expected class.
* `EscalationDecisionEvaluator` (`evaluations/evaluators/escalation-decision.json`)
  - a `uipath-binary-classification` evaluator checking the `escalated`
  boolean against the expected outcome.

Two cases (`sales-demo-request-wrong-department`,
`billing-refund-calm-wrong-escalation`) have deliberately wrong ground truth,
mirroring the pattern in `classification_agent`, to demonstrate the
evaluators catching a mismatch.

Since `draft_auto_reply` and `escalate_to_human` call real UiPath services
(LLM Gateway, Action Center), running the full eval set end-to-end requires
valid credentials in `.env`:

```bash
uipath eval
```

## Publish your coded agent

Once tested locally, publish the agent to Orchestrator:

```bash
uipath pack
uipath publish
```
