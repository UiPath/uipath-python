"""Assertions for list-target-output-key-evals testcase.

Validates that evaluating multiple output fields at once (targetOutputKey as a
list) works correctly for both ExactMatch and JsonSimilarity evaluators.

Expected outcomes
-----------------
- headphones-all-match  : ListKeysExactMatch=1.0, ListKeysJsonSimilarity=1.0
- shoes-all-match       : ListKeysExactMatch=1.0, ListKeysJsonSimilarity=1.0
- headphones-wrong-price: ListKeysExactMatch=0.0, ListKeysJsonSimilarity=1.0
"""

import json
import os

# Maps evaluationName → evaluator ID → expected score (1.0 = pass, 0.0 = fail)
EXPECTED: dict[str, dict[str, float]] = {
    "Headphones - all keys match": {
        "ListKeysExactMatch": 1.0,
        "ListKeysJsonSimilarity": 1.0,
    },
    "Running Shoes - all keys match": {
        "ListKeysExactMatch": 1.0,
        "ListKeysJsonSimilarity": 1.0,
    },
    "Headphones - wrong price (should fail)": {
        "ListKeysExactMatch": 0.0,
        "ListKeysJsonSimilarity": 1.0,
    },
}


def main() -> None:
    output_file = "default.json"
    assert os.path.isfile(output_file), f"Output file '{output_file}' not found"
    print(f"Found output file: {output_file}")

    with open(output_file, "r", encoding="utf-8") as f:
        output_data = json.load(f)

    assert "evaluationSetResults" in output_data, "Missing 'evaluationSetResults'"
    evaluation_results = output_data["evaluationSetResults"]
    assert len(evaluation_results) > 0, "No evaluation results found"
    print(f"Found {len(evaluation_results)} evaluation result(s)")

    failures: list[str] = []

    for eval_result in evaluation_results:
        eval_name = eval_result.get("evaluationName", "")
        expected_scores = EXPECTED.get(eval_name)

        if expected_scores is None:
            print(f"  [skip] '{eval_name}' not in EXPECTED map")
            continue

        print(f"\n  Validating: {eval_name}")

        run_results = eval_result.get("evaluationRunResults", [])
        assert len(run_results) > 0, f"No run results for '{eval_name}'"

        for run in run_results:
            evaluator_id = run.get("evaluatorId", run.get("evaluatorName", ""))
            score = run.get("result", {}).get("score", None)

            if evaluator_id not in expected_scores:
                print(f"    [skip] unexpected evaluator '{evaluator_id}'")
                continue

            expected = expected_scores[evaluator_id]
            ok = score == expected
            status = "pass" if ok else "FAIL"
            print(f"    {evaluator_id}: score={score} expected={expected} ({status})")
            if not ok:
                failures.append(
                    f"{eval_name} / {evaluator_id}: got {score}, expected {expected}"
                )

    print(f"\n{'=' * 60}")
    if failures:
        for f in failures:
            print(f"  FAIL: {f}")
        print(f"{'=' * 60}")
        assert False, f"{len(failures)} assertion(s) failed"

    print("  All assertions passed!")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
