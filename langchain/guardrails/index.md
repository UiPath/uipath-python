# Guardrails

Guardrails inspect inputs and outputs for policy violations — PII, harmful content, prompt injection, intellectual property, and custom rules — and respond by logging, blocking, or modifying the data.

The UiPath LangChain SDK exposes two complementary patterns:

- **Middleware** — a LangChain-native approach. Guardrail classes are passed as a list to `create_agent(..., middleware=[...])`. Each class registers hooks (`before_agent`, `after_agent`, `before_model`, `after_model`, `wrap_tool_call`) automatically for the configured scope.
- **Decorator** — the same `@guardrail` API from the core SDK, extended to understand LangChain/LangGraph objects. Scope is inferred automatically from the decorated target type.

For the full list of validators, actions, execution stages, and the low-level API, see the [core guardrails documentation](https://uipath.github.io/uipath-python/core/guardrails/).

______________________________________________________________________

## Middleware pattern

Middleware is the preferred approach when all guardrail configuration should live in one place, next to the `create_agent()` call.

### How it works

Each built-in middleware class is **iterable** — unpacking it with `*` yields one or more `AgentMiddleware` hook objects that LangChain registers internally. Pass them all inside the `middleware=[]` list:

```
from langchain.agents import create_agent

agent = create_agent(
    model=llm,
    tools=[my_tool],
    system_prompt=SYSTEM_PROMPT,
    middleware=[
        *UiPathPIIDetectionMiddleware(...),
        *UiPathHarmfulContentMiddleware(...),
        # ... more middleware
    ],
)
```

### Imports

```
from uipath_langchain.guardrails import (
    BlockAction,
    EscalateAction,
    LogAction,
    LoggingSeverityLevel,
    UiPathDeterministicGuardrailMiddleware,
    UiPathHarmfulContentMiddleware,
    UiPathIntellectualPropertyMiddleware,
    UiPathLLMAsJudgeMiddleware,
    UiPathPIIDetectionMiddleware,
    UiPathUserPromptAttacksMiddleware,
    PIIDetectionEntity,
    HarmfulContentEntity,
    GuardrailExecutionStage,
)
from uipath_langchain.guardrails.enums import (
    HarmfulContentEntityType,
    IntellectualPropertyEntityType,
    PIIDetectionEntityType,
)
from uipath.core.guardrails import GuardrailScope
```

### Built-in middleware classes

| Class                                    | Supported scopes | Stage support             | Extra parameters                                                                                   |
| ---------------------------------------- | ---------------- | ------------------------- | -------------------------------------------------------------------------------------------------- |
| `UiPathPIIDetectionMiddleware`           | AGENT, LLM, TOOL | PRE / POST / PRE_AND_POST | `entities`, `tools`, `stage`                                                                       |
| `UiPathHarmfulContentMiddleware`         | AGENT, LLM, TOOL | PRE / POST / PRE_AND_POST | `entities`, `tools`, `stage`                                                                       |
| `UiPathUserPromptAttacksMiddleware`      | LLM only         | PRE only                  | —                                                                                                  |
| `UiPathIntellectualPropertyMiddleware`   | AGENT, LLM only  | POST only                 | `entities`                                                                                         |
| `UiPathLLMAsJudgeMiddleware`             | AGENT, LLM, TOOL | PRE / POST / PRE_AND_POST | `guardrail_text`, `model`, `threshold`, `positive_examples`, `negative_examples`, `tools`, `stage` |
| `UiPathDeterministicGuardrailMiddleware` | TOOL only        | PRE / POST / PRE_AND_POST | `tools`, `rules`, `stage`                                                                          |

TOOL scope for `UiPathPIIDetectionMiddleware`, `UiPathHarmfulContentMiddleware`, and `UiPathLLMAsJudgeMiddleware` requires passing `tools=[...]` to restrict `wrap_tool_call` hooks to specific tools.

All classes share these common parameters:

- **`name`** (`str`) — display name for this guardrail instance.
- **`action`** — what to do on violation: `LogAction(...)`, `BlockAction(...)`, or `EscalateAction(...)` (escalate to a human — see [Escalation action](#escalation-action-human-in-the-loop)).
- **`scopes`** (`list[GuardrailScope]`) — restrict which hooks are registered. Defaults shown in the table above. Use `GuardrailScope.AGENT`, `GuardrailScope.LLM`, `GuardrailScope.TOOL`.
- **`enabled_for_evals`** (`bool`, default `True`) — set `False` to skip this guardrail when the agent runs in evaluation mode.

Additional parameters per class:

- **`UiPathPIIDetectionMiddleware`** / **`UiPathHarmfulContentMiddleware`**: `entities` (list of entity configs), `tools` (restrict TOOL-scope hooks to specific tools), `stage`.
- **`UiPathUserPromptAttacksMiddleware`**: no extra parameters.
- **`UiPathIntellectualPropertyMiddleware`**: `entities` (list of `IntellectualPropertyEntityType` values).
- **`UiPathLLMAsJudgeMiddleware`**: `guardrail_text` (required — the plain-language rule the judge evaluates against, ≤ 4000 chars), `model` (required — judge model id, e.g. `"gpt-4o-2024-08-06"`; must be a model your governance policy allows for the LLM-as-judge guardrail — LLM Gateway enforces the permitted list), `threshold` (`0` strictest … `6` most lenient, default `2`), `positive_examples` / `negative_examples` (optional calibration payloads — ≤ 2 each, ≤ 1000 chars each), `tools` (required only when `GuardrailScope.TOOL` is used), `stage`. See the [core guardrails documentation](https://uipath.github.io/uipath-python/core/guardrails/#llm-as-judge) for the full parameter reference.
- **`UiPathDeterministicGuardrailMiddleware`**: `tools` (required — list of tools to guard), `rules` (list of lambda functions), `stage`.

### Full example

```
from langchain.agents import create_agent
from langchain_core.tools import tool
from uipath_langchain.chat import UiPathChat
from uipath_langchain.guardrails import (
    BlockAction,
    LogAction,
    LoggingSeverityLevel,
    UiPathDeterministicGuardrailMiddleware,
    UiPathHarmfulContentMiddleware,
    UiPathIntellectualPropertyMiddleware,
    UiPathLLMAsJudgeMiddleware,
    UiPathPIIDetectionMiddleware,
    UiPathUserPromptAttacksMiddleware,
    PIIDetectionEntity,
    HarmfulContentEntity,
    GuardrailExecutionStage,
)
from uipath_langchain.guardrails.enums import (
    HarmfulContentEntityType,
    IntellectualPropertyEntityType,
    PIIDetectionEntityType,
)
from uipath.core.guardrails import GuardrailScope


@tool
def analyze_text(text: str) -> str:
    """Count words in the provided text."""
    return f"Word count: {len(text.split())}"


llm = UiPathChat(model="gpt-4o-2024-08-06")

agent = create_agent(
    model=llm,
    tools=[analyze_text],
    system_prompt="You are a helpful assistant.",
    middleware=[
        # PII detection on agent input/output and LLM messages
        *UiPathPIIDetectionMiddleware(
            name="PII detector",
            scopes=[GuardrailScope.AGENT, GuardrailScope.LLM],
            action=LogAction(severity_level=LoggingSeverityLevel.WARNING),
            entities=[
                PIIDetectionEntity(PIIDetectionEntityType.EMAIL, threshold=0.5),
                PIIDetectionEntity(PIIDetectionEntityType.CREDIT_CARD_NUMBER, threshold=0.5),
            ],
        ),
        # PII detection restricted to TOOL scope for specific tools
        *UiPathPIIDetectionMiddleware(
            name="Tool PII detector",
            scopes=[GuardrailScope.TOOL],
            action=LogAction(severity_level=LoggingSeverityLevel.WARNING),
            entities=[
                PIIDetectionEntity(PIIDetectionEntityType.PHONE_NUMBER, threshold=0.5),
            ],
            tools=[analyze_text],
            enabled_for_evals=False,
        ),
        # Block adversarial user prompts at the LLM level
        *UiPathUserPromptAttacksMiddleware(
            name="User prompt attacks",
            action=BlockAction(),
            enabled_for_evals=False,
        ),
        # Block harmful content in agent + LLM messages
        *UiPathHarmfulContentMiddleware(
            name="Harmful content",
            scopes=[GuardrailScope.AGENT, GuardrailScope.LLM],
            action=BlockAction(),
            entities=[
                HarmfulContentEntity(HarmfulContentEntityType.VIOLENCE, threshold=2),
            ],
        ),
        # Log IP violations in LLM output (POST only)
        *UiPathIntellectualPropertyMiddleware(
            name="IP detection",
            scopes=[GuardrailScope.LLM],
            action=LogAction(severity_level=LoggingSeverityLevel.WARNING),
            entities=[IntellectualPropertyEntityType.TEXT],
        ),
        # LLM-as-judge: block responses that violate a plain-language rule (POST)
        *UiPathLLMAsJudgeMiddleware(
            name="No financial advice",
            scopes=[GuardrailScope.AGENT],
            action=BlockAction(),
            guardrail_text=(
                "The response must remain professional and must not contain "
                "financial or investment advice."
            ),
            model="gpt-4o-2024-08-06",
            stage=GuardrailExecutionStage.POST,
        ),
        # Deterministic: block tool input longer than 1000 chars
        *UiPathDeterministicGuardrailMiddleware(
            tools=[analyze_text],
            rules=[lambda data: len(data.get("text", "")) > 1000],
            action=BlockAction(detail="Input too long"),
            stage=GuardrailExecutionStage.PRE,
            name="Length limiter",
        ),
    ],
)
```

### Deterministic middleware

`UiPathDeterministicGuardrailMiddleware` applies in-process rule functions without any API call.

- **`rules`** — list of callables. For `PRE` stage: `(input_dict: dict) -> bool`. For `POST` stage: `(input_dict: dict, output_dict: dict) -> bool`. Return `True` to signal a violation.
- **`rules=[]`** (empty list) — always triggers the action, useful for unconditional transforms.
- **`stage`** — `GuardrailExecutionStage.PRE`, `POST`, or `PRE_AND_POST`.

```
# Always replace a word in tool output (unconditional transform, empty rules)
*UiPathDeterministicGuardrailMiddleware(
    tools=[analyze_text],
    rules=[],
    action=CustomFilterAction(word_to_filter="count", replacement="total"),
    stage=GuardrailExecutionStage.POST,
    name="Output transformer",
),
```

### Custom middleware hooks

For logic that doesn't fit a built-in class, implement raw middleware hooks using the `langchain.agents.middleware` decorators and pass them directly to the middleware list.

Available hook decorators: `before_agent`, `after_agent`, `before_model`, `after_model`, `wrap_tool_call`.

```
from langchain.agents.middleware import AgentState, before_agent, after_agent
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime


@before_agent
async def log_agent_input(state: AgentState, runtime: Runtime) -> None:
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            print(f"[INPUT] {msg.content}")
            break


@after_agent
async def log_agent_output(state: AgentState, runtime: Runtime) -> None:
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, AIMessage):
            print(f"[OUTPUT] {msg.content}")
            break


LoggingMiddleware = [log_agent_input, log_agent_output]

agent = create_agent(
    model=llm,
    tools=[analyze_text],
    middleware=[
        *LoggingMiddleware,
        *UiPathPIIDetectionMiddleware(...),
    ],
)
```

### Escalation action (human-in-the-loop)

`EscalateAction` routes a violation to a **human reviewer** instead of logging or blocking it. On a violation it builds the review payload and calls the documented HITL primitive [`interrupt(CreateEscalation(...))`](https://uipath.github.io/uipath-python/langchain/human_in_the_loop/#createescalation) — creating a task in a UiPath **Action App** and **suspending the run** until the reviewer responds. On resume:

- **Approve** — if the reviewer edited the content, the edited value is substituted back into the flagged message / tool args / output; otherwise the original is kept. The edit is read from `ReviewedInputs` for a PRE (input) escalation and `ReviewedOutputs` for a POST (output) one.
- **Reject** — raises `GuardrailBlockException`, terminating the run.

```
from uipath_langchain.guardrails import EscalateAction
from uipath.platform.action_center.tasks import TaskRecipient, TaskRecipientType

*UiPathPIIDetectionMiddleware(
    name="PII escalation",
    scopes=[GuardrailScope.AGENT],
    stage=GuardrailExecutionStage.PRE,   # validate once → escalate once per run
    action=EscalateAction(
        app_name="Guardrail Escalation Action App",
        app_folder_path="Shared",
        # route the review task to a specific recipient (user / group / email)
        recipient=TaskRecipient(
            type=TaskRecipientType.EMAIL, value="reviewer@example.com"
        ),
    ),
    entities=[PIIDetectionEntity(PIIDetectionEntityType.EMAIL, threshold=0.5)],
),
```

Parameters:

- **`app_name`** (`str`, required) — the published Action App that renders the review task.
- **`app_folder_path`** (`str`) — folder where the app is deployed.
- **`assignee`** (`str`) — the simple username/email to assign the task to.
- **`recipient`** (`TaskRecipient`) — a typed escalation target (shown above); takes precedence over `assignee`. Supports the four `TaskRecipientType` members — `USER_ID`, `GROUP_ID`, `EMAIL` (user email), and `GROUP_NAME`, e.g. `TaskRecipient(type=TaskRecipientType.GROUP_NAME, value="Reviewers")`.
- **`title`** (`str`) — task title; defaults to a message derived from the guardrail name.

> 💡 **Escalate once per run.** On AGENT/LLM scope a guardrail validates both *before* and *after* by default, which can escalate twice. Set `stage=GuardrailExecutionStage.PRE` (or `POST`) so only a single checkpoint is registered.
>
> ⚠️ **Requires a published Action App.** The target app must exist in the configured folder for the task to be created. Resume is durable — the run suspends on `interrupt()` and resumes when the task is completed. See [Human In The Loop](https://uipath.github.io/uipath-python/langchain/human_in_the_loop/) for the underlying primitive.

### Custom actions

Both the built-in middleware and `UiPathDeterministicGuardrailMiddleware` accept any `GuardrailAction` subclass as the `action` parameter. This lets you implement content sanitisation, redaction, or any other custom response to a violation:

```
import re
from dataclasses import dataclass
from typing import Any
from uipath.core.guardrails import GuardrailValidationResult, GuardrailValidationResultType
from uipath_langchain.guardrails import GuardrailAction


@dataclass
class RedactAction(GuardrailAction):
    pattern: str
    replacement: str = "[REDACTED]"

    def handle_validation_result(
        self,
        result: GuardrailValidationResult,
        data: str | dict[str, Any],
        guardrail_name: str,
    ) -> str | dict[str, Any] | None:
        if result.result != GuardrailValidationResultType.VALIDATION_FAILED:
            return None
        if isinstance(data, str):
            return re.sub(self.pattern, self.replacement, data, flags=re.IGNORECASE)
        return None
```

______________________________________________________________________

## Decorator pattern

Importing `uipath_langchain.guardrails` auto-registers a LangChain adapter that extends `@guardrail` to wrap LangChain/LangGraph objects in addition to plain Python callables. All validators, actions, execution stages, stacking, and `GuardrailExclude` work exactly as described in the [core guardrails documentation](https://uipath.github.io/uipath-python/core/guardrails/) — use `uipath_langchain.guardrails` as the import path, which re-exports everything from the core SDK.

```
from uipath_langchain.guardrails import guardrail, PIIValidator, BlockAction, ...
```

### LangChain target types

On LangChain objects, scope is **inferred automatically** from the target — no `stage` inference, but no explicit `scopes=` parameter is needed either:

| Decorated target          | Inferred scope | Notes                                                 |
| ------------------------- | -------------- | ----------------------------------------------------- |
| `@tool` function          | TOOL           | `@guardrail` must be placed **above** `@tool`         |
| `BaseChatModel` factory   | LLM            | Decorate the factory function, not the model instance |
| `create_agent()` factory  | AGENT          | Decorate the factory function, not the returned agent |
| LangGraph node (async fn) | AGENT          | —                                                     |

### LLM factory

```
from uipath_langchain.chat import UiPathChat
from uipath_langchain.guardrails import guardrail, PIIValidator, BlockAction, GuardrailExecutionStage, PIIDetectionEntity
from uipath_langchain.guardrails.enums import PIIDetectionEntityType

@guardrail(
    validator=PIIValidator(
        entities=[PIIDetectionEntity(PIIDetectionEntityType.EMAIL, threshold=0.5)],
    ),
    action=BlockAction(),
    name="LLM PII check",
    stage=GuardrailExecutionStage.PRE,
)
def create_llm():
    return UiPathChat(model="gpt-4o-2024-08-06")

llm = create_llm()
```

### Tool

`@guardrail` must be placed **above** `@tool`:

```
from langchain_core.tools import tool
from uipath_langchain.guardrails import guardrail, CustomValidator, BlockAction, GuardrailExecutionStage

@guardrail(
    validator=CustomValidator(lambda args: len(args.get("text", "")) > 1000),
    action=BlockAction(detail="Text exceeds 1000 characters"),
    stage=GuardrailExecutionStage.PRE,
    name="Length limiter",
)
@tool
def analyze_text(text: str) -> str:
    """Count words in the provided text."""
    return f"Word count: {len(text.split())}"
```

### Agent factory

```
from langchain.agents import create_agent
from uipath_langchain.guardrails import guardrail, HarmfulContentValidator, BlockAction, GuardrailExecutionStage, HarmfulContentEntity
from uipath_langchain.guardrails.enums import HarmfulContentEntityType

@guardrail(
    validator=HarmfulContentValidator(
        entities=[HarmfulContentEntity(HarmfulContentEntityType.VIOLENCE, threshold=2)],
    ),
    action=BlockAction(),
    name="Block harmful content",
    stage=GuardrailExecutionStage.PRE,
)
def create_my_agent():
    return create_agent(model=llm, tools=[analyze_text], system_prompt="...")

agent = create_my_agent()
```

### LLM-as-judge

Use `LLMAsJudgeValidator` to check content against a plain-language rule via a judge LLM. Scope is inferred from the decorated target (here, the agent factory → AGENT scope). See the [core guardrails documentation](https://uipath.github.io/uipath-python/core/guardrails/#llm-as-judge) for the full parameter reference (`threshold`, `positive_examples`, `negative_examples`, and their limits).

```
from langchain.agents import create_agent
from uipath_langchain.guardrails import guardrail, LLMAsJudgeValidator, BlockAction, GuardrailExecutionStage

@guardrail(
    validator=LLMAsJudgeValidator(
        guardrail_text=(
            "The response must remain professional and must not contain "
            "financial or investment advice."
        ),
        model="gpt-4o-2024-08-06",
        threshold=2,
    ),
    action=BlockAction(),
    name="No financial advice",
    stage=GuardrailExecutionStage.POST,
)
def create_my_agent():
    return create_agent(model=llm, tools=[analyze_text], system_prompt="...")

agent = create_my_agent()
```

### LangGraph node

```
from uipath_langchain.guardrails import guardrail, PIIValidator, BlockAction, GuardrailExecutionStage, PIIDetectionEntity
from uipath_langchain.guardrails.enums import PIIDetectionEntityType

@guardrail(
    validator=PIIValidator(
        entities=[PIIDetectionEntity(PIIDetectionEntityType.PERSON, threshold=0.5)],
    ),
    action=BlockAction(title="Person name in input"),
    name="Node PII check",
    stage=GuardrailExecutionStage.PRE,
)
async def my_node(state: Input) -> Output:
    ...
```

### Escalation action (human-in-the-loop)

`EscalateAction` works on the decorator path exactly as it does for middleware — on a violation it suspends the run via `interrupt(CreateEscalation(...))`, creates a review task in a UiPath **Action App**, and resumes on Approve/Reject. It is the **same action class** as the middleware path; just pass it as the `action` of a `@guardrail` on the factory you want to guard. The escalation task's `Component` / `ExecutionStage` are **derived automatically** from the inferred scope of the decorated target — no extra configuration:

```
from langchain.agents import create_agent
from uipath_langchain.guardrails import (
    guardrail,
    EscalateAction,
    PIIValidator,
    GuardrailExecutionStage,
    PIIDetectionEntity,
)
from uipath_langchain.guardrails.enums import PIIDetectionEntityType
from uipath.platform.action_center.tasks import TaskRecipient, TaskRecipientType

@guardrail(
    validator=PIIValidator(
        entities=[PIIDetectionEntity(PIIDetectionEntityType.EMAIL, threshold=0.5)],
    ),
    action=EscalateAction(
        app_name="Guardrail Escalation Action App",
        app_folder_path="Shared",
        # optional: route the review task to a specific recipient
        recipient=TaskRecipient(
            type=TaskRecipientType.EMAIL, value="reviewer@example.com"
        ),
    ),
    name="Agent PII escalation",
    stage=GuardrailExecutionStage.PRE,   # escalate once per run
)
def create_my_agent():
    return create_agent(model=llm, tools=[analyze_text], system_prompt="...")

agent = create_my_agent()
```

On resume: **Approve** continues, substituting the reviewer's edit if any — read from `ReviewedInputs` for a PRE (input) escalation and `ReviewedOutputs` for a POST (output) one, otherwise keeping the original; **Reject** raises `GuardrailBlockException` and terminates the run. The `app_name` / `app_folder_path` / `assignee` / `recipient` / `title` parameters and the auto-derived payload fields behave identically to the [middleware escalation action](#escalation-action-human-in-the-loop) above — refer to it for the full parameter list.

> 💡 **Scope inference for the payload context.** `Component` / `ExecutionStage` are derived automatically for the adapter-handled LangChain targets — `@tool`, `BaseChatModel` factories, and `create_agent()` factories. On a plain LangGraph node or plain Python function (handled by the core `@guardrail`, which doesn't publish the LangChain runtime context) the escalation still suspends, but those two fields are not populated.
>
> 💡 **Escalate once per run.** As with middleware, AGENT/LLM scope validates both *before* and *after* by default. Set `stage=GuardrailExecutionStage.PRE` (or `POST`) so only a single checkpoint is registered.

______________________________________________________________________

## Choosing between middleware and decorator

|                              | Middleware                                            | Decorator                                      |
| ---------------------------- | ----------------------------------------------------- | ---------------------------------------------- |
| Configuration location       | Centralised in `create_agent()`                       | Per-target, co-located with the object         |
| Scope specification          | Explicit `scopes=` parameter                          | Auto-inferred from the decorated type          |
| Works outside `create_agent` | No                                                    | Yes — any LangGraph graph or plain function    |
| Reusable validator objects   | No                                                    | Yes — declare once, use in multiple decorators |
| Parameter exclusion          | No                                                    | `GuardrailExclude()` annotation                |
| Custom deterministic rules   | `UiPathDeterministicGuardrailMiddleware(rules=[...])` | `CustomValidator(lambda ...)`                  |

Use **middleware** when you want all guardrail policy in one place alongside a single `create_agent()` call. Use **decorators** when building custom LangGraph graphs, reusing validators across multiple agents, or guarding code outside the agent context.

______________________________________________________________________

## Sample agents

- [`samples/joke-agent`](https://github.com/UiPath/uipath-langchain-python/tree/main/samples/joke-agent) — middleware pattern
- [`samples/joke-agent-decorator`](https://github.com/UiPath/uipath-langchain-python/tree/main/samples/joke-agent-decorator) — decorator pattern

______________________________________________________________________

## Reference

### GuardrailScope

Imported from `uipath.core.guardrails`.

| Value   | Description                                                               |
| ------- | ------------------------------------------------------------------------- |
| `AGENT` | Hooks run at agent input/output boundary (`before_agent` / `after_agent`) |
| `LLM`   | Hooks run around every LLM call (`before_model` / `after_model`)          |
| `TOOL`  | Hooks run around every tool call (`wrap_tool_call`)                       |

### GuardrailExecutionStage

Imported from `uipath_langchain.guardrails`.

| Value          | When it fires                                |
| -------------- | -------------------------------------------- |
| `PRE`          | Before the call (inspect / block inputs)     |
| `POST`         | After the call (inspect / transform outputs) |
| `PRE_AND_POST` | Both checkpoints (the default)               |

### LoggingSeverityLevel

Used in `LogAction(severity_level=...)`. Imported from `uipath_langchain.guardrails`.

| Value     |
| --------- |
| `DEBUG`   |
| `INFO`    |
| `WARNING` |
| `ERROR`   |

### PIIDetectionEntityType

Imported from `uipath_langchain.guardrails.enums`. Wrap each value in `PIIDetectionEntity(entity_type, threshold=0.5)` — `threshold` is a float from `0.0` to `1.0`.

PII detection entity types supported by UiPath guardrails.

| Value                                   |
| --------------------------------------- |
| `PERSON`                                |
| `ADDRESS`                               |
| `DATE`                                  |
| `PHONE_NUMBER`                          |
| `EUGPS_COORDINATES`                     |
| `EMAIL`                                 |
| `CREDIT_CARD_NUMBER`                    |
| `INTERNATIONAL_BANKING_ACCOUNT_NUMBER`  |
| `SWIFT_CODE`                            |
| `ABA_ROUTING_NUMBER`                    |
| `US_DRIVERS_LICENSE_NUMBER`             |
| `UK_DRIVERS_LICENSE_NUMBER`             |
| `US_INDIVIDUAL_TAXPAYER_IDENTIFICATION` |
| `UK_UNIQUE_TAXPAYER_NUMBER`             |
| `US_BANK_ACCOUNT_NUMBER`                |
| `US_SOCIAL_SECURITY_NUMBER`             |
| `USUK_PASSPORT_NUMBER`                  |
| `URL`                                   |
| `IP_ADDRESS`                            |

### HarmfulContentEntityType

Imported from `uipath_langchain.guardrails.enums`. Wrap each value in `HarmfulContentEntity(entity_type, threshold=2)` — `threshold` must be one of `0`, `2`, `4`, or `6` (higher = less sensitive).

Harmful content entity types supported by UiPath guardrails.

| Value       |
| ----------- |
| `HATE`      |
| `SELF_HARM` |
| `SEXUAL`    |
| `VIOLENCE`  |

### IntellectualPropertyEntityType

Imported from `uipath_langchain.guardrails.enums`. Pass values directly in `entities=[...]` — no wrapper model class.

Intellectual property entity types supported by UiPath guardrails.

| Value  |
| ------ |
| `TEXT` |
| `CODE` |
