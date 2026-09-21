# Ticket Triage Agent: System 1 / System 2 Pattern

This sample demonstrates a two-tier triage pattern for support tickets:

1. **Tier 1 (System 1) - fast structured triage.** A "System One" model
   takes the ticket text and a set of typed questions, and returns
   calibrated typed answers (a classification, a 0-1 probability, and a
   score) instead of free text - orders of magnitude cheaper and faster than an
   LLM call. This sample uses TypeSafe AI's `Jev` model via the
   `typesafe-sdk` package.
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

This sample calls TypeSafe AI's real `typesafe-sdk` PyPI package, not a
mock. `typesafe-sdk` is a very recently published package (it went out the
same day this sample was first written, with several releases in one day),
so before wiring it in we statically inspected the wheel's source (no
install/execution): it's a normal, apparently auto-generated API client
(the response schemas reference an OpenAPI spec) with no `eval`/`exec`/
`subprocess` calls, no exfiltration of environment variables, and a single
documented API host (`api.typesafe.ai`). Its `httpx2` dependency is a real,
independent package (also used by the `mcp` SDK) unrelated to TypeSafe AI.
If you're pulling this into your own project, do your own review before
trusting a same-day release.

```python
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

client = TypeSafeClient()  # reads TYPESAFE_API_KEY from the environment
response = client.system_one(state=..., questions={...})
```

`pyproject.toml` pins `typesafe-sdk>=0.7.0` rather than leaving it
unbounded, since `uipath`'s own `uv` install already applies a
minimum-package-age safety check that skips the very newest release.

## Prerequisites

* [UV package manager](https://docs.astral.sh/uv/) installed
* A TypeSafe AI API key (`TYPESAFE_API_KEY`) for the Tier 1 triage step
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

Copy `.env.example` to `.env` and fill in your Orchestrator URL, access
token, and TypeSafe AI API key:

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

1. `triage_ticket` sends the ticket's subject/message to `Jev` (via
   `TypeSafeClient.system_one`) as `state`, along with three typed
   `questions` (`department: Choice`, `is_urgent: Noul`,
   `frustration: Score`), and gets back a `TriageDecision`.
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
