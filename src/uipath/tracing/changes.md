# Filter Parent Span Changes

## Problem

When `UIPATH_FILTER_PARENT_SPAN` is set along with `UIPATH_PARENT_SPAN_ID`, we want to:
1. **Filter out** the root span (e.g., LangGraph) from being exported
2. **Reparent** its children to `UIPATH_PARENT_SPAN_ID` so they appear under the correct parent in the trace UI

## Changes Made

### _utils.py (lines 213-232)

- Added `is_root = otel_span.parent is None` check
- For root spans: set `ParentId` to `UIPATH_PARENT_SPAN_ID`
- Added `uipath.root_span = True` marker in attributes to identify root spans later

### _otel_exporters.py (lines 116-393)

- Added `_parent_id_mapping: dict[str, str]` to track filtered span IDs across batches
- In `export()`: call `_filter_root_and_reparent()` when both env vars are set
- `_filter_root_and_reparent()` does:
  - **Pass 1**: Find spans with `uipath.root_span=True`, add their ID to mapping
  - **Pass 2**: Filter out root spans, reparent children whose parent is in mapping
  - **Orphan handling**: If a span's parent is not in the batch and not the new parent, reparent it (handles case where root came in earlier batch)

## Environment Variables

- `UIPATH_PARENT_SPAN_ID`: The parent span ID to use for root spans
- `UIPATH_FILTER_PARENT_SPAN`: When set (any truthy value), enables filtering of root spans

## Behavior

| Env Vars Set | Behavior |
|--------------|----------|
| `UIPATH_PARENT_SPAN_ID` only | Root spans get this as their parent ID |
| Both `UIPATH_FILTER_PARENT_SPAN` + `UIPATH_PARENT_SPAN_ID` | Root spans are filtered out, their children are reparented to `UIPATH_PARENT_SPAN_ID` |
