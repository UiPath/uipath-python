import json
import os

# ── 1. Verify agent output exists and succeeded ──────────────────────────────
output_file = "__uipath/output.json"
assert os.path.isfile(output_file), "Agent output file not found"

with open(output_file, "r", encoding="utf-8") as f:
    output_data = json.load(f)

status = output_data.get("status")
assert status == "successful", f"Agent execution failed with status: {status}"

output = output_data.get("output", {})

assert "syntax" in output, "Missing 'syntax' in output"
assert "style" in output, "Missing 'style' in output"
assert "improvements" in output, "Missing 'improvements' in output"
assert "summary" in output, "Missing 'summary' in output"

assert isinstance(output["syntax"]["valid"], bool), "'syntax.valid' must be a bool"
assert isinstance(output["syntax"]["errors"], list), "'syntax.errors' must be a list"

score = output["style"]["score"]
assert isinstance(score, int), "'style.score' must be an int"
assert 0 <= score <= 100, f"'style.score' out of range: {score}"
assert isinstance(output["style"]["violations"], list), (
    "'style.violations' must be a list"
)

assert isinstance(output["improvements"]["suggestions"], list), (
    "'improvements.suggestions' must be a list"
)
assert isinstance(output["improvements"]["refactored_snippet"], str), (
    "'improvements.refactored_snippet' must be a str"
)

# ── 2. Verify simulation produced non-default values ─────────────────────────
# Real tool impls always return: score=100, violations=[], suggestions=[].
# The LLM simulation should detect issues in the input code and return richer output.
simulated_something = (
    score < 100
    or len(output["style"]["violations"]) > 0
    or len(output["improvements"]["suggestions"]) > 0
)
assert simulated_something, (
    "Output matches hardcoded real-tool defaults — simulation may not have run. "
    f"style.score={score}, violations={output['style']['violations']}, "
    f"suggestions={output['improvements']['suggestions']}"
)

print(
    f"Simulation confirmed: score={score}, "
    f"violations={len(output['style']['violations'])}, "
    f"suggestions={len(output['improvements']['suggestions'])}"
)
print("All assertions passed.")
