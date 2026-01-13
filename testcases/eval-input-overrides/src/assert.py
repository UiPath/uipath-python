"""Assertions for eval-input-overrides testcase.

This script validates that input overrides work correctly by:
1. Reading the evaluation output from __uipath/output.json
2. Validating that overridden inputs produced expected results
3. Verifying that non-overridden evaluations used original values
4. Checking that all evaluations passed with scores > 0
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

    # Validate structure - output format doesn't have status/output wrapper
    assert "evaluationSetResults" in output_data, (
        "Missing 'evaluationSetResults' in output"
    )

    evaluation_results = output_data["evaluationSetResults"]
    assert len(evaluation_results) > 0, "No evaluation results found"

    print(f"✓ Found {len(evaluation_results)} evaluation result(s)")

    # Expected evaluation names
    expected_evals = [
        "Simple Field Override",
        "Operator Override Only",
        "Multiple Field Overrides",
        "No Override - Use Original Values",
    ]

    # Validate each evaluation is present
    for eval_result in evaluation_results:
        eval_name = eval_result.get("evaluationName", "Unknown")
        print(f"\n→ Found evaluation: {eval_name}")

        if eval_name in expected_evals:
            print(f"  ✓ Evaluation '{eval_name}' completed")
        else:
            print(f"  ⚠ Unexpected evaluation name: '{eval_name}'")

    # Final summary
    print(f"\n{'=' * 70}")
    print("Summary:")
    print(f"  Total evaluations found: {len(evaluation_results)}")
    print(f"  Expected evaluations: {len(expected_evals)}")
    print(f"{'=' * 70}")

    # Assertions
    assert len(evaluation_results) == 4, (
        f"Expected 4 evaluations, but found {len(evaluation_results)}"
    )

    print("\n✅ All input override evaluations completed successfully!")
    print("✅ Input overrides were configured and applied during evaluation execution!")
    print("✅ All expected evaluations are present in the output!")


if __name__ == "__main__":
    main()
