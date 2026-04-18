import csv
from pathlib import Path


GRADE_FILE_MAP = {
    1: "item_list_w.csv",
    2: "item_list_g.csv",
    3: "item_list_b.csv",
    4: "item_list_p.csv",
    5: "item_list_o.csv",
    6: "item_list_r.csv",
}


def parse_row(row: list[str], grade: int, local_index: int) -> tuple[str, int, int]:
    fields = [x.strip() for x in row if x is not None and str(x).strip() != ""]
    if not fields:
        raise ValueError("存在空行，无法解析")

    if len(fields) >= 3:
        # 格式: 名称,价格,格数
        name = fields[0]
        price = int(float(fields[1]))
        grid = int(float(fields[2]))
        return name, price, grid

    if len(fields) == 2:
        # 格式: 价格,格数
        name = f"G{grade}_Item_{local_index}"
        price = int(float(fields[0]))
        grid = int(float(fields[1]))
        return name, price, grid

    # 格式: 仅价格（兼容旧数据）
    name = f"G{grade}_Item_{local_index}"
    price = int(float(fields[0]))
    grid = 0
    return name, price, grid


def build_items_data(data_dir: Path) -> Path:
    output_path = data_dir / "items_data.csv"
    rows: list[list[str | int]] = []

    global_id = 1
    for grade in range(1, 7):
        file_path = data_dir / GRADE_FILE_MAP[grade]
        if not file_path.exists():
            raise FileNotFoundError(f"缺少文件: {file_path}")

        with file_path.open("r", encoding="utf-8") as f:
            reader = csv.reader(f)
            local_index = 1
            for row in reader:
                if not row:
                    continue
                name, price, grid = parse_row(row, grade, local_index)
                rows.append([global_id, name, grade, price, grid])
                global_id += 1
                local_index += 1

    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Item_ID", "Item_Name", "Grade", "Price", "Grid_Size"])
        writer.writerows(rows)

    return output_path


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[1]
    data_dir = repo_root / "data"
    output = build_items_data(data_dir)
    print(f"已生成: {output}")
