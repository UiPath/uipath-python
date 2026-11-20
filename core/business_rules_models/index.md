Models for the UiPath Business Rules service.

## BusinessRuleCaller

Bases: `BaseModel`

Who is running the rule, kept in the deployed run's execution audit.

Each field defaults to the current job's value from the environment. This describes the calling resource, not the rule: `folder_key` here is the caller's folder, which can differ from the folder the rule runs in.

## BusinessRuleDecision

Bases: `BaseModel`

The result of evaluating a single decision.

## BusinessRuleError

Bases: `BaseModel`

A code/message pair describing an input-level or decision-level error.

## BusinessRuleRunResult

Bases: `BaseModel`

The outcome of running a business rule against one input.

The shape is the same for deployed and debug runs.

## BusinessRuleStatus

Bases: `str`, `Enum`

The overall outcome of running a business rule against one input.

## BusinessRuleTraceContext

Bases: `BaseModel`

An existing trace to file the run's spans under.

Optional on `run()`: when omitted, the SDK takes the trace from `UIPATH_TRACE_ID` and the current span, as it does for every service.

### to_traceparent

```
to_traceparent()
```

Return the W3C traceparent value for this context.
