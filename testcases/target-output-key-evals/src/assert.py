"""Assertions for target-output-key-evals testcase.

Validates that targetOutputKey path resolution works correctly across
legacy evaluators with nested dot-notation and array-index paths.
"""

import json
import os

EXPECTED_EVALUATORS = {
    "legacy-equality-full-output",
    "legacy-equality-flat-key",
    "legacy-equality-nested-path",
    "legacy-equality-deep-nested",
    "legacy-equality-array-index",
    "legacy-equality-array-tag",
    "legacy-json-similarity-nested",
    "legacy-json-similarity-customer",
}


def main() -> None:
    output_file = "target-output-key.json"
    assert os.path.isfile(output_file), f"Output file '{output_file}' not found"
    print(f"  Found output file: {output_file}")

    with open(output_file, "r", encoding="utf-8") as f:
        output_data = json.load(f)

    assert "evaluationSetResults" in output_data, "Missing 'evaluationSetResults'"

    evaluation_results = output_data["evaluationSetResults"]
    assert len(evaluation_results) > 0, "No evaluation results found"
    print(f"  Found {len(evaluation_results)} evaluation result(s)")

    failed_count = 0
    seen_evaluators: set[str] = set()

    for eval_result in evaluation_results:
        eval_name = eval_result.get("evaluationName", "Unknown")
        print(f"\n  Validating: {eval_name}")

        eval_run_results = eval_result.get("evaluationRunResults", [])
        assert len(eval_run_results) > 0, f"No run results for '{eval_name}'"

        for eval_run in eval_run_results:
            evaluator_id = eval_run.get("evaluatorId", "Unknown")
            evaluator_name = eval_run.get("evaluatorName", evaluator_id)
            result = eval_run.get("result", {})
            score = result.get("score")

            seen_evaluators.add(evaluator_id)

            # ExactMatch evaluators should score True (1/True)
            # JsonSimilarity evaluators should score 100.0
            if "equality" in evaluator_id or "exact" in evaluator_id.lower():
                if score is True or score == 1:
                    print(f"    {evaluator_name}: score={score} (exact match pass)")
                else:
                    print(
                        f"    {evaluator_name}: score={score} (FAILED - expected True)"
                    )
                    failed_count += 1
            elif "json-similarity" in evaluator_id:
                if isinstance(score, (int, float)) and score >= 99.0:
                    print(f"    {evaluator_name}: score={score:.1f} (similarity pass)")
                else:
                    print(
                        f"    {evaluator_name}: score={score} (FAILED - expected >= 99)"
                    )
                    failed_count += 1
            else:
                if score is not None and score > 0:
                    print(f"    {evaluator_name}: score={score}")
                else:
                    print(
                        f"    {evaluator_name}: score={score} (FAILED - expected > 0)"
                    )
                    failed_count += 1

    # Verify all expected evaluators were seen
    missing = EXPECTED_EVALUATORS - seen_evaluators
    if missing:
        print(f"\n  Missing evaluators: {missing}")
        failed_count += len(missing)

    print(f"\n{'=' * 60}")
    print(f"  Failed: {failed_count}")
    print(f"{'=' * 60}")

    assert failed_count == 0, f"{failed_count} assertion(s) failed"
    print("\n  All assertions passed!")


if __name__ == "__main__":
    main()
