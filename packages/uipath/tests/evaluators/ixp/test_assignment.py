"""Tests for the pure-Python linear_sum_assignment (scipy replacement).

Everything except the final differential test is scipy-independent and runs
in CI: optimality is checked against brute force over all permutations, plus
hand-computed cases, adversarial greedy traps, closed-form structured
matrices, structural properties, determinism, and the failure contract.
The differential test additionally pins exact index-level parity with scipy
when it is installed.
"""

from __future__ import annotations

import itertools
import random

import pytest

from uipath.eval.evaluators.ixp.assignment import linear_sum_assignment


def brute_force_best_total(matrix: list[list[float]], maximize: bool) -> float:
    """Optimal assignment total by trying every permutation."""
    num_rows = len(matrix)
    num_cols = len(matrix[0])
    if num_rows <= num_cols:
        totals = (
            sum(matrix[row][col] for row, col in enumerate(cols))
            for cols in itertools.permutations(range(num_cols), num_rows)
        )
    else:
        totals = (
            sum(matrix[row][col] for col, row in enumerate(rows))
            for rows in itertools.permutations(range(num_rows), num_cols)
        )
    return max(totals) if maximize else min(totals)


def assignment_total(
    matrix: list[list[float]], rows: list[int], cols: list[int]
) -> float:
    return sum(matrix[row][col] for row, col in zip(rows, cols, strict=True))


def test_known_square_cases() -> None:
    # classic minimize example: pick 1 and 2 off the diagonal
    rows, cols = linear_sum_assignment([[4.0, 1.0], [2.0, 8.0]])
    assert (rows, cols) == ([0, 1], [1, 0])
    # maximize picks 4 and 8
    rows, cols = linear_sum_assignment([[4.0, 1.0], [2.0, 8.0]], maximize=True)
    assert (rows, cols) == ([0, 1], [0, 1])
    # 1x1
    assert linear_sum_assignment([[7.0]]) == ([0], [0])


def test_rectangular_wide_and_tall() -> None:
    # wide: 2 rows, 3 cols — every row assigned, one col unused
    matrix = [[1.0, 9.0, 2.0], [9.0, 1.0, 2.0]]
    rows, cols = linear_sum_assignment(matrix, maximize=True)
    assert rows == [0, 1]
    assert sorted(cols) == [0, 1]
    assert assignment_total(matrix, rows, cols) == 18.0
    # tall: 3 rows, 1 col — exercises the transpose branch
    rows, cols = linear_sum_assignment([[1.0], [2.0], [3.0]], maximize=True)
    assert (rows, cols) == ([2], [0])
    rows, cols = linear_sum_assignment([[1.0], [2.0], [3.0]])
    assert (rows, cols) == ([0], [0])


def test_output_is_valid_partial_permutation() -> None:
    rng = random.Random(1)
    for _ in range(200):
        num_rows = rng.randint(1, 6)
        num_cols = rng.randint(1, 6)
        matrix = [
            [rng.uniform(-5, 5) for _ in range(num_cols)] for _ in range(num_rows)
        ]
        rows, cols = linear_sum_assignment(matrix, maximize=rng.random() < 0.5)
        expected_size = min(num_rows, num_cols)
        assert len(rows) == len(cols) == expected_size
        assert len(set(rows)) == expected_size  # no row used twice
        assert len(set(cols)) == expected_size  # no col used twice
        assert rows == sorted(rows)  # row indices ascending, like scipy
        assert all(0 <= row < num_rows for row in rows)
        assert all(0 <= col < num_cols for col in cols)


def test_optimal_total_matches_brute_force() -> None:
    rng = random.Random(2)
    for _ in range(300):
        num_rows = rng.randint(1, 5)
        num_cols = rng.randint(1, 5)
        # integer costs with heavy ties, like capture similarities
        matrix = [
            [float(rng.randint(0, 3)) for _ in range(num_cols)] for _ in range(num_rows)
        ]
        for maximize in (False, True):
            rows, cols = linear_sum_assignment(matrix, maximize=maximize)
            assert assignment_total(matrix, rows, cols) == brute_force_best_total(
                matrix, maximize
            )


def test_optimal_total_with_float_and_negative_costs() -> None:
    rng = random.Random(3)
    for _ in range(100):
        num_rows = rng.randint(1, 5)
        num_cols = rng.randint(1, 5)
        matrix = [
            [rng.uniform(-10, 10) for _ in range(num_cols)] for _ in range(num_rows)
        ]
        rows, cols = linear_sum_assignment(matrix, maximize=True)
        assert assignment_total(matrix, rows, cols) == pytest.approx(
            brute_force_best_total(matrix, True)
        )


def test_maximize_equals_negated_minimize_total() -> None:
    rng = random.Random(4)
    for _ in range(50):
        matrix = [[rng.uniform(0, 9) for _ in range(4)] for _ in range(4)]
        negated = [[-value for value in row] for row in matrix]
        max_rows, max_cols = linear_sum_assignment(matrix, maximize=True)
        min_rows, min_cols = linear_sum_assignment(negated)
        assert assignment_total(matrix, max_rows, max_cols) == pytest.approx(
            -assignment_total(negated, min_rows, min_cols)
        )


def test_tie_breaking_is_deterministic_and_scipy_shaped() -> None:
    # every optimal assignment totals 8 here; scipy (and therefore this
    # port, verified by the differential test) picks cols [2, 1]
    matrix = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
    assert linear_sum_assignment(matrix, maximize=True) == ([0, 1], [2, 1])
    # same input twice → identical output
    tie_matrix = [[1.0, 1.0], [1.0, 1.0]]
    first = linear_sum_assignment(tie_matrix, maximize=True)
    assert first == linear_sum_assignment(tie_matrix, maximize=True)


def test_all_zero_similarities_still_assigns_fully() -> None:
    # capture matching relies on min(n, m) pairs even at zero similarity
    rows, cols = linear_sum_assignment([[0.0, 0.0], [0.0, 0.0]], maximize=True)
    assert len(rows) == 2 and sorted(cols) == [0, 1]


def test_empty_inputs() -> None:
    assert linear_sum_assignment([]) == ([], [])
    assert linear_sum_assignment([[]]) == ([], [])


def test_infeasible_matrix_raises() -> None:
    infinity = float("inf")
    with pytest.raises(ValueError):
        linear_sum_assignment([[infinity, infinity]], maximize=False)


def test_greedy_trap() -> None:
    # a greedy matcher takes 10 first and is stuck with 1 (total 11);
    # the optimal assignment sacrifices the 10 for 9 + 9 = 18
    matrix = [[10.0, 9.0], [9.0, 1.0]]
    rows, cols = linear_sum_assignment(matrix, maximize=True)
    assert assignment_total(matrix, rows, cols) == 18.0
    # deeper trap: optimum avoids the whole greedy diagonal
    matrix = [
        [9.0, 8.0, 0.0],
        [8.0, 0.0, 1.0],
        [0.0, 1.0, 2.0],
    ]
    rows, cols = linear_sum_assignment(matrix, maximize=True)
    assert assignment_total(matrix, rows, cols) == brute_force_best_total(matrix, True)


def test_structured_matrices_with_closed_form_optimum() -> None:
    # cost[i][j] = i * j: by the rearrangement inequality the maximum
    # pairs large with large (identity), the minimum pairs large with small
    for size in (2, 3, 5, 8):
        matrix = [[float(i * j) for j in range(size)] for i in range(size)]
        rows, cols = linear_sum_assignment(matrix, maximize=True)
        assert assignment_total(matrix, rows, cols) == float(
            sum(i * i for i in range(size))
        )
        rows, cols = linear_sum_assignment(matrix)
        assert assignment_total(matrix, rows, cols) == float(
            sum(i * (size - 1 - i) for i in range(size))
        )
    # diagonally dominant: identity assignment is uniquely optimal
    matrix = [
        [5.0, 1.0, 1.0],
        [1.0, 5.0, 1.0],
        [1.0, 1.0, 5.0],
    ]
    assert linear_sum_assignment(matrix, maximize=True) == (
        [0, 1, 2],
        [0, 1, 2],
    )


def test_identical_rows_and_columns() -> None:
    # all rows identical: every assignment is optimal; result must still be
    # a full valid pairing with the right total
    matrix = [[3.0, 3.0, 3.0]] * 3
    rows, cols = linear_sum_assignment(matrix, maximize=True)
    assert rows == [0, 1, 2] and sorted(cols) == [0, 1, 2]
    assert assignment_total(matrix, rows, cols) == 9.0
    # one column strictly dominates: exactly one row can have it
    matrix = [[9.0, 0.0], [9.0, 0.0], [9.0, 0.0]]
    rows, cols = linear_sum_assignment(matrix, maximize=True)
    assert sorted(cols) == [0, 1]
    assert assignment_total(matrix, rows, cols) == 9.0


def test_single_row_and_single_column() -> None:
    row = [[3.0, 7.0, 5.0, 7.0]]
    assert linear_sum_assignment(row, maximize=True) == ([0], [1])
    assert linear_sum_assignment(row) == ([0], [0])
    column = [[3.0], [7.0], [5.0]]
    assert linear_sum_assignment(column, maximize=True) == ([1], [0])
    assert linear_sum_assignment(column) == ([0], [0])


def test_near_tie_precision() -> None:
    # values differing by 1e-9 must still resolve to the true optimum
    epsilon = 1e-9
    matrix = [[1.0, 1.0 + epsilon], [1.0 + epsilon, 1.0]]
    rows, cols = linear_sum_assignment(matrix, maximize=True)
    assert assignment_total(matrix, rows, cols) == pytest.approx(2.0 + 2 * epsilon)


def test_larger_matrices_stay_valid_and_beat_sampled_permutations() -> None:
    # brute force is impossible at this size; check structural validity and
    # that the reported optimum beats greedy and many random permutations
    rng = random.Random(5)
    size = 40
    matrix = [[rng.uniform(0, 100) for _ in range(size)] for _ in range(size)]
    rows, cols = linear_sum_assignment(matrix, maximize=True)
    assert rows == list(range(size))
    assert sorted(cols) == list(range(size))
    total = assignment_total(matrix, rows, cols)

    # greedy row-by-row baseline
    taken: set[int] = set()
    greedy_total = 0.0
    for row_values in matrix:
        best_col = max(
            (col for col in range(size) if col not in taken),
            key=lambda col: row_values[col],
        )
        taken.add(best_col)
        greedy_total += row_values[best_col]
    assert total >= greedy_total - 1e-9

    permutation = list(range(size))
    for _ in range(500):
        rng.shuffle(permutation)
        sampled = sum(matrix[i][permutation[i]] for i in range(size))
        assert total >= sampled - 1e-9


def test_determinism_across_repeated_calls() -> None:
    rng = random.Random(6)
    for _ in range(50):
        matrix = [[float(rng.randint(0, 2)) for _ in range(rng.randint(1, 6))]]
        matrix = matrix * rng.randint(1, 6)
        first = linear_sum_assignment(matrix, maximize=True)
        for _ in range(3):
            assert linear_sum_assignment(matrix, maximize=True) == first


def test_input_matrix_is_not_mutated() -> None:
    matrix = [[1.0, 2.0], [3.0, 4.0]]
    snapshot = [row[:] for row in matrix]
    linear_sum_assignment(matrix, maximize=True)
    linear_sum_assignment(matrix)
    assert matrix == snapshot


def test_differential_vs_scipy_exact_indices() -> None:
    """Index-level parity with scipy across several regimes (skipped in
    environments without scipy — the brute-force tests above still pin
    optimality there)."""
    np = pytest.importorskip("numpy")
    scipy_optimize = pytest.importorskip("scipy.optimize")

    rng = random.Random(20260714)
    regimes = [
        # (rows, cols, value factory) — ties, floats, negatives, rectangular
        (8, 8, lambda: float(rng.randint(0, 3))),
        (6, 3, lambda: float(rng.randint(0, 2))),
        (3, 6, lambda: float(rng.randint(0, 2))),
        (5, 5, lambda: rng.uniform(-10, 10)),
        (7, 2, lambda: rng.uniform(0, 1)),
    ]
    for num_rows, num_cols, value in regimes:
        for _ in range(400):
            matrix = [[value() for _ in range(rng.randint(1, num_cols))]]
            width = len(matrix[0])
            matrix = [
                [value() for _ in range(width)] for _ in range(rng.randint(1, num_rows))
            ]
            for maximize in (False, True):
                scipy_rows, scipy_cols = scipy_optimize.linear_sum_assignment(
                    np.array(matrix, dtype=np.float32), maximize=maximize
                )
                # float32 truncation must be applied on our side too for a
                # fair index-level comparison
                truncated = [[float(np.float32(v)) for v in row] for row in matrix]
                our_rows, our_cols = linear_sum_assignment(truncated, maximize=maximize)
                assert list(scipy_rows) == our_rows
                assert list(scipy_cols) == our_cols
