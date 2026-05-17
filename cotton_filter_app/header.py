"""Excel header detection and column mapping."""

from __future__ import annotations

from typing import Any, Sequence

import pandas as pd

from .constants import HEADER_SCAN_ROWS
from .models import ColumnMap
from .rules import RuleSet, load_ruleset
from .text_utils import normalize_text


def build_column_map(
    header_cells: Sequence[Any],
    rule_set: RuleSet | None = None,
) -> ColumnMap:
    """根据本地列名规则返回统一字段名到列索引的映射。"""

    active_rule_set = rule_set or load_ruleset()
    candidates: list[tuple[int, int, str, int]] = []

    for column_index, cell_value in enumerate(header_cells):
        for rule in active_rule_set.column_candidates(cell_value):
            candidates.append(
                (
                    rule.sort_order,
                    column_index,
                    rule.field_name,
                    column_index,
                )
            )

    column_map: ColumnMap = {}
    used_columns: set[int] = set()

    for _, _, field_name, column_index in sorted(candidates):
        if field_name in column_map or column_index in used_columns:
            continue
        column_map[field_name] = column_index
        used_columns.add(column_index)

    return column_map


def find_header_row(
    raw_frame: pd.DataFrame,
    max_scan_rows: int = HEADER_SCAN_ROWS,
    rule_set: RuleSet | None = None,
) -> int:
    """在前几行中寻找最像表头的行，找不到时返回 -1。"""

    active_rule_set = rule_set or load_ruleset()
    best_row = -1
    best_score = 0
    scan_limit = min(max_scan_rows, len(raw_frame))

    for row_index in range(scan_limit):
        column_map = build_column_map(
            raw_frame.iloc[row_index].tolist(),
            rule_set=active_rule_set,
        )
        required_hits = sum(
            1 for column_name in active_rule_set.required_fields if column_name in column_map
        )
        score = required_hits * 100 + len(column_map)

        if score > best_score:
            best_row = row_index
            best_score = score

    minimum_score = len(active_rule_set.required_fields) * 100
    return best_row if best_score >= minimum_score else -1
