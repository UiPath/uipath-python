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

# Check required fields and structure
assert "output" in output_data, "Missing 'output' field in agent response"

# Check the specific structure of the output
output_section = output_data.get("output")
assert isinstance(output_section, dict), "Output field should be a dictionary"
assert "joke" in output_section, "Missing 'joke' field in output section"
assert "critique" in output_section, "Missing 'critique' field in output section"

# Check that the fields are not empty
joke = output_section.get("joke")
critique = output_section.get("critique")
assert joke and isinstance(joke, str), "Joke field should be a non-empty string"
assert critique and isinstance(critique, str), (
    "Critique field should be a non-empty string"
)

print("Required fields validation passed")
print(f"Output structure validation passed - joke: '{joke}', critique: '{critique}'")
