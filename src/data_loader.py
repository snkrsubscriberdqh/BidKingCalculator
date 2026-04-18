import csv
from pathlib import Path
from typing import Dict, Iterable, Optional

import numpy as np


GRADE_FILE_MAP = {
    1: "item_list_w.csv",
    2: "item_list_g.csv",
    3: "item_list_b.csv",
    4: "item_list_p.csv",
    5: "item_list_o.csv",
    6: "item_list_r.csv",
}


def parse_price_from_row(row: Iterable[str]) -> int:
    parsed = parse_row_price_grid(row)
    return parsed[0]


def _parse_int_like(text: str) -> Optional[int]:
    try:
        return int(float(text.strip()))
    except Exception:
        return None


def parse_row_price_grid(row: Iterable[str]) -> tuple[int, Optional[int]]:
    fields = [cell.strip() for cell in row if cell is not None and str(cell).strip() != ""]
    if not fields:
        raise ValueError("空行无法解析价格/格数")

    if len(fields) == 1:
        return int(float(fields[0])), None

    # 格式A: 名称,价格[,格数]
    if _parse_int_like(fields[0]) is None:
        price = _parse_int_like(fields[1])
        if price is None:
            raise ValueError(f"无法解析价格列: {fields}")
        grid = _parse_int_like(fields[2]) if len(fields) >= 3 else None
        return price, grid

    # 格式B: 价格,格数
    price = _parse_int_like(fields[0])
    if price is None:
        raise ValueError(f"无法解析价格列: {fields}")
    grid = _parse_int_like(fields[1]) if len(fields) >= 2 else None
    return price, grid


def load_price_pools(data_dir: str) -> Dict[int, np.ndarray]:
    data_path = Path(data_dir)
    pools: Dict[int, np.ndarray] = {}

    for grade, file_name in GRADE_FILE_MAP.items():
        file_path = data_path / file_name
        if not file_path.exists():
            raise FileNotFoundError(f"缺少数据文件: {file_path}")

        prices = []
        with file_path.open("r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if not row:
                    continue
                price, _ = parse_row_price_grid(row)
                prices.append(price)

        if not prices:
            raise ValueError(f"文件无有效价格数据: {file_path}")
        pools[grade] = np.asarray(prices, dtype=np.int64)

    return pools


def load_grid_size_options_by_grade(data_dir: str) -> Dict[int, list[int]]:
    data_path = Path(data_dir)
    options: Dict[int, list[int]] = {}

    for grade, file_name in GRADE_FILE_MAP.items():
        file_path = data_path / file_name
        if not file_path.exists():
            raise FileNotFoundError(f"缺少数据文件: {file_path}")

        grids = set()
        with file_path.open("r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if not row:
                    continue
                _, grid = parse_row_price_grid(row)
                if grid is not None and grid > 0:
                    grids.add(int(grid))
        options[grade] = sorted(grids)

    return options


def load_item_grade_mapping(data_dir: str) -> Dict[int, int]:
    data_path = Path(data_dir)
    candidates = [
        data_path / "items_data.csv",
        data_path / "items_data.tsv",
    ]
    file_path = None
    for p in candidates:
        if p.exists():
            file_path = p
            break
    if file_path is None:
        return {}

    delimiter = "," if file_path.suffix.lower() == ".csv" else "\t"
    mapping: Dict[int, int] = {}
    with file_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        if not reader.fieldnames:
            return {}
        lowered = {name.lower(): name for name in reader.fieldnames}
        item_id_col = lowered.get("item_id")
        grade_col = lowered.get("grade")
        if not item_id_col or not grade_col:
            return {}
        for row in reader:
            try:
                item_id = int(float(row[item_id_col]))
                grade = int(float(row[grade_col]))
            except Exception:
                continue
            if 1 <= grade <= 6:
                mapping[item_id] = grade
    return mapping
