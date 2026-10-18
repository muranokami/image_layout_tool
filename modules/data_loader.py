"""入力データ（Excel/CSV）の読み込みとバリデーション"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

REQUIRED_COLUMNS = ["id", "template_id", "product_image_path"]
OPTIONAL_COLUMNS = [
    "title_text",
    "sub_text",
    "bg_prompt",
    "bg_asset_path",
    "illust_prompt",
    "illust_asset_path",
    "output_filename",
]
ALL_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS


def load_rows(input_path: str) -> list[dict[str, Any]]:
    """Excel(.xlsx)またはCSVを読み込み、行の辞書リストとして返す"""
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"入力ファイルが見つかりません: {input_path}")

    if path.suffix.lower() in (".xlsx", ".xlsm"):
        df = pd.read_excel(path, dtype=str)
    elif path.suffix.lower() == ".csv":
        df = pd.read_csv(path, dtype=str)
    else:
        raise ValueError(f"未対応のファイル形式です: {path.suffix}")

    df = df.fillna("")

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"必須列が不足しています: {missing}")

    for col in OPTIONAL_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    rows: list[dict[str, Any]] = []
    for i, r in df.iterrows():
        row = {col: str(r.get(col, "")).strip() for col in ALL_COLUMNS}
        if not row["id"]:
            raise ValueError(f"{i + 2}行目: id が空です")
        if not row["output_filename"]:
            row["output_filename"] = f"{row['id']}.png"
        rows.append(row)

    return rows
