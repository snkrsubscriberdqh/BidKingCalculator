from typing import Dict, List, Optional

import numpy as np

from .constraints import (
    check_avg_grid_rounded_feasible,
    check_divisibility,
    check_grid_total_reachable,
    check_price_bounds_feasible,
    price_bounds_to_total_range,
)
from .models import CountCombination, SolverConstraints


def _in_range(value: int, low: int, high: int) -> bool:
    return low <= value <= high


def _bounds_for_grade(grade: int, constraints: SolverConstraints) -> tuple[int, int]:
    if grade in constraints.exact_count_by_grade:
        exact = constraints.exact_count_by_grade[grade]
        return exact, exact
    low = constraints.min_count_by_grade.get(grade, 0)
    high = constraints.max_count_by_grade.get(grade, constraints.total_count)
    return low, high


def _check_grade_bounds(combo: CountCombination, constraints: SolverConstraints) -> bool:
    by_grade = combo.by_grade()
    for grade, value in by_grade.items():
        low, high = _bounds_for_grade(grade, constraints)
        if not _in_range(value, low, high):
            return False
    return True


def _check_divisibility_constraints(combo: CountCombination, constraints: SolverConstraints) -> bool:
    options = constraints.grid_size_options_by_grade
    half_tol = constraints.avg_grid_half_tolerance
    if constraints.avg_grid_o is not None:
        if options.get(5):
            if not check_avg_grid_rounded_feasible(
                constraints.avg_grid_o, combo.o, options.get(5, []), half_tolerance=half_tol
            ):
                return False
        else:
            if constraints.avg_grid_o == 0:
                if combo.o != 0:
                    return False
            elif combo.o <= 0 or not check_divisibility(constraints.avg_grid_o, combo.o):
                return False
    if constraints.avg_grid_p is not None:
        if options.get(4):
            if not check_avg_grid_rounded_feasible(
                constraints.avg_grid_p, combo.p, options.get(4, []), half_tolerance=half_tol
            ):
                return False
        else:
            if constraints.avg_grid_p == 0:
                if combo.p != 0:
                    return False
            elif combo.p <= 0 or not check_divisibility(constraints.avg_grid_p, combo.p):
                return False
    if constraints.avg_grid_b is not None:
        if options.get(3):
            if not check_avg_grid_rounded_feasible(
                constraints.avg_grid_b, combo.b, options.get(3, []), half_tolerance=half_tol
            ):
                return False
        else:
            if constraints.avg_grid_b == 0:
                if combo.b != 0:
                    return False
            elif combo.b <= 0 or not check_divisibility(constraints.avg_grid_b, combo.b):
                return False
    return True


def _check_price_avg_constraints(
    combo: CountCombination,
    constraints: SolverConstraints,
    price_pools: Optional[Dict[int, np.ndarray]],
) -> bool:
    if not constraints.price_avg_clues:
        return True
    if price_pools is None:
        return False

    by_grade = combo.by_grade()
    for clue in constraints.price_avg_clues:
        grade_count = by_grade.get(clue.grade, 0) if clue.count_override is None else clue.count_override
        if grade_count <= 0:
            return False
        pool = price_pools.get(clue.grade)
        if pool is None or len(pool) == 0:
            return False
        min_price = int(pool.min())
        max_price = int(pool.max())
        if not check_price_bounds_feasible(clue.avg_price, grade_count, min_price, max_price):
            return False
        if clue.exact_reachable and not _check_price_bounds_exact_reachable(clue.avg_price, grade_count, pool):
            return False
    return True


def _check_price_bounds_exact_reachable(avg_price: float, count: int, pool: np.ndarray) -> bool:
    if count <= 0:
        return False
    min_total, max_total = price_bounds_to_total_range(avg_price, count)
    if min_total > max_total:
        return False

    pool_values = np.unique(pool.astype(np.int64))
    if len(pool_values) == 0:
        return False

    min_unit = int(pool_values.min())
    max_unit = int(pool_values.max())
    if max_total < min_unit * count or min_total > max_unit * count:
        return False

    possible = {0}
    max_state_count = 40_000
    for used in range(1, count + 1):
        remaining = count - used
        lower_need = min_total - remaining * max_unit
        upper_need = max_total - remaining * min_unit

        next_possible = set()
        for partial in possible:
            for price in pool_values:
                total = partial + int(price)
                if lower_need <= total <= upper_need:
                    next_possible.add(total)
        if not next_possible:
            return False
        if len(next_possible) > max_state_count:
            # State explosion fallback: keep the solver responsive and defer to coarse feasible check.
            return True
        possible = next_possible

    return any(min_total <= x <= max_total for x in possible)


def _check_grid_total_clues(combo: CountCombination, constraints: SolverConstraints) -> bool:
    if not constraints.grade_grid_total_clues:
        return True
    by_grade = combo.by_grade()
    for clue in constraints.grade_grid_total_clues:
        count = by_grade.get(clue.grade, 0)
        if not check_grid_total_reachable(count, clue.total_grid, clue.candidate_grid_sizes):
            return False
    return True


def _grade_reachable_grid_sums(count: int, sizes: List[int], cap: int) -> set[int]:
    if count < 0:
        return set()
    if count == 0:
        return {0}
    values = sorted({int(x) for x in sizes if int(x) > 0})
    if not values:
        return set()

    reachable = {0}
    for _ in range(count):
        nxt = set()
        for s in reachable:
            for v in values:
                t = s + v
                if t <= cap:
                    nxt.add(t)
        if not nxt:
            return set()
        reachable = nxt
    return reachable


def _check_global_total_grid_clue(combo: CountCombination, constraints: SolverConstraints) -> bool:
    target = constraints.global_total_grid
    if target is None:
        return True
    if target < 0:
        return False
    options = constraints.grid_size_options_by_grade
    if not options:
        return False

    by_grade = combo.by_grade()
    min_total = 0
    max_total = 0
    for grade, count in by_grade.items():
        if count <= 0:
            continue
        sizes = options.get(grade, [])
        if not sizes:
            return False
        min_size = min(sizes)
        max_size = max(sizes)
        min_total += count * min_size
        max_total += count * max_size
    if target < min_total or target > max_total:
        return False

    reachable = {0}
    for grade, count in by_grade.items():
        if count <= 0:
            continue
        sizes = options.get(grade, [])
        grade_sums = _grade_reachable_grid_sums(count, sizes, target)
        if not grade_sums:
            return False

        nxt = set()
        for a in reachable:
            for b in grade_sums:
                t = a + b
                if t <= target:
                    nxt.add(t)
        if not nxt:
            return False
        reachable = nxt
    return target in reachable


def _check_silhouette_clues(combo: CountCombination, constraints: SolverConstraints) -> bool:
    if not constraints.silhouette_clues:
        return True
    by_grade = combo.by_grade()
    for clue in constraints.silhouette_clues:
        total = sum(by_grade.get(g, 0) for g in clue.candidate_grades)
        if total < clue.min_exist_count:
            return False
    return True


def solve_valid_combinations(
    constraints: SolverConstraints,
    price_pools: Optional[Dict[int, np.ndarray]] = None,
) -> List[CountCombination]:
    total = constraints.total_count
    gw = constraints.gw_count
    valid: List[CountCombination] = []

    if total < 0:
        return valid
    if gw is not None and (gw < 0 or gw > total):
        return valid

    if gw is not None:
        target_high = total - gw
        for r in range(0, target_high + 1):
            for o in range(0, target_high - r + 1):
                for p in range(0, target_high - r - o + 1):
                    b = target_high - r - o - p
                    for g in range(0, gw + 1):
                        w = gw - g
                        combo = CountCombination(w=w, g=g, b=b, p=p, o=o, r=r)
                        if (
                            _check_grade_bounds(combo, constraints)
                            and _check_divisibility_constraints(combo, constraints)
                            and _check_price_avg_constraints(combo, constraints, price_pools)
                            and _check_grid_total_clues(combo, constraints)
                            and _check_global_total_grid_clue(combo, constraints)
                            and _check_silhouette_clues(combo, constraints)
                        ):
                            valid.append(combo)
        return valid

    for r in range(0, total + 1):
        for o in range(0, total - r + 1):
            for p in range(0, total - r - o + 1):
                for b in range(0, total - r - o - p + 1):
                    for g in range(0, total - r - o - p - b + 1):
                        w = total - r - o - p - b - g
                        combo = CountCombination(w=w, g=g, b=b, p=p, o=o, r=r)
                        if (
                            _check_grade_bounds(combo, constraints)
                            and _check_divisibility_constraints(combo, constraints)
                            and _check_price_avg_constraints(combo, constraints, price_pools)
                            and _check_grid_total_clues(combo, constraints)
                            and _check_global_total_grid_clue(combo, constraints)
                            and _check_silhouette_clues(combo, constraints)
                        ):
                            valid.append(combo)

    return valid
