"""Legacy Faithfulness evaluator for assessing whether agent output claims are grounded in context."""

import json
from typing import Any, Optional

from uipath.eval.models import NumericEvaluationResult
from uipath.platform.chat import UiPathLlmChatService

from ..models.models import AgentExecution, EvaluationResult
from .legacy_base_evaluator import (
    LegacyBaseEvaluator,
    LegacyEvaluationCriteria,
    LegacyEvaluatorConfig,
    track_evaluation_metrics,
)
from .legacy_evaluator_utils import (
    clean_model_name,
    serialize_object,
)


class LegacyFaithfulnessEvaluatorConfig(LegacyEvaluatorConfig):
    """Configuration for legacy faithfulness evaluators."""

    name: str = "LegacyFaithfulnessEvaluator"
    model: str = ""


class LegacyFaithfulnessEvaluator(
    LegacyBaseEvaluator[LegacyFaithfulnessEvaluatorConfig]
):
    """Legacy evaluator that assesses faithfulness using an LLM.

    This evaluator extracts claims from agent output using a 3-stage pipeline
    (selection, disambiguation, decomposition) and evaluates whether each claim
    is grounded in the available context sources extracted from agent traces.
    The final score is the percentage of claims that are grounded.
    """

    model: str
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
        """Evaluate faithfulness of agent output against available context.

        Args:
            agent_execution: The execution details containing agent_trace with spans
            evaluation_criteria: Legacy evaluation criteria containing expected_output

        Returns:
            NumericEvaluationResult with normalized score (0-100) and detailed justification
        """
        # Extract agent output
        agent_output = str(evaluation_criteria.expected_output or "")
        if not agent_output or not agent_output.strip():
            return NumericEvaluationResult(
                score=0.0,
                details="No agent output provided for faithfulness evaluation.",
            )

        # Extract context sources from traces
        context_sources = self._extract_context_sources(agent_execution.agent_trace)

        if not context_sources:
            return NumericEvaluationResult(
                score=0.0,
                details="No context sources found in the agent execution trace.",
            )

        # Stage 1: Extract verifiable claims from agent output
        claims = await self._extract_claims(agent_output)

        if not claims:
            return NumericEvaluationResult(
                score=100.0,
                details="No verifiable claims found in agent output.",
            )

        # Stage 2: Evaluate each claim against context sources
        claim_evaluations = await self._evaluate_claims_against_context(
            claims, context_sources
        )

        # Calculate score
        grounded_claims = [c for c in claim_evaluations if c["is_grounded"]]
        score = (
            (len(grounded_claims) / len(claim_evaluations)) * 100
            if claim_evaluations
            else 0.0
        )
        score = max(0, min(100, score))

        # Build justification
        justification = self._format_justification(score, claim_evaluations)

        return NumericEvaluationResult(
            score=score,
            details=justification,
        )

    def _extract_context_sources(self, agent_trace: list[Any]) -> list[dict[str, str]]:
        """Extract context sources from agent execution trace.

        Looks for tool call outputs and context grounding spans that provide context.

        Returns:
            List of context source dicts with 'content' and 'source' keys
        """
        context_sources = []

        for span in agent_trace:
            if not hasattr(span, "attributes") or span.attributes is None:
                continue

            attrs = span.attributes

            tool_name = attrs.get("openinference.span.kind")
            if not tool_name or tool_name == "UNKNOWN":
                continue

            output_value = attrs.get("output.value")
            if not output_value:
                continue

            try:
                output_data = (
                    json.loads(output_value)
                    if isinstance(output_value, str)
                    else output_value
                )

                # For RETRIEVER spans, extract individual documents
                if tool_name == "RETRIEVER":
                    documents = output_data.get("documents", [])
                    if documents:
                        for doc in documents:
                            content = self._serialize_content(doc)
                            context_sources.append(
                                {"content": content, "source": "Context Grounding"}
                            )
                else:
                    # For other tool calls, extract the full output
                    content = self._serialize_content(output_data)
                    context_sources.append({"content": content, "source": tool_name})
            except (ValueError, TypeError):
                continue

        return context_sources

    def _serialize_content(self, content: Any) -> str:
        """Serialize content to string format."""
        return serialize_object(content, sort_keys=False)

    async def _extract_claims(self, agent_output: str) -> list[dict[str, str]]:
        """Extract verifiable claims from agent output using 3-stage pipeline.

        Stages:
        1. Selection: Filter to verifiable sentences
        2. Disambiguation: Resolve internal ambiguities
        3. Decomposition: Extract standalone claims

        Returns:
            List of claim dicts with 'text' and 'original_sentence' keys
        """
        # Stage 1: Selection
        verifiable_sentences = await self._select_verifiable_sentences(agent_output)
        if not verifiable_sentences:
            return []

        # Stage 2: Disambiguation
        disambiguated_sentences = await self._disambiguate_sentences(
            verifiable_sentences, agent_output
        )
        if not disambiguated_sentences:
            return []

        # Stage 3: Decomposition
        claims = await self._decompose_to_claims(disambiguated_sentences, agent_output)
        return claims

    async def _select_verifiable_sentences(self, agent_output: str) -> list[str]:
        """Stage 1: Filter agent output to verifiable sentences."""
        prompt = f"""You are an expert evaluator identifying verifiable claims.

TASK: Identify sentences in the agent output that contain verifiable, factual claims.
Filter out subjective opinions, instructions, questions, and meta-commentary.

OUTPUT FORMAT: Return a JSON object with a "sentences" field containing an array of strings.
Each string should be a complete sentence from the original output.

<agent_output>
{agent_output}
</agent_output>

Identify and return only the verifiable sentences."""

        response_obj = await self._get_structured_llm_response(
            prompt,
            schema_name="claim_selection",
            schema={
                "type": "object",
                "properties": {
                    "sentences": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of verifiable sentences from agent output",
                    }
                },
                "required": ["sentences"],
            },
        )

        return response_obj.get("sentences", [])

    async def _disambiguate_sentences(
        self, sentences: list[str], full_output: str
    ) -> list[dict[str, str]]:
        """Stage 2: Resolve ambiguities in sentences."""
        if not sentences:
            return []

        sentences_text = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(sentences))

        prompt = f"""You are an expert at disambiguating claims.

TASK: For each sentence, resolve any internal ambiguities using the full agent output as context.
Replace pronouns, references, and implicit information with explicit, standalone versions.

<full_agent_output>
{full_output}
</full_agent_output>

<sentences_to_disambiguate>
{sentences_text}
</sentences_to_disambiguate>

OUTPUT FORMAT: Return a JSON object with a "disambiguated" field containing an array of objects.
Each object must have:
- "original": the original sentence
- "disambiguated": the disambiguated version"""

        response_obj = await self._get_structured_llm_response(
            prompt,
            schema_name="claim_disambiguation",
            schema={
                "type": "object",
                "properties": {
                    "disambiguated": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "original": {"type": "string"},
                                "disambiguated": {"type": "string"},
                            },
                            "required": ["original", "disambiguated"],
                        },
                        "description": "List of disambiguated sentences",
                    }
                },
                "required": ["disambiguated"],
            },
        )

        return response_obj.get("disambiguated", [])

    async def _decompose_to_claims(
        self, disambiguated: list[dict[str, str]], full_output: str
    ) -> list[dict[str, str]]:
        """Stage 3: Decompose sentences into standalone verifiable claims."""
        if not disambiguated:
            return []

        sentences_text = "\n".join(
            f"{i + 1}. {item.get('disambiguated', '')}"
            for i, item in enumerate(disambiguated)
        )

        prompt = f"""You are an expert at claim decomposition.

TASK: Break down each sentence into standalone, atomic claims that can be independently verified.
Each claim should be self-contained and not depend on other claims for context.

<sentences>
{sentences_text}
</sentences>

<full_context>
{full_output}
</full_context>

OUTPUT FORMAT: Return a JSON object with a "claims" field containing an array of objects.
Each object must have:
- "claim": the standalone claim
- "original_sentence": which sentence it came from (number)"""

        response_obj = await self._get_structured_llm_response(
            prompt,
            schema_name="claim_decomposition",
            schema={
                "type": "object",
                "properties": {
                    "claims": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "claim": {"type": "string"},
                                "original_sentence": {"type": "string"},
                            },
                            "required": ["claim", "original_sentence"],
                        },
                        "description": "List of decomposed claims",
                    }
                },
                "required": ["claims"],
            },
        )

        claims_data = response_obj.get("claims", [])
        return [
            {
                "text": c.get("claim", ""),
                "original_sentence": c.get("original_sentence", ""),
            }
            for c in claims_data
            if c.get("claim", "").strip()
        ]

    async def _evaluate_claims_against_context(
        self,
        claims: list[dict[str, str]],
        context_sources: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        """Evaluate each claim against context sources.

        Returns:
            List of claim evaluations with grounding status and source attribution
        """
        claim_evaluations = []

        for claim in claims:
            claim_text = claim.get("text", "")
            if not claim_text.strip():
                continue

            supporting_sources = []
            contradicting_sources = []

            # Evaluate claim against each context source
            for source in context_sources:
                source_content = source.get("content", "")
                source_name = source.get("source", "Unknown")

                stance = await self._evaluate_claim_stance(claim_text, source_content)

                if stance == "SUPPORTS":
                    supporting_sources.append(source_name)
                elif stance == "CONTRADICTS":
                    contradicting_sources.append(source_name)

            # A claim is grounded if it has supporting sources and no contradicting ones
            is_grounded = (
                len(supporting_sources) > 0 and len(contradicting_sources) == 0
            )

            claim_evaluations.append(
                {
                    "claim": claim_text,
                    "original_sentence": claim.get("original_sentence", ""),
                    "is_grounded": is_grounded,
                    "supporting_sources": supporting_sources,
                    "contradicting_sources": contradicting_sources,
                }
            )

        return claim_evaluations

    async def _evaluate_claim_stance(self, claim: str, context: str) -> str:
        """Evaluate whether a context source supports, contradicts, or is irrelevant to a claim.

        Returns:
            One of: "SUPPORTS", "CONTRADICTS", "IRRELEVANT"
        """
        prompt = f"""You are an expert evaluator assessing the relationship between claims and sources.

TASK: Determine if the source supports, contradicts, or is irrelevant to the claim.

DEFINITION:
- SUPPORTS: The source provides evidence that makes the claim more likely to be true
- CONTRADICTS: The source provides evidence that makes the claim false or less likely
- IRRELEVANT: The source does not address the claim at all

<claim>
{claim}
</claim>

<source>
{context}
</source>

OUTPUT FORMAT: Return a JSON object with a "stance" field.
The stance must be exactly one of: "SUPPORTS", "CONTRADICTS", or "IRRELEVANT"."""

        response_obj = await self._get_structured_llm_response(
            prompt,
            schema_name="claim_stance_evaluation",
            schema={
                "type": "object",
                "properties": {
                    "stance": {
                        "type": "string",
                        "enum": ["SUPPORTS", "CONTRADICTS", "IRRELEVANT"],
                        "description": "Stance of the source relative to the claim",
                    }
                },
                "required": ["stance"],
            },
        )

        stance = response_obj.get("stance", "IRRELEVANT").upper()
        if stance not in ["SUPPORTS", "CONTRADICTS", "IRRELEVANT"]:
            stance = "IRRELEVANT"

        return stance

    def _format_justification(
        self, score: float, claim_evaluations: list[dict[str, Any]]
    ) -> str:
        """Format detailed justification with claim breakdown."""
        grounded_claims = [c for c in claim_evaluations if c["is_grounded"]]
        ungrounded_claims = [c for c in claim_evaluations if not c["is_grounded"]]

        justification = (
            f"Overall Faithfulness: {score:.1f}/100 "
            f"({len(grounded_claims)}/{len(claim_evaluations)} claims grounded).\n"
        )

        if claim_evaluations:
            justification += "---\n"

            if grounded_claims:
                justification += "\n✓ GROUNDED CLAIMS:\n\n"
                for i, eval_item in enumerate(grounded_claims, 1):
                    justification += f'{i}. "{eval_item["claim"]}"\n'
                    if eval_item["supporting_sources"]:
                        sources_str = ", ".join(eval_item["supporting_sources"])
                        justification += f"   Supporting Sources: {sources_str}\n"
                    justification += "\n"

            if ungrounded_claims:
                justification += "\n✗ UNGROUNDED CLAIMS:\n\n"
                for i, eval_item in enumerate(ungrounded_claims, 1):
                    justification += f'{i}. "{eval_item["claim"]}"\n'
                    if eval_item["contradicting_sources"]:
                        sources_str = ", ".join(eval_item["contradicting_sources"])
                        justification += f"   Contradicting Sources: {sources_str}\n"
                    if (
                        not eval_item["supporting_sources"]
                        and not eval_item["contradicting_sources"]
                    ):
                        justification += "   No supporting sources found in context.\n"
                    justification += "\n"

        return justification.rstrip()

    async def _get_structured_llm_response(
        self,
        evaluation_prompt: str,
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Get structured LLM response using JSON schema."""
        # Remove community-agents suffix from llm model name
        model = clean_model_name(self.model)

        # Prepare the request
        request_data = {
            "model": model,
            "messages": [
                {"role": "system", "content": "Faithfulness Evaluation"},
                {"role": "user", "content": evaluation_prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "schema": schema,
                },
            },
        }

        assert self.llm, "LLM should be initialized before calling this method."
        response = await self.llm.chat_completions(**request_data)
        content = response.choices[-1].message.content or "{}"
        return json.loads(content)
