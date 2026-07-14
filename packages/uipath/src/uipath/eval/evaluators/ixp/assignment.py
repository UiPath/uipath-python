"""Pure-Python replacement for scipy.optimize.linear_sum_assignment.

Mirrors scipy's rectangular LSAP solver (_lsap.c, shortest augmenting path /
Jonker-Volgenant) step for step — including the tie-breaking rule that prefers
an unassigned sink among equal-cost columns and the reverse-order `remaining`
scan — so optimal-assignment composition matches scipy on the tie cases that
affect FP/FN attribution (parity checklist §4.9).
"""

from collections.abc import Sequence

_INF = float("inf")


def linear_sum_assignment(
    cost: Sequence[Sequence[float]], maximize: bool = False
) -> tuple[list[int], list[int]]:
    nr = len(cost)
    nc = len(cost[0]) if nr else 0

    transposed = nr > nc
    if transposed:
        matrix = [[float(cost[i][j]) for i in range(nr)] for j in range(nc)]
        nr, nc = nc, nr
    else:
        matrix = [[float(v) for v in row] for row in cost]

    if maximize:
        matrix = [[-v for v in row] for row in matrix]

    if nr == 0 or nc == 0:
        return [], []

    u = [0.0] * nr
    v = [0.0] * nc
    col4row = [-1] * nr
    row4col = [-1] * nc

    for cur_row in range(nr):
        # --- augmenting_path (Dijkstra from cur_row), as in scipy _lsap.c ---
        min_val = 0.0
        remaining = [nc - it - 1 for it in range(nc)]
        num_remaining = nc
        sr = [False] * nr
        sc = [False] * nc
        shortest_path_costs = [_INF] * nc
        path = [-1] * nc

        i = cur_row
        sink = -1
        while sink == -1:
            index = -1
            lowest = _INF
            sr[i] = True
            row_cost = matrix[i]
            ui = u[i]
            for it in range(num_remaining):
                j = remaining[it]
                r = min_val + row_cost[j] - ui - v[j]
                if r < shortest_path_costs[j]:
                    path[j] = i
                    shortest_path_costs[j] = r
                # among equal-cost columns prefer one that is a new sink
                if shortest_path_costs[j] < lowest or (
                    shortest_path_costs[j] == lowest and row4col[j] == -1
                ):
                    lowest = shortest_path_costs[j]
                    index = it
            min_val = lowest
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

        # --- update dual variables ---
        u[cur_row] += min_val
        for ir in range(nr):
            if sr[ir] and ir != cur_row:
                u[ir] += min_val - shortest_path_costs[col4row[ir]]
        for jc in range(nc):
            if sc[jc]:
                v[jc] -= min_val - shortest_path_costs[jc]

        # --- augment along the alternating path back to cur_row ---
        j = sink
        while True:
            i = path[j]
            row4col[j] = i
            col4row[i], j = j, col4row[i]
            if i == cur_row:
                break

    if transposed:
        pairs = sorted((col4row[i], i) for i in range(nr))
        return [p[0] for p in pairs], [p[1] for p in pairs]
    return list(range(nr)), col4row
