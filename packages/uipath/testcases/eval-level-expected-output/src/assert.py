"""Assertions for eval-level-expected-output testcase.

Validates that evaluation-level expectedOutput is correctly injected
into output-based evaluators (ExactMatch, JsonSimilarity, LLMJudge)
while non-output evaluators (Contains) remain unaffected.
"""

import json
import os

# Evaluators expected in the deterministic eval set
DETERMINISTIC_EVALUATORS = {
    "ExactMatchEvaluator",
    "JsonSimilarityEvaluator",
    "ContainsEvaluator",
}

# Evaluators expected in the LLM judge eval set
LLM_JUDGE_EVALUATORS = {
    "ExactMatchEvaluator",
    "LLMJudgeOutputEvaluator",
}

# Evaluations in the deterministic eval set
DETERMINISTIC_EVALUATIONS = {
    "Eval-level expectedOutput with null criteria (addition)",
    "Eval-level expectedOutput with null criteria (multiplication)",
    "Per-evaluator expectedOutput overrides eval-level",
    "Mixed: some evaluators null, some explicit",
}

# Evaluations in the LLM judge eval set
LLM_JUDGE_EVALUATIONS = {
    "LLM Judge uses eval-level expectedOutput (addition)",
    "LLM Judge uses eval-level expectedOutput (multiplication)",
}


def validate_output_file(
    output_file: str,
    expected_evaluations: set[str],
    expected_evaluators: set[str],
    min_score: float = 0.99,
) -> None:
    """Validate an evaluation output file.

    Args:
        output_file: Path to the evaluation output JSON file.
        expected_evaluations: Set of evaluation names to expect.
        expected_evaluators: Set of evaluator IDs/names to expect.
        min_score: Minimum acceptable score for all evaluators.
    """
    assert os.path.isfile(output_file), f"Output file '{output_file}' not found"
    print(f"  Found output file: {output_file}")

    with open(output_file, "r", encoding="utf-8") as f:
        output_data = json.load(f)

    assert "evaluationSetResults" in output_data, "Missing 'evaluationSetResults'"

    evaluation_results = output_data["evaluationSetResults"]
    assert len(evaluation_results) > 0, "No evaluation results found"
    print(f"  Found {len(evaluation_results)} evaluation result(s)")

    failed_count = 0
    seen_evaluations: set[str] = set()
    seen_evaluators: set[str] = set()

    for eval_result in evaluation_results:
        eval_name = eval_result.get("evaluationName", "Unknown")
        seen_evaluations.add(eval_name)
        print(f"\n  Validating: {eval_name}")

        eval_run_results = eval_result.get("evaluationRunResults", [])
        assert len(eval_run_results) > 0, f"No run results for '{eval_name}'"

        for eval_run in eval_run_results:
            evaluator_id = eval_run.get("evaluatorId", "Unknown")
            evaluator_name = eval_run.get("evaluatorName", evaluator_id)
            result = eval_run.get("result", {})
            score = result.get("score")

            seen_evaluators.add(evaluator_id)

            is_passing = False
            if score is True:
                is_passing = True
            elif isinstance(score, (int, float)) and score >= min_score:
                is_passing = True

            if is_passing:
                display = f"{score:.2f}" if isinstance(score, float) else str(score)
                print(f"    {evaluator_name}: score={display} (pass)")
            else:
                print(
                    f"    {evaluator_name}: score={score} "
                    f"(FAILED - expected >= {min_score})"
                )
                failed_count += 1

    # Verify all expected evaluations were seen
    missing_evals = expected_evaluations - seen_evaluations
    if missing_evals:
        print(f"\n  Missing evaluations: {missing_evals}")
        failed_count += len(missing_evals)

    # Verify all expected evaluators were seen
    missing_evaluators = expected_evaluators - seen_evaluators
    if missing_evaluators:
        print(f"\n  Missing evaluators: {missing_evaluators}")
        failed_count += len(missing_evaluators)

    print(f"\n{'=' * 60}")
    print(f"  Failed: {failed_count}")
    print(f"{'=' * 60}")

    assert failed_count == 0, f"{failed_count} assertion(s) failed for {output_file}"
    print(f"\n  All assertions passed for {output_file}!")


def main() -> None:
    """Main assertion logic."""
    # 1. Validate deterministic evaluators (ExactMatch, JsonSimilarity, Contains)
    #    All scores should be >= 0.99 since these are deterministic calculations
    print("\n--- Deterministic Evaluators ---")
    validate_output_file(
        "eval-level-expected-output.json",
        expected_evaluations=DETERMINISTIC_EVALUATIONS,
        expected_evaluators=DETERMINISTIC_EVALUATORS,
        min_score=0.99,
    )

    # 2. Validate LLM judge evaluators
    #    ExactMatch should score >= 0.99, LLM judge scores can vary
    #    but should be > 0 (semantically correct answers)
    print("\n--- LLM Judge Evaluators ---")
    validate_output_file(
        "eval-level-expected-output-llm-judge.json",
        expected_evaluations=LLM_JUDGE_EVALUATIONS,
        expected_evaluators=LLM_JUDGE_EVALUATORS,
        min_score=0.5,  # LLM judge scores can vary, but should be well above 0
    )

    print("\n  All eval-level expectedOutput assertions passed!")


if __name__ == "__main__":
    main()
