import json
import os

# Check NuGet package
uipath_dir = ".uipath"
assert os.path.exists(uipath_dir), "NuGet package directory (.uipath) not found"

nupkg_files = [f for f in os.listdir(uipath_dir) if f.endswith(".nupkg")]
assert nupkg_files, "NuGet package file (.nupkg) not found in .uipath directory"

print(f"NuGet package found: {nupkg_files[0]}")

# Check agent output file
output_file = "__uipath/output.json"
assert os.path.isfile(output_file), "Agent output file not found"

print("Agent output file found")

# Check status and required fields
with open(output_file, "r", encoding="utf-8") as f:
    output_data = json.load(f)

# Check status
status = output_data.get("status")
assert status == "successful", f"Agent execution failed with status: {status}"

print("Agent execution status: successful")

# Check required fields for ticket classification agent
assert "output" in output_data, "Missing 'output' field in agent response"

print("Required fields validation passed")
