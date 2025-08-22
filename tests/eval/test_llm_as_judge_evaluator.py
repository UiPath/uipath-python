"""Tests for LlmAsAJudgeEvaluator."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from uipath.eval.evaluators.llm_as_judge_evaluator import LlmAsAJudgeEvaluator
from uipath.eval.models import EvaluationResult, ScoreType


class TestLlmAsAJudgeEvaluator:
    """Test cases for LlmAsAJudgeEvaluator class."""

    def test_init_valid_prompt(self):
        """Test initialization with valid prompt containing required placeholders."""
        prompt = "Compare {{ActualOutput}} with {{ExpectedOutput}} and provide a score."
        model = "test-model"

        with patch.object(LlmAsAJudgeEvaluator, "_initialize_llm"):
            evaluator = LlmAsAJudgeEvaluator(prompt=prompt, model=model)

            assert evaluator.prompt == prompt
            assert evaluator.model == model
            assert evaluator.name == "LlmAsAJudgeEvaluator"
            assert evaluator.target_output_key == "*"

    def test_init_custom_parameters(self):
        """Test initialization with custom name, description, and target key."""
        prompt = "Evaluate {{ActualOutput}} against {{ExpectedOutput}}."
        model = "test-model"
        name = "CustomJudge"
        description = "Custom evaluation description"
        target_key = "result"

        with patch.object(LlmAsAJudgeEvaluator, "_initialize_llm"):
            evaluator = LlmAsAJudgeEvaluator(
                prompt=prompt,
                model=model,
                name=name,
                description=description,
                target_output_key=target_key,
            )

            assert evaluator.name == name
            assert evaluator.description == description
            assert evaluator.target_output_key == target_key

    def test_init_missing_actual_output_placeholder(self):
        """Test initialization fails when ActualOutput placeholder is missing."""
        prompt = "Compare with {{ExpectedOutput}} and provide a score."
        model = "test-model"

        with pytest.raises(ValueError) as excinfo:
            with patch.object(LlmAsAJudgeEvaluator, "_initialize_llm"):
                LlmAsAJudgeEvaluator(prompt=prompt, model=model)

        assert "{{ActualOutput}}" in str(excinfo.value)
        assert "missing required placeholders" in str(excinfo.value)

    def test_init_missing_expected_output_placeholder(self):
        """Test initialization fails when ExpectedOutput placeholder is missing."""
        prompt = "Compare {{ActualOutput}} with something and provide a score."
        model = "test-model"

        with pytest.raises(ValueError) as excinfo:
            with patch.object(LlmAsAJudgeEvaluator, "_initialize_llm"):
                LlmAsAJudgeEvaluator(prompt=prompt, model=model)

        assert "{{ExpectedOutput}}" in str(excinfo.value)
        assert "missing required placeholders" in str(excinfo.value)

    def test_init_missing_both_placeholders(self):
        """Test initialization fails when both placeholders are missing."""
        prompt = "Just provide a score."
        model = "test-model"

        with pytest.raises(ValueError) as excinfo:
            with patch.object(LlmAsAJudgeEvaluator, "_initialize_llm"):
                LlmAsAJudgeEvaluator(prompt=prompt, model=model)

        error_message = str(excinfo.value)
        assert "{{ActualOutput}}" in error_message
        assert "{{ExpectedOutput}}" in error_message
        assert "missing required placeholders" in error_message

    def test_create_evaluation_prompt(self):
        """Test prompt formatting with actual and expected outputs."""
        prompt = (
            "Compare {{ActualOutput}} with {{ExpectedOutput}} and score from 0-100."
        )
        model = "test-model"

        with patch.object(LlmAsAJudgeEvaluator, "_initialize_llm"):
            evaluator = LlmAsAJudgeEvaluator(prompt=prompt, model=model)

        expected_output = {"result": "Expected result"}
        actual_output = {"result": "Actual result"}

        formatted_prompt = evaluator._create_evaluation_prompt(
            expected_output, actual_output
        )

        expected = "Compare {'result': 'Actual result'} with {'result': 'Expected result'} and score from 0-100."
        assert formatted_prompt == expected

    @pytest.mark.asyncio
    async def test_evaluate_successful_llm_response(self):
        """Test successful evaluation with valid LLM response."""
        prompt = "Evaluate {{ActualOutput}} against {{ExpectedOutput}}."
        model = "test-model"

        # Mock LLM response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[
            0
        ].message.content = (
            '{"score": 85.5, "justification": "Good match with minor differences."}'
        )

        with patch.object(LlmAsAJudgeEvaluator, "_initialize_llm"):
            evaluator = LlmAsAJudgeEvaluator(prompt=prompt, model=model)
            evaluator.llm = AsyncMock()
            evaluator.llm.chat_completions.return_value = mock_response

        expected_output = {"result": "Expected"}
        actual_output = {"result": "Actual"}

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=expected_output,
            actual_output=actual_output,
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert isinstance(result, EvaluationResult)
        assert result.score == 85.5
        assert result.details == "Good match with minor differences."
        assert result.score_type == ScoreType.NUMERICAL

    @pytest.mark.asyncio
    async def test_evaluate_json_parse_error(self):
        """Test evaluation handles JSON parsing errors gracefully."""
        prompt = "Evaluate {{ActualOutput}} against {{ExpectedOutput}}."
        model = "test-model"

        # Mock LLM response with invalid JSON
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Invalid JSON response"

        with patch.object(LlmAsAJudgeEvaluator, "_initialize_llm"):
            evaluator = LlmAsAJudgeEvaluator(prompt=prompt, model=model)
            evaluator.llm = AsyncMock()
            evaluator.llm.chat_completions.return_value = mock_response

        expected_output = {"result": "Expected"}
        actual_output = {"result": "Actual"}

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=expected_output,
            actual_output=actual_output,
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert isinstance(result, EvaluationResult)
        assert result.score == 0.0
        assert (
            result.details is not None
            and "Error parsing LLM response" in result.details
        )
        assert result.score_type == ScoreType.ERROR

    @pytest.mark.asyncio
    async def test_evaluate_llm_exception(self):
        """Test evaluation handles LLM API exceptions gracefully."""
        prompt = "Evaluate {{ActualOutput}} against {{ExpectedOutput}}."
        model = "test-model"

        with patch.object(LlmAsAJudgeEvaluator, "_initialize_llm"):
            evaluator = LlmAsAJudgeEvaluator(prompt=prompt, model=model)
            evaluator.llm = AsyncMock()
            evaluator.llm.chat_completions.side_effect = Exception("API Error")

        expected_output = {"result": "Expected"}
        actual_output = {"result": "Actual"}

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=expected_output,
            actual_output=actual_output,
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert isinstance(result, EvaluationResult)
        assert result.score == 0.0
        assert (
            result.details is not None
            and "Error during LLM evaluation: API Error" in result.details
        )
        assert result.score_type == ScoreType.ERROR

    @pytest.mark.asyncio
    async def test_evaluate_community_agents_suffix_removal(self):
        """Test that community-agents suffix is removed from model name."""
        prompt = "Evaluate {{ActualOutput}} against {{ExpectedOutput}}."
        model = "test-model-community-agents"

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[
            0
        ].message.content = '{"score": 100, "justification": "Perfect match."}'

        with patch.object(LlmAsAJudgeEvaluator, "_initialize_llm"):
            evaluator = LlmAsAJudgeEvaluator(prompt=prompt, model=model)
            evaluator.llm = AsyncMock()
            evaluator.llm.chat_completions.return_value = mock_response

        expected_output = {"result": "Expected"}
        actual_output = {"result": "Actual"}

        await evaluator.evaluate(
            agent_input=None,
            expected_output=expected_output,
            actual_output=actual_output,
            uipath_eval_spans=None,
            execution_logs="",
        )

        # Check that the model name passed to LLM doesn't include the suffix
        call_args = evaluator.llm.chat_completions.call_args[1]
        assert call_args["model"] == "test-model"

    @pytest.mark.asyncio
    async def test_get_llm_response_request_format(self):
        """Test that LLM request is formatted correctly with JSON schema."""
        prompt = "Evaluate {{ActualOutput}} against {{ExpectedOutput}}."
        model = "test-model"

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[
            0
        ].message.content = '{"score": 75, "justification": "Reasonable match."}'

        with patch.object(LlmAsAJudgeEvaluator, "_initialize_llm"):
            evaluator = LlmAsAJudgeEvaluator(prompt=prompt, model=model)
            evaluator.llm = AsyncMock()
            evaluator.llm.chat_completions.return_value = mock_response

        evaluation_prompt = "Test evaluation prompt"

        await evaluator._get_llm_response(evaluation_prompt)

        # Verify the request structure
        call_args = evaluator.llm.chat_completions.call_args[1]

        assert call_args["model"] == model
        assert call_args["messages"] == [{"role": "user", "content": evaluation_prompt}]

        response_format = call_args["response_format"]
        assert response_format["type"] == "json_schema"

        schema = response_format["json_schema"]["schema"]
        assert "score" in schema["properties"]
        assert "justification" in schema["properties"]
        assert schema["required"] == ["score", "justification"]

        # Verify score constraints
        score_props = schema["properties"]["score"]
        assert score_props["minimum"] == 0
        assert score_props["maximum"] == 100
