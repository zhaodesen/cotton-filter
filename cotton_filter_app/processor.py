"""Excel sheet and workbook processing."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pandas as pd

from .header import build_column_map, find_header_row
from .models import ColumnMap, ProcessedRow, Record, SheetProcessResult
from .rules import ColumnRule, DataRule, RuleSet, load_ruleset, matches_range
from .scoring import extract_color_percent, parse_float, score_record
from .text_utils import normalize_text

ProgressLogger = Callable[[str], None]
ColorColumns = list[tuple[int, str]]
ISSUE_COLUMNS = ("异常类型", "异常说明", "Excel行号", "标准字段", "原列名", "原值")


def is_empty_cell(value: object) -> bool:
    """判断单元格是否为空。"""

    return value is None or pd.isna(value) or str(value).strip() == ""


def is_color_grade_label(value: object, rule_set: RuleSet | None = None) -> bool:
    """判断组合表头中的子列是否是颜色级标签。"""

    active_rule_set = rule_set or load_ruleset()
    return active_rule_set.is_value_alias("颜色级", value)


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


def clean_header_label(value: object) -> str:
    """把原始表头整理成可写出的列名。"""

    if is_empty_cell(value):
        return ""
    return str(value).replace("\n", " ").strip()


def make_unique_headers(headers: list[str]) -> list[str]:
    """避免输出 Excel 中重复列名造成歧义。"""

    seen: dict[str, int] = {}
    unique_headers: list[str] = []
    for index, header in enumerate(headers, start=1):
        base = header or f"列{index}"
        count = seen.get(base, 0) + 1
        seen[base] = count
        unique_headers.append(base if count == 1 else f"{base}_{count}")
    return unique_headers


def build_original_headers(
    raw_frame: pd.DataFrame,
    header_row: int,
    color_columns: ColorColumns | None = None,
) -> list[str]:
    """保留原表头；组合颜色级子列补上父级表头，便于追溯。"""

    header_cells = raw_frame.iloc[header_row].tolist()
    subheader_cells = (
        raw_frame.iloc[header_row + 1].tolist()
        if header_row + 1 < len(raw_frame)
        else []
    )
    color_column_indexes = {column_index for column_index, _ in color_columns or []}
    current_group = ""
    headers: list[str] = []

    for column_index, cell_value in enumerate(header_cells):
        header = clean_header_label(cell_value)
        if header:
            current_group = header

        subheader = (
            clean_header_label(subheader_cells[column_index])
            if column_index < len(subheader_cells)
            else ""
        )
        if (
            subheader
            and current_group
            and (column_index in color_column_indexes or "颜色" in current_group)
        ):
            headers.append(f"{current_group or header}/{subheader}")
        else:
            headers.append(header)

    return make_unique_headers(headers)


def raw_row_to_dict(row: pd.Series, headers: list[str]) -> Record:
    """按原始列名保留一行 Excel 数据。"""

    return {
        header: row.iloc[column_index]
        for column_index, header in enumerate(headers)
    }


def issue_row(
    *,
    issue_type: str,
    message: str,
    headers: list[str],
    raw_row: pd.Series | None = None,
    excel_row_number: int | None = None,
    field_name: str = "",
    original_column: str = "",
    original_value: object = "",
) -> Record:
    """构造识别异常行，行级异常会附带原始 Excel 数据。"""

    row_data = raw_row_to_dict(raw_row, headers) if raw_row is not None else {}
    row_data.update(
        {
            "异常类型": issue_type,
            "异常说明": message,
            "Excel行号": excel_row_number,
            "标准字段": field_name,
            "原列名": original_column,
            "原值": original_value,
        }
    )
    return row_data


def find_similar_column_rule(
    column_name: str,
    rule_set: RuleSet,
) -> ColumnRule | None:
    """查找疑似已有列名规则但未精确命中的表头。"""

    column_key = normalize_text(column_name)
    if not column_key:
        return None

    candidates = [
        rule
        for rule in rule_set.enabled_column_rules()
        if rule.alias_key
        and rule.alias_key != column_key
        and column_key.startswith(rule.alias_key)
    ]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda rule: (len(rule.alias_key), -rule.sort_order, -(rule.id or 0)),
        reverse=True,
    )[0]


def append_unmapped_column_issues(
    issue_rows: list[Record],
    headers: list[str],
    column_map: ColumnMap,
    color_columns: ColorColumns,
    rule_set: RuleSet,
) -> None:
    """提示疑似列名规则缺失的原始列。"""

    mapped_columns = set(column_map.values())
    color_column_indexes = {column_index for column_index, _ in color_columns}
    for column_index, original_column in enumerate(headers):
        if (
            not original_column
            or column_index in mapped_columns
            or column_index in color_column_indexes
        ):
            continue

        similar_rule = find_similar_column_rule(original_column, rule_set)
        if similar_rule is None:
            continue

        issue_rows.append(
            issue_row(
                issue_type="列名未覆盖",
                message=(
                    f"该原始列名疑似 {similar_rule.field_name}，"
                    "但未命中列名规则，请在列名规则中新增对应别名"
                ),
                headers=headers,
                field_name=similar_rule.field_name,
                original_column=original_column,
            )
        )


def value_alias_rules_exist(rule_set: RuleSet, field_name: str) -> bool:
    """判断某字段是否有值别名规则。"""

    return any(
        rule.rule_type == "value_alias" and rule.field_name == field_name
        for rule in rule_set.enabled_data_rules()
    )


def value_is_covered_by_alias(
    rule_set: RuleSet,
    field_name: str,
    value: object,
) -> bool:
    """判断单元格值是否被当前字段的值别名规则覆盖。"""

    if not value_alias_rules_exist(rule_set, field_name) or is_empty_cell(value):
        return True
    if rule_set.value_alias_output(field_name, value) is not None:
        return True

    value_key = normalize_text(value)
    return any(
        rule.rule_type == "value_alias"
        and rule.field_name == field_name
        and (
            (bool(rule.match_key) and rule.match_key in value_key)
            or (
                bool(normalize_text(rule.output_value))
                and normalize_text(rule.output_value) in value_key
            )
        )
        for rule in rule_set.enabled_data_rules()
    )


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

    record["_得分"] = score_record(record, rule_set=active_rule_set)
    record["_与基差差距"] = basis - record["_得分"]

    return record


def build_filter_mask(
    frame: pd.DataFrame,
    rule_set: RuleSet,
) -> pd.Series:
    """根据过滤规则生成命中掩码。"""

    filter_rules = rule_set.filter_rules()
    if not filter_rules:
        return pd.Series(True, index=frame.index)

    keyword_rules = [
        rule for rule in filter_rules if rule.rule_type == "keyword_filter"
    ]
    range_rules = [
        rule for rule in filter_rules if rule.rule_type != "keyword_filter"
    ]

    excluded = pd.Series(False, index=frame.index)
    for rule in keyword_rules:
        rule_excluded = frame.apply(
            lambda row: filter_rule_matches(row, rule, rule_set),
            axis=1,
        )
        excluded = excluded | rule_excluded

    if not range_rules:
        return ~excluded

    grouped: dict[str, list[DataRule]] = {}
    for rule in range_rules:
        grouped.setdefault(rule.field_name, []).append(rule)

    mask = ~excluded
    for field_rules in grouped.values():
        candidate_frame = frame[mask]
        if candidate_frame.empty:
            return mask
        field_mask = pd.Series(False, index=frame.index)
        field_mask.loc[candidate_frame.index] = candidate_frame.apply(
            lambda row: any(
                filter_rule_matches(row, rule, rule_set) for rule in field_rules
            ),
            axis=1,
        )
        mask = mask & field_mask
    return mask


def format_output_frame(
    records: list[Record],
    rule_set: RuleSet | None = None,
) -> pd.DataFrame:
    """筛选并整理最终输出 DataFrame。"""

    active_rule_set = rule_set or load_ruleset()
    frame = pd.DataFrame(records)
    kept = frame[build_filter_mask(frame, active_rule_set)].copy()

    kept = kept.rename(columns={"_得分": "得分", "_与基差差距": "与基差差距"})
    available_columns = [
        column for column in active_rule_set.output_fields if column in kept.columns
    ]
    return kept[available_columns]


def format_original_output_frame(
    processed_rows: list[ProcessedRow],
    headers: list[str],
    rule_set: RuleSet,
) -> pd.DataFrame:
    """按原始列名输出筛选命中的原始行，并追加计算列。"""

    if not processed_rows:
        return pd.DataFrame(columns=[*headers, "得分", "与基差差距"])

    record_frame = pd.DataFrame([row.record for row in processed_rows])
    kept_rows = [
        row
        for row, keep in zip(
            processed_rows,
            build_filter_mask(record_frame, rule_set).tolist(),
        )
        if keep
    ]
    output_rows: list[Record] = []
    for processed_row in kept_rows:
        row_data = raw_row_to_dict(processed_row.raw_row, headers)
        row_data["得分"] = processed_row.record.get("_得分")
        row_data["与基差差距"] = processed_row.record.get("_与基差差距")
        output_rows.append(row_data)

    return pd.DataFrame(output_rows, columns=[*headers, "得分", "与基差差距"])


def filter_rule_matches(
    row: pd.Series,
    rule: DataRule,
    rule_set: RuleSet,
) -> bool:
    """判断单条记录是否命中过滤规则。

    关键词过滤是排除规则：返回 True 表示该行需要过滤出去。
    """

    source_value = row.get(rule.field_name)
    if rule.rule_type == "keyword_filter":
        return rule.match_key in normalize_text(source_value)

    if rule.field_name == "与基差差距":
        source_value = row.get("_与基差差距")
        numeric_value = parse_float(source_value, default=float("nan"))
    elif rule.field_name == "颜色级":
        source_value = row.get(rule.field_name)
        numeric_value = extract_color_percent(source_value, rule, rule_set)
    else:
        source_value = row.get(rule.field_name)
        if not rule_set.rule_matches_value(rule, source_value):
            return False
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


def process_sheet_result(
    raw_frame: pd.DataFrame,
    log: ProgressLogger | None = None,
    sheet_name: str = "",
) -> SheetProcessResult:
    """处理单个 sheet，返回原始列输出结果和识别异常。"""

    rule_set = load_ruleset()
    log_prefix = f"[{sheet_name}] " if sheet_name else ""
    header_row = find_header_row(raw_frame, rule_set=rule_set)
    if header_row < 0:
        issue = issue_row(
            issue_type="表头未识别",
            message="前置行中未识别到满足必需字段的表头",
            headers=[],
        )
        if log:
            log(f"{log_prefix}未识别到表头，跳过")
        return SheetProcessResult(
            normal_frame=pd.DataFrame(),
            issue_frame=pd.DataFrame([issue], columns=ISSUE_COLUMNS),
        )

    if log:
        log(f"{log_prefix}识别到表头行: 第 {header_row + 1} 行")

    header_cells = raw_frame.iloc[header_row].tolist()
    column_map = build_column_map(header_cells, rule_set=rule_set)
    color_columns = detect_color_columns(raw_frame, header_row, column_map, rule_set)
    headers = build_original_headers(raw_frame, header_row, color_columns)
    issue_rows: list[Record] = []
    append_unmapped_column_issues(
        issue_rows,
        headers,
        column_map,
        color_columns,
        rule_set,
    )

    missing_columns = [
        column_name for column_name in rule_set.required_fields if column_name not in column_map
    ]
    for field_name in missing_columns:
        issue_rows.append(
            issue_row(
                issue_type="列名未覆盖",
                message=f"缺少必需字段 {field_name}，请在列名规则中新增对应别名",
                headers=headers,
                field_name=field_name,
            )
        )

    if missing_columns:
        if log:
            log(f"{log_prefix}缺少必需字段: {', '.join(missing_columns)}，跳过")
        return SheetProcessResult(
            normal_frame=pd.DataFrame(columns=[*headers, "得分", "与基差差距"]),
            issue_frame=pd.DataFrame(issue_rows),
        )

    body = raw_frame.iloc[header_row + 1 :].reset_index(drop=True)
    processed_rows: list[ProcessedRow] = []

    for body_index, row in body.iterrows():
        excel_row_number = header_row + body_index + 2
        basis_value = row.iloc[column_map["基差"]]
        if pd.isna(parse_float(basis_value, default=float("nan"))):
            if not is_empty_cell(basis_value):
                issue_rows.append(
                    issue_row(
                        issue_type="数据未识别",
                        message="基差无法解析为数字，该行不会参与筛选",
                        headers=headers,
                        raw_row=row,
                        excel_row_number=excel_row_number,
                        field_name="基差",
                        original_column=headers[column_map["基差"]],
                        original_value=basis_value,
                    )
                )
            continue

        record = build_record(row, column_map, color_columns, rule_set)
        if record is None:
            continue

        processed_rows.append(
            ProcessedRow(
                record=record,
                raw_row=row,
                excel_row_number=excel_row_number,
            )
        )

        for field_name, column_index in column_map.items():
            if field_name == "颜色级" and color_columns:
                continue
            value = row.iloc[column_index]
            if value_is_covered_by_alias(rule_set, field_name, value):
                continue
            issue_rows.append(
                issue_row(
                    issue_type="数据规则未覆盖",
                    message=f"{field_name} 的值未命中值别名规则，请在数据规则中新增匹配值",
                    headers=headers,
                    raw_row=row,
                    excel_row_number=excel_row_number,
                    field_name=field_name,
                    original_column=headers[column_index],
                    original_value=value,
                )
            )

    normal_frame = format_original_output_frame(processed_rows, headers, rule_set)
    if log:
        log(f"{log_prefix}数据行 {len(body)} 行，有效基差行 {len(processed_rows)} 行")
        log(f"{log_prefix}命中筛选条件 {len(normal_frame)} 行")
    return SheetProcessResult(
        normal_frame=normal_frame,
        issue_frame=pd.DataFrame(issue_rows, columns=ISSUE_COLUMNS),
    )


def filter_file(src: Path, dst: Path, log: ProgressLogger | None = None) -> int:
    """处理单个 Excel 文件，返回保留行数。"""

    if log:
        log(f"读取工作簿: {src.name}")
    sheet_results: list[pd.DataFrame] = []
    issue_results: list[pd.DataFrame] = []

    with pd.ExcelFile(src) as excel_file:
        if log:
            log(f"发现 {len(excel_file.sheet_names)} 个 sheet: {', '.join(excel_file.sheet_names)}")

        for sheet_name in excel_file.sheet_names:
            if log:
                log(f"开始读取 sheet: {sheet_name}")
            raw_frame = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
            if log:
                log(f"[{sheet_name}] 原始尺寸: {len(raw_frame)} 行 x {len(raw_frame.columns)} 列")
            result = process_sheet_result(raw_frame, log=log, sheet_name=sheet_name)

            normal_frame = result.normal_frame.copy()
            normal_frame.insert(0, "来源sheet", sheet_name)
            sheet_results.append(normal_frame)

            issue_frame = result.issue_frame.copy()
            issue_frame.insert(0, "来源sheet", sheet_name)
            issue_results.append(issue_frame)

    output_frame = (
        pd.concat(sheet_results, ignore_index=True)
        if sheet_results
        else pd.DataFrame()
    )
    issue_frame = (
        pd.concat(issue_results, ignore_index=True)
        if issue_results
        else pd.DataFrame(columns=["来源sheet", *ISSUE_COLUMNS])
    )
    if log:
        log(
            f"写出结果: {dst.name}，筛选 {len(output_frame)} 行，识别异常 {len(issue_frame)} 条"
        )
    with pd.ExcelWriter(dst) as writer:
        output_frame.to_excel(writer, sheet_name="筛选结果", index=False)
        issue_frame.to_excel(writer, sheet_name="识别异常", index=False)
    return len(output_frame)
