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

```
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

```
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

```
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

```
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

| Stage          | When evaluated           | Supported by                                                        |
| -------------- | ------------------------ | ------------------------------------------------------------------- |
| `PRE`          | Before the function runs | All validators                                                      |
| `POST`         | After the function runs  | All except `PromptInjectionValidator`, `UserPromptAttacksValidator` |
| `PRE_AND_POST` | Both before and after    | `PIIValidator`, `HarmfulContentValidator`, `CustomValidator`        |

## Built-in Validators

Built-in validators are backed by the UiPath Guardrails API (powered by Azure Content Safety). They require a UiPath connection with the appropriate entitlements.

### PII Detection

Detects personally identifiable information in text. Supports 18 entity types with per-entity confidence thresholds.

```
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

```
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

```
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

```
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

```
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

```
from uipath.platform.guardrails import LogAction, LoggingSeverityLevel

action = LogAction(severity_level=LoggingSeverityLevel.WARNING)
action = LogAction(severity_level=LoggingSeverityLevel.ERROR, message="PII found in output")
```

### BlockAction

Raises `GuardrailBlockException` to stop execution immediately. Framework adapters (e.g. LangChain) catch this exception and convert it to their own error type.

```
from uipath.platform.guardrails import BlockAction

action = BlockAction()
action = BlockAction(title="PII detected", detail="Email address found in response")
```

### Custom Actions

Subclass `GuardrailAction` to implement custom behaviour, such as content sanitisation:

```
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

```
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

```
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

```
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

```
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

```
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

______________________________________________________________________

## API Reference

### Service

## GuardrailsService

Service for validating text against UiPath Guardrails.

This service provides an interface for evaluating built-in guardrails such as:

- PII detection
- Prompt injection detection

Deterministic and custom guardrails are not yet supported.

Version Availability

This service is available starting from **uipath** version **2.2.12**.

### evaluate_guardrail

```
evaluate_guardrail(input_data, guardrail)
```

Validate input text using the provided guardrail.

Parameters:

| Name         | Type                        | Description                               | Default                                                                                                |
| ------------ | --------------------------- | ----------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `input_data` | \`str                       | dict[str, Any]\`                          | The text or structured data to validate. Dictionaries will be converted to a string before validation. |
| `guardrail`  | `BuiltInValidatorGuardrail` | A guardrail instance used for validation. | *required*                                                                                             |

Returns:

| Name                        | Type                        | Description                              |
| --------------------------- | --------------------------- | ---------------------------------------- |
| `GuardrailValidationResult` | `GuardrailValidationResult` | The outcome of the guardrail evaluation. |

### Decorator

Single `@guardrail` decorator for all guardrail types.

## guardrail

```
guardrail(
    func=None,
    *,
    validator,
    action,
    name="Guardrail",
    description=None,
    stage=GuardrailExecutionStage.PRE_AND_POST,
    enabled_for_evals=True,
)
```

Apply a guardrail to any callable — tool functions, LLM factories, agent nodes.

When applied to a plain function or async function, the decorator collects function parameters (PRE) and return value (POST) and evaluates them against the guardrail. Use :class:`~._core.GuardrailExclude` to opt individual parameters out of serialization.

When applied to a factory function whose return value is recognised by a registered framework adapter (e.g. a LangChain `BaseChatModel`), the returned object is wrapped so every subsequent `invoke()` call is guarded.

Multiple `@guardrail` decorators can be stacked on the same callable.

Parameters:

| Name                | Type                      | Description                                                                 | Default                                              |
| ------------------- | ------------------------- | --------------------------------------------------------------------------- | ---------------------------------------------------- |
| `func`              | `Any`                     | Callable to decorate. Supplied directly when used without parentheses.      | `None`                                               |
| `validator`         | `GuardrailValidatorBase`  | :class:~.validators.GuardrailValidatorBase defining what to check.          | *required*                                           |
| `action`            | `GuardrailAction`         | :class:~.\_models.GuardrailAction defining how to respond on violation.     | *required*                                           |
| `name`              | `str`                     | Human-readable name for this guardrail instance.                            | `'Guardrail'`                                        |
| `description`       | \`str                     | None\`                                                                      | Optional description passed to API-based guardrails. |
| `stage`             | `GuardrailExecutionStage` | When to evaluate — PRE, POST, or PRE_AND_POST. Defaults to PRE_AND_POST.    | `PRE_AND_POST`                                       |
| `enabled_for_evals` | `bool`                    | Whether this guardrail is active in evaluation scenarios. Defaults to True. | `True`                                               |

Returns:

| Type  | Description                                   |
| ----- | --------------------------------------------- |
| `Any` | The decorated callable (or framework object). |

Raises:

| Type                      | Description                                                                       |
| ------------------------- | --------------------------------------------------------------------------------- |
| `ValueError`              | If action is invalid, or the validator does not support the requested stage.      |
| `GuardrailBlockException` | Raised at runtime by :class:~.\_actions.BlockAction when a violation is detected. |

### Execution Stage

Enums for guardrail decorators.

## GuardrailExecutionStage

Execution stage for guardrails.

### POST

```
POST = 'post'
```

Evaluate after the target executes.

### PRE

```
PRE = 'pre'
```

Evaluate before the target executes.

### PRE_AND_POST

```
PRE_AND_POST = 'pre&post'
```

Evaluate both before and after the target executes.

## PIIDetectionEntityType

PII detection entity types supported by UiPath guardrails.

These entities match the available options from the UiPath guardrails service backend. The enum values correspond to the exact strings expected by the API.

## HarmfulContentEntityType

Harmful content entity types supported by UiPath guardrails.

These entities correspond to the Azure Content Safety categories.

## IntellectualPropertyEntityType

Intellectual property entity types supported by UiPath guardrails.

### Actions

Models for guardrail decorators.

## GuardrailAction

Interface for defining custom actions when a guardrail violation is detected.

Subclass this to implement custom behaviour on validation failure, such as logging, blocking, or content sanitisation. Built-in implementations are :class:`LogAction` and :class:`BlockAction`.

### handle_validation_result

```
handle_validation_result(result, data, guardrail_name)
```

Handle a guardrail validation result.

Called when guardrail validation fails. May return modified data to sanitise/filter the validated content before execution continues, or `None` to leave it unchanged.

Parameters:

| Name             | Type                        | Description                                        | Default                                                                                                                        |
| ---------------- | --------------------------- | -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `result`         | `GuardrailValidationResult` | The validation result from the guardrails service. | *required*                                                                                                                     |
| `data`           | \`str                       | dict[str, Any]\`                                   | The data that was validated (string or dictionary). Depending on context this can be tool input, tool output, or message text. |
| `guardrail_name` | `str`                       | The name of the guardrail that triggered.          | *required*                                                                                                                     |

Returns:

| Type  | Description    |
| ----- | -------------- |
| \`str | dict[str, Any] |
| \`str | dict[str, Any] |

## PIIDetectionEntity

PII entity configuration with detection threshold.

Parameters:

| Name        | Type    | Description                                               | Default    |
| ----------- | ------- | --------------------------------------------------------- | ---------- |
| `name`      | `str`   | The entity type name (e.g. PIIDetectionEntityType.EMAIL). | *required* |
| `threshold` | `float` | Confidence threshold (0.0 to 1.0) for detection.          | `0.5`      |

## HarmfulContentEntity

Harmful content entity configuration with severity threshold.

Parameters:

| Name        | Type  | Description                                                    | Default    |
| ----------- | ----- | -------------------------------------------------------------- | ---------- |
| `name`      | `str` | The entity type name (e.g. HarmfulContentEntityType.VIOLENCE). | *required* |
| `threshold` | `int` | Severity threshold (0 to 6) for detection. Defaults to 2.      | `2`        |

Built-in GuardrailAction implementations.

## LoggingSeverityLevel

Logging severity level for :class:`LogAction`.

## LogAction

Log guardrail violations without stopping execution.

Parameters:

| Name             | Type                   | Description                                | Default                                                        |
| ---------------- | ---------------------- | ------------------------------------------ | -------------------------------------------------------------- |
| `severity_level` | `LoggingSeverityLevel` | Python logging level. Defaults to WARNING. | `WARNING`                                                      |
| `message`        | \`str                  | None\`                                     | Custom log message. If omitted, the validation reason is used. |

### handle_validation_result

```
handle_validation_result(result, data, guardrail_name)
```

Log the violation and return `None` (no data modification).

## BlockAction

Block execution by raising :class:`GuardrailBlockException`.

Framework adapters catch `GuardrailBlockException` at the wrapper boundary and convert it to their own runtime error type.

Parameters:

| Name     | Type  | Description | Default                                                                 |
| -------- | ----- | ----------- | ----------------------------------------------------------------------- |
| `title`  | \`str | None\`      | Exception title. Defaults to a message derived from the guardrail name. |
| `detail` | \`str | None\`      | Exception detail. Defaults to the validation reason.                    |

### handle_validation_result

```
handle_validation_result(result, data, guardrail_name)
```

Raise :class:`GuardrailBlockException` when validation fails.

Exceptions for guardrail decorators.

## GuardrailBlockException

Raised by BlockAction when a guardrail blocks execution.

Framework adapters (e.g. LangChain) should catch this and convert it to their own runtime exception type at the outermost wrapper boundary.

Parameters:

| Name     | Type  | Description                      | Default    |
| -------- | ----- | -------------------------------- | ---------- |
| `title`  | `str` | Brief title for the block event. | *required* |
| `detail` | `str` | Detailed reason for the block.   | *required* |

### Exclude Marker

Core framework-agnostic utilities for guardrail decorators.

## GuardrailExclude

Marker to exclude a parameter from guardrail input serialization.

Use with :data:`typing.Annotated` to prevent a specific function parameter from being collected into the guardrail evaluation payload::

```
async def process(
    text: str,
    config: Annotated[dict, GuardrailExclude()],
) -> str: ...
```

### Validators

Abstract base classes for guardrail validators.

## GuardrailValidatorBase

Root base class for guardrail validators.

Concrete validators should subclass either :class:`BuiltInGuardrailValidator` (for UiPath API-backed validation) or :class:`CustomGuardrailValidator` (for in-process Python validation).

### supported_stages

```
supported_stages = []
```

Stages this validator supports. Empty list means all stages are allowed.

### run

```
run(
    name,
    description,
    enabled_for_evals,
    data,
    stage,
    input_data,
    output_data,
)
```

Execute the guardrail evaluation.

Called by the `@guardrail` decorator at each function invocation. Subclasses override this via :class:`BuiltInGuardrailValidator` or :class:`CustomGuardrailValidator`.

Raises:

| Type                  | Description                                    |
| --------------------- | ---------------------------------------------- |
| `NotImplementedError` | Always — subclass one of the two ABCs instead. |

### validate_stage

```
validate_stage(stage)
```

Raise `ValueError` if *stage* is not in :attr:`supported_stages`.

Parameters:

| Name    | Type                      | Description                | Default    |
| ------- | ------------------------- | -------------------------- | ---------- |
| `stage` | `GuardrailExecutionStage` | Requested execution stage. | *required* |

Raises:

| Type         | Description                                                 |
| ------------ | ----------------------------------------------------------- |
| `ValueError` | If :attr:supported_stages is non-empty and stage is absent. |

## BuiltInGuardrailValidator

Base for validators that delegate to the UiPath Guardrails API.

Subclass this and implement :meth:`get_built_in_guardrail` to create an API-backed guardrail validator (e.g. PII detection, prompt injection).

Example::

```
class MyValidator(BuiltInGuardrailValidator):
    def get_built_in_guardrail(self, name, description, enabled_for_evals):
        return BuiltInValidatorGuardrail(
            id=str(uuid4()),
            name=name,
            ...
        )
```

### get_built_in_guardrail

```
get_built_in_guardrail(
    name, description, enabled_for_evals
)
```

Build the UiPath API guardrail definition for this validator.

Parameters:

| Name                | Type   | Description                             | Default               |
| ------------------- | ------ | --------------------------------------- | --------------------- |
| `name`              | `str`  | Name for the guardrail instance.        | *required*            |
| `description`       | \`str  | None\`                                  | Optional description. |
| `enabled_for_evals` | `bool` | Whether active in evaluation scenarios. | *required*            |

Returns:

| Type                        | Description                                                  |
| --------------------------- | ------------------------------------------------------------ |
| `BuiltInValidatorGuardrail` | class:BuiltInValidatorGuardrail ready to be sent to the API. |

### run

```
run(
    name,
    description,
    enabled_for_evals,
    data,
    stage,
    input_data,
    output_data,
)
```

Evaluate via the UiPath Guardrails API.

Lazily initialises the `UiPath` client on the first call and reuses it for all subsequent invocations.

## CustomGuardrailValidator

Base for validators that run entirely in-process.

Subclass this and implement :meth:`evaluate` to create a local guardrail validator that requires no UiPath API call.

Example::

```
class ProfanityValidator(CustomGuardrailValidator):
    BANNED = {"badword"}

    def evaluate(self, data, stage, input_data, output_data):
        text = (input_data or {}).get("message", "")
        if any(w in text.lower() for w in self.BANNED):
            return GuardrailValidationResult(
                result=GuardrailValidationResultType.VALIDATION_FAILED,
                reason="Profanity detected",
            )
        return GuardrailValidationResult(result=GuardrailValidationResultType.PASSED)
```

### evaluate

```
evaluate(data, stage, input_data, output_data)
```

Perform local validation without a UiPath API call.

Return a result with `VALIDATION_FAILED` to **trigger** the guardrail (causing the configured :class:`~uipath.platform.guardrails.decorators.GuardrailAction` to fire), or `PASSED` to let execution continue unchanged.

Parameters:

| Name          | Type                      | Description                            | Default                                                |
| ------------- | ------------------------- | -------------------------------------- | ------------------------------------------------------ |
| `data`        | \`str                     | dict[str, Any]\`                       | Primary data being evaluated.                          |
| `stage`       | `GuardrailExecutionStage` | Current execution stage (PRE or POST). | *required*                                             |
| `input_data`  | \`dict[str, Any]          | None\`                                 | Normalised function input dict, or None.               |
| `output_data` | \`dict[str, Any]          | None\`                                 | Normalised function output dict, or None at PRE stage. |

Returns:

| Type                        | Description                                               |
| --------------------------- | --------------------------------------------------------- |
| `GuardrailValidationResult` | class:~uipath.core.guardrails.GuardrailValidationResult — |
| `GuardrailValidationResult` | return VALIDATION_FAILED to activate the guardrail,       |
| `GuardrailValidationResult` | PASSED to allow execution to continue.                    |

### run

```
run(
    name,
    description,
    enabled_for_evals,
    data,
    stage,
    input_data,
    output_data,
)
```

Delegate to :meth:`evaluate`.

PII detection guardrail validator.

## PIIValidator

Validate data for PII entities using the UiPath PII detection API.

Supported at all stages.

Parameters:

| Name       | Type                           | Description                                                                                                                                                  | Default    |
| ---------- | ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------- |
| `entities` | `Sequence[PIIDetectionEntity]` | One or more :class:~uipath.platform.guardrails.decorators.PIIDetectionEntity instances specifying which PII types to detect and their confidence thresholds. | *required* |

Raises:

| Type         | Description           |
| ------------ | --------------------- |
| `ValueError` | If entities is empty. |

### __init__

```
__init__(entities)
```

Initialize PIIValidator with a list of entities to detect.

### get_built_in_guardrail

```
get_built_in_guardrail(
    name, description, enabled_for_evals
)
```

Build a PII detection :class:`BuiltInValidatorGuardrail`.

Parameters:

| Name                | Type   | Description                             | Default               |
| ------------------- | ------ | --------------------------------------- | --------------------- |
| `name`              | `str`  | Name for the guardrail.                 | *required*            |
| `description`       | \`str  | None\`                                  | Optional description. |
| `enabled_for_evals` | `bool` | Whether active in evaluation scenarios. | *required*            |

Returns:

| Name         | Type                        | Description                                        |
| ------------ | --------------------------- | -------------------------------------------------- |
| `Configured` | `BuiltInValidatorGuardrail` | class:BuiltInValidatorGuardrail for PII detection. |

Harmful content detection guardrail validator.

## HarmfulContentValidator

Validate data for harmful content using the UiPath API.

Supported at all stages (PRE, POST, PRE_AND_POST).

Parameters:

| Name       | Type                             | Description                                                                                                                                                                   | Default    |
| ---------- | -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| `entities` | `Sequence[HarmfulContentEntity]` | One or more :class:~uipath.platform.guardrails.decorators.HarmfulContentEntity instances specifying which harmful content categories to detect and their severity thresholds. | *required* |

Raises:

| Type         | Description           |
| ------------ | --------------------- |
| `ValueError` | If entities is empty. |

### __init__

```
__init__(entities)
```

Initialize HarmfulContentValidator with entities to detect.

### get_built_in_guardrail

```
get_built_in_guardrail(
    name, description, enabled_for_evals
)
```

Build a harmful content :class:`BuiltInValidatorGuardrail`.

Parameters:

| Name                | Type   | Description                             | Default               |
| ------------------- | ------ | --------------------------------------- | --------------------- |
| `name`              | `str`  | Name for the guardrail.                 | *required*            |
| `description`       | \`str  | None\`                                  | Optional description. |
| `enabled_for_evals` | `bool` | Whether active in evaluation scenarios. | *required*            |

Returns:

| Name         | Type                        | Description                                                    |
| ------------ | --------------------------- | -------------------------------------------------------------- |
| `Configured` | `BuiltInValidatorGuardrail` | class:BuiltInValidatorGuardrail for harmful content detection. |

Prompt injection detection guardrail validator.

## PromptInjectionValidator

Validate input for prompt injection attacks via the UiPath API.

Restricted to PRE stage only — prompt injection is an input-only concern.

Parameters:

| Name        | Type    | Description                                                | Default |
| ----------- | ------- | ---------------------------------------------------------- | ------- |
| `threshold` | `float` | Detection confidence threshold (0.0–1.0). Defaults to 0.5. | `0.5`   |

Raises:

| Type         | Description                         |
| ------------ | ----------------------------------- |
| `ValueError` | If threshold is outside [0.0, 1.0]. |

### __init__

```
__init__(threshold=0.5)
```

Initialize PromptInjectionValidator with a detection threshold.

### get_built_in_guardrail

```
get_built_in_guardrail(
    name, description, enabled_for_evals
)
```

Build a prompt injection :class:`BuiltInValidatorGuardrail`.

Parameters:

| Name                | Type   | Description                             | Default               |
| ------------------- | ------ | --------------------------------------- | --------------------- |
| `name`              | `str`  | Name for the guardrail.                 | *required*            |
| `description`       | \`str  | None\`                                  | Optional description. |
| `enabled_for_evals` | `bool` | Whether active in evaluation scenarios. | *required*            |

Returns:

| Name         | Type                        | Description                                           |
| ------------ | --------------------------- | ----------------------------------------------------- |
| `Configured` | `BuiltInValidatorGuardrail` | class:BuiltInValidatorGuardrail for prompt injection. |

Intellectual property detection guardrail validator.

## IntellectualPropertyValidator

Validate output for intellectual property violations using the UiPath API.

Restricted to POST stage only — IP detection is an output-only concern.

Parameters:

| Name       | Type            | Description                                                                 | Default    |
| ---------- | --------------- | --------------------------------------------------------------------------- | ---------- |
| `entities` | `Sequence[str]` | One or more entity type strings (e.g. IntellectualPropertyEntityType.TEXT). | *required* |

Raises:

| Type         | Description           |
| ------------ | --------------------- |
| `ValueError` | If entities is empty. |

### __init__

```
__init__(entities)
```

Initialize IntellectualPropertyValidator with entities to detect.

### get_built_in_guardrail

```
get_built_in_guardrail(
    name, description, enabled_for_evals
)
```

Build an intellectual property :class:`BuiltInValidatorGuardrail`.

Parameters:

| Name                | Type   | Description                             | Default               |
| ------------------- | ------ | --------------------------------------- | --------------------- |
| `name`              | `str`  | Name for the guardrail.                 | *required*            |
| `description`       | \`str  | None\`                                  | Optional description. |
| `enabled_for_evals` | `bool` | Whether active in evaluation scenarios. | *required*            |

Returns:

| Name         | Type                        | Description                                       |
| ------------ | --------------------------- | ------------------------------------------------- |
| `Configured` | `BuiltInValidatorGuardrail` | class:BuiltInValidatorGuardrail for IP detection. |

User prompt attacks detection guardrail validator.

## UserPromptAttacksValidator

Validate input for user prompt attacks via the UiPath API.

Restricted to PRE stage only — prompt attacks are an input-only concern. Takes no parameters.

### get_built_in_guardrail

```
get_built_in_guardrail(
    name, description, enabled_for_evals
)
```

Build a user prompt attacks :class:`BuiltInValidatorGuardrail`.

Parameters:

| Name                | Type   | Description                             | Default               |
| ------------------- | ------ | --------------------------------------- | --------------------- |
| `name`              | `str`  | Name for the guardrail.                 | *required*            |
| `description`       | \`str  | None\`                                  | Optional description. |
| `enabled_for_evals` | `bool` | Whether active in evaluation scenarios. | *required*            |

Returns:

| Name         | Type                        | Description                                              |
| ------------ | --------------------------- | -------------------------------------------------------- |
| `Configured` | `BuiltInValidatorGuardrail` | class:BuiltInValidatorGuardrail for user prompt attacks. |

Custom (rule-based) guardrail validator.

## RuleFunction

```
RuleFunction = (
    Callable[[dict[str, Any]], bool]
    | Callable[[dict[str, Any], dict[str, Any]], bool]
)
```

Type alias for custom rule functions passed to :class:`CustomValidator`.

The rule must return `True` to **trigger** the guardrail (i.e. signal a violation that causes the configured action to fire), or `False` to let execution continue unchanged.

It accepts either one parameter (the input or output dict) or two parameters (input dict, output dict — POST stage only).

Examples::

```
# Triggered when "donkey" appears in the joke argument
CustomValidator(lambda args: "donkey" in args.get("joke", "").lower())

# Triggered when the output joke exceeds 500 characters
CustomValidator(lambda args: len(args.get("joke", "")) > 500)

# Two-parameter form: triggered at POST when output contains input keyword
CustomValidator(lambda inp, out: inp.get("topic", "") in out.get("joke", ""))
```

## CustomValidator

Validate function input/output using a local Python rule function.

No UiPath API call is made. Applicable at any stage.

The *rule* is called with the collected parameter dict (PRE stage) or the serialised return-value dict (POST stage). It must return `True` to **activate** the guardrail — i.e. to signal a violation and invoke the configured :class:`~uipath.platform.guardrails.decorators.GuardrailAction`. Return `False` (or any falsy value) to let execution continue unchanged.

Parameters:

| Name   | Type           | Description                                                                                     | Default    |
| ------ | -------------- | ----------------------------------------------------------------------------------------------- | ---------- |
| `rule` | `RuleFunction` | A :data:RuleFunction that returns True to trigger the guardrail. Must accept 1 or 2 parameters. | *required* |

Raises:

| Type         | Description                                                    |
| ------------ | -------------------------------------------------------------- |
| `ValueError` | If rule is not callable or has an unsupported parameter count. |

### __init__

```
__init__(rule)
```

Initialize CustomValidator with a rule callable.

### evaluate

```
evaluate(data, stage, input_data, output_data)
```

Run the rule against the collected input or output dict.

The rule receives the PRE parameter dict or POST return-value dict and must return `True` to **trigger** the guardrail (VALIDATION_FAILED), or `False` to pass.

Parameters:

| Name          | Type                      | Description                  | Default                                                 |
| ------------- | ------------------------- | ---------------------------- | ------------------------------------------------------- |
| `data`        | \`str                     | dict[str, Any]\`             | Unused; the rule operates on input_data or output_data. |
| `stage`       | `GuardrailExecutionStage` | Current stage (PRE or POST). | *required*                                              |
| `input_data`  | \`dict[str, Any]          | None\`                       | Collected function input dict.                          |
| `output_data` | \`dict[str, Any]          | None\`                       | Collected function output dict, or None at PRE stage.   |

Returns:

| Type                        | Description                                               |
| --------------------------- | --------------------------------------------------------- |
| `GuardrailValidationResult` | class:~uipath.core.guardrails.GuardrailValidationResult — |
| `GuardrailValidationResult` | VALIDATION_FAILED when the rule returns True (guardrail   |
| `GuardrailValidationResult` | triggered), PASSED otherwise.                             |
