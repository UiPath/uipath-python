# Job Attachment Evaluation Sample

This sample demonstrates end-to-end evaluation of agent outputs stored as job attachments.

## Overview

When an agent produces large outputs (reports, documents, data files), it's more efficient to store them as job attachments rather than returning them directly. This sample shows how to:

1. **Create and upload job attachments** from an agent
2. **Return attachment URIs** as agent output
3. **Automatically download and evaluate** attachment content

The evaluation framework automatically detects attachment URIs (pattern: `urn:uipath:cas:file:orchestrator:{uuid}`), downloads the content, and evaluates it against expected criteria.

## Features Demonstrated

- **Attachment Upload**: Upload text content as a job attachment
- **Attachment URI Output**: Return the attachment URI in agent output
- **Automatic Download**: Evaluators automatically download and read attachment content
- **Multiple Evaluator Types**: ExactMatch, Contains, and LineByLine evaluation
- **Different Report Types**: Sales, inventory, employee, and generic reports

## Prerequisites

```bash
# Ensure you have UiPath credentials configured
export UIPATH_URL="https://your-tenant.uipath.com"
export UIPATH_ACCESS_TOKEN="your-access-token"

# Or use the auth command
uipath auth
```

## Installation

```bash
cd samples/attachment_evaluation_test

# Install dependencies
uv sync

# Verify installation
uv run uipath --version
```

## Usage

### Run the Agent Manually

```bash
# Generate a sales report
uv run uipath run main '{"task": "Generate sales report"}'

# Generate an inventory report
uv run uipath run main '{"task": "Generate inventory report"}'

# Generate an employee report
uv run uipath run main '{"task": "Generate employee report"}'

# Generate a generic report
uv run uipath run main '{"task": "Complete project review"}'
```

**Output format:**
```json
{
  "report": "urn:uipath:cas:file:orchestrator:12345678-1234-1234-1234-123456789abc",
  "task": "Generate sales report",
  "status": "completed"
}
```

The `report` field contains the attachment URI which evaluators will automatically download and evaluate.

### Run Evaluations

```bash
# Run all evaluation test cases
uv run uipath eval main evaluations/eval-sets/default.json --workers 1

# Run with detailed output
uv run uipath eval main evaluations/eval-sets/default.json --workers 1 --verbose
```

## Evaluation Results

The sample includes 5 test cases with 3 evaluators:

### Evaluators

1. **ReportContentMatch** - ExactMatch evaluator that compares full attachment content
2. **ReportContainsKeyword** - Contains evaluator that checks for specific keywords
3. **LineByLineContains** - LineByLine Contains evaluator for multiline validation

### Test Cases

| Test Case | Input | Evaluators | Expected Result |
|-----------|-------|------------|-----------------|
| Test sales report exact match | "Generate sales report" | ReportContentMatch, ReportContainsKeyword | Both pass (1.0) |
| Test inventory report contains keywords | "Generate inventory report" | ReportContainsKeyword | Pass (1.0) |
| Test employee report line-by-line | "Generate employee report" | LineByLineContains | Pass (1.0) |
| Test generic report exact match | "Complete project review" | ReportContentMatch, ReportContainsKeyword | Both pass (1.0) |
| Test partial match with contains | "Generate sales report" | ReportContainsKeyword | Pass (1.0) |

Expected output:
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
┃  Evaluation                        ┃  ReportContentMatch  ┃  ReportContainsKeyword  ┃  LineByLineContains  ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
│  Test sales report exact match     │                 1.0  │                     1.0  │                  -   │
│  Test inventory report contains    │                  -   │                     1.0  │                  -   │
│  Test employee report line-by-line │                  -   │                      -   │                1.0   │
│  Test generic report exact match   │                 1.0  │                     1.0  │                  -   │
│  Test partial match with contains  │                  -   │                     1.0  │                  -   │
├────────────────────────────────────┼──────────────────────┼──────────────────────────┼──────────────────────┤
│  Average                           │                 1.0  │                     1.0  │                1.0   │
└────────────────────────────────────┴──────────────────────┴──────────────────────────┴──────────────────────┘
```

## How It Works

### 1. Agent Creates Attachment

```python
from uipath.platform import UiPath

# Generate content
content = "Sales Report Q4 2024\n\nTotal Revenue: $1,250,000\n..."

# Upload as attachment
client = UiPath()
attachment_id = client.attachments.upload(
    name="report_sales.txt",
    content=content,
)

# Return URI
return {
    "report": f"urn:uipath:cas:file:orchestrator:{attachment_id}"
}
```

### 2. Evaluator Configuration

```json
{
  "version": "1.0",
  "evaluatorTypeId": "uipath-exact-match",
  "evaluatorConfig": {
    "name": "ReportContentMatch",
    "targetOutputKey": "report",
    "caseSensitive": false
  }
}
```

The `targetOutputKey` points to the field containing the attachment URI.

### 3. Automatic Download and Evaluation

When the evaluator runs:
1. Extracts value from `agent_output["report"]`
2. Detects it's an attachment URI (matches pattern)
3. Downloads the attachment content automatically
4. Evaluates the downloaded content against expected criteria

## File Structure

```
attachment_evaluation_test/
├── main.py                                # Agent that creates attachments
├── uipath.json                            # Agent configuration
├── pyproject.toml                         # Dependencies
├── README.md                              # Full documentation
├── QUICKSTART.md                          # Quick start guide
└── evaluations/
    ├── evaluators/
    │   ├── exact-match.json               # ExactMatch evaluator config
    │   ├── contains-keyword.json          # Contains evaluator config
    │   └── line-by-line-contains.json     # LineByLine evaluator config
    └── eval-sets/
        └── default.json                   # Test cases with evaluation criteria
```

## Key Concepts

### Attachment URI Pattern

```
urn:uipath:cas:file:orchestrator:{attachment-uuid}
```

Example:
```
urn:uipath:cas:file:orchestrator:123e4567-e89b-12d3-a456-426614174000
```

### Target Output Key

The `targetOutputKey` in evaluator configuration specifies which field contains the attachment URI:

```json
{
  "targetOutputKey": "report"  // Looks for agent_output["report"]
}
```

For nested paths, use dot notation:
```json
{
  "targetOutputKey": "results.report"  // agent_output["results"]["report"]
}
```

### Supported Evaluators

All output evaluators support attachment evaluation:
- **ExactMatch** - Full content match
- **Contains** - Keyword/substring search
- **JsonSimilarity** - JSON structure comparison (if attachment contains JSON)
- **LLM-based evaluators** - Can analyze attachment content

## Troubleshooting

### Authentication Errors

```bash
# Verify credentials are set
echo $UIPATH_URL
echo $UIPATH_ACCESS_TOKEN

# Or authenticate interactively
uipath auth
```

### Attachment Not Found

If you see "Attachment with key X not found":
- Ensure you're connected to the correct tenant
- Check that the folder context matches where the attachment was created
- Verify the attachment UUID is correct

### Download Failures

If attachment download fails:
- Check network connectivity to your UiPath tenant
- Verify your access token has permissions to read attachments
- Check if the attachment still exists (not deleted)

## Learn More

- [UiPath Python SDK Documentation](https://docs.uipath.com/)
- [Evaluation Framework Guide](../../src/uipath/_resources/eval.md)
- [Job Attachments API](https://docs.uipath.com/orchestrator/reference/api-attachments)
- [Line-by-Line Evaluation Sample](../line_by_line_test/)

## Advanced Usage

### Custom Report Types

Modify `main.py` to add more report types:

```python
elif "financial" in task.lower():
    content = """Financial Report

    Revenue: $X
    Expenses: $Y
    Profit: $Z
    """
```

### Binary Attachments

For binary files (images, PDFs), upload as bytes:

```python
attachment_id = client.attachments.upload(
    name="document.pdf",
    source_path="/path/to/file.pdf",  # Or use content=<bytes>
)
```

### Multiple Attachments

Return multiple attachment URIs:

```python
return {
    "primary_report": f"urn:uipath:cas:file:orchestrator:{id1}",
    "detailed_report": f"urn:uipath:cas:file:orchestrator:{id2}",
}
```

Then configure evaluators for each:
```json
{
  "targetOutputKey": "primary_report"  // Evaluates first attachment
}
```
