"""Pure-Python replacement for scipy.optimize.linear_sum_assignment.

Mirrors scipy's rectangular LSAP solver (_lsap.c, shortest augmenting path /
Jonker-Volgenant) step for step — including the tie-breaking rule that prefers
an unassigned sink among equal-cost columns and the reverse-order `remaining`
scan — so optimal-assignment composition matches scipy on the tie cases that
affect FP/FN attribution (parity checklist §4.9). The function decomposition
follows _lsap.c's own augmenting_path/solve split.
"""

from collections.abc import Sequence

_INF = float("inf")


def _prepare_matrix(
    cost: Sequence[Sequence[float]], maximize: bool
) -> tuple[list[list[float]], bool]:
    """Copy to floats, transposing when rows outnumber columns (as scipy
    does) and negating for maximize mode."""
    num_rows = len(cost)
    num_cols = len(cost[0]) if num_rows else 0
    transposed = num_rows > num_cols
    if transposed:
        matrix = [[float(cost[i][j]) for i in range(num_rows)] for j in range(num_cols)]
    else:
        matrix = [[float(value) for value in row] for row in cost]
    if maximize:
        matrix = [[-value for value in row] for row in matrix]
    return matrix, transposed


def _scan_columns(
    row_cost: list[float],
    potential: float,
    v: list[float],
    min_val: float,
    remaining: list[int],
    num_remaining: int,
    shortest_path_costs: list[float],
    path: list[int],
    row4col: list[int],
    i: int,
) -> tuple[float, int]:
    """One Dijkstra relaxation sweep over the not-yet-visited columns.

    Returns the lowest tentative cost and the `remaining` index holding it —
    among equal-cost columns preferring one that is a new sink, exactly as
    scipy's _lsap.c does.
    """
    lowest = _INF
    index = -1
    for it in range(num_remaining):
        j = remaining[it]
        r = min_val + row_cost[j] - potential - v[j]
        if r < shortest_path_costs[j]:
            path[j] = i
            shortest_path_costs[j] = r
        if shortest_path_costs[j] < lowest or (
            shortest_path_costs[j] == lowest and row4col[j] == -1
        ):
            lowest = shortest_path_costs[j]
            index = it
    return lowest, index


def _augmenting_path(
    matrix: list[list[float]],
    u: list[float],
    v: list[float],
    row4col: list[int],
    cur_row: int,
    sr: list[bool],
    sc: list[bool],
    shortest_path_costs: list[float],
    path: list[int],
) -> tuple[int, float]:
    """Find the shortest augmenting path from cur_row (scipy's
    augmenting_path); returns the sink column and its path cost."""
    num_cols = len(matrix[0])
    min_val = 0.0
    remaining = [num_cols - it - 1 for it in range(num_cols)]
    num_remaining = num_cols

    i = cur_row
    sink = -1
    while sink == -1:
        sr[i] = True
        min_val, index = _scan_columns(
            matrix[i],
            u[i],
            v,
            min_val,
            remaining,
            num_remaining,
            shortest_path_costs,
            path,
            row4col,
            i,
        )
        if min_val == _INF:  # infeasible
            raise ValueError("cost matrix is infeasible")
        j = remaining[index]
        if row4col[j] == -1:
            sink = j
        else:
            i = row4col[j]
        sc[j] = True
        num_remaining -= 1
        remaining[index] = remaining[num_remaining]
    return sink, min_val


def _update_dual_variables(
    u: list[float],
    v: list[float],
    cur_row: int,
    min_val: float,
    sr: list[bool],
    sc: list[bool],
    shortest_path_costs: list[float],
    col4row: list[int],
) -> None:
    u[cur_row] += min_val
    for ir in range(len(u)):
        if sr[ir] and ir != cur_row:
            u[ir] += min_val - shortest_path_costs[col4row[ir]]
    for jc in range(len(v)):
        if sc[jc]:
            v[jc] -= min_val - shortest_path_costs[jc]


def _augment(
    path: list[int],
    row4col: list[int],
    col4row: list[int],
    sink: int,
    cur_row: int,
) -> None:
    """Flip the alternating path from the sink back to cur_row."""
    j = sink
    while True:
        i = path[j]
        row4col[j] = i
        col4row[i], j = j, col4row[i]
        if i == cur_row:
            break


def linear_sum_assignment(
    cost: Sequence[Sequence[float]], maximize: bool = False
) -> tuple[list[int], list[int]]:
    matrix, transposed = _prepare_matrix(cost, maximize)
    num_rows = len(matrix)
    num_cols = len(matrix[0]) if num_rows else 0
    if num_rows == 0 or num_cols == 0:
        return [], []

    u = [0.0] * num_rows
    v = [0.0] * num_cols
    col4row = [-1] * num_rows
    row4col = [-1] * num_cols

    for cur_row in range(num_rows):
        sr = [False] * num_rows
        sc = [False] * num_cols
        shortest_path_costs = [_INF] * num_cols
        path = [-1] * num_cols

        sink, min_val = _augmenting_path(
            matrix, u, v, row4col, cur_row, sr, sc, shortest_path_costs, path
        )
        _update_dual_variables(
            u, v, cur_row, min_val, sr, sc, shortest_path_costs, col4row
        )
        _augment(path, row4col, col4row, sink, cur_row)

    if transposed:
        pairs = sorted((col4row[i], i) for i in range(num_rows))
        return [pair[0] for pair in pairs], [pair[1] for pair in pairs]
    return list(range(num_rows)), col4row
