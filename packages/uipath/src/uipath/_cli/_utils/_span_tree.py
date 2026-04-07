"""Reusable span-tree building, filtering, and Rich rendering utilities.

This module provides the core primitives for visualising OpenTelemetry span
trees.  It is consumed by ``cli_trace.py`` (post-hoc file visualisation) and
can be imported by any other module that needs to render span trees — for
example a live trajectory reporter during ``uipath eval``.
"""

import json
from datetime import datetime
from fnmatch import fnmatch
from typing import Any

# ---------------------------------------------------------------------------
# Tree data structure
# ---------------------------------------------------------------------------


class SpanNode:
    """A node in the span tree."""

    def __init__(self, span: dict[str, Any]):
        self.span = span
        self.children: list["SpanNode"] = []

    @property
    def name(self) -> str:
        return self.span.get("name", "<unknown>")

    @property
    def status_code(self) -> str:
        status = self.span.get("status", {})
        if isinstance(status, dict):
            return (status.get("status_code") or "UNSET").upper()
        return "UNSET"

    @property
    def status_icon(self) -> str:
        code = self.status_code
        if code == "OK":
            return "[green]✓[/green]"
        elif code == "ERROR":
            return "[red]✗[/red]"
        return "[dim]○[/dim]"

    @property
    def attributes(self) -> dict[str, Any]:
        return self.span.get("attributes", {})

    @property
    def span_type(self) -> str | None:
        return self.attributes.get("span_type")

    @property
    def duration_ms(self) -> float | None:
        """Compute duration in milliseconds from OTel timestamps."""
        start = self.span.get("start_time")
        end = self.span.get("end_time")
        if start is None or end is None:
            return None
        try:
            t0 = parse_otel_time(start)
            t1 = parse_otel_time(end)
            return (t1 - t0).total_seconds() * 1000
        except Exception:
            return None

    @property
    def duration_str(self) -> str:
        ms = self.duration_ms
        if ms is None:
            return ""
        if ms < 1000:
            return f"{ms:.0f}ms"
        return f"{ms / 1000:.1f}s"

    @property
    def events(self) -> list[dict[str, Any]]:
        return self.span.get("events", []) or []


# ---------------------------------------------------------------------------
# Timestamp parsing
# ---------------------------------------------------------------------------


def parse_otel_time(value: Any) -> datetime:
    """Parse an OTel timestamp string to datetime."""
    if isinstance(value, (int, float)):
        # Nanoseconds since epoch
        return datetime.fromtimestamp(value / 1e9)
    s = str(value)
    # OTel format: "2024-01-15T10:30:00.000000Z"
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse timestamp: {value}")


# ---------------------------------------------------------------------------
# Tree building
# ---------------------------------------------------------------------------


def build_tree_from_jsonl(spans: list[dict[str, Any]]) -> list[SpanNode]:
    """Build a span tree using ``context.span_id`` / ``parent_id``."""
    nodes_by_id: dict[str, SpanNode] = {}
    roots: list[SpanNode] = []

    # First pass: create nodes
    for sp in spans:
        ctx = sp.get("context", {})
        span_id = ctx.get("span_id")
        if span_id is None:
            # Eval-normalised span without IDs — handled separately
            continue
        nodes_by_id[span_id] = SpanNode(sp)

    # Second pass: link parents
    for sp in spans:
        ctx = sp.get("context", {})
        span_id = ctx.get("span_id")
        parent_id = sp.get("parent_id")
        if span_id is None:
            continue
        node = nodes_by_id[span_id]
        if parent_id and parent_id in nodes_by_id:
            nodes_by_id[parent_id].children.append(node)
        else:
            roots.append(node)

    return roots


def build_tree_from_eval(spans: list[dict[str, Any]]) -> list[SpanNode]:
    """Build a span tree using ``parent_name`` (eval verbose format).

    Since multiple spans may share a name, we use position-based matching:
    the first child referencing a parent_name attaches to the first span
    with that name that hasn't been used yet as a parent for that same
    child name.
    """
    nodes = [SpanNode(sp) for sp in spans]
    name_to_nodes: dict[str, list[SpanNode]] = {}
    for node in nodes:
        name_to_nodes.setdefault(node.name, []).append(node)

    roots: list[SpanNode] = []
    for node in nodes:
        parent_name = node.span.get("parent_name")
        if parent_name and parent_name in name_to_nodes:
            # Attach to first matching parent
            parent_candidates = name_to_nodes[parent_name]
            if parent_candidates:
                parent_candidates[0].children.append(node)
            else:
                roots.append(node)
        else:
            roots.append(node)

    return roots


def build_tree(spans: list[dict[str, Any]], is_eval: bool) -> list[SpanNode]:
    """Build a span tree from loaded spans."""
    if is_eval:
        return build_tree_from_eval(spans)
    return build_tree_from_jsonl(spans)


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def _matches_filter(
    node: SpanNode,
    *,
    name_pattern: str | None,
    span_type_filter: str | None,
    status_filter: str | None,
) -> bool:
    """Check if a span matches the filter criteria."""
    if name_pattern:
        if not fnmatch(node.name.lower(), name_pattern.lower()):
            return False

    if span_type_filter:
        st = node.span_type
        if st is None or st.lower() != span_type_filter.lower():
            return False

    if status_filter:
        if node.status_code.lower() != status_filter.lower():
            return False

    return True


def filter_tree(
    roots: list[SpanNode],
    *,
    name_pattern: str | None = None,
    span_type_filter: str | None = None,
    status_filter: str | None = None,
) -> list[SpanNode]:
    """Filter the span tree, keeping ancestors of matching nodes."""
    if not name_pattern and not span_type_filter and not status_filter:
        return roots

    def _keep(node: SpanNode) -> SpanNode | None:
        # Recurse into children first
        kept_children = []
        for child in node.children:
            result = _keep(child)
            if result is not None:
                kept_children.append(result)

        self_matches = _matches_filter(
            node,
            name_pattern=name_pattern,
            span_type_filter=span_type_filter,
            status_filter=status_filter,
        )

        if self_matches or kept_children:
            new_node = SpanNode(node.span)
            new_node.children = kept_children
            return new_node

        return None

    filtered = []
    for root in roots:
        result = _keep(root)
        if result is not None:
            filtered.append(result)
    return filtered


def _subtree_contains(node: SpanNode, pattern: str) -> bool:
    """Check if any node in the subtree matches the name pattern."""
    if fnmatch(node.name.lower(), pattern.lower()):
        return True
    return any(_subtree_contains(child, pattern) for child in node.children)


def filter_contains(
    roots: list[SpanNode],
    pattern: str,
) -> list[SpanNode]:
    """Keep full subtrees where any descendant matches the pattern.

    Walks from the top and finds the shallowest nodes whose subtree
    contains a match *and* that are not just the matching leaf itself.
    This way you see the full agent trajectory around the matching span,
    not just the span alone.

    For eval traces this typically returns the per-evaluation subtrees
    (Evaluation → root → main → …) rather than the top-level
    Evaluation Set Run.
    """
    kept: list[SpanNode] = []

    def _collect(node: SpanNode) -> None:
        if not _subtree_contains(node, pattern):
            return

        # Count how many direct children also contain the match
        children_with_match = [
            c for c in node.children if _subtree_contains(c, pattern)
        ]

        if len(children_with_match) > 1:
            # Multiple children match — drill into each separately
            # (e.g. Evaluation Set Run with several matching Evaluations)
            for child in children_with_match:
                _collect(child)
        elif len(children_with_match) == 1:
            child = children_with_match[0]
            # If the only matching child is a leaf that matches the
            # pattern itself, keep *this* node so we show context.
            # Otherwise drill deeper.
            child_is_leaf_match = (
                not child.children
                or not any(_subtree_contains(gc, pattern) for gc in child.children)
            ) and fnmatch(child.name.lower(), pattern.lower())

            if child_is_leaf_match:
                kept.append(node)
            else:
                _collect(child)
        else:
            # This node itself matches (no child does) — keep its parent
            # would have been better, but we're already here, so keep it.
            kept.append(node)

    for root in roots:
        _collect(root)

    return kept


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def safe_parse_json(value: Any) -> Any:
    """Try to parse a JSON string; return as-is if it fails."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            pass
    return value


def truncate(value: str, max_len: int = 200) -> str:
    """Truncate a string to *max_len* characters, appending ``...``."""
    if max_len <= 0:
        return value
    if len(value) <= max_len:
        return value
    return value[:max_len] + "..."


def span_label(node: SpanNode) -> str:
    """Build a human-friendly label for a span."""
    attrs = node.attributes
    span_kind = (attrs.get("openinference.span.kind") or "").upper()

    # LLM span
    if span_kind == "LLM" or attrs.get("llm.model_name"):
        model = attrs.get("llm.model_name", "")
        if model:
            return f"LLM ({model})"
        return "LLM call"

    # Tool span
    if span_kind == "TOOL" or (node.span_type or "").upper() == "TOOL":
        tool_name = attrs.get("tool.name", node.name)
        return f"🔧 {tool_name}"

    return node.name


# ---------------------------------------------------------------------------
# Rich rendering
# ---------------------------------------------------------------------------


def render_span_node(
    parent_tree: Any,
    node: SpanNode,
    *,
    show_input: bool = True,
    show_output: bool = True,
    show_full: bool = False,
    max_value_length: int = 200,
) -> None:
    """Render a single span node and its children into a Rich Tree."""
    attrs = node.attributes

    # Build the header line
    duration = node.duration_str
    st = node.span_type or ""
    status = node.status_icon

    # Determine display label based on span type
    label = span_label(node)

    parts = [f"[bold]{label}[/bold]"]
    if duration:
        parts.append(f"[dim]({duration})[/dim]")
    parts.append(status)
    if st and show_full:
        parts.append(f"[dim]\\[{st}][/dim]")

    header = " ".join(parts)
    branch = parent_tree.add(header)

    # Show key attributes
    if show_full:
        _render_all_attributes(branch, attrs, max_value_length=max_value_length)
    else:
        _render_key_attributes(
            branch,
            attrs,
            node,
            show_input=show_input,
            show_output=show_output,
            max_value_length=max_value_length,
        )

    # Show error events
    for event in node.events:
        event_name = event.get("name", "")
        if event_name == "exception":
            event_attrs = event.get("attributes", {})
            exc_type = event_attrs.get("exception.type", "")
            exc_msg = event_attrs.get("exception.message", "")
            branch.add(
                f"[red]⚠ {exc_type}: {truncate(str(exc_msg), max_value_length)}[/red]"
            )

    # Recurse into children
    for child in node.children:
        render_span_node(
            branch,
            child,
            show_input=show_input,
            show_output=show_output,
            show_full=show_full,
            max_value_length=max_value_length,
        )


def _render_key_attributes(
    branch: Any,
    attrs: dict[str, Any],
    node: SpanNode,
    *,
    show_input: bool,
    show_output: bool,
    max_value_length: int = 200,
) -> None:
    """Show only the most interesting attributes."""
    # Input
    if show_input:
        input_val = attrs.get("input.value")
        if input_val:
            parsed = safe_parse_json(input_val)
            display = truncate(
                json.dumps(parsed, default=str)
                if isinstance(parsed, (dict, list))
                else str(parsed),
                max_value_length,
            )
            branch.add(f"[cyan]input:[/cyan] {display}")

    # Output
    if show_output:
        output_val = attrs.get("output.value")
        if output_val:
            parsed = safe_parse_json(output_val)
            display = truncate(
                json.dumps(parsed, default=str)
                if isinstance(parsed, (dict, list))
                else str(parsed),
                max_value_length,
            )
            branch.add(f"[green]output:[/green] {display}")

    # LLM tokens
    prompt_tokens = attrs.get("llm.token_count.prompt")
    completion_tokens = attrs.get("llm.token_count.completion")
    if prompt_tokens is not None or completion_tokens is not None:
        parts = []
        if prompt_tokens is not None:
            parts.append(f"prompt={prompt_tokens}")
        if completion_tokens is not None:
            parts.append(f"completion={completion_tokens}")
        total = attrs.get("llm.token_count.total")
        if total is not None:
            parts.append(f"total={total}")
        branch.add(f"[yellow]tokens:[/yellow] {', '.join(parts)}")

    # Run type
    run_type = attrs.get("run_type")
    if run_type:
        branch.add(f"[dim]run_type: {run_type}[/dim]")


def _render_all_attributes(
    branch: Any, attrs: dict[str, Any], *, max_value_length: int = 200
) -> None:
    """Show all span attributes."""
    if not attrs:
        return
    attr_branch = branch.add("[dim]attributes[/dim]")
    for key, value in sorted(attrs.items()):
        display_value = safe_parse_json(value) if isinstance(value, str) else value
        if isinstance(display_value, (dict, list)):
            display_str = truncate(
                json.dumps(display_value, default=str), max_value_length
            )
        else:
            display_str = truncate(str(display_value), max_value_length)
        attr_branch.add(f"[yellow]{key}[/yellow]: {display_str}")


def render_tree(
    roots: list[SpanNode],
    *,
    show_input: bool = True,
    show_output: bool = True,
    show_full: bool = False,
    max_value_length: int = 200,
) -> None:
    """Render the full span tree to the console."""
    from rich.console import Console
    from rich.tree import Tree

    rich_console = Console(force_terminal=True)

    if not roots:
        rich_console.print("[yellow]No spans to display.[/yellow]")
        return

    # Group by trace_id if available
    trace_groups: dict[str, list[SpanNode]] = {}
    ungrouped: list[SpanNode] = []
    for root in roots:
        trace_id = root.span.get("context", {}).get("trace_id")
        if trace_id:
            trace_groups.setdefault(trace_id, []).append(root)
        else:
            ungrouped.append(root)

    def _print_roots(console: Console, label: str, tree_roots: list[SpanNode]) -> None:
        tree = Tree(label)
        for root in tree_roots:
            render_span_node(
                tree,
                root,
                show_input=show_input,
                show_output=show_output,
                show_full=show_full,
                max_value_length=max_value_length,
            )
        console.print(tree)
        console.print()

    for trace_id, group_roots in trace_groups.items():
        # Shorten trace_id for display
        display_id = str(trace_id).replace("0x", "")
        if len(display_id) > 16:
            display_id = display_id[:8] + "…" + display_id[-8:]
        _print_roots(
            rich_console,
            f"[bold magenta]Trace[/bold magenta] [dim]{display_id}[/dim]",
            group_roots,
        )

    if ungrouped:
        _print_roots(
            rich_console,
            "[bold magenta]Trace[/bold magenta]",
            ungrouped,
        )

    # Summary
    total_spans = count_spans(roots)
    rich_console.print(f"[dim]{total_spans} spans total[/dim]")


def count_spans(roots: list[SpanNode]) -> int:
    """Count total number of spans across all trees."""
    count = 0
    for root in roots:
        count += 1
        count += count_spans(root.children)
    return count
