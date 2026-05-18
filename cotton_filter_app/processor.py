"""Excel sheet and workbook processing."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pandas as pd

from .header import build_column_map, find_header_row, normalize_text
from .models import ColumnMap, Record
from .rules import DataRule, RuleSet, load_ruleset, matches_range
from .scoring import extract_max_color_percent, parse_float, score_record
from .text_utils import normalize_text

ProgressLogger = Callable[[str], None]
ColorColumns = list[tuple[int, str]]


def is_empty_cell(value: object) -> bool:
    """判断单元格是否为空。"""

    return value is None or pd.isna(value) or str(value).strip() == ""


def is_color_grade_label(value: object, rule_set: RuleSet | None = None) -> bool:
    """判断组合表头中的子列是否是颜色级标签。"""

    active_rule_set = rule_set or load_ruleset()
    if active_rule_set.is_value_alias("颜色级", value):
        return True

    text = normalize_text(value)
    if not text or text in {"无", "--"}:
        return False
    return False


def detect_color_columns(
    raw_frame: pd.DataFrame,
    header_row: int,
    column_map: ColumnMap,
    rule_set: RuleSet | None = None,
) -> ColorColumns:
    """识别类似“颜色级比例(%)”下分多列的组合表头。"""

    if "颜色级" not in column_map or header_row + 1 >= len(raw_frame):
        return []

    start_column = column_map["颜色级"]
    header_cells = raw_frame.iloc[header_row].tolist()
    subheader_cells = raw_frame.iloc[header_row + 1].tolist()
    end_column = start_column + 1

    while end_column < len(header_cells) and is_empty_cell(header_cells[end_column]):
        end_column += 1

    if end_column - start_column <= 1:
        return []

    color_columns: ColorColumns = []
    for column_index in range(start_column, end_column):
        label = subheader_cells[column_index]
        if is_color_grade_label(label, rule_set=rule_set):
            color_columns.append((column_index, str(label).replace("\n", "")))

    return color_columns


def build_color_summary(
    row: pd.Series,
    color_columns: ColorColumns,
    rule_set: RuleSet | None = None,
) -> str:
    """把多列颜色级比例合并成统一的“颜色级:占比%”文本。"""

    active_rule_set = rule_set or load_ruleset()
    parts: list[str] = []
    for column_index, label in color_columns:
        value = row.iloc[column_index]
        percent = parse_float(value, default=float("nan"))
        if pd.isna(percent) or percent <= 0:
            continue
        standard_label = active_rule_set.value_alias_output("颜色级", label) or label
        parts.append(f"{standard_label}:{percent:g}%")

    return "，".join(parts)


def build_record(
    row: pd.Series,
    column_map: ColumnMap,
    color_columns: ColorColumns | None = None,
    rule_set: RuleSet | None = None,
) -> Record | None:
    """从一行 Excel 数据中构建统一字段记录。"""

    active_rule_set = rule_set or load_ruleset()
    basis = parse_float(row.iloc[column_map["基差"]], default=float("nan"))
    if pd.isna(basis):
        return None

    record = {
        field_name: row.iloc[column_index]
        for field_name, column_index in column_map.items()
    }
    for field_name, value in list(record.items()):
        standard_value = active_rule_set.value_alias_output(field_name, value)
        if standard_value:
            record[field_name] = standard_value

    if color_columns:
        color_summary = build_color_summary(row, color_columns, active_rule_set)
        if color_summary:
            record["颜色级"] = color_summary

    record["_基差"] = basis
    record["_得分"] = score_record(record, rule_set=active_rule_set)
    record["_与基差差距"] = basis - record["_得分"]

    return record


def format_output_frame(
    records: list[Record],
    rule_set: RuleSet | None = None,
) -> pd.DataFrame:
    """筛选并整理最终输出 DataFrame。"""

    active_rule_set = rule_set or load_ruleset()
    frame = pd.DataFrame(records)
    filter_rules = active_rule_set.filter_rules()
    if filter_rules:
        mask = pd.Series(False, index=frame.index)
        for rule in filter_rules:
            mask = mask | frame.apply(
                lambda row: filter_rule_matches(row, rule, active_rule_set),
                axis=1,
            )
        kept = frame[mask].copy()
    else:
        kept = frame.copy()

    kept = kept.rename(columns={"_得分": "得分", "_与基差差距": "与基差差距"})
    available_columns = [
        column for column in active_rule_set.output_fields if column in kept.columns
    ]
    return kept[available_columns]


def filter_rule_matches(
    row: pd.Series,
    rule: DataRule,
    rule_set: RuleSet,
) -> bool:
    """判断单条记录是否命中过滤规则。"""

    source_value = row.get(rule.field_name)
    if rule.rule_type == "keyword_filter":
        return rule.match_key in normalize_text(source_value)

    if rule.field_name == "与基差差距":
        source_value = row.get("_与基差差距")
        numeric_value = parse_float(source_value, default=float("nan"))
    else:
        source_value = row.get(rule.field_name)
        if not rule_set.rule_matches_value(rule, source_value):
            return False
        if rule.field_name == "颜色级":
            numeric_value = extract_max_color_percent(source_value, rule_set)
        else:
            numeric_value = parse_float(source_value, default=float("nan"))

    if pd.isna(numeric_value):
        return False
    return matches_range(numeric_value, rule)


def process_sheet(
    raw_frame: pd.DataFrame,
    log: ProgressLogger | None = None,
    sheet_name: str = "",
) -> pd.DataFrame | None:
    """处理单个 sheet；非数据表或无保留行时返回 None。"""

    rule_set = load_ruleset()
    log_prefix = f"[{sheet_name}] " if sheet_name else ""
    header_row = find_header_row(raw_frame, rule_set=rule_set)
    if header_row < 0:
        if log:
            log(f"{log_prefix}未识别到表头，跳过")
        return None

    if log:
        log(f"{log_prefix}识别到表头行: 第 {header_row + 1} 行")

    column_map = build_column_map(
        raw_frame.iloc[header_row].tolist(),
        rule_set=rule_set,
    )
    missing_columns = [
        column_name for column_name in rule_set.required_fields if column_name not in column_map
    ]
    if missing_columns:
        if log:
            log(f"{log_prefix}缺少必需字段: {', '.join(missing_columns)}，跳过")
        return None

    body = raw_frame.iloc[header_row + 1 :].reset_index(drop=True)
    color_columns = detect_color_columns(raw_frame, header_row, column_map, rule_set)
    records = [
        record
        for _, row in body.iterrows()
        if (record := build_record(row, column_map, color_columns, rule_set)) is not None
    ]

    if log:
        log(f"{log_prefix}数据行 {len(body)} 行，有效基差行 {len(records)} 行")

    if not records:
        if log:
            log(f"{log_prefix}没有可评分数据，跳过")
        return None

    output_frame = format_output_frame(records, rule_set=rule_set)
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
