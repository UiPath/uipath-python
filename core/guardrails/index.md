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
