# Tracing

The `traced()` decorator enables automatic tracing of function calls, inputs, and outputs. It is designed to help you monitor, debug, and audit your code by capturing detailed information about function executions, including arguments, return values, and exceptions.

You can view the traces of an Orchestrator job by going to the Jobs page, click a job, a side panel will open, and they will be available under the `Trace` tab. These can also be seen in UiPath Maestro when your agent is part of a larger process orchestration.

## Usage

Apply the `@traced()` decorator to any function (sync, async, generator, or async generator) to automatically record its execution as a trace span.

```python hl_lines="3 7"
from uipath.tracing import traced

@traced()
def my_function(x, y):
    return x + y

@traced(name="custom_span", run_type="my_type")
async def my_async_function(a, b):
    return a * b
```

## Parameters

| Parameter         | Type                                | Description                                                                                       |
|------------------|-------------------------------------|---------------------------------------------------------------------------------------------------|
| name             | Optional[str]                       | Custom name for the trace span. Defaults to the function name.                                    |
| run_type         | Optional[str]                       | Category for the run (e.g., "uipath"). Useful for filtering traces.                              |
| span_type        | Optional[str]                       | Custom type for the span. Defaults to function type (sync/async/generator).                       |
| input_processor  | Optional[Callable[[dict], dict]]    | Function to process/transform inputs before recording. Receives a dict of arguments.              |
| output_processor | Optional[Callable[[Any], Any]]      | Function to process/transform outputs before recording. Receives the function's return value.      |
| hide_input       | bool                                | If True, input data is redacted in the trace for privacy/security.                                |
| hide_output      | bool                                | If True, output data is redacted in the trace for privacy/security.                               |

## Input and Output Processors

Processors allow you to mask, redact, or transform sensitive data before it is recorded in the trace. For example:

```python hl_lines="13"
def mask_inputs(inputs):
    inputs = inputs.copy()
    if 'password' in inputs:
        inputs['password'] = '***REDACTED***'
    return inputs

def anonymize_output(output):
    if isinstance(output, dict) and 'email' in output:
        output = output.copy()
        output['email'] = 'anonymous@example.com'
    return output

@traced(input_processor=mask_inputs, output_processor=anonymize_output)
def login(user, password):
    # ...
    return {"email": user + "@example.com"}
```

## Privacy Controls

- Set `hide_input=True` to prevent input data from being logged.
- Set `hide_output=True` to prevent output data from being logged.

```python hl_lines="1"
@traced(hide_input=True, hide_output=True)
def sensitive_operation(secret):
    ...
```

## Supported Function Types

- Regular functions (sync/async)
- Generator functions (sync/async)

## Example with plain python agents

When used with plain python agents please call `wait_for_tracers()` at the end of the script to ensure all traces are sent, if this is not called the agent could end without sending all the traces.

```python hl_lines="3 8"

from uipath.tracing import traced, wait_for_tracers

@traced(name="process_payment", run_type="payment", hide_input=True)
def process_payment(card_number, amount):
    # Sensitive input will not be logged
    return {"status": "success", "amount": amount}

@traced()
def main():
    process_payment()

def main_wait_traces():
    try:
        main()
    finally:
        # this needs to be called after the last `traced` function is done
        # to ensure the trace associated with main is saved
        wait_for_tracers()

if __name__ == "__main__":
    main_wait_traces()
```


## Example with langchain agents

When using `uipath-langchain` there is no need to call wait_for_tracers our framework will ensure that is called.

```python hl_lines="1"
@traced()
def my_custom_traced_function(input: str) -> str:
    return { "x": "some-output" }
```

You can also use `@traceable()` attribute from langchain, but we recommend using `@traced()` attribute instead.

```python hl_lines="1"
@traceable()
# @traced()  ---> do not use both at the same time or it will duplicate spans.
def my_custom_traced_function(input: str) -> str:
    return { "x": "some-output" }
```