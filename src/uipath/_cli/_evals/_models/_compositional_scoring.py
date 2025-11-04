"""Compositional evaluation scoring with weighted evaluators, cascading effects, and heat maps."""

from collections import defaultdict
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ScoringStrategy(str, Enum):
    """Strategy for aggregating evaluator scores."""

    WEIGHTED_AVERAGE = "weighted_average"
    MIN = "min"
    MAX = "max"
    PRODUCT = "product"
    HARMONIC_MEAN = "harmonic_mean"


class CascadeMode(str, Enum):
    """How cascading/interdependency affects scoring."""

    NONE = "none"  # No cascading - evaluators are independent
    MULTIPLICATIVE = "multiplicative"  # Multiply scores in sequence
    PENALTY = "penalty"  # Apply penalty based on previous failures
    CONDITIONAL = "conditional"  # Only run if previous evaluators pass threshold


class EvaluatorWeight(BaseModel):
    """Weight configuration for a single evaluator."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    evaluator_id: str
    weight: float = Field(default=1.0, ge=0.0)
    cascade_order: Optional[int] = Field(
        default=None,
        description="Order in cascade chain (lower runs first). None means no cascade.",
    )
    cascade_impact: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="How much this evaluator's failure impacts downstream (0.0-1.0)",
    )
    threshold: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Minimum score for this evaluator to pass (used in conditional cascade)",
    )


class CompositionalScoringConfig(BaseModel):
    """Configuration for compositional scoring across evaluators."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    strategy: ScoringStrategy = ScoringStrategy.WEIGHTED_AVERAGE
    cascade_mode: CascadeMode = CascadeMode.NONE
    evaluator_weights: List[EvaluatorWeight] = Field(default_factory=list)
    default_weight: float = Field(default=1.0, ge=0.0)
    normalize_weights: bool = Field(
        default=True, description="Whether to normalize weights to sum to 1.0"
    )


class EvaluatorScoreBreakdown(BaseModel):
    """Detailed score breakdown for a single evaluator."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    evaluator_id: str
    evaluator_name: str
    raw_score: float
    weighted_score: float
    weight: float
    cascade_penalty: float = Field(
        default=0.0, description="Penalty applied due to cascading failures (0.0 = no penalty)"
    )
    num_datapoints: int
    datapoint_scores: List[float] = Field(default_factory=list)


class CompositionalScoreResult(BaseModel):
    """Result of compositional scoring with detailed breakdown."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    final_score: float
    strategy: ScoringStrategy
    cascade_mode: CascadeMode
    evaluator_breakdowns: List[EvaluatorScoreBreakdown]
    total_datapoints: int


class FlowScoreResult(BaseModel):
    """Score result for a single flow/split."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    flow_id: str
    flow_name: str
    compositional_score: CompositionalScoreResult
    num_datapoints: int


class InterFlowCompositionalScore(BaseModel):
    """Aggregated compositional score across multiple flows."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    overall_score: float
    flow_scores: List[FlowScoreResult]
    weighted_by_datapoints: bool = Field(
        default=False,
        description="Whether scores were weighted by number of datapoints per flow",
    )


class HeatMapCell(BaseModel):
    """Single cell in evaluation heat map."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    flow_id: str
    evaluator_id: str
    score: float
    impact: float = Field(
        description="Impact on overall agent accuracy (0.0-1.0)"
    )
    num_datapoints: int


class EvalScoreHeatMap(BaseModel):
    """Heat map showing scores and impact of evaluators across flows."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    cells: List[HeatMapCell]
    flows: List[str]
    evaluators: List[str]

    def to_matrix(self) -> Dict[str, Any]:
        """Convert heat map to matrix format for visualization."""
        # Create a 2D matrix: flows x evaluators
        matrix = defaultdict(lambda: defaultdict(dict))

        for cell in self.cells:
            matrix[cell.flow_id][cell.evaluator_id] = {
                "score": cell.score,
                "impact": cell.impact,
                "num_datapoints": cell.num_datapoints,
            }

        return {
            "flows": self.flows,
            "evaluators": self.evaluators,
            "matrix": dict(matrix),
        }


class CompositionalScorer:
    """Orchestrates compositional scoring with various strategies and cascade modes."""

    @staticmethod
    def calculate_compositional_score(
        evaluator_scores: Dict[str, float],
        evaluator_datapoints: Dict[str, List[float]],
        config: CompositionalScoringConfig,
    ) -> CompositionalScoreResult:
        """Calculate compositional score with configured strategy and cascade mode.

        Args:
            evaluator_scores: Map of evaluator_id to average score (0-100)
            evaluator_datapoints: Map of evaluator_id to list of per-datapoint scores
            config: Compositional scoring configuration

        Returns:
            CompositionalScoreResult with detailed breakdown
        """
        # Build weight map
        weight_map = {ew.evaluator_id: ew for ew in config.evaluator_weights}

        # Prepare evaluator data
        evaluator_data = []
        for eval_id, raw_score in evaluator_scores.items():
            weight_config = weight_map.get(
                eval_id, EvaluatorWeight(evaluator_id=eval_id, weight=config.default_weight)
            )
            datapoints = evaluator_datapoints.get(eval_id, [])
            evaluator_data.append({
                "id": eval_id,
                "raw_score": raw_score,
                "weight": weight_config.weight,
                "cascade_order": weight_config.cascade_order,
                "cascade_impact": weight_config.cascade_impact,
                "threshold": weight_config.threshold,
                "datapoints": datapoints,
            })

        # Apply cascade mode
        cascade_penalties = CompositionalScorer._apply_cascade(
            evaluator_data, config.cascade_mode
        )

        # Calculate scores based on strategy
        breakdowns = []
        total_weighted_score = 0.0
        total_weight = 0.0

        for eval_data in evaluator_data:
            eval_id = eval_data["id"]
            raw_score = eval_data["raw_score"]
            weight = eval_data["weight"]
            cascade_penalty = cascade_penalties.get(eval_id, 0.0)

            # Apply cascade penalty
            adjusted_score = raw_score * (1.0 - cascade_penalty)

            # Calculate weighted score
            weighted_score = adjusted_score * weight

            breakdowns.append(
                EvaluatorScoreBreakdown(
                    evaluator_id=eval_id,
                    evaluator_name=eval_id,  # Could be enriched with actual name
                    raw_score=raw_score,
                    weighted_score=weighted_score,
                    weight=weight,
                    cascade_penalty=cascade_penalty * 100.0,  # Convert to percentage
                    num_datapoints=len(eval_data["datapoints"]),
                    datapoint_scores=eval_data["datapoints"],
                )
            )

            total_weighted_score += weighted_score
            total_weight += weight

        # Calculate final score based on strategy
        if config.strategy == ScoringStrategy.WEIGHTED_AVERAGE:
            if config.normalize_weights and total_weight > 0:
                final_score = total_weighted_score / total_weight
            else:
                final_score = total_weighted_score
        elif config.strategy == ScoringStrategy.MIN:
            final_score = min((b.weighted_score for b in breakdowns), default=0.0)
        elif config.strategy == ScoringStrategy.MAX:
            final_score = max((b.weighted_score for b in breakdowns), default=0.0)
        elif config.strategy == ScoringStrategy.PRODUCT:
            final_score = 1.0
            for breakdown in breakdowns:
                final_score *= (breakdown.weighted_score / 100.0)
            final_score *= 100.0  # Scale back to 0-100
        elif config.strategy == ScoringStrategy.HARMONIC_MEAN:
            if breakdowns:
                sum_reciprocals = sum(1.0 / max(b.weighted_score, 0.01) for b in breakdowns)
                final_score = len(breakdowns) / sum_reciprocals if sum_reciprocals > 0 else 0.0
            else:
                final_score = 0.0

        total_datapoints = sum(len(ed["datapoints"]) for ed in evaluator_data)

        return CompositionalScoreResult(
            final_score=final_score,
            strategy=config.strategy,
            cascade_mode=config.cascade_mode,
            evaluator_breakdowns=breakdowns,
            total_datapoints=total_datapoints,
        )

    @staticmethod
    def _apply_cascade(
        evaluator_data: List[Dict[str, Any]], cascade_mode: CascadeMode
    ) -> Dict[str, float]:
        """Apply cascade effects based on mode.

        Args:
            evaluator_data: List of evaluator data dicts
            cascade_mode: How to apply cascading

        Returns:
            Map of evaluator_id to cascade penalty (0.0-1.0)
        """
        penalties = {}

        if cascade_mode == CascadeMode.NONE:
            return {ed["id"]: 0.0 for ed in evaluator_data}

        # Sort by cascade_order (None goes to end)
        sorted_evals = sorted(
            evaluator_data,
            key=lambda x: (x["cascade_order"] is None, x["cascade_order"]),
        )

        if cascade_mode == CascadeMode.MULTIPLICATIVE:
            cumulative_failure = 0.0
            for eval_data in sorted_evals:
                eval_id = eval_data["id"]
                penalties[eval_id] = cumulative_failure

                # Update cumulative failure based on this evaluator's score
                failure_rate = 1.0 - (eval_data["raw_score"] / 100.0)
                cascade_impact = eval_data.get("cascade_impact", 1.0)
                cumulative_failure += failure_rate * cascade_impact * (1.0 - cumulative_failure)

        elif cascade_mode == CascadeMode.PENALTY:
            for i, eval_data in enumerate(sorted_evals):
                eval_id = eval_data["id"]

                # Calculate penalty based on all previous evaluators
                total_penalty = 0.0
                for prev_eval in sorted_evals[:i]:
                    prev_score = prev_eval["raw_score"]
                    prev_impact = prev_eval.get("cascade_impact", 1.0)

                    # Penalty increases with previous failures
                    failure_severity = (100.0 - prev_score) / 100.0
                    total_penalty += failure_severity * prev_impact

                penalties[eval_id] = min(total_penalty, 1.0)  # Cap at 1.0

        elif cascade_mode == CascadeMode.CONDITIONAL:
            for i, eval_data in enumerate(sorted_evals):
                eval_id = eval_data["id"]

                # Check if any previous evaluator failed threshold
                should_penalize = False
                for prev_eval in sorted_evals[:i]:
                    if prev_eval["raw_score"] < prev_eval.get("threshold", 0.0):
                        should_penalize = True
                        break

                penalties[eval_id] = 1.0 if should_penalize else 0.0

        return penalties

    @staticmethod
    def calculate_inter_flow_score(
        flow_scores: List[FlowScoreResult],
        weight_by_datapoints: bool = False,
    ) -> InterFlowCompositionalScore:
        """Calculate compositional score across multiple flows.

        Args:
            flow_scores: List of individual flow scores
            weight_by_datapoints: Whether to weight by number of datapoints

        Returns:
            InterFlowCompositionalScore with aggregated results
        """
        if not flow_scores:
            return InterFlowCompositionalScore(
                overall_score=0.0,
                flow_scores=[],
                weighted_by_datapoints=weight_by_datapoints,
            )

        if weight_by_datapoints:
            total_score = 0.0
            total_datapoints = 0

            for flow_score in flow_scores:
                total_score += flow_score.compositional_score.final_score * flow_score.num_datapoints
                total_datapoints += flow_score.num_datapoints

            overall_score = total_score / total_datapoints if total_datapoints > 0 else 0.0
        else:
            # Simple average across flows
            total_score = sum(fs.compositional_score.final_score for fs in flow_scores)
            overall_score = total_score / len(flow_scores)

        return InterFlowCompositionalScore(
            overall_score=overall_score,
            flow_scores=flow_scores,
            weighted_by_datapoints=weight_by_datapoints,
        )

    @staticmethod
    def generate_heat_map(
        inter_flow_score: InterFlowCompositionalScore,
    ) -> EvalScoreHeatMap:
        """Generate heat map from inter-flow compositional scores.

        Args:
            inter_flow_score: Inter-flow score result

        Returns:
            EvalScoreHeatMap with cells, flows, and evaluators
        """
        cells = []
        flow_ids = set()
        evaluator_ids = set()

        for flow_score in inter_flow_score.flow_scores:
            flow_ids.add(flow_score.flow_id)

            for breakdown in flow_score.compositional_score.evaluator_breakdowns:
                evaluator_ids.add(breakdown.evaluator_id)

                # Calculate impact as contribution to overall score
                # Impact = (evaluator's weighted score / total score) * (flow datapoints / total datapoints)
                flow_weight = 1.0
                if inter_flow_score.weighted_by_datapoints:
                    total_datapoints = sum(fs.num_datapoints for fs in inter_flow_score.flow_scores)
                    flow_weight = flow_score.num_datapoints / total_datapoints if total_datapoints > 0 else 0.0

                contribution = (breakdown.weighted_score / 100.0) * breakdown.weight * flow_weight

                cells.append(
                    HeatMapCell(
                        flow_id=flow_score.flow_id,
                        evaluator_id=breakdown.evaluator_id,
                        score=breakdown.raw_score,
                        impact=contribution,
                        num_datapoints=breakdown.num_datapoints,
                    )
                )

        return EvalScoreHeatMap(
            cells=cells,
            flows=sorted(flow_ids),
            evaluators=sorted(evaluator_ids),
        )
