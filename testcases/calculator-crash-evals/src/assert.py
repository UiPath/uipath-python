"""Assertions for calculator-crash-evals testcase.

This script validates that the calculator crash evaluations work correctly by:
1. Reading the evaluation output from __uipath/output.json
2. Validating that all evaluations have scores equal to 0 (since the calculator crashes)
"""

import json
import os


def main() -> None:
    """Main assertion logic."""
    # Check if output file exists
    output_file = "__uipath/output.json"

    assert os.path.isfile(output_file), (
        f"Evaluation output file '{output_file}' not found"
    )
    print(f"✓ Found evaluation output file: {output_file}")

    # Load evaluation results
    with open(output_file, "r", encoding="utf-8") as f:
        output_data = json.load(f)

    print("✓ Loaded evaluation output")

    # Check status
    status = output_data.get("status")
    assert status == "successful", f"Evaluation run failed with status: {status}"
    print("✓ Evaluation run status: successful")

    # Extract output data
    output = output_data.get("output", {})

    # Validate structure
    assert "evaluationSetResults" in output, "Missing 'evaluationSetResults' in output"

    evaluation_results = output["evaluationSetResults"]
    assert len(evaluation_results) > 0, "No evaluation results found"

    print(f"✓ Found {len(evaluation_results)} evaluation result(s)")

    # Validate each evaluation result
    passed_count = 0
    failed_count = 0
    skipped_count = 0
    all_scores_zero = True

    for eval_result in evaluation_results:
        eval_name = eval_result.get("evaluationName", "Unknown")
        print(f"\n→ Validating: {eval_name}")

        try:
            # Validate evaluation results are present
            eval_run_results = eval_result.get("evaluationRunResults", [])
            if len(eval_run_results) == 0:
                print(f"  ⊘ Skipping '{eval_name}' (no evaluation run results)")
                skipped_count += 1
                continue

            # Check that all evaluations have scores equal to 0
            all_passed = True
            for eval_run in eval_run_results:
                evaluator_name = eval_run.get("evaluatorName", "Unknown")
                result = eval_run.get("result", {})
                score = result.get("score", 0)

                # Check if score is equal to 0
                if score == 0:
                    print(f"  ✓ {evaluator_name}: score={score:.1f} (expected 0)")
                else:
                    print(f"  ✗ {evaluator_name}: score={score:.1f} (expected 0)")
                    all_passed = False
                    all_scores_zero = False

            if all_passed:
                print(f"  ✓ All evaluators passed for '{eval_name}' (all scores are 0)")
                passed_count += 1
            else:
                print(f"  ✗ Some evaluators failed for '{eval_name}'")
                failed_count += 1

        except Exception as e:
            print(f"  ✗ Error validating '{eval_name}': {e}")
            failed_count += 1

    # Final summary
    print(f"\n{'=' * 60}")
    print("Summary:")
    print(f"  Total evaluations: {passed_count + failed_count + skipped_count}")
    print(f"  ✓ Passed: {passed_count}")
    print(f"  ✗ Failed: {failed_count}")
    print(f"  ⊘ Skipped: {skipped_count}")
    print(f"{'=' * 60}")

    assert failed_count == 0, "Some assertions failed"
    assert all_scores_zero, "Not all evaluation scores are 0 as expected"

    print(
        "\n✅ All assertions passed! All scores are 0 as expected for crash scenarios."
    )


if __name__ == "__main__":
    main()
