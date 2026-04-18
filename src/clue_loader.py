import json
from pathlib import Path
from typing import Any, Dict, List


def _as_int_list(values: Any, field_name: str, key: str) -> List[int]:
    if not isinstance(values, list):
        raise ValueError(f"轮廓 {key} 的 {field_name} 必须是数组")
    return [int(x) for x in values]


def load_silhouette_dict(data_dir: str) -> Dict[str, Dict[str, List[int]]]:
    file_path = Path(data_dir) / "silhouette_dict.json"
    if not file_path.exists():
        return {}

    with file_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    if not isinstance(raw, dict):
        raise ValueError("silhouette_dict.json 顶层必须是对象")

    result: Dict[str, Dict[str, List[int]]] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            raise ValueError("silhouette_dict.json 的键必须是字符串")

        grades: List[int] = []
        item_ids: List[int] = []
        # 兼容旧格式: "silhouette_xxx": [4,5]
        if isinstance(value, list):
            grades = _as_int_list(value, "grades", key)
        elif isinstance(value, dict):
            if "grades" in value:
                grades = _as_int_list(value.get("grades", []), "grades", key)
            if "item_ids" in value:
                item_ids = _as_int_list(value.get("item_ids", []), "item_ids", key)
        else:
            raise ValueError(f"轮廓 {key} 的值必须是数组或对象")

        for g in grades:
            if g < 1 or g > 6:
                raise ValueError(f"轮廓 {key} 包含非法等级 {g}，必须在1-6")

        result[key] = {
            "grades": sorted(set(grades)),
            "item_ids": sorted(set(item_ids)),
        }

    return result
