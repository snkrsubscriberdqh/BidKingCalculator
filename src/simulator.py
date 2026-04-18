import math
from typing import Dict, List

import numpy as np

from .models import CountCombination, SimulationResult


GRADE_PRIOR = {1: 32, 2: 32, 3: 16, 4: 8, 5: 2, 6: 1}
_PRIOR_SUM = float(sum(GRADE_PRIOR.values()))
GRADE_PROB = {g: (w / _PRIOR_SUM) for g, w in GRADE_PRIOR.items()}


def _combo_log_weight(combo: CountCombination) -> float:
    # Game uses replacement draws across grades, so count vectors follow multinomial PMF.
    by_grade = combo.by_grade()
    n = combo.total
    log_coeff = math.lgamma(n + 1) - sum(math.lgamma(by_grade[g] + 1) for g in by_grade)
    log_prob = sum(by_grade[g] * math.log(GRADE_PROB[g]) for g in by_grade)
    return log_coeff + log_prob


def _weighted_quantile(values: np.ndarray, weights: np.ndarray, quantile: float) -> float:
    order = np.argsort(values)
    sorted_values = values[order]
    sorted_weights = weights[order]
    cdf = np.cumsum(sorted_weights)
    threshold = quantile * cdf[-1]
    idx = np.searchsorted(cdf, threshold, side="left")
    idx = min(idx, len(sorted_values) - 1)
    return float(sorted_values[idx])


def _inverse_price_probs(pool: np.ndarray) -> np.ndarray:
    prices = pool.astype(np.float64)
    # Guard against zero/negative prices in dirty data.
    prices = np.where(prices > 0, prices, 1.0)
    inv = 1.0 / prices
    return inv / inv.sum()


def run_monte_carlo(
    combinations: List[CountCombination],
    price_pools: Dict[int, np.ndarray],
    num_samples: int = 10_000,
    seed: int | None = None,
    safe_bid_mode: str = "equal",
    safe_bid_confidence_pct: float = 95.0,
    filter_extreme_red: bool = False,
    red_extreme_percentile: float = 95.0,
    max_red_extreme_count: int = 1,
    filter_extreme_orange: bool = False,
    orange_extreme_percentile: float = 95.0,
    max_orange_extreme_count: int = 1,
    use_count_dependency: bool = False,
    red_additional_decay: float = 0.25,
    orange_additional_decay: float = 0.5,
    max_red_count: int = -1,
    max_orange_count: int = -1,
) -> SimulationResult:
    if not combinations:
        raise ValueError("无合法组合，无法进行模拟")
    if num_samples <= 0:
        raise ValueError("num_samples 必须大于 0")
    if not (0 < safe_bid_confidence_pct < 100):
        raise ValueError("safe_bid_confidence_pct 必须在 (0, 100) 区间")
    if not (0 < red_extreme_percentile < 100):
        raise ValueError("red_extreme_percentile 必须在 (0, 100) 区间")
    if not (0 < orange_extreme_percentile < 100):
        raise ValueError("orange_extreme_percentile 必须在 (0, 100) 区间")
    if max_red_extreme_count < 0:
        raise ValueError("max_red_extreme_count 不能为负数")
    if max_orange_extreme_count < 0:
        raise ValueError("max_orange_extreme_count 不能为负数")
    if not (0 < red_additional_decay <= 1):
        raise ValueError("red_additional_decay 必须在 (0, 1] 区间")
    if not (0 < orange_additional_decay <= 1):
        raise ValueError("orange_additional_decay 必须在 (0, 1] 区间")
    if max_red_count < -1 or max_orange_count < -1:
        raise ValueError("max_red_count/max_orange_count 只能是 -1 或非负整数")

    rng = np.random.default_rng(seed)
    combo_logs = np.asarray([_combo_log_weight(c) for c in combinations], dtype=np.float64)
    combo_logs -= combo_logs.max()
    combo_weights = np.exp(combo_logs)
    if use_count_dependency or max_red_count >= 0 or max_orange_count >= 0:
        combo_penalties = np.ones(len(combinations), dtype=np.float64)
        for i, combo in enumerate(combinations):
            by_grade = combo.by_grade()
            red_count = by_grade.get(6, 0)
            orange_count = by_grade.get(5, 0)
            if max_red_count >= 0 and red_count > max_red_count:
                combo_penalties[i] = 0.0
                continue
            if max_orange_count >= 0 and orange_count > max_orange_count:
                combo_penalties[i] = 0.0
                continue
            if use_count_dependency:
                if red_count > 1:
                    combo_penalties[i] *= red_additional_decay ** (red_count - 1)
                if orange_count > 1:
                    combo_penalties[i] *= orange_additional_decay ** (orange_count - 1)
        combo_weights *= combo_penalties
    if combo_weights.sum() <= 0:
        raise ValueError("红/橙数量依赖参数过于严格，导致无可用组合权重")
    combo_weights = combo_weights / combo_weights.sum()
    if safe_bid_mode not in {"equal", "prior"}:
        raise ValueError("safe_bid_mode 必须是 'equal' 或 'prior'")

    # Within one grade, item appearance probability is inversely proportional to item value.
    pool_probs = {grade: _inverse_price_probs(pool) for grade, pool in price_pools.items()}

    means = []
    combo_order = []
    combo_safe_q = []
    combo_pess_q = []
    theoretical_max_values = []
    all_values = []
    all_weights = []

    equal_combo_weight = 1.0 / len(combinations)
    tail_quantile = (100.0 - float(safe_bid_confidence_pct)) / 100.0
    for combo, w in zip(combinations, combo_weights):
        totals = np.zeros(num_samples, dtype=np.int64)
        by_grade = combo.by_grade()
        theoretical_max = 0
        valid_mask = np.ones(num_samples, dtype=bool)

        for grade, count in by_grade.items():
            if count <= 0:
                continue
            pool = price_pools[grade]
            probs = pool_probs[grade]
            # In-game sampling is with replacement.
            picks = rng.choice(pool, size=(num_samples, count), replace=True, p=probs)
            totals += picks.sum(axis=1)
            theoretical_max += int(pool.max()) * count

            if filter_extreme_red and grade == 6:
                red_threshold = np.percentile(pool, red_extreme_percentile)
                extreme_red_count = (picks >= red_threshold).sum(axis=1)
                valid_mask &= extreme_red_count <= max_red_extreme_count
            if filter_extreme_orange and grade == 5:
                orange_threshold = np.percentile(pool, orange_extreme_percentile)
                extreme_orange_count = (picks >= orange_threshold).sum(axis=1)
                valid_mask &= extreme_orange_count <= max_orange_extreme_count

        totals_used = totals[valid_mask] if (filter_extreme_red or filter_extreme_orange) else totals
        if totals_used.size == 0:
            # Avoid empty-sample collapse when filter is too strict.
            totals_used = totals

        mean_value = float(totals_used.mean())
        safe_q_value = float(np.quantile(totals_used, tail_quantile))
        pess_q_value = float(np.quantile(totals_used, 0.01))

        means.append(mean_value)
        combo_order.append(combo)
        combo_safe_q.append(safe_q_value)
        combo_pess_q.append(pess_q_value)
        theoretical_max_values.append(float(theoretical_max))
        all_values.append(totals_used.astype(np.float64))
        quantile_combo_weight = w if safe_bid_mode == "prior" else equal_combo_weight
        all_weights.append(
            np.full(totals_used.size, quantile_combo_weight / totals_used.size, dtype=np.float64)
        )

    all_values_arr = np.concatenate(all_values)
    all_weights_arr = np.concatenate(all_weights)
    expected_value = float(np.dot(np.asarray(means), combo_weights))
    safe_bid_95 = _weighted_quantile(all_values_arr, all_weights_arr, tail_quantile)
    pessimistic_bid = _weighted_quantile(all_values_arr, all_weights_arr, 0.01)
    max_value = float(np.max(np.asarray(theoretical_max_values)))

    means_arr = np.asarray(means, dtype=np.float64)
    safe_arr = np.asarray(combo_safe_q, dtype=np.float64)
    pess_arr = np.asarray(combo_pess_q, dtype=np.float64)
    max_arr = np.asarray(theoretical_max_values, dtype=np.float64)

    expected_idx = int(np.argmin(np.abs(means_arr - expected_value)))
    safe_idx = int(np.argmin(np.abs(safe_arr - safe_bid_95)))
    pessimistic_idx = int(np.argmin(np.abs(pess_arr - pessimistic_bid)))
    max_idx = int(np.argmax(max_arr))

    return SimulationResult(
        expected_value=expected_value,
        safe_bid_95=safe_bid_95,
        pessimistic_bid=pessimistic_bid,
        expected_combo=combo_order[expected_idx],
        expected_combo_value=float(means_arr[expected_idx]),
        safe_bid_combo=combo_order[safe_idx],
        safe_bid_combo_value=float(safe_arr[safe_idx]),
        pessimistic_combo=combo_order[pessimistic_idx],
        pessimistic_combo_value=float(pess_arr[pessimistic_idx]),
        max_combo=combo_order[max_idx],
        max_combo_value=float(max_arr[max_idx]),
        max_value=max_value,
        combination_count=len(combinations),
    )
