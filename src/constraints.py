import math
from fractions import Fraction


def denominator_from_avg_grid(avg_grid: float) -> int:
    frac = Fraction(str(avg_grid)).limit_denominator()
    return frac.denominator


def check_divisibility(avg_grid: float, count: int) -> bool:
    denominator = denominator_from_avg_grid(avg_grid)
    return count % denominator == 0


def check_total_count(total_count: int, *counts: int) -> bool:
    return sum(counts) == total_count


def check_gw_count(g_count: int, w_count: int, gw_count: int) -> bool:
    return g_count + w_count == gw_count


def check_price_bounds(avg_price: float, total_price: int, count: int) -> bool:
    if count <= 0:
        return False
    avg_price_cent = avg_price * 100
    lower = math.floor((avg_price_cent - 0.5) * count)
    upper = math.ceil((avg_price_cent + 0.5) * count)
    total_cent = total_price * 100
    return lower <= total_cent <= upper


def check_price_bounds_feasible(avg_price: float, count: int, min_unit_price: int, max_unit_price: int) -> bool:
    if count <= 0:
        return False
    avg_price_cent = avg_price * 100
    lower = math.floor((avg_price_cent - 0.5) * count)
    upper = math.ceil((avg_price_cent + 0.5) * count)
    feasible_lower = min_unit_price * count * 100
    feasible_upper = max_unit_price * count * 100
    return max(lower, feasible_lower) <= min(upper, feasible_upper)


def price_bounds_to_total_range(avg_price: float, count: int) -> tuple[int, int]:
    avg_price_cent = avg_price * 100
    lower_cent = math.floor((avg_price_cent - 0.5) * count)
    upper_cent = math.ceil((avg_price_cent + 0.5) * count)
    min_total_price = math.ceil(lower_cent / 100)
    max_total_price = math.floor(upper_cent / 100)
    return min_total_price, max_total_price


def check_grid_total_reachable(count: int, total_grid: int, candidate_grid_sizes: list[int]) -> bool:
    if count < 0 or total_grid < 0 or not candidate_grid_sizes:
        return False
    if count == 0:
        return total_grid == 0

    sizes = sorted({int(x) for x in candidate_grid_sizes if int(x) > 0})
    if not sizes:
        return False

    min_size, max_size = sizes[0], sizes[-1]
    if total_grid < count * min_size or total_grid > count * max_size:
        return False

    possible = {0}
    max_state_count = 40_000
    for used in range(1, count + 1):
        remaining = count - used
        lower_need = total_grid - remaining * max_size
        upper_need = total_grid - remaining * min_size

        nxt = set()
        for partial in possible:
            for s in sizes:
                total = partial + s
                if lower_need <= total <= upper_need:
                    nxt.add(total)
        if not nxt:
            return False
        if len(nxt) > max_state_count:
            return True
        possible = nxt

    return total_grid in possible


def check_avg_grid_rounded_feasible(
    avg_grid: float,
    count: int,
    candidate_grid_sizes: list[int],
    display_decimals: int = 2,
    half_tolerance: float | None = None,
) -> bool:
    if count < 0:
        return False
    if half_tolerance is None:
        unit = 10 ** (-display_decimals)
        half = unit / 2.0
    else:
        half = float(half_tolerance)
        if half <= 0:
            return False
    if count == 0:
        return abs(avg_grid) <= half
    if avg_grid <= 0:
        return False

    sizes = sorted({int(x) for x in candidate_grid_sizes if int(x) > 0})
    if not sizes:
        return False

    lower = max(0.0, float(avg_grid) - half)
    upper = float(avg_grid) + half
    min_total = math.ceil(lower * count - 1e-9)
    max_total = math.floor(upper * count + 1e-9)
    if min_total > max_total:
        return False

    min_size, max_size = sizes[0], sizes[-1]
    if max_total < min_size * count or min_total > max_size * count:
        return False

    possible = {0}
    max_state_count = 40_000
    for used in range(1, count + 1):
        remaining = count - used
        lower_need = min_total - remaining * max_size
        upper_need = max_total - remaining * min_size

        nxt = set()
        for partial in possible:
            for s in sizes:
                total = partial + s
                if lower_need <= total <= upper_need:
                    nxt.add(total)
        if not nxt:
            return False
        if len(nxt) > max_state_count:
            return True
        possible = nxt

    return any(min_total <= x <= max_total for x in possible)
