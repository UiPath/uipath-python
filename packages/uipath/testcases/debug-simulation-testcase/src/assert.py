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

# ── 2. Verify weather report structure ────────────────────────────────────────
assert "current" in output, "Missing 'current' in output"
assert "forecast" in output, "Missing 'forecast' in output"
assert "summary" in output, "Missing 'summary' in output"

current = output["current"]
assert "city" in current, "Missing 'city' in current weather"
assert "temperature" in current, "Missing 'temperature' in current weather"
assert "condition" in current, "Missing 'condition' in current weather"
assert "humidity" in current, "Missing 'humidity' in current weather"

assert isinstance(current["temperature"], (int, float)), (
    "'temperature' must be a number"
)
assert isinstance(current["humidity"], int), "'humidity' must be an int"

# ── 3. Verify simulation produced non-default values ─────────────────────────
# Real tool impls return: temperature=20.0, condition="unknown", humidity=50,
# forecast=[]. The component simulation should return richer output.
simulated_something = (
    current["condition"] != "unknown"
    or current["humidity"] != 50
    or len(output["forecast"]) > 0
)
assert simulated_something, (
    "Output matches hardcoded real-tool defaults — simulation may not have run. "
    f"condition={current['condition']}, humidity={current['humidity']}, "
    f"forecast_len={len(output['forecast'])}"
)

print(
    f"Simulation confirmed: condition={current['condition']}, "
    f"humidity={current['humidity']}, forecast_days={len(output['forecast'])}"
)
print("All assertions passed.")
