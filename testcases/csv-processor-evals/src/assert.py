"""Assertions for csv-processor-evals testcase.

This script validates that the CSV processor evaluations work correctly by:
1. Reading the evaluation output from file-input-tests-local.json
2. Validating that evaluations have scores equal to 1.0
"""

import json
import os


def main() -> None:
    """Main assertion logic."""
    # Check if output file exists
    output_file = "file-input-tests-local.json"
    assert os.path.isfile(output_file), (
        f"Evaluation output file '{output_file}' not found"
    )
    print(f"✓ Found evaluation output file: {output_file}")

    # Load evaluation results
    with open(output_file, "r", encoding="utf-8") as f:
        output_data = json.load(f)

    print("✓ Loaded evaluation output")

    # Extract output data
    output = output_data

    # Validate structure
    assert "evaluationSetResults" in output, "Missing 'evaluationSetResults' in output"

    evaluation_results = output["evaluationSetResults"]
    assert len(evaluation_results) > 0, "No evaluation results found"

    print(f"✓ Found {len(evaluation_results)} evaluation result(s)")

    # Validate each evaluation result
    passed_count = 0
    failed_count = 0
    skipped_count = 0
    has_perfect_scores = False

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

            # Check that evaluations have scores = 1.0
            all_passed = True
            min_score = 100
            for eval_run in eval_run_results:
                evaluator_name = eval_run.get("evaluatorName", "Unknown")
                result = eval_run.get("result", {})
                score = result.get("score", 0)
                min_score = min(min_score, score)

                # Check if score is 1.0
                if score == 1.0:
                    has_perfect_scores = True
                    print(f"  ✓ {evaluator_name}: score={score:.1f}")
                else:
                    print(f"  ✗ {evaluator_name}: score={score:.1f} (expected 1.0)")
                    all_passed = False

            if all_passed and min_score == 1.0:
                print(f"  ✓ All evaluators passed for '{eval_name}' (all scores: 1.0)")
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
    assert has_perfect_scores, "No evaluation scores equal to 1.0 were found"

    print("\n✅ All assertions passed!")

    # Check __uipath/output.json if it exists
    output_file = "__uipath/output.json"
    if os.path.isfile(output_file):
        print(f"\n✓ Found evaluation output file: {output_file}")

        # Load evaluation results
        with open(output_file, "r", encoding="utf-8") as f:
            output_data = json.load(f)

        print("✓ Loaded evaluation output")

        # Check status
        status = output_data.get("status")
        assert status == "successful", f"Evaluation run failed with status: {status}"
        print("✓ Evaluation run status: successful")


if __name__ == "__main__":
    main()
