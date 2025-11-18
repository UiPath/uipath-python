import json

with open("results/extraction_response.json", "r") as f:
    extraction_response = json.load(f)

with open("expected/extraction_response_expected.json", "r") as f:
    extraction_response_expected = json.load(f)

assert extraction_response == extraction_response_expected