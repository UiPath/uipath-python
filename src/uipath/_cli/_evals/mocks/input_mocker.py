"""LLM Input Mocker implementation."""

import json
from datetime import datetime
from typing import Any, Dict

from uipath import UiPath
from uipath._cli._evals._models._evaluation_set import EvaluationItem
from uipath.tracing._traced import traced

from .cache_manager import CacheManager
from .mocker import UiPathInputMockingError


def get_input_mocking_prompt(
    input_schema: str,
    input_generation_instructions: str,
    expected_behavior: str,
    expected_output: str,
) -> str:
    """Generate the LLM input mocking prompt."""
    current_date = datetime.utcnow().strftime("%Y-%m-%d")

    return f"""You are simulating input for automated testing purposes of an Agent as part of a simulation run.
You will need to generate realistic input to a LLM agent which will call various tools to achieve a goal. This must be in the exact format of the INPUT_SCHEMA.
You may need to follow specific INPUT_GENERATION_INSTRUCTIONS. If no relevant instructions are provided pertaining to input generation, use the other provided information and your own judgement to generate input.
If the INPUT_GENERATION_INSTRUCTIONS are provided, you MUST follow them exactly. For example if the instructions say to generate a value for a field to be before a certain calendar date, you must generate a value that is before that date.

The current date is: {current_date}

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


@traced(name="__mocker__")
async def generate_llm_input(
    evaluation_item: EvaluationItem,
    input_schema: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate synthetic input using an LLM based on the evaluation context."""
    try:
        llm = UiPath().llm

        prompt = get_input_mocking_prompt(
            input_schema=json.dumps(input_schema, indent=2),
            input_generation_instructions=evaluation_item.input_mocking_strategy.prompt
            if evaluation_item.input_mocking_strategy
            else "",
            expected_behavior=evaluation_item.expected_agent_behavior or "",
            expected_output=json.dumps(evaluation_item.expected_output, indent=2)
            if evaluation_item.expected_output
            else "",
        )

        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "agent_input",
                "strict": True,
                "schema": input_schema,
            },
        }

        model_parameters = (
            evaluation_item.input_mocking_strategy.model
            if evaluation_item.input_mocking_strategy
            else None
        )
        completion_kwargs = (
            model_parameters.model_dump(by_alias=False, exclude_none=True)
            if model_parameters
            else {}
        )

        cache_key_data = {
            "prompt": prompt,
            "response_format": response_format,
            "completion_kwargs": completion_kwargs,
        }

        cached_response = CacheManager.get(
            mocker_type="input_mocker",
            eval_set_id=evaluation_item.eval_set_id,
            eval_item_id=evaluation_item.id,
            cache_key_data=cache_key_data,
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

        CacheManager.set(
            mocker_type="input_mocker",
            eval_set_id=evaluation_item.eval_set_id,
            eval_item_id=evaluation_item.id,
            cache_key_data=cache_key_data,
            response=result,
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
