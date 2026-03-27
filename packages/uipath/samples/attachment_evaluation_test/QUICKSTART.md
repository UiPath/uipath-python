# Quick Start Guide

Get up and running with the attachment evaluation sample in 5 minutes!

## Step 1: Install Dependencies

```bash
cd samples/attachment_evaluation_test
uv sync
```

## Step 2: Set Up UiPath Credentials

Choose one of these methods:

### Option A: Environment Variables

```bash
export UIPATH_URL="https://your-tenant.uipath.com"
export UIPATH_ACCESS_TOKEN="your-access-token"
```

### Option B: Interactive Auth

```bash
uv run uipath auth
```

Follow the prompts to authenticate.

## Step 3: Run the Agent

```bash
# Generate a sales report
uv run uipath run main '{"task": "Generate sales report"}'
```

**Expected output:**
```json
{
  "report": "urn:uipath:cas:file:orchestrator:abc12345-...",
  "task": "Generate sales report",
  "status": "completed"
}
```

The `report` field contains the attachment URI!

## Step 4: Run Evaluations

```bash
uv run uipath eval main evaluations/eval-sets/default.json --workers 1
```

**Expected output:**
```
Running evaluations...
✓ Test sales report exact match - PASSED (2/2 evaluators)
✓ Test inventory report contains - PASSED (1/1 evaluator)
✓ Test employee report line-by-line - PASSED (1/1 evaluator)
✓ Test generic report exact match - PASSED (2/2 evaluators)
✓ Test partial match with contains - PASSED (1/1 evaluator)

Summary: 5/5 tests passed
```

## What's Happening?

1. **Agent runs** and generates report content
2. **Content is uploaded** as a job attachment to UiPath
3. **Attachment URI** is returned in agent output
4. **Evaluators detect** the URI automatically
5. **Attachment is downloaded** and content is evaluated
6. **Results are displayed** showing pass/fail

## Try Different Reports

```bash
# Inventory report
uv run uipath run main '{"task": "Generate inventory report"}'

# Employee report
uv run uipath run main '{"task": "Generate employee report"}'

# Generic report
uv run uipath run main '{"task": "Complete project review"}'
```

## View Attachment Content

After running the agent, you can manually download the attachment to see its content:

```bash
# Extract the UUID from the output
# urn:uipath:cas:file:orchestrator:YOUR-UUID-HERE

# Or check in UiPath Orchestrator UI:
# Orchestrator > Jobs > Job Details > Attachments
```

## Customize

### Add New Report Types

Edit `main.py` and add a new condition:

```python
elif "financial" in task.lower():
    content = """Your report content here"""
```

### Add New Evaluators

Create a new evaluator config in `evaluations/evaluators/`:

```json
{
  "version": "1.0",
  "evaluatorTypeId": "uipath-json-similarity",
  "evaluatorConfig": {
    "name": "MyEvaluator",
    "targetOutputKey": "report"
  }
}
```

### Add New Test Cases

Edit `evaluations/eval-sets/default.json` and add:

```json
{
  "name": "My test case",
  "input": {"task": "..."},
  "evaluationCriteria": {
    "MyEvaluator": {...}
  }
}
```

## Troubleshooting

### "Attachment not found"
- Check your credentials point to the correct tenant
- Verify the attachment wasn't deleted

### "Permission denied"
- Ensure your access token has attachment read/write permissions

### "Module not found"
- Run `uv sync` to install dependencies

## Next Steps

- Read the full [README.md](./README.md) for detailed documentation
- Check [../../src/uipath/_resources/eval.md](../../src/uipath/_resources/eval.md) for evaluation framework details
- See [../line_by_line_test/](../line_by_line_test/) for line-by-line evaluation examples

## Need Help?

- [UiPath Python SDK Documentation](https://docs.uipath.com/)
- [GitHub Issues](https://github.com/UiPath/uipath-python-sdk/issues)
