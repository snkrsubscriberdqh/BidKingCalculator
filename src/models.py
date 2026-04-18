from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class CountCombination:
    w: int
    g: int
    b: int
    p: int
    o: int
    r: int

    def by_grade(self) -> Dict[int, int]:
        return {
            1: self.w,
            2: self.g,
            3: self.b,
            4: self.p,
            5: self.o,
            6: self.r,
        }

    @property
    def total(self) -> int:
        return self.w + self.g + self.b + self.p + self.o + self.r


@dataclass
class PriceAvgClue:
    grade: int
    avg_price: float
    count_override: Optional[int] = None
    exact_reachable: bool = False


@dataclass
class GradeGridTotalClue:
    grade: int
    total_grid: int
    candidate_grid_sizes: List[int]


@dataclass
class SilhouetteClue:
    candidate_grades: List[int]
    candidate_item_ids: List[int] = field(default_factory=list)
    source_id: Optional[str] = None
    min_exist_count: int = 1


@dataclass
class SolverConstraints:
    total_count: int
    gw_count: Optional[int] = None
    avg_grid_o: Optional[float] = None
    avg_grid_p: Optional[float] = None
    avg_grid_b: Optional[float] = None
    avg_grid_half_tolerance: float = 0.05
    global_total_grid: Optional[int] = None
    grid_size_options_by_grade: Dict[int, List[int]] = field(default_factory=dict)
    min_count_by_grade: Dict[int, int] = field(default_factory=dict)
    max_count_by_grade: Dict[int, int] = field(default_factory=dict)
    exact_count_by_grade: Dict[int, int] = field(default_factory=dict)
    price_avg_clues: List[PriceAvgClue] = field(default_factory=list)
    grade_grid_total_clues: List[GradeGridTotalClue] = field(default_factory=list)
    silhouette_clues: List[SilhouetteClue] = field(default_factory=list)


@dataclass
class SimulationResult:
    expected_value: float
    safe_bid_95: float
    pessimistic_bid: float
    max_value: float
    combination_count: int
    expected_combo: Optional[CountCombination]
    expected_combo_value: float
    safe_bid_combo: Optional[CountCombination]
    safe_bid_combo_value: float
    pessimistic_combo: Optional[CountCombination]
    pessimistic_combo_value: float
    max_combo: Optional[CountCombination]
    max_combo_value: float
