"""LLM Input Mocker implementation."""

import json
from datetime import datetime
from typing import Any

from opentelemetry import trace

from uipath.core.tracing import traced
from uipath.platform import UiPath
from uipath.platform.chat import UiPathLlmChatService

from .._execution_context import eval_set_run_id_context
from ._mock_context import cache_manager_context
from ._mocker import UiPathInputMockingError
from ._types import (
    InputMockingStrategy,
)


def get_input_mocking_prompt(
    input_schema: str,
    input_generation_instructions: str,
    expected_behavior: str,
    expected_output: str,
) -> str:
    """Generate the LLM input mocking prompt."""
    current_datetime = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    return f"""You are simulating input for automated testing purposes of an Agent as part of a simulation run.
You will need to generate realistic input to a LLM agent which will call various tools to achieve a goal. This must be in the exact format of the INPUT_SCHEMA.
You may need to follow specific INPUT_GENERATION_INSTRUCTIONS. If no relevant instructions are provided pertaining to input generation, use the other provided information and your own judgement to generate input.
If the INPUT_GENERATION_INSTRUCTIONS are provided, you MUST follow them exactly. For example if the instructions say to generate a value for a field to be before a certain calendar date, you must generate a value that is before that date.

The current date and time is: {current_datetime}

#INPUT_SCHEMA: You MUST OUTPUT THIS EXACT JSON SCHEMA
{input_schema}
#END_INPUT_SCHEMA

#INPUT_GENERATION_INSTRUCTIONS
{input_generation_instructions}
#END_INPUT_GENERATION_INSTRUCTIONS

#EXPECTED_BEHAVIOR
{expected_behavior}
#END_EXPECTED_BEHAVIOR

#EXPECTED_OUTPUT
{expected_output}
#END_EXPECTED_OUTPUT

Based on the above information, provide a realistic input to the LLM agent. Your response should:
1. Match the expected input format according to the INPUT_SCHEMA exactly
2. Be consistent with the style and level of detail in the example inputs
3. Consider the context of the the agent being tested
4. Be realistic and representative of what a real user might say or ask

OUTPUT: ONLY the simulated agent input in the exact format of the INPUT_SCHEMA in valid JSON. Do not include any explanations, quotation marks, or markdown."""


@traced(name="Simulate Input")
async def generate_llm_input(
    mocking_strategy: InputMockingStrategy,
    input_schema: dict[str, Any],
    expected_behavior: str,
    expected_output: dict[str, Any],
    agent_model: str | None = None,
) -> dict[str, Any]:
    """Generate synthetic input using an LLM based on the evaluation context."""
    # Set custom span attributes to match agents repo pattern
    current_span = trace.get_current_span()
    if current_span and current_span.is_recording():
        current_span.set_attribute("span_type", "simulatedInput")
        current_span.set_attribute("type", "simulatedInput")
        current_span.set_attribute("uipath.custom_instrumentation", True)

    try:
        uipath = UiPath()
        llm = UiPathLlmChatService(
            uipath._config,
            uipath._execution_context,
            requesting_product="agentsplayground",
            requesting_feature="agents-evaluations",
            agenthub_config="agentsevals",
            action_id=eval_set_run_id_context.get(),
        )
        cache_manager = cache_manager_context.get()

        # Ensure additionalProperties is set for strict mode compatibility
        if "additionalProperties" not in input_schema:
            input_schema["additionalProperties"] = False

        prompt_generation_args = {
            "input_schema": json.dumps(input_schema),
            "input_generation_instructions": mocking_strategy.prompt
            if mocking_strategy
            else "",
            "expected_behavior": expected_behavior or "",
            "expected_output": json.dumps(expected_output),
        }

        prompt = get_input_mocking_prompt(**prompt_generation_args)

        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "agent_input",
                "strict": False,
                "schema": input_schema,
            },
        }

        model_parameters = mocking_strategy.model if mocking_strategy else None
        completion_kwargs = (
            model_parameters.model_dump(by_alias=False, exclude_none=True)
            if model_parameters
            else {}
        )

        # Use the agent's configured model when no simulation-specific model is set
        if "model" not in completion_kwargs and agent_model:
            completion_kwargs["model"] = agent_model

        if cache_manager is not None:
            cache_key_data = {
                "response_format": response_format,
                "completion_kwargs": completion_kwargs,
                "prompt_generation_args": prompt_generation_args,
            }

            cached_response = cache_manager.get(
                mocker_type="input_mocker",
                cache_key_data=cache_key_data,
                function_name="generate_llm_input",
            )

            if cached_response is not None:
                return cached_response

        response = await llm.chat_completions(
            [{"role": "user", "content": prompt}],
            response_format=response_format,
            **completion_kwargs,
        )

        generated_input_str = response.choices[0].message.content
        result = json.loads(generated_input_str)

        if cache_manager is not None:
            cache_manager.set(
                mocker_type="input_mocker",
                cache_key_data=cache_key_data,
                response=result,
                function_name="generate_llm_input",
            )

        return result
    except json.JSONDecodeError as e:
        raise UiPathInputMockingError(
            f"Failed to parse LLM response as JSON: {str(e)}"
        ) from e
    except UiPathInputMockingError:
        raise
    except Exception as e:
        raise UiPathInputMockingError(f"Failed to generate input: {str(e)}") from e
