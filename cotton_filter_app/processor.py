"""Excel sheet and workbook processing."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

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

ProgressLogger = Callable[[str], None]


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


def process_sheet(
    raw_frame: pd.DataFrame,
    log: ProgressLogger | None = None,
    sheet_name: str = "",
) -> pd.DataFrame | None:
    """处理单个 sheet；非数据表或无保留行时返回 None。"""

    log_prefix = f"[{sheet_name}] " if sheet_name else ""
    header_row = find_header_row(raw_frame)
    if header_row < 0:
        if log:
            log(f"{log_prefix}未识别到表头，跳过")
        return None

    if log:
        log(f"{log_prefix}识别到表头行: 第 {header_row + 1} 行")

    column_map = build_column_map(raw_frame.iloc[header_row].tolist())
    missing_columns = [
        column_name for column_name in REQUIRED_COLUMNS if column_name not in column_map
    ]
    if missing_columns:
        if log:
            log(f"{log_prefix}缺少必需字段: {', '.join(missing_columns)}，跳过")
        return None

    body = raw_frame.iloc[header_row + 1 :].reset_index(drop=True)
    records = [
        record
        for _, row in body.iterrows()
        if (record := build_record(row, column_map)) is not None
    ]

    if log:
        log(f"{log_prefix}数据行 {len(body)} 行，有效基差行 {len(records)} 行")

    if not records:
        if log:
            log(f"{log_prefix}没有可评分数据，跳过")
        return None

    output_frame = format_output_frame(records)
    if log:
        log(f"{log_prefix}命中筛选条件 {len(output_frame)} 行")
    return output_frame if len(output_frame) else None


def filter_file(src: Path, dst: Path, log: ProgressLogger | None = None) -> int:
    """处理单个 Excel 文件，返回保留行数。"""

    if log:
        log(f"读取工作簿: {src.name}")
    excel_file = pd.ExcelFile(src)
    if log:
        log(f"发现 {len(excel_file.sheet_names)} 个 sheet: {', '.join(excel_file.sheet_names)}")
    sheet_results: list[pd.DataFrame] = []

    for sheet_name in excel_file.sheet_names:
        if log:
            log(f"开始读取 sheet: {sheet_name}")
        raw_frame = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
        if log:
            log(f"[{sheet_name}] 原始尺寸: {len(raw_frame)} 行 x {len(raw_frame.columns)} 列")
        result = process_sheet(raw_frame, log=log, sheet_name=sheet_name)
        if result is None:
            continue

        result.insert(0, "来源sheet", sheet_name)
        sheet_results.append(result)

    if not sheet_results:
        if log:
            log("当前文件没有命中结果，不生成输出文件")
        return 0

    output_frame = pd.concat(sheet_results, ignore_index=True)
    if log:
        log(f"写出结果: {dst.name}，共 {len(output_frame)} 行")
    output_frame.to_excel(dst, index=False)
    return len(output_frame)
