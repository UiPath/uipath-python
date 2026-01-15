"""Legacy Context Precision evaluator for assessing the relevance of context chunks to queries."""

import ast
import json
from typing import Any, Optional

from uipath.eval.models import NumericEvaluationResult

from ...platform.chat import UiPathLlmChatService
from ..models.models import AgentExecution, EvaluationResult
from .legacy_base_evaluator import (
    LegacyBaseEvaluator,
    LegacyEvaluationCriteria,
    LegacyEvaluatorConfig,
    track_evaluation_metrics,
)
from .legacy_evaluator_utils import clean_model_name, serialize_object


class LegacyContextPrecisionEvaluatorConfig(LegacyEvaluatorConfig):
    """Configuration for legacy context precision evaluators."""

    name: str = "LegacyContextPrecisionEvaluator"
    model: str = ""
    prompt: str = """You are an expert evaluator assessing the relevance of context chunks to a given query.

TASK: Evaluate how relevant each provided context chunk is to answering the query.
Your scoring should be deterministic - the same chunk-query pair should always receive the same score.

EVALUATION CRITERIA:
Score each chunk using the HIGHEST applicable range (if multiple apply, use the highest):

- HIGHLY RELEVANT (80-100) - Directly answers or addresses the query:
  * 95-100: Contains the exact, complete answer to the query
  * 85-94: Directly addresses the query with comprehensive information (but not the complete answer)
  * 80-84: Provides a direct but partial answer to the query

- MODERATELY RELEVANT (50-79) - Provides useful supporting information:
  * 70-79: Contains substantial supporting information that helps understand the topic
  * 60-69: Provides relevant context or background information
  * 50-59: Has some connection to the query but limited usefulness

- SLIGHTLY RELEVANT (20-49) - Contains tangentially related information:
  * 35-49: Mentions related concepts, terms, or entities from the query
  * 20-34: Very indirect connection to the query topic

- NOT RELEVANT (0-19) - Has no meaningful connection to the query:
  * 10-19: Contains some keywords from the query but no meaningful connection
  * 0-9: Completely unrelated to the query or empty/malformed content

IMPORTANT INSTRUCTIONS:
1. Evaluate EACH chunk independently - do not let one chunk influence another's score
2. Base relevance ONLY on how well the chunk helps answer the specific query
3. Consider semantic meaning, not just keyword matches
4. If a chunk is empty or malformed, assign a score of 0
5. Scores must be integers between 0 and 100 inclusive
6. Be consistent: similar content should receive similar scores
7. Use the specific sub-ranges above to guide precise scoring
8. HIERARCHY RULE: If a chunk meets criteria for multiple ranges, always assign the HIGHEST applicable score

OUTPUT FORMAT:
You MUST respond using the provided tool with a JSON object containing:
- A "relevancies" field that is an array
- Each array element must be an object with "relevancy_score" (integer 0-100)
- The array must have the same number of elements as context chunks provided
- Order matters: the first score corresponds to the first chunk, etc.

EXAMPLE STRUCTURE (do not copy values, this is just format):
{
  "relevancies": [
    {"relevancy_score": 85},
    {"relevancy_score": 45},
    {"relevancy_score": 0}
  ]
}

<query>
{{Query}}
</query>

<context_chunks>
{{Chunks}}
</context_chunks>

Evaluate each chunk's relevance to the query and respond with the structured output."""


class LegacyContextPrecisionEvaluator(
    LegacyBaseEvaluator[LegacyContextPrecisionEvaluatorConfig]
):
    """Legacy evaluator that assesses context precision using an LLM.

    This evaluator extracts context grounding spans from agent execution traces
    and uses an LLM to score the relevance of each chunk to its corresponding query.
    The final score is the mean of all chunk relevancy scores (normalized to 0-1).
    """

    model: str
    query_placeholder: str = "{{Query}}"
    chunks_placeholder: str = "{{Chunks}}"
    llm: Optional[UiPathLlmChatService] = None

    def model_post_init(self, __context: Any):
        """Initialize the LLM service after model creation."""
        super().model_post_init(__context)
        self._initialize_llm()

    def _initialize_llm(self):
        """Initialize the LLM used for evaluation."""
        from uipath.platform import UiPath

        uipath = UiPath()
        self.llm = uipath.llm

    @track_evaluation_metrics
    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: LegacyEvaluationCriteria,
    ) -> EvaluationResult:
        """Evaluate context precision from agent execution traces.

        Args:
            agent_execution: The execution details containing agent_trace with spans
            evaluation_criteria: Legacy evaluation criteria (unused for context precision)

        Returns:
            NumericEvaluationResult with normalized score (0-1) and detailed justification
        """
        # Extract context grounding spans from the trace
        context_groundings = self._extract_context_groundings(
            agent_execution.agent_trace
        )

        if not context_groundings:
            return NumericEvaluationResult(
                score=0.0,
                details="No context grounding tool calls found in the agent execution trace.",
            )

        # Evaluate each context grounding call
        all_scores = []
        evaluation_details = []

        for idx, grounding in enumerate(context_groundings, 1):
            query = grounding.get("query", "")
            chunks = grounding.get("chunks", [])

            if not query or not chunks:
                evaluation_details.append(
                    f"{idx}. Query: (empty) - SKIPPED (no query or chunks)"
                )
                continue

            scores = await self._evaluate_context_grounding(query, chunks)

            if scores:
                mean_score = sum(scores) / len(scores)
                all_scores.append(mean_score)

                # Format score summaries for this grounding
                score_summaries = [f"Relevancy: {s:d}/100" for s in scores]
                evaluation_details.append(
                    f'{idx}. Query: "{query}"\n'
                    f"\tAvg. Score: {mean_score:.1f}/100 ({len(scores)} chunks). "
                    f"Chunk Relevancies: [{', '.join(score_summaries)}]."
                )

        if not all_scores:
            return NumericEvaluationResult(
                score=0.0,
                details="No valid context chunks were found for evaluation.",
            )

        # Calculate overall mean score (0-100 range)
        overall_mean = sum(all_scores) / len(all_scores)
        overall_mean = max(0, min(100, overall_mean))

        # Build justification
        justification = f"Overall Context Precision: {overall_mean:.1f}/100 ({len(context_groundings)} Context Tool Call(s) evaluated).\n"
        if evaluation_details:
            justification += "---\nPer-Context Tool Call Details:\n\n"
            justification += "\n\n".join(evaluation_details)

        return NumericEvaluationResult(
            score=overall_mean,
            details=justification,
        )

    def _parse_span_value(self, value_str: str) -> Any:
        """Parse span value that could be JSON or Python literal syntax.

        Args:
            value_str: String that could be JSON or Python literal (dict/list)

        Returns:
            Parsed Python object (dict, list, etc.)

        Raises:
            ValueError: If string cannot be parsed as JSON or literal
        """
        try:
            # Try JSON first (most common)
            return json.loads(value_str)
        except json.JSONDecodeError:
            try:
                # Fall back to Python literal_eval for Python syntax
                return ast.literal_eval(value_str)
            except (ValueError, SyntaxError) as e:
                raise ValueError(f"Cannot parse value: {value_str}") from e

    def _extract_context_groundings(
        self, agent_trace: list[Any]
    ) -> list[dict[str, Any]]:
        """Extract context groundings from agent execution trace.

        Looks for spans with input.value and output.value attributes that represent
        context grounding tool calls.
        """
        context_groundings = []

        for span in agent_trace:
            if not hasattr(span, "attributes") or span.attributes is None:
                continue

            attrs = span.attributes

            if attrs.get("openinference.span.kind", None) != "RETRIEVER":
                # NOTE: all tool calls can be extracted using this approach
                continue

            # Look for spans with input.value and output.value (context grounding calls)
            query = attrs.get("input.value")
            try:
                chunks = self._normalize_chunks(
                    json.loads(attrs.get("output.value")).get("documents")
                )

                if chunks:
                    context_groundings.append(
                        {
                            "query": str(query),
                            "chunks": chunks,
                        }
                    )
            except (ValueError, KeyError, TypeError):
                # Skip spans that don't have the expected structure
                continue

        return context_groundings

    def _normalize_chunks(self, results: Any) -> list[str]:
        """Normalize various chunk representations to a list of strings."""
        if isinstance(results, list):
            return [self._serialize_chunk(chunk) for chunk in results]
        elif isinstance(results, dict):
            # Handle dict representations of chunks
            return [self._serialize_chunk(results)]
        elif isinstance(results, str):
            return [results]
        else:
            return [str(results)]

    def _serialize_chunk(self, chunk: Any) -> str:
        """Serialize a single chunk to string format."""
        return serialize_object(chunk, sort_keys=True)

    async def _evaluate_context_grounding(
        self, query: str, chunks: list[str]
    ) -> list[int]:
        """Evaluate the relevance of chunks to a query using the LLM.

        Args:
            query: The query string
            chunks: List of context chunks to evaluate

        Returns:
            List of relevancy scores (0-100) for each chunk
        """
        # Create evaluation prompt
        chunks_text = "\n".join(chunks)
        prompt = self.evaluator_config.prompt.replace(
            self.query_placeholder, query
        ).replace(self.chunks_placeholder, chunks_text)

        # Get LLM response
        response_obj = await self._get_structured_llm_response(prompt)

        # Extract relevancy scores from response
        relevancies = response_obj.get("relevancies", [])
        if not relevancies:
            raise ValueError("No relevancies found in LLM response")

        scores = []
        for rel in relevancies:
            if isinstance(rel, dict) and "relevancy_score" in rel:
                score = rel["relevancy_score"]
                # Clamp score to 0-100
                score = max(0, min(100, int(score)))
                scores.append(score)

        return scores

    async def _get_structured_llm_response(
        self, evaluation_prompt: str
    ) -> dict[str, Any]:
        """Get structured LLM response using the context precision schema."""
        # Remove community-agents suffix from llm model name
        model = clean_model_name(self.model)

        # Prepare the request
        request_data = {
            "model": model,
            "messages": [
                {"role": "system", "content": "Context Precision Evaluation"},
                {"role": "user", "content": evaluation_prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "context_precision_evaluation",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "relevancies": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "relevancy_score": {
                                            "type": "number",
                                            "description": "Relevancy score for the chunk (0-100).",
                                        }
                                    },
                                    "required": ["relevancy_score"],
                                },
                                "description": "List of relevancy scores for each context chunk",
                            }
                        },
                        "required": ["relevancies"],
                    },
                },
            },
        }

        assert self.llm, "LLM should be initialized before calling this method."
        response = await self.llm.chat_completions(**request_data)
        content = response.choices[-1].message.content or "{}"
        return json.loads(content)
