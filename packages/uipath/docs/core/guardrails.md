# Guardrails

Guardrails are safeguards applied before and/or after execution to inspect inputs and outputs for policy violations — PII, harmful content, prompt injection, intellectual property, and custom rules — and respond by logging, blocking, or modifying the data.

They can be applied at three scopes:

- **Tool** — individual tool functions called by an agent
- **LLM** — LLM factory functions or chat model objects (e.g. LangChain `BaseChatModel`)
- **Agent** — agent-level methods and nodes

The `@guardrail` decorator works with plain Python functions, async functions, and any LangChain/LangGraph object recognised by a registered framework adapter.

## Usage

Apply the `@guardrail` decorator to any callable — tool functions, LLM factories, agent factories, or async agent nodes. The decorator intercepts calls at the configured stage and evaluates the data against the provided validator.

**Tool function:**

```python
from uipath.platform.guardrails import (
    BlockAction,
    GuardrailExecutionStage,
    PIIDetectionEntity,
    PIIDetectionEntityType,
    PIIValidator,
    guardrail,
)

@guardrail(
    validator=PIIValidator(
        entities=[PIIDetectionEntity(PIIDetectionEntityType.EMAIL, threshold=0.5)]
    ),
    action=BlockAction(),
    name="No PII in output",
    stage=GuardrailExecutionStage.POST,
)
def analyze_joke(joke: str) -> str:
    ...
```

When using LangChain's `@tool`, `@guardrail` must be placed **above** `@tool`:

```python
from langchain_core.tools import tool

@guardrail(
    validator=PromptInjectionValidator(threshold=0.5),
    action=BlockAction(),
    name="No prompt injection",
    stage=GuardrailExecutionStage.PRE,
)
@tool  # @guardrail wraps the already-decorated tool object
def analyze_joke(joke: str) -> str:
    ...
```

**LLM factory function:**

```python
@guardrail(
    validator=PromptInjectionValidator(threshold=0.5),
    action=BlockAction(),
    name="LLM Prompt Injection Detection",
    stage=GuardrailExecutionStage.PRE,
)
def create_llm():
    return UiPathChat(model="gpt-4o-2024-08-06")
```

**Agent factory or async node:**

```python
@guardrail(
    validator=PIIValidator(
        entities=[PIIDetectionEntity(PIIDetectionEntityType.PERSON, threshold=0.5)]
    ),
    action=BlockAction(
        title="Person name detection",
        detail="Person name detected and is not allowed",
    ),
    name="Agent PII Detection",
    stage=GuardrailExecutionStage.PRE,
)
async def joke_node(state: Input) -> Output:
    ...
```

## Execution Stages

The `stage` parameter controls when the guardrail evaluates. Not all validators support all stages.

| Stage | When evaluated | Supported by |
|-------|---------------|--------------|
| `PRE` | Before the function runs | All validators |
| `POST` | After the function runs | All except `PromptInjectionValidator`, `UserPromptAttacksValidator` |
| `PRE_AND_POST` | Both before and after | `PIIValidator`, `HarmfulContentValidator`, `CustomValidator` |

## Built-in Validators

Built-in validators are backed by the UiPath Guardrails API (powered by Azure Content Safety). They require a UiPath connection with the appropriate entitlements.

### PII Detection

Detects personally identifiable information in text. Supports 18 entity types with per-entity confidence thresholds.

```python
from uipath.platform.guardrails import (
    BlockAction,
    PIIDetectionEntity,
    PIIDetectionEntityType,
    PIIValidator,
    guardrail,
)

@guardrail(
    validator=PIIValidator(
        entities=[
            PIIDetectionEntity(name=PIIDetectionEntityType.EMAIL, threshold=0.7),
            PIIDetectionEntity(name=PIIDetectionEntityType.PHONE_NUMBER, threshold=0.5),
            PIIDetectionEntity(name=PIIDetectionEntityType.US_SOCIAL_SECURITY_NUMBER),
        ]
    ),
    action=BlockAction(),
    name="No PII",
)
def process_document(content: str) -> str:
    ...
```

`threshold` is a confidence value between `0.0` and `1.0` (default `0.5`). Lower values increase sensitivity.

### Harmful Content

Detects harmful or unsafe content across four Azure Content Safety categories. Each category has a severity threshold from `0` (most sensitive) to `6` (least sensitive), defaulting to `2`.

```python
from uipath.platform.guardrails import (
    BlockAction,
    HarmfulContentEntity,
    HarmfulContentEntityType,
    HarmfulContentValidator,
    guardrail,
)

@guardrail(
    validator=HarmfulContentValidator(
        entities=[
            HarmfulContentEntity(name=HarmfulContentEntityType.VIOLENCE, threshold=2),
            HarmfulContentEntity(name=HarmfulContentEntityType.HATE, threshold=2),
        ]
    ),
    action=BlockAction(),
    name="Safe content only",
)
def generate_response(prompt: str) -> str:
    ...
```

### Prompt Injection

Detects prompt injection attacks in user input. Restricted to `PRE` stage only — this is an input concern.

```python
from uipath.platform.guardrails import (
    BlockAction,
    GuardrailExecutionStage,
    PromptInjectionValidator,
    guardrail,
)

@guardrail(
    validator=PromptInjectionValidator(threshold=0.5),
    action=BlockAction(),
    name="No prompt injection",
    stage=GuardrailExecutionStage.PRE,
)
def run_agent_step(user_input: str) -> str:
    ...
```

### User Prompt Attacks

Detects adversarial user prompt patterns (e.g. jailbreak attempts). No configuration parameters required. Restricted to `PRE` stage only.

```python
from uipath.platform.guardrails import (
    BlockAction,
    GuardrailExecutionStage,
    UserPromptAttacksValidator,
    guardrail,
)

@guardrail(
    validator=UserPromptAttacksValidator(),
    action=BlockAction(),
    name="No prompt attacks",
    stage=GuardrailExecutionStage.PRE,
)
def chat(message: str) -> str:
    ...
```

### Intellectual Property

Detects potential intellectual property violations in generated output. Restricted to `POST` stage only — this is an output concern.

```python
from uipath.platform.guardrails import (
    BlockAction,
    GuardrailExecutionStage,
    IntellectualPropertyEntityType,
    IntellectualPropertyValidator,
    guardrail,
)

@guardrail(
    validator=IntellectualPropertyValidator(
        entities=[
            IntellectualPropertyEntityType.TEXT,
            IntellectualPropertyEntityType.CODE,
        ]
    ),
    action=BlockAction(),
    name="No IP violations",
    stage=GuardrailExecutionStage.POST,
)
def generate_code(spec: str) -> str:
    ...
```

## Actions

Actions define what happens when a violation is detected.

### LogAction

Logs the violation and lets execution continue. The original data is unchanged.

```python
from uipath.platform.guardrails import LogAction, LoggingSeverityLevel

action = LogAction(severity_level=LoggingSeverityLevel.WARNING)
action = LogAction(severity_level=LoggingSeverityLevel.ERROR, message="PII found in output")
```

### BlockAction

Raises `GuardrailBlockException` to stop execution immediately. Framework adapters (e.g. LangChain) catch this exception and convert it to their own error type.

```python
from uipath.platform.guardrails import BlockAction

action = BlockAction()
action = BlockAction(title="PII detected", detail="Email address found in response")
```

### Custom Actions

Subclass `GuardrailAction` to implement custom behaviour, such as content sanitisation:

```python
from typing import Any
from uipath.core.guardrails import GuardrailValidationResult
from uipath.platform.guardrails import GuardrailAction

class RedactAction(GuardrailAction):
    def handle_validation_result(
        self,
        result: GuardrailValidationResult,
        data: str | dict[str, Any],
        guardrail_name: str,
    ) -> str | dict[str, Any] | None:
        # Return modified data to replace the original, or None to leave unchanged
        if isinstance(data, str):
            return "[REDACTED]"
        return None
```

## Custom Validators

`CustomValidator` applies an in-process rule function without any API call. The rule receives the input dict (PRE stage) or both input and output dicts (POST stage), and returns `True` to signal a violation.

```python
from uipath.platform.guardrails import BlockAction, CustomValidator, guardrail

@guardrail(
    validator=CustomValidator(rule=lambda data: "forbidden" in str(data).lower()),
    action=BlockAction(),
    name="No forbidden words",
)
def my_tool(text: str) -> str:
    ...
```

For POST-stage rules, accept two parameters to inspect both input and output:

```python
def check_output(input_data: dict, output_data: dict) -> bool:
    # Return True to trigger the guardrail
    return len(output_data.get("response", "")) > 5000

@guardrail(
    validator=CustomValidator(rule=check_output),
    action=BlockAction(detail="Response exceeds maximum length"),
    name="Length limit",
    stage=GuardrailExecutionStage.POST,
)
def summarize(query: str) -> dict:
    ...
```

For full control, subclass `CustomGuardrailValidator` directly.

## Excluding Parameters

Use `GuardrailExclude` with `Annotated` to prevent a specific parameter from being included in the guardrail evaluation payload. Useful for internal context objects, credentials, or other data that should never be inspected.

```python
from typing import Annotated
from uipath.platform.guardrails import BlockAction, GuardrailExclude, PIIValidator, guardrail

@guardrail(
    validator=PIIValidator(entities=[PIIDetectionEntity(name=PIIDetectionEntityType.EMAIL)]),
    action=BlockAction(),
    name="No PII",
)
def process(
    user_message: str,
    internal_config: Annotated[dict, GuardrailExclude()],  # excluded from guardrail
) -> str:
    ...
```

## Stacking Guardrails

Multiple `@guardrail` decorators can be stacked on the same function. Each is evaluated independently at its configured stage.

```python
@guardrail(
    validator=PromptInjectionValidator(),
    action=BlockAction(),
    name="No injection",
    stage=GuardrailExecutionStage.PRE,
)
@guardrail(
    validator=PIIValidator(entities=[PIIDetectionEntity(name=PIIDetectionEntityType.EMAIL)]),
    action=LogAction(),
    name="PII audit",
    stage=GuardrailExecutionStage.POST,
)
def handle_request(user_input: str) -> str:
    ...
```

## Low-level API

For direct programmatic use without the decorator, the `GuardrailsService` is available on the `UiPath` client:

```python
from uipath.platform import UiPath
from uipath.platform.guardrails import BuiltInValidatorGuardrail

sdk = UiPath()
result = sdk.guardrails.evaluate_guardrail(
    input_data="Contact me at user@example.com",
    guardrail=BuiltInValidatorGuardrail(
        id="my-guardrail",
        name="PII check",
        guardrail_type="builtInValidator",
        validator_type="pii_detection",
    ),
)
print(result.result, result.reason)
```

---

## API Reference

### Service

::: uipath.platform.guardrails._guardrails_service
    options:
      members:
        - GuardrailsService

### Decorator

::: uipath.platform.guardrails.decorators._guardrail
    options:
      members:
        - guardrail

### Execution Stage

::: uipath.platform.guardrails.decorators._enums
    options:
      members:
        - GuardrailExecutionStage
        - PIIDetectionEntityType
        - HarmfulContentEntityType
        - IntellectualPropertyEntityType

### Actions

::: uipath.platform.guardrails.decorators._models
    options:
      members:
        - GuardrailAction
        - PIIDetectionEntity
        - HarmfulContentEntity

::: uipath.platform.guardrails.decorators._actions
    options:
      members:
        - LoggingSeverityLevel
        - LogAction
        - BlockAction

::: uipath.platform.guardrails.decorators._exceptions
    options:
      members:
        - GuardrailBlockException

### Exclude Marker

::: uipath.platform.guardrails.decorators._core
    options:
      members:
        - GuardrailExclude

### Validators

::: uipath.platform.guardrails.decorators.validators._base
    options:
      members:
        - GuardrailValidatorBase
        - BuiltInGuardrailValidator
        - CustomGuardrailValidator

::: uipath.platform.guardrails.decorators.validators.pii
    options:
      members:
        - PIIValidator

::: uipath.platform.guardrails.decorators.validators.harmful_content
    options:
      members:
        - HarmfulContentValidator

::: uipath.platform.guardrails.decorators.validators.prompt_injection
    options:
      members:
        - PromptInjectionValidator

::: uipath.platform.guardrails.decorators.validators.intellectual_property
    options:
      members:
        - IntellectualPropertyValidator

::: uipath.platform.guardrails.decorators.validators.user_prompt_attacks
    options:
      members:
        - UserPromptAttacksValidator

::: uipath.platform.guardrails.decorators.validators.custom
    options:
      members:
        - CustomValidator
        - RuleFunction
