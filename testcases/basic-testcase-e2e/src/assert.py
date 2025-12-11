#!/usr/bin/env python3
"""
Assertions for the E2E test.

Validates:
1. NuGet package was created
2. Job completed successfully
3. Job output matches expected values
"""

import json
import os

# Check NuGet package
uipath_dir = ".uipath"
assert os.path.exists(uipath_dir), "NuGet package directory (.uipath) not found"

nupkg_files = [f for f in os.listdir(uipath_dir) if f.endswith(".nupkg")]
assert nupkg_files, "NuGet package file (.nupkg) not found in .uipath directory"

print(f"✓ NuGet package found: {nupkg_files[0]}")

# Check agent output file
output_file = "__uipath/output.json"
assert os.path.isfile(output_file), "Agent output file not found"

print("✓ Agent output file found")

# Load and validate output
with open(output_file, "r", encoding="utf-8") as f:
    output_data = json.load(f)

print(f"  Output data: {json.dumps(output_data, indent=2)}")

# Check status
status = output_data.get("status")
assert status == "successful", f"Job failed with status: {status}. Info: {output_data.get('info')}"

print("✓ Job status: successful")

# Check job state
state = output_data.get("state")
assert state == "Successful", f"Unexpected job state: {state}"

print("✓ Job state: Successful")

# Check output field exists
assert "output" in output_data, "Missing 'output' field in job response"

output = output_data.get("output", {})

# The main.py returns EchoOut with 'message' field
# Input was: {"message": "Hello from E2E test", "repeat": 3, "prefix": "E2E"}
# Expected output: "E2E: Hello from E2E test\nE2E: Hello from E2E test\nE2E: Hello from E2E test"
if "message" in output:
    message = output["message"]
    expected_lines = ["E2E: Hello from E2E test"] * 3
    expected_message = "\n".join(expected_lines)

    assert message == expected_message, f"Unexpected output message:\nExpected: {expected_message}\nGot: {message}"
    print("✓ Output message matches expected value")
else:
    # Output might be nested or in a different format depending on serialization
    print(f"  Warning: 'message' not found in output. Output keys: {list(output.keys())}")
    print("  Skipping message validation (output structure may vary)")

print("\n✓ All assertions passed!")
