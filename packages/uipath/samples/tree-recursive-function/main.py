"""Sample with recursive calls for testing call graph visualization."""

import logging
from pydantic.dataclasses import dataclass
from uipath.tracing import traced

logger = logging.getLogger(__name__)


@dataclass
class TreeNode:
    value: int
    left: "TreeNode | None" = None
    right: "TreeNode | None" = None


@dataclass
class TreeStats:
    depth: int
    total_nodes: int
    leaf_count: int
    max_value: int
    path_to_max: list[str]

@traced
def log_visit(node_value: int, depth: int) -> None:
    logger.info("Visiting node %d at depth %d", node_value, depth)

@traced
def is_leaf(node: TreeNode) -> bool:
    return node.left is None and node.right is None

@traced
def compute_depth(node: TreeNode | None) -> int:
    """Classic recursive depth computation."""
    if node is None:
        return 0
    left_depth = compute_depth(node.left)
    right_depth = compute_depth(node.right)
    return 1 + max(left_depth, right_depth)

@traced
def count_nodes(node: TreeNode | None) -> int:
    """Recursive node count."""
    if node is None:
        return 0
    return 1 + count_nodes(node.left) + count_nodes(node.right)

@traced
def count_leaves(node: TreeNode | None) -> int:
    """Recursive leaf count — calls is_leaf."""
    if node is None:
        return 0
    if is_leaf(node):
        return 1
    return count_leaves(node.left) + count_leaves(node.right)

@traced
def find_max(node: TreeNode | None) -> int:
    """Recursive max-value search."""
    if node is None:
        return float("-inf")
    left_max = find_max(node.left)
    right_max = find_max(node.right)
    return max(node.value, left_max, right_max)

@traced
def find_path_to_value(node: TreeNode | None, target: int) -> list[str]:
    """Recursive path finding — uses is_leaf as a helper."""
    if node is None:
        return []
    if node.value == target:
        return [str(node.value)]
    left_path = find_path_to_value(node.left, target)
    if left_path:
        return [str(node.value)] + left_path
    right_path = find_path_to_value(node.right, target)
    if right_path:
        return [str(node.value)] + right_path
    return []

@traced
def analyze_tree(tree: TreeNode) -> TreeStats:
    """Entrypoint that fans out into multiple recursive helpers."""
    log_visit(tree.value, 0)

    depth = compute_depth(tree)
    total = count_nodes(tree)
    leaves = count_leaves(tree)
    max_val = find_max(tree)
    path = find_path_to_value(tree, max_val)

    return TreeStats(
        depth=depth,
        total_nodes=total,
        leaf_count=leaves,
        max_value=max_val,
        path_to_max=path,
    )

@traced
async def main(input: TreeNode) -> TreeStats:
    return analyze_tree(input)
