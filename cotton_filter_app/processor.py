"""Excel sheet and workbook processing."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .constants import (
    MAX_SCORE_GAP,
    MIN_SCORE_GAP,
    OUTPUT_COLUMNS,
    REQUIRED_COLUMNS,
)
from .header import build_column_map, find_header_row
from .models import ColumnMap, Record
from .scoring import parse_float, score_record


def build_record(row: pd.Series, column_map: ColumnMap) -> Record | None:
    """从一行 Excel 数据中构建统一字段记录。"""

    basis = parse_float(row.iloc[column_map["基差"]], default=float("nan"))
    if pd.isna(basis):
        return None

    record = {
        field_name: row.iloc[column_index]
        for field_name, column_index in column_map.items()
    }
    record["_基差"] = basis
    record["_得分"] = score_record(record)
    record["_与基差差距"] = basis - record["_得分"]

    return record


def format_output_frame(records: list[Record]) -> pd.DataFrame:
    """筛选并整理最终输出 DataFrame。"""

    frame = pd.DataFrame(records)
    kept = frame[
        (frame["_与基差差距"] > MIN_SCORE_GAP)
        & (frame["_与基差差距"] <= MAX_SCORE_GAP)
    ].copy()

    kept = kept.rename(columns={"_得分": "得分", "_与基差差距": "与基差差距"})
    available_columns = [
        column for column in OUTPUT_COLUMNS if column in kept.columns
    ]
    return kept[available_columns]


def process_sheet(raw_frame: pd.DataFrame) -> pd.DataFrame | None:
    """处理单个 sheet；非数据表或无保留行时返回 None。"""

    header_row = find_header_row(raw_frame)
    if header_row < 0:
        return None

    column_map = build_column_map(raw_frame.iloc[header_row].tolist())
    if not all(column_name in column_map for column_name in REQUIRED_COLUMNS):
        return None

    body = raw_frame.iloc[header_row + 1 :].reset_index(drop=True)
    records = [
        record
        for _, row in body.iterrows()
        if (record := build_record(row, column_map)) is not None
    ]

    if not records:
        return None

    output_frame = format_output_frame(records)
    return output_frame if len(output_frame) else None


def filter_file(src: Path, dst: Path) -> int:
    """处理单个 Excel 文件，返回保留行数。"""

    excel_file = pd.ExcelFile(src)
    sheet_results: list[pd.DataFrame] = []

    for sheet_name in excel_file.sheet_names:
        raw_frame = pd.read_excel(src, sheet_name=sheet_name, header=None)
        result = process_sheet(raw_frame)
        if result is None:
            continue

        result.insert(0, "来源sheet", sheet_name)
        sheet_results.append(result)

    if not sheet_results:
        return 0

    output_frame = pd.concat(sheet_results, ignore_index=True)
    output_frame.to_excel(dst, index=False)
    return len(output_frame)
